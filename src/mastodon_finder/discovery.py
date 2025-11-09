import logging
from typing import Dict, List, Set

import mastodon_finder.mastodon_client as mastodon_client

log = logging.getLogger(__name__)


def discover_accounts(
    keywords: List[str],
    hashtags: List[str],
    profile_keywords: List[str],
    profile_hashtags: List[str],
    max_pages_per_term: int,
) -> Dict[int, List[str]]:
    """
    Discovers candidate accounts from keywords and hashtags.
    Returns a dict mapping {account_id: [list_of_discovery_reasons]}.
    """
    # Use a set to auto-deduplicate reasons per account
    candidates: Dict[int, Set[str]] = {}

    # 1. Search by Keywords (in posts)
    for keyword in keywords:
        statuses = mastodon_client.search_statuses_by_keyword(
            keyword, max_pages_per_term
        )
        for status in statuses:
            try:
                # Use .account to get the author (Cheat Sheet 3.2)
                account_id = status.account.id
                candidates.setdefault(account_id, set()).add(f"keyword:{keyword}")
            except Exception as e:
                log.warning(f"Could not parse account from status {status.id}: {e}")

    # 2. Search by Hashtags (in posts)
    for tag in hashtags:
        statuses = mastodon_client.search_statuses_by_hashtag(tag, max_pages_per_term)
        for status in statuses:
            try:
                account_id = status.account.id
                candidates.setdefault(account_id, set()).add(f"hashtag:{tag}")
            except Exception as e:
                log.warning(f"Could not parse account from status {status.id}: {e}")

    # 3. Search by Profile Terms
    # Combine keywords and hashtags (with # prepended) into one list
    profile_terms = list(profile_keywords)
    profile_terms.extend([f"#{tag}" for tag in profile_hashtags])

    for term in profile_terms:
        # Call the new client function
        accounts = mastodon_client.search_accounts_by_keyword(term)
        for account in accounts:
            try:
                account_id = account.id
                candidates.setdefault(account_id, set()).add(f"profile_term:{term}")
            except Exception as e:
                log.warning(f"Could not parse account from profile search: {e}")

    # 4. Convert sets to lists for final output
    final_candidates = {id: list(reasons) for id, reasons in candidates.items()}
    log.info(
        f"Discovery phase complete. Found {len(final_candidates)} unique accounts."
    )

    return final_candidates
