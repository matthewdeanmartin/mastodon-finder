# finder.py

import argparse
import logging
# +++ NEW IMPORT +++
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import List  # +++ NEW IMPORT +++

import mastodon_finder.config as config
import mastodon_finder.discovery as discovery
import mastodon_finder.enrich as enrich
import mastodon_finder.llm_runner as llm_runner
# +++ NEW IMPORT +++
import mastodon_finder.mastodon_client as mastodon_client
import mastodon_finder.prompt_builder as prompt_builder
import mastodon_finder.report as report
from mastodon_finder.config import MINIMUM_POSTS
# +++ NEW IMPORT +++
from mastodon_finder.enrich import AccountDossier

log = logging.getLogger(__name__)


# +++ NEW FILTERING FUNCTION +++
def _pre_llm_filter(
        dossiers: List[AccountDossier], args: argparse.Namespace
) -> List[AccountDossier]:
    """Applies all pre-LLM filtering rules based on CLI args."""
    log.info(f"Applying pre-LLM filters to {len(dossiers)} dossiers...")
    final_dossiers = []

    # 1. Activity Filter (--since-days)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=args.since_days)

    for d in dossiers:
        # Filter 1: Inactivity
        if d.latest_post_date and d.latest_post_date < cutoff_date:
            log.info(
                f"Skipping {d.acct}: Inactive (last post {d.latest_post_date.date()})"
            )
            continue

        # Filter 2: Bot Filter (--filter-bots)
        if args.filter_bots and d.bot:
            log.info(f"Skipping {d.acct}: Account is marked as a bot.")
            continue


        # Filter 3: Language Filter (--language)
        lang_filter = args.language.lower()
        if lang_filter != 'none':
            # Get all non-None languages detected in recent posts
            post_langs = {lang for _, _, lang in d.recent_posts if lang}
            if not post_langs:
                log.info(f"Skipping {d.acct}: Could not detect language in any posts.")
                continue
            if lang_filter not in post_langs:
                log.info(f"Skipping {d.acct}: No posts detected in '{lang_filter}'. Found: {post_langs}")
                continue

        # Filter 4: No Replies Filter (--filter-replies)
        if args.filter_replies and d.reply_posts_found == 0:
            log.info(f"Skipping {d.acct}: No replies found in recent {args.max_statuses} statuses.")
            continue

        # Filter 5: Link-Only Filter (--filter-link-only)
        if args.filter_link_only and d.recent_posts:
            link_post_count = 0
            total_posts = len(d.recent_posts)
            for _, post_text, _ in d.recent_posts:
                if re.search(r'https?://', post_text):
                    link_post_count += 1

            if total_posts > 0:
                link_ratio = link_post_count / total_posts
                if link_ratio >= config.LINK_ONLY_THRESHOLD:
                    log.info(f"Skipping {d.acct}: Posts are {link_ratio * 100:.0f}% links (>= threshold).")
                    continue

        # Filter 6: not enough original posts
        if len(d.recent_posts)<MINIMUM_POSTS:
            log.info(f"Skipping {d.acct}: Not enough posts, needed {MINIMUM_POSTS}, found {len(d.recent_posts)}.")
            continue

        # Filter 7: not enough original posts
        if "bsky.brid.gy" in d.url.lower():
            log.info(f"Skipping {d.acct}: Bluesky bridge.")
            continue

        # If all filters passed:
        final_dossiers.append(d)

    return final_dossiers


def main():
    parser = argparse.ArgumentParser(
        description="Mastodon account discovery and scoring tool."
    )

    # --- Arguments (from Spec 7) ---
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=config.DEFAULT_KEYWORDS,
        help="List of keywords to search for.",
    )
    parser.add_argument(
        "--hashtags",
        nargs="+",
        default=config.DEFAULT_HASHTAGS,
        help="List of hashtags (without #) to search for.",
    )

    # +++ NEW: Profile search arguments +++
    parser.add_argument(
        "--profile-keywords",
        nargs="+",
        default=config.DEFAULT_PROFILE_KEYWORDS,
        help="List of keywords to search for in *user profiles*.",
    )
    parser.add_argument(
        "--profile-hashtags",
        nargs="+",
        default=config.DEFAULT_PROFILE_HASHTAGS,
        help="List of hashtags (without #) to search for in *user profiles*.",
    )

    parser.add_argument(
        "--topics",
        nargs="+",
        default=config.DEFAULT_TOPICS,
        help="List of topics to include in the LLM rubric.",
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=config.MAX_ACCOUNTS_PER_RUN,
        help="Max number of accounts to process.",
    )
    parser.add_argument(
        "--max-statuses",
        type=int,
        default=config.MAX_STATUSES_PER_ACCOUNT,
        help="Max statuses to fetch per account for the dossier.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=config.MAX_PAGES_PER_TERM,
        help="Max pages of results to fetch per term.",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=config.DEFAULT_SINCE_DAYS,
        help="Skip accounts with no original posts in this many days.",
    )

    # +++ NEW CLI ARGUMENTS +++
    parser.add_argument(
        "--filter-bots",
        dest="filter_bots",
        action="store_true",
        default=config.FILTER_BOT_ACCOUNTS,
        help="Skip accounts marked as bots.",
    )
    parser.add_argument(
        "--no-filter-bots",
        dest="filter_bots",
        action="store_false",
        help="Do not skip bot accounts.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=config.DEFAULT_LANGUAGE_FILTER,
        help="Skip accounts that don't post in this language (e.g., 'en'). Set to 'None' to disable.",
    )
    parser.add_argument(
        "--filter-replies",
        dest="filter_replies",
        action="store_true",
        default=config.FILTER_NO_REPLIES,
        help="Skip accounts that don't reply to others.",
    )
    parser.add_argument(
        "--no-filter-replies",
        dest="filter_replies",
        action="store_false",
        help="Allow accounts that don't reply.",
    )
    parser.add_argument(
        "--filter-link-only",
        dest="filter_link_only",
        action="store_true",
        default=config.FILTER_LINK_ONLY,
        help="Skip accounts that mostly post links.",
    )
    parser.add_argument(
        "--no-filter-link-only",
        dest="filter_link_only",
        action="store_false",
        help="Allow accounts that mostly post links.",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to save a report file (e.g., report.md or report.csv).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and enrichment, print prompts, but do not call LLM.",
    )

    args = parser.parse_args()

    # --- Validate Config ---
    # This runs the check only when the CLI is executed,
    # not when modules are imported for testing.
    config.validate_config()

    # --- +++ NEW: Fetch Following List +++ ---
    # This is the first call, triggers client init
    try:
        log.info("Fetching list of accounts you already follow...")
        following_ids = mastodon_client.get_my_following_ids()
        log.info(f"Found {len(following_ids)} accounts you follow. These will be skipped.")
    except ConnectionError as e:
        # Handle connection error during friend fetch
        log.error(f"Application failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        # Handle other errors like auth failure on verify_credentials
        log.error(f"Failed to fetch following list: {e}.")
        following_ids = set()
        sys.exit(2)

    # --- Main Application Flow (from Spec 10) ---

    log.info("--- Starting mastodon-finder ---")
    log.info(f"Post Keywords: {args.keywords}")
    log.info(f"Post Hashtags: {args.hashtags}")
    # +++ NEW: Log profile terms +++
    log.info(f"Profile Keywords: {args.profile_keywords}")
    log.info(f"Profile Hashtags: {args.profile_hashtags}")
    log.info(f"LLM Topics: {args.topics}")

    try:
        # 1. Discovery Phase
        # +++ MODIFIED: Pass new args +++
        candidates = discovery.discover_accounts(
            args.keywords,
            args.hashtags,
            args.profile_keywords,
            args.profile_hashtags,
            args.max_pages
        )
        if not candidates:
            log.info("No candidates found. Exiting.")
            return

        # --- +++ NEW: Filter Already Followed +++ ---
        filtered_candidates = {}
        skipped_count = 0
        for account_id, reasons in candidates.items():
            if account_id in following_ids:
                skipped_count += 1
                continue
            else:
                filtered_candidates[account_id] = reasons

        log.info(f"Discovered {len(candidates)} total candidates.")
        log.info(f"Skipping {skipped_count} accounts you already follow.")
        log.info(f"Enriching {len(filtered_candidates)} new candidates.")

        if not filtered_candidates:
            log.info("No new candidates to process. Exiting.")
            return

        # 2. Enrichment Phase
        dossiers = enrich.build_dossiers(
            filtered_candidates, args.max_statuses, args.max_accounts
        )

        # 3. Pre-LLM Filtering
        final_dossiers = _pre_llm_filter(dossiers, args)
        log.info(f"Processing {len(final_dossiers)} active, filtered candidates.")

        # 4. Evaluation Phase (LLM)
        results = []
        for dossier in final_dossiers:
            # 4a. Build Prompt
            system_prompt, user_prompt = prompt_builder.build_prompt(
                dossier, args.topics
            )

            if args.dry_run:
                print(f"\n--- [DRY RUN] System Prompt for {dossier.acct} ---")
                print(system_prompt)
                print(f"\n--- [DRY RUN] User Prompt for {dossier.acct} ---")
                print(user_prompt)
                print("--- [DRY RUN] End Prompt ---")
                results.append(llm_runner.EvaluationResult(dossier, "MAYBE", "DRY_RUN"))
                continue

            # 4b. Run LLM
            llm_output = llm_runner.run_llm(system_prompt, user_prompt)

            # 4c. Parse Result
            result = llm_runner.parse_llm_output(dossier, llm_output)
            results.append(result)

        # 5. Output Phase
        if results:
            report.write_report(results, args.output_file)
        else:
            log.info("No active accounts were processed.")

    except ConnectionError as e:
        # This catches the lazy-init failure from get_client()
        log.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
