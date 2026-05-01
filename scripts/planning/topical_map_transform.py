#!/usr/bin/env python3
"""
topical_map_transform.py — pure transform: DataForSEO keyword_ideas +
related_keywords (+ optional Phase 7 geo_analysis staging) raw JSON →
schema-shaped rows for master.xlsx#topical_map.

Reads the raw responses of:
  - mcp__dataforseo__dataforseo_labs_google_keyword_ideas    (REQUIRED)
  - mcp__dataforseo__dataforseo_labs_google_related_keywords (REQUIRED)

Optionally cross-references Phase 7 staging signals when available:
  - _state/staging/geo_analysis_*.json   (LLM mention topical signal)
  - _state/staging/content_gaps_*.json   (broad keyword inventory cross-ref)

Builds a two-level pillar / cluster taxonomy:
  - PILLAR  : the seed concept itself + the highest-volume keyword_ideas
              candidates that share the seed's topical core (page_type=pillar).
  - CLUSTER : related_keywords subtopics distributed under the dominant
              pillar by lexical overlap (page_type=cluster).
  - SUPPORTING: long-tail volume rows that don't elevate to cluster status
              (page_type=supporting). Fed downstream into cluster_keywords
              by the Phase 8 W-C1 cluster-map sibling.

Output rows shaped per master-excel.schema.json#topical_map (10 columns):
    pillar, cluster, primary_keyword, monthly_volume, data_source,
    assigned_url, page_type, status, priority, note

D-003 helper IMPORT (mandatory, no copy):
    from scripts.ingestion.dfs_pull import _normalize_dfs_response

Re-using the upstream helper keeps DFS REST envelope vs flat wrapper
tolerance in ONE place — copying would silently fork the contract. The
identity is locked by `tests/skills/test_topical_map.py
::test_topical_map_dfs_normalize_helper_imported`.

F-09 contract (cross-sheet invariant):
    cluster_keywords.assigned_url ⊆ topical_map.assigned_url
This module emits topical_map rows with `assigned_url=""` by default
(unassigned). The Phase 8 W-C1 cluster-map sibling reads the resulting
topical_map.assigned_url superset before deciding any cluster_keywords
row. The cross-sheet check itself is run by the drift-check skill, not
here — this module only validates its OWN row writes are F-09-compatible
(superset side).

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports.
    The skill orchestrator (skills/planning/topical-map/SKILL.md) owns
    the `transaction.append` write through the workflow_runner approve
    gate — see ADR-019 (single approved write path) + ADR-021.
  - Idempotent: same input → byte-identical output.

CLI:
  python3 scripts/planning/topical_map_transform.py \\
      --raw-keyword-ideas    inbox/dfs/{date}-keyword_ideas-topical-{slug}.json \\
      --raw-related-keywords inbox/dfs/{date}-related_keywords-topical-{slug}.json \\
      --seed-keyword         "<seed>" \\
      [--geo-staging         _state/staging/geo_analysis_geo_signals_{date}_{slug}.json] \\
      [--max-pillars         5] \\
      [--max-clusters-per-pillar 6] \\
      [--default-status      TODO] \\
      [--output-dir          _state/transform/{run_id}/]

Stdout: JSON {"topical_map": [...rows...], "meta": {...}}.

Refs:
  - schemas/master-excel.schema.json#topical_map     (10 required columns)
  - schemas/master-excel.schema.json#/definitions/statusEnum
  - schemas/skill-frontmatter.schema.json            (frontmatter contract)
  - schemas/events.schema.json                       (source.kind=dataforseo_mcp,
                                                       target_excel_sheet=topical_map)
  - schemas/cross-sheet-invariants.json              (F-09 superset contract,
                                                       D-01 pillar key contract)
  - spec §11.6 (DFS keyword discovery), §16.5 (raw inbox + transform stage),
    §16.8 (budget pre-flight).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# scripts/* is a namespace package; ensure repo root on sys.path so
# `from scripts.ingestion.dfs_pull import _normalize_dfs_response` works
# both as a module import and from the CLI entry-point.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover — import-time wiring
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (W-C2 brief): re-use the upstream helper rather than
# copying it — keeps DFS REST envelope vs flat wrapper tolerance in ONE
# place. The identity is locked by an import-discipline test.
from scripts.ingestion.dfs_pull import _normalize_dfs_response  # noqa: E402


# ---------------------------------------------------------------------------
# Constants — schema-aligned column tuple
# (master-excel.schema.json#topical_map required_columns, exactly 10 cols)
# ---------------------------------------------------------------------------

TOPICAL_MAP_COLUMNS: tuple[str, ...] = (
    "pillar",
    "cluster",
    "primary_keyword",
    "monthly_volume",
    "data_source",
    "assigned_url",
    "page_type",
    "status",
    "priority",
    "note",
)

# statusEnum — master-excel.schema.json#/definitions/statusEnum.
_STATUS_ENUM = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

# page_type convention values. The schema does NOT define an enum for
# page_type (free string column), but the topical-map skill commits to
# this small vocabulary so downstream consumers (cluster-map, monthly-
# report) can branch on it. New values require an ADR (Open Question
# Q-W-C2-01 documents the lack of a formal enum).
PAGE_TYPE_PILLAR: str = "pillar"
PAGE_TYPE_CLUSTER: str = "cluster"
PAGE_TYPE_SUPPORTING: str = "supporting"

_PAGE_TYPE_VALUES = frozenset({
    PAGE_TYPE_PILLAR,
    PAGE_TYPE_CLUSTER,
    PAGE_TYPE_SUPPORTING,
})

# data_source label written into every row for provenance.
DATA_SOURCE_LABEL: str = "dataforseo_mcp"

# Default planning knobs.
DEFAULT_MAX_PILLARS: int = 5
DEFAULT_MAX_CLUSTERS_PER_PILLAR: int = 6
DEFAULT_MAX_SUPPORTING_PER_CLUSTER: int = 0          # 0 = no supporting rows
DEFAULT_MIN_PILLAR_VOLUME: int = 100                  # below this, demoted to supporting
DEFAULT_MIN_CLUSTER_VOLUME: int = 30                  # below this, dropped or supporting

# DoS guard — refuse to project more than this many candidates per MCP tool
# even when the API returns a giant page. Mirrors content_gaps DoS guard.
DEFAULT_KEYWORD_CAP: int = 5000

# Path to the canonical budget pre-flight script (subprocess wrapper paterni
# from W-A3/W-A4). Skill orchestrator invokes this before any paid call.
BUDGET_CHECK_SCRIPT: Path = _REPO_ROOT / "scripts" / "budget" / "check_budget.py"

# DFS credit estimates (paid).
#   keyword_ideas:    ~1 credit per request (covers up to `limit` keywords).
#   related_keywords: ~1 credit per request (covers depth-bounded fanout).
# Conservative: 1 run hits BOTH endpoints once → ~2 credits.
CREDITS_PER_KEYWORD_IDEAS_CALL: float = 1.0
CREDITS_PER_RELATED_KEYWORDS_CALL: float = 1.0


# ---------------------------------------------------------------------------
# Errors (DURUR-style explicit)
# ---------------------------------------------------------------------------

class TopicalMapError(Exception):
    """Base class for topical_map_transform errors (DURUR)."""


class RowSchemaError(TopicalMapError):
    """A produced row drifts from the master-excel topical_map schema."""


class BudgetExceededError(TopicalMapError):
    """Budget pre-flight DURUR — projected DFS spend exceeds the daily cap."""


class KeywordCapExceededError(TopicalMapError):
    """DoS guard DURUR — MCP returned more candidates than the cap allows."""


class GeoStagingMissingError(TopicalMapError):
    """Phase 7 geo-analysis staging file expected but cannot be read.

    Raised only when the caller explicitly passed a geo_staging path AND
    `--require-geo-staging` was set. Default behaviour is GRACEFUL skip:
    callers without geo signal still get a valid topical_map (Phase 8 ramp).
    """


class PageTypeError(TopicalMapError):
    """A produced row's page_type drifts from the documented vocabulary."""


# ---------------------------------------------------------------------------
# Helpers — primitive coercion (mirrors content_gaps + dfs_pull patterns)
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
    """UTC ISO 8601 with microsecond precision and explicit '+00:00' offset."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ---------------------------------------------------------------------------
# Lexical helpers — pillar bucket assignment
# ---------------------------------------------------------------------------

# Drop tiny words when computing topical overlap (Turkish + English stop
# words). Kept short on purpose: the overlap score is coarse and
# deterministic; full NLP belongs in a separate skill.
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "for", "in", "on", "to", "at",
    "is", "are", "was", "were", "be", "been", "with", "by", "as", "from",
    "ve", "ile", "icin", "için", "bu", "şu", "ne", "ya", "da", "de",
    "ki", "mi", "mu", "mü", "mı", "ben", "biz", "siz", "onlar",
    "ama", "fakat", "veya", "yada",
})


def _tokenize(text: str) -> set[str]:
    """Lower-case word tokens, drop stop words and tokens shorter than 3 chars.

    Deterministic and idempotent — identical input → identical output. The
    set return type is intentional: order does not matter for overlap
    scoring and it kills duplicate tokens in one step.
    """
    if not isinstance(text, str):
        return set()
    lowered = text.lower()
    # Split on non-alphanumeric (Unicode-aware) so Turkish chars survive.
    tokens = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
    return {t for t in tokens if len(t) >= 3 and t not in _STOP_WORDS}


def _topical_overlap(a_tokens: set[str], b_tokens: set[str]) -> float:
    """Jaccard overlap (|A∩B| / |A∪B|) ∈ [0, 1].

    Returns 0.0 when either side is empty. Deterministic.
    """
    if not a_tokens or not b_tokens:
        return 0.0
    inter = a_tokens & b_tokens
    union = a_tokens | b_tokens
    if not union:
        return 0.0
    return len(inter) / len(union)


# ---------------------------------------------------------------------------
# Candidate extraction (DFS keyword_ideas / related_keywords)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Candidate:
    """Internal candidate from a single DFS item, before pillar/cluster
    assignment."""
    keyword: str
    volume: int
    source: str          # "keyword_ideas" | "related_keywords"
    tokens: frozenset[str]


def _extract_candidate(
    item: Mapping[str, Any],
    *,
    source: str,
) -> _Candidate | None:
    """Pull a candidate keyword + volume out of a single normalized DFS item.

    Tolerates both `keyword_ideas` (top-level keyword + keyword_info.search_volume)
    and `related_keywords` (nested under keyword_data.* OR flattened upstream).
    """
    if not isinstance(item, dict):
        return None

    # related_keywords nests the candidate under 'keyword_data'; unwrap once.
    payload = item.get("keyword_data") if isinstance(item.get("keyword_data"), dict) else item

    keyword_raw = payload.get("keyword") or item.get("keyword")
    if not keyword_raw or not isinstance(keyword_raw, str) or not keyword_raw.strip():
        return None
    keyword = keyword_raw.strip()

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
    if volume < 0:
        volume = 0

    return _Candidate(
        keyword=keyword,
        volume=int(volume),
        source=source,
        tokens=frozenset(_tokenize(keyword)),
    )


def _gather_candidates(
    raw_keyword_ideas: dict | None,
    raw_related_keywords: dict | None,
    *,
    keyword_cap: int,
) -> list[_Candidate]:
    """Pull candidates from both DFS payloads, dedupe by lower-case keyword.

    Higher-volume entries win on duplicates. Source provenance is the
    first-seen source per keyword (deterministic given input order).
    """
    out_by_key: dict[str, _Candidate] = {}

    def _ingest(raw: dict | None, *, source: str, endpoint_label: str) -> None:
        if raw is None:
            return
        items = _normalize_dfs_response(raw, expected_endpoint=endpoint_label)
        if len(items) > keyword_cap:
            raise KeywordCapExceededError(
                f"{source}: MCP returned {len(items)} candidates > "
                f"keyword_cap={keyword_cap}; refusing to project (DoS guard)"
            )
        for it in items:
            cand = _extract_candidate(it, source=source)
            if cand is None:
                continue
            key = cand.keyword.lower()
            existing = out_by_key.get(key)
            if existing is None or cand.volume > existing.volume:
                out_by_key[key] = cand

    _ingest(
        raw_keyword_ideas,
        source="keyword_ideas",
        endpoint_label="dataforseo_labs_google_keyword_ideas",
    )
    _ingest(
        raw_related_keywords,
        source="related_keywords",
        endpoint_label="dataforseo_labs_google_related_keywords",
    )

    # Sort by volume desc, then keyword asc for determinism.
    return sorted(
        out_by_key.values(),
        key=lambda c: (-c.volume, c.keyword),
    )


# ---------------------------------------------------------------------------
# Geo-analysis staging consume (Phase 7 W-B4 cross-ref, OPTIONAL)
# ---------------------------------------------------------------------------

def _load_geo_staging(path: str | os.PathLike[str] | None) -> list[dict]:
    """Return the list of geo_signals rows from a Phase 7 staging file.

    Graceful: missing / unreadable file → []. Skill caller may opt to
    raise via require=True; the transform-level helper itself NEVER raises
    just because the file is absent (that's GraceFul Skip — the brief's
    DURUR #5 is a SKILL-level decision, not a transform-level one).

    The accepted shape mirrors geo_analysis_transform write_staging
    output: a top-level list (when the staging file holds a single table)
    OR a dict envelope with a 'rows'/'geo_signals' key.
    """
    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    # Accept either:
    #   - top-level list of rows
    #   - dict envelope { "rows": [...] }     (dfs_pull staging style)
    #   - dict envelope { "geo_signals": [...] } (legacy)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = (
            data.get("geo_signals")
            or data.get("rows")
            or data.get("data")
            or []
        )
    else:
        return []
    return [r for r in rows if isinstance(r, dict)]


def _geo_signal_for_query(
    geo_rows: Sequence[dict],
    keyword: str,
) -> dict | None:
    """Return the geo_signals row that matches a candidate keyword (case-
    insensitive on `query`). None when no match."""
    if not geo_rows or not keyword:
        return None
    target = keyword.strip().lower()
    for row in geo_rows:
        q = row.get("query")
        if isinstance(q, str) and q.strip().lower() == target:
            return row
    return None


# ---------------------------------------------------------------------------
# Pillar / cluster assignment
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PillarAssignment:
    """A pillar keyword + its assigned clusters (post-bucketing)."""
    pillar_keyword: str
    pillar_volume: int
    pillar_source: str
    clusters: tuple[_Candidate, ...]
    supporting: tuple[_Candidate, ...]


def _select_pillars(
    candidates: Sequence[_Candidate],
    *,
    seed_keyword: str,
    max_pillars: int,
    min_pillar_volume: int,
) -> list[_Candidate]:
    """Pick the top pillar candidates.

    Strategy:
      1. The seed_keyword is always pillar #1 (synthetic candidate if it
         isn't in the DFS results — a search with 0 volume still earns
         pillar status because it's the user's anchor).
      2. The remaining slots fill with the highest-volume candidates that
         (a) clear `min_pillar_volume`, (b) have non-empty token overlap
         with the seed (>0 — the candidate must share at least one
         meaningful word with the seed; otherwise it's a sibling topic,
         not a sub-pillar), and (c) don't share their token-set with an
         already-selected pillar.
    """
    seed = seed_keyword.strip()
    seed_tokens = frozenset(_tokenize(seed))

    # Synthetic seed candidate when missing.
    seed_cand: _Candidate | None = None
    for c in candidates:
        if c.keyword.lower() == seed.lower():
            seed_cand = c
            break
    if seed_cand is None:
        seed_cand = _Candidate(
            keyword=seed,
            volume=0,
            source="seed",
            tokens=seed_tokens,
        )

    pillars: list[_Candidate] = [seed_cand]
    pillar_token_signatures: list[frozenset[str]] = [seed_tokens]

    if max_pillars <= 1:
        return pillars

    for c in candidates:
        if len(pillars) >= max_pillars:
            break
        if c.keyword.lower() == seed.lower():
            continue
        if c.volume < min_pillar_volume:
            continue
        # Must share at least one token with the seed (still a sub-pillar
        # of the same overall topic).
        if not (c.tokens & seed_tokens):
            continue
        # Reject if its token set is a subset of an already-selected pillar
        # (avoids "dental clinic" + "dental clinics" both getting pillar
        # status — Turkish/English plurals etc.).
        if any(c.tokens <= sig or sig <= c.tokens for sig in pillar_token_signatures):
            continue
        pillars.append(c)
        pillar_token_signatures.append(c.tokens)

    return pillars


def _assign_clusters(
    candidates: Sequence[_Candidate],
    *,
    pillars: Sequence[_Candidate],
    max_clusters_per_pillar: int,
    min_cluster_volume: int,
    max_supporting_per_cluster: int,
) -> list[_PillarAssignment]:
    """Bucket candidates under their best-matching pillar by token overlap.

    Algorithm (deterministic):
      1. Build an exclusion set of pillar keywords (lower-case).
      2. For each remaining candidate, compute token overlap against EVERY
         pillar; assign to the pillar with the maximum overlap > 0.
         Ties broken by pillar order (earlier wins) — pillars are already
         sorted by volume desc, so the dominant pillar absorbs ties.
      3. Per pillar, sort assigned candidates by volume desc and take the
         first `max_clusters_per_pillar` as cluster rows; the next
         `max_supporting_per_cluster` as supporting rows; rest dropped.
      4. Apply `min_cluster_volume` to demote low-volume clusters into
         supporting rows.
    """
    pillar_lower = {p.keyword.lower() for p in pillars}

    # buckets[pillar_index] = list of candidates assigned to that pillar.
    buckets: dict[int, list[_Candidate]] = {i: [] for i in range(len(pillars))}

    for c in candidates:
        if c.keyword.lower() in pillar_lower:
            continue  # don't re-cluster a pillar under itself
        # Pick the best pillar match.
        best_idx: int | None = None
        best_score: float = 0.0
        for i, p in enumerate(pillars):
            score = _topical_overlap(c.tokens, p.tokens)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            # No overlap with any pillar — skip; the candidate belongs to
            # a sibling topic and shouldn't pollute this taxonomy.
            continue
        buckets[best_idx].append(c)

    out: list[_PillarAssignment] = []
    for i, pillar in enumerate(pillars):
        bucket = buckets[i]
        # Sort by volume desc, keyword asc for determinism.
        bucket.sort(key=lambda c: (-c.volume, c.keyword))

        # Pre-split: anything below min_cluster_volume goes to supporting.
        clusters_pool: list[_Candidate] = [
            c for c in bucket if c.volume >= min_cluster_volume
        ]
        supporting_pool: list[_Candidate] = [
            c for c in bucket if c.volume < min_cluster_volume
        ]

        clusters = clusters_pool[:max_clusters_per_pillar]
        # Anything that didn't fit becomes additional supporting.
        overflow = clusters_pool[max_clusters_per_pillar:]
        supporting_pool = overflow + supporting_pool
        supporting = supporting_pool[:max_supporting_per_cluster]

        out.append(_PillarAssignment(
            pillar_keyword=pillar.keyword,
            pillar_volume=pillar.volume,
            pillar_source=pillar.source,
            clusters=tuple(clusters),
            supporting=tuple(supporting),
        ))

    return out


# ---------------------------------------------------------------------------
# Row projection — schema-locked column tuple
# ---------------------------------------------------------------------------

def _priority_for_volume(volume: int) -> str:
    """P1 / P2 / P3 tier from monthly_volume — stable mapping.

      volume >= 1000 → P1
      volume >=  300 → P2
      otherwise      → P3
    """
    if volume >= 1000:
        return "P1"
    if volume >= 300:
        return "P2"
    return "P3"


def _build_note(
    *,
    seed_keyword: str,
    geo_signal: dict | None,
    pillar_volume: int,
) -> str:
    """One-line note: seed anchor, geo-gap if any, pillar volume hint.

    Empty when no signal — never None (schema column is free string).
    """
    parts: list[str] = []
    if seed_keyword:
        parts.append(f"seed={seed_keyword}")
    if geo_signal:
        gap = geo_signal.get("geo_gap")
        if gap:
            parts.append(f"geo_gap={gap}")
        score = geo_signal.get("llm_visibility_score")
        if score is not None:
            try:
                parts.append(f"llm_vis={float(score):.2f}")
            except (TypeError, ValueError):
                pass
    if pillar_volume:
        parts.append(f"pillar_vol={pillar_volume}")
    return "; ".join(parts)


def _project_row(
    *,
    pillar_keyword: str,
    cluster_keyword: str | None,
    primary_keyword: str,
    monthly_volume: int,
    page_type: str,
    default_status: str,
    note: str,
) -> dict:
    """Build one row dict in the exact schema column order, with defensive
    page_type / status / column-tuple validation.
    """
    if page_type not in _PAGE_TYPE_VALUES:
        raise PageTypeError(
            f"page_type {page_type!r} not in documented vocabulary "
            f"{sorted(_PAGE_TYPE_VALUES)}"
        )
    if default_status not in _STATUS_ENUM:
        raise RowSchemaError(
            f"status must be in statusEnum, got {default_status!r}"
        )

    row = {
        "pillar": pillar_keyword,
        "cluster": cluster_keyword if cluster_keyword is not None else "",
        "primary_keyword": primary_keyword,
        "monthly_volume": int(monthly_volume),
        "data_source": DATA_SOURCE_LABEL,
        "assigned_url": "",            # F-09 superset side: empty until cluster-map / manual.
        "page_type": page_type,
        "status": default_status,
        "priority": _priority_for_volume(int(monthly_volume)),
        "note": note,
    }

    # Schema-shape self-check (defensive — catches future drift in the
    # row literal above before it lands in the workbook).
    if tuple(row.keys()) != TOPICAL_MAP_COLUMNS:
        raise RowSchemaError(
            f"row column drift: got {tuple(row.keys())}, "
            f"expected {TOPICAL_MAP_COLUMNS}"
        )
    if not isinstance(row["monthly_volume"], int):
        raise RowSchemaError(
            f"monthly_volume must be int, "
            f"got {type(row['monthly_volume']).__name__}"
        )
    return row


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    *,
    raw_keyword_ideas: dict | None,
    raw_related_keywords: dict | None,
    seed_keyword: str,
    geo_staging_rows: Sequence[dict] | None = None,
    max_pillars: int = DEFAULT_MAX_PILLARS,
    max_clusters_per_pillar: int = DEFAULT_MAX_CLUSTERS_PER_PILLAR,
    max_supporting_per_cluster: int = DEFAULT_MAX_SUPPORTING_PER_CLUSTER,
    min_pillar_volume: int = DEFAULT_MIN_PILLAR_VOLUME,
    min_cluster_volume: int = DEFAULT_MIN_CLUSTER_VOLUME,
    keyword_cap: int = DEFAULT_KEYWORD_CAP,
    default_status: str = "TODO",
    fetched_at: str | None = None,
) -> dict:
    """
    Build a pillar/cluster taxonomy → master.xlsx#topical_map row list.

    Args:
        raw_keyword_ideas:    parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_keyword_ideas.
            REST envelope OR flat wrapper tolerated (D-003 fix via
            imported `_normalize_dfs_response`).
        raw_related_keywords: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_related_keywords.
        seed_keyword:         the seed concept driving the taxonomy. Becomes
            pillar #1 even if absent from the DFS payload.
        geo_staging_rows:     optional list of geo_signals rows (Phase 7
            W-B4 staging consume). When present, each topical_map row's
            `note` column is enriched with the matching `geo_gap` /
            `llm_visibility_score` signals.
        max_pillars:          upper bound on pillar rows (default 5).
        max_clusters_per_pillar: upper bound on cluster rows per pillar
            (default 6).
        max_supporting_per_cluster: upper bound on supporting rows per
            pillar bucket (default 0 — supporting rows OFF unless caller
            opts in; keeps initial topical_map writes lean).
        min_pillar_volume:    monthly_volume threshold for elevating a
            non-seed candidate to pillar status (default 100).
        min_cluster_volume:   monthly_volume threshold for cluster status
            (default 30); below → demoted to supporting pool.
        keyword_cap:          DoS guard per MCP tool (default 5000).
        default_status:       statusEnum seed for all new rows (default
            "TODO"). Must be in master-excel.schema.json
            #/definitions/statusEnum.
        fetched_at:           ISO 8601 timestamp; defaults to now (UTC, μs).

    Returns:
        {
          "topical_map": [<row>, ...],  # 10-column rows, schema-locked
          "meta": {...},
        }

    Topical_map row shape (master-excel.schema.json#topical_map, 10 cols):
        pillar          str   pillar keyword (page_type=pillar row's primary_keyword)
        cluster         str   cluster keyword OR "" for pillar / supporting rows
        primary_keyword str   the row's own keyword (pillar/cluster/supporting)
        monthly_volume  int   DFS keyword_info.search_volume
        data_source     str   "dataforseo_mcp" (provenance label)
        assigned_url    str   ""  (F-09 superset side; cluster-map fills)
        page_type       str   "pillar" | "cluster" | "supporting"
        status          str   statusEnum (default "TODO")
        priority        str   "P1" / "P2" / "P3" (volume tiers)
        note            str   "seed=...; geo_gap=...; llm_vis=...; pillar_vol=..."

    DURUR triggers (raise TopicalMapError, do NOT silently fallback):
      - default_status not in statusEnum
      - DFS payload exceeds keyword_cap (KeywordCapExceededError)
      - DFS payload shape unparseable (ValueError from _normalize_dfs_response)
      - emitted row column tuple drifts (RowSchemaError)
      - emitted row page_type outside the documented vocabulary (PageTypeError)

    Empty/no-candidate cases are NOT errors — the seed itself becomes a
    single-row topical_map (page_type=pillar) so downstream consumers
    always see a valid F-09 superset to anchor against.
    """
    if not isinstance(seed_keyword, str) or not seed_keyword.strip():
        raise TopicalMapError("seed_keyword must be a non-empty string")
    if default_status not in _STATUS_ENUM:
        raise RowSchemaError(
            f"default_status must be one of {sorted(_STATUS_ENUM)}, "
            f"got {default_status!r}"
        )
    if not isinstance(max_pillars, int) or max_pillars < 1:
        raise TopicalMapError(
            f"max_pillars must be a positive int, got {max_pillars!r}"
        )
    if not isinstance(max_clusters_per_pillar, int) or max_clusters_per_pillar < 0:
        raise TopicalMapError(
            f"max_clusters_per_pillar must be a non-negative int, "
            f"got {max_clusters_per_pillar!r}"
        )
    if not isinstance(keyword_cap, int) or keyword_cap <= 0:
        raise TopicalMapError(
            f"keyword_cap must be a positive int, got {keyword_cap!r}"
        )

    seed = seed_keyword.strip()
    ts = fetched_at or _utc_iso_microseconds()

    # 1. Gather + dedupe candidates (DoS-guarded via keyword_cap).
    candidates = _gather_candidates(
        raw_keyword_ideas, raw_related_keywords,
        keyword_cap=keyword_cap,
    )

    # 2. Pillar selection (seed always = pillar #1).
    pillars = _select_pillars(
        candidates,
        seed_keyword=seed,
        max_pillars=max_pillars,
        min_pillar_volume=min_pillar_volume,
    )

    # 3. Bucket remaining candidates under pillars by token overlap.
    assignments = _assign_clusters(
        candidates,
        pillars=pillars,
        max_clusters_per_pillar=max_clusters_per_pillar,
        min_cluster_volume=min_cluster_volume,
        max_supporting_per_cluster=max_supporting_per_cluster,
    )

    # 4. Project rows. Order: per-pillar block → pillar row first, then its
    #    cluster rows (volume desc), then supporting rows.
    rows: list[dict] = []
    geo_rows: list[dict] = list(geo_staging_rows or [])

    for assign in assignments:
        # 4a. Pillar row.
        pillar_geo = _geo_signal_for_query(geo_rows, assign.pillar_keyword)
        rows.append(_project_row(
            pillar_keyword=assign.pillar_keyword,
            cluster_keyword=None,                  # pillar rows have empty cluster
            primary_keyword=assign.pillar_keyword,
            monthly_volume=assign.pillar_volume,
            page_type=PAGE_TYPE_PILLAR,
            default_status=default_status,
            note=_build_note(
                seed_keyword=seed,
                geo_signal=pillar_geo,
                pillar_volume=assign.pillar_volume,
            ),
        ))

        # 4b. Cluster rows.
        for cluster in assign.clusters:
            cl_geo = _geo_signal_for_query(geo_rows, cluster.keyword)
            rows.append(_project_row(
                pillar_keyword=assign.pillar_keyword,
                cluster_keyword=cluster.keyword,
                primary_keyword=cluster.keyword,
                monthly_volume=cluster.volume,
                page_type=PAGE_TYPE_CLUSTER,
                default_status=default_status,
                note=_build_note(
                    seed_keyword=seed,
                    geo_signal=cl_geo,
                    pillar_volume=assign.pillar_volume,
                ),
            ))

        # 4c. Supporting rows (off by default, max_supporting_per_cluster=0).
        for supp in assign.supporting:
            sp_geo = _geo_signal_for_query(geo_rows, supp.keyword)
            rows.append(_project_row(
                pillar_keyword=assign.pillar_keyword,
                cluster_keyword=supp.keyword,
                primary_keyword=supp.keyword,
                monthly_volume=supp.volume,
                page_type=PAGE_TYPE_SUPPORTING,
                default_status=default_status,
                note=_build_note(
                    seed_keyword=seed,
                    geo_signal=sp_geo,
                    pillar_volume=assign.pillar_volume,
                ),
            ))

    # 5. Final defensive shape lock — every emitted row must match the
    #    schema column tuple exactly.
    for r in rows:
        if tuple(r.keys()) != TOPICAL_MAP_COLUMNS:
            raise RowSchemaError(
                f"row column drift on emit: got {tuple(r.keys())}, "
                f"expected {TOPICAL_MAP_COLUMNS}"
            )

    return {
        "topical_map": rows,
        "meta": {
            "seed_keyword": seed,
            "fetched_at": ts,
            "row_count": len(rows),
            "pillar_count": sum(
                1 for r in rows if r["page_type"] == PAGE_TYPE_PILLAR
            ),
            "cluster_count": sum(
                1 for r in rows if r["page_type"] == PAGE_TYPE_CLUSTER
            ),
            "supporting_count": sum(
                1 for r in rows if r["page_type"] == PAGE_TYPE_SUPPORTING
            ),
            "candidates_seen": len(candidates),
            "geo_staging_rows_consumed": len(geo_rows),
            "max_pillars": int(max_pillars),
            "max_clusters_per_pillar": int(max_clusters_per_pillar),
            "default_status": default_status,
        },
    }


# ---------------------------------------------------------------------------
# Budget pre-flight (subprocess wrapper paterni — W-A3/W-A4)
# ---------------------------------------------------------------------------

def estimate_credits(
    *,
    use_keyword_ideas: bool = True,
    use_related_keywords: bool = True,
) -> float:
    """Estimate DFS credits for a topical-map run.

    keyword_ideas:    ~1 credit per call (covers up to keyword_cap items).
    related_keywords: ~1 credit per call.
    """
    total = 0.0
    if use_keyword_ideas:
        total += CREDITS_PER_KEYWORD_IDEAS_CALL
    if use_related_keywords:
        total += CREDITS_PER_RELATED_KEYWORDS_CALL
    return total


def preflight_budget(
    *,
    project_config_path: str | os.PathLike[str],
    events_path: str | os.PathLike[str],
    script_path: str | os.PathLike[str] = BUDGET_CHECK_SCRIPT,
) -> dict:
    """Run scripts/budget/check_budget.py as a subprocess and DURUR if exit 1.

    Returns the parsed envelope on PASS:
        {"budget_per_day": int, "used_24h": ..., "remaining": ...,
         "exceeded": bool}

    Raises BudgetExceededError when the subprocess exits non-zero — that is
    the canonical "budget would be exceeded by this run" signal per
    §16.8 + W-A3/W-A4. Stderr is preserved on the exception for manager
    diagnostics.

    Mirrors `scripts.discovery.content_gaps_transform.preflight_budget` —
    same boundary semantics, same exception class shape (paid-MCP DURUR).
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
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="topical_map_transform.py",
        description=(
            "Transform DFS keyword_ideas + related_keywords (+ optional "
            "Phase 7 geo_analysis staging) JSON → master.xlsx#topical_map "
            "rows (10-column schema-locked). Skill orchestrator owns the "
            "transaction.append write through workflow_runner approve gate."
        ),
    )
    p.add_argument("--raw-keyword-ideas", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_keyword_ideas JSON.")
    p.add_argument("--raw-related-keywords", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_related_keywords JSON.")
    p.add_argument("--seed-keyword", required=True,
                   help="The seed concept driving the taxonomy (becomes pillar #1).")
    p.add_argument("--geo-staging", default=None,
                   help="Optional path to Phase 7 geo_analysis_geo_signals staging JSON.")
    p.add_argument("--max-pillars", type=int, default=DEFAULT_MAX_PILLARS,
                   help=f"Upper bound on pillar rows (default: {DEFAULT_MAX_PILLARS}).")
    p.add_argument("--max-clusters-per-pillar", type=int,
                   default=DEFAULT_MAX_CLUSTERS_PER_PILLAR,
                   help=f"Upper bound on cluster rows per pillar (default: "
                        f"{DEFAULT_MAX_CLUSTERS_PER_PILLAR}).")
    p.add_argument("--max-supporting-per-cluster", type=int,
                   default=DEFAULT_MAX_SUPPORTING_PER_CLUSTER,
                   help=f"Upper bound on supporting rows per pillar bucket "
                        f"(default: {DEFAULT_MAX_SUPPORTING_PER_CLUSTER}; 0 = OFF).")
    p.add_argument("--min-pillar-volume", type=int,
                   default=DEFAULT_MIN_PILLAR_VOLUME,
                   help=f"Volume threshold for non-seed pillar promotion "
                        f"(default: {DEFAULT_MIN_PILLAR_VOLUME}).")
    p.add_argument("--min-cluster-volume", type=int,
                   default=DEFAULT_MIN_CLUSTER_VOLUME,
                   help=f"Volume threshold for cluster status (default: "
                        f"{DEFAULT_MIN_CLUSTER_VOLUME}).")
    p.add_argument("--keyword-cap", type=int, default=DEFAULT_KEYWORD_CAP,
                   help=f"DoS guard per MCP tool (default: {DEFAULT_KEYWORD_CAP}).")
    p.add_argument("--default-status", default="TODO",
                   help="statusEnum seed value for new rows (default: TODO).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write topical_map.json into this directory.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    ideas_path = Path(args.raw_keyword_ideas)
    if not ideas_path.exists():
        print(f"raw keyword_ideas JSON not found: {ideas_path}", file=sys.stderr)
        return 2
    raw_ideas = _read_json(ideas_path)

    related_path = Path(args.raw_related_keywords)
    if not related_path.exists():
        print(f"raw related_keywords JSON not found: {related_path}", file=sys.stderr)
        return 2
    raw_related = _read_json(related_path)

    geo_rows = _load_geo_staging(args.geo_staging) if args.geo_staging else []

    try:
        result = transform(
            raw_keyword_ideas=raw_ideas,
            raw_related_keywords=raw_related,
            seed_keyword=args.seed_keyword,
            geo_staging_rows=geo_rows,
            max_pillars=args.max_pillars,
            max_clusters_per_pillar=args.max_clusters_per_pillar,
            max_supporting_per_cluster=args.max_supporting_per_cluster,
            min_pillar_volume=args.min_pillar_volume,
            min_cluster_volume=args.min_cluster_volume,
            keyword_cap=args.keyword_cap,
            default_status=args.default_status,
        )
    except (TopicalMapError, ValueError) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "topical_map.json"
        out_path.write_text(
            json.dumps(result["topical_map"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "topical_map_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "TOPICAL_MAP_COLUMNS",
    "PAGE_TYPE_PILLAR",
    "PAGE_TYPE_CLUSTER",
    "PAGE_TYPE_SUPPORTING",
    "DATA_SOURCE_LABEL",
    "DEFAULT_MAX_PILLARS",
    "DEFAULT_MAX_CLUSTERS_PER_PILLAR",
    "DEFAULT_MAX_SUPPORTING_PER_CLUSTER",
    "DEFAULT_MIN_PILLAR_VOLUME",
    "DEFAULT_MIN_CLUSTER_VOLUME",
    "DEFAULT_KEYWORD_CAP",
    "BUDGET_CHECK_SCRIPT",
    "CREDITS_PER_KEYWORD_IDEAS_CALL",
    "CREDITS_PER_RELATED_KEYWORDS_CALL",
    "TopicalMapError",
    "RowSchemaError",
    "BudgetExceededError",
    "KeywordCapExceededError",
    "GeoStagingMissingError",
    "PageTypeError",
    "_normalize_dfs_response",   # re-exported (IDENTITY preserved) for callers
    "transform",
    "estimate_credits",
    "preflight_budget",
    "main",
)
