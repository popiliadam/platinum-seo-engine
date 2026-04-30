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

CLI:
  python3 scripts/discovery/quickwins_transform.py \
      --raw inbox/gsc/2026-04-30-detect_quick_wins-dentnotion.json \
      [--enriched inbox/gsc/2026-04-30-enhanced_search_analytics-dentnotion.json] \
      [--top-n 50] \
      [--threshold-position-max 20] \
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
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urlsplit,
    urlunsplit,
)

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
)

# Default scheme ports we strip from netloc (D-03).
_DEFAULT_PORTS = {"http": "80", "https": "443"}

# Tracking-style query params we drop entirely (D-03 cleanup; deterministic
# and idempotent). Keep the list small + obviously-tracking; do NOT drop
# arbitrary query keys (would lose canonicality).
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "msclkid",
})


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """
    Normalize a URL per D-03 invariant.

    Rules (deterministic, idempotent):
      1. Trim surrounding whitespace.
      2. Lowercase scheme + host (path/query case-preserved).
      3. IDN host → punycode (idna ascii) when non-ASCII.
      4. Strip default port (:80 for http, :443 for https).
      5. Trailing slash on path: keep root '/' as-is, strip on others.
      6. Drop fragment (everything after '#').
      7. Drop tracking params (utm_*, gclid, fbclid, ...).
      8. Sort remaining query params by key, stable for equal keys.

    Returns the normalized URL string. Raises ValueError on completely
    unparseable input (empty / no scheme).
    """
    if not isinstance(url, str):
        raise ValueError(f"url must be a string, got {type(url).__name__}")
    raw = url.strip()
    if not raw:
        raise ValueError("url is empty")

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if not scheme:
        raise ValueError(f"url missing scheme: {url!r}")

    # Host + port handling.
    host = parts.hostname or ""
    if host:
        try:
            host_ascii = host.encode("idna").decode("ascii")
        except (UnicodeError, UnicodeDecodeError):
            # Non-IDN-encodable host (e.g. underscore, raw IP). Lowercase ASCII
            # fallback preserves determinism without crashing.
            host_ascii = host.lower()
        else:
            host_ascii = host_ascii.lower()
    else:
        host_ascii = ""

    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host_ascii}:{port}"
    else:
        netloc = host_ascii

    # Userinfo is preserved as-is (rare, but don't lose it). Lowercase only
    # the host portion.
    if parts.username is not None:
        user = quote(parts.username, safe="")
        if parts.password is not None:
            user = f"{user}:{quote(parts.password, safe='')}"
        netloc = f"{user}@{netloc}"

    # Path: strip trailing slash unless path is exactly '/'.
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
        if not path:
            path = "/"

    # Query: drop tracking, sort the rest.
    qs_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned = [(k, v) for (k, v) in qs_pairs if k.lower() not in _TRACKING_PARAMS]
    cleaned.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(cleaned, doseq=False)

    # Fragment dropped entirely.
    fragment = ""

    return urlunsplit((scheme, netloc, path, query, fragment))


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

def _opportunity_label(score: float) -> str:
    """Coarse opportunity label used as an at-a-glance hint in the sheet."""
    if score >= 5000:
        return "High"
    if score >= 1500:
        return "Medium"
    return "Low"


def _priority_label(score: float) -> str:
    """severityEnum-aligned priority (CRITICAL/HIGH/MEDIUM/LOW)."""
    if score >= 5000:
        return "HIGH"
    if score >= 1500:
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


def transform(
    raw: dict,
    *,
    enriched: dict[tuple[str, str], EnrichmentRow] | None = None,
    top_n: int = 50,
    threshold_position_max: int = 20,
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
        threshold_position_max: Position ceiling used in scoring.

    Returns:
        {"quick_wins": [...], "opportunity": [...], "meta": {...}}.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"raw must be a dict, got {type(raw).__name__}")
    if top_n is None or top_n < 1:
        raise ValueError(f"top_n must be a positive int, got {top_n!r}")

    items = raw.get("quickWins") or raw.get("quick_wins") or []
    if not isinstance(items, list):
        raise ValueError("raw['quickWins'] must be a list")

    enrich = enriched or {}

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

        score = opportunity_score(
            impressions, position,
            threshold_position_max=threshold_position_max,
        )

        ctr_pct = _row_pct(ctr_raw)

        scored.append({
            "_score": score,
            "query": str(query),
            "url": url_n,
            "current_position": round(float(position), 2),
            "impressions_30d": int(impressions),
            "clicks_30d": int(clicks) if clicks is not None else 0,
            "ctr_pct": ctr_pct,
            "potential_clicks": int(potential) if potential is not None else 0,
            "opportunity": _opportunity_label(score),
            "action": _action_text(float(position)),
            "priority": _priority_label(score),
        })

    # Stable sort: score desc, then by query asc for determinism.
    scored.sort(key=lambda r: (-r["_score"], r["query"], r["url"]))
    top = scored[:top_n]

    quick_wins_rows = [
        {k: r[k] for k in QUICK_WINS_COLUMNS}
        for r in top
    ]

    # Opportunity sheet aggregates by query (one row per query, max score).
    opp_by_query: dict[str, dict] = {}
    for r in top:
        q = r["query"]
        existing = opp_by_query.get(q)
        if existing is None or r["_score"] > existing["_score"]:
            opp_by_query[q] = {
                "_score": r["_score"],
                "query": q,
                "opportunity_score": round(float(r["_score"]), 2),
                "current_position": r["current_position"],
                "ctr_pct": r["ctr_pct"],
                "impressions_30d": r["impressions_30d"],
                "clicks_30d": r["clicks_30d"],
                "potential_clicks": r["potential_clicks"],
                "assigned_url_action": f"{r['url']} | {r['action']}",
            }

    opportunity_rows = [
        {k: v[k] for k in OPPORTUNITY_COLUMNS}
        for v in sorted(
            opp_by_query.values(),
            key=lambda r: (-r["_score"], r["query"]),
        )
    ]

    return {
        "quick_wins": quick_wins_rows,
        "opportunity": opportunity_rows,
        "meta": {
            "input_count": len(items),
            "scored_count": len(scored),
            "top_n_applied": len(quick_wins_rows),
            "opportunity_count": len(opportunity_rows),
            "threshold_position_max": threshold_position_max,
            "enriched_used": bool(enrich),
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
    p.add_argument("--top-n", type=int, default=50,
                   help="Top-N rows by opportunity score (default: 50).")
    p.add_argument("--threshold-position-max", type=int, default=20,
                   help="Position ceiling for scoring (default: 20).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write quick_wins.json + opportunity.json here.")
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

    try:
        result = transform(
            raw,
            enriched=enriched,
            top_n=args.top_n,
            threshold_position_max=args.threshold_position_max,
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
    "transform",
    "main",
)
