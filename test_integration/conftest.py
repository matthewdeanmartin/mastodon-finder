"""Integration fixtures: run the finder's real Mastodon client against a mock.

These tests boot the ``mastodon_mock`` package (published on PyPI) as a uvicorn
server on a free port and point ``mastodon_finder``'s actual client (real
Mastodon.py, real caching, real pagination walkers) at it — no live instance, no
API keys. The finder is read-only, so this is purely about correctness and about
finding gaps between the finder's expectations and the mock.

The whole package self-skips on Python < 3.13 (mastodon_mock's
``requires-python``) or if ``mastodon_mock`` is not installed (install
``mastodon_mock[test]``). The free-port/uvicorn/threading boilerplate this file
used to hand-roll now lives in ``mastodon_mock.testing.MockServer``.

Run just this suite::

    uv run pytest test_integration
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

if sys.version_info < (3, 13):
    pytest.skip(
        "mastodon_mock requires Python >= 3.13; skipping mock integration suite",
        allow_module_level=True,
    )

pytest.importorskip(
    "mastodon_mock",
    reason="install mastodon_mock[test] to run these tests",
)

from mastodon_mock.config import (  # noqa: E402
    SeedAccount,
    SeedConfig,
    SeedFollow,
    SeedStatus,
)
from mastodon_mock.testing import MockServer  # noqa: E402

from mastodon_finder import mastodon_client  # noqa: E402
from mastodon_finder.settings import Settings  # noqa: E402

# The token the finder authenticates with (the "me" account doing the searching).
ME_TOKEN = "finder_token"

# A seed designed to exercise every discovery path the finder uses:
#   * "rustacean" / "pythonista" have searchable usernames + display names,
#   * their statuses carry hashtags (#rust, #python) and keyword text,
#   * "me" follows nobody yet; "rustacean" has a couple of followers so the
#     "follow what they follow" expansion (account_followers) returns rows.
INTEGRATION_SEED = SeedConfig(
    accounts=[
        SeedAccount(username="me", display_name="The Finder", access_token=ME_TOKEN),
        # rustacean carries a token so reply/reblog-filtering tests can post as it.
        SeedAccount(username="rustacean", display_name="Rusty Dev", note="I write Rust all day", access_token="rustacean_token"),
        SeedAccount(username="pythonista", display_name="Py Thon", note="Python and data"),
        SeedAccount(username="follower_one", display_name="Follower One"),
        SeedAccount(username="follower_two", display_name="Follower Two"),
        SeedAccount(username="botaccount", display_name="A Bot", bot=True),
    ],
    follows=[
        SeedFollow(follower="follower_one", following="rustacean"),
        SeedFollow(follower="follower_two", following="rustacean"),
        SeedFollow(follower="me", following="pythonista"),
    ],
    statuses=[
        SeedStatus(account="rustacean", text="shipping some #rust today, love the borrow checker"),
        SeedStatus(account="rustacean", text="another post about ownership in rust"),
        SeedStatus(account="pythonista", text="a neat #python trick for dataframes"),
        SeedStatus(account="botaccount", text="beep boop #rust automated post"),
    ],
)


@pytest.fixture(scope="session")
def mock_server_url() -> Iterator[str]:
    """Session-scoped mock server backed by the integration seed.

    ``MockServer`` owns the free port, readiness wait, and teardown.
    """
    with MockServer(seed=INTEGRATION_SEED) as server:
        yield server.base_url


@pytest.fixture
def finder_settings(mock_server_url: str) -> Settings:
    """A finder Settings object pointed at the mock with the seeded token."""
    settings = Settings()
    settings.env.MASTODON_BASE_URL = mock_server_url
    settings.env.MASTODON_ACCESS_TOKEN = ME_TOKEN
    return settings


@pytest.fixture(autouse=True)
def isolate_client_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset all of mastodon_client's module-level state for each test.

    The finder keeps a singleton client, an ``lru_cache`` on the account id, and
    two on-disk pickle caches. Without resetting them a test would reuse a client
    from a prior server, or serve stale cached responses — so we point the caches
    at ``tmp_path`` and clear the singleton/lru per test.
    """
    cache_dir = tmp_path / ".cache"
    cache_me_dir = tmp_path / ".cache_me"
    cache_dir.mkdir()
    cache_me_dir.mkdir()
    monkeypatch.setattr(mastodon_client, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(mastodon_client, "CACHE_ME_DIR", cache_me_dir)
    monkeypatch.setattr(mastodon_client, "CACHE_ENABLED", True)
    # Don't let the singleton or lru leak across tests/servers.
    monkeypatch.setattr(mastodon_client, "_CLIENT_SINGLETON", None)
    mastodon_client._get_my_account_id.cache_clear()
    # The cache cleaner walks real dirs and is irrelevant here.
    monkeypatch.setattr(mastodon_client, "_clean_old_cache_files", lambda *a, **k: None)
    yield


@pytest.fixture
def finder_client(finder_settings: Settings):
    """An initialized finder client singleton bound to the mock."""
    return mastodon_client.get_client(finder_settings)


@pytest.fixture
def rustacean_poster(mock_server_url: str):
    """A raw Mastodon.py client as ``rustacean`` to author replies/reblogs.

    The finder is read-only; this is purely a test affordance to set up state
    (a reply, a reblog) that the finder's read path then has to handle.
    """
    from mastodon import Mastodon

    return Mastodon(access_token="rustacean_token", api_base_url=mock_server_url)
