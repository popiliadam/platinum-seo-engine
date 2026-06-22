#!/usr/bin/env python3
"""
keyword_aio_intel_transform.py — pure transform: raw DFS keyword signals +
SERP AI-Overview → {keyword_set, aio} for the Brief Paketi (CCE batch B1).

Part of the Competitive Content Engine "Silahlanma Motoru". Distils two things
the writer needs from DataForSEO:

  - keyword_set: the candidate keyword expansion. Built from
    ``keyword_suggestions`` (the reliable substring signal, design §4b) and
    enriched / extended by ``keyword_overview`` (per-keyword volume + intent).
  - aio: the Google AI Overview target — the answer_points the AIO makes and
    the cited_sources it shows, so the writer can cover them (AEO gate). When
    the SERP carries no ``ai_overview`` item, ``aio.present`` is False and the
    AEO gate relaxes to "intro answers first" (design §6 R2).

MCP boundary (load-bearing):
    This script NEVER calls MCP. Claude (the skill) calls the DataForSEO MCP
    tools, writes the raw JSON to disk, and this transform ``json.load``s it
    via the CLI. Pure Python only. Pattern reference: scripts/ingestion/dfs_pull.py.

DFS dual-shape (D-003):
    All three raw payloads tolerate the REST envelope
    (``tasks[0].result[0].items``) OR the flat wrapper (``items``) via
    ``scripts.ingestion.dfs_pull._normalize_dfs_response`` — IMPORTED, never
    copied, so any future shape fix is inherited automatically.

Source enum caveat (documented for the manager):
    The Brief schema's ``keyword_set[].source`` enum is ``dfs_suggestions|gsc``.
    This transform sees no GSC input, so every entry is labelled
    ``"dfs_suggestions"`` — including keywords that came from keyword_overview,
    since the enum has no ``dfs_overview`` value. Both are DFS keyword signals.

Pure function discipline (mirrors dfs_pull.py / new_content_plan_transform.py):
    - No state mutation; no file write side-effects on import (CLI only).
    - Idempotent: same input → byte-identical output (no timestamps).

CLI:
    python3 scripts/production/keyword_aio_intel_transform.py \\
        [--raw-overview inbox/cce/{date}-overview-{slug}.json] \\
        [--raw-suggestions inbox/cce/{date}-suggestions-{slug}.json] \\
        [--raw-serp inbox/cce/{date}-serp-{slug}.json] \\
        [--market TR] \\
        [--output _state/cce/{run}/keyword_aio.json]

    Stdout (or --output file): {"keyword_set": [...], "aio": {...}}.

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§4b keyword_aio_intel), docs/superpowers/plans/2026-06-22-competitive-content-
engine.md (Brief Paketi schema). AIO payload shape (docs-verified):
docs/superpowers/plans/amo/2026-06-10-gap-specs-measurement-ai.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

# scripts/ is a namespace package; ensure repo root on sys.path so the absolute
# import of the DFS shape normaliser resolves when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (NOT copy) — D-003 dual-shape normaliser owned by dfs_pull.
from scripts.ingestion.dfs_pull import _normalize_dfs_response  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: keyword_set[].source value emitted by this transform (enum-constrained).
_SOURCE_DFS_SUGGESTIONS = "dfs_suggestions"

#: Title-case intent labels (master/Brief intent enum). Unknown / missing maps
#: to None here so the merge can distinguish "no data" from a real label; the
#: final entry defaults to "Informational" only when every source is silent.
_INTENT_MAP: dict[str, str] = {
    "informational": "Informational",
    "commercial": "Commercial",
    "transactional": "Transactional",
    "navigational": "Navigational",
}
_DEFAULT_INTENT = "Informational"

#: Empty AIO block (no AI Overview present for the query).
_ABSENT_AIO: dict[str, Any] = {"present": False, "answer_points": [], "cited_sources": []}


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


def _dedup_preserve(seq: Iterable[str]) -> list[str]:
    """Exact dedup, preserving first-seen order. Skips empties."""
    out: list[str] = []
    seen: set[str] = set()
    for item in seq:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _intent_label(raw: Any) -> str | None:
    """Normalise a raw intent token to a Title-case label, or None if absent /
    unrecognised (so the merge can fall back to another source)."""
    if not isinstance(raw, str):
        return None
    return _INTENT_MAP.get(raw.strip().lower())


def _safe_items(raw: Any) -> list[dict]:
    """Normalise a DFS payload to a list of item dicts. Tolerant: None or an
    unrecognised shape yields []."""
    if not isinstance(raw, dict):
        return []
    try:
        items = _normalize_dfs_response(raw)
    except (ValueError, TypeError):
        return []
    return [it for it in items if isinstance(it, dict)]


def _item_volume(item: dict) -> int | None:
    """Probe keyword_info.search_volume then a top-level search_volume."""
    ki = item.get("keyword_info")
    if isinstance(ki, dict):
        v = _safe_int(ki.get("search_volume"))
        if v is not None:
            return v
    return _safe_int(item.get("search_volume"))


def _item_intent(item: dict) -> str | None:
    """Extract a Title-case intent label from a DFS keyword item, or None."""
    sii = item.get("search_intent_info")
    raw = None
    if isinstance(sii, dict):
        raw = sii.get("main_intent") or sii.get("primary_intent")
    if raw is None:
        alt = item.get("search_intent") or item.get("intent")
        if isinstance(alt, dict):
            raw = alt.get("main_intent") or alt.get("primary_intent")
        elif isinstance(alt, str):
            raw = alt
    return _intent_label(raw)


# ---------------------------------------------------------------------------
# keyword_set
# ---------------------------------------------------------------------------

def _keyword_map(items: list[dict]) -> dict[str, dict]:
    """Build {kw_lower: {kw, volume, intent}} from DFS keyword items,
    first-seen wins (preserves the source ordering)."""
    out: dict[str, dict] = {}
    for it in items:
        kw = it.get("keyword")
        if not isinstance(kw, str) or not kw.strip():
            continue
        key = kw.strip().casefold()
        if key in out:
            continue
        out[key] = {
            "kw": kw.strip(),
            "volume": _item_volume(it),
            "intent": _item_intent(it),
        }
    return out


def _build_keyword_set(raw_overview: Any, raw_suggestions: Any) -> list[dict]:
    """Merge suggestions (primary) + overview (enrich + extend) → keyword_set.

    Order: suggestions in their order, then overview-only keywords in theirs.
    For a keyword present in both, overview's volume/intent win (more
    authoritative per-keyword). source is always 'dfs_suggestions'.
    """
    sug_map = _keyword_map(_safe_items(raw_suggestions))
    ov_map = _keyword_map(_safe_items(raw_overview))

    ordered_keys = list(sug_map.keys())
    for key in ov_map:
        if key not in sug_map:
            ordered_keys.append(key)

    keyword_set: list[dict] = []
    for key in ordered_keys:
        sug = sug_map.get(key)
        ov = ov_map.get(key)
        base = sug or ov  # for the kw display string (suggestion casing wins)

        ov_vol = ov["volume"] if ov else None
        sug_vol = sug["volume"] if sug else None
        volume = ov_vol if ov_vol is not None else (sug_vol if sug_vol is not None else 0)

        ov_intent = ov["intent"] if ov else None
        sug_intent = sug["intent"] if sug else None
        intent = ov_intent or sug_intent or _DEFAULT_INTENT

        keyword_set.append({
            "kw": base["kw"],
            "volume": int(volume),
            "intent": intent,
            "source": _SOURCE_DFS_SUGGESTIONS,
        })
    return keyword_set


# ---------------------------------------------------------------------------
# AI Overview
# ---------------------------------------------------------------------------

def _collect_ref_urls(refs: Any, out: list[str]) -> None:
    """Append every string ``url`` from a references[] list to ``out``."""
    if not isinstance(refs, list):
        return
    for ref in refs:
        if isinstance(ref, dict):
            url = ref.get("url")
            if isinstance(url, str) and url.strip():
                out.append(url.strip())


def _extract_aio(raw_serp: Any) -> dict:
    """Extract the AI Overview block from a serp_organic_live_advanced payload.

    Returns {"present", "answer_points", "cited_sources"}. answer_points come
    from the ai_overview's nested ``items[]`` (ai_overview_element ``text`` /
    ``markdown`` / ``title``), falling back to the ai_overview's own
    ``markdown``. cited_sources come from the top-level ``references[]`` plus
    any per-element ``references[]``. Absent AIO → present=False, empties.
    """
    items = _safe_items(raw_serp)
    aio = next((it for it in items if it.get("type") == "ai_overview"), None)
    if aio is None:
        return {"present": False, "answer_points": [], "cited_sources": []}

    answer_points: list[str] = []
    sources: list[str] = []

    _collect_ref_urls(aio.get("references"), sources)  # top-level refs first

    elements = aio.get("items")
    if isinstance(elements, list):
        for el in elements:
            if not isinstance(el, dict):
                continue
            txt = el.get("text") or el.get("markdown") or el.get("title")
            if isinstance(txt, str) and txt.strip():
                answer_points.append(_collapse_ws(txt))
            _collect_ref_urls(el.get("references"), sources)

    if not answer_points:
        md = aio.get("markdown")
        if isinstance(md, str) and md.strip():
            answer_points.append(_collapse_ws(md))

    return {
        "present": True,
        "answer_points": _dedup_preserve(answer_points),
        "cited_sources": _dedup_preserve(sources),
    }


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(raw_overview: dict, raw_suggestions: dict, raw_serp: dict, *, market: str) -> dict:
    """Distil DFS keyword signals + SERP AI-Overview into {keyword_set, aio}.

    Args:
        raw_overview: raw DFS ``keyword_overview`` JSON (volume + intent
            enrichment). None → no enrichment / no extra keywords.
        raw_suggestions: raw DFS ``keyword_suggestions`` JSON (the reliable
            substring signal; primary keyword_set source). None → empty.
        raw_serp: raw DFS ``serp_organic_live_advanced`` JSON (AI Overview
            source). None / no ai_overview item → aio.present=False.
        market: project market code (e.g. "TR"). Required, non-empty.

    All three raw payloads tolerate REST-envelope OR flat-wrapper shape.

    Returns:
        {
          "keyword_set": [ {kw, volume, intent, source}, ... ],
          "aio": {"present": bool, "answer_points": [str], "cited_sources": [url]},
        }

    Raises:
        ValueError: market is not a non-empty string.
    """
    if not isinstance(market, str) or not market.strip():
        raise ValueError("market must be a non-empty string")

    return {
        "keyword_set": _build_keyword_set(raw_overview, raw_suggestions),
        "aio": _extract_aio(raw_serp),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="keyword_aio_intel_transform.py",
        description="Transform raw DFS keyword signals + SERP AI-Overview → "
                    "{keyword_set, aio} for the Brief Paketi (CCE arming engine, B1).",
    )
    p.add_argument("--raw-overview", default=None,
                   help="Optional path to keyword_overview JSON (volume + intent enrich).")
    p.add_argument("--raw-suggestions", default=None,
                   help="Optional path to keyword_suggestions JSON (primary keyword_set).")
    p.add_argument("--raw-serp", default=None,
                   help="Optional path to serp_organic_live_advanced JSON (AI Overview).")
    p.add_argument("--market", default="TR",
                   help="Project market code (default: TR).")
    p.add_argument("--output", default=None,
                   help="If set, write {keyword_set, aio} JSON here; else stdout.")
    return p.parse_args(list(argv))


def _read_json_opt(path_str: str | None) -> dict | None:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    raw_overview = _read_json_opt(args.raw_overview)
    raw_suggestions = _read_json_opt(args.raw_suggestions)
    raw_serp = _read_json_opt(args.raw_serp)

    try:
        result = transform(raw_overview, raw_suggestions, raw_serp, market=args.market)
    except ValueError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps({
            "keyword_aio_path": str(out_path.resolve()),
            "keyword_count": len(result["keyword_set"]),
            "aio_present": result["aio"]["present"],
        }, ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "transform",
    "main",
)
