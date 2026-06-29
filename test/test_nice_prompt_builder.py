# tests/test_nice_prompt_builder.py
"""Tests for the "find nice people" rubric. See spec/find_nice_people.md."""

from datetime import datetime, timezone

import pytest

from mastodon_finder.enrich import AccountDossier
from mastodon_finder.nice_prompt_builder import build_prompt as build_nice_prompt
from mastodon_finder.prompt_builder import build_prompt as build_topic_prompt
from mastodon_finder.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    settings = Settings()
    # A topic is set on purpose to prove the nice rubric ignores it.
    settings.llm.topics = ["cobol", "mainframes"]
    settings.filters.language = "en"
    return settings


@pytest.fixture
def mock_dossier() -> AccountDossier:
    return AccountDossier(
        account_id=123,
        acct="@alice@mastodon.social",
        display_name="Alice",
        url="https://mastodon.social/@alice",
        followers_count=120,
        following_count=80,
        statuses_count=300,
        created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        note_html="<p>Just a person who likes gardening.</p>",
        note_text="Just a person who likes gardening.",
        fields={"Pronouns": "she/her"},
        discovered_via=["follows:@cobolworx"],
        bot=False,
        reply_posts_found=12,
        recent_posts=[
            (
                datetime(2024, 5, 1, tzinfo=timezone.utc),
                "Loving the spring weather!",
                "en",
            ),
        ],
    )


def test_rubric_scores_three_axes(mock_dossier, mock_settings):
    system_prompt, _ = build_nice_prompt(mock_dossier, mock_settings)
    assert "person:" in system_prompt
    assert "sentiment:" in system_prompt
    assert "replies:" in system_prompt


def test_rubric_ignores_topics(mock_dossier, mock_settings):
    """Nice mode must not leak llm.topics into the rubric."""
    system_prompt, _ = build_nice_prompt(mock_dossier, mock_settings)
    assert "cobol" not in system_prompt.lower()
    assert "mainframes" not in system_prompt.lower()


def test_strict_output_contract(mock_dossier, mock_settings):
    system_prompt, _ = build_nice_prompt(mock_dossier, mock_settings)
    assert "DECISION: <FOLLOW|MAYBE|SKIP>" in system_prompt
    assert "REASONING:" in system_prompt


def test_user_sections_match_topic_mode(mock_dossier, mock_settings):
    """The account-data portion must be identical across modes."""
    _, nice_user = build_nice_prompt(mock_dossier, mock_settings)
    _, topic_user = build_topic_prompt(mock_dossier, mock_settings)
    assert nice_user == topic_user
    assert "Alice" in nice_user
    assert "gardening" in nice_user


def test_language_line_present_when_filter_active(mock_dossier, mock_settings):
    mock_settings.filters.language = "en"
    system_prompt, _ = build_nice_prompt(mock_dossier, mock_settings)
    assert "language other than 'en'" in system_prompt


def test_language_line_absent_when_filter_none(mock_dossier, mock_settings):
    mock_settings.filters.language = "none"
    system_prompt, _ = build_nice_prompt(mock_dossier, mock_settings)
    assert "language other than" not in system_prompt
