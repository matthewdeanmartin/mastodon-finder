# mastodon_finder/finder.py

from __future__ import annotations

import argparse
import logging
import logging.config
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from rich import print as rprint

import mastodon_finder.discovery as discovery
import mastodon_finder.enrich as enrich
import mastodon_finder.llm_runner as llm_runner
import mastodon_finder.mastodon_client as mastodon_client
import mastodon_finder.prompt_builder as prompt_builder
import mastodon_finder.report as report
from mastodon_finder.__about__ import __version__
from mastodon_finder.enrich import AccountDossier

# Import the new settings and init modules
from mastodon_finder.init import create_default_config
from mastodon_finder.settings import Settings, load_settings
from mastodon_finder.utils.cli_suggestions import SmartParser
from mastodon_finder.utils.logging_config import generate_config

log = logging.getLogger(__name__)


def _pre_llm_filter(
    dossiers: List[AccountDossier], settings: Settings
) -> Tuple[List[AccountDossier], Dict[str, int]]:
    """
    Applies all pre-LLM filtering rules based on the Settings object.
    Returns a tuple of (filtered_dossiers, discard_counts).
    """
    log.info(f"Applying pre-LLM filters to {len(dossiers)} dossiers...")
    final_dossiers = []
    discard_counts: Dict[str, int] = {}

    filters = settings.filters
    limits = settings.limits

    # 1. Activity Filter (--since-days)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=filters.since_days)

    for d in dossiers:
        # Filter 1: Inactivity
        if d.latest_post_date and d.latest_post_date < cutoff_date:
            reason = "Inactive"
            log.info(
                f"Skipping {d.acct}: {reason} (last post {d.latest_post_date.date()})"
            )
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 2: Bot Filter (--filter-bots)
        if filters.filter_bots and d.bot:
            reason = "Bot Account"
            log.info(f"Skipping {d.acct}: {reason}")
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 3: Language Filter (--language)
        lang_filter = settings.language_filter  # Use computed property
        if lang_filter != "none":
            # Get all non-None languages detected in recent posts
            post_langs = {lang for _, _, lang in d.recent_posts if lang}
            if not post_langs:
                reason = "Language Undetected"
                log.info(f"Skipping {d.acct}: {reason}")
                discard_counts.setdefault(reason, 0)
                discard_counts[reason] += 1
                continue
            if lang_filter not in post_langs:
                reason = f"Language Mismatch (Not '{lang_filter}')"
                log.info(f"Skipping {d.acct}: {reason}. Found: {post_langs}")
                discard_counts.setdefault(reason, 0)
                discard_counts[reason] += 1
                continue

        # Filter 4: No Replies Filter (--filter-replies)
        if filters.filter_replies and d.reply_posts_found == 0:
            reason = "No Replies Found"
            log.info(
                f"Skipping {d.acct}: {reason} in recent {limits.max_statuses} statuses."
            )
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 5: Link-Only Filter (--filter-link-only)
        if filters.filter_link_only and d.recent_posts:
            link_post_count = 0
            total_posts = len(d.recent_posts)
            for _, post_text, _ in d.recent_posts:
                if re.search(r"https?://", post_text):
                    link_post_count += 1

            if total_posts > 0:
                link_ratio = link_post_count / total_posts
                if link_ratio >= filters.link_only_threshold:
                    reason = "Link-Only Posts"
                    log.info(
                        f"Skipping {d.acct}: {reason} ({link_ratio * 100:.0f}% >= threshold)."
                    )
                    discard_counts.setdefault(reason, 0)
                    discard_counts[reason] += 1
                    continue

        # Filter 6: Not enough original posts
        if len(d.recent_posts) < filters.minimum_posts:
            reason = "Not Enough Posts"
            log.info(
                f"Skipping {d.acct}: {reason} (needed {filters.minimum_posts}, found {len(d.recent_posts)})."
            )
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 7: Bluesky Bridge
        if "bsky.brid.gy" in d.url.lower():
            reason = "Bluesky Bridge"
            log.info(f"Skipping {d.acct}: {reason}")
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 8: Friend Full Up (--filter-friend-full-up)
        ffu = filters.friend_full_up
        if ffu.enable:
            # Only apply if following_count is non-zero
            if d.following_count > 0:
                follow_back_ratio = d.followers_count / d.following_count

                if (
                    d.following_count > ffu.max_following
                    and d.followers_count > ffu.max_followers
                    and follow_back_ratio < ffu.min_follow_back_ratio
                ):
                    reason = "Friend Full Up"
                    log.info(
                        f"Skipping {d.acct}: {reason} (Follows: {d.following_count}, "
                        f"Followers: {d.followers_count}, Ratio: {follow_back_ratio:.2f})"
                    )
                    discard_counts.setdefault(reason, 0)
                    discard_counts[reason] += 1
                    continue

        # Filter 9: Too-Chatty Filter
        # Calculate account age in days, ensure at least 1 to avoid ZeroDivisionError
        age_in_days = (datetime.now(timezone.utc) - d.created_at).days
        if age_in_days < 1:
            age_in_days = 1

        # Calculate average posts per year
        posts_per_year = (d.statuses_count / age_in_days) * 365.25

        if posts_per_year > filters.max_posts_per_year:
            reason = "Too Chatty"
            log.info(
                f"Skipping {d.acct}: {reason} (found {posts_per_year:.0f} posts/year, limit is {filters.max_posts_per_year})."
            )
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 10: Negative bio keywords
        if filters.reject_bio_keywords:
            full_text = f"{d.display_name} {d.note_text}".lower()
            found_keyword = None
            for keyword in filters.reject_bio_keywords:
                if keyword.lower() in full_text:
                    found_keyword = keyword
                    break

            if found_keyword:
                reason = "Rejected Keyword in Bio"
                log.info(f"Skipping {d.acct}: {reason} (found '{found_keyword}').")
                discard_counts.setdefault(reason, 0)
                discard_counts[reason] += 1
                continue

        # Filter 11: Check if note_text is None or just whitespace
        if filters.filter_no_bio and not d.note_text.strip():
            reason = "Empty Bio"
            log.info(f"Skipping {d.acct}: {reason}.")
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # Filter 12: (You already calculated age_in_days for the "Too Chatty" filter)
        if age_in_days < filters.min_account_age_days:
            reason = "Account Too New"
            log.info(
                f"Skipping {d.acct}: {reason} (age {age_in_days} days, min is {filters.min_account_age_days})."
            )
            discard_counts.setdefault(reason, 0)
            discard_counts[reason] += 1
            continue

        # If all filters passed:
        final_dossiers.append(d)

    log.info(
        f"Filtering complete. {len(final_dossiers)} dossiers remaining. "
        f"{sum(discard_counts.values())} discarded."
    )
    return final_dossiers, discard_counts


def _confirm_run_settings(settings: Settings):
    """Prints a summary of the run and asks for user confirmation."""
    rprint("[bold]--- Run Configuration Summary ---[/bold]")

    # Discovery
    rprint("\n[bold]Discovery Sources:[/bold]")
    rprint(f"- Post Keywords: {settings.discovery.keywords}")
    rprint(f"- Post Hashtags: {settings.discovery.hashtags}")
    rprint(f"- Profile Keywords: {settings.discovery.profile_keywords}")
    rprint(f"- Profile Hashtags: {settings.discovery.profile_hashtags}")
    rprint(f"- Follow Targets: {settings.discovery.follow_targets}")

    # LLM
    rprint(f"\n[bold]LLM Topics:[/bold] {settings.llm.topics}")
    rprint(
        f"- LLM Evaluation: {'Enabled' if settings.llm.enable else '[yellow]Disabled (pre-filter only)[/yellow]'}"
    )

    # Limits
    rprint("\n[bold]Limits:[/bold]")
    rprint(f"- Max Accounts to Process: {settings.limits.max_accounts}")
    rprint(f"- Max Statuses per Account: {settings.limits.max_statuses}")
    rprint(f"- Max Pages per Term: {settings.limits.max_pages}")
    rprint(f"- Max Followers per Target: {settings.limits.follow_target_limit}")

    # Filters
    rprint("\n[bold]Filters:[/bold]")
    rprint(f"- Skip if no post in: {settings.filters.since_days} days")
    rprint(f"- Min original posts: {settings.filters.minimum_posts}")
    rprint(f"- Skip Bots: {settings.filters.filter_bots}")
    rprint(f"- Skip No-Replies: {settings.filters.filter_replies}")
    rprint(f"- Skip Link-Only: {settings.filters.filter_link_only}")
    rprint(f"- Skip Friend-Full-Up: {settings.filters.friend_full_up.enable}")
    rprint(f"- Language Filter: '{settings.language_filter}'")

    # Output
    rprint("\n[bold]Output:[/bold]")
    rprint(f"- Output File: {settings.output_file or 'None (console only)'}")
    rprint(f"- [yellow]Dry Run Mode[/yellow]: {settings.dry_run}")

    rprint("\n[bold]Proceed with this configuration? (y/N): [/bold]", end="")

    try:
        confirm = input().strip().lower()
        if confirm not in ("y", "yes"):
            rprint("[red]Aborted by user.[/red]")
            sys.exit(0)
    except KeyboardInterrupt:
        rprint("\n[red]Aborted by user.[/red]")
        sys.exit(0)

    rprint("[green]Proceeding...[/green]\n")


def setup_arg_parser() -> argparse.ArgumentParser:
    """Sets up the argparse.ArgumentParser with subparsers."""
    parser = SmartParser(description="Mastodon account discovery and scoring tool.")
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # # --- Setup Logging ---
    # if args.verbose:
    #     log_level = "DEBUG"
    # elif args.quiet:
    #     log_level = "CRITICAL"
    # else:
    #     log_level = "INFO"
    log_level = "INFO"
    logging.config.dictConfig(generate_config(level=log_level))

    # Use subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- 'init' command ---
    _parser_init = subparsers.add_parser(
        "init", help="Create a default 'finder.toml' config file."
    )

    # --- 'auth' command ---  <-- ADD THIS BLOCK
    _parser_auth = subparsers.add_parser(
        "auth", help="Run interactive auth flow to get Mastodon API keys."
    )

    # --- 'run' command ---
    parser_run = subparsers.add_parser(
        "run", help="Run the discovery tool (default command)."
    )
    # Make 'run' the default
    # --- Check if a command was given. If not, default to 'run'.
    # This is a bit more robust than parser.set_defaults
    if len(sys.argv) == 1:
        sys.argv.append("run")
    # parser.set_defaults(command="run") # This can be tricky with subparsers

    # --- Arguments for 'run' command ---
    # Set all defaults to None so we can detect if they were set
    parser_run.add_argument("--keywords", nargs="+", default=None)
    parser_run.add_argument("--hashtags", nargs="+", default=None)
    parser_run.add_argument("--profile-keywords", nargs="+", default=None)
    parser_run.add_argument("--profile-hashtags", nargs="+", default=None)
    parser_run.add_argument("--follow-targets", nargs="+", default=None)
    parser_run.add_argument("--follow-target-limit", type=int, default=None)
    parser_run.add_argument("--topics", nargs="+", default=None)
    parser_run.add_argument("--max-accounts", type=int, default=None)
    parser_run.add_argument("--max-statuses", type=int, default=None)
    parser_run.add_argument("--max-pages", type=int, default=None)
    parser_run.add_argument("--since-days", type=int, default=None)

    # Filter Arguments
    # Use store_true/store_false with default=None
    parser_run.add_argument(
        "--filter-bots", dest="filter_bots", action="store_true", default=None
    )
    parser_run.add_argument(
        "--no-filter-bots", dest="filter_bots", action="store_false", default=None
    )
    parser_run.add_argument("--language", type=str, default=None)
    parser_run.add_argument(
        "--filter-replies", dest="filter_replies", action="store_true", default=None
    )
    parser_run.add_argument(
        "--no-filter-replies", dest="filter_replies", action="store_false", default=None
    )
    parser_run.add_argument(
        "--filter-link-only", dest="filter_link_only", action="store_true", default=None
    )
    parser_run.add_argument(
        "--no-filter-link-only",
        dest="filter_link_only",
        action="store_false",
        default=None,
    )

    # Friend Full Up Filter Arguments
    parser_run.add_argument(
        "--filter-friend-full-up",
        dest="filter_friend_full_up",
        action="store_true",
        default=None,
    )
    parser_run.add_argument(
        "--no-filter-friend-full-up",
        dest="filter_friend_full_up",
        action="store_false",
        default=None,
    )
    parser_run.add_argument("--max-following", type=int, default=None)
    parser_run.add_argument("--max-followers", type=int, default=None)
    parser_run.add_argument("--min-follow-back-ratio", type=float, default=None)

    # Other Arguments
    parser_run.add_argument("--output-file", type=str, default=None)
    parser_run.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=None
    )
    parser_run.add_argument(
        "--yes",
        "-y",
        dest="yes",
        action="store_true",
        default=None,
        help="Skip confirmation prompt",
    )

    parser_run.add_argument(
        "--no-llm",
        dest="llm_enable",
        action="store_false",
        default=None,
        help="Disable LLM evaluation (run discovery and pre-filters only)",
    )
    parser_run.add_argument(
        "--llm",
        dest="llm_enable",
        action="store_true",
        default=None,
        help="Force enable LLM evaluation (overrides finder.toml)",
    )

    return parser


def main():
    parser = setup_arg_parser()

    # Handle the case where no command is given, default to 'run'
    # This is needed because `dest="command"` with subparsers can return None
    args = parser.parse_args()
    if args.command is None:
        args.command = "run"
        # We need to re-parse *within the context of 'run'*
        # This is a quirk of argparse.
        # A simpler way is to just default to 'run' if no command is specified
        # We'll handle this by re-parsing if args.command is None.
        # Let's adjust the arg parser logic slightly.

    # --- Re-setup parser logic for robustness ---
    parser = setup_arg_parser()
    args = parser.parse_args()
    if args.command is None:
        # If no command (e.g., just `python -m mastodon_finder`), default to 'run'
        # and re-parse to apply 'run's arguments
        args = parser.parse_args(["run"] + sys.argv[1:])

    # --- Handle 'init' command ---
    if args.command == "init":
        create_default_config()
        sys.exit(0)

    # --- Handle 'auth' command ---  <-- ADD THIS BLOCK
    if args.command == "auth":
        # Import dynamically to avoid circular dependencies
        # and keep auth logic separate
        import mastodon_finder.auth

        mastodon_finder.auth.run_auth_flow()
        sys.exit(0)

    # --- Handle 'run' command (default) ---
    # 1. Load, merge, and validate settings
    if args.command == "run":
        settings = load_settings(args)

        # 2. Confirm Run Settings (if not --yes)
        if not settings.yes:
            _confirm_run_settings(settings)

        # 3. Initialize Mastodon client (this is the first network call)
        try:
            log.info("Initializing Mastodon client...")
            # Pass settings to the client on first call
            mastodon_client.get_client(settings)

            log.info("Fetching list of accounts you already follow...")
            following_ids = mastodon_client.get_my_following_ids()
            log.info(
                f"Found {len(following_ids)} accounts you follow. These will be skipped."
            )

            my_id = mastodon_client._get_my_account_id()
            if my_id:
                following_ids.add(my_id)
                log.info(f"Ensuring 'self' account (ID: {my_id}) is also skipped.")

        except ConnectionError as e:
            log.error(f"Application failed to start: {e}")
            sys.exit(1)
        except Exception as e:
            log.error(f"Failed to fetch following list: {e}.")
            following_ids = set()
            sys.exit(2)

        # --- Main Application Flow ---
        log.info("--- Starting mastodon-finder ---")
        log.info(f"Post Keywords: {settings.discovery.keywords}")
        log.info(f"Post Hashtags: {settings.discovery.hashtags}")
        log.info(f"Profile Keywords: {settings.discovery.profile_keywords}")
        log.info(f"Profile Hashtags: {settings.discovery.profile_hashtags}")
        log.info(f"Follow Targets: {settings.discovery.follow_targets}")
        log.info(f"LLM Topics: {settings.llm.topics}")

        try:
            # 1. Discovery Phase
            candidates = discovery.discover_accounts(
                settings.discovery,
                settings.limits,
            )
            if not candidates:
                log.info("No candidates found. Exiting.")
                return

            # --- Filter Already Followed (and self) ---
            filtered_candidates = {}
            skipped_count = 0
            for account_id, reasons in candidates.items():
                if account_id in following_ids:
                    skipped_count += 1
                    continue
                else:
                    filtered_candidates[account_id] = reasons

            log.info(f"Discovered {len(candidates)} total candidates.")
            log.info(f"Skipping {skipped_count} accounts (followed or self).")
            log.info(f"Enriching {len(filtered_candidates)} new candidates.")

            if not filtered_candidates:
                log.info("No new candidates to process. Exiting.")
                return

            # 2. Enrichment Phase
            dossiers = enrich.build_dossiers(
                filtered_candidates,
                settings.limits.max_statuses,
                settings.limits.max_accounts,
            )

            # 3. Pre-LLM Filtering
            final_dossiers, discard_counts = _pre_llm_filter(dossiers, settings)
            log.info(f"Processing {len(final_dossiers)} active, filtered candidates.")

            # 4. Evaluation Phase (LLM)
            results = []
            if settings.llm.enable:
                log.info(
                    f"--- Starting Evaluation Phase ({len(final_dossiers)} candidates) ---"
                )

                for dossier in final_dossiers:
                    # 4a. Build Prompt
                    system_prompt, user_prompt = prompt_builder.build_prompt(
                        dossier, settings
                    )

                    if settings.dry_run:
                        print(f"\n--- [DRY RUN] System Prompt for {dossier.acct} ---")
                        print(system_prompt)
                        print(f"\n--- [DRY RUN] User Prompt for {dossier.acct} ---")
                        print(user_prompt)
                        print("--- [DRY RUN] End Prompt ---")
                        results.append(
                            llm_runner.EvaluationResult(dossier, "MAYBE", "DRY_RUN")
                        )
                        continue

                    # 4b. Run LLM (pass settings for initialization)
                    llm_output = llm_runner.run_llm(
                        system_prompt, user_prompt, settings
                    )

                    # 4c. Parse Result
                    result = llm_runner.parse_llm_output(dossier, llm_output)
                    results.append(result)

            else:
                # LLM is disabled. Convert all passed dossiers directly to results.
                log.info(
                    "LLM evaluation is disabled. Generating report from pre-filtered accounts."
                )
                for dossier in final_dossiers:
                    results.append(
                        llm_runner.EvaluationResult(
                            dossier=dossier,
                            decision="MAYBE",  # Use MAYBE as a neutral default
                            reasoning="LLM evaluation was disabled.",
                        )
                    )

            # 5. Output Phase
            if results:
                report.write_report(results, discard_counts, settings)
            else:
                log.info("No active accounts were processed.")

        except ConnectionError as e:
            # This catches the lazy-init failure from get_client()
            log.error(f"Application failed to start: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
