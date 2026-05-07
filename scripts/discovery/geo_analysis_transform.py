#!/usr/bin/env python3
"""
geo_analysis_transform.py — pure transform: DataForSEO LLM mentions search
+ SERP organic JSON → AEO/GEO actionable signals (3 staging tables).

Reads two raw DFS payloads:
  - mcp__dataforseo__ai_optimization_llm_mentions_search   (LLM mentions per
    query × model — visibility in LLM-generated answers)
  - mcp__dataforseo__serp_organic_live_advanced            (traditional SERP
    organic positions — current ranking baseline)

Cross-references both signals to surface AEO/GEO gaps:
  - LLM-visible AND SERP top-3        → "AEO_HEALTHY"   (monitor)
  - SERP top-3 but no LLM mention     → "AEO_NEEDED"    (write AEO content)
  - LLM-visible but no SERP top-3     → "SERP_GAP"      (boost SERP rank)
  - Neither                           → "ABSENT"        (research / pillar)

Cross-source URL canonicalization (D-03 invariant): both `cited_url`
(LLM payload, when present) and `serp_url` run through `_normalize_url`
before any join, so a trailing slash, fragment, or tracking param does
NOT desync the cross-source merge. The helper mirrors the spec from
`scripts.discovery.on_page_audit_transform._normalize_url` (re-implemented
here so this module is self-contained — D-03 is a project-wide rule, not
an on-page-audit-private helper, and re-exposing it keeps the import
graph shallow per W-B4 brief).

D-003 staging-only routing: the transform emits THREE staging tables and
NEVER writes to master.xlsx. The skill orchestrator persists each into
``_state/staging/geo_analysis_{table}_{date}_{slug}.json``. Phase 8+
downstream skills (e.g. cluster-map, monthly-report) consume these.

Pure function discipline (mirrors dfs_pull / on_page_audit_transform):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports.
  - Idempotent: same input → same output (`fetched_at` is the only
    intentional run-to-run field).

CLI:
  python3 scripts/discovery/geo_analysis_transform.py \\
      --raw-llm-mentions inbox/dfs/{date}-llm_mentions_search-{slug}.json \\
      --raw-serp         inbox/dfs/{date}-serp_organic-{slug}.json \\
      --project-name     "Acme Brand" \\
      [--project-slug    {slug}] \\
      [--output-dir      _state/transform/{run_id}/]

Errors raised:
  - GeoAnalysisError:        base class (DURUR).
  - LlmMentionsDriftError:   LLM mentions payload has shape drift
                             (model field renamed, mention_text missing).
  - BudgetExceededError:     subprocess `check_budget.py --check` exit 1
                             (skill caller invokes; helper exposed here
                             for clean test mocking).
  - ProjectNameMissingError: project_name (display_name) missing from
                             project config — `our_brand_mentioned`
                             match cannot run without it.

Refs: schemas/skill-frontmatter.schema.json (frontmatter contract),
schemas/events.schema.json (source.kind=dataforseo_mcp, staging-only ⇒
target_excel_sheet=null), schemas/cross-sheet-invariants.json (D-03 URL
canonicalization), spec §11.6 (LLM mentions tooling), §16.5 (raw inbox
+ transform stage), §16.8 (budget pre-flight).

IMPORT discipline: `_normalize_dfs_response` is imported from
`scripts.ingestion.dfs_pull` — copying the helper would silently fork
the REST/flat shape contract. See `test_geo_analysis.py::test_normalize_*`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
# scripts/* is a namespace package; ensure repo root is on sys.path so
# `from scripts.*` imports work both as a module and from the CLI entry-point.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover — import-time wiring
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (W-B4 brief): re-use the upstream helper rather than
# copying it — keeps DFS REST envelope vs flat wrapper tolerance in ONE
# place. Copying would silently fork the contract on the next DFS shape
# change. See tests/skills/test_geo_analysis.py for the import test.
from scripts.ingestion.dfs_pull import _normalize_dfs_response  # noqa: E402

# Canonical D-03 URL normalize (K-01 dedup, v1.5-Phase-1 Tier 1).
from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation above)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)


# ---------------------------------------------------------------------------
# Constants — staging table column shapes
# ---------------------------------------------------------------------------

#: Per-LLM-mention rows (one row per mention across all models per query).
LLM_MENTIONS_COLUMNS: tuple[str, ...] = (
    "query",
    "model",
    "mention_text",
    "cited_url",
    "our_brand_mentioned",
    "our_url_cited",
)

#: Per-SERP-position rows (one row per organic position per query, top 10).
SERP_ORGANIC_COLUMNS: tuple[str, ...] = (
    "query",
    "serp_position",
    "serp_url",
    "serp_title",
)

#: Cross-ref derived geo-signal rows (one row per query).
GEO_SIGNALS_COLUMNS: tuple[str, ...] = (
    "query",
    "llm_visibility_score",
    "our_brand_mentioned_count",
    "our_url_cited_count",
    "serp_top_3_present",
    "geo_gap",
    "action",
)

#: Mention text truncation cap (brief mandate ≤500 chars).
MENTION_TEXT_MAX_CHARS = 500

#: SERP top-3 threshold for cross-ref decision.
SERP_TOP_N = 3

#: AEO healthy threshold — mentioned in ≥50% of queried models.
AEO_HEALTHY_THRESHOLD = 0.5

#: Geo-gap labels (sort order = severity desc).
GAP_AEO_NEEDED = "AEO_NEEDED"
GAP_SERP_GAP = "SERP_GAP"
GAP_ABSENT = "ABSENT"
GAP_AEO_HEALTHY = "AEO_HEALTHY"

#: Sort order for output: AEO_NEEDED first (most actionable), then
#: SERP_GAP, ABSENT, AEO_HEALTHY (already-good, monitor only).
_GAP_SORT_RANK = {
    GAP_AEO_NEEDED: 0,
    GAP_SERP_GAP: 1,
    GAP_ABSENT: 2,
    GAP_AEO_HEALTHY: 3,
}

#: DFS LLM-mentions credit estimate (paid). Per spec §11.6 the endpoint
#: pricing varies by model fan-out; we default to a conservative 5 credits
#: per query (covers 4-5 models × 1 credit-equivalent).
CREDITS_PER_QUERY_LLM_MENTIONS = 5.0

#: DFS SERP organic_live_advanced ~1 credit per query (standard).
CREDITS_PER_QUERY_SERP_ORGANIC = 1.0

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class GeoAnalysisError(Exception):
    """Base error for geo-analysis transform failures (DURUR)."""


class LlmMentionsDriftError(GeoAnalysisError):
    """DFS llm_mentions_search payload has shape drift — model / mention_text
    field renamed or missing. STOP, surface to manager (DURUR)."""


class BudgetExceededError(GeoAnalysisError):
    """Budget pre-flight (`check_budget.py --check`) exited non-zero."""


class ProjectNameMissingError(GeoAnalysisError):
    """project.config display_name (project_name) is empty/missing — the
    `our_brand_mentioned` matcher cannot run without it."""


# ---------------------------------------------------------------------------
# URL canonicalization (D-03 invariant) — mirrors on_page_audit_transform
# ---------------------------------------------------------------------------

def _normalize_url(url: Any) -> str:
    """Hybrid D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Tolerant on empty / scheme-less input (returns "") — LLM citations
    may surface a brand without a full URL. Strict on non-string type
    (raises :class:`GeoAnalysisError`) so caller bugs are still loud.

    K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    if url is None or url == "":
        return ""
    if not isinstance(url, str):
        raise GeoAnalysisError(
            f"url must be a string, got {type(url).__name__}"
        )
    if not url.strip():
        return ""
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError:
        # Scheme-less / unparseable -> graceful empty (LLM citation tolerance).
        return ""


# ---------------------------------------------------------------------------
# Helpers — primitives
# ---------------------------------------------------------------------------

def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def _truncate(text: str, max_chars: int = MENTION_TEXT_MAX_CHARS) -> str:
    """Cap text at max_chars (UTF-8-safe slice on character boundary)."""
    if not isinstance(text, str):
        text = _safe_str(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _is_brand_match(text: str, brand: str) -> bool:
    """Case-insensitive substring presence; empty brand → False."""
    if not brand or not text:
        return False
    return brand.lower() in text.lower()


def _utc_iso_microseconds() -> str:
    """UTC ISO 8601 with microsecond precision and `+00:00` offset."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ---------------------------------------------------------------------------
# Cross-source data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LlmMentionRow:
    query: str
    model: str
    mention_text: str
    cited_url_normalized: str   # "" when no URL accompanies the mention
    our_brand_mentioned: bool
    our_url_cited: bool


@dataclass(frozen=True)
class SerpOrganicRow:
    query: str
    serp_position: int
    serp_url_normalized: str
    serp_title: str


# ---------------------------------------------------------------------------
# LLM mentions parsing (drift-strict)
# ---------------------------------------------------------------------------

def _extract_per_query_blocks(
    raw: dict,
    *,
    expected_endpoint: str,
) -> list[dict]:
    """Run `_normalize_dfs_response` and return the list of per-query
    item dicts. The DFS llm_mentions_search and serp_organic_live_advanced
    both return a list-of-items shape; the contents differ but the
    envelope is identical (REST or flat tolerated upstream)."""
    items = _normalize_dfs_response(raw, expected_endpoint=expected_endpoint)
    return [it for it in items if isinstance(it, dict)]


def _build_llm_mention_rows(
    raw: dict | None,
    *,
    project_name: str,
    project_url_root_norm: str,
) -> list[LlmMentionRow]:
    """Project DFS llm_mentions_search payload into per-mention rows.

    Drift detection: the items list is tolerated empty, but each non-empty
    item MUST carry a recognisable `model` field and either a top-level
    `mentions[]` list OR a single `mention_text` field. Renames or
    structurally absent fields raise LlmMentionsDriftError.

    Each item shape (DFS contract):
        {"keyword": "<query>",
         "model": "gpt-4" | "claude-sonnet-4" | ...,
         "mentions": [
             {"text": "...", "cited_url": "https://..."},
             ...
         ]}
    Or flat per-mention:
        {"keyword": "...", "model": "...",
         "mention_text": "...", "cited_url": "..."}
    """
    if raw is None:
        return []

    items = _extract_per_query_blocks(
        raw, expected_endpoint="ai_optimization_llm_mentions_search",
    )

    out: list[LlmMentionRow] = []
    for it in items:
        # Normalize the query field (DFS uses "keyword" historically; some
        # endpoints use "query"). Both are accepted.
        query_raw = it.get("keyword")
        if query_raw is None:
            query_raw = it.get("query")
        if query_raw is None:
            # Empty per-query block — DFS sometimes returns an empty stub
            # for queries the model couldn't process. Skip silently.
            continue
        query = _safe_str(query_raw).strip()
        if not query:
            continue

        model = it.get("model")
        if model is None:
            # Model field renamed/missing → drift signal (DURUR).
            raise LlmMentionsDriftError(
                f"llm_mentions_search item missing 'model' field for "
                f"query={query!r} — possible upstream shape drift"
            )
        model_str = _safe_str(model).strip()

        # Two shapes tolerated:
        #   nested:  it["mentions"] = [{"text": ..., "cited_url": ...}, ...]
        #   flat:    it has "mention_text" / "cited_url" directly.
        mentions_block = it.get("mentions")
        if isinstance(mentions_block, list) and mentions_block:
            mention_iter: Iterable[dict] = (
                m for m in mentions_block if isinstance(m, dict)
            )
        elif "mention_text" in it or "text" in it:
            mention_iter = iter([it])
        else:
            # No mentions array AND no flat mention_text — drift signal.
            raise LlmMentionsDriftError(
                f"llm_mentions_search item missing 'mentions[]' / "
                f"'mention_text' for model={model_str!r} query={query!r} — "
                "possible upstream shape drift"
            )

        for m in mention_iter:
            text_raw = m.get("mention_text")
            if text_raw is None:
                text_raw = m.get("text")
            if text_raw is None:
                # Per-mention drift — strictly required.
                raise LlmMentionsDriftError(
                    f"llm_mentions_search mention missing 'mention_text' "
                    f"for model={model_str!r} query={query!r}"
                )
            text = _truncate(_safe_str(text_raw))

            cited_url_raw = m.get("cited_url") or m.get("url") or ""
            cited_url_norm = _normalize_url(_safe_str(cited_url_raw))

            our_brand = _is_brand_match(text, project_name)
            # our_url_cited: D-03 normalized cited_url must startswith our
            # project root (same scheme+host). Empty cited_url → False.
            our_url_cited = (
                bool(cited_url_norm)
                and bool(project_url_root_norm)
                and cited_url_norm.startswith(project_url_root_norm)
            )

            out.append(LlmMentionRow(
                query=query,
                model=model_str,
                mention_text=text,
                cited_url_normalized=cited_url_norm,
                our_brand_mentioned=our_brand,
                our_url_cited=our_url_cited,
            ))

    return out


# ---------------------------------------------------------------------------
# SERP organic parsing
# ---------------------------------------------------------------------------

def _build_serp_organic_rows(raw: dict | None) -> list[SerpOrganicRow]:
    """Project DFS serp_organic_live_advanced payload into per-position rows.

    Each item carries `keyword` (the query) and `items[]` of organic
    positions. Each position has `rank_absolute` / `position`, `url`, `title`.
    """
    if raw is None:
        return []

    blocks = _extract_per_query_blocks(
        raw, expected_endpoint="serp_organic_live_advanced",
    )

    out: list[SerpOrganicRow] = []
    for blk in blocks:
        query_raw = blk.get("keyword") or blk.get("query") or ""
        query = _safe_str(query_raw).strip()
        if not query:
            continue

        # Per-block items[] hold the SERP positions (organic + features).
        # Some payloads inline the rank dict at top level; tolerate both.
        positions = blk.get("items")
        if not isinstance(positions, list):
            positions = blk.get("organic_results") or []
        if not isinstance(positions, list):
            positions = []

        for pos in positions:
            if not isinstance(pos, dict):
                continue
            # Filter to organic results — DFS interleaves SERP features
            # (knowledge_graph, video, etc.) which aren't ranking signals.
            type_field = pos.get("type")
            if type_field is not None and type_field != "organic":
                continue

            rank = pos.get("rank_absolute")
            if rank is None:
                rank = pos.get("position")
            if rank is None:
                continue
            rank_int = _safe_int(rank)
            if rank_int <= 0:
                continue

            url_raw = pos.get("url") or pos.get("link") or ""
            url_norm = _normalize_url(_safe_str(url_raw))
            title = _safe_str(pos.get("title"))

            out.append(SerpOrganicRow(
                query=query,
                serp_position=rank_int,
                serp_url_normalized=url_norm,
                serp_title=title,
            ))

    return out


# ---------------------------------------------------------------------------
# Cross-ref → geo signals
# ---------------------------------------------------------------------------

def _action_for_gap(gap: str) -> str:
    """Heuristic action recommendation per geo_gap label."""
    return {
        GAP_AEO_NEEDED: "write AEO-formatted answer content (FAQ + schema)",
        GAP_SERP_GAP: "boost SERP rank — internal links + content depth",
        GAP_AEO_HEALTHY: "monitor — already cited by LLMs",
        GAP_ABSENT: "research priority — pillar / cluster gap",
    }.get(gap, "investigate")


def _classify_gap(
    *,
    llm_visibility_score: float,
    serp_top_3_present: bool,
    our_brand_mentioned_count: int,
) -> str:
    """Decide the geo_gap label per the brief truth-table.

    Logic (priority order):
      1. SERP top-3 AND no LLM mention   → AEO_NEEDED  (most actionable)
      2. LLM mention but no SERP top-3   → SERP_GAP
      3. Brand mentioned in ≥50% LLMs    → AEO_HEALTHY
      4. Otherwise                       → ABSENT
    """
    has_llm = our_brand_mentioned_count > 0
    if serp_top_3_present and not has_llm:
        return GAP_AEO_NEEDED
    if has_llm and not serp_top_3_present:
        return GAP_SERP_GAP
    if llm_visibility_score >= AEO_HEALTHY_THRESHOLD and serp_top_3_present:
        return GAP_AEO_HEALTHY
    if has_llm and serp_top_3_present:
        # Mentioned in <50% of models AND SERP top-3 → still AEO_NEEDED
        # because the AEO surface area is the bigger lever.
        return GAP_AEO_NEEDED
    return GAP_ABSENT


def _build_geo_signal_rows(
    *,
    llm_rows: Sequence[LlmMentionRow],
    serp_rows: Sequence[SerpOrganicRow],
    project_url_root_norm: str,
) -> list[dict]:
    """Cross-reference per-query LLM + SERP signals → one geo signal row
    per query.

    llm_visibility_score = our_brand_mentioned_count / models_queried
                            (0.0–1.0). Computed as the count of distinct
                            models that mentioned the brand divided by the
                            count of distinct models seen for the query.
    """
    # Group LLM rows by query.
    by_query_llm: dict[str, list[LlmMentionRow]] = {}
    for r in llm_rows:
        by_query_llm.setdefault(r.query, []).append(r)

    # Group SERP rows by query.
    by_query_serp: dict[str, list[SerpOrganicRow]] = {}
    for r in serp_rows:
        by_query_serp.setdefault(r.query, []).append(r)

    all_queries = set(by_query_llm) | set(by_query_serp)
    out: list[dict] = []
    for q in sorted(all_queries):
        l_rows = by_query_llm.get(q, [])
        s_rows = by_query_serp.get(q, [])

        # Models seen for this query (including those that did NOT mention
        # the brand — denominator for the visibility score).
        models_seen = {r.model for r in l_rows if r.model}
        models_with_brand = {
            r.model for r in l_rows if r.our_brand_mentioned and r.model
        }
        models_queried_count = len(models_seen)
        brand_mentioned_count = len(models_with_brand)

        if models_queried_count == 0:
            llm_visibility_score = 0.0
        else:
            llm_visibility_score = round(
                brand_mentioned_count / models_queried_count, 4,
            )

        our_url_cited_count = sum(1 for r in l_rows if r.our_url_cited)

        # SERP top-N detection: project root present in any of the top-N
        # positions (D-03 normalized URL prefix).
        serp_top_3_present = False
        if project_url_root_norm:
            top_n_urls = [
                r.serp_url_normalized
                for r in s_rows
                if r.serp_position <= SERP_TOP_N
            ]
            serp_top_3_present = any(
                u.startswith(project_url_root_norm)
                for u in top_n_urls
                if u
            )

        gap = _classify_gap(
            llm_visibility_score=llm_visibility_score,
            serp_top_3_present=serp_top_3_present,
            our_brand_mentioned_count=brand_mentioned_count,
        )
        action = _action_for_gap(gap)

        out.append({
            "query": q,
            "llm_visibility_score": llm_visibility_score,
            "our_brand_mentioned_count": brand_mentioned_count,
            "our_url_cited_count": our_url_cited_count,
            "serp_top_3_present": serp_top_3_present,
            "geo_gap": gap,
            "action": action,
        })

    # Sort by gap severity (rank), then by query asc for determinism.
    out.sort(key=lambda r: (_GAP_SORT_RANK.get(r["geo_gap"], 99), r["query"]))
    return out


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    raw_llm_mentions: dict | None,
    raw_serp: dict | None,
    *,
    project_name: str,
    project_url_root: str = "",
    project_slug: str = "run",
    fetched_at: str | None = None,
) -> dict:
    """
    Build the three geo-analysis staging tables from raw DFS payloads.

    Args:
        raw_llm_mentions: parsed JSON of mcp__dataforseo__ai_optimization_llm_mentions_search.
                          None → empty mentions table.
        raw_serp:         parsed JSON of mcp__dataforseo__serp_organic_live_advanced.
                          None → empty serp table.
        project_name:     project display_name from project.config — REQUIRED
                          for our_brand_mentioned matching. Empty / missing
                          raises ProjectNameMissingError.
        project_url_root: project domain root (e.g. "https://example.com").
                          Empty disables our_url_cited / serp_top_3_present
                          (graceful) and causes those signals to be False.
        project_slug:     embedded in meta envelope; defaults to 'run'.
        fetched_at:       ISO 8601 timestamp; defaults to now (UTC, μs).

    Returns:
        {
          "llm_mentions": [...rows...],
          "serp_organic": [...rows...],
          "geo_signals":  [...rows...],
          "meta": {...},
        }

    Raises:
        ProjectNameMissingError: project_name empty/missing.
        LlmMentionsDriftError:   shape drift in raw_llm_mentions.
        ValueError:              unparseable DFS shape (via _normalize_dfs_response).
        GeoAnalysisError:        catch-all base.
    """
    if not isinstance(project_name, str) or not project_name.strip():
        raise ProjectNameMissingError(
            "project_name (project.config display_name) is empty or missing — "
            "configure project_name first; our_brand_mentioned matching "
            "cannot run without it"
        )

    ts = fetched_at or _utc_iso_microseconds()

    # D-03 normalize the project root URL once — used for our_url_cited
    # and serp_top_3_present checks.
    project_url_root_norm = _normalize_url(project_url_root) if project_url_root else ""

    # 1. Per-mention LLM rows.
    llm_rows = _build_llm_mention_rows(
        raw_llm_mentions,
        project_name=project_name,
        project_url_root_norm=project_url_root_norm,
    )

    # 2. Per-position SERP rows.
    serp_rows = _build_serp_organic_rows(raw_serp)

    # 3. Cross-ref per-query geo signals.
    geo_signals = _build_geo_signal_rows(
        llm_rows=llm_rows,
        serp_rows=serp_rows,
        project_url_root_norm=project_url_root_norm,
    )

    # Project to schema-locked column tuples (drop incidental keys, lock
    # column order). Each row dict carries exactly its declared columns.
    llm_mentions_table = [
        {
            "query": r.query,
            "model": r.model,
            "mention_text": r.mention_text,
            "cited_url": r.cited_url_normalized,
            "our_brand_mentioned": r.our_brand_mentioned,
            "our_url_cited": r.our_url_cited,
        }
        for r in llm_rows
    ]

    serp_organic_table = [
        {
            "query": r.query,
            "serp_position": r.serp_position,
            "serp_url": r.serp_url_normalized,
            "serp_title": r.serp_title,
        }
        for r in serp_rows
    ]

    geo_signals_table = [
        {k: r[k] for k in GEO_SIGNALS_COLUMNS}
        for r in geo_signals
    ]

    return {
        "llm_mentions": llm_mentions_table,
        "serp_organic": serp_organic_table,
        "geo_signals": geo_signals_table,
        "meta": {
            "project_slug": project_slug,
            "project_name": project_name,
            "project_url_root_norm": project_url_root_norm,
            "fetched_at": ts,
            "llm_mention_row_count": len(llm_mentions_table),
            "serp_organic_row_count": len(serp_organic_table),
            "geo_signal_row_count": len(geo_signals_table),
            "queries_analyzed": len({
                *(r["query"] for r in llm_mentions_table),
                *(r["query"] for r in serp_organic_table),
            }),
        },
    }


# ---------------------------------------------------------------------------
# Budget pre-flight (mirrors on_page_audit_transform / dfs_pull semantics)
# ---------------------------------------------------------------------------

def estimate_credits(query_count: int) -> float:
    """Estimate DFS credits for a geo-analysis run.

    llm_mentions_search:        ~5 credits per query (model fan-out).
    serp_organic_live_advanced: ~1 credit per query.
    """
    if query_count <= 0:
        return 0.0
    return float(query_count) * (
        CREDITS_PER_QUERY_LLM_MENTIONS + CREDITS_PER_QUERY_SERP_ORGANIC
    )


def preflight_budget(
    *,
    estimated_credits: float,
    project_config_path: str,
    events_path: str,
) -> dict:
    """Run the §16.8 budget pre-flight via the in-process check_budget
    helpers and DURUR if exceeded.

    Returns the parsed budget envelope on PASS. Raises BudgetExceededError
    on FAIL (estimate + 24h usage > daily cap).

    Mirrors `scripts.discovery.on_page_audit_transform.preflight_budget` —
    same boundary semantics: under budget → envelope; over → DURUR;
    module unavailable → DURUR (pre-flight is mandatory for paid MCPs).
    """
    try:
        from scripts.budget import check_budget as _cb
    except ImportError as exc:
        raise BudgetExceededError(
            "scripts.budget.check_budget unavailable — pre-flight "
            f"integration is mandatory for paid MCPs ({exc})"
        ) from exc

    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)

    try:
        budget = _cb._load_budget(cfg_path)  # type: ignore[attr-defined]
    except SystemExit as exc:
        raise BudgetExceededError(
            f"budget pre-flight: project-config unreadable ({cfg_path}): "
            f"exit={exc.code}"
        ) from exc

    used = _cb._sum_last_24h(  # type: ignore[attr-defined]
        evt_path, datetime.now(timezone.utc),
    )
    projected = float(used) + float(estimated_credits)
    payload = {
        "budget_per_day": int(budget),
        "used_24h": used,
        "estimated_credits": float(estimated_credits),
        "projected_used": projected,
        "remaining_after": float(budget) - projected,
        "exceeded": projected > float(budget),
    }
    if payload["exceeded"]:
        raise BudgetExceededError(
            f"budget pre-flight FAIL: projected={projected:.2f} > "
            f"budget={budget} (used_24h={used}, estimate={estimated_credits})"
        )
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="geo_analysis_transform.py",
        description=(
            "Transform DFS llm_mentions_search + serp_organic_live_advanced "
            "JSON → 3 staging tables (llm_mentions, serp_organic, geo_signals)."
        ),
    )
    p.add_argument(
        "--raw-llm-mentions", required=True,
        help="Path to raw mcp__dataforseo__ai_optimization_llm_mentions_search JSON.",
    )
    p.add_argument(
        "--raw-serp", default=None,
        help="Optional path to mcp__dataforseo__serp_organic_live_advanced JSON.",
    )
    p.add_argument(
        "--project-name", required=True,
        help="Project display_name (matches project.config) — used for "
             "our_brand_mentioned substring matching (case-insensitive).",
    )
    p.add_argument(
        "--project-url-root", default="",
        help="Project domain root (e.g. https://example.com) for "
             "our_url_cited / serp_top_3_present checks.",
    )
    p.add_argument(
        "--project-slug", default="run",
        help="Project slug embedded in meta envelope (default: 'run').",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write the 3 staging tables here as JSON.",
    )
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    llm_path = Path(args.raw_llm_mentions)
    if not llm_path.exists():
        print(f"raw llm_mentions JSON not found: {llm_path}", file=sys.stderr)
        return 2
    raw_llm = _read_json(llm_path)

    raw_serp: dict | None = None
    if args.raw_serp:
        serp_path = Path(args.raw_serp)
        if serp_path.exists():
            try:
                raw_serp = _read_json(serp_path)
            except (OSError, json.JSONDecodeError):
                raw_serp = None

    try:
        result = transform(
            raw_llm,
            raw_serp,
            project_name=args.project_name,
            project_url_root=args.project_url_root,
            project_slug=args.project_slug,
        )
    except (GeoAnalysisError, ValueError) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("llm_mentions", "serp_organic", "geo_signals"):
            out_path = out_dir / f"geo_analysis_{name}.json"
            out_path.write_text(
                json.dumps(result[name], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(json.dumps({
            "output_dir": str(out_dir.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "LLM_MENTIONS_COLUMNS",
    "SERP_ORGANIC_COLUMNS",
    "GEO_SIGNALS_COLUMNS",
    "MENTION_TEXT_MAX_CHARS",
    "SERP_TOP_N",
    "AEO_HEALTHY_THRESHOLD",
    "GAP_AEO_NEEDED",
    "GAP_SERP_GAP",
    "GAP_AEO_HEALTHY",
    "GAP_ABSENT",
    "CREDITS_PER_QUERY_LLM_MENTIONS",
    "CREDITS_PER_QUERY_SERP_ORGANIC",
    "GeoAnalysisError",
    "LlmMentionsDriftError",
    "BudgetExceededError",
    "ProjectNameMissingError",
    "_normalize_url",
    "transform",
    "estimate_credits",
    "preflight_budget",
    "main",
)
