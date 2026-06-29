# tests/test_settings.py

import argparse
import sys
from unittest.mock import Mock

import pytest

from mastodon_finder.settings import Settings, load_toml_config


@pytest.fixture
def mock_cli_args() -> argparse.Namespace:
    """
    Provides a mock argparse.Namespace object where all
    configurable values are None, simulating that no
    CLI arguments were provided.
    """
    return argparse.Namespace(
        keywords=None,
        hashtags=None,
        profile_keywords=None,
        profile_hashtags=None,
        follow_targets=None,
        follow_target_limit=None,
        topics=None,
        max_accounts=None,
        max_statuses=None,
        max_pages=None,
        since_days=None,
        filter_bots=None,
        language=None,
        filter_replies=None,
        filter_link_only=None,
        filter_friend_full_up=None,
        max_following=None,
        max_followers=None,
        min_follow_back_ratio=None,
        output_file=None,
        dry_run=None,
        yes=None,
        llm_enable=None,
    )


# --- Tests for load_toml_config ---


def test_load_toml_config_happy_path(tmp_path):
    """
    Tests that a valid TOML file is correctly loaded into a dict.
    """
    toml_content = """
    [discovery]
    keywords = ["toml_keyword"]

    [limits]
    max_accounts = 99
    """
    config_file = tmp_path / "finder.toml"
    config_file.write_text(toml_content)

    config = load_toml_config(str(config_file))

    assert config == {
        "discovery": {"keywords": ["toml_keyword"]},
        "limits": {"max_accounts": 99},
    }


def test_load_toml_config_file_not_found():
    """
    Tests that an empty dict is returned if the config file doesn't exist.
    """
    config = load_toml_config("non_existent_file.toml")
    assert config == {}


def test_load_toml_config_invalid_toml(tmp_path, monkeypatch):
    """
    Tests that invalid TOML syntax causes a SystemExit.
    """
    config_file = tmp_path / "bad.toml"
    config_file.write_text('[discovery]\nkeywords = ["unclosed string')

    # Mock sys.exit to prevent the test runner from stopping
    mock_exit = Mock()
    monkeypatch.setattr(sys, "exit", mock_exit)

    load_toml_config(str(config_file))

    # Assert that sys.exit(1) was called
    mock_exit.assert_called_with(1)


# --- Tests for load_settings (Merge Logic) ---


# --- Tests for Validation and Computed Properties ---


def test_validate_api_keys_success(monkeypatch):
    """
    Tests that validation passes when keys are set.
    """
    # Mock sys.exit to ensure it's NOT called
    mock_exit = Mock()
    monkeypatch.setattr(sys, "exit", mock_exit)

    settings = Settings()
    # Manually set env values
    settings.env.MASTODON_BASE_URL = "https://foo.com"
    settings.env.MASTODON_ACCESS_TOKEN = "token"

    settings.validate_api_keys()
    mock_exit.assert_not_called()


def test_validate_api_keys_success_on_dry_run(monkeypatch):
    """
    Tests that validation is skipped on a dry run, even with missing keys.
    """
    mock_exit = Mock()
    monkeypatch.setattr(sys, "exit", mock_exit)

    settings = Settings(dry_run=True)  # No keys, but dry_run=True
    settings.validate_api_keys()

    mock_exit.assert_not_called()


def test_computed_property_language_filter():
    """
    Tests the .language_filter property logic.
    """
    settings = Settings()

    settings.filters.language = "en"
    assert settings.language_filter == "en"

    settings.filters.language = "EN"
    assert settings.language_filter == "en"

    settings.filters.language = "none"
    assert settings.language_filter == "none"

    settings.filters.language = "None"
    assert settings.language_filter == "none"

    settings.filters.language = None
    assert settings.language_filter == "none"


def test_computed_property_llm_enabled():
    """
    Tests the .llm_enabled property logic.
    """
    settings = Settings()

    # Default: Enabled, not dry run
    settings.llm.enable = True
    settings.dry_run = False
    assert settings.llm_enabled is True
    assert settings.llm_really_disabled is False

    # Disabled
    settings.llm.enable = False
    settings.dry_run = False
    assert settings.llm_enabled is False
    assert settings.llm_really_disabled is True

    # Dry run (enabled)
    settings.llm.enable = True
    settings.dry_run = True
    # llm_enabled should be True to allow prompt building
    assert settings.llm_enabled is True
    assert settings.llm_really_disabled is False

    # Dry run (disabled)
    settings.llm.enable = False
    settings.dry_run = True
    # llm_enabled should *still* be True for dry run
    assert settings.llm_enabled is True
    # But llm_really_disabled should be True
    assert settings.llm_really_disabled is True


# --- Evaluation mode (find-nice workflow) ---


def test_evaluation_mode_defaults_to_topic():
    assert Settings().evaluation.mode == "topic"


def test_evaluation_mode_from_toml():
    settings = Settings(**{"evaluation": {"mode": "nice"}})
    assert settings.evaluation.mode == "nice"


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["run"], "topic"),  # default, no override
        (["run", "--mode", "nice"], "nice"),
        (["run", "--nice"], "nice"),
        (["run", "--topic"], "topic"),
    ],
)
def test_evaluation_mode_cli_override(argv, expected):
    from mastodon_finder.finder import setup_arg_parser
    from mastodon_finder.settings import merge_cli_args

    args = setup_arg_parser().parse_args(argv)
    settings = Settings()
    merge_cli_args(settings, args)
    assert settings.evaluation.mode == expected


def test_cli_mode_overrides_toml():
    from mastodon_finder.finder import setup_arg_parser
    from mastodon_finder.settings import merge_cli_args

    args = setup_arg_parser().parse_args(["run", "--topic"])
    settings = Settings(**{"evaluation": {"mode": "nice"}})
    merge_cli_args(settings, args)
    assert settings.evaluation.mode == "topic"
