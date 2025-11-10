# tests/test_enrich.py

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from langdetect import LangDetectException

from mastodon_finder.enrich import build_dossier, build_dossiers, strip_html

# --- Fixtures ---


@pytest.fixture
def mock_api_account() -> Mock:
    """Returns a mock Mastodon Account object."""
    mock = Mock()
    mock.id = 123
    mock.acct = "@test_user@mastodon.social"
    mock.display_name = "Test User"
    mock.url = "https://mastodon.social/@test_user"
    mock.followers_count = 100
    mock.following_count = 50
    mock.statuses_count = 200
    mock.created_at = datetime(2022, 1, 1, tzinfo=timezone.utc)
    mock.note = (
        "<p>This is my bio.</p> Check my <a href='https.example.com'>website</a>."
    )
    mock.fields = [
        Mock(name="<p>Website</p>", value="https://example.com"),
        Mock(name="GitHub", value="<strong>test_user</strong>"),
    ]
    mock.bot = False
    return mock


@pytest.fixture
def mock_api_statuses() -> list[Mock]:
    """Returns a list of mock Mastodon Status objects."""
    # 1. An original post
    status_1 = Mock()
    status_1.id = 1001
    status_1.in_reply_to_id = None
    status_1.content = "<p>This is an original post about Python.</p>"
    status_1.created_at = datetime(2023, 10, 2, tzinfo=timezone.utc)

    # 2. A reply (should be skipped)
    status_2 = Mock()
    status_2.id = 1002
    status_2.in_reply_to_id = 999  # Not None
    status_2.content = "This is a reply."
    status_2.created_at = datetime(2023, 10, 1, tzinfo=timezone.utc)

    # 3. Another original post (for langdetect exception)
    status_3 = Mock()
    status_3.id = 1003
    status_3.in_reply_to_id = None
    status_3.content = "Short"  # This will fail langdetect
    status_3.created_at = datetime(2023, 9, 30, tzinfo=timezone.utc)

    return [status_1, status_2, status_3]


@pytest.fixture
def mock_mastodon_client(monkeypatch):
    """Mocks all mastodon_client functions used by enrich.py."""
    mock_get_account = Mock()
    mock_get_statuses = Mock()

    monkeypatch.setattr("mastodon_finder.mastodon_client.get_account", mock_get_account)
    monkeypatch.setattr(
        "mastodon_finder.mastodon_client.get_account_statuses",
        mock_get_statuses,
    )
    return mock_get_account, mock_get_statuses


@pytest.fixture
def mock_langdetect(monkeypatch):
    """Mocks langdetect.detect."""
    mock_detect_func = Mock()

    # Define side effect behavior
    def detect_side_effect(text):
        if "Python" in text:
            return "en"
        if "Short" in text:
            # Simulate failure on short text
            raise LangDetectException(code=6, message="No features in text")
        return "fr"

    mock_detect_func.side_effect = detect_side_effect
    monkeypatch.setattr("mastodon_finder.enrich.detect", mock_detect_func)
    return mock_detect_func


# --- Tests for strip_html ---


@pytest.mark.parametrize(
    "html_input, expected_text",
    [
        ("<p>Hello</p>", "Hello"),
        ("Hello <br>world", "Hello world"),
        ("<p>Line 1</p><p>Line 2</p>", "Line 1 Line 2"),
        ("No html here", "No html here"),
        ("", ""),
        (None, ""),
        (
            "Check <a href='...'>this</a> link.",
            "Check this link.",
        ),
    ],
)
def test_strip_html(html_input, expected_text):
    assert strip_html(html_input) == expected_text


# --- Tests for build_dossier ---


def test_build_dossier_api_failures(mock_mastodon_client):
    """
    Tests that build_dossier returns None if API calls fail.
    """
    mock_get_account, mock_get_statuses = mock_mastodon_client

    # Case 1: get_account returns None
    mock_get_account.return_value = None
    mock_get_statuses.return_value = []  # Doesn't matter
    assert build_dossier(1, ["reason"], 10) is None

    # Case 2: get_account_statuses returns None
    mock_get_account.return_value = Mock()  # Success
    mock_get_statuses.return_value = None
    assert build_dossier(1, ["reason"], 10) is None


# --- Tests for build_dossiers ---


@patch("mastodon_finder.enrich.build_dossier")
def test_build_dossiers_sorting_and_limit(mock_build_dossier):
    """
    Tests that build_dossiers sorts candidates by discovery
    reason count and respects the max_accounts limit.
    """
    # Setup candidates dict (unsorted)
    candidates = {
        10: ["reason1"],  # 1 reason
        20: ["reason1", "reason2", "reason3"],  # 3 reasons (should be first)
        30: ["reason1", "reason2"],  # 2 reasons (should be second)
        40: ["reason1", "reason2", "reason3", "reason4"],  # 4 reasons (should be first)
        50: ["reason1"],  # 1 reason
    }

    # Mock build_dossier to just return a simple object
    def build_dossier_side_effect(acct_id, reasons, max_statuses):
        # Return a mock dossier with just the ID
        return Mock(account_id=acct_id)

    mock_build_dossier.side_effect = build_dossier_side_effect

    # 1. Test sorting (with a high limit)
    dossiers = build_dossiers(candidates, max_statuses=10, max_accounts=100)

    # Check that all 5 were processed
    assert len(dossiers) == 5
    # Check that they are sorted by reason count (descending)
    processed_ids = [d.account_id for d in dossiers]
    assert processed_ids[0] == 40
    assert processed_ids[1] == 20
    assert processed_ids[2] == 30
    # The order of 10 and 50 (both 1 reason) is not guaranteed
    assert set(processed_ids[3:]) == {10, 50}

    # 2. Test max_accounts limit
    mock_build_dossier.reset_mock()
    dossiers_limited = build_dossiers(candidates, max_statuses=10, max_accounts=2)

    # Check that only 2 were processed
    assert len(dossiers_limited) == 2
    # Check that they were the top 2
    processed_ids_limited = [d.account_id for d in dossiers_limited]
    assert processed_ids_limited == [40, 20]


@patch("mastodon_finder.enrich.build_dossier")
def test_build_dossiers_handles_none(mock_build_dossier):
    """
    Tests that if build_dossier returns None for an account,
    it is not included in the final list.
    """
    candidates = {
        1: ["reason1", "reason2"],  # Will succeed
        2: ["reason1"],  # Will fail (return None)
    }

    def build_dossier_side_effect(acct_id, reasons, max_statuses):
        if acct_id == 1:
            return Mock(account_id=acct_id)
        if acct_id == 2:
            return None  # Simulate API failure
        return None

    mock_build_dossier.side_effect = build_dossier_side_effect

    dossiers = build_dossiers(candidates, max_statuses=10, max_accounts=10)

    assert len(dossiers) == 1
    assert dossiers[0].account_id == 1
