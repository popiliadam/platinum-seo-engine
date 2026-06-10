#!/usr/bin/env python3
"""
robots_policy_transform.py — pure robots.txt / noindex lifecycle governance.

Lints the LIVE robots.txt, scans for the R-133 noindex/disallow trap and R-58
lifecycle drift, and produces a recommendation-only proposed robots.txt + a
platform-specific deployment-instruction matrix — see
``rules/tech-seo-governance.md`` (R-131 governed policy, R-132 noindex deployment
path / R-58 deployability, R-133 mutual exclusion).

Key facts encoded (Google Search Central):
  - ``noindex`` in robots.txt is UNSUPPORTED → HIGH lint
    (https://developers.google.com/search/docs/crawling-indexing/block-indexing).
  - A robots.txt-disallowed page can never have its ``noindex`` seen → R-133 trap.
  - robots.txt is crawl-management, not index-removal.

Pure-function discipline (mirrors sf_projection / facet_nav_audit_transform):
  - No I/O in the compute path (the live fetch is the SKILL's Scrapling GET; this
    transform receives the already-fetched text — "" on a 404/unreachable, which
    yields a MEDIUM 'missing robots.txt', never a crash).
  - No master.xlsx writes; deterministic output; BOM-safe directive reads.
  - No paid MCP; no slug literals.
  - Recommendation-only: the engine NEVER writes to client infrastructure.

Refs: schemas/master-excel.schema.json (robots_txt 5-col + severityEnum),
scripts/util/sheet_merge.py (RP- merge-write the SKILL uses),
rules/tech-seo-governance.md (R-131..R-133, R-58 cross-link),
rules/content-html-discipline.md (R-58 lifecycle robots-meta map).
"""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

_DETAIL_CHAR_CAP = 300
_IMPORTANT_KINDS = {"product", "category", "blog", "hub"}

#: robots.txt directives the engine recognises (everything else = LOW unknown lint).
_KNOWN_DIRECTIVES = {
    "user-agent", "disallow", "allow", "sitemap", "crawl-delay",
    "host", "clean-param", "noindex", "request-rate", "visit-time",
}

#: R-132 deployment matrix keyed by the 6-value project.config[platform] enum.
#: ``verified`` is True ONLY where the mechanism is confirmable from official
#: platform docs; ticimax/ideasoft/imagaza carry verified=False with a generic
#: instruction (fabricating panel paths is forbidden — spec GAP-T3 §c).
PLATFORM_DEPLOYMENT_MATRIX: dict[str, dict[str, Any]] = {
    "wordpress": {
        "robots_txt_channel": "Rank Math/Yoast → SEO → Tools → robots.txt editor (or hosting file manager at web root)",
        "per_page_noindex_channel": "Rank Math/Yoast per-post panel → Advanced → Robots Meta → 'No Index'",
        "header_channel": "server: add `X-Robots-Tag: noindex` via .htaccess (Apache) or `add_header` (nginx)",
        "verified": True,
    },
    "wordpress+woocommerce": {
        "robots_txt_channel": "Rank Math/Yoast → SEO → Tools → robots.txt editor (or hosting file manager at web root)",
        "per_page_noindex_channel": "Rank Math/Yoast per-product panel → Advanced → Robots Meta → 'No Index' (WooCommerce product/category)",
        "header_channel": "server: add `X-Robots-Tag: noindex` via .htaccess (Apache) or `add_header` (nginx)",
        "verified": True,
    },
    "ticimax": {
        "robots_txt_channel": "platform panel veya destek talebi — kesin menü yolu operatör tarafından doğrulanmalı",
        "per_page_noindex_channel": "platform SEO paneli (sayfa bazlı robots meta) — menü yolu operatör tarafından doğrulanmalı",
        "header_channel": "platform/CDN config — X-Robots-Tag desteği operatör tarafından doğrulanmalı",
        "verified": False,
    },
    "ideasoft": {
        "robots_txt_channel": "platform panel veya destek talebi — kesin menü yolu operatör tarafından doğrulanmalı",
        "per_page_noindex_channel": "platform SEO paneli (sayfa bazlı robots meta) — menü yolu operatör tarafından doğrulanmalı",
        "header_channel": "platform/CDN config — X-Robots-Tag desteği operatör tarafından doğrulanmalı",
        "verified": False,
    },
    "imagaza": {
        "robots_txt_channel": "platform panel veya destek talebi — kesin menü yolu operatör tarafından doğrulanmalı",
        "per_page_noindex_channel": "platform SEO paneli (sayfa bazlı robots meta) — menü yolu operatör tarafından doğrulanmalı",
        "header_channel": "platform/CDN config — X-Robots-Tag desteği operatör tarafından doğrulanmalı",
        "verified": False,
    },
    "custom": {
        "robots_txt_channel": "edit /robots.txt at the web root and redeploy",
        "per_page_noindex_channel": "add `<meta name=\"robots\" content=\"noindex,follow\">` in the page <head> template",
        "header_channel": "nginx `add_header X-Robots-Tag \"noindex\";` or Apache `Header set X-Robots-Tag \"noindex\"`",
        "verified": True,
    },
}


# ---------------------------------------------------------------------------
# Exceptions (DURUR hierarchy)
# ---------------------------------------------------------------------------

class RobotsPolicyError(Exception):
    """Base class for robots-policy-audit transform errors."""


class RobotsDirectivesMissingError(RobotsPolicyError):
    """directives_all.csv was not provided (DURUR #2)."""


class RobotsLifecycleUnreadableError(RobotsPolicyError):
    """new_content_plan lifecycle rows unreadable / not provided (DURUR #3)."""


class RobotsProposedSiteWideBlockError(RobotsPolicyError):
    """The proposed robots.txt would disallow ``/`` — never emit (DURUR #4)."""


class RobotsDirectivesSchemaDriftError(RobotsPolicyError):
    """directives_all.csv rows carry no recognisable Address column (drift guard)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_key(key: Any) -> str:
    return str(key or "").lstrip("﻿").strip().strip('"').lower()


def _norm(row: dict) -> dict:
    return {_clean_key(k): v for k, v in row.items()}


def _truncate(text: str, cap: int = _DETAIL_CHAR_CAP) -> str:
    text = str(text or "")
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _finding(level: str, issue: str, detail: str, resolution: str) -> dict:
    return {
        "id": None,
        "level": level,
        "issue": _truncate(issue),
        "detail": _truncate(detail),
        "resolution": _truncate(resolution),
    }


def _parse_robots(text: str) -> dict:
    """Parse robots.txt into groups + global lists (sitemaps / noindex / unknown)."""
    groups: list[dict] = []
    cur: dict | None = None
    sitemaps: list[str] = []
    noindex_lines: list[str] = []
    unknown: list[str] = []
    last_was_agent = False
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            unknown.append(line)
            continue
        directive, value = line.split(":", 1)
        d = directive.strip().lower()
        v = value.strip()
        if d == "user-agent":
            if cur is None or not last_was_agent:
                cur = {"agents": set(), "disallow": [], "allow": []}
                groups.append(cur)
            cur["agents"].add(v.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if d in ("disallow", "allow"):
            if cur is None:
                cur = {"agents": {"*"}, "disallow": [], "allow": []}
                groups.append(cur)
            cur[d].append(v)
        elif d == "sitemap":
            sitemaps.append(v)
        elif d == "noindex":
            noindex_lines.append(line)
        elif d not in _KNOWN_DIRECTIVES:
            unknown.append(line)
    star_disallow = [p for g in groups if "*" in g["agents"] for p in g["disallow"]]
    return {
        "groups": groups,
        "star_disallow": star_disallow,
        "sitemaps": sitemaps,
        "noindex_lines": noindex_lines,
        "unknown": unknown,
    }


def _robotparser(text: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.parse((text or "").splitlines())
    return rp


def _is_noindex(nrow: dict) -> bool:
    meta = str(nrow.get("meta robots 1") or nrow.get("meta robots") or "").lower()
    xrobots = str(nrow.get("x-robots-tag 1") or nrow.get("x-robots-tag") or "").lower()
    return "noindex" in meta or "noindex" in xrobots


def _address(nrow: dict) -> str:
    return str(nrow.get("address") or "").strip()


def _slug_in_address(slug: str, address: str) -> bool:
    s = str(slug or "").strip("/").lower()
    return bool(s) and s in str(address or "").lower()


def _build_proposed(text: str, domain: str, facet_block: str | None) -> str:
    """Live file − unsupported/site-wide lines + Sitemap + optional facet block.

    Raises RobotsProposedSiteWideBlockError if the result would block ``/`` (#4).
    """
    kept: list[str] = []
    has_agent = False
    has_sitemap = False
    for raw in (text or "").splitlines():
        stripped = raw.split("#", 1)[0].strip()
        if not stripped or ":" not in stripped:
            continue
        directive, value = stripped.split(":", 1)
        d = directive.strip().lower()
        v = value.strip()
        if d == "noindex":
            continue  # Google-unsupported — never propagate
        if d == "disallow" and v == "/":
            continue  # never propagate a site-wide block
        if d == "user-agent":
            has_agent = True
        if d == "sitemap":
            has_sitemap = True
        kept.append(f"{directive.strip()}: {v}" if v else f"{directive.strip()}:")
    if not has_agent:
        kept.insert(0, "User-agent: *")
    if facet_block and facet_block.strip():
        kept.append("")
        for fl in facet_block.splitlines():
            if fl.strip():
                kept.append(fl.rstrip())
                if fl.strip().lower().startswith("sitemap:"):
                    has_sitemap = True
    if not has_sitemap:
        kept.append(f"Sitemap: https://{domain}/sitemap.xml")
    proposed = "\n".join(kept) + "\n"
    if "/" in _parse_robots(proposed)["star_disallow"]:
        raise RobotsProposedSiteWideBlockError(
            "proposed robots.txt would disallow '/' (site-wide block) — refusing "
            "to emit (DURUR #4); resolve the source of the site-wide Disallow first"
        )
    return proposed


def _render_deployment(platform: str) -> str:
    entry = PLATFORM_DEPLOYMENT_MATRIX.get(platform, PLATFORM_DEPLOYMENT_MATRIX["custom"])
    verified = "verified" if entry["verified"] else "UNVERIFIED (operator must confirm)"
    return (
        f"Platform: {platform} ({verified})\n"
        f"  1. robots.txt: {entry['robots_txt_channel']}\n"
        f"  2. per-page noindex: {entry['per_page_noindex_channel']}\n"
        f"  3. X-Robots-Tag header: {entry['header_channel']}\n"
    )


# ---------------------------------------------------------------------------
# Public transform
# ---------------------------------------------------------------------------

def transform(
    robots_txt_text: str | None,
    directives_rows: Iterable[dict] | None,
    internal_rows: Iterable[dict] | None,
    lifecycle_rows: Iterable[dict] | None,
    platform: str,
    domain: str,
    facet_block: str | None = None,
    url_patterns: list[dict] | None = None,
) -> dict:
    """Lint robots.txt + scan R-133/R-58 + build proposed file & deployment matrix.

    Returns ``{"robots_txt_rows", "proposed_robots_txt", "deployment_instructions",
    "summary"}``. ``robots_txt_rows`` carry id=None (sheet_merge assigns RP-NNN).
    """
    if directives_rows is None:
        raise RobotsDirectivesMissingError(
            "directives_all.csv not provided — run sf-import or use live SF mode (DURUR #2)"
        )
    if lifecycle_rows is None:
        raise RobotsLifecycleUnreadableError(
            "new_content_plan lifecycle rows unreadable (DURUR #3)"
        )

    directives = [_norm(r) for r in directives_rows]
    if directives and not any("address" in r for r in directives):
        raise RobotsDirectivesSchemaDriftError(
            "directives_all.csv has no 'Address' column — re-export with default "
            "data_fields or use live SF mode (drift guard)"
        )
    internal = [_norm(r) for r in (internal_rows or [])]
    lifecycle = [_norm(r) for r in lifecycle_rows]
    url_patterns = url_patterns or []

    parsed = _parse_robots(robots_txt_text or "")
    rp = _robotparser(robots_txt_text or "")
    findings: list[dict] = []

    # --- lint -------------------------------------------------------------
    if not (robots_txt_text or "").strip():
        findings.append(_finding(
            "MEDIUM", "Missing robots.txt (404 / empty)",
            f"No robots.txt found at https://{domain}/robots.txt. A robots.txt is "
            "recommended for crawl management + the Sitemap directive.",
            "Deploy the proposed robots.txt; include the Sitemap directive.",
        ))
    if parsed["noindex_lines"]:
        findings.append(_finding(
            "HIGH", "noindex: directive in robots.txt is unsupported by Google",
            f"{len(parsed['noindex_lines'])} `noindex:` line(s): "
            f"{', '.join(parsed['noindex_lines'][:5])}. Google ignores robots.txt "
            "noindex — de-indexing needs a crawlable meta/X-Robots noindex.",
            "Remove the noindex: lines; deploy noindex via the platform channel "
            "(per tech-seo-governance noindex-deployment rules).",
        ))
    if "/" in parsed["star_disallow"]:
        findings.append(_finding(
            "CRITICAL", "Site-wide Disallow: / blocks the entire site",
            f"robots.txt under User-agent: * contains `Disallow: /` — this blocks "
            f"crawling of the whole site at https://{domain}/.",
            "Remove the site-wide Disallow immediately unless the site is "
            "intentionally staged; the proposed file omits it.",
        ))
    if not parsed["sitemaps"]:
        findings.append(_finding(
            "MEDIUM", "Missing Sitemap: directive",
            "robots.txt declares no `Sitemap:` line — sitemap discovery relies on "
            "GSC submission only.",
            f"Add `Sitemap: https://{domain}/sitemap.xml` (proposed file includes it).",
        ))
    for line in parsed["unknown"][:10]:
        findings.append(_finding(
            "LOW", "Unknown / non-standard robots.txt directive",
            f"Unrecognised line: {line!r}.",
            "Verify the directive is intended; non-standard directives are ignored "
            "by Google.",
        ))

    # --- R-133 noindex/disallow mutual exclusion --------------------------
    conflict_urls = [
        _address(r) for r in directives
        if _is_noindex(r) and _address(r) and not rp.can_fetch("*", _address(r))
    ]
    if conflict_urls:
        findings.append(_finding(
            "HIGH", "noindex + robots.txt disallow conflict (mutual exclusion)",
            f"{len(conflict_urls)} URL(s) are BOTH disallowed in robots.txt AND "
            f"carry noindex — Google can never see the noindex (de-indexing trap). "
            f"Examples: {', '.join(conflict_urls[:5])}",
            "Deploy noindex, verify de-indexed, THEN disallow (per tech-seo-"
            "governance mutual-exclusion rules); remove the premature disallow now.",
        ))

    # --- R-58 lifecycle drift ---------------------------------------------
    on_hold_drift: list[str] = []
    removed_live: list[str] = []
    for lc in lifecycle:
        status = str(lc.get("lifecycle_status") or "").strip().upper()
        slug = lc.get("url_slug") or lc.get("url slug") or ""
        if status == "ON_HOLD":
            for d in directives:
                if _slug_in_address(slug, _address(d)) and not _is_noindex(d):
                    on_hold_drift.append(_address(d) or str(slug))
                    break
        elif status == "REMOVED":
            for i in internal:
                if _slug_in_address(slug, _address(i)) \
                        and str(i.get("indexability") or "").strip().lower() == "indexable":
                    removed_live.append(_address(i) or str(slug))
                    break
    if on_hold_drift:
        findings.append(_finding(
            "HIGH", "ON_HOLD lifecycle slug still indexable (R-58 noindex undeployed)",
            f"{len(on_hold_drift)} ON_HOLD page(s) are still `index` per directives — "
            f"the lifecycle noindex was never deployed. Examples: "
            f"{', '.join(on_hold_drift[:5])}",
            "Deploy noindex,follow via the platform deployment path (per tech-seo-"
            "governance noindex-deployment rules).",
        ))
    if removed_live:
        findings.append(_finding(
            "MEDIUM", "REMOVED lifecycle slug still live (200/indexable)",
            f"{len(removed_live)} REMOVED page(s) are still crawlable/indexable. "
            f"Examples: {', '.join(removed_live[:5])}",
            "Route through content-remediation (301/410 per content-update-"
            "discipline retire rules).",
        ))

    # --- important-page protection ----------------------------------------
    blocked_important: list[str] = []
    for up in url_patterns:
        if str(up.get("kind") or "").lower() not in _IMPORTANT_KINDS:
            continue
        pattern = str(up.get("pattern") or "").strip()
        if not pattern:
            continue
        path = pattern if pattern.startswith("/") else "/" + pattern
        if not rp.can_fetch("*", f"https://{domain}{path}"):
            blocked_important.append(f"{up.get('kind')}:{pattern}")
    if blocked_important:
        findings.append(_finding(
            "HIGH", "Important page pattern disallowed in robots.txt",
            f"robots.txt disallows URL pattern(s) for important page kind(s): "
            f"{', '.join(blocked_important)}. These should be crawlable.",
            "Remove the disallow for these patterns (the proposed file is a starting "
            "point — review before deploy).",
        ))

    proposed = _build_proposed(robots_txt_text or "", domain, facet_block)
    deployment = _render_deployment(platform)

    by_level: dict[str, int] = {}
    for r in findings:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
    summary = {
        "verdict": "FINDINGS" if findings else "COMPLIANT",
        "total_findings": len(findings),
        "by_level": by_level,
        "platform": platform,
        "platform_verified": PLATFORM_DEPLOYMENT_MATRIX.get(
            platform, PLATFORM_DEPLOYMENT_MATRIX["custom"]
        )["verified"],
        "has_sitemap": bool(parsed["sitemaps"]),
    }
    return {
        "robots_txt_rows": findings,
        "proposed_robots_txt": proposed,
        "deployment_instructions": deployment,
        "summary": summary,
    }


__all__ = (
    "transform",
    "PLATFORM_DEPLOYMENT_MATRIX",
    "RobotsPolicyError",
    "RobotsDirectivesMissingError",
    "RobotsLifecycleUnreadableError",
    "RobotsProposedSiteWideBlockError",
    "RobotsDirectivesSchemaDriftError",
)
