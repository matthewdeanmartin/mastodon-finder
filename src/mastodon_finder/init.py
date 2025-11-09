# mastodon_finder/init.py
import logging
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_FILENAME = "finder.toml"
GITIGNORE_LINE = f"\n# Mastodon Finder config\n/{CONFIG_FILENAME}\n"

# This is a template for the TOML file.
TOML_TEMPLATE = """
# Mastodon Finder Configuration File
# Settings in this file override the hardcoded defaults.
# Command-line switches override settings in this file.

[discovery]
# Keywords to search for in posts
# keywords = ["golang", "ruby", "rust"]

# Hashtags to search for in posts
# hashtags = ["golang", "ruby", "rust"]

# Keywords to search for in user profiles
# profile_keywords = ["golang", "ruby", "rust"]

# Hashtags to search for in user profiles
# profile_hashtags = ["golang", "ruby", "rust"]

# Mastodon handles (e.g., "@user@server") to find followers of
# follow_targets = ["@some_connector_account@mastodon.social"]


[limits]
# Max accounts to process in a single run
max_accounts = 200

# Max original statuses to fetch per account for the dossier
max_statuses = 120

# Max pages of results to fetch per keyword/hashtag
max_pages = 4

# Max followers to fetch per target account (-1 for all)
follow_target_limit = -1


[filters]
# Skip accounts with no original posts in this many days
since_days = 60

# Minimum number of original (non-reply) posts required
minimum_posts = 5

# Skip accounts marked as bots
filter_bots = true

# Skip accounts that don't post in this language (e.g., 'en').
# Set to "none" to disable.
language = "en"

# Skip accounts that don't appear to reply to others
filter_replies = true

# Skip accounts where posts are just links
filter_link_only = true

# Percentage of posts that must be links to trigger filter_link_only
# 1.0 = 100% of posts, 0.9 = 90% of posts
link_only_threshold = 0.9

[filters.friend_full_up]
# Enable the "friend full up" filter
enable = true
# Max following count threshold
max_following = 5000
# Max followers count threshold
max_followers = 5000
# Min (followers / following) ratio
min_follow_back_ratio = 0.25


[llm]
# Topics to include in the LLM rubric
# topics = ["software developer, software engineer"]

# Default OpenAI model to use if OpenRouter is not configured
default_openai_model = "gpt-4o-mini"

# Model temperature (0 = deterministic, 1 = creative)
temperature = 0.0

# API call timeout in seconds
timeout = 30


# Note: API keys (MASTODON_*, OPENROUTER_*, OPENAI_*)
# should be set in a .env file, not here.
"""


def create_default_config():
    """
    Creates a default finder.toml and adds it to .gitignore.
    """
    config_file = Path(CONFIG_FILENAME)
    gitignore_file = Path(".gitignore")

    # 1. Create finder.toml
    if config_file.exists():
        print(f"'{CONFIG_FILENAME}' already exists. Skipping creation.")
    else:
        try:
            config_file.write_text(TOML_TEMPLATE.strip())
            print(f"Created default config file: '{CONFIG_FILENAME}'")
        except Exception as e:
            log.error(f"Failed to create config file: {e}")
            return

    # 2. Add to .gitignore
    if not gitignore_file.exists():
        try:
            gitignore_file.write_text(GITIGNORE_LINE.strip())
            print("Created '.gitignore' and added config file to it.")
        except Exception as e:
            log.error(f"Failed to create .gitignore: {e}")
    else:
        try:
            content = gitignore_file.read_text()
            if CONFIG_FILENAME not in content:
                with open(gitignore_file, "a") as f:
                    f.write(GITIGNORE_LINE)
                print(f"Added '{CONFIG_FILENAME}' to existing '.gitignore'.")
            else:
                print(f"'{CONFIG_FILENAME}' already in '.gitignore'.")
        except Exception as e:
            log.error(f"Failed to update .gitignore: {e}")