#!/usr/bin/env python3
"""
tech_audit_transform.py — pure transform: DataForSEO Lighthouse +
on_page_content_parsing raw JSON → schema-shaped tech_seo rows.

Reads two paid-MCP raw responses per URL:
  - mcp__dataforseo__on_page_lighthouse  (~5-10 credits/URL — Performance,
    LCP, FID/INP, CLS, TBT, TTI, FCP audits)
  - mcp__dataforseo__on_page_content_parsing  (~2-3 credits/URL — title,
    meta description, H1 count, structured data presence, internal links,
    images alt coverage)

The transform aggregates issues per `issue_category` (Performance, Layout
Stability, Meta Tags, Headings, Structured Data) and emits rows shaped for
master.xlsx#tech_seo (6 cols, schema-locked):

    issue_category | detail | affected_urls | impact | resolution | priority

`impact` is the master-excel.schema severityEnum
(CRITICAL / HIGH / MEDIUM / LOW). `priority` maps impact → P0/P1/P2.

DFS HEAVY — paid MCP. Budget pre-flight is MANDATORY before any DFS call;
this transform exposes `preflight_budget()` (subprocess-based wrapper
around scripts/budget/check_budget.py) and `BudgetExceededError` as the
DURUR vehicle so the skill can route an `awaiting_approval` workflow
state per spec §10 + ADR-016.

Pure function discipline (mirrors quickwins_transform.py + dfs_pull.py):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports.
  - Idempotent: same input → same output.
  - severityEnum strict — only CRITICAL/HIGH/MEDIUM/LOW emitted.

CLI:
  python3 scripts/discovery/tech_audit_transform.py \\
      --lighthouse inbox/dfs/{date}-lighthouse-{slug}.json \\
      --content-parsing inbox/dfs/{date}-content_parsing-{slug}.json \\
      [--url-cap 50] \\
      [--output-dir _state/transform/{run_id}/]

Refs: schemas/master-excel.schema.json (tech_seo sheet, severityEnum
$defs), schemas/events.schema.json (source.kind=dataforseo_mcp,
target_excel_sheet=tech_seo, cost.credits per ADR-016),
schemas/skill-frontmatter.schema.json (frontmatter contract), spec §11.6
(DFS on-page tools), §16.5 (raw JSON inbox + transform), §16.8 (budget
pre-flight). Pattern reference: scripts/util/dfs_response.py
(canonical endpoint-aware DFS response normalize SSOT, Y-02 v1.6-Phase-3
Tier 1) + scripts/ingestion/dfs_pull.py (budget pre-flight integration).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

# scripts/budget is a namespace package (no __init__.py); make repo root
# importable so tests + CLI can both reach it.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Schema-locked column order for master.xlsx#tech_seo (6 cols, A..F).
TECH_SEO_COLUMNS: tuple[str, ...] = (
    "issue_category",
    "detail",
    "affected_urls",
    "impact",
    "resolution",
    "priority",
)

#: severityEnum values from schemas/master-excel.schema.json $defs.severityEnum.
#: Strict — transform only emits these four values for the impact column.
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

SEVERITY_ENUM: tuple[str, ...] = (
    SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
)

#: severity → priority bucket (rules: CRITICAL/HIGH→P0, MEDIUM→P1, LOW→P2).
_PRIORITY_BY_SEVERITY = {
    SEVERITY_CRITICAL: "P0",
    SEVERITY_HIGH: "P0",
    SEVERITY_MEDIUM: "P1",
    SEVERITY_LOW: "P2",
}

#: Severity ordering for stable sort (high-impact rows first in the sheet).
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ENUM)}

#: Issue category labels (no slug literals — generic SEO domain vocabulary).
CATEGORY_PERFORMANCE = "Performance"
CATEGORY_LAYOUT = "Layout Stability"
CATEGORY_META = "Meta Tags"
CATEGORY_HEADINGS = "Headings"
CATEGORY_STRUCTURED_DATA = "Structured Data"

#: Cap on affected_urls cell length (Excel friendliness — anything past this
#: is collapsed to a count + first-N sample).
AFFECTED_URLS_CHAR_CAP = 480
AFFECTED_URLS_SAMPLE_N = 5

#: Default DoS prevention cap on URL list length (configurable per project).
DEFAULT_URL_CAP = 50

#: Per-URL DFS credit estimates (worker brief / spec §11.6, conservative
#: upper-bounds — we always estimate the MAX so pre-flight is safe).
LIGHTHOUSE_CREDITS_PER_URL = 10        # 5-10 range, take 10
CONTENT_PARSING_CREDITS_PER_URL = 3    # 2-3 range, take 3


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TechAuditError(Exception):
    """Base class for tech_audit_transform errors."""


class BudgetExceededError(TechAuditError):
    """Budget pre-flight DURUR — DFS calls would exceed the daily cap.
    Skill must route to workflow_runner `awaiting_approval` state per
    spec §10."""


class URLCapExceededError(TechAuditError):
    """DoS prevention DURUR — caller passed > url_cap URLs."""


class LighthouseSchemaDriftError(TechAuditError):
    """Lighthouse response missing expected fields (e.g. performance score
    field renamed). Refuse to silently emit rows."""


class ContentParsingSchemaDriftError(TechAuditError):
    """on_page_content_parsing response missing expected fields. Refuse to
    silently emit rows."""


class RowSchemaError(TechAuditError):
    """Row drift: unexpected column set or non-severityEnum impact value."""


# ---------------------------------------------------------------------------
# DFS response shape adapter — canonical SSOT in scripts.util.dfs_response
# (Y-02 v1.6-Phase-3 Tier 1 dedup; was a local copy of dfs_pull pattern
# extended for Lighthouse inline at result-level). The canonical helper
# accepts an `endpoint_type` discriminator; binding here without one means
# "broadest tolerance" — the function still inspects Lighthouse inline
# payloads at the per-result level (preserving the original tech_audit
# semantic).
# ---------------------------------------------------------------------------

from scripts.util.dfs_response import (  # noqa: E402  (sys.path mutation above)
    normalize_dfs_response as _normalize_dfs_response,
)


# ---------------------------------------------------------------------------
# Budget pre-flight (subprocess wrapper around scripts/budget/check_budget.py)
# ---------------------------------------------------------------------------

def estimate_credits(
    url_count: int,
    *,
    use_lighthouse: bool = True,
    use_content_parsing: bool = True,
) -> int:
    """Conservative upper-bound credit estimate for a tech-audit run.

    lighthouse: 10 credits/URL (5-10 published range — pick max).
    content_parsing: 3 credits/URL (2-3 published range — pick max).
    """
    if url_count <= 0:
        return 0
    total = 0
    if use_lighthouse:
        total += url_count * LIGHTHOUSE_CREDITS_PER_URL
    if use_content_parsing:
        total += url_count * CONTENT_PARSING_CREDITS_PER_URL
    return total


def preflight_budget(
    *,
    estimated_credits: int,
    project_config_path: str | Path,
    events_path: str | Path,
    check_budget_script: str | Path | None = None,
) -> dict:
    """Run §16.8 budget pre-flight and DURUR if exceeded.

    Subprocess-based: invokes scripts/budget/check_budget.py and parses
    its stdout JSON envelope (single-line format documented in the
    script's docstring). The check script's exit code 0 means within
    budget (after summing 24h actual usage); we additionally fail when
    `actual + estimate > budget` so the pre-flight is forward-looking.

    Returns the merged budget envelope dict. Raises BudgetExceededError
    when projected usage exceeds the daily cap (skill routes the run to
    `awaiting_approval`). The exception message carries the full envelope
    so manager review has full context.
    """
    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)
    script = (
        Path(check_budget_script) if check_budget_script
        else _REPO_ROOT / "scripts" / "budget" / "check_budget.py"
    )

    if not script.exists():
        raise BudgetExceededError(
            f"budget pre-flight script missing: {script}"
        )

    try:
        proc = subprocess.run(
            [sys.executable, str(script),
             "--project-config", str(cfg_path),
             "--events", str(evt_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise BudgetExceededError(
            f"budget pre-flight timed out after 30s: {exc}"
        ) from exc

    # The script ALWAYS prints a one-line JSON envelope on stdout — even
    # when it exits 1 (exceeded). Parse it; if parsing fails, treat as
    # DURUR (safer than guessing).
    try:
        envelope = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise BudgetExceededError(
            f"budget pre-flight: malformed envelope (exit={proc.returncode}, "
            f"stdout={proc.stdout!r}, stderr={proc.stderr!r})"
        ) from exc

    used = float(envelope.get("used_24h", 0))
    budget = float(envelope.get("budget_per_day", 0))
    projected = used + float(estimated_credits)
    payload = {
        "budget_per_day": budget,
        "used_24h": used,
        "estimated_credits": int(estimated_credits),
        "projected_used": projected,
        "remaining_after": budget - projected,
        "exceeded": (projected > budget) or bool(envelope.get("exceeded")),
        "exit_code": proc.returncode,
    }
    if payload["exceeded"]:
        raise BudgetExceededError(
            f"budget pre-flight FAIL: projected={projected:.2f} > "
            f"budget={budget} (used_24h={used}, estimate={estimated_credits}, "
            f"exit={proc.returncode}). "
            "Route workflow to awaiting_approval per spec §10."
        )
    return payload


# ---------------------------------------------------------------------------
# Lighthouse extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LighthouseSignal:
    """One URL's lighthouse summary, normalised for downstream rules."""

    url: str
    performance_score: float | None     # 0..100
    lcp_seconds: float | None
    cls: float | None
    fcp_seconds: float | None
    tbt_ms: float | None
    tti_seconds: float | None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _extract_lighthouse_signal(item: dict) -> LighthouseSignal:
    """Pull the standard lighthouse audits out of a single DFS item.

    Tolerates two flavours:
      - DFS-wrapped: item['lighthouse']['categories']['performance']['score']
        + item['lighthouse']['audits'][{audit_id}]['numericValue']
      - Flat:        item['performance_score'], item['lcp'], etc.

    Lighthouse score is a 0..1 float upstream — we expose it as 0..100
    for downstream rule readability. LCP/FCP are seconds (numericValue is
    milliseconds; convert). CLS is a unitless float.
    """
    url = _safe_str(item.get("url") or item.get("page_url") or item.get("target"))

    lh = item.get("lighthouse") or {}
    if isinstance(lh, dict) and lh:
        cats = (lh.get("categories") or {})
        perf_cat = cats.get("performance") or {}
        score = _safe_float(perf_cat.get("score"))
        if score is not None and score <= 1.0:
            score = round(score * 100.0, 2)

        audits = lh.get("audits") or {}
        if not isinstance(audits, dict):
            audits = {}

        def _audit_num(audit_id: str) -> float | None:
            a = audits.get(audit_id) or {}
            if not isinstance(a, dict):
                return None
            return _safe_float(a.get("numericValue"))

        lcp_ms = _audit_num("largest-contentful-paint")
        fcp_ms = _audit_num("first-contentful-paint")
        tbt_ms = _audit_num("total-blocking-time")
        tti_ms = _audit_num("interactive")
        cls = _audit_num("cumulative-layout-shift")
        return LighthouseSignal(
            url=url,
            performance_score=score,
            lcp_seconds=(lcp_ms / 1000.0) if lcp_ms is not None else None,
            cls=cls,
            fcp_seconds=(fcp_ms / 1000.0) if fcp_ms is not None else None,
            tbt_ms=tbt_ms,
            tti_seconds=(tti_ms / 1000.0) if tti_ms is not None else None,
        )

    # Flat fallback.
    score = _safe_float(item.get("performance_score") or item.get("performance"))
    if score is not None and score <= 1.0:
        score = round(score * 100.0, 2)
    return LighthouseSignal(
        url=url,
        performance_score=score,
        lcp_seconds=_safe_float(item.get("lcp") or item.get("largest_contentful_paint")),
        cls=_safe_float(item.get("cls") or item.get("cumulative_layout_shift")),
        fcp_seconds=_safe_float(item.get("fcp") or item.get("first_contentful_paint")),
        tbt_ms=_safe_float(item.get("tbt") or item.get("total_blocking_time")),
        tti_seconds=_safe_float(item.get("tti") or item.get("interactive")),
    )


def _validate_lighthouse_items(items: Sequence[dict]) -> None:
    """Drift gate: every item must carry an identifiable URL AND at least
    one of the canonical performance signals (score or LCP). Empty input
    is OK (transform tolerates 0-URL runs); malformed items are not."""
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            raise LighthouseSchemaDriftError(
                f"lighthouse item {idx}: not a dict ({type(it).__name__})"
            )
        url = it.get("url") or it.get("page_url") or it.get("target")
        if not url:
            raise LighthouseSchemaDriftError(
                f"lighthouse item {idx}: missing url/page_url/target"
            )
        lh = it.get("lighthouse") or {}
        flat_perf = it.get("performance_score") or it.get("performance")
        # Item must either expose a wrapped lighthouse block OR a flat
        # performance signal — otherwise the field was renamed upstream
        # and we refuse to silently mask the drift.
        has_wrapped = isinstance(lh, dict) and (
            (lh.get("categories") or {}).get("performance") is not None
            or lh.get("audits") is not None
        )
        if not has_wrapped and flat_perf is None and it.get("lcp") is None:
            raise LighthouseSchemaDriftError(
                f"lighthouse item {idx} ({url!r}): missing performance "
                "score / lcp / lighthouse.categories.performance — schema drift"
            )


# ---------------------------------------------------------------------------
# Content parsing extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentSignal:
    """One URL's on_page_content_parsing summary."""

    url: str
    title: str
    title_length: int
    meta_description: str
    meta_description_length: int
    h1_count: int
    has_structured_data: bool
    is_commercial: bool
    internal_links: int
    images_total: int
    images_without_alt: int


def _extract_content_signal(item: dict) -> ContentSignal:
    """Pull canonical content_parsing fields out of one DFS item.

    DFS shape: item['page_content']['main_topic'] / item['meta'] etc.
    Flat shape: title/meta_description/h1 directly on item.
    """
    url = _safe_str(item.get("url") or item.get("page_url") or item.get("target"))

    meta_block = item.get("meta") or {}
    if not isinstance(meta_block, dict):
        meta_block = {}

    title = _safe_str(meta_block.get("title") or item.get("title"))
    meta_desc = _safe_str(
        meta_block.get("description")
        or meta_block.get("meta_description")
        or item.get("meta_description")
    )

    # H1 count: prefer page_content.h1.length when wrapped, else flat.
    page = item.get("page_content") or {}
    if not isinstance(page, dict):
        page = {}

    h1_value = page.get("h1") if "h1" in page else item.get("h1")
    if isinstance(h1_value, list):
        h1_count = len([h for h in h1_value if h])
    elif isinstance(h1_value, str):
        h1_count = 1 if h1_value.strip() else 0
    else:
        h1_count_field = item.get("h1_count")
        h1_count = _safe_int(h1_count_field) or 0

    # Structured data — DFS exposes `schema` blocks; we accept any non-empty
    # iterable as evidence of presence.
    schema_block = item.get("schema") or item.get("structured_data") or page.get("schema")
    if isinstance(schema_block, list):
        has_structured = bool(schema_block)
    elif isinstance(schema_block, dict):
        has_structured = bool(schema_block)
    else:
        has_structured = bool(item.get("has_structured_data"))

    # Commercial intent is a downstream hint — if the DFS payload tags it
    # we honour it, otherwise we treat as commercial when the URL path
    # contains a generic e-commerce token (cheap heuristic; avoids slug
    # literals).
    intent = _safe_str(item.get("page_intent") or item.get("intent")).lower()
    is_commercial = (
        intent in {"commercial", "transactional"}
        or bool(item.get("is_commercial"))
    )

    internal_links = _safe_int(
        page.get("internal_links_count")
        or item.get("internal_links_count")
        or item.get("internal_links")
    ) or 0

    images_total = _safe_int(
        page.get("images_count")
        or item.get("images_count")
        or item.get("images_total")
    ) or 0
    images_without_alt = _safe_int(
        page.get("images_without_alt")
        or item.get("images_without_alt")
    ) or 0

    return ContentSignal(
        url=url,
        title=title,
        title_length=len(title),
        meta_description=meta_desc,
        meta_description_length=len(meta_desc),
        h1_count=h1_count,
        has_structured_data=has_structured,
        is_commercial=is_commercial,
        internal_links=internal_links,
        images_total=images_total,
        images_without_alt=images_without_alt,
    )


def _validate_content_items(items: Sequence[dict]) -> None:
    """Drift gate: each item must carry a URL AND at least one of the
    canonical signals (meta block OR title OR page_content)."""
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            raise ContentParsingSchemaDriftError(
                f"content_parsing item {idx}: not a dict ({type(it).__name__})"
            )
        url = it.get("url") or it.get("page_url") or it.get("target")
        if not url:
            raise ContentParsingSchemaDriftError(
                f"content_parsing item {idx}: missing url/page_url/target"
            )
        # At least one of meta / page_content / title must be present —
        # otherwise the upstream schema renamed everything we care about.
        has_meta = isinstance(it.get("meta"), dict)
        has_page = isinstance(it.get("page_content"), dict)
        has_title = "title" in it
        if not (has_meta or has_page or has_title):
            raise ContentParsingSchemaDriftError(
                f"content_parsing item {idx} ({url!r}): missing "
                "meta / page_content / title — schema drift"
            )


# ---------------------------------------------------------------------------
# Issue detection — pure rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Finding:
    """One per-URL finding before category aggregation."""

    category: str
    label: str          # short detail label, e.g. "LCP slow"
    severity: str
    resolution: str
    url: str


def _performance_findings(sig: LighthouseSignal) -> list[_Finding]:
    out: list[_Finding] = []
    if sig.performance_score is not None and sig.performance_score < 50:
        out.append(_Finding(
            category=CATEGORY_PERFORMANCE,
            label=f"Performance score {sig.performance_score:.0f}/100",
            severity=SEVERITY_HIGH,
            resolution="Optimize images, defer unused JS, audit critical "
                      "rendering path",
            url=sig.url,
        ))
    if sig.lcp_seconds is not None and sig.lcp_seconds > 2.5:
        out.append(_Finding(
            category=CATEGORY_PERFORMANCE,
            label=f"LCP slow ({sig.lcp_seconds:.2f}s)",
            severity=SEVERITY_MEDIUM,
            resolution="Optimize hero image, preload LCP element, lazy-"
                      "load below-fold media",
            url=sig.url,
        ))
    if sig.fcp_seconds is not None and sig.fcp_seconds > 1.8:
        out.append(_Finding(
            category=CATEGORY_PERFORMANCE,
            label=f"FCP slow ({sig.fcp_seconds:.2f}s)",
            severity=SEVERITY_LOW,
            resolution="Reduce render-blocking resources, inline critical CSS",
            url=sig.url,
        ))
    return out


def _layout_findings(sig: LighthouseSignal) -> list[_Finding]:
    out: list[_Finding] = []
    if sig.cls is not None and sig.cls > 0.1:
        out.append(_Finding(
            category=CATEGORY_LAYOUT,
            label=f"Layout shift (CLS {sig.cls:.3f})",
            severity=SEVERITY_MEDIUM,
            resolution="Reserve space for images/embeds, set width+height "
                      "attributes, avoid late-inserted DOM nodes",
            url=sig.url,
        ))
    return out


def _meta_findings(sig: ContentSignal) -> list[_Finding]:
    out: list[_Finding] = []
    if sig.title and sig.title_length > 60:
        out.append(_Finding(
            category=CATEGORY_META,
            label=f"Title too long ({sig.title_length} chars)",
            severity=SEVERITY_LOW,
            resolution="Trim title to 50-60 chars, front-load primary keyword",
            url=sig.url,
        ))
    if not sig.meta_description:
        out.append(_Finding(
            category=CATEGORY_META,
            label="Meta description missing",
            severity=SEVERITY_MEDIUM,
            resolution="Write 140-160 char unique meta description with "
                      "primary keyword + CTA",
            url=sig.url,
        ))
    elif sig.meta_description_length > 160:
        out.append(_Finding(
            category=CATEGORY_META,
            label=f"Meta description too long ({sig.meta_description_length} chars)",
            severity=SEVERITY_MEDIUM,
            resolution="Trim meta description to <=160 chars to avoid truncation",
            url=sig.url,
        ))
    return out


def _heading_findings(sig: ContentSignal) -> list[_Finding]:
    if sig.h1_count == 1:
        return []
    if sig.h1_count == 0:
        label = "H1 missing"
    else:
        label = f"H1 anomaly ({sig.h1_count} H1 tags)"
    return [_Finding(
        category=CATEGORY_HEADINGS,
        label=label,
        severity=SEVERITY_MEDIUM,
        resolution="Use exactly one H1 per page, demote extras to H2",
        url=sig.url,
    )]


def _structured_data_findings(sig: ContentSignal) -> list[_Finding]:
    if sig.has_structured_data:
        return []
    if sig.is_commercial:
        return [_Finding(
            category=CATEGORY_STRUCTURED_DATA,
            label="Structured data missing on commercial page",
            severity=SEVERITY_LOW,
            resolution="Add Product/Service/Organization JSON-LD schema",
            url=sig.url,
        )]
    return []


def _detect_findings(
    lighthouse_signals: Sequence[LighthouseSignal],
    content_signals: Sequence[ContentSignal],
) -> list[_Finding]:
    findings: list[_Finding] = []
    for sig in lighthouse_signals:
        findings.extend(_performance_findings(sig))
        findings.extend(_layout_findings(sig))
    for sig in content_signals:
        findings.extend(_meta_findings(sig))
        findings.extend(_heading_findings(sig))
        findings.extend(_structured_data_findings(sig))
    return findings


# ---------------------------------------------------------------------------
# Aggregation → tech_seo rows
# ---------------------------------------------------------------------------

def _format_affected_urls(urls: Sequence[str]) -> str:
    """Comma-separate; collapse to count + first-N sample if > char cap."""
    deduped: list[str] = []
    seen: set[str] = set()
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)
    joined = ", ".join(deduped)
    if len(joined) <= AFFECTED_URLS_CHAR_CAP:
        return joined
    sample = ", ".join(deduped[:AFFECTED_URLS_SAMPLE_N])
    return f"{len(deduped)} URLs (sample: {sample})"


def _max_severity(severities: Iterable[str]) -> str:
    """Return the highest-impact severity in the iterable (lowest rank)."""
    best = SEVERITY_LOW
    best_rank = _SEVERITY_RANK[SEVERITY_LOW]
    for s in severities:
        r = _SEVERITY_RANK.get(s, 99)
        if r < best_rank:
            best_rank = r
            best = s
    return best


def _aggregate_to_rows(findings: Sequence[_Finding]) -> list[dict]:
    """Group findings by issue_category, build tech_seo rows."""
    if not findings:
        return []

    by_cat: dict[str, list[_Finding]] = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)

    rows: list[dict] = []
    for category, items in by_cat.items():
        urls = [it.url for it in items if it.url]
        labels = sorted({it.label for it in items})
        severity = _max_severity(it.severity for it in items)
        # Resolution: deterministic — pick the resolution from the
        # highest-severity finding, fall back to the first.
        sorted_items = sorted(
            items,
            key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), f.label),
        )
        resolution = sorted_items[0].resolution

        # detail: count + comma-joined unique labels (capped).
        detail = f"{len(items)} finding(s): " + "; ".join(labels[:5])
        if len(labels) > 5:
            detail += f" (+{len(labels) - 5} more)"

        row = {
            "issue_category": category,
            "detail": detail,
            "affected_urls": _format_affected_urls(urls),
            "impact": severity,
            "resolution": resolution,
            "priority": _PRIORITY_BY_SEVERITY[severity],
        }
        _validate_row(row)
        rows.append(row)

    # Sort by impact desc (CRITICAL first), category asc for determinism.
    rows.sort(key=lambda r: (
        _SEVERITY_RANK.get(r["impact"], 99),
        r["issue_category"],
    ))
    return rows


def _validate_row(row: dict) -> None:
    """Defensive: row must carry exactly the schema-locked column set,
    and `impact` must be a severityEnum value."""
    if set(row.keys()) != set(TECH_SEO_COLUMNS):
        raise RowSchemaError(
            f"tech_seo row column drift: expected={set(TECH_SEO_COLUMNS)}, "
            f"got={set(row.keys())}"
        )
    if row["impact"] not in SEVERITY_ENUM:
        raise RowSchemaError(
            f"tech_seo row impact not in severityEnum: got={row['impact']!r}, "
            f"allowed={SEVERITY_ENUM}"
        )


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    *,
    lighthouse_raw: dict | None,
    content_parsing_raw: dict | None,
    url_cap: int = DEFAULT_URL_CAP,
) -> dict:
    """
    Transform DFS Lighthouse + on_page_content_parsing payloads into
    schema-shaped tech_seo rows.

    Args:
        lighthouse_raw: parsed JSON from
            mcp__dataforseo__on_page_lighthouse. None → no perf/layout
            findings (transform tolerates one-sided runs).
        content_parsing_raw: parsed JSON from
            mcp__dataforseo__on_page_content_parsing. None → no
            meta/heading/structured-data findings.
        url_cap: DoS prevention. raises URLCapExceededError when either
            payload's item count > url_cap.

    Returns:
        {
          "tech_seo": [<row dict>, ...],
          "meta": {
            "lighthouse_url_count": int,
            "content_parsing_url_count": int,
            "finding_count": int,
            "row_count": int,
            "url_cap": int,
          },
        }

    Raises:
        URLCapExceededError       — DoS prevention (item count > cap).
        LighthouseSchemaDriftError — lighthouse payload drift.
        ContentParsingSchemaDriftError — content_parsing payload drift.
        RowSchemaError            — defensive row validation (should
                                    not fire for module-built rows).
        ValueError                — payload shape unparseable.
    """
    if not isinstance(url_cap, int) or url_cap < 1:
        raise ValueError(f"url_cap must be a positive int, got {url_cap!r}")

    lighthouse_signals: list[LighthouseSignal] = []
    if lighthouse_raw is not None:
        items = _normalize_dfs_response(
            lighthouse_raw, expected_endpoint="on_page_lighthouse",
        )
        if len(items) > url_cap:
            raise URLCapExceededError(
                f"lighthouse: {len(items)} URLs exceeds cap {url_cap} "
                "(DoS prevention; raise --url-cap or split the run)"
            )
        _validate_lighthouse_items(items)
        lighthouse_signals = [_extract_lighthouse_signal(it) for it in items]

    content_signals: list[ContentSignal] = []
    if content_parsing_raw is not None:
        items = _normalize_dfs_response(
            content_parsing_raw, expected_endpoint="on_page_content_parsing",
        )
        if len(items) > url_cap:
            raise URLCapExceededError(
                f"content_parsing: {len(items)} URLs exceeds cap {url_cap} "
                "(DoS prevention; raise --url-cap or split the run)"
            )
        _validate_content_items(items)
        content_signals = [_extract_content_signal(it) for it in items]

    findings = _detect_findings(lighthouse_signals, content_signals)
    rows = _aggregate_to_rows(findings)

    return {
        "tech_seo": rows,
        "meta": {
            "lighthouse_url_count": len(lighthouse_signals),
            "content_parsing_url_count": len(content_signals),
            "finding_count": len(findings),
            "row_count": len(rows),
            "url_cap": url_cap,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tech_audit_transform.py",
        description="Transform DFS Lighthouse + content_parsing JSON → "
                    "master.xlsx#tech_seo rows (6 cols, schema-locked).",
    )
    p.add_argument("--lighthouse", default=None,
                   help="Path to raw mcp__dataforseo__on_page_lighthouse JSON.")
    p.add_argument("--content-parsing", default=None,
                   help="Path to raw mcp__dataforseo__on_page_content_parsing JSON.")
    p.add_argument("--url-cap", type=int, default=DEFAULT_URL_CAP,
                   help=f"DoS prevention cap on URL count (default: {DEFAULT_URL_CAP}).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write tech_seo.json into this directory.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    lighthouse_raw: dict | None = None
    if args.lighthouse:
        lh_path = Path(args.lighthouse)
        if not lh_path.exists():
            print(f"lighthouse JSON not found: {lh_path}", file=sys.stderr)
            return 2
        lighthouse_raw = _read_json(lh_path)

    content_raw: dict | None = None
    if args.content_parsing:
        cp_path = Path(args.content_parsing)
        if not cp_path.exists():
            print(f"content_parsing JSON not found: {cp_path}", file=sys.stderr)
            return 2
        content_raw = _read_json(cp_path)

    try:
        result = transform(
            lighthouse_raw=lighthouse_raw,
            content_parsing_raw=content_raw,
            url_cap=args.url_cap,
        )
    except (
        URLCapExceededError,
        LighthouseSchemaDriftError,
        ContentParsingSchemaDriftError,
        RowSchemaError,
        ValueError,
    ) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts_path = out_dir / "tech_seo.json"
        ts_path.write_text(
            json.dumps(result["tech_seo"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "tech_seo_path": str(ts_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "TECH_SEO_COLUMNS",
    "SEVERITY_ENUM",
    "SEVERITY_CRITICAL",
    "SEVERITY_HIGH",
    "SEVERITY_MEDIUM",
    "SEVERITY_LOW",
    "CATEGORY_PERFORMANCE",
    "CATEGORY_LAYOUT",
    "CATEGORY_META",
    "CATEGORY_HEADINGS",
    "CATEGORY_STRUCTURED_DATA",
    "DEFAULT_URL_CAP",
    "LIGHTHOUSE_CREDITS_PER_URL",
    "CONTENT_PARSING_CREDITS_PER_URL",
    "TechAuditError",
    "BudgetExceededError",
    "URLCapExceededError",
    "LighthouseSchemaDriftError",
    "ContentParsingSchemaDriftError",
    "RowSchemaError",
    "LighthouseSignal",
    "ContentSignal",
    "_normalize_dfs_response",
    "estimate_credits",
    "preflight_budget",
    "transform",
    "main",
)
