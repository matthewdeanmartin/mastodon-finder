# tests/test_prompt_builder.py

from datetime import datetime, timezone

import pytest

from mastodon_finder.enrich import AccountDossier
from mastodon_finder.prompt_builder import build_prompt
from mastodon_finder.settings import Settings


@pytest.fixture
def mock_base_settings() -> Settings:
    """Returns a default Settings object for testing."""
    settings = Settings()
    settings.llm.topics = ["software development", "python"]
    settings.filters.language = "en"
    return settings


@pytest.fixture
def mock_full_dossier() -> AccountDossier:
    """Returns a dossier with all fields populated."""
    return AccountDossier(
        account_id=123,
        acct="@test_user@mastodon.social",
        display_name="Test User",
        url="https://mastodon.social/@test_user",
        followers_count=100,
        following_count=50,
        statuses_count=200,
        created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        note_html="<p>This is my bio.</p>",
        note_text="This is my bio.",
        fields={"Website": "https://example.com", "GitHub": "test_user"},
        discovered_via=["keyword:python", "hashtag:dev"],
        bot=False,
        reply_posts_found=2,
        recent_posts=[
            (
                datetime(2023, 10, 2, tzinfo=timezone.utc),
                "This is the first post.",
                "en",
            ),
            (
                datetime(2023, 10, 1, tzinfo=timezone.utc),
                "This is the second post.",
                "en",
            ),
        ],
    )


@pytest.fixture
def mock_empty_dossier(mock_full_dossier: AccountDossier) -> AccountDossier:
    """Returns a dossier with minimal/empty fields."""
    mock_full_dossier.note_text = ""
    mock_full_dossier.fields = {}
    mock_full_dossier.recent_posts = []
    return mock_full_dossier


# --- System Prompt (Rubric) Tests ---


def test_build_prompt_system_prompt_happy_path(
    mock_full_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that the system prompt correctly includes topics and language filter.
    """
    system_prompt, _ = build_prompt(mock_full_dossier, mock_base_settings)

    # Check for topics
    assert (
        "- Topic matches almost all of these: software development, python"
        in system_prompt
    )
    # Check for language filter
    assert "- Language is primarily not en" in system_prompt
    # Check for format instructions
    assert "DECISION: <FOLLOW|MAYBE|SKIP>" in system_prompt


def test_build_prompt_system_prompt_no_lang_filter(
    mock_full_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that the language filter rule is omitted if set to 'none'.
    """
    mock_base_settings.filters.language = "none"
    system_prompt, _ = build_prompt(mock_full_dossier, mock_base_settings)

    # Check that the language rule is NOT present
    assert "- Language is primarily not" not in system_prompt


def test_build_prompt_system_prompt_different_topics(
    mock_full_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that custom topics are correctly inserted.
    """
    mock_base_settings.llm.topics = ["coffee", "hiking"]
    system_prompt, _ = build_prompt(mock_full_dossier, mock_base_settings)

    # Check for new topics
    assert "- Topic matches almost all of these: coffee, hiking" in system_prompt


# --- User Prompt (Dossier) Tests ---


def test_build_prompt_user_prompt_full_dossier(
    mock_full_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that the user prompt is fully populated from a rich dossier.
    """
    _, user_prompt = build_prompt(mock_full_dossier, mock_base_settings)

    # Check [ACCOUNT] section
    assert "[ACCOUNT]" in user_prompt
    assert "Handle: @test_user@mastodon.social" in user_prompt
    assert "Followers: 100" in user_prompt
    assert "Account created: 2022-01-01" in user_prompt
    assert "Discovered because: keyword:python, hashtag:dev" in user_prompt

    # Check [BIO] section
    assert "\n[BIO]\nThis is my bio." in user_prompt

    # Check [FIELDS] section
    assert "\n[FIELDS]\n" in user_prompt
    assert "- Website: https://example.com" in user_prompt
    assert "- GitHub: test_user" in user_prompt

    # Check [RECENT ORIGINAL POSTS] section
    assert "\n[RECENT ORIGINAL POSTS]\n" in user_prompt
    assert "1. (2023-10-02) This is the first post." in user_prompt
    assert "2. (2023-10-01) This is the second post." in user_prompt


def test_build_prompt_user_prompt_empty_dossier(
    mock_empty_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that the user prompt uses correct fallbacks for empty fields.
    """
    _, user_prompt = build_prompt(mock_empty_dossier, mock_base_settings)

    # Check [BIO] section fallback
    assert "\n[BIO]\nNo bio provided." in user_prompt

    # Check [FIELDS] section fallback
    assert "\n[FIELDS]\nNo profile fields set." in user_prompt

    # Check [RECENT ORIGINAL POSTS] section fallback
    assert "\n[RECENT ORIGINAL POSTS]\nNo recent original posts found." in user_prompt


def test_build_prompt_user_prompt_post_truncation(
    mock_full_dossier: AccountDossier, mock_base_settings: Settings
):
    """
    Tests that long posts are truncated to 250 chars.
    """
    long_text = "a" * 300
    mock_full_dossier.recent_posts = [
        (datetime(2023, 10, 1, tzinfo=timezone.utc), long_text, "en")
    ]

    _, user_prompt = build_prompt(mock_full_dossier, mock_base_settings)

    expected_post_line = f"1. (2023-10-01) {'a' * 250}..."
    assert expected_post_line in user_prompt
    assert "a" * 300 not in user_prompt  # Make sure full text isn't there
