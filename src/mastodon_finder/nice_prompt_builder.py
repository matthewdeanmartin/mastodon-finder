# mastodon_finder/nice_prompt_builder.py

from __future__ import annotations

from typing import Tuple

from mastodon_finder.enrich import AccountDossier
from mastodon_finder.prompt_builder import build_user_sections
from mastodon_finder.settings import Settings


def build_prompt(
    dossier: AccountDossier,
    settings: Settings,
) -> Tuple[str, str]:
    """
    Builds system and user prompts for the "find nice people" rubric.

    Unlike the topic-mode rubric, this one ignores ``llm.topics`` entirely and
    instead asks the model to score three orthogonal axes about the *person* behind
    the account: personhood, sentiment, and whether they reply to others. See
    spec/find_nice_people.md.

    The user-data portion of the prompt is identical to topic mode (shared via
    ``prompt_builder.build_user_sections``); only the rubric differs.
    """

    user_prompt = build_user_sections(dossier)

    lang_filter = settings.language_filter

    rubric_lines = [
        "\n[RUBRIC]",
        "You are deciding whether to follow a Mastodon account because the person "
        "behind it seems like a nice individual to have friendly conversations with.",
        "Topic relevance is NOT a factor. Do not consider what they post about, only "
        "who they are and how they behave.",
        "",
        "Score the account on three axes:",
        "",
        "1. person: yes | org | bot | unsure",
        "   - yes    = a real individual human.",
        "   - org    = organization, company, brand, news outlet, project, team, or "
        "aggregator account (even if a human runs it).",
        "   - bot    = automated, scheduled, or feed-mirroring account.",
        "   - unsure = not enough signal to tell.",
        "",
        "2. sentiment: positive | neutral | negative | unsure",
        "   - Judge the GENERAL emotional tone of the recent posts.",
        "   - Occasional venting is fine. Only choose 'negative' when the account is "
        "PREDOMINANTLY cranky, angry, hostile, sneering, or relentlessly doom-posting.",
        "",
        "3. replies: yes | no | unsure",
        "   - yes = there is evidence the person engages in back-and-forth "
        "conversation with others (replies, @-mentions, second-person/conversational "
        "phrasing). The dossier's 'Discovered because' and reply counts are hints.",
        "   - no  = appears to only broadcast, never converse.",
        "",
        "Map the three scores to a single decision:",
        "- FOLLOW: person == yes AND sentiment in {positive, neutral} AND replies == yes.",
        "- SKIP:   person in {org, bot} OR sentiment == negative.",
        "- MAYBE:  anything else (e.g. a real person but sentiment or replies is unsure).",
    ]

    # Language remains relevant for conversation even though topic does not.
    if lang_filter != "none":
        rubric_lines.append(
            f"- Lean toward SKIP if the person primarily posts in a language other "
            f"than '{lang_filter}'."
        )

    rubric_lines.extend(
        [
            "",
            "Respond *only* in this exact format:",
            "DECISION: <FOLLOW|MAYBE|SKIP>",
            "REASONING:",
            "- person: <yes|org|bot|unsure> - <short why>",
            "- sentiment: <positive|neutral|negative|unsure> - <short why>",
            "- replies: <yes|no|unsure> - <short why>",
        ]
    )

    system_prompt = "\n".join(rubric_lines)

    return system_prompt, user_prompt
