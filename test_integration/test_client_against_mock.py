"""Drive each mastodon_client function against the mock server.

These prove the finder's client layer — singleton init, version/credential
checks, the search wrappers, the pagination walkers, and the pickle cache — works
against a real HTTP server, not just against unittest.mock stand-ins. Assertions
are about shape and invariants so they'd hold against real Mastodon too.
"""

from __future__ import annotations

from mastodon_finder import mastodon_client
from mastodon_finder.settings import Settings


def _resolved(handle: str) -> int:
    """Resolve a seeded handle to an id, failing if it doesn't resolve.

    Narrows ``int | None`` to ``int`` for the account calls that require it.
    """
    account_id = mastodon_client.lookup_account_id_by_handle(handle)
    assert account_id is not None, f"seeded handle {handle!r} should resolve"
    return account_id


def test_get_client_connects_and_verifies(finder_settings: Settings) -> None:
    client = mastodon_client.get_client(finder_settings)
    # retrieve_mastodon_version() ran during init without raising.
    version = client.retrieve_mastodon_version()
    assert version
    me = client.me()
    assert me["username"] == "me"


def test_get_my_account_id_round_trips(finder_client) -> None:
    account_id = mastodon_client._get_my_account_id()
    assert account_id is not None
    # NB: Mastodon.py returns ids as MaybeSnowflakeIdType, not a plain int — it
    # behaves like an int (int()/== against another wrapper) but is not one.
    # Assert int-coercibility rather than isinstance(int).
    assert int(account_id) > 0
    # The cached "me" doc lives under CACHE_ME_DIR; a second call is a cache hit.
    assert mastodon_client._get_my_account_id() == account_id


def test_search_statuses_by_keyword(finder_client) -> None:
    results = mastodon_client.search_statuses_by_keyword("rust", max_pages=2)
    assert isinstance(results, list)
    assert results, "seeded #rust statuses should match a keyword search"
    # Mastodon.py wraps dicts in AttributeDict — author is reachable as .account.
    assert all(hasattr(s, "account") for s in results)


def test_search_statuses_by_keyword_is_cached(finder_client) -> None:
    first = mastodon_client.search_statuses_by_keyword("ownership", max_pages=1)
    # Second call must come from the pickle cache (same content), not re-hit HTTP.
    second = mastodon_client.search_statuses_by_keyword("ownership", max_pages=1)
    assert [s.id for s in first] == [s.id for s in second]


def test_search_statuses_by_hashtag_paginates(finder_client) -> None:
    results = mastodon_client.search_statuses_by_hashtag("rust", max_pages=3, page_size=1)
    assert isinstance(results, list)
    # Two human #rust posts + one bot #rust post are seeded under the tag.
    ids = {s.id for s in results}
    assert len(ids) >= 2


def test_search_accounts_by_keyword(finder_client) -> None:
    accounts = mastodon_client.search_accounts_by_keyword("Rusty")
    assert isinstance(accounts, list)
    assert any(a.username == "rustacean" for a in accounts)


def test_lookup_account_id_by_handle_exact_match(finder_client) -> None:
    account_id = mastodon_client.lookup_account_id_by_handle("rustacean")
    # See note in test_get_my_account_id_round_trips: ids are int-like, not int.
    assert account_id is not None
    assert int(account_id) > 0
    # Resolving the same handle again is a cache hit returning the same id.
    assert mastodon_client.lookup_account_id_by_handle("rustacean") == account_id


def test_lookup_account_id_by_handle_unknown_returns_none(finder_client) -> None:
    assert mastodon_client.lookup_account_id_by_handle("nobody_here_xyz") is None


def test_get_account_and_statuses(finder_client) -> None:
    rust_id = _resolved("rustacean")
    account = mastodon_client.get_account(rust_id)
    assert account is not None
    assert account.username == "rustacean"

    statuses = mastodon_client.get_account_statuses(rust_id, limit=40, exclude_reblogs=True)
    assert statuses is not None
    assert len(statuses) >= 2
    assert all(s.account.id == rust_id for s in statuses)


def test_get_account_followers_pagination(finder_client) -> None:
    rust_id = _resolved("rustacean")
    followers = mastodon_client.get_account_followers(rust_id, max_followers=-1)
    usernames = {f.username for f in followers}
    assert {"follower_one", "follower_two"} <= usernames


def test_get_account_followers_respects_max(finder_client) -> None:
    rust_id = _resolved("rustacean")
    followers = mastodon_client.get_account_followers(rust_id, max_followers=1)
    assert len(followers) == 1


def test_get_my_following_ids(finder_client) -> None:
    following = mastodon_client.get_my_following_ids()
    # "me" follows "pythonista" in the seed.
    assert isinstance(following, set)
    pythonista_id = mastodon_client.lookup_account_id_by_handle("pythonista")
    assert pythonista_id in following
