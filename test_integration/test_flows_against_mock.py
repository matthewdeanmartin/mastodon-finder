"""End-to-end finder flows (discovery + enrichment) against the mock.

These run the finder's *own* higher-level code — ``discovery.discover_accounts``
and ``enrich.build_dossier`` — over a real HTTP mock, which is where the dossier
builder's field-level expectations (note, fields, counts, created_at, content,
in_reply_to_id) get checked against what the mock actually serializes. This is
the most likely place to surface a mock gap.
"""

from __future__ import annotations

import datetime as dt

from mastodon_finder import discovery, enrich, mastodon_client
from mastodon_finder.settings import DiscoveryConfig, LimitsConfig


def _require_id(handle: str) -> int:
    """Resolve a seeded handle, failing the test if it doesn't resolve.

    Also narrows ``int | None`` to ``int`` for the calls below.
    """
    account_id = mastodon_client.lookup_account_id_by_handle(handle)
    assert account_id is not None, f"seeded handle {handle!r} should resolve"
    return account_id


def test_discover_accounts_by_keyword_and_hashtag(finder_client) -> None:
    disc = DiscoveryConfig(keywords=["ownership"], hashtags=["python"])
    limits = LimitsConfig(max_pages=2)

    candidates = discovery.discover_accounts(disc, limits)

    assert candidates, "discovery should find at least one candidate"
    rust_id = mastodon_client.lookup_account_id_by_handle("rustacean")
    py_id = mastodon_client.lookup_account_id_by_handle("pythonista")
    # "ownership" keyword → rustacean's post; "#python" hashtag → pythonista's.
    assert any("keyword:ownership" in reasons for reasons in candidates.values())
    assert rust_id in candidates
    assert py_id in candidates
    assert any("hashtag:python" in r for r in candidates[py_id])


def test_discover_accounts_via_follow_targets(finder_client) -> None:
    disc = DiscoveryConfig(follow_targets=["rustacean"])
    limits = LimitsConfig(follow_target_limit=-1)

    candidates = discovery.discover_accounts(disc, limits)

    f1 = mastodon_client.lookup_account_id_by_handle("follower_one")
    f2 = mastodon_client.lookup_account_id_by_handle("follower_two")
    assert f1 in candidates and f2 in candidates
    assert all("follows_target:rustacean" in candidates[i] for i in (f1, f2))


def test_discover_accounts_by_profile_term(finder_client) -> None:
    disc = DiscoveryConfig(profile_keywords=["Rusty"])
    limits = LimitsConfig()

    candidates = discovery.discover_accounts(disc, limits)

    rust_id = mastodon_client.lookup_account_id_by_handle("rustacean")
    assert rust_id in candidates
    assert any(r.startswith("profile_term:") for r in candidates[rust_id])


def test_build_dossier_has_well_formed_fields(finder_client) -> None:
    rust_id = _require_id("rustacean")

    dossier = enrich.build_dossier(rust_id, ["keyword:rust"], max_statuses=40)

    assert dossier is not None
    assert dossier.account_id == rust_id
    assert dossier.acct == "rustacean"
    assert dossier.display_name == "Rusty Dev"
    # note_text is HTML-stripped; the seed bio carried through.
    assert "Rust" in dossier.note_text
    assert isinstance(dossier.followers_count, int)
    assert isinstance(dossier.statuses_count, int)
    assert isinstance(dossier.created_at, dt.datetime)
    assert dossier.discovered_via == ["keyword:rust"]
    assert dossier.bot is False
    # recent_posts: list of (created_at, text, detected_lang) tuples.
    assert dossier.recent_posts
    for created_at, text, _lang in dossier.recent_posts:
        assert isinstance(created_at, dt.datetime)
        assert isinstance(text, str) and text


def test_build_dossier_marks_bot_accounts(finder_client) -> None:
    bot_id = _require_id("botaccount")
    dossier = enrich.build_dossier(bot_id, ["hashtag:rust"], max_statuses=40)
    assert dossier is not None
    assert dossier.bot is True


def test_dossier_separates_replies_from_original_posts(finder_client, rustacean_poster) -> None:
    """The dossier counts replies separately and keeps them out of recent_posts.

    Drives the finder's reply-filtering branch against statuses the mock
    actually marks with ``in_reply_to_id`` — verifying both that the mock sets
    the field and that the finder reads it correctly.
    """
    rust_id = _require_id("rustacean")

    # rustacean replies to its own first post → an in_reply_to_id status.
    own = rustacean_poster.account_statuses(rust_id, exclude_reblogs=True, limit=1)[0]
    rustacean_poster.status_post("a follow-up reply", in_reply_to_id=own.id)

    dossier = enrich.build_dossier(rust_id, ["keyword:rust"], max_statuses=40)
    assert dossier is not None
    assert dossier.reply_posts_found >= 1
    # No reply text should leak into the original-posts list.
    assert "follow-up reply" not in " ".join(text for _c, text, _l in dossier.recent_posts)


def test_account_statuses_excludes_reblogs(finder_client, rustacean_poster) -> None:
    """exclude_reblogs=True (what the dossier requests) actually filters boosts."""
    rust_id = _require_id("rustacean")
    py_id = _require_id("pythonista")

    # rustacean boosts one of pythonista's posts.
    py_post = rustacean_poster.account_statuses(py_id, limit=1)[0]
    rustacean_poster.status_reblog(py_post.id)

    with_reblogs = mastodon_client.get_account_statuses(rust_id, limit=40, exclude_reblogs=False)
    without_reblogs = mastodon_client.get_account_statuses(rust_id, limit=40, exclude_reblogs=True)
    assert with_reblogs is not None and without_reblogs is not None
    assert len(with_reblogs) == len(without_reblogs) + 1
    assert all(s.reblog is None for s in without_reblogs)
