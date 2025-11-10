# mastodon_finder/report.py

from __future__ import annotations

import csv
import logging
from typing import Dict, List

from rich import print as rprint

from mastodon_finder.llm_runner import EvaluationResult
from mastodon_finder.settings import Settings

log = logging.getLogger(__name__)

COLOR_MAP = {
    "FOLLOW": "bold green",
    "MAYBE": "bold yellow",
    "SKIP": "bold dim",
    "ERROR": "bold red",
    "DRY_RUN": "bold blue",
}

# Define the desired sort order for the final report
DECISION_ORDER = {
    "FOLLOW": 0,
    "MAYBE": 1,
    "SKIP": 2,
    "DRY_RUN": 3,
    "ERROR": 4,
}


def write_report(
    results: List[EvaluationResult],
    discard_counts: Dict[str, int],
    settings: Settings,
):
    """
    Writes a summary report to the console and optionally to a file (MD or CSV).
    Sorts the report by FOLLOW, MAYBE, SKIP.
    Includes a summary of discarded accounts.
    """

    log.info(f"\n--- Final Report: {len(results)} Accounts Evaluated ---")

    # --- 1. Sort Results ---
    def sort_key(res) -> int:
        return DECISION_ORDER.get(res.decision, 99)

    sorted_results = sorted(results, key=sort_key)

    # --- 2. Terminal Output (Rich) ---
    # Get user's base URL for follow links
    base_url = "mastodon.social"  # Default
    # --- Use settings object ---
    if settings.mastodon_base_url:
        # Strip protocol for a cleaner URL
        base_url = settings.mastodon_base_url.replace("https://", "").replace(
            "http://", ""
        )

    for res in sorted_results:
        color = COLOR_MAP.get(res.decision, "white")
        # Pad decision string for alignment (7 chars: "MAYBE", "FOLLOW", "SKIP")
        decision_str = f"[[{color}]{res.decision: <7}[/]]"

        # Format: https://<your_instance>/@<user>@<their_instance>
        follow_url = f"https://{base_url}/@{res.dossier.acct}"

        # Use rich print (rprint)
        rprint(f"\n{decision_str} {res.dossier.acct} ({follow_url})")
        rprint(f"  Discovered via: {', '.join(res.dossier.discovered_via)}")
        rprint(f"  Reasoning: {res.reasoning.splitlines()[0]}")  # First line

    # --- 3. Discard Summary ---
    rprint("\n[bold]--- Filter Discard Summary ---[/bold]")
    if not discard_counts:
        rprint("No accounts were discarded by pre-LLM filters.")
    else:
        for reason, count in sorted(discard_counts.items()):
            rprint(f"- [bold]{reason}[/bold]: {count} account(s)")

    # --- 4. File Output ---
    # --- Use settings object ---
    output_file = settings.output_file
    if output_file:
        log.info(f"Writing full report to {output_file}...")
        try:
            if output_file.endswith(".csv"):
                _write_csv(sorted_results, output_file)
            else:
                # Default to Markdown
                _write_md(sorted_results, output_file)
        except Exception as e:
            log.error(f"Failed to write report file: {e}")
            raise


def _write_md(results: List[EvaluationResult], filename: str) -> None:
    """Writes a Markdown report."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Mastodon Finder Report\n\n")
        f.write(f"Processed {len(results)} accounts.\n\n")

        # List is now pre-sorted by write_report
        for res in results:
            d = res.dossier
            f.write(f"## [{res.decision}] {d.display_name} (`{d.acct}`)\n\n")
            f.write(f"- **URL**: {d.url}\n")
            f.write(
                f"- **Stats**: {d.followers_count} Followers | {d.following_count} Following | {d.statuses_count} Posts\n"
            )
            f.write(f"- **Discovered**: {', '.join(d.discovered_via)}\n")
            f.write(f"- **Bio**: {d.note_text.replace(chr(10), ' ')}\n")
            f.write("\n**Reasoning:**\n")
            f.write(f"> {res.reasoning.replace(chr(10), ' ')}\n\n")
            f.write("---\n")


def _write_csv(results: List[EvaluationResult], filename: str) -> None:
    """Writes a CSV report (as per Spec 2)."""
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(
            [
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
        )
        # Rows (list is now pre-sorted by write_report)
        for res in results:
            d = res.dossier
            writer.writerow(
                [
                    res.decision,
                    d.acct,
                    d.display_name,
                    d.url,
                    d.followers_count,
                    d.following_count,
                    d.statuses_count,
                    "|".join(d.discovered_via),
                    res.reasoning.replace(chr(10), " "),
                    d.note_text.replace(chr(10), " "),
                ]
            )
