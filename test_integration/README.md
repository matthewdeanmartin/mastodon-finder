# Integration tests (mastodon_mock-backed)

These tests run `mastodon_finder`'s **real** Mastodon client (real Mastodon.py,
real pickle caching, real pagination walkers) and its higher-level
discovery/enrichment flows against [`mastodon_mock`](../../mastodon_mock) — an
unpublished, stateful mock Mastodon server — booted as a local HTTP server. **No
live instance, no API keys.** The finder is read-only, so this is purely about
correctness and about finding gaps between the finder's expectations and the
mock.

## What they prove

- `mastodon_client`: singleton init + version/credential check, keyword/hashtag/
  account search, handle lookup, `account`/`account_statuses`, follower and
  following pagination, and the on-disk cache.
- `discovery.discover_accounts`: keyword, hashtag, profile-term, and
  "follow what they follow" expansion all resolve real candidates.
- `enrich.build_dossier`: every dossier field (note, fields, counts, created_at,
  content, in_reply_to_id, bot) is well-formed off the mock's serialization;
  replies are separated from original posts and reblogs are excluded.

## How it works

`conftest.py` boots `mastodon_mock` (session-scoped, in-memory, seeded with
searchable accounts, hashtagged statuses, and follow edges) and points a finder
`Settings` at it. An autouse fixture resets `mastodon_client`'s module-level
state per test — the singleton client, the `lru_cache` on the account id, and
the two pickle cache dirs (redirected to `tmp_path`) — so tests don't reuse a
client from a prior server or serve stale cached responses.

## Running

```bash
uv run pytest test_integration
# or
make test-integration
```

Self-skips on Python < 3.13 or if `mastodon_mock` is not installed (it is an
editable path dev dependency on the sibling repo; see `[tool.uv.sources]` in
`pyproject.toml`). Excluded from the default `make test` run. Drop the path
source for a version pin once `mastodon_mock` is published.

## Findings

See [`findings.md`](findings.md) for what driving the finder against the mock
taught us — most notably that Mastodon.py returns ids as `MaybeSnowflakeIdType`
(not `int`), which is fine for the finder but a real gotcha for any consumer.
