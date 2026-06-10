#!/usr/bin/env python3
"""
quickwins_transform.py — pure transform: GSC quick-wins JSON → schema-shaped rows.

Reads the raw response of mcp__gsc__detect_quick_wins (and optional
mcp__gsc__enhanced_search_analytics enrichment), normalizes URLs per
D-03 (lowercase scheme+host, strip default ports, collapse trailing
slash except root, sort+filter query string, drop fragment, IDN ->
punycode), computes an opportunity score, ranks top-N, and emits two
row lists shaped for master.xlsx#quick_wins and master.xlsx#opportunity
(see schemas/master-excel.schema.json required_columns).

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same input → same output.

Opportunity scoring is the GAP-M3 expected-CTR-uplift model: ranked by
``expected_uplift_clicks`` (impressions × CTR(target position) × AIO factor −
current clicks), with the legacy headroom score retained as a deterministic
tiebreaker. CTR/AIO numbers come from ``ctr-curve.json`` (R-139 — no literals
here). AIO presence (R-140) rides optional columns K–N / I–J.

CLI:
  python3 scripts/discovery/quickwins_transform.py \
      --raw inbox/gsc/{date}-detect_quick_wins-{slug}.json \
      [--enriched inbox/gsc/{date}-enhanced_search_analytics-{slug}.json] \
      [--top-n 50] \
      [--threshold-position-max 20] \
      [--ctr-curve ctr-curve.json] \
      [--aio-presence inbox/dfs/{date}-aio_presence-{slug}.json] \
      [--output-dir .]

Stdout: JSON {"quick_wins": [...], "opportunity": [...], "meta": {...}}.
With --output-dir set: also writes quick_wins.json + opportunity.json
into that directory and prints their absolute paths.

Refs: schemas/master-excel.schema.json (quick_wins, opportunity sheets,
definitions block), schemas/gsc-tool-mapping.schema.json (D-03 URL
normalization invariant), spec §16.5 (raw JSON inbox + transform stage).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Direct re-export: quickwins previously raised bare ValueError;
# URLNormalizeError(ValueError) preserves that contract (K-01 dedup,
# v1.5-Phase-1 Tier 1).
from scripts.util.profile_aware_defaults import (  # noqa: E402
    cascade_default,
)
from scripts.util.url_normalize import normalize_url  # noqa: E402,F401
from scripts.util import ctr_curve as _ctr_curve  # noqa: E402

# ---------------------------------------------------------------------------
# Constants — schema-aligned column names (master-excel.schema.json)
# ---------------------------------------------------------------------------

QUICK_WINS_COLUMNS = (
    "query",
    "url",
    "current_position",
    "impressions_30d",
    "clicks_30d",
    "ctr_pct",
    "potential_clicks",
    "opportunity",
    "action",
    "priority",
    # GAP-M2 D3 additive (ADR-018; no schema_version bump). aio_presence ∈
    # {present, not_detected, unchecked} (measurement-discipline R-140);
    # expected_uplift_clicks = GAP-M3 CTR-uplift model (R-139 curve).
    "aio_presence",
    "aio_own_cited",
    "aio_checked_date",
    "expected_uplift_clicks",
)

OPPORTUNITY_COLUMNS = (
    "query",
    "opportunity_score",
    "current_position",
    "ctr_pct",
    "impressions_30d",
    "clicks_30d",
    "potential_clicks",
    "assigned_url_action",
    # GAP-M2 D3 additive (mirrors quick_wins; opportunity_score col stays the
    # legacy headroom number — expected_uplift_clicks carries the v2 model).
    "aio_presence",
    "expected_uplift_clicks",
)

# ---------------------------------------------------------------------------
# Tunable defaults (Y-06 cascade candidates — profile config can override
# at main() resolution via cascade_default with the same keys).
# ---------------------------------------------------------------------------

_DEFAULT_TOP_N: int = 50
_DEFAULT_THRESHOLD_POSITION_MAX: int = 20

# ---------------------------------------------------------------------------
# Opportunity score
# ---------------------------------------------------------------------------

def opportunity_score(
    impressions: float,
    position: float,
    *,
    threshold_position_max: int = 20,
) -> float:
    """
    Compute an opportunity score for a single quick-win row.

    Formula (deterministic, monotonic in impressions and in
    (threshold_position_max - position)):

        score = impressions * max(0, threshold_position_max - position)

    Rationale: a query at position 11 with 1000 impressions has a much
    larger upside than a query at position 19 with 1000 impressions.
    Capping at threshold_position_max ensures rows that drift beyond the
    threshold (between fetch and transform) score 0 instead of negative.
    """
    if impressions is None or position is None:
        return 0.0
    try:
        imp = float(impressions)
        pos = float(position)
    except (TypeError, ValueError):
        return 0.0
    return imp * max(0.0, float(threshold_position_max) - pos)


def expected_uplift_clicks(
    impressions: float,
    position: float,
    clicks: float | None,
    curve: "_ctr_curve.Curve",
    aio_presence: str = "unchecked",
) -> int:
    """Expected 28-day click gain from moving a quick-win onto page 1.

    Model (GAP-M3; forecast-style scoring):

        target  = min(10, max(5, position - 5))   # page-1 bottom half, never top-3
        ctr_t   = curve.expected_ctr(target) * curve.aio_factor(target, aio_presence)
        uplift  = max(0, round(impressions * ctr_t - current_clicks))

    Observed clicks are subtracted so a row that already converts well does
    not double-count. AIO-`present` queries carry the curve's per-position
    discount; `not_detected`/`unchecked` are NOT discounted (R-140 honesty —
    an unproven AIO is flagged, never penalised). All CTR/discount numbers
    come from ``curve`` (ctr-curve.json), never literals (R-139).
    """
    if impressions is None or position is None:
        return 0
    try:
        imp = float(impressions)
        pos = float(position)
    except (TypeError, ValueError):
        return 0
    target = min(10.0, max(5.0, pos - 5.0))
    ctr_t = curve.expected_ctr(target) * curve.aio_factor(target, aio_presence)
    try:
        current = float(clicks or 0)
    except (TypeError, ValueError):
        current = 0.0
    return max(0, int(round(imp * ctr_t - current)))


def load_aio_presence(path: Path) -> dict[str, dict]:
    """Read a consolidated AIO-presence file → ``{query: presence-info}``.

    Expected shape (built by quick-wins Step `fetch_aio_presence` from the
    raw SERP inbox payload): ``{query: {"aio_presence": "present"|"not_detected",
    "own_domain_cited": bool, "checked_date": str, "detection_source": str}}``.
    Only decisive presence rows (`present`/`not_detected`) are recorded;
    queries absent from the file stay ``unchecked`` downstream. Missing or
    malformed file → ``{}`` (AIO enrichment is optional — never DURUR here;
    the curve scorer simply treats every query as `unchecked`).
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict] = {}
    for query, info in data.items():
        if not isinstance(info, dict):
            continue
        presence = info.get("aio_presence")
        if presence not in ("present", "not_detected"):
            continue
        out[str(query)] = {
            "aio_presence": presence,
            "own_domain_cited": bool(info.get("own_domain_cited")),
            "checked_date": str(info.get("checked_date") or ""),
            "detection_source": str(info.get("detection_source") or ""),
        }
    return out


# ---------------------------------------------------------------------------
# Enrichment loader (optional)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnrichmentRow:
    query: str
    url_normalized: str
    clicks: int | None
    impressions: int | None
    ctr: float | None
    position: float | None


def _load_enrichment(path: Path) -> dict[tuple[str, str], EnrichmentRow]:
    """
    Read an mcp__gsc__enhanced_search_analytics raw JSON; index rows by
    (query, normalized_url). Returns an empty dict on missing file or
    malformed payload — enrichment is optional.
    """
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}

    rows = data.get("rows") or data.get("data") or []
    out: dict[tuple[str, str], EnrichmentRow] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        keys = r.get("keys") or []
        if len(keys) < 2:
            continue
        query = str(keys[0])
        try:
            url_n = normalize_url(str(keys[1]))
        except ValueError:
            continue
        out[(query, url_n)] = EnrichmentRow(
            query=query,
            url_normalized=url_n,
            clicks=_safe_int(r.get("clicks")),
            impressions=_safe_int(r.get("impressions")),
            ctr=_safe_float(r.get("ctr")),
            position=_safe_float(r.get("position")),
        )
    return out


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


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

# GAP-M3: labels are re-banded on click units (expected_uplift_clicks/28d),
# NOT the legacy headroom score. Thresholds are cascade_default-overridable
# (keys uplift_high_threshold / uplift_medium_threshold). These are label
# bands, not curve constants — outside R-139's grep-sentinel scope.
_UPLIFT_HIGH_THRESHOLD: int = 50
_UPLIFT_MEDIUM_THRESHOLD: int = 15


def _opportunity_label(
    uplift: float,
    *,
    high: float = _UPLIFT_HIGH_THRESHOLD,
    medium: float = _UPLIFT_MEDIUM_THRESHOLD,
) -> str:
    """Coarse opportunity label (expected-clicks band) — at-a-glance sheet hint."""
    if uplift >= high:
        return "High"
    if uplift >= medium:
        return "Medium"
    return "Low"


def _priority_label(
    uplift: float,
    *,
    high: float = _UPLIFT_HIGH_THRESHOLD,
    medium: float = _UPLIFT_MEDIUM_THRESHOLD,
) -> str:
    """severityEnum-aligned priority (HIGH/MEDIUM/LOW) on the expected-clicks band."""
    if uplift >= high:
        return "HIGH"
    if uplift >= medium:
        return "MEDIUM"
    return "LOW"


def _action_text(position: float) -> str:
    """Short, concrete action hint based on position bucket."""
    if position <= 13:
        return "Refresh meta + on-page entity coverage to break top-10"
    if position <= 16:
        return "Add internal links + improve title CTR"
    return "Expand content depth + add FAQ schema"


def _row_pct(ctr: float | None) -> float:
    """
    Convert GSC ctr (0-1 fractional) → integer-friendly percentage.

    GSC quick-wins responses sometimes return CTR as a percent already
    (e.g. 0.63 == 0.63%). enhanced_search_analytics returns 0-1
    fractional. Heuristic: if value <= 1.0 treat as fractional; else as
    already-percent. Rounded to 4 decimals to keep the schema clean.
    """
    if ctr is None:
        return 0.0
    try:
        val = float(ctr)
    except (TypeError, ValueError):
        return 0.0
    if val <= 1.0:
        val = val * 100.0
    return round(val, 4)


# ---------------------------------------------------------------------------
# Control-cohort matching (GAP-M-W2 — R-138 intervention cohort tagging)
# ---------------------------------------------------------------------------

# Same-band match tolerances (R-138). Cohort-file `matching` block mirrors these.
_COHORT_POSITION_TOLERANCE: float = 2.0
_COHORT_IMPRESSIONS_RATIO_MAX: float = 2.0
_COHORT_ROW_KEYS = ("query", "url", "position", "impressions_30d", "clicks_30d")


def _cohort_row(r: dict) -> dict:
    """Project a scored row into the cohort-file shape consumed by
    scripts/reporting/intervention_outcome.py (position = current_position)."""
    return {
        "query": r["query"],
        "url": r["url"],
        "position": r["current_position"],
        "impressions_30d": r["impressions_30d"],
        "clicks_30d": r["clicks_30d"],
    }


def _select_control_cohort(
    treated: list[dict],
    candidates: list[dict],
    *,
    position_tolerance: float = _COHORT_POSITION_TOLERANCE,
    impressions_ratio_max: float = _COHORT_IMPRESSIONS_RATIO_MAX,
) -> list[dict]:
    """Greedy nearest-position control match (R-138).

    For each treated row, pick the nearest UNUSED candidate (from the
    scored-but-not-selected tail) whose position is within ``position_tolerance``
    and whose impressions are within ``[1/ratio_max, ratio_max]`` of the treated
    row. Each candidate is used at most once; candidates whose query collides
    with ANY treated query are skipped (the downstream outcome indexes by query,
    so treated/control must be query-disjoint). Deterministic: ``candidates`` is
    already rank-sorted, so candidate index breaks distance ties.
    """
    ratio_min = 1.0 / impressions_ratio_max
    treated_queries = {t["query"] for t in treated}
    used: set[int] = set()
    controls: list[dict] = []
    for t in treated:
        t_pos = float(t["current_position"])
        t_imp = float(t["impressions_30d"])
        if t_imp <= 0:
            continue
        best_idx: int | None = None
        best_key: tuple[float, int] | None = None
        for idx, c in enumerate(candidates):
            if idx in used or c["query"] in treated_queries:
                continue
            c_imp = float(c["impressions_30d"])
            if c_imp <= 0:
                continue
            pos_diff = abs(float(c["current_position"]) - t_pos)
            if pos_diff > position_tolerance:
                continue
            ratio = c_imp / t_imp
            if not (ratio_min <= ratio <= impressions_ratio_max):
                continue
            key = (pos_diff, idx)
            if best_key is None or key < best_key:
                best_key, best_idx = key, idx
        if best_idx is not None:
            used.add(best_idx)
            controls.append(_cohort_row(candidates[best_idx]))
    return controls


def transform(
    raw: dict,
    *,
    enriched: dict[tuple[str, str], EnrichmentRow] | None = None,
    top_n: int = 50,
    threshold_position_max: int = 20,
    dedup_by_url: bool = True,
    curve: "_ctr_curve.Curve | None" = None,
    aio_presence: dict[str, dict] | None = None,
) -> dict:
    """
    Transform an mcp__gsc__detect_quick_wins payload into schema-shaped
    quick_wins + opportunity row lists.

    Args:
        raw: Parsed JSON payload from mcp__gsc__detect_quick_wins. Must
             contain a 'quickWins' (or 'quick_wins') list.
        enriched: Optional mapping (query, url_normalized) → EnrichmentRow
                  used to back-fill clicks/impressions/ctr/position when
                  the quick-wins payload is sparse.
        top_n: Cap on output row count (after ranking).
        threshold_position_max: Position ceiling used in the LEGACY headroom
                  score (retained as the v2 ranking tiebreaker + col B).
        dedup_by_url: D-011 fix (Phase 7 closeout). When True (default),
                      keep only the best row per url_normalized (collapses
                      multi-query rows that share a URL). Phase 6 live capture
                      surfaced 33 quick_wins rows → 7 unique URLs (~26
                      duplicate). Set False for multi-query analysis.
        curve: GAP-M3 CTR-uplift curve. None ⇒ load the bundled
               ``ctr-curve.json`` (DURUR #11 if missing/invalid — never a
               silent fallback to the legacy formula). The curve is ALWAYS
               applied; "required" is satisfied by no-fallback, not by a
               mandatory positional arg (keeps existing callers working).
        aio_presence: GAP-M2 consolidated ``{query: presence-info}`` map (see
               ``load_aio_presence``). None ⇒ every query is ``unchecked``.

    Returns:
        {"quick_wins": [...], "opportunity": [...], "meta": {...}}.
        Primary ranking key = expected_uplift_clicks (desc); legacy
        opportunity_score is tiebreaker #2 (then query asc, url asc).
    """
    if not isinstance(raw, dict):
        raise ValueError(f"raw must be a dict, got {type(raw).__name__}")
    if top_n is None or top_n < 1:
        raise ValueError(f"top_n must be a positive int, got {top_n!r}")

    items = raw.get("quickWins") or raw.get("quick_wins") or []
    if not isinstance(items, list):
        raise ValueError("raw['quickWins'] must be a list")

    if curve is None:
        # DURUR #11: missing/invalid ctr-curve.json raises CurveLoadError —
        # no silent fallback to the legacy headroom formula.
        curve = _ctr_curve.load_curve(_REPO_ROOT / "ctr-curve.json")

    enrich = enriched or {}
    aio_map = aio_presence or {}

    scored: list[dict] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        query = entry.get("query")
        page = entry.get("page") or entry.get("url")
        if not query or not page:
            continue

        try:
            url_n = normalize_url(str(page))
        except ValueError:
            continue

        position = _safe_float(entry.get("currentPosition")
                               or entry.get("position"))
        impressions = _safe_int(entry.get("impressions"))
        clicks = _safe_int(entry.get("currentClicks") or entry.get("clicks"))
        ctr_raw = entry.get("currentCtr")
        if ctr_raw is None:
            ctr_raw = entry.get("ctr")
        potential = _safe_int(entry.get("potentialClicks"))

        # Enrich (back-fill) when the quick-wins row is sparse.
        e = enrich.get((str(query), url_n))
        if e:
            if position is None:
                position = e.position
            if impressions is None:
                impressions = e.impressions
            if clicks is None:
                clicks = e.clicks
            if ctr_raw is None:
                ctr_raw = e.ctr

        if position is None or impressions is None:
            # Cannot score without these; skip silently rather than crash —
            # caller can audit raw JSON for sparse rows.
            continue

        # Legacy headroom score — retained as the v2 ranking tiebreaker and as
        # the opportunity sheet's col B (no column re-semantics).
        legacy_score = opportunity_score(
            impressions, position,
            threshold_position_max=threshold_position_max,
        )

        # GAP-M2: per-query AIO presence (consolidated map). Decisive only;
        # queries absent from the map stay "unchecked" (R-140: unchecked ≠
        # not_detected).
        aio_info = aio_map.get(str(query))
        row_presence = aio_info["aio_presence"] if aio_info else "unchecked"
        row_own_cited = bool(aio_info["own_domain_cited"]) if aio_info else False
        row_checked_date = aio_info["checked_date"] if aio_info else ""

        # GAP-M3: expected 28-day click uplift (CTR curve × AIO factor).
        uplift = expected_uplift_clicks(
            impressions, position, clicks, curve, aio_presence=row_presence,
        )

        ctr_pct = _row_pct(ctr_raw)

        scored.append({
            "_uplift": uplift,
            "_legacy": legacy_score,
            "query": str(query),
            "url": url_n,
            "current_position": round(float(position), 2),
            "impressions_30d": int(impressions),
            "clicks_30d": int(clicks) if clicks is not None else 0,
            "ctr_pct": ctr_pct,
            "potential_clicks": int(potential) if potential is not None else 0,
            "opportunity": _opportunity_label(uplift),
            "action": _action_text(float(position)),
            "priority": _priority_label(uplift),
            "aio_presence": row_presence,
            "aio_own_cited": row_own_cited,
            "aio_checked_date": row_checked_date,
            "expected_uplift_clicks": uplift,
        })

    # Ranking key (GAP-M3): expected_uplift_clicks desc (primary), then the
    # legacy headroom score desc (tiebreaker #2), then query/url asc — the
    # existing deterministic tiebreak discipline.
    def _rank_key(r: dict) -> tuple:
        return (-r["_uplift"], -r["_legacy"], r["query"], r["url"])

    # D-011 fix (Phase 7 closeout): collapse rows that share the same
    # url_normalized — keep the best row per URL by the v2 rank key.
    if dedup_by_url:
        by_url: dict[str, dict] = {}
        for r in scored:
            existing = by_url.get(r["url"])
            if existing is None or _rank_key(r) < _rank_key(existing):
                by_url[r["url"]] = r
        scored = list(by_url.values())

    scored.sort(key=_rank_key)
    top = scored[:top_n]

    quick_wins_rows = [
        {k: r[k] for k in QUICK_WINS_COLUMNS}
        for r in top
    ]

    # Opportunity sheet aggregates by query (one row per query, best rank).
    opp_by_query: dict[str, dict] = {}
    for r in top:
        q = r["query"]
        existing = opp_by_query.get(q)
        if existing is None or _rank_key(r) < _rank_key(existing):
            opp_by_query[q] = {
                "_uplift": r["_uplift"],
                "_legacy": r["_legacy"],
                "query": q,
                "url": r["url"],
                "opportunity_score": round(float(r["_legacy"]), 2),
                "current_position": r["current_position"],
                "ctr_pct": r["ctr_pct"],
                "impressions_30d": r["impressions_30d"],
                "clicks_30d": r["clicks_30d"],
                "potential_clicks": r["potential_clicks"],
                "assigned_url_action": f"{r['url']} | {r['action']}",
                "aio_presence": r["aio_presence"],
                "expected_uplift_clicks": r["expected_uplift_clicks"],
            }

    opportunity_rows = [
        {k: v[k] for k in OPPORTUNITY_COLUMNS}
        for v in sorted(opp_by_query.values(), key=_rank_key)
    ]

    aio_checked_count = sum(
        1 for r in quick_wins_rows
        if r["aio_presence"] in ("present", "not_detected")
    )

    # GAP-M-W2 (R-138): match a control cohort from the scored-but-not-selected
    # tail (rank top_n+1 ..) — same-band, untouched queries used for the
    # treated-vs-control attribution. `scored` is rank-sorted; `top` is its
    # selected prefix, so `scored[len(top):]` is the candidate pool.
    control_cohort = _select_control_cohort(top, scored[len(top):])

    return {
        "quick_wins": quick_wins_rows,
        "opportunity": opportunity_rows,
        "control_cohort": control_cohort,
        "meta": {
            "input_count": len(items),
            "scored_count": len(scored),
            "top_n_applied": len(quick_wins_rows),
            "opportunity_count": len(opportunity_rows),
            "threshold_position_max": threshold_position_max,
            "enriched_used": bool(enrich),
            "dedup_by_url_applied": bool(dedup_by_url),
            "score_version": "2.0",
            "curve_version": curve.curve_version,
            "aio_checked_count": aio_checked_count,
            "controls_matched": len(control_cohort),
            "cohort_matching": {
                "position_tolerance": _COHORT_POSITION_TOLERANCE,
                "impressions_ratio_max": _COHORT_IMPRESSIONS_RATIO_MAX,
            },
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="quickwins_transform.py",
        description="Transform GSC detect_quick_wins JSON → schema-shaped rows.",
    )
    p.add_argument("--raw", required=True,
                   help="Path to raw mcp__gsc__detect_quick_wins JSON.")
    p.add_argument("--enriched", default=None,
                   help="Optional path to enhanced_search_analytics JSON.")
    p.add_argument("--top-n", type=int, default=None,
                   help=f"Top-N rows by opportunity score (inline default: "
                        f"{_DEFAULT_TOP_N}; profile override via Y-06 "
                        f"cascade_default).")
    p.add_argument("--threshold-position-max", type=int, default=None,
                   help=f"Position ceiling for scoring (inline default: "
                        f"{_DEFAULT_THRESHOLD_POSITION_MAX}; profile "
                        f"override via Y-06 cascade_default).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write quick_wins.json + opportunity.json here.")
    p.add_argument("--ctr-curve", default=str(_REPO_ROOT / "ctr-curve.json"),
                   help="Path to the versioned CTR/AIO curve (R-139). "
                        "Default: engine-root ctr-curve.json. Missing/invalid "
                        "→ DURUR (no silent fallback to the legacy formula).")
    p.add_argument("--aio-presence", default=None,
                   help="Optional consolidated AIO-presence JSON "
                        "({query: presence-info}); absent → all queries "
                        "'unchecked' (GAP-M2).")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    raw_path = Path(args.raw)
    if not raw_path.exists():
        print(f"raw JSON not found: {raw_path}", file=sys.stderr)
        return 2
    raw = _read_json(raw_path)

    enriched: dict[tuple[str, str], EnrichmentRow] = {}
    if args.enriched:
        enriched = _load_enrichment(Path(args.enriched))

    # Y-06 three-tier cascade: CLI override > profile config > inline default.
    # Profile dict empty pending project-config schema fields; load_profile
    # wiring is opt-in for future v1.7+.
    top_n = cascade_default(
        {}, "top_n", _DEFAULT_TOP_N, override=args.top_n,
    )
    threshold_position_max = cascade_default(
        {}, "threshold_position_max", _DEFAULT_THRESHOLD_POSITION_MAX,
        override=args.threshold_position_max,
    )

    # GAP-M3: load the versioned curve (DURUR #11 on missing/invalid).
    try:
        curve = _ctr_curve.load_curve(args.ctr_curve)
    except _ctr_curve.CurveLoadError as exc:
        print(f"ctr-curve load failed (DURUR #11): {exc}", file=sys.stderr)
        return 1

    # GAP-M2: optional consolidated AIO-presence map (absent → all unchecked).
    aio_presence = (
        load_aio_presence(Path(args.aio_presence)) if args.aio_presence else None
    )

    try:
        result = transform(
            raw,
            enriched=enriched,
            top_n=top_n,
            threshold_position_max=threshold_position_max,
            curve=curve,
            aio_presence=aio_presence,
        )
    except ValueError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        qw_path = out_dir / "quick_wins.json"
        op_path = out_dir / "opportunity.json"
        qw_path.write_text(
            json.dumps(result["quick_wins"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        op_path.write_text(
            json.dumps(result["opportunity"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "quick_wins_path": str(qw_path.resolve()),
            "opportunity_path": str(op_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "QUICK_WINS_COLUMNS",
    "OPPORTUNITY_COLUMNS",
    "normalize_url",
    "opportunity_score",
    "expected_uplift_clicks",
    "load_aio_presence",
    "transform",
    "main",
)
