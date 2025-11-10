
---

## Configuration Layers

Settings are merged in this order:

1. **Hardcoded Pydantic defaults** (inside `settings.py`).
2. **`.env`** — secrets and API settings (Mastodon, LLM).
3. **`finder.toml`** — discovery, limits, filters, LLM defaults.
4. **CLI arguments** — final override.

This makes it easy to ship sensible defaults while letting specific runs override discovery targets or filters.

---

## What Each Module Does

* **`auth.py`** – interactive CLI OAuth:

  * prompts for instance URL,
  * registers app (`mastodon_finder`),
  * requests `read` scope,
  * exchanges code for token,
  * appends `MASTODON_BASE_URL` and `MASTODON_ACCESS_TOKEN` to `.env`.
  * handles common Mastodon errors cleanly.

* **`settings.py`** – the heart of configuration:

  * Pydantic models for discovery, limits, filters, LLM.
  * loads `.env` via `pydantic-settings`.
  * loads `finder.toml` via `tomli` if present.
  * merges CLI args on top.
  * validates Mastodon creds unless in dry-run mode.
  * exposes computed helpers like `language_filter`.

* **`init.py`** – writes starter `finder.toml` plus a `.gitignore` entry.

* **`mastodon_client.py`** – a thin, cached wrapper over `mastodon.py`:

  * creates a singleton client **only once** (first call must provide `Settings`).
  * normalizes base URL, verifies connection.
  * provides high-level functions: search by keyword, search by hashtag, account lookup by handle, get followers, get account, get statuses, get *your* following IDs.
  * implements filesystem pickled caches in `.cache` / `.cache_me` and cleans out old files.
  * hides Mastodon’s sometimes non-paginated search behavior.

* **`discovery.py`** – turns your search strategy into **candidate account IDs**:

  * search statuses by keyword → author → reason `keyword:<word>`
  * search statuses by hashtag → author → reason `hashtag:<tag>`
  * search accounts by profile terms → reason `profile_term:<term>`
  * expand via `follow_targets` → reason `follows_target:<handle>`
  * returns `{account_id: [reasons...]}`

* **`enrich.py`** – for each candidate account, build a uniform `AccountDossier`:

  * fetch account object → stats, URL, bio HTML, fields, created_at, bot flag.
  * fetch recent **original** posts (non-replies, non-boosts) up to `max_statuses`.
  * strip HTML from bio and fields via `BeautifulSoup`.
  * attempt language detection on posts via `langdetect`.
  * count how many replies we **skipped**, to support "must-reply" filters.

* **`finder.py`** – glue / CLI runner:

  * parses args, loads/merges settings, shows run summary,
  * initializes Mastodon client and **also fetches the accounts you already follow** so we don’t suggest them again,
  * discovery → enrichment → pre-LLM filters → LLM → report,
  * exits on common connection errors with deterministic codes.

* **`prompt_builder.py`** – converts an `AccountDossier` + `Settings` into a system prompt + user prompt, with a rubric and rigid output format.

* **`llm_runner.py`** – one-shot LLM caller & parser:

  * lazy-inits OpenAI / OpenRouter client based on `.env` and settings,
  * sends `[SYSTEM]` rubric + `[USER]` dossier,
  * expects output like:

    ```
    DECISION: FOLLOW
    REASONING:
    - ...
    ```
  * parses loose / malformed outputs and falls back to `MAYBE` with diagnostics.

* **`report.py`** – sorts decisions by usefulness (FOLLOW → MAYBE → SKIP → ERROR), renders to rich terminal, prints discard summary, and optionally writes CSV/Markdown.



---

## Notes on Mastodon API Behavior

* `search(...)` for statuses/accounts is **not** paginated like timelines; the client wrapper hides this and just returns what’s available.
* Timelines (like hashtag timelines) *are* paginated; the wrapper walks pages up to `limits.max_pages`.
* Account lookup by handle can return fuzzy matches; the wrapper tries to match exact `acct` first.
* Your own following list is fetched and cached separately in `.cache_me` so we can efficiently skip already-followed accounts.


---

## Development Hints

* The code is already separated into thin modules; unit tests can hit `discovery`, `enrich`, and the LLM parser independently.
* The LLM runner is defensive: even if the model returns junk, you still get a usable `EvaluationResult`.
* The Mastodon client is cached and cleanup is built in; delete `.cache` / `.cache_me` if you want to force fresh calls.

