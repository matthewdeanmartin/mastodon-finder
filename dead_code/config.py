# mastodon_finder/config.py
import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Mastodon API Configuration ---
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")


DEFAULT_FOLLOW_TARGETS = [

]
DEFAULT_FOLLOW_LIMIT = -1

# --- Discovery Terms (Defaults) ---
DEFAULT_KEYWORDS = [ "golang", "ruby", "cobol", "c++", "rust", "typescript"]
DEFAULT_HASHTAGS = ["golang", "ruby", "cobol", "c++", "rust", "typescript"]
DEFAULT_TOPICS = [
    "software developer, software engineer, coder"
]

# --- Profile search terms ---
DEFAULT_PROFILE_KEYWORDS = [ "golang", "ruby", "cobol", "c++", "rust", "typescript"]
DEFAULT_PROFILE_HASHTAGS = [ "golang", "ruby", "cobol", "c++", "rust", "typescript"]

# --- Fetch Limits (Defaults) ---
# Max accounts to process in a single run
MAX_ACCOUNTS_PER_RUN =200
# Max original statuses to fetch per account
MAX_STATUSES_PER_ACCOUNT = 120
# Max pages of results to fetch per keyword/hashtag
MAX_PAGES_PER_TERM = 4
# Page size for API calls
DEFAULT_PAGE_LIMIT = 40

# --- Filtering (Defaults) ---
# Skip accounts with no original posts in this many days
DEFAULT_SINCE_DAYS = 60

MINIMUM_POSTS = 5

# --- NEW FILTER SETTINGS ---
# Skip accounts marked as bots
FILTER_BOT_ACCOUNTS = True
# Skip accounts that don't post in this language (e.g., 'en').
# Set to None to disable.
DEFAULT_LANGUAGE_FILTER = "en"
# Skip accounts that don't appear to reply to others
FILTER_NO_REPLIES = True
# Skip accounts where posts are just links
FILTER_LINK_ONLY = True
# Percentage of posts that must be links to trigger FILTER_LINK_ONLY
# 1.0 = 100% of posts, 0.9 = 90% of posts
LINK_ONLY_THRESHOLD = 0.9

# --- "Friend Full Up" Filter (NEW) ---
# Skip accounts that follow too many, are followed by too many,
# and have a low follow-back ratio (followers / following)
FILTER_FRIEND_FULL_UP = True
FRIEND_FULL_MAX_FOLLOWING = 5000 # people that can't meaningfully follow back because their feed is a flood
FRIEND_FULL_MAX_FOLLOWERS = 5000 # celebrities. This many or may not be a problem
# e.g., 0.25 = followers are < 25% of following
FRIEND_FULL_MIN_RATIO = 0.25


# --- LLM Settings ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")  # e.g., "smarty"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- LLM Defaults ---
# Default model to use if OPENROUTER_MODEL is not set
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
# API call settings
LLM_TEMPERATURE = 0
LLM_TIMEOUT = 30  # seconds


def validate_config() -> None:
    """
    Validates that required environment variables are set.
    Called by the main CLI entry point, not on import.
    """
    if not MASTODON_BASE_URL or not MASTODON_ACCESS_TOKEN:
        print(
            "Error: MASTODON_BASE_URL and MASTODON_ACCESS_TOKEN must be set in your .env file."
        )
        print("Please create a .env file based on the spec.")
        sys.exit(1)  # This is fine for a CLI entry point

    # Add a non-fatal warning for LLM config
    if not OPENROUTER_API_KEY and not OPENAI_API_KEY:
        print("Warning: Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set.")
        print("         LLM calls will fail. (This is OK for --dry-run)")
    elif OPENROUTER_API_KEY and (not OPENROUTER_BASE_URL or not OPENROUTER_MODEL):
        print(
            "Warning: OPENROUTER_API_KEY is set, but OPENROUTER_BASE_URL or OPENROUTER_MODEL is missing."
        )
        print("         OpenRouter calls may fail.")
