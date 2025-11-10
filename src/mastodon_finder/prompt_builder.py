# mastodon_finder/prompt_builder.py

from __future__ import annotations

from typing import Tuple

from mastodon_finder.enrich import AccountDossier
from mastodon_finder.settings import Settings


def build_prompt(
    dossier: AccountDossier,
    settings: Settings,
) -> Tuple[str, str]:
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
        # TODO: why ignoring language?
        for i, (timestamp, text, _language) in enumerate(dossier.recent_posts, 1):
            # Limit post length for prompt tokens
            short_text = (text[:250] + "...") if len(text) > 250 else text
            post_lines.append(
                f"{i}. ({timestamp.date()}) {short_text.replace(chr(10), ' ')}"
            )
    else:
        post_lines.append("No recent original posts found.")

    # --- [SYSTEM PROMPT / RUBRIC] Section ---
    # --- Use settings object ---
    topics_str = ", ".join(settings.llm.topics)
    lang_filter = settings.language_filter

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
    ]

    # Only add language filter rule if it's not 'none'
    if lang_filter != "none":
        rubric_lines.append(f"- Language is primarily not {lang_filter}")

    rubric_lines.extend(
        [
            "",
            "Respond *only* in this exact format:",
            "DECISION: <FOLLOW|MAYBE|SKIP>",
            "REASONING:",
            "- ...",
            "- ...",
        ]
    )

    # Combine all parts
    user_prompt = "\n".join(account_lines + bio_lines + field_lines + post_lines)
    system_prompt = "\n".join(rubric_lines)

    return system_prompt, user_prompt
