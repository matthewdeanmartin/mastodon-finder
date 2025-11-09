import hashlib
import json
import logging
import pickle
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Set

from mastodon import (
    Mastodon,
    MastodonAPIError,
    MastodonNetworkError,
    MastodonRatelimitError,
)

import mastodon_finder.config as config

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Caching Setup ---
CACHE_ENABLED = True
CACHE_DIR = Path(".cache")
CACHE_ME_DIR = Path(".cache_me")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_ME_DIR.mkdir(exist_ok=True)


def _get_cache_key(func_name: str, *args: Any, **kwargs: Any) -> str:
    """Creates a stable cache key (hash) from function name and args."""
    key_data = {"func": func_name, "args": args, "kwargs": kwargs}
    # Use sort_keys=True for consistent hashing
    key_str = json.dumps(key_data, sort_keys=True)
    # Use md5 for a short, effective hash
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_from_cache(key: str, cache_dir: Path) -> Optional[Any]:
    """Reads a result from the specified file system cache using pickle."""
    if not CACHE_ENABLED:
        return None
    cache_file = cache_dir / f"{key}.pkl"  # Use .pkl extension
    if cache_file.exists():
        log.info(f"Cache HIT for key {key} (file: {cache_file.name})")
        try:
            with open(cache_file, "rb") as f:  # Open in read-binary mode
                return pickle.load(f)  # Use pickle.load
        except (pickle.UnpicklingError, EOFError):  # Handle pickle errors
            log.warning(f"Cache file {cache_file} corrupted. Deleting.")
            cache_file.unlink()
    log.info(f"Cache MISS for key {key} (file: {cache_file.name})")
    return None


def _write_to_cache(key: str, data: Any, cache_dir: Path):
    """Writes a result to the specified file system cache using pickle."""
    if not CACHE_ENABLED:
        return
    cache_file = cache_dir / f"{key}.pkl"  # Use .pkl extension
    try:
        with open(cache_file, "wb") as f:  # Open in write-binary mode
            # Use pickle.dump with the highest protocol
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        log.warning(f"Failed to write cache file {cache_file}: {e}")


# --- End Caching Setup ---


# --- Client Initialization ---
# Use lru_cache(maxsize=1) as a simple, thread-safe way to create a singleton
# that is initialized on first use, not on import. This makes the module
# safe to import in unit tests.
@lru_cache(maxsize=1)
def get_client() -> Mastodon:
    """
    Initializes and returns a singleton Mastodon client.
    This is lazy-loaded on first call, making the module testable.
    """
    # Sanitize base URL
    if not config.MASTODON_BASE_URL:
        # This will be caught by validate_config(), but good to check.
        raise ConnectionError("MASTODON_BASE_URL is not set.")

    # Strip any trailing slashes to prevent 404 errors on endpoints
    api_base_url = config.MASTODON_BASE_URL.rstrip("/")

    log.info(f"Initializing Mastodon client for {api_base_url}...")
    try:
        client = Mastodon(
            access_token=config.MASTODON_ACCESS_TOKEN,
            api_base_url=api_base_url,
            ratelimit_method="wait",  # Let Mastodon.py handle pauses
        )
        # verify_credentials() is the first network call
        client.retrieve_mastodon_version()
        log.info("Successfully connected and verified credentials.")
        return client
    except Exception as e:
        log.error(f"Failed to connect to Mastodon API: {e}")
        # Raise the exception so the caller (main.py) can handle it
        raise ConnectionError(f"Failed to connect to Mastodon API: {e}") from e


# --- Helper Function for Pagination (from Cheat Sheet) ---
def _fetch_paginated_results(
    fetch_func_name: str,  # Pass the name of the method to call
    max_pages: int,
    limit_per_page: int,
    **kwargs,
) -> List[dict]:
    """Generic helper to walk timeline/search pages."""
    all_results = []
    # Get the initialized client. This is the first point
    # where get_client() will be executed.
    client = get_client()

    try:
        # Get the actual function (e.g., client.search) from the client object
        fetch_func = getattr(client, fetch_func_name)

        page = fetch_func(limit=limit_per_page, **kwargs)
        page_count = 0
        while page and page_count < max_pages:
            all_results.extend(page)
            page_count += 1
            log.info(f"Fetched page {page_count} ({len(page)} items)...")
            page = client.fetch_next(page)

    except (MastodonNetworkError, MastodonAPIError, MastodonRatelimitError) as e:
        log.warning(f"Error during pagination for {fetch_func_name}: {e}")
    except AttributeError:
        log.error(f"Client object does not have method '{fetch_func_name}'")
        raise

    return all_results


# --- Function to get user's own ID ---
@lru_cache(maxsize=1)
def _get_my_account_id() -> Optional[int]:
    """
    Fetches the authenticated user's account ID.
    Caches the result.
    """
    key = _get_cache_key("_get_my_account_id")
    cached_data = _get_from_cache(key, CACHE_ME_DIR)
    if cached_data is not None:
        return cached_data.get("id")

    log.info("Fetching authenticated user's account ID...")
    client = get_client()
    try:
        my_account_info = client.me()
        _write_to_cache(key, my_account_info, CACHE_ME_DIR)
        return my_account_info.get("id")
    except Exception as e:
        log.error(f"Could not verify credentials to get user ID: {e}")
        raise


# --- Function to get following list ---
def get_my_following_ids() -> Set[int]:
    """
    Fetches the set of account IDs the user currently follows.
    """
    my_id = _get_my_account_id()
    if not my_id:
        log.error("Cannot fetch following list: User ID unknown.")
        sys.exit(3)

    # Caching wrapper
    key = _get_cache_key("get_my_following_ids", my_id)
    cached_data = _get_from_cache(key, CACHE_ME_DIR)
    if cached_data is not None:
        return set(cached_data)  # Re-hydrate from list to set

    log.info(f"Fetching following list for account {my_id}...")

    # The _fetch_paginated_results helper doesn't work for this endpoint.
    # We must call account_following() directly and then use fetch_remaining().
    try:
        client = get_client()
        # Fetch the first page (limit=40 is default, 80 is max)
        # We pass 'id' as a keyword arg to be explicit.
        first_page = client.account_following(id=my_id, limit=80)

        # Fetch all remaining pages
        all_following = client.fetch_remaining(first_page)

        following_ids = {acct["id"] for acct in all_following}

        _write_to_cache(key, list(following_ids), CACHE_ME_DIR)  # Cache as a list
        return following_ids
    except (MastodonNetworkError, MastodonAPIError) as e:
        log.error(f"Could not fetch following list: {e}")
        raise
    except Exception as e:
        log.error(f"An unexpected error occurred fetching following list: {e}")
        raise


# --- API Functions (from Spec) ---


def search_statuses_by_keyword(keyword: str, max_pages: int) -> List[Any]:
    """
    Searches for statuses matching a keyword.
    Uses search(result_type="statuses") as per cheat sheet.

    --- BUG FIX ---
    The search() endpoint is NOT paginated like timelines.
    It returns a single dict. We cannot use _fetch_paginated_results.
    The max_pages argument is ignored for this specific function.
    """
    # Caching wrapper
    # Note: max_pages is included in the key for consistency, though unused
    key = _get_cache_key("search_statuses_by_keyword", keyword, max_pages)

    cached_data = _get_from_cache(key, CACHE_DIR)
    if cached_data is not None:
        return cached_data  # type: ignore

    log.info(
        f"Searching for keyword: '{keyword}'... (Note: max_pages is ignored for keyword search)"
    )
    client = get_client()

    try:
        results = client.search(
            q=keyword, result_type="statuses", resolve=True  # Attempt federated lookup
        )
        # The search result is a dict: {'accounts': [], 'statuses': [], 'hashtags': []}
        data = results.get("statuses", [])
        _write_to_cache(key, data, CACHE_DIR)
        return data
    except (MastodonNetworkError, MastodonAPIError, MastodonRatelimitError) as e:
        log.warning(f"Error during keyword search for '{keyword}': {e}")
        return []


def search_statuses_by_hashtag(tag: str, max_pages: int) -> List[Any]:
    """
    Fetches statuses for a specific hashtag timeline.
    Uses timeline("tag/...") as per cheat sheet.
    """
    # Caching wrapper
    key = _get_cache_key("search_statuses_by_hashtag", tag, max_pages)
    cached_data = _get_from_cache(key, CACHE_DIR)
    if cached_data is not None:
        return cached_data  # type: ignore

    log.info(f"Searching for hashtag: '#{tag}'...")
    timeline_name = f"tag/{tag.lstrip('#')}"
    data = _fetch_paginated_results(
        fetch_func_name="timeline",  # Pass name of method
        max_pages=max_pages,
        limit_per_page=config.DEFAULT_PAGE_LIMIT,
        timeline=timeline_name,
    )

    _write_to_cache(key, data, CACHE_DIR)
    return data


def search_accounts_by_keyword(keyword: str) -> List[Any]:
    """
    Searches for accounts matching a keyword in their profile.
    Uses search(result_type="accounts").
    This endpoint is not paginated.
    """
    # Caching wrapper
    key = _get_cache_key("search_accounts_by_keyword", keyword)
    cached_data = _get_from_cache(key, CACHE_DIR)
    if cached_data is not None:
        return cached_data  # type: ignore

    log.info(f"Searching for accounts matching: '{keyword}'...")
    client = get_client()

    try:
        results = client.search(
            q=keyword, result_type="accounts", resolve=True  # Attempt federated lookup
        )
        # The search result is a dict: {'accounts': [], 'statuses': [], 'hashtags': []}
        data = results.get("accounts", [])
        # +++ MODIFIED: Use CACHE_DIR +++
        _write_to_cache(key, data, CACHE_DIR)
        return data
    except (MastodonNetworkError, MastodonAPIError, MastodonRatelimitError) as e:
        log.warning(f"Error during account search for '{keyword}': {e}")
        return []


def get_account(account_id: int) -> Optional[Any]:
    """
    Gets the full, canonical account info.
    """
    # Caching wrapper
    key = _get_cache_key("get_account", account_id)
    # +++ MODIFIED: Use CACHE_DIR +++
    cached_data = _get_from_cache(key, CACHE_DIR)
    if cached_data is not None:
        return cached_data  # type: ignore

    client = get_client()  # Get client
    try:
        data = client.account(account_id)
        # +++ MODIFIED: Use CACHE_DIR +++
        _write_to_cache(key, data, CACHE_DIR)
        return data
    except (MastodonNetworkError, MastodonAPIError) as e:
        log.error(f"Could not fetch account {account_id}: {e}")
        return None


def get_account_statuses(
    account_id: int, limit: int, exclude_reblogs: bool = True
) -> Optional[List[Any]]:
    """
    Gets recent statuses, excluding reblogs as specified.
    """
    # Caching wrapper
    key = _get_cache_key("get_account_statuses", account_id, limit, exclude_reblogs)
    # +++ MODIFIED: Use CACHE_DIR +++
    cached_data = _get_from_cache(key, CACHE_DIR)
    if cached_data is not None:
        return cached_data  # type: ignore

    client = get_client()  # Get client
    try:
        data = client.account_statuses(
            account_id,
            limit=limit,
            exclude_reblogs=exclude_reblogs,
            # exclude_replies=True,  <--- [!!] REMOVE THIS LINE [!!]
        )
        # +++ MODIFIED: Use CACHE_DIR +++
        _write_to_cache(key, data, CACHE_DIR)
        return data
    except (MastodonNetworkError, MastodonAPIError) as e:
        log.error(f"Could not fetch statuses for {account_id}: {e}")
        return None
