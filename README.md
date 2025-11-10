# mastodon_finder

Mastodon account discovery, enrichment, and LLM-based scoring tool.

This project automates the workflow:

1. Discover candidate accounts on Mastodon via keywords, hashtags, profile terms, and "follow what they follow" expansion.
2. Enrich each account into a uniform dossier (bio, fields, recent original posts, stats, discovery reasons).
3. Apply a stack of deterministic pre-LLM filters (language, activity, link-only, bots, etc.).
4. Optionally hand each dossier to an LLM for rubric-based FOLLOW / MAYBE / SKIP decisions.
5. Output a human-readable report to the terminal (rich) and optionally to CSV / Markdown.


## Install (pipx)

This tool is intended to be used as a CLI. Prefer **pipx** so that dependencies stay isolated and you can update easily.

```bash
# If your package is published or in a local path, do something like:
pipx install mastodon-finder  # or: pipx install .
```

If you are developing locally:

```bash
# from repo root
pipx install --editable .
```

That will expose the `mastodon-finder` (module: `mastodon_finder`) entrypoint on your PATH without polluting your global Python.

## Quick Start

1. **Create a config** (once):

   ```bash
   mastodon-finder init
   ```

   This writes `finder.toml` and suggests adding it to `.gitignore`.

2. **Authenticate to Mastodon** (once per account):

   ```bash
   mastodon-finder auth
   ```

   This interactive flow will:

   * Ask for your instance URL (e.g. `mastodon.social`).
   * Register an app called `mastodon_finder` with `read` scope.
   * Open (print) an authorization URL.
   * Ask you to paste back the authorization code.
   * Write `MASTODON_BASE_URL=...` and `MASTODON_ACCESS_TOKEN=...` into `.env`.

3. **Run a discovery/eval pass**:

   ```bash
   mastodon-finder run --yes
   ```

   `--yes` skips the interactive "are you sure" run-summary.

You can override most things from the CLI without editing the TOML.

## CLI Overview

The main entrypoint is the package itself:

```bash
mastodon-finder [command]
```

Commands:

* `init` — write a starter `finder.toml` with reasonable defaults.
* `auth` — run interactive OAuth flow and append creds into `.env`.
* `run` (default) — perform discovery → enrichment → filter → (optional) LLM → report.

If you run without a subcommand, it defaults to `run`.


## Pipeline

1. Gets your current friend lists
2. Finds possible friends by keyword, hashtag, "follows special interest account"
3. Remove accounts with bad metrics (inactivity, no original content, etc)
4. Ask LLM to grade each candidate on a rubric
5. Display "FOLLOW", "MAYBE", "SKIP" report

## Features

- Search by keyword, hashtag for post, for account bio
- Search by "followers of an account" as signal of interest, geograph, etc.
- Filters out already followed
- Caching for info about self, e.g. current friends
- Caching for other API calls, e.g. for resuming a failed run
- langdetect for posts
- Filter
    - by minimum number of posts - is anyone one home
    - post recency - is anyone home now
    - original vs retweet - do they write their own content
    - original vs all links - is this an RSS feed cross posted to mastodon?
    - does the author ever reply to anyone?
- LLM filter
    - By static rubric
        - Is it the right language?
        - Is it the right topic?
        - Did it hit all the topics?
        - Is there some other unforeseen problem?


## Example Runs

**Run with alternative discovery terms:**

```bash
mastodon-finder run \
  --keywords python ai mastodon \
  --hashtags fediverse \
  --profile-keywords "django" "fastapi" \
  --max-accounts 80 \
  --max-statuses 120 \
  --yes
```

**Run without LLM, just pre-filters and report:**

```bash
mastodon-finder run --no-llm --yes
```

**Run focused on a single follow-target:**

```bash
mastodon-finder run \
  --follow-targets "@coolconnector@mastodon.social" \
  --follow-target-limit 500 \
  --yes
```

## How it works: Discovery & Filtering Pipeline

1. **Discovery** (`discovery.discover_accounts`)

   * Collects IDs and tags them with reasons.
   * Important: follow-target expansion can return *many* accounts, so there is a per-target limit.

2. **Enrichment** (`enrich.build_dossiers`)

   * Sorts candidates by number of discovery reasons (simple prioritization).
   * Stops at `limits.max_accounts`.
   * Produces a clean, LLM-ready, language-aware dossier list.

3. **Pre-LLM Filters** (`finder._pre_llm_filter`)

   * Activity cutoff (posted within N days).
   * Bot flag.
   * Language match (or "none").
   * Must-have replies.
   * Link-only threshold.
   * Minimum original posts.
   * "Friend full up" (high following/follower + low follow-back ratio).
   * Too chatty (posts/year cap).
   * Reject bio keywords (e.g. to block crypto/NFT/etc.).
   * Non-empty bio.
   * Minimum account age.
   * Special-case block for `bsky.brid.gy` relays.
   * Each discard increments a counter, reported at the end.

4. **LLM Evaluation** (optional)

   * Only on the survivors.
   * LLM rubric comes from `settings.llm.topics` and the fixed template.
   * Can be disabled with `--no-llm`, in which case all pre-filtered accounts become `MAYBE`.

5. **Output**

   * Rich terminal render with follow URLs normalized to your instance.
   * Optional CSV/MD report for offline review.

## Environment / Secrets

* `.env` is the source of truth for:

  * `MASTODON_BASE_URL`
  * `MASTODON_ACCESS_TOKEN`
  * `OPENROUTER_API_KEY` + `OPENROUTER_BASE_URL` + `OPENROUTER_MODEL` (optional)
  * `OPENAI_API_KEY` (optional)

`auth` will append the Mastodon entries for you. Keep `.env` out of version control.

## Reporting & Exports

* Terminal shows decisions, discovery reasons, first reasoning line, and a follow link rooted at **your** Mastodon host.
* CSV export makes it easy to sort/filter in spreadsheets.
* Markdown export is human-friendly for PRs or sharing with teammates.

## Prior Art

Bad profile search and bad search has been touted as an intentional privacy feature

### Directories

- [Trunk](https://communitywiki.org/trunk)
- [Fedi.Directory](https://fedi.directory/)

- [Just a bunch of sheets](https://researchbuzz.me/2022/11/05/a-big-list-of-mastodon-resources/) 