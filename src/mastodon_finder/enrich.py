# mastodon_finder/enrich.py

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from langdetect import LangDetectException, detect

import mastodon_finder.mastodon_client as mastodon_client

log = logging.getLogger(__name__)


# --- Data Structure (from Spec 4.4) ---
@dataclass
class AccountDossier:
    account_id: int
    acct: str  # e.g., @user@instance.social
    display_name: str
    url: str
    followers_count: int
    following_count: int
    statuses_count: int
    created_at: datetime
    note_html: str
    note_text: str  # HTML stripped
    fields: Dict[str, str]  # Profile metadata fields
    discovered_via: List[str]
    bot: bool  # Account is marked as a bot
    reply_posts_found: int  # Number of replies in recent statuses
    recent_posts: List[Tuple[datetime, str, Optional[str]]] = field(
        default_factory=list
    )  # (ts, text, lang)

    # Helper property for filtering
    @property
    def latest_post_date(self) -> Optional[datetime]:
        return self.recent_posts[0][0] if self.recent_posts else None


# --- HTML Stripping Utility (from Cheat Sheet 13) ---
def strip_html(html_content: str) -> str:
    """Strips HTML tags to get plain text."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Replace <p> and <br> with newlines for readability
        for tag in soup.find_all(["p", "br"]):
            tag.append("\n")
        # .get_text() collapses whitespace, strip=True cleans ends
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return html_content  # Fallback


# --- Enrichment Function ---
def build_dossier(
    account_id: int, discovery_reasons: List[str], max_statuses: int
) -> Optional[AccountDossier]:
    """
    Fetches full account and status info to build a dossier.
    """
    log.info(f"Enriching account {account_id}...")

    # 1. Get Account Info (Cheat Sheet 3.3)
    acct = mastodon_client.get_account(account_id)
    if not acct:
        log.warning(f"Skipping account {account_id}: Failed to fetch profile.")
        return None

    # 2. Get Account Statuses (Cheat Sheet 3.4)
    statuses = mastodon_client.get_account_statuses(
        account_id, limit=max_statuses, exclude_reblogs=True
    )
    if statuses is None:
        log.warning(f"Skipping account {account_id}: Failed to fetch statuses.")
        return None  # Or return dossier with empty posts

    # 3. Normalize and Clean Data
    note_text = strip_html(acct.note)

    # Clean profile fields
    profile_fields = {}
    if acct.fields:
        for f in acct.fields:
            field_name = strip_html(f.name)
            field_value = strip_html(f.value)
            profile_fields[field_name] = field_value

    # Clean recent posts
    recent_posts = []
    # For reply filter
    replies_found = 0
    for p in statuses:
        # Logic for reply filter
        if p.in_reply_to_id:
            replies_found += 1
            continue  # Don't include replies in the dossier's post list

        post_text = strip_html(p.content)

        # Logic for language filter
        detected_lang = None
        if post_text:
            try:
                detected_lang = detect(post_text)
            except LangDetectException:
                log.debug(f"Could not detect language for post {p.id}")
                detected_lang = None

            recent_posts.append((p.created_at, post_text, detected_lang))

    # 4. Build and return dossier
    return AccountDossier(
        account_id=acct.id,
        acct=acct.acct,
        display_name=acct.display_name,
        url=acct.url,
        followers_count=acct.followers_count,
        following_count=acct.following_count,
        statuses_count=acct.statuses_count,
        created_at=acct.created_at,
        note_html=acct.note,
        note_text=note_text,
        fields=profile_fields,
        discovered_via=discovery_reasons,
        bot=acct.bot,
        reply_posts_found=replies_found,
        recent_posts=recent_posts,
    )


def build_dossiers(
    candidates: Dict[int, List[str]], max_statuses: int, max_accounts: int
) -> List[AccountDossier]:
    """Builds dossiers for all candidates, up to a limit."""
    dossiers = []

    # Sort candidates by # of discovery reasons (simple heuristic)
    sorted_candidates = sorted(
        candidates.items(), key=lambda item: len(item[1]), reverse=True
    )

    for account_id, reasons in sorted_candidates[:max_accounts]:
        dossier = build_dossier(account_id, reasons, max_statuses)
        if dossier:
            dossiers.append(dossier)

    log.info(f"Successfully enriched {len(dossiers)} dossiers.")
    return dossiers
