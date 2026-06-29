# Spec: "Find Nice People" Workflow

## 1. Motivation

The original `mastodon-finder` workflow is **topic-driven**. You discover candidate
accounts (keywords, hashtags, profile terms, "follows what they follow"), run them
through deterministic mechanical filters, and then ask an LLM whether each account is
*on-topic* for a set of `llm.topics` (e.g. "COBOL", "software engineering"). The
LLM rubric in `prompt_builder.py` is almost entirely about topic match.

The **"find nice people"** workflow keeps the *exact same* discovery mechanism and the
*exact same* mechanical pre-LLM filters, but changes **what the LLM evaluates**. Instead
of "is this account on-topic?", we ask three orthogonal questions about the *person
behind the account*:

1. **Personhood** — Is this a real individual human, as opposed to an organization,
   brand, news outlet, project account, aggregator, or literal bot?
2. **Positive sentiment** — Is this person's posting tone generally positive /
   neutral / warm, as opposed to chronically cranky, angry, hostile, or doom-posting?
3. **Engagement / replies** — Is there evidence they actually *talk to* other people
   (reply, converse), rather than only broadcasting?

The idea: you find people because they orbit some account you like (the follow-target),
but you decide whether to follow them based on whether they seem like a *nice person to
have a conversation with* — not on topic.

## 2. Design principles

- **Preserve the existing workflow completely.** The topic-driven path must behave
  identically. The nice-people path is a *new, parallel* path selected by an explicit
  mode flag. No existing default changes behavior.
- **Reuse the pipeline.** Discovery, enrichment, dossiers, mechanical pre-LLM filters,
  the `EvaluationResult` shape, the parser, and the report are all reused unchanged.
- **Only the LLM rubric/prompt differs** between modes, plus a small amount of
  plumbing to select the prompt builder.
- **Same decision vocabulary** — `FOLLOW` / `MAYBE` / `SKIP` / `ERROR` — so the parser
  and report require no changes.

## 3. Mode selection

A new evaluation mode is introduced:

- `topic` (default) — the existing behavior.
- `nice` — the new "find nice people" rubric.

Selection precedence (lowest to highest), matching the existing settings layering:

1. Default: `topic`.
2. `finder.toml`: `[evaluation] mode = "nice"`.
3. CLI: `--mode {topic,nice}`, or the convenience flags `--nice` (= `--mode nice`)
   and `--topic` (= `--mode topic`).
4. Subcommand: `mastodon-finder find-nice` is sugar that runs `run` with mode forced
   to `nice`. All other `run` flags are accepted.

The mode lives on the `Settings` object as `settings.evaluation.mode`.

## 4. Mechanical filters (unchanged)

All deterministic pre-LLM filters from `finder._pre_llm_filter` apply **identically** in
both modes:

- Inactivity (`since_days`)
- Bot flag (`filter_bots`)
- Language match (`language`)
- Must-have replies (`filter_replies`)
- Link-only threshold (`filter_link_only`, `link_only_threshold`)
- Minimum original posts (`minimum_posts`)
- Bluesky bridge block
- Friend-full-up
- Too-chatty (`max_posts_per_year`)
- Reject-bio-keywords
- Non-empty bio (`filter_no_bio`)
- Minimum account age (`min_account_age_days`)

Note that `filter_replies` already gives a *mechanical* pre-screen for engagement; the
LLM `replies` axis is a softer, qualitative confirmation on top of it. The two are
complementary — keep both.

## 5. The "nice" rubric (LLM)

When `mode == "nice"`, prompt construction is delegated to
`nice_prompt_builder.build_prompt(dossier, settings)`. The `[ACCOUNT]`, `[BIO]`,
`[FIELDS]`, and `[RECENT ORIGINAL POSTS]` user-data sections are built exactly as in
the topic builder (we factor the shared section-building out so both builders stay in
sync). Only the `[RUBRIC]` system prompt differs.

### 5.1 System rubric

The model is told it is deciding whether to follow a Mastodon account **as a person
worth having friendly conversations with**, and is asked to score three axes:

- **person**: `yes` / `org` / `bot` / `unsure`
  - `yes` — a real individual human.
  - `org` — organization, company, brand, news outlet, project, team, or aggregator
    account (even if a human runs it).
  - `bot` — automated / scheduled / feed-mirroring account.
  - `unsure` — not enough signal.
- **sentiment**: `positive` / `neutral` / `negative` / `unsure`
  - Judge the *general emotional tone* of the recent posts. Occasional venting is
    fine; classify `negative` only when the account is *predominantly* cranky, angry,
    hostile, sneering, or relentlessly doom-posting.
- **replies**: `yes` / `no` / `unsure`
  - `yes` — evidence the person engages in back-and-forth conversation with others.
    The dossier carries a `reply_posts_found` count and a `discovered_via` list as
    hints; conversational, second-person, or "@"-addressed phrasing in the visible
    posts also counts.
  - `no` — appears to only broadcast.

### 5.2 Decision mapping

The model is instructed to map its three axis scores to a single decision:

- **FOLLOW** when: `person == yes` **and** `sentiment in {positive, neutral}` **and**
  `replies == yes`.
- **SKIP** when: `person in {org, bot}` **or** `sentiment == negative`.
- **MAYBE** otherwise (e.g. real person but `replies`/`sentiment` is `unsure`).

The model must still respond in the existing strict output contract so the existing
parser works unchanged:

```
DECISION: <FOLLOW|MAYBE|SKIP>
REASONING:
- person: <yes|org|bot|unsure> — <short why>
- sentiment: <positive|neutral|negative|unsure> — <short why>
- replies: <yes|no|unsure> — <short why>
```

`llm.topics` is **ignored** in nice mode (topic relevance is explicitly not a factor).
The language line from the rubric is still emitted when a language filter is active,
since "is this person posting in my language" remains relevant for conversation.

## 6. Plumbing changes (implementation)

| File | Change |
|------|--------|
| `settings.py` | Add `EvaluationConfig` (`mode: Literal["topic","nice"]`), add `evaluation` to `Settings`, merge `--mode` from CLI. |
| `prompt_builder.py` | Factor shared user-data section building into `build_user_sections(dossier)`; topic builder uses it. (Behavior identical.) |
| `nice_prompt_builder.py` | **New.** `build_prompt(dossier, settings)` reusing `build_user_sections`, with the nice rubric from §5. |
| `finder.py` | Add `--mode/--nice/--topic` to `run`; add `find-nice` subcommand; in the eval loop, pick the prompt builder by `settings.evaluation.mode`; show mode in the run summary. |
| `init.py` | Add a commented `[evaluation]` block documenting `mode`. |
| `report.py` | Unchanged. (Decision vocabulary is identical.) |
| `llm_runner.py` | Unchanged. |
| `enrich.py` / `discovery.py` | Unchanged. |

## 7. CLI

```bash
# Topic mode (unchanged default)
mastodon-finder run --yes

# Nice mode, three equivalent forms:
mastodon-finder run --nice --yes
mastodon-finder run --mode nice --yes
mastodon-finder find-nice --yes

# Nice mode driven by a follow-target (the canonical use case)
mastodon-finder find-nice \
  --follow-targets "@coolconnector@mastodon.social" \
  --follow-target-limit 500 \
  --yes
```

`--no-llm` still works in nice mode and yields `MAYBE` for every survivor, just as in
topic mode.

## 8. Testing

- `test_settings.py`: mode defaults to `topic`; toml `[evaluation] mode` parses;
  `--mode`, `--nice`, `--topic` override correctly.
- `test_nice_prompt_builder.py` (new): rubric mentions person/sentiment/replies, does
  **not** depend on `llm.topics`, reuses the same user-data sections, and emits the
  strict output contract. Language line present only when a language filter is active.
- Existing `test_prompt_builder.py` must still pass unchanged (topic path preserved).

## 9. Non-goals

- No change to discovery sources or mechanical filters.
- No new decision tokens; `FOLLOW/MAYBE/SKIP` reused.
- No sentiment model is trained locally — sentiment is judged by the LLM.
- No change to report formats.
