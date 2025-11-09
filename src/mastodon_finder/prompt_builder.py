# mastodon_finder/prompt_builder.py
from typing import List, Tuple

from mastodon_finder.config import DEFAULT_LANGUAGE_FILTER
from mastodon_finder.enrich import AccountDossier


def build_prompt(dossier: AccountDossier, user_topics: List[str]) -> Tuple[str, str]:
    """
    Converts an AccountDossier into system and user prompts
    for the LLM, as per Spec 4.5 and 5.
    """

    # --- [USER DATA] Section ---
    # This is the data specific to this one account
    account_lines = [
        "[ACCOUNT]",
        f"Handle: {dossier.acct}",
        f"Display name: {dossier.display_name}",
        f"URL: {dossier.url}",
        f"Followers: {dossier.followers_count}",
        f"Following: {dossier.following_count}",
        f"Statuses total: {dossier.statuses_count}",
        f"Account created: {dossier.created_at.date()}",
        f"Discovered because: {', '.join(dossier.discovered_via)}",
    ]

    # --- [BIO] Section ---
    bio_lines = [
        "\n[BIO]",
        dossier.note_text.strip() if dossier.note_text else "No bio provided.",
    ]

    # --- [FIELDS] Section ---
    field_lines = ["\n[FIELDS]"]
    if dossier.fields:
        for name, value in dossier.fields.items():
            field_lines.append(f"- {name}: {value}")
    else:
        field_lines.append("No profile fields set.")

    # --- [RECENT ORIGINAL POSTS] Section ---
    post_lines = ["\n[RECENT ORIGINAL POSTS]"]
    if dossier.recent_posts:
        for i, (timestamp, text, language) in enumerate(dossier.recent_posts, 1):
            # Limit post length for prompt tokens
            short_text = (text[:250] + "...") if len(text) > 250 else text
            post_lines.append(
                f"{i}. ({timestamp.date()}) {short_text.replace(chr(10), ' ')}"
            )
    else:
        post_lines.append("No recent original posts found.")

    # --- [SYSTEM PROMPT / RUBRIC] Section (from Spec 5) ---
    # This is the instruction set
    topics_str = ", ".join(user_topics)
    rubric_lines = [
        "\n[RUBRIC]",
        "You are an analyst deciding whether to follow a Mastodon account.",
        "You will be given a dossier on an account and must decide: FOLLOW, MAYBE, or SKIP.",
        "",
        "Follow if:",
        f"- Topic matches almost all of these: {topics_str}",
        "- Bio suggests a real person or project.",
        "",
        "Maybe if:",
        "- Topic is adjacent or signal is mixed.",
        "",
        "Skip if:",
        "- Strong negative sentiment to matched topics.",
        "- No relevant content.",
        "- Obvious bot or spam account.",
        f"- Language is primarily not {DEFAULT_LANGUAGE_FILTER}" "",
        "Respond *only* in this exact format:",
        "DECISION: <FOLLOW|MAYBE|SKIP>",
        "REASONING:",
        "- ...",
        "- ...",
    ]

    # Combine all parts
    user_prompt = "\n".join(account_lines + bio_lines + field_lines + post_lines)
    system_prompt = "\n".join(rubric_lines)

    return system_prompt, user_prompt
