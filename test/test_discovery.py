# tests/test_discovery.py
from __future__ import annotations

from unittest.mock import Mock

import pytest

from mastodon_finder import discovery
from mastodon_finder.settings import DiscoveryConfig, LimitsConfig

# --- Fixtures ---


@pytest.fixture
def mock_discovery_config() -> DiscoveryConfig:
    """Returns a DiscoveryConfig populated with test data."""
    return DiscoveryConfig(
        keywords=["python", "go"],
        hashtags=["rust"],
        profile_keywords=["dev"],
        profile_hashtags=["hiring"],
        follow_targets=["@target@foo.com", "@bad@handle.com"],
    )


@pytest.fixture
def mock_limits_config() -> LimitsConfig:
    """Returns a basic LimitsConfig."""
    return LimitsConfig(
        max_pages=2,
        follow_target_limit=100,
    )


@pytest.fixture
def mock_mastodon_client(monkeypatch) -> dict[str, Mock]:
    """Mocks all mastodon_client functions used by discovery.py."""
    mock_funcs = {
        "search_statuses_by_keyword": Mock(),
        "search_statuses_by_hashtag": Mock(),
        "search_accounts_by_keyword": Mock(),
        "lookup_account_id_by_handle": Mock(),
        "get_account_followers": Mock(),
    }

    for name, mock_func in mock_funcs.items():
        monkeypatch.setattr(f"mastodon_finder.mastodon_client.{name}", mock_func)

    return mock_funcs


@pytest.fixture
def mock_api_data() -> dict[str, list[Mock]]:
    """Provides mock Status and Account objects for the client to return."""
    # Mock status objects (they have an .account attribute)
    status_py = Mock(account=Mock(id=101))
    status_go = Mock(account=Mock(id=102))
    status_rust = Mock(account=Mock(id=101))  # Duplicate ID

    # Mock account objects (they have an .id attribute)
    acct_dev = Mock(id=103)
    acct_hiring = Mock(id=104)
    acct_follower = Mock(id=201)

    return {
        "status_python": [status_py],
        "status_go": [status_go],
        "status_rust": [status_rust],
        "acct_dev": [acct_dev],
        "acct_hiring": [acct_hiring],
        "followers": [acct_follower, acct_dev],  # acct_dev is a duplicate
    }


# --- Test Cases ---


def test_discover_accounts_happy_path_and_merge(
    mock_discovery_config: DiscoveryConfig,
    mock_limits_config: LimitsConfig,
    mock_mastodon_client: dict[str, Mock],
    mock_api_data: dict[str, list[Mock]],
):
    """
    Tests that all discovery sources are called and results are
    correctly aggregated and de-duplicated.
    """
    # --- Setup Mock Return Values ---
    # 1. Keywords
    mock_mastodon_client["search_statuses_by_keyword"].side_effect = [
        mock_api_data["status_python"],  # For "python"
        mock_api_data["status_go"],  # For "go"
    ]
    # 2. Hashtags
    mock_mastodon_client["search_statuses_by_hashtag"].return_value = mock_api_data[
        "status_rust"
    ]
    # 3. Profile Terms
    mock_mastodon_client["search_accounts_by_keyword"].side_effect = [
        mock_api_data["acct_dev"],  # For "dev"
        mock_api_data["acct_hiring"],  # For "#hiring"
    ]
    # 4. Follow Targets
    mock_mastodon_client["lookup_account_id_by_handle"].side_effect = [
        901,  # For "@target@foo.com"
        None,  # For "@bad@handle.com"
    ]
    mock_mastodon_client["get_account_followers"].return_value = mock_api_data[
        "followers"
    ]

    # --- Run Discovery ---
    candidates = discovery.discover_accounts(mock_discovery_config, mock_limits_config)

    # --- Verify API Calls ---
    # 1. Keywords
    assert mock_mastodon_client["search_statuses_by_keyword"].call_count == 2
    mock_mastodon_client["search_statuses_by_keyword"].assert_any_call("python", 2)
    # 2. Hashtags
    mock_mastodon_client["search_statuses_by_hashtag"].assert_called_once_with(
        "rust", 2, 40
    )
    # 3. Profile Terms
    assert mock_mastodon_client["search_accounts_by_keyword"].call_count == 2
    mock_mastodon_client["search_accounts_by_keyword"].assert_any_call("dev")
    mock_mastodon_client["search_accounts_by_keyword"].assert_any_call("#hiring")
    # 4. Follow Targets
    assert mock_mastodon_client["lookup_account_id_by_handle"].call_count == 2
    mock_mastodon_client["get_account_followers"].assert_called_once_with(901, 100)

    # --- Verify Final Candidates Dictionary ---
    assert len(candidates) == 5  # IDs: 101, 102, 103, 104, 201

    # Check reasons for each account
    # We compare sets since the order of reasons in the list isn't guaranteed
    assert set(candidates[101]) == {"keyword:python", "hashtag:rust"}
    assert set(candidates[102]) == {"keyword:go"}
    assert set(candidates[103]) == {
        "profile_term:dev",
        "follows_target:@target@foo.com",
    }
    assert set(candidates[104]) == {"profile_term:#hiring"}
    assert set(candidates[201]) == {"follows_target:@target@foo.com"}


def test_discover_accounts_no_sources(
    mock_limits_config: LimitsConfig,
    mock_mastodon_client: dict[str, Mock],
):
    """
    Tests that no API calls are made if all discovery lists are empty.
    """
    empty_config = DiscoveryConfig(
        keywords=[],
        hashtags=[],
        profile_keywords=[],
        profile_hashtags=[],
        follow_targets=[],
    )

    candidates = discovery.discover_accounts(empty_config, mock_limits_config)

    # Verify no API calls were made
    for mock_func in mock_mastodon_client.values():
        mock_func.assert_not_called()

    # Verify result is empty
    assert candidates == {}
