# tests/test_auth.py


import pytest

from mastodon_finder import auth

# --- Tests for _sanitize_url ---


@pytest.mark.parametrize(
    "url_in, expected_url_out",
    [
        # Standard case
        ("https://mastodon.social", "https://mastodon.social"),
        # Missing protocol
        ("mastodon.social", "https://mastodon.social"),
        # Trailing slash
        ("https://mastodon.social/", "https://mastodon.social"),
        # Both
        ("mastodon.social/", "https://mastodon.social"),
        # HTTP protocol
        ("http://mastodon.social", "http://mastodon.social"),
    ],
)
def test_sanitize_url(url_in, expected_url_out):
    """
    Tests that URLs are correctly normalized with https and no trailing slash.
    """
    assert auth._sanitize_url(url_in) == expected_url_out


# --- Tests for _get_instance_url ---


def test_get_instance_url_happy_path(monkeypatch):
    """
    Tests that a valid URL with a protocol is returned.
    """
    # Mock 'input' to return a valid URL
    monkeypatch.setattr("builtins.input", lambda _: "example.com")
    url = auth._get_instance_url()
    assert url == "https://example.com"
