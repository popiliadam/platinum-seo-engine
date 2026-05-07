"""tests/util/test_url_normalize.py — D-03 URL normalization invariant.

Single canonical implementation lives in :mod:`scripts.util.url_normalize`.
Ten transform/ingestion/validation modules delegate to it via an adapter
that wraps :class:`URLNormalizeError` into the caller's domain-specific
exception (K-01 dedup, v1.5-Phase-1 Tier 1).

Rules (D-03 invariant — deterministic + idempotent):
    1. Trim surrounding whitespace.
    2. Lowercase scheme + host (path/query case-preserved).
    3. IDN host -> punycode (idna ascii) when non-ASCII.
    4. Strip default port (:80 for http, :443 for https); keep others.
    5. Trailing slash on path: keep root '/' as-is, strip on others.
    6. Drop fragment (everything after '#').
    7. Drop tracking params (utm_*, gclid, fbclid, mc_cid, mc_eid, msclkid).
       Comparison is case-insensitive on the key (UTM_SOURCE == utm_source).
    8. Sort remaining query params by (key, value) for stable repr.

DURUR triggers (raise URLNormalizeError):
    * input is not a string
    * input is empty after trim
    * input has no scheme component
"""

from __future__ import annotations

import pytest

from scripts.util.url_normalize import URLNormalizeError, normalize_url


# ---------------------------------------------------------------------------
# Rule 1 — Lowercase scheme + host
# ---------------------------------------------------------------------------

def test_lowercase_scheme():
    assert normalize_url("HTTP://Example.com/Foo") == "http://example.com/Foo"


def test_lowercase_host():
    assert normalize_url("https://EXAMPLE.com/path") == "https://example.com/path"


def test_path_case_preserved():
    assert normalize_url("https://example.com/CamelCase") == "https://example.com/CamelCase"


def test_query_value_case_preserved():
    assert normalize_url("https://example.com/?Q=ValueABC") == "https://example.com/?Q=ValueABC"


# ---------------------------------------------------------------------------
# Rule 3 — IDN host → punycode
# ---------------------------------------------------------------------------

def test_idn_host_punycode():
    # Münih → xn--mnchen-3ya (idna ascii)
    assert normalize_url("https://münchen.example/page") == "https://xn--mnchen-3ya.example/page"


# ---------------------------------------------------------------------------
# Rule 4 — Strip default port
# ---------------------------------------------------------------------------

def test_strip_default_port_http_80():
    assert normalize_url("http://example.com:80/path") == "http://example.com/path"


def test_strip_default_port_https_443():
    assert normalize_url("https://example.com:443/path") == "https://example.com/path"


def test_keep_non_default_port():
    assert normalize_url("https://example.com:8080/path") == "https://example.com:8080/path"


# ---------------------------------------------------------------------------
# Rule 5 — Trailing slash collapse (root preserved)
# ---------------------------------------------------------------------------

def test_strip_trailing_slash_non_root():
    assert normalize_url("https://example.com/foo/") == "https://example.com/foo"


def test_keep_root_slash():
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_synthesize_root_slash_when_missing():
    # urlsplit on "https://example.com" yields path="" — implementation
    # promotes empty path to root slash for stable canonical form.
    assert normalize_url("https://example.com") == "https://example.com/"


# ---------------------------------------------------------------------------
# Rule 6 — Drop fragment
# ---------------------------------------------------------------------------

def test_drop_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_drop_fragment_with_query():
    assert normalize_url("https://example.com/page?a=1#section") == "https://example.com/page?a=1"


# ---------------------------------------------------------------------------
# Rule 7 — Drop tracking params (case-insensitive on key)
# ---------------------------------------------------------------------------

def test_drop_tracking_param_utm():
    assert normalize_url("https://example.com/?utm_source=google") == "https://example.com/"


def test_drop_tracking_param_gclid():
    assert normalize_url("https://example.com/?gclid=abc123") == "https://example.com/"


def test_drop_tracking_param_fbclid():
    assert normalize_url("https://example.com/?fbclid=xyz") == "https://example.com/"


def test_tracking_param_drop_case_insensitive():
    assert normalize_url("https://example.com/?UTM_SOURCE=google") == "https://example.com/"


def test_keep_non_tracking_query():
    assert normalize_url("https://example.com/?id=42") == "https://example.com/?id=42"


# ---------------------------------------------------------------------------
# Rule 8 — Sort query params
# ---------------------------------------------------------------------------

def test_sort_query_params():
    assert normalize_url("https://example.com/?b=2&a=1") == "https://example.com/?a=1&b=2"


def test_blank_query_value_preserved():
    # parse_qsl(keep_blank_values=True) preserves "?flag=" — caller depends
    # on this for boolean-flag style query strings.
    assert normalize_url("https://example.com/?flag=") == "https://example.com/?flag="


# ---------------------------------------------------------------------------
# Idempotency (D-03 self-check)
# ---------------------------------------------------------------------------

def test_idempotent_simple():
    once = normalize_url("https://example.com/path/?b=2&a=1#frag")
    twice = normalize_url(once)
    assert once == twice


def test_idempotent_complex():
    raw = "  HTTPS://Example.COM:443/Path/?utm_source=g&id=42#section  "
    once = normalize_url(raw)
    twice = normalize_url(once)
    assert once == twice
    assert once == "https://example.com/Path?id=42"


# ---------------------------------------------------------------------------
# Rule 1 — Whitespace trim
# ---------------------------------------------------------------------------

def test_strip_surrounding_whitespace():
    assert normalize_url("  https://example.com/  ") == "https://example.com/"


# ---------------------------------------------------------------------------
# Userinfo preservation (rare but must not be silently dropped)
# ---------------------------------------------------------------------------

def test_userinfo_preserved():
    out = normalize_url("https://user:pass@example.com/path")
    assert out == "https://user:pass@example.com/path"


# ---------------------------------------------------------------------------
# DURUR triggers
# ---------------------------------------------------------------------------

def test_non_string_raises():
    with pytest.raises(URLNormalizeError, match="must be a string"):
        normalize_url(123)  # type: ignore[arg-type]


def test_none_raises():
    with pytest.raises(URLNormalizeError, match="must be a string"):
        normalize_url(None)  # type: ignore[arg-type]


def test_empty_string_raises():
    with pytest.raises(URLNormalizeError, match="empty"):
        normalize_url("")


def test_whitespace_only_raises():
    with pytest.raises(URLNormalizeError, match="empty"):
        normalize_url("   ")


def test_no_scheme_raises():
    with pytest.raises(URLNormalizeError, match="missing scheme"):
        normalize_url("example.com/path")


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

def test_url_normalize_error_is_value_error():
    """URLNormalizeError extends ValueError so legacy bare-ValueError
    callers (quickwins_transform pre-K-01) keep working without code change."""
    assert issubclass(URLNormalizeError, ValueError)


def test_module_exports():
    import scripts.util.url_normalize as mod
    assert "normalize_url" in mod.__all__
    assert "URLNormalizeError" in mod.__all__
