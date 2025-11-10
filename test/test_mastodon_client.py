# tests/test_mastodon_client.py

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import the module we are testing
from mastodon_finder import mastodon_client
from mastodon_finder.mastodon_client import (
    _get_from_cache,
    _write_to_cache,
    get_account,
    get_client,
    get_my_following_ids,
    search_statuses_by_hashtag,
    search_statuses_by_keyword,
)
from mastodon_finder.settings import Settings

# --- Fixtures ---


@pytest.fixture
def mock_settings() -> Settings:
    """Returns a Settings object with mock credentials."""
    settings = Settings()
    settings.env.MASTODON_BASE_URL = "https://test.instance.com"
    settings.env.MASTODON_ACCESS_TOKEN = "test_token_123"
    return settings


@pytest.fixture
def isolated_cache_dir(tmp_path: Path, monkeypatch):
    """
    Redirects the cache directories to a temporary path and
    ensures caching is enabled.
    """
    cache_dir = tmp_path / ".cache"
    cache_me_dir = tmp_path / ".cache_me"
    cache_dir.mkdir()
    cache_me_dir.mkdir()

    monkeypatch.setattr(mastodon_client, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(mastodon_client, "CACHE_ME_DIR", cache_me_dir)
    monkeypatch.setattr(mastodon_client, "CACHE_ENABLED", True)

    return cache_dir, cache_me_dir


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    """
    Ensures the client singleton is reset before every test,
    preventing state leakage.
    """
    monkeypatch.setattr(mastodon_client, "_CLIENT_SINGLETON", None)
    # Also reset the @lru_cache for _get_my_account_id
    mastodon_client._get_my_account_id.cache_clear()


@pytest.fixture
def mock_mastodon_lib():
    """Mocks the mastodon.Mastodon class and its key methods."""
    # We patch the class where it's *imported*
    with patch("mastodon_finder.mastodon_client.Mastodon") as mock_class:
        mock_instance = Mock()
        # Mock methods called during initialization and use
        mock_instance.retrieve_mastodon_version.return_value = "4.0.0"
        mock_instance.me.return_value = {"id": 999}
        mock_instance.account.return_value = {"id": 123, "acct": "test"}
        mock_instance.search.return_value = {"statuses": [{"id": 1}]}

        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def initialized_client(
    mock_settings, mock_mastodon_lib, isolated_cache_dir, monkeypatch
):
    """
    Fixture to get a fully initialized client, mocking
    the cache cleaner for simplicity.
    """
    # Mock the cache cleaner as it's tested separately
    monkeypatch.setattr(mastodon_client, "_clean_old_cache_files", Mock())
    # This call initializes the singleton
    get_client(mock_settings)
    # Reset mocks *after* init so we can test API calls
    mock_mastodon_lib.reset_mock()
    return mock_mastodon_lib


# --- Tests for Cache Helper Functions ---


def test_cache_write_and_read(isolated_cache_dir):
    """Tests that data can be written to and read from the cache."""
    cache_dir, _ = isolated_cache_dir
    key = "test_key"
    data = {"hello": "world"}

    _write_to_cache(key, data, cache_dir)

    # Check that the file was created
    cache_file = cache_dir / f"{key}.pkl"
    assert cache_file.exists()

    # Read it back
    retrieved_data = _get_from_cache(key, cache_dir)
    assert retrieved_data == data


def test_get_from_cache_miss(isolated_cache_dir):
    """Tests that a cache miss returns None."""
    cache_dir, _ = isolated_cache_dir
    assert _get_from_cache("missing_key", cache_dir) is None


def test_get_from_cache_corrupted_file(isolated_cache_dir):
    """Tests that a corrupted pickle file is handled and deleted."""
    cache_dir, _ = isolated_cache_dir
    key = "corrupt_key"
    cache_file = cache_dir / f"{key}.pkl"

    # Write invalid pickle data
    cache_file.write_text("not pickle data")

    assert cache_file.exists()
    retrieved_data = _get_from_cache(key, cache_dir)

    # Should return None and delete the bad file
    assert retrieved_data is None
    assert not cache_file.exists()


# --- Tests for get_client Initialization ---


def test_get_client_not_initialized_error():
    """Tests that calling get_client without settings first raises a ValueError."""
    with pytest.raises(ValueError, match="client not initialized"):
        get_client()


def test_get_client_first_call_success(mock_settings, mock_mastodon_lib, monkeypatch):
    """Tests that the first call initializes the Mastodon lib correctly."""
    mock_clean_cache = Mock()
    monkeypatch.setattr(mastodon_client, "_clean_old_cache_files", mock_clean_cache)

    # Patch the class to check how it's called
    with patch("mastodon_finder.mastodon_client.Mastodon") as mock_class:
        mock_class.return_value = mock_mastodon_lib

        client = get_client(mock_settings)

        # Check that the cache cleaner was called
        mock_clean_cache.assert_called_once()

        # Check that Mastodon lib was initialized correctly
        mock_class.assert_called_once_with(
            access_token="test_token_123",
            api_base_url="https://test.instance.com",  # no slash
            ratelimit_method="wait",
        )
        # Check that credentials were verified
        mock_mastodon_lib.retrieve_mastodon_version.assert_called_once()
        assert client == mock_mastodon_lib


def test_get_client_is_singleton(mock_settings, mock_mastodon_lib, monkeypatch):
    """Tests that subsequent calls return the same client instance."""
    monkeypatch.setattr(mastodon_client, "_clean_old_cache_files", Mock())

    client1 = get_client(mock_settings)
    client2 = get_client()  # No settings on second call

    assert client1 is client2
    # Check that init logic (e.g., version check) only ran once
    assert mock_mastodon_lib.retrieve_mastodon_version.call_count == 1


# --- Tests for API Function Caching & Logic ---


def test_get_account_caching_behavior(initialized_client):
    """
    Tests the full cache-miss -> cache-hit cycle for an API function.
    """
    mock_client = initialized_client
    mock_client.account.return_value = {"id": 123, "acct": "test@foo.com"}

    # 1. First call (Cache MISS)
    result1 = get_account(123)

    # Check that the API was called
    mock_client.account.assert_called_once_with(123)
    assert result1 == {"id": 123, "acct": "test@foo.com"}

    # 2. Second call (Cache HIT)
    mock_client.account.reset_mock()  # Reset mock before next call
    result2 = get_account(123)

    # Check that the API was NOT called
    mock_client.account.assert_not_called()
    assert result2 == {"id": 123, "acct": "test@foo.com"}


def test_search_statuses_by_keyword(initialized_client):
    """Tests the non-paginated search function."""
    mock_client = initialized_client
    mock_client.search.return_value = {"statuses": [{"id": 10}]}

    result = search_statuses_by_keyword("python", max_pages=1)

    mock_client.search.assert_called_once_with(
        q="python", result_type="statuses", resolve=True
    )
    assert result == [{"id": 10}]


def test_search_statuses_by_hashtag_pagination(initialized_client):
    """Tests the helper for paginated timeline results."""
    mock_client = initialized_client

    page1 = [{"id": 1}]
    page2 = [{"id": 2}]

    # Mock the paginated call
    mock_client.timeline.return_value = page1
    # fetch_next returns the next page, then None to stop
    mock_client.fetch_next.side_effect = [page2, None]

    result = search_statuses_by_hashtag("rust", max_pages=3, page_size=1)

    mock_client.timeline.assert_called_once_with(limit=1, timeline="tag/rust")
    assert mock_client.fetch_next.call_count == 2
    assert result == [{"id": 1}, {"id": 2}]


def test_get_my_following_ids(initialized_client, monkeypatch):
    """Tests the pagination logic for get_my_following_ids."""
    mock_client = initialized_client

    # Mock _get_my_account_id to return the test ID
    monkeypatch.setattr(mastodon_client, "_get_my_account_id", lambda: 999)

    first_page = [{"id": 10}]
    # fetch_remaining returns the *full* list
    all_following = [{"id": 10}, {"id": 20}, {"id": 30}]

    mock_client.account_following.return_value = first_page
    mock_client.fetch_remaining.return_value = all_following

    result = get_my_following_ids()

    # Check that client.me() was used (implicitly by the patch)
    mock_client.account_following.assert_called_with(id=999, limit=80)
    mock_client.fetch_remaining.assert_called_with(first_page)
    assert result == {10, 20, 30}
