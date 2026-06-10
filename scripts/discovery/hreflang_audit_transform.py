#!/usr/bin/env python3
"""
hreflang_audit_transform.py — pure hreflang / i18n governance.

Computes the reciprocity graph from SF ``hreflang_all.csv``, validates codes +
x-default, joins return targets against ``internal_all`` indexability + status and
``canonicals_all``, and emits HF- findings into the ``robots_txt`` shape — see
``rules/tech-seo-governance.md`` (R-125 reciprocity, R-126 code/x-default validity,
R-127 locale consistency).

PASS-trivial on the single-language portfolio (tr-TR / en-CA / en-NG): zero
hreflang annotations → ``verdict: NOT_APPLICABLE`` (absence of hreflang is correct,
not a defect). Fully validates clusters when a multi-language client arrives.

Pure-function discipline (mirrors sf_projection / facet_nav_audit_transform):
  - No I/O in the compute path; never mutates the parsed CSV rows.
  - No master.xlsx writes (the SKILL commits via sheet_merge, prefix HF-).
  - BOM-safe header reads (``_clean_key``); deterministic output.
  - No paid MCP; no slug literals.

Code validity (R-126): a PERMISSIVE BCP-47-ish SHAPE regex
``^[a-z]{2,3}(-[A-Za-z]{4})?(-[A-Z]{2})?$|^x-default$`` (never RED on an
exotic-but-valid code like ``zh-Hant-TW``), PLUS the one documented region mistake
R-126 names — ``uk`` where the ISO code is ``gb`` (the regex alone accepts the
``en-UK`` shape, but R-126 flags it). No full ISO-3166 table → no false positives.

Refs: schemas/master-excel.schema.json (robots_txt 5-col + severityEnum),
scripts/util/sheet_merge.py (HF- merge-write the SKILL uses),
rules/tech-seo-governance.md (R-125..R-127),
https://developers.google.com/search/docs/specialty/international/localized-versions.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlsplit

_DETAIL_CHAR_CAP = 300
_OFFENDER_SAMPLE = 5

# Permissive BCP-47-ish SHAPE regex (R-126) — lang (+ optional script + region).
_CODE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{4})?(-[A-Z]{2})?$")
# Documented region mistakes R-126 names (region subtag -> ISO 3166-1 correction).
_COMMON_INVALID_REGIONS = {"uk": "GB"}

_CODE_COL_RE = re.compile(r"hreflang\s*(\d+)$")
_URL_COL_RE = re.compile(r"hreflang\s*(\d+)\s+url$")


# ---------------------------------------------------------------------------
# Exceptions (DURUR hierarchy)
# ---------------------------------------------------------------------------

class HreflangAuditError(Exception):
    """Base class for hreflang-audit transform errors."""


class HreflangSchemaDriftError(HreflangAuditError):
    """hreflang_all rows carry no recognisable hreflang columns (DURUR drift guard)."""


# ---------------------------------------------------------------------------
# BOM-safe helpers
# ---------------------------------------------------------------------------

def _clean_key(key: Any) -> str:
    return str(key or "").lstrip("﻿").strip().strip('"').lower()


def _normalize_row(row: dict) -> dict:
    return {_clean_key(k): v for k, v in row.items()}


def _truncate(text: str, cap: int = _DETAIL_CHAR_CAP) -> str:
    text = str(text or "")
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _finding(level: str, issue: str, detail: str, resolution: str, cap: int) -> dict:
    return {
        "id": None,
        "level": level,
        "issue": _truncate(issue, cap),
        "detail": _truncate(detail, cap),
        "resolution": _truncate(resolution, cap),
    }


def _nurl(url: Any) -> str:
    return str(url or "").strip()


def _is_absolute(url: str) -> bool:
    split = urlsplit(url)
    return bool(split.scheme and split.netloc)


def _sample(items: list[str]) -> str:
    head = items[:_OFFENDER_SAMPLE]
    suffix = "" if len(items) <= _OFFENDER_SAMPLE else f" (+{len(items) - _OFFENDER_SAMPLE} more)"
    return ", ".join(head) + suffix


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _has_any_hreflang_col(norm_rows: list[dict]) -> bool:
    for r in norm_rows:
        for k in r:
            if _CODE_COL_RE.search(k) or _URL_COL_RE.search(k):
                return True
    return False


def _extract_annotations(nrow: dict) -> list[tuple[str, str]]:
    """Pull (code, url) annotations from a normalized SF hreflang row."""
    codes: dict[str, str] = {}
    urls: dict[str, str] = {}
    for k, v in nrow.items():
        m = _URL_COL_RE.search(k)
        if m:
            urls[m.group(1)] = _nurl(v)
            continue
        m = _CODE_COL_RE.search(k)
        if m:
            codes[m.group(1)] = str(v or "").strip()
    anns: list[tuple[str, str]] = []
    for idx, code in codes.items():
        if not code:
            continue
        anns.append((code, urls.get(idx, "")))
    return anns


def _code_issue(code: str) -> str | None:
    """Return a human reason if ``code`` is invalid, else None (R-126 permissive)."""
    c = code.strip()
    if c.lower() == "x-default":
        return None
    if not _CODE_RE.match(c):
        return (f"malformed hreflang code {c!r} (expected ISO 639-1 language + "
                f"optional script/region, or x-default)")
    parts = c.split("-")
    region = parts[-1] if len(parts) >= 2 and len(parts[-1]) == 2 else None
    if region and region.lower() in _COMMON_INVALID_REGIONS:
        return (f"invalid region subtag in {c!r} — use "
                f"{_COMMON_INVALID_REGIONS[region.lower()]!r} (ISO 3166-1, not {region!r})")
    return None


def _lang_subtag(code: str) -> str:
    c = code.strip().lower()
    if c == "x-default" or not c:
        return ""
    return c.split("-", 1)[0]


# ---------------------------------------------------------------------------
# Public transform
# ---------------------------------------------------------------------------

def transform(
    hreflang_rows: Iterable[dict] | None,
    canonical_rows: Iterable[dict] | None = None,
    internal_rows: Iterable[dict] | None = None,
    content_locale: str = "",
    *,
    detail_cap: int = _DETAIL_CHAR_CAP,
) -> dict:
    """Validate hreflang clusters; emit HF- findings into the robots_txt shape.

    Returns ``{"robots_txt_rows", "summary", "verdict"}`` where verdict is one of
    ``COMPLIANT`` / ``FINDINGS`` / ``NOT_APPLICABLE``. Single-language reality
    (zero hreflang annotations) short-circuits to NOT_APPLICABLE with empty rows.
    """
    rows = list(hreflang_rows or [])
    if not rows:
        return _result([], "NOT_APPLICABLE", 0, 0)

    norm = [_normalize_row(r) for r in rows]
    if not _has_any_hreflang_col(norm):
        raise HreflangSchemaDriftError(
            "hreflang_all has no recognisable 'HTML hreflang N'/'... URL' columns — "
            "re-export hreflang_all with default data_fields or use live SF mode (DURUR)"
        )

    declares: dict[str, list[tuple[str, str]]] = {}
    for nrow in norm:
        addr = _nurl(nrow.get("address"))
        if not addr:
            continue
        declares[addr] = _extract_annotations(nrow)

    pages_with_hreflang = sum(1 for anns in declares.values() if anns)
    total_annotations = sum(len(anns) for anns in declares.values())
    if total_annotations == 0:
        # hreflang columns exist but every value is empty → no hreflang to validate.
        return _result([], "NOT_APPLICABLE", 0, pages_with_hreflang)

    # language-target set per page (excludes x-default — reciprocity is per-language)
    lang_targets: dict[str, set[str]] = {
        p: {_nurl(u) for c, u in anns if c.strip().lower() != "x-default" and _nurl(u)}
        for p, anns in declares.items()
    }

    # join maps for return-target validation
    idx_map = {_nurl(_normalize_row(r).get("address")): _normalize_row(r)
               for r in (internal_rows or []) if _nurl(_normalize_row(r).get("address"))}
    canon_map: dict[str, str] = {}
    for r in (canonical_rows or []):
        n = _normalize_row(r)
        a = _nurl(n.get("address"))
        if a:
            canon_map[a] = _nurl(n.get("canonical link element 1") or n.get("canonical"))
    for a, n in idx_map.items():  # internal_all also carries a canonical column
        canon_map.setdefault(a, _nurl(n.get("canonical link element 1") or n.get("canonical")))

    findings: list[dict] = []
    non_reciprocal: list[str] = []
    missing_self: list[str] = []
    relative_urls: list[str] = []
    code_problems: list[str] = []
    noindex_targets: list[str] = []
    noncanonical_targets: list[str] = []
    non200_targets: list[str] = []
    all_codes: list[str] = []
    has_x_default = False

    for page, anns in declares.items():
        if not anns:
            continue
        # self-reference (language targets must include the page itself)
        if lang_targets.get(page) and page not in lang_targets[page]:
            missing_self.append(page)
        for code, url in anns:
            all_codes.append(code)
            if code.strip().lower() == "x-default":
                has_x_default = True
            issue = _code_issue(code)
            if issue:
                code_problems.append(f"{page} → {issue}")
            target = _nurl(url)
            if target and not _is_absolute(target):
                relative_urls.append(f"{page}: {code}={target}")
                continue
            if not target:
                continue
            # reciprocity (language annotations only)
            if code.strip().lower() != "x-default" and target in declares and target != page:
                if page not in lang_targets.get(target, set()):
                    non_reciprocal.append(f"{page} → {target}")
            # return-target indexability / canonical / status (only where we have data)
            irow = idx_map.get(target)
            if irow is not None:
                indexability = str(irow.get("indexability") or "").strip().lower()
                istatus = str(irow.get("indexability status") or "").strip().lower()
                status_code = str(irow.get("status code") or "").strip()
                if indexability == "non-indexable" or "noindex" in istatus:
                    noindex_targets.append(target)
                elif status_code and status_code != "200":
                    non200_targets.append(target)
            canon = canon_map.get(target)
            if canon and canon != target:
                noncanonical_targets.append(target)

    cap = detail_cap

    if non_reciprocal:
        findings.append(_finding(
            "HIGH", "Non-reciprocal (one-directional) hreflang pair",
            f"{len(set(non_reciprocal))} pair(s) where A links B but B omits the "
            f"return link — Google IGNORES non-reciprocal annotations. "
            f"Examples: {_sample(sorted(set(non_reciprocal)))}",
            "Add the missing return link so every cluster member lists itself + all "
            "members (per tech-seo-governance hreflang reciprocity).", cap))
    if missing_self:
        findings.append(_finding(
            "MEDIUM", "Missing self-reference hreflang annotation",
            f"{len(set(missing_self))} page(s) declare alternates but do not list "
            f"themselves. Examples: {_sample(sorted(set(missing_self)))}",
            "Each page must include a self-referential hreflang for its own locale.", cap))
    if relative_urls:
        findings.append(_finding(
            "MEDIUM", "Relative / protocol-less hreflang URL",
            f"{len(set(relative_urls))} hreflang target(s) are not fully-qualified "
            f"absolute URLs. Examples: {_sample(sorted(set(relative_urls)))}",
            "hreflang targets must be absolute (scheme + host) URLs.", cap))
    if code_problems:
        findings.append(_finding(
            "MEDIUM", "Invalid hreflang language/region code",
            f"{len(set(code_problems))} invalid code(s). "
            f"Examples: {_sample(sorted(set(code_problems)))}",
            "Use ISO 639-1 language (+ optional ISO 3166-1 Alpha-2 region) or "
            "x-default (per tech-seo-governance hreflang code validity).", cap))
    if noindex_targets:
        findings.append(_finding(
            "HIGH", "hreflang return target is noindex / non-indexable",
            f"{len(set(noindex_targets))} hreflang target(s) are non-indexable — a "
            f"noindexed return target breaks the cluster. "
            f"Examples: {_sample(sorted(set(noindex_targets)))}",
            "Make the return target indexable, or remove it from the cluster.", cap))
    if noncanonical_targets:
        findings.append(_finding(
            "HIGH", "hreflang return target is non-self-canonical",
            f"{len(set(noncanonical_targets))} hreflang target(s) canonicalise to a "
            f"different URL — a non-self-canonical target breaks the cluster. "
            f"Examples: {_sample(sorted(set(noncanonical_targets)))}",
            "hreflang targets must be self-canonical (canonical == the URL itself).", cap))
    if non200_targets:
        findings.append(_finding(
            "HIGH", "hreflang return target returns non-200",
            f"{len(set(non200_targets))} hreflang target(s) are not HTTP 200. "
            f"Examples: {_sample(sorted(set(non200_targets)))}",
            "hreflang targets must return 200.", cap))

    distinct_langs = {_lang_subtag(c) for c in all_codes if _lang_subtag(c)}
    if len(distinct_langs) >= 2 and not has_x_default:
        findings.append(_finding(
            "LOW", "Missing x-default on a multi-language cluster",
            f"{len(distinct_langs)} language variants present but no x-default "
            "annotation (recommended for unmatched users, not required).",
            "Add an x-default hreflang pointing at the locale-selector or primary "
            "version.", cap))

    locale_lang = _lang_subtag(content_locale)
    if locale_lang and distinct_langs and locale_lang not in distinct_langs:
        findings.append(_finding(
            "MEDIUM", "Declared content locale absent from hreflang clusters (config ↔ site)",
            f"project.config content_locale {content_locale!r} (language {locale_lang!r}) "
            f"appears in no hreflang cluster (cluster languages: "
            f"{', '.join(sorted(distinct_langs))}).",
            "Extend the portfolio config to the real variants, or fix the site's "
            "hreflang (per tech-seo-governance locale consistency).", cap))

    cluster_count = _count_clusters(declares, lang_targets)
    verdict = "FINDINGS" if findings else "COMPLIANT"
    return _result(findings, verdict, cluster_count, pages_with_hreflang)


def _count_clusters(declares: dict, lang_targets: dict[str, set[str]]) -> int:
    """Connected components among crawled pages linked by language hreflang."""
    pages = [p for p, anns in declares.items() if anns]
    adj: dict[str, set[str]] = {p: set() for p in pages}
    page_set = set(pages)
    for p in pages:
        for t in lang_targets.get(p, set()):
            if t in page_set and t != p:
                adj[p].add(t)
                adj[t].add(p)
    seen: set[str] = set()
    clusters = 0
    for p in pages:
        if p in seen:
            continue
        clusters += 1
        stack = [p]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj[cur] - seen)
    return clusters


def _result(findings: list[dict], verdict: str, cluster_count: int,
            pages_with_hreflang: int) -> dict:
    by_level: dict[str, int] = {}
    for r in findings:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
    return {
        "robots_txt_rows": findings,
        "summary": {
            "verdict": verdict,
            "cluster_count": cluster_count,
            "findings_total": len(findings),
            "pages_with_hreflang": pages_with_hreflang,
            "by_level": by_level,
        },
        "verdict": verdict,
    }


__all__ = (
    "transform",
    "HreflangAuditError",
    "HreflangSchemaDriftError",
)
