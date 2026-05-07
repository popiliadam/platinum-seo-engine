"""scripts/util/url_normalize.py — D-03 URL normalization (single canonical).

Ten transform/ingestion/validation modules previously each defined their
own ``normalize_url`` (or ``_normalize_url``) with the same 8-rule D-03
invariant.  Drift between the copies surfaced exactly once during the
2026-05-07 audit (K-01); this module collapses them into one authority
and the call-sites adapt-wrap :class:`URLNormalizeError` into their own
domain-specific exception classes.

Rules (D-03 invariant — deterministic + idempotent):
    1. Trim surrounding whitespace.
    2. Lowercase scheme + host (path/query case-preserved).
    3. IDN host -> punycode (idna ascii) when non-ASCII; raw-IP and
       underscore hosts fall back to lowercase ASCII.
    4. Strip default port (:80 for http, :443 for https); keep others.
    5. Trailing slash on path: keep root '/' as-is, strip on others.
       Empty path is promoted to '/' for stable canonical form.
    6. Drop fragment (everything after '#').
    7. Drop tracking params (utm_*, gclid, fbclid, mc_cid, mc_eid,
       msclkid). Comparison is case-insensitive on the key.
    8. Sort remaining query params by (key, value) for stable repr.
       parse_qsl(keep_blank_values=True) so ``?flag=`` round-trips.

DURUR triggers (raise :class:`URLNormalizeError`):
    * input is not a string
    * input is empty after trim
    * input has no scheme component

Refs:
    * spec D-03 (URL normalization invariant)
    * schemas/gsc-tool-mapping.schema.json (D-03 reference)
    * 2026-05-07 scripts audit K-01 closure (v1.5-Phase-1 Tier 1)
"""

from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

__all__ = ["URLNormalizeError", "normalize_url"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Scheme -> default port mapping. Only :80 (http) and :443 (https) are
#: stripped; non-default ports stay on the netloc.
_DEFAULT_PORTS: dict[str, str] = {"http": "80", "https": "443"}

#: Tracking-style query params dropped wholesale during normalization.
#: Kept intentionally narrow (UTM family + the four major ad-platform
#: click IDs) — dropping arbitrary keys would lose canonicality.
_TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
})


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class URLNormalizeError(ValueError):
    """Raised on invalid input to :func:`normalize_url`.

    Extends :class:`ValueError` so legacy callers that expected a bare
    ``ValueError`` (pre-K-01 ``quickwins_transform``) continue to work.
    Domain-specific call-sites wrap this into their own exception class
    via the import-adapter pattern documented in K-01.
    """


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Return the D-03 canonical form of ``url``.

    See module docstring for the full rule list and DURUR triggers.
    """
    if not isinstance(url, str):
        raise URLNormalizeError(
            f"url must be a string, got {type(url).__name__}"
        )
    raw = url.strip()
    if not raw:
        raise URLNormalizeError("url is empty")

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if not scheme:
        raise URLNormalizeError(f"url missing scheme: {url!r}")

    # Host: IDN -> punycode (with lowercase fallback for non-IDN-encodable
    # hosts such as raw IPs or underscore-bearing labels).
    host = parts.hostname or ""
    if host:
        try:
            host_ascii = host.encode("idna").decode("ascii")
        except (UnicodeError, UnicodeDecodeError):
            host_ascii = host.lower()
        else:
            host_ascii = host_ascii.lower()
    else:
        host_ascii = ""

    # Port: strip default-for-scheme; keep all others.
    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host_ascii}:{port}"
    else:
        netloc = host_ascii

    # Userinfo (rare). Re-quote conservatively so weird characters don't
    # break the canonical roundtrip.
    if parts.username is not None:
        user = quote(parts.username, safe="")
        if parts.password is not None:
            user = f"{user}:{quote(parts.password, safe='')}"
        netloc = f"{user}@{netloc}"

    # Path: empty -> '/', non-root trailing slash stripped.
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
        if not path:
            path = "/"

    # Query: drop tracking (case-insensitive key match), sort the rest.
    qs_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned = [(k, v) for (k, v) in qs_pairs if k.lower() not in _TRACKING_PARAMS]
    cleaned.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(cleaned, doseq=False)

    # Fragment dropped entirely (D-03 rule 6).
    return urlunsplit((scheme, netloc, path, query, ""))
