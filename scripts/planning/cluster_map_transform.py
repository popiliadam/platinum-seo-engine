#!/usr/bin/env python3
"""
cluster_map_transform.py — pure transform: DataForSEO keyword_suggestions
+ related_keywords + GSC enhanced_search_analytics raw JSON →
schema-shaped rows for master.xlsx#cluster_keywords (11 cols).

Reads raw responses of:
  - mcp__dataforseo__dataforseo_labs_google_keyword_suggestions   (REQUIRED)
  - mcp__dataforseo__dataforseo_labs_google_related_keywords      (REQUIRED)
  - mcp__gsc__enhanced_search_analytics                           (REQUIRED — enrichment)
  - mcp__dataforseo__dataforseo_labs_search_intent                (optional intent boost)

Tolerates BOTH DFS response shapes via
``scripts.ingestion.dfs_pull._normalize_dfs_response`` (D-003 root-cause
fix — REST envelope ``tasks[0].result[0].items`` AND flat wrapper
``items``). The function is IMPORTED — never copied — so any future
shape fix in dfs_pull is inherited automatically.

Pure function discipline (mirrors dfs_pull.py + cannibalization /
content_gaps transforms):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. The cluster-map skill
    layer calls scripts.excel.transaction.append; this transform only
    PROJECTS rows into the schema-locked tuple.
  - Idempotent: same input → same output.

D-02 invariant (CRITICAL Phase 8 gate):
  ``cluster_keywords.cluster ⊆ data/cluster defs``. The transform
  REQUIRES a ``cluster_defs`` list (sourced from
  ``master.xlsx#topical_map`` column B by the skill layer). Every
  emitted row's cluster value MUST belong to that list — otherwise
  ``ClusterDefError`` (DURUR #7) is raised before any rows escape.

CLI:
  python3 scripts/planning/cluster_map_transform.py \\
      --raw-keyword-suggestions inbox/dfs/{date}-keyword_suggestions-cluster-{slug}.json \\
      --raw-related-keywords    inbox/dfs/{date}-related_keywords-cluster-{slug}.json \\
      --raw-gsc                 inbox/gsc/{date}-enhanced_search_analytics-cluster-{slug}.json \\
      --cluster-defs-json       /tmp/cluster_defs.json \\
      [--seed-keyword "<seed>"] \\
      [--keyword-cap 5000] \\
      [--default-status TODO] \\
      [--project-slug {slug}] \\
      [--output-dir _state/transform/{run_id}/]

Stdout: JSON {"cluster_keywords": [...], "meta": {...}}.

Refs: schemas/master-excel.schema.json#cluster_keywords (11 required_columns
+ intent enum), schemas/cross-sheet-invariants.json#D-02
(cluster ⊆ data/cluster defs HIGH), schemas/events.schema.json
(target_excel_sheet=cluster_keywords + source.kind=dataforseo_mcp /
gsc_mcp), spec §11.6 (DFS keyword discovery), §16.5 (raw JSON inbox +
transform stage), §16.8 (budget pre-flight). Pattern reference:
scripts/discovery/content_gaps_transform.py (paid-MCP DFS heavy +
budget pre-flight subprocess wrapper) +
scripts/discovery/cannibalization_transform.py (Excel-write target
shape).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

# scripts/budget + scripts/ingestion are namespace packages; ensure repo
# root on sys.path so absolute imports resolve when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (NOT copy): _normalize_dfs_response is owned by
# scripts.ingestion.dfs_pull. We REUSE it so any shape evolution is
# inherited automatically — Phase 6 D-003 lesson, Phase 7 W-B1 paterni.
from scripts.ingestion.dfs_pull import (   # noqa: E402  (sys.path mutation above)
    _normalize_dfs_response,
)


# ---------------------------------------------------------------------------
# Constants — schema-aligned column tuple (master-excel.schema.json
# #cluster_keywords required_columns, exact order, 11 cols)
# ---------------------------------------------------------------------------

CLUSTER_KEYWORDS_COLUMNS: tuple[str, ...] = (
    "cluster",
    "keyword",
    "monthly_volume",
    "data_source",
    "assigned_url",
    "gsc_clicks",
    "gsc_impressions",
    "gsc_position",
    "intent",
    "forbidden_kw",
    "forbidden_reason",
)

#: intent enum (master-excel.schema.json#cluster_keywords col I).
_INTENT_ENUM: frozenset[str] = frozenset({
    "Informational", "Commercial", "Transactional", "Navigational",
})

#: statusEnum allowed values (kept here for future status-driven projection;
#: the cluster_keywords sheet itself does NOT carry a status column, but
#: callers may pass default_status into project.config-driven blocklist
#: enforcement downstream).
_STATUS_ENUM: frozenset[str] = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

#: DoS guard — refuse to project more than this many candidates per MCP
#: tool even when the API returns a giant page. Configurable via
#: --keyword-cap.
DEFAULT_KEYWORD_CAP: int = 5000

#: Path to the canonical budget pre-flight script (subprocess wrapper
#: paterni from W-A3/W-A4 + Phase 7 W-B1).
BUDGET_CHECK_SCRIPT: Path = _REPO_ROOT / "scripts" / "budget" / "check_budget.py"

#: Source labels in the data_source column.
SOURCE_KEYWORD_SUGGESTIONS: str = "keyword_suggestions"
SOURCE_RELATED_KEYWORDS: str = "related_keywords"

#: data_source column strings (combinations).
DS_DFS_ONLY: str = "dataforseo"
DS_DFS_PLUS_GSC: str = "dataforseo+gsc"

#: Token splitter for cluster Jaccard scoring.
_TOKEN_SPLIT = re.compile(r"[\s\-_/.,;:!?()\[\]{}]+")


# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class ClusterMapError(Exception):
    """Base class for cluster_map_transform errors."""


class BudgetExceededError(ClusterMapError):
    """Budget pre-flight DURUR — projected DFS spend exceeds the daily cap."""


class KeywordCapExceededError(ClusterMapError):
    """DoS guard DURUR — MCP returned more candidates than the cap allows."""


class ClusterDefError(ClusterMapError):
    """D-02 invariant DURUR — emitted cluster falls outside cluster_defs
    (i.e. data/cluster defs sourced from master.xlsx#topical_map)."""


class RowSchemaError(ClusterMapError):
    """A produced row drifts from the master-excel cluster_keywords schema."""


class GscPayloadError(ClusterMapError):
    """GSC payload is missing / wrong type / not parseable."""


# ---------------------------------------------------------------------------
# Helpers — type coercion (mirrors dfs_pull / content_gaps patterns)
# ---------------------------------------------------------------------------

def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _utc_iso_microseconds() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _tokenize(s: str) -> set[str]:
    """Split a string into a lowercase token set (order-insensitive).

    Used by the cluster-assignment Jaccard scorer. Empty / whitespace-only
    inputs return an empty set (no signal — caller falls through).
    """
    if not s:
        return set()
    parts = _TOKEN_SPLIT.split(s.lower().strip())
    return {p for p in parts if p}


# ---------------------------------------------------------------------------
# Budget pre-flight (subprocess wrapper paterni — Phase 7 W-B1)
# ---------------------------------------------------------------------------

def preflight_budget(
    *,
    project_config_path: str | os.PathLike[str],
    events_path: str | os.PathLike[str],
    script_path: str | os.PathLike[str] = BUDGET_CHECK_SCRIPT,
) -> dict:
    """Run scripts/budget/check_budget.py as a subprocess and DURUR if exit 1.

    Returns the parsed envelope on PASS:
        {"budget_per_day": int, "used_24h": ..., "remaining": ..., "exceeded": bool}

    Raises BudgetExceededError when the subprocess exits non-zero — that
    is the canonical "budget would be exceeded by this run" signal per
    §16.8 + W-A3/W-A4 + Phase 7 W-B1. Stderr is preserved on the
    exception for manager diagnostics.
    """
    cmd = [
        sys.executable,
        str(script_path),
        "--project-config", str(project_config_path),
        "--events", str(events_path),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise BudgetExceededError(
            "budget pre-flight FAIL "
            f"(exit={proc.returncode}): stdout={proc.stdout.strip()!r} "
            f"stderr={proc.stderr.strip()!r}"
        )
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        raise BudgetExceededError(
            f"budget pre-flight stdout was not JSON: {proc.stdout!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Cluster assignment heuristic (D-02 source-of-truth)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ClusterDef:
    """Original-case cluster string + cached lowercase token set."""
    name: str
    name_lower: str
    tokens: frozenset[str]


def _build_cluster_defs(raw_defs: Sequence[str]) -> list[_ClusterDef]:
    """Deduplicate (case-insensitive) + project to _ClusterDef list.

    Raises ClusterDefError when the input is empty / non-string-bearing —
    D-02 invariant requires at least one cluster definition to exist
    before keyword projection can proceed.
    """
    if not isinstance(raw_defs, (list, tuple)):
        raise ClusterDefError(
            f"cluster_defs must be a list, got {type(raw_defs).__name__}"
        )
    seen: dict[str, _ClusterDef] = {}
    for raw in raw_defs:
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen[key] = _ClusterDef(
            name=s, name_lower=key, tokens=frozenset(_tokenize(s)),
        )
    out = list(seen.values())
    if not out:
        raise ClusterDefError(
            "cluster_defs is empty — D-02 cannot be satisfied without at "
            "least one cluster definition (sourced from "
            "master.xlsx#topical_map column B)"
        )
    return out


def _assign_cluster(
    keyword: str,
    defs: Sequence[_ClusterDef],
) -> _ClusterDef | None:
    """
    Pick the best cluster for ``keyword`` from ``defs``.

    Algorithm:
      1. Token Jaccard similarity between keyword tokens and each cluster
         def tokens. Highest wins.
      2. Tie-break: cluster.name_lower as substring of keyword.lower()
         (specificity bonus).
      3. Final tie-break: alphabetical on name_lower (deterministic).
      4. If best Jaccard == 0 AND no substring match → return None
         (caller skips the keyword to avoid D-02 violation).
    """
    if not keyword or not defs:
        return None
    kw_tokens = _tokenize(keyword)
    kw_lower = keyword.lower()
    if not kw_tokens:
        return None

    best: tuple[float, int, str, _ClusterDef] | None = None
    for d in defs:
        if not d.tokens:
            continue
        inter = len(kw_tokens & d.tokens)
        union = len(kw_tokens | d.tokens)
        jaccard = (inter / union) if union else 0.0
        substring_bonus = 1 if d.name_lower and d.name_lower in kw_lower else 0
        # Sort by (jaccard desc, substring desc, name_lower asc).
        key = (-jaccard, -substring_bonus, d.name_lower, d)
        if best is None or key < best:
            best = key  # type: ignore[assignment]

    if best is None:
        return None
    neg_j, neg_sub, _, chosen = best
    if (-neg_j) <= 0.0 and (-neg_sub) <= 0:
        # Zero-signal match: refuse to assign rather than fabricate a cluster.
        return None
    return chosen


# ---------------------------------------------------------------------------
# Intent extractor
# ---------------------------------------------------------------------------

def _intent_label(item: Mapping[str, Any]) -> str:
    """Map DFS search_intent_info / search_intent / item.intent_info to
    the master-excel intent enum {Informational, Commercial,
    Transactional, Navigational}. Default 'Informational'.
    """
    raw = (
        item.get("search_intent_info")
        or item.get("search_intent")
        or item.get("intent_info")
        or item.get("intent")
    )
    if not raw:
        return "Informational"
    if isinstance(raw, dict):
        main = (
            raw.get("main_intent")
            or raw.get("primary_intent")
            or raw.get("intent")
            or ""
        )
    else:
        main = str(raw)
    norm = str(main).strip().lower()
    return {
        "informational": "Informational",
        "commercial": "Commercial",
        "transactional": "Transactional",
        "navigational": "Navigational",
    }.get(norm, "Informational")


# ---------------------------------------------------------------------------
# Candidate extractor — DFS keyword_suggestions / related_keywords
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Candidate:
    """Internal candidate before cluster_keywords projection."""
    keyword: str
    monthly_volume: int
    intent: str
    source: str


def _extract_candidate(
    item: Mapping[str, Any],
    *,
    source: str,
) -> _Candidate | None:
    """Pull a candidate keyword + volume + intent out of one DFS item.

    DFS shapes accommodated:
      - keyword_suggestions: keyword on top, keyword_info.search_volume.
      - related_keywords: nested under keyword_data.{keyword,
        keyword_info,...} OR flat (when wrapper has already flattened).
    """
    if not isinstance(item, dict):
        return None

    payload = item.get("keyword_data") if isinstance(item.get("keyword_data"), dict) else item

    keyword = payload.get("keyword") or item.get("keyword")
    if not keyword or not isinstance(keyword, str) or not keyword.strip():
        return None

    ki = payload.get("keyword_info") or {}
    if not isinstance(ki, dict):
        ki = {}

    volume = _safe_int(ki.get("search_volume"))
    if volume is None:
        volume = _safe_int(payload.get("search_volume"))
    if volume is None:
        volume = _safe_int(item.get("search_volume"))
    if volume is None:
        volume = 0

    intent = _intent_label(payload) or _intent_label(item)
    if intent not in _INTENT_ENUM:
        intent = "Informational"

    return _Candidate(
        keyword=keyword.strip(),
        monthly_volume=int(volume),
        intent=intent,
        source=source,
    )


# ---------------------------------------------------------------------------
# GSC enrichment
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _GscRow:
    """A single (query, page) GSC enhanced_search_analytics row."""
    query: str
    url: str
    clicks: int
    impressions: int
    position: float


def _extract_gsc_query_and_page(keys: list) -> tuple[str | None, str | None]:
    """Find the query and page within a GSC row's `keys` array.

    Mirrors cannibalization_transform._extract_query_and_page: the page
    is the first http(s)://... entry, the query is the first remaining
    string entry. Defensive against caller-controlled `dimensions` order.
    """
    if not isinstance(keys, list):
        return None, None
    page: str | None = None
    query: str | None = None
    for k in keys:
        if not isinstance(k, str):
            continue
        ks = k.strip()
        if not ks:
            continue
        if (ks[:7].lower() == "http://" or ks[:8].lower() == "https://") and page is None:
            page = ks
        elif query is None and not (ks[:7].lower() == "http://" or ks[:8].lower() == "https://"):
            query = ks
    return query, page


def _parse_gsc_rows(payload: dict | None) -> list[_GscRow]:
    """Parse a GSC enhanced_search_analytics payload into _GscRow list.

    Tolerates ``rows`` OR ``data`` envelope. Skips entries missing query
    or page. Returns [] for None input (the skill layer decides whether
    that is a DURUR — see GscPayloadError below).
    """
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise GscPayloadError(
            f"GSC payload must be a dict, got {type(payload).__name__}"
        )
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        raise GscPayloadError(
            f"GSC payload 'rows' must be a list, got {type(rows).__name__}"
        )

    out: list[_GscRow] = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys") or []
        query, page = _extract_gsc_query_and_page(keys)
        if not query or not page:
            continue
        clicks = _safe_int(entry.get("clicks")) or 0
        impressions = _safe_int(entry.get("impressions")) or 0
        position = _safe_float(entry.get("position")) or 0.0
        out.append(_GscRow(
            query=query.strip().lower(),
            url=page.strip(),
            clicks=int(clicks),
            impressions=int(impressions),
            position=float(position),
        ))
    return out


def _index_gsc(gsc_rows: Sequence[_GscRow]) -> dict[str, dict[str, Any]]:
    """Build a per-query aggregate from GSC rows.

    Returns {query_lower: {"clicks": int, "impressions": int,
                            "position": float, "top_url": str}}.
    Position is impression-weighted; top_url is the URL with the most
    clicks (ties broken by lower position then alpha).
    """
    grouped: dict[str, dict[str, Any]] = {}
    for r in gsc_rows:
        bucket = grouped.setdefault(r.query, {
            "clicks": 0,
            "impressions": 0,
            "pos_w_sum": 0.0,
            "per_url": {},  # url → (clicks, position)
        })
        bucket["clicks"] += r.clicks
        bucket["impressions"] += r.impressions
        bucket["pos_w_sum"] += r.position * max(r.impressions, 1)
        per_url: dict[str, tuple[int, float]] = bucket["per_url"]
        prev = per_url.get(r.url)
        if prev is None:
            per_url[r.url] = (r.clicks, r.position)
        else:
            per_url[r.url] = (prev[0] + r.clicks, prev[1])

    out: dict[str, dict[str, Any]] = {}
    for q, b in grouped.items():
        impressions = int(b["impressions"])
        position = round(b["pos_w_sum"] / max(impressions, 1), 2) if impressions else 0.0
        per_url: dict[str, tuple[int, float]] = b["per_url"]
        if per_url:
            top_url = sorted(
                per_url.items(),
                key=lambda kv: (-kv[1][0], kv[1][1], kv[0]),
            )[0][0]
        else:
            top_url = ""
        out[q] = {
            "clicks": int(b["clicks"]),
            "impressions": impressions,
            "position": float(position),
            "top_url": top_url,
        }
    return out


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    *,
    raw_keyword_suggestions: dict | None,
    raw_related_keywords: dict | None,
    raw_gsc: dict | None,
    cluster_defs: Sequence[str],
    project_slug: str,
    seed_keyword: str,
    keyword_cap: int = DEFAULT_KEYWORD_CAP,
    default_status: str = "TODO",
) -> dict:
    """Transform DFS keyword_suggestions + related_keywords (+ GSC enrichment)
    into schema-shaped cluster_keywords rows.

    Args:
        raw_keyword_suggestions: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_keyword_suggestions
            (REQUIRED at the skill level; pass None to indicate empty
            fetch). Tolerates REST envelope OR flat wrapper.
        raw_related_keywords: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_related_keywords
            (REQUIRED at the skill level).
        raw_gsc: parsed JSON from mcp__gsc__enhanced_search_analytics
            (REQUIRED for enrichment columns; pass None to skip
            enrichment — callers that DURUR on GSC failure should NOT
            pass None here).
        cluster_defs: list of cluster names (D-02 source of truth, from
            master.xlsx#topical_map column B). Must be non-empty.
        project_slug: project slug (carried in meta only — transform is
            data-driven, no slug branching).
        seed_keyword: seed keyword that drove the fetches (carried in
            meta for traceability).
        keyword_cap: DoS guard; if any tool's normalized item list
            exceeds this count → KeywordCapExceededError.
        default_status: statusEnum for downstream blocklist enforcement
            (current sheet has no status column; reserved).

    Returns:
        {"cluster_keywords": [<row>, ...], "meta": {...}}.

    Raises:
        ValueError:               project_slug/seed_keyword empty;
                                  shape unparseable (propagates from
                                  _normalize_dfs_response).
        KeywordCapExceededError:  raw items list exceeds keyword_cap.
        ClusterDefError:          cluster_defs empty / drift.
        RowSchemaError:           emitted row column drift (defensive).
        GscPayloadError:          raw_gsc shape wrong (when not None).
    """
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise ValueError("project_slug must be a non-empty string")
    if not isinstance(seed_keyword, str) or not seed_keyword.strip():
        raise ValueError("seed_keyword must be a non-empty string")
    if not isinstance(keyword_cap, int) or keyword_cap <= 0:
        raise ValueError(f"keyword_cap must be a positive int, got {keyword_cap!r}")
    if default_status not in _STATUS_ENUM:
        raise ValueError(
            f"default_status must be in {sorted(_STATUS_ENUM)}, "
            f"got {default_status!r}"
        )

    # D-02 source-of-truth gate — reject non-list/tuple inputs BEFORE
    # any list() coercion (a bare string is iterable but is not a defs
    # list; converting it would split into chars and silently corrupt).
    if not isinstance(cluster_defs, (list, tuple)):
        raise ClusterDefError(
            f"cluster_defs must be a list or tuple, "
            f"got {type(cluster_defs).__name__}"
        )
    defs = _build_cluster_defs(list(cluster_defs))
    defs_name_set = {d.name for d in defs}

    # 1. Normalize DFS payloads via imported helper (D-003 root-cause fix).
    sugg_items: list[dict] = []
    if raw_keyword_suggestions is not None:
        sugg_items = _normalize_dfs_response(
            raw_keyword_suggestions,
            expected_endpoint="dataforseo_labs_google_keyword_suggestions",
        )
        if len(sugg_items) > keyword_cap:
            raise KeywordCapExceededError(
                f"keyword_suggestions: MCP returned {len(sugg_items)} > "
                f"keyword_cap={keyword_cap}; refusing to project (DoS guard)"
            )

    related_items: list[dict] = []
    if raw_related_keywords is not None:
        related_items = _normalize_dfs_response(
            raw_related_keywords,
            expected_endpoint="dataforseo_labs_google_related_keywords",
        )
        if len(related_items) > keyword_cap:
            raise KeywordCapExceededError(
                f"related_keywords: MCP returned {len(related_items)} > "
                f"keyword_cap={keyword_cap}; refusing to project (DoS guard)"
            )

    # 2. Project to candidates (one per DFS item).
    candidates: list[_Candidate] = []
    for it in sugg_items:
        c = _extract_candidate(it, source=SOURCE_KEYWORD_SUGGESTIONS)
        if c is not None:
            candidates.append(c)
    for it in related_items:
        c = _extract_candidate(it, source=SOURCE_RELATED_KEYWORDS)
        if c is not None:
            candidates.append(c)

    # 3. Deduplicate by lowercase keyword (keep highest volume; prefer
    #    keyword_suggestions source on volume tie).
    by_kw: dict[str, _Candidate] = {}
    source_priority = {
        SOURCE_KEYWORD_SUGGESTIONS: 0,
        SOURCE_RELATED_KEYWORDS: 1,
    }
    for c in candidates:
        key = c.keyword.lower()
        prev = by_kw.get(key)
        if prev is None:
            by_kw[key] = c
            continue
        # Higher volume wins; on tie, prefer suggestions.
        if c.monthly_volume > prev.monthly_volume:
            by_kw[key] = c
        elif (
            c.monthly_volume == prev.monthly_volume
            and source_priority[c.source] < source_priority[prev.source]
        ):
            by_kw[key] = c

    # 4. Index GSC enrichment.
    gsc_rows = _parse_gsc_rows(raw_gsc) if raw_gsc is not None else []
    gsc_index = _index_gsc(gsc_rows)

    # 5. Assign cluster + project to schema-locked row tuple.
    rows: list[dict] = []
    skipped_no_cluster: int = 0
    gsc_hits: int = 0
    for kw_lower, c in by_kw.items():
        chosen = _assign_cluster(c.keyword, defs)
        if chosen is None:
            skipped_no_cluster += 1
            continue
        if chosen.name not in defs_name_set:
            # Defensive — should be impossible, but D-02 demands a
            # hard floor before any row escapes.
            raise ClusterDefError(
                f"cluster {chosen.name!r} for keyword {c.keyword!r} is not "
                f"a member of cluster_defs (D-02 violation)"
            )

        gsc_hit = gsc_index.get(kw_lower)
        if gsc_hit:
            gsc_clicks = int(gsc_hit["clicks"])
            gsc_impressions = int(gsc_hit["impressions"])
            gsc_position = float(gsc_hit["position"])
            assigned_url = str(gsc_hit["top_url"]) or ""
            data_source = DS_DFS_PLUS_GSC
            gsc_hits += 1
        else:
            gsc_clicks = 0
            gsc_impressions = 0
            gsc_position = 0.0
            assigned_url = ""
            data_source = DS_DFS_ONLY

        row = {
            "cluster":          chosen.name,
            "keyword":          c.keyword,
            "monthly_volume":   int(c.monthly_volume),
            "data_source":      data_source,
            "assigned_url":     assigned_url,
            "gsc_clicks":       int(gsc_clicks),
            "gsc_impressions":  int(gsc_impressions),
            "gsc_position":     float(round(gsc_position, 2)),
            "intent":           c.intent,
            "forbidden_kw":     "",
            "forbidden_reason": "",
        }

        # Defensive schema-shape self-checks.
        if tuple(row.keys()) != CLUSTER_KEYWORDS_COLUMNS:
            raise RowSchemaError(
                f"row column drift: got {tuple(row.keys())}, "
                f"expected {CLUSTER_KEYWORDS_COLUMNS}"
            )
        if not isinstance(row["monthly_volume"], int):
            raise RowSchemaError(
                f"monthly_volume must be int, "
                f"got {type(row['monthly_volume']).__name__}"
            )
        if not isinstance(row["gsc_clicks"], int) or not isinstance(
            row["gsc_impressions"], int
        ):
            raise RowSchemaError("gsc_clicks/impressions must be int")
        if not isinstance(row["gsc_position"], (int, float)):
            raise RowSchemaError("gsc_position must be number")
        if row["intent"] not in _INTENT_ENUM:
            raise RowSchemaError(
                f"intent must be in {sorted(_INTENT_ENUM)}, "
                f"got {row['intent']!r}"
            )

        rows.append(row)

    # 6. Sort: cluster asc → monthly_volume desc → keyword asc (deterministic).
    rows.sort(
        key=lambda r: (r["cluster"].lower(), -int(r["monthly_volume"]), r["keyword"].lower())
    )

    return {
        "cluster_keywords": rows,
        "meta": {
            "project_slug":         project_slug.strip(),
            "seed_keyword":         seed_keyword.strip(),
            "fetched_at":           _utc_iso_microseconds(),
            "keyword_cap":          int(keyword_cap),
            "default_status":       default_status,
            "cluster_count":        len({r["cluster"] for r in rows}),
            "row_count":            len(rows),
            "candidate_count":      len(by_kw),
            "skipped_no_cluster":   skipped_no_cluster,
            "gsc_match_count":      gsc_hits,
            "gsc_match_pct":        round(
                (gsc_hits / len(rows)) if rows else 0.0, 4,
            ),
            "sugg_item_count":      len(sugg_items),
            "related_item_count":   len(related_items),
            "gsc_row_count":        len(gsc_rows),
        },
    }


# ---------------------------------------------------------------------------
# Phase 7 staging consume helper
# ---------------------------------------------------------------------------

def consume_content_gaps_staging(
    staging_path: str | os.PathLike[str],
) -> list[dict]:
    """Read a Phase 7 content_gaps_keyword_ideas staging JSON and return
    rows as DFS-shaped items (so downstream cluster assignment treats
    them identically to live keyword_suggestions output).

    The staging schema (content_gaps_transform.CONTENT_GAPS_COLUMNS):
        id, keyword, search_volume, keyword_difficulty, competition,
        cpc, gap_score, source, seed_keyword, content_hash, fetched_at

    We project each row into a minimal DFS-item shape:
        {"keyword": <kw>, "keyword_info": {"search_volume": <vol>}}

    Raises:
        FileNotFoundError on missing path.
        ValueError on shape drift (rows missing keys).
    """
    p = Path(staging_path)
    if not p.exists():
        raise FileNotFoundError(f"staging path not found: {p}")
    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(
            f"staging payload must be a dict, got {type(payload).__name__}"
        )
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError(
            f"staging 'rows' must be a list, got {type(rows).__name__}"
        )
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        kw = r.get("keyword")
        if not kw:
            continue
        out.append({
            "keyword": str(kw).strip(),
            "keyword_info": {
                "search_volume": _safe_int(r.get("search_volume")) or 0,
            },
        })
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cluster_map_transform.py",
        description=(
            "Transform DataForSEO keyword_suggestions / related_keywords "
            "+ GSC enhanced_search_analytics JSON → cluster_keywords rows "
            "(11 cols, master.xlsx#cluster_keywords schema). D-02 invariant "
            "enforced via cluster_defs (sourced from "
            "master.xlsx#topical_map by the skill layer)."
        ),
    )
    p.add_argument("--raw-keyword-suggestions", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_keyword_suggestions JSON.")
    p.add_argument("--raw-related-keywords", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_related_keywords JSON.")
    p.add_argument("--raw-gsc", required=True,
                   help="Path to raw mcp__gsc__enhanced_search_analytics JSON (query+page dims).")
    p.add_argument("--cluster-defs-json", required=True,
                   help="Path to a JSON list of cluster names (D-02 source-of-truth, "
                        "sourced by the skill from master.xlsx#topical_map column B).")
    p.add_argument("--seed-keyword", required=True,
                   help="The seed keyword that drove the fetches.")
    p.add_argument("--keyword-cap", type=int, default=DEFAULT_KEYWORD_CAP,
                   help=f"DoS guard (default: {DEFAULT_KEYWORD_CAP}).")
    p.add_argument("--default-status", default="TODO",
                   help="statusEnum default (default: TODO).")
    p.add_argument("--project-slug", default="run",
                   help="Project slug embedded in meta (default: 'run').")
    p.add_argument("--output-dir", default=None,
                   help="If set, write cluster_keywords.json into this directory.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    sugg_path = Path(args.raw_keyword_suggestions)
    if not sugg_path.exists():
        print(f"raw keyword_suggestions JSON not found: {sugg_path}", file=sys.stderr)
        return 2
    raw_sugg = _read_json(sugg_path)

    related_path = Path(args.raw_related_keywords)
    if not related_path.exists():
        print(f"raw related_keywords JSON not found: {related_path}", file=sys.stderr)
        return 2
    raw_related = _read_json(related_path)

    gsc_path = Path(args.raw_gsc)
    if not gsc_path.exists():
        print(f"raw GSC JSON not found: {gsc_path}", file=sys.stderr)
        return 2
    raw_gsc = _read_json(gsc_path)

    defs_path = Path(args.cluster_defs_json)
    if not defs_path.exists():
        print(f"cluster_defs JSON not found: {defs_path}", file=sys.stderr)
        return 2
    cluster_defs = _read_json(defs_path)
    if not isinstance(cluster_defs, list):
        print(
            f"cluster_defs JSON must be a list, got {type(cluster_defs).__name__}",
            file=sys.stderr,
        )
        return 2

    try:
        result = transform(
            raw_keyword_suggestions=raw_sugg,
            raw_related_keywords=raw_related,
            raw_gsc=raw_gsc,
            cluster_defs=cluster_defs,
            project_slug=args.project_slug,
            seed_keyword=args.seed_keyword,
            keyword_cap=args.keyword_cap,
            default_status=args.default_status,
        )
    except (
        ValueError,
        ClusterMapError,
    ) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "cluster_keywords.json"
        out_path.write_text(
            json.dumps(result["cluster_keywords"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "cluster_keywords_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CLUSTER_KEYWORDS_COLUMNS",
    "DEFAULT_KEYWORD_CAP",
    "BUDGET_CHECK_SCRIPT",
    "SOURCE_KEYWORD_SUGGESTIONS",
    "SOURCE_RELATED_KEYWORDS",
    "DS_DFS_ONLY",
    "DS_DFS_PLUS_GSC",
    "ClusterMapError",
    "BudgetExceededError",
    "KeywordCapExceededError",
    "ClusterDefError",
    "RowSchemaError",
    "GscPayloadError",
    "_normalize_dfs_response",   # re-exported (IDENTITY preserved)
    "preflight_budget",
    "consume_content_gaps_staging",
    "transform",
    "main",
)
