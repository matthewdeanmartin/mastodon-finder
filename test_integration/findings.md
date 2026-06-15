# Findings from pointing mastodon-finder at mastodon_mock

Date: 2026-06-14. Goal: extra test coverage for the finder, and surfacing any
gaps/breaks in `mastodon_mock`. The finder is read-only, so unlike the
`activist` write tests there is no ban risk — this is pure correctness work.

## Headline finding (about Mastodon.py, not the mock)

**Account/status ids come back as `mastodon.types_base.MaybeSnowflakeIdType`,
not `int`.** This surfaced when an early test asserted `isinstance(account_id,
int)` and failed against the mock.

Behaviour of the wrapper:

- `int(id)` and `str(id)` work, and `id` compares **equal to another wrapper**
  of the same id (and survives pickling — which the finder's cache relies on).
- But `MaybeSnowflakeIdType(123) == 123` is **`False`**, and `123 in {wrapper}`
  is **`False`**. Wrapper-vs-plain-int equality does **not** hold.

Why it's fine for the finder today: both sides of every comparison come from
Mastodon.py (the discovery candidate keys are `status.account.id`; the
"already following" set is built from `acct["id"]`), so they're wrapper-vs-wrapper
and compare correctly — `finder.py`'s `if account_id in following_ids:` skip
logic works. **But it is a latent trap:** any place that mixes a hand-built
`int` id with an API-returned id (e.g. a CLI-supplied id, a DB integer, a test)
would silently miscompare. Worth a `int(...)` normalization at the client
boundary if that ever happens. Tests here assert int-*coercibility*, not
`isinstance(int)`.

This is a Mastodon.py contract, so it would behave identically against a real
server — the mock just made it visible.

## Mock behaviour: everything the finder needs works

Verified against the mock, all correct:

- `retrieve_mastodon_version()` / `me()` for client init.
- `search(result_type="statuses"|"accounts")` returns the right buckets;
  keyword and profile-term discovery resolve real candidates.
- `timeline("tag/<tag>")` + `fetch_next` paginate hashtag results.
- `account()` serializes every dossier field: `note`, `fields`,
  `followers_count`/`following_count`/`statuses_count`, `created_at` (a real
  `datetime`), `bot`, `last_status_at`.
- `account_statuses(exclude_reblogs=True)` genuinely filters boosts; statuses
  carry `in_reply_to_id` so the dossier's reply-vs-original split works.
- `account_followers` / `account_following` paginate; the finder's
  `max_followers` trim and `fetch_remaining` both behave.

## Mock limitation (by design, not a break)

**No federated `resolve`.** `search(q="@user@remote.example", resolve=True)`
returns zero accounts — the mock is local-only ("no webfinger resolve", see
`mastodon_mock/routers/search.py`). The finder's `lookup_account_id_by_handle`
handles an empty result gracefully (returns `None`), so discovery via a remote
follow-target handle simply finds nothing against the mock. Consumers that need
to exercise federated resolution can't do it here; a future mock enhancement
could synthesize a stub remote account when `resolve=True` and the handle has a
domain. Filed as a note, not fixed — no finder code path breaks on it.
