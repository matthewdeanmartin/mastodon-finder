# mastodon_finder/settings.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import tomli
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Model for .env file settings ---
# These are secrets and API configs
class EnvironmentSettings(BaseSettings):
    """Settings loaded from .env file."""

    # Load from .env file
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Mastodon API
    MASTODON_BASE_URL: Optional[str] = None
    MASTODON_ACCESS_TOKEN: Optional[str] = None

    # LLM Settings
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None


# --- Models for TOML configuration ---
# These models represent the structure in finder.toml


class DiscoveryConfig(BaseModel):
    keywords: List[str] = Field(default=[])
    hashtags: List[str] = Field(default=[])
    profile_keywords: List[str] = Field(default=[])
    profile_hashtags: List[str] = Field(default=[])
    follow_targets: List[str] = Field(default=[])


class LimitsConfig(BaseModel):
    max_accounts: int = Field(default=200, gt=0)
    max_statuses: int = Field(default=200, gt=0)
    max_pages: int = Field(default=4, gt=0)
    follow_target_limit: int = Field(default=-1)


class FriendFullUpFilterConfig(BaseModel):
    enable: bool = Field(default=True)
    max_following: int = Field(default=5000, gt=0)
    max_followers: int = Field(default=5000, gt=0)
    min_follow_back_ratio: float = Field(default=0.25, ge=0)


class FilterConfig(BaseModel):
    since_days: int = Field(default=60, gt=0)
    minimum_posts: int = Field(default=5, ge=0)
    filter_bots: bool = Field(default=True)
    language: str = Field(default="en")
    filter_replies: bool = Field(default=True)
    filter_link_only: bool = Field(default=True)
    link_only_threshold: float = Field(default=0.9, ge=0, le=1)
    friend_full_up: FriendFullUpFilterConfig = Field(
        default_factory=FriendFullUpFilterConfig
    )
    max_posts_per_year: int = Field(default=15000, gt=0)
    reject_bio_keywords: List[str] = Field(default=[])
    filter_no_bio: bool = Field(default=True)
    min_account_age_days: int = Field(default=30, ge=0)


class LLMConfig(BaseModel):
    enable: bool = Field(default=True)
    topics: List[str] = Field(default=[])
    default_openai_model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0, ge=0, le=2)
    timeout: int = Field(default=30, gt=0)


# --- Main Configuration Model ---
# This model combines all config sources


class Settings(BaseModel):
    """
    The main settings object for the application.
    It holds all configuration, validated and merged.
    """

    # From .env file
    env: EnvironmentSettings = Field(default_factory=EnvironmentSettings)

    # From .toml file (with defaults)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # From CLI (no defaults, they are None)
    # These fields are *not* part of the TOML structure
    # They are set by the loader after merging.
    output_file: Optional[str] = Field(default=None)
    dry_run: bool = Field(default=False)
    yes: bool = Field(default=False)  # For skipping confirmation

    # --- Computed Properties ---
    @property
    def llm_enabled(self) -> bool:  # <-- ADD THIS HELPER
        """Returns True if LLM is enabled and not a dry run."""
        if self.dry_run:
            return True  # Dry run still needs to build prompts
        return self.llm.enable

    @property
    def llm_really_disabled(self) -> bool:  # <-- ADD THIS HELPER
        """Returns True if LLM is fully disabled (not just dry run)."""
        return not self.llm.enable

    @property
    def mastodon_base_url(self) -> Optional[str]:
        return self.env.MASTODON_BASE_URL

    @property
    def mastodon_access_token(self) -> Optional[str]:
        return self.env.MASTODON_ACCESS_TOKEN

    @property
    def language_filter(self) -> str:
        # Standardize to 'none'
        if self.filters.language is None or self.filters.language.lower() == "none":
            return "none"
        return self.filters.language.lower()

    # --- Validation ---
    def validate_api_keys(self) -> None:
        """
        Validates that required API keys are set for a non-dry-run.
        """
        if self.dry_run:
            return  # Skip key validation on dry run

        if not self.mastodon_base_url or not self.mastodon_access_token:
            print(
                "Error: MASTODON_BASE_URL and MASTODON_ACCESS_TOKEN must be set in your .env file."
            )
            print("Please create a .env file or run 'mastodon-finder init'.")
            sys.exit(1)

        # Add a non-fatal warning for LLM config
        if not self.env.OPENROUTER_API_KEY and not self.env.OPENAI_API_KEY:
            print("Warning: Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set.")
            print("         LLM calls will fail.")
        elif self.env.OPENROUTER_API_KEY and (
            not self.env.OPENROUTER_BASE_URL or not self.env.OPENROUTER_MODEL
        ):
            print(
                "Warning: OPENROUTER_API_KEY is set, but OPENROUTER_BASE_URL or OPENROUTER_MODEL is missing."
            )
            print("         OpenRouter calls may fail.")


def load_toml_config(config_path: str = "finder.toml") -> Dict:
    """
    Loads and parses the TOML config file if it exists.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        return {}

    try:
        with open(config_file, "rb") as f:
            return tomli.load(f)
    except tomli.TOMLDecodeError as e:
        print(f"Error: Invalid TOML in '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not read '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)


def merge_cli_args(settings: Settings, cli_args: "argparse.Namespace") -> None:
    """
    Merges CLI arguments into the settings object.
    CLI arguments (if not None) override TOML and defaults.
    """
    # This function *mutates* the settings object.

    # --- Discovery ---
    if cli_args.keywords is not None:
        settings.discovery.keywords = cli_args.keywords
    if cli_args.hashtags is not None:
        settings.discovery.hashtags = cli_args.hashtags
    if cli_args.profile_keywords is not None:
        settings.discovery.profile_keywords = cli_args.profile_keywords
    if cli_args.profile_hashtags is not None:
        settings.discovery.profile_hashtags = cli_args.profile_hashtags
    if cli_args.follow_targets is not None:
        settings.discovery.follow_targets = cli_args.follow_targets

    # --- Limits ---
    if cli_args.max_accounts is not None:
        settings.limits.max_accounts = cli_args.max_accounts
    if cli_args.max_statuses is not None:
        settings.limits.max_statuses = cli_args.max_statuses
    if cli_args.max_pages is not None:
        settings.limits.max_pages = cli_args.max_pages
    if cli_args.follow_target_limit is not None:
        settings.limits.follow_target_limit = cli_args.follow_target_limit

    # --- Filters ---
    if cli_args.since_days is not None:
        settings.filters.since_days = cli_args.since_days
    if cli_args.filter_bots is not None:
        settings.filters.filter_bots = cli_args.filter_bots
    if cli_args.language is not None:
        settings.filters.language = cli_args.language
    if cli_args.filter_replies is not None:
        settings.filters.filter_replies = cli_args.filter_replies
    if cli_args.filter_link_only is not None:
        settings.filters.filter_link_only = cli_args.filter_link_only

    # Friend Full Up Filter
    if cli_args.filter_friend_full_up is not None:
        settings.filters.friend_full_up.enable = cli_args.filter_friend_full_up
    if cli_args.max_following is not None:
        settings.filters.friend_full_up.max_following = cli_args.max_following
    if cli_args.max_followers is not None:
        settings.filters.friend_full_up.max_followers = cli_args.max_followers
    if cli_args.min_follow_back_ratio is not None:
        settings.filters.friend_full_up.min_follow_back_ratio = (
            cli_args.min_follow_back_ratio
        )

    # --- LLM ---
    if cli_args.topics is not None:
        settings.llm.topics = cli_args.topics
    if cli_args.llm_enable is not None:
        settings.llm.enable = cli_args.llm_enable

    # --- Top-level CLI args ---
    if cli_args.output_file is not None:
        settings.output_file = cli_args.output_file
    if cli_args.dry_run is not None:
        settings.dry_run = cli_args.dry_run
    if cli_args.yes is not None:
        settings.yes = cli_args.yes


def load_settings(cli_args: "argparse.Namespace") -> Settings:
    """
    The main function to load, merge, and validate settings.
    Order:
    1. Hardcoded defaults (in Pydantic models)
    2. .env file (for env block)
    3. finder.toml file
    4. CLI arguments
    """
    try:
        # 1. Load defaults and .env file
        settings = Settings()

        # 2. Load finder.toml
        toml_config = load_toml_config()

        # 3. Merge TOML config into settings
        #    Pydantic's model_copy(update=...) does a deep merge
        if toml_config:
            settings = settings.model_copy(update=toml_config, deep=True)

        # 4. Merge CLI arguments
        merge_cli_args(settings, cli_args)

        # 5. Run final validation (e.g., check API keys)
        settings.validate_api_keys()

        return settings

    except ValidationError as e:
        print("Error: Invalid configuration:", file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)
