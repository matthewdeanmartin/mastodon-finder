# tests/test_report.py

import csv
import re
from datetime import datetime
from pathlib import Path

import pytest

from mastodon_finder.enrich import AccountDossier
from mastodon_finder.llm_runner import EvaluationResult
from mastodon_finder.report import write_report
from mastodon_finder.settings import Settings

# --- Fixtures ---


@pytest.fixture
def mock_base_settings() -> Settings:
    """Returns a default Settings object for testing."""
    settings = Settings()
    # Set the user's instance URL for testing follow links
    settings.env.MASTODON_BASE_URL = "https://my-instance.social"
    return settings


@pytest.fixture
def mock_dossiers() -> dict[str, AccountDossier]:
    """Provides a dict of mock dossiers, one for each decision type."""
    return {
        "follow": AccountDossier(
            account_id=1,
            acct="@follow_user@example.com",
            display_name="Follow User",
            url="https://example.com/@follow_user",
            followers_count=100,
            following_count=10,
            statuses_count=1000,
            created_at=datetime.now(),
            note_html="<p>Bio for follow</p>",
            note_text="Bio for follow",
            fields={},
            discovered_via=["keyword:python"],
            bot=False,
            reply_posts_found=10,
        ),
        "maybe": AccountDossier(
            account_id=2,
            acct="@maybe_user@example.com",
            display_name="Maybe User",
            url="https://example.com/@maybe_user",
            followers_count=50,
            following_count=50,
            statuses_count=500,
            created_at=datetime.now(),
            note_html="Bio for maybe",
            note_text="Bio for maybe",
            fields={},
            discovered_via=["hashtag:rust"],
            bot=False,
            reply_posts_found=5,
        ),
        "skip": AccountDossier(
            account_id=3,
            acct="@skip_user@example.com",
            display_name="Skip User",
            url="https://example.com/@skip_user",
            followers_count=10,
            following_count=100,
            statuses_count=10,
            created_at=datetime.now(),
            note_html="Bio for skip",
            note_text="Bio for skip",
            fields={},
            discovered_via=["profile_term:bot"],
            bot=True,
            reply_posts_found=0,
        ),
    }


@pytest.fixture
def mock_unsorted_results(
    mock_dossiers: dict[str, AccountDossier],
) -> list[EvaluationResult]:
    """
    Returns an unsorted list of EvaluationResult objects
    to test the report's sorting logic.
    """
    return [
        EvaluationResult(
            dossier=mock_dossiers["maybe"],
            decision="MAYBE",
            reasoning="Mixed signals.",
        ),
        EvaluationResult(
            dossier=mock_dossiers["skip"],
            decision="SKIP",
            reasoning="Looks like a bot.",
        ),
        EvaluationResult(
            dossier=mock_dossiers["follow"],
            decision="FOLLOW",
            reasoning="Perfect match for python.",
        ),
    ]


@pytest.fixture
def mock_discard_counts() -> dict[str, int]:
    """Returns a dictionary of discard reasons and counts."""
    return {
        "Inactive": 10,
        "Bot Account": 5,
        "Language Mismatch": 2,
    }


# --- Test Cases ---


def test_write_report_console_no_discards(
    mock_unsorted_results: list[EvaluationResult],
    mock_base_settings: Settings,
    capsys,
):
    """
    Tests that the correct message is shown when no accounts are discarded.
    """
    mock_base_settings.output_file = None

    write_report(mock_unsorted_results, {}, mock_base_settings)  # Empty dict

    out, _ = capsys.readouterr()

    assert "--- Filter Discard Summary ---" in out
    assert "No accounts were discarded by pre-LLM filters." in out


def test_write_report_md_file_output(
    mock_unsorted_results: list[EvaluationResult],
    mock_base_settings: Settings,
    tmp_path: Path,
):
    """
    Tests that a Markdown file is correctly generated.
    This implicitly tests _write_md.
    """
    md_file = tmp_path / "report.md"
    mock_base_settings.output_file = str(md_file)

    write_report(mock_unsorted_results, {}, mock_base_settings)

    assert md_file.exists()
    content = md_file.read_text()

    # Check for header
    assert "# Mastodon Finder Report" in content
    assert f"Processed {len(mock_unsorted_results)} accounts." in content

    # Check for sorted results
    # Use re.DOTALL to make . match newlines
    assert re.search(
        r"## \[FOLLOW\].*@follow_user@example.com.*## \[MAYBE\].*@maybe_user@example.com",
        content,
        re.DOTALL,
    )

    # Check for data
    assert "- **URL**: https://example.com/@follow_user" in content
    assert "- **Bio**: Bio for follow" in content
    assert "> Perfect match for python." in content
    assert "---" in content


def test_write_report_csv_file_output(
    mock_unsorted_results: list[EvaluationResult],
    mock_base_settings: Settings,
    tmp_path: Path,
):
    """
    Tests that a CSV file is correctly generated.
    This implicitly tests _write_csv.
    """
    csv_file = tmp_path / "report.csv"
    mock_base_settings.output_file = str(csv_file)

    write_report(mock_unsorted_results, {}, mock_base_settings)

    assert csv_file.exists()

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # 1. Check Header
    expected_header = [
        "decision",
        "acct",
        "display_name",
        "url",
        "followers",
        "following",
        "statuses",
        "discovered_via",
        "reasoning",
        "bio",
    ]
    assert rows[0] == expected_header

    # 2. Check Row Count
    assert len(rows) == len(mock_unsorted_results) + 1  # Data + Header

    # 3. Check Sorting and Data (first data row should be FOLLOW)
    follow_row = rows[1]
    assert follow_row[0] == "FOLLOW"
    assert follow_row[1] == "@follow_user@example.com"
    assert follow_row[7] == "keyword:python"
    assert follow_row[8] == "Perfect match for python."
    assert follow_row[9] == "Bio for follow"

    # 4. Check other rows
    assert rows[2][0] == "MAYBE"
    assert rows[3][0] == "SKIP"
