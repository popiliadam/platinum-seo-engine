#!/usr/bin/env python3
"""
dfs_pull.py — pure transform: DataForSEO keyword_overview + Google Ads
search_volume raw JSON → schema-shaped rows for master.xlsx.

Reads the raw response of mcp__dataforseo__dataforseo_labs_google_keyword_overview
(primary) plus the optional mcp__dataforseo__keywords_data_google_ads_search_volume
fallback / cross-check, normalises units, applies the TR forwarding
workaround (the dataforseo-mcp-server@2.8.9 wrapper does not always
forward location_code/language_code — see SKILL.md TR Workaround), and
emits two row lists shaped for the master-excel.schema sheets:

  - cluster_keywords  (per-keyword volume / position rows; col contract
                       at schemas/master-excel.schema.json#/sheets/cluster_keywords)
  - opportunity       (per-keyword opportunity score; shared writer with
                       quick-wins per F-09 invariant — append-only, do NOT
                       overwrite quick-wins rows)

Drift note: the worker brief refers to a `keyword_data` sheet but the
canonical master-excel schema does NOT define one (`keyword_data` is a
DataForSEO endpoint *category* in dataforseo-endpoint-mapping.schema.json,
not an Excel sheet). This module targets `cluster_keywords` (the closest
schema-locked sheet) and `opportunity`. Manager: confirm before commit.

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same input → same output.

CLI:
  python3 scripts/ingestion/dfs_pull.py \\
      --raw-overview inbox/dfs/2026-05-01-keyword_overview-{slug}.json \\
      [--raw-volume inbox/dfs/2026-05-01-search_volume-{slug}.json] \\
      [--location-code 2792] \\
      [--language-code tr] \\
      [--output-dir _state/transform/{run_id}/]

Stdout: JSON {"cluster_keywords": [...], "opportunity": [...], "meta": {...}}.
With --output-dir set: also writes cluster_keywords.json + opportunity.json
into that directory and prints their absolute paths.

Refs: schemas/master-excel.schema.json (cluster_keywords, opportunity sheets,
definitions block), schemas/dataforseo-endpoint-mapping.schema.json (DFS
endpoint contract; cost.credits_per_call), schemas/events.schema.json
(source.kind=dataforseo_mcp), spec §13 (DFS integration), §16.5 (raw JSON
inbox + transform stage), §16.8 (budget pre-flight).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# scripts/budget is a namespace package (no __init__.py); use importlib path.
# ScriptDir = scripts/ingestion → repo_root = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Soft import — budget pre-flight is REQUIRED at runtime but we want the
# transform module itself to be importable even if the budget script's
# CLI isn't on sys.path during tests. The check is invoked through
# `preflight_budget()` below, which raises BudgetError on failure.
try:  # pragma: no cover — import-time wiring
    from scripts.budget import check_budget as _check_budget_mod  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    _check_budget_mod = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants — schema-aligned column names (master-excel.schema.json)
# ---------------------------------------------------------------------------

# cluster_keywords: A=cluster, B=keyword, C=monthly_volume, D=data_source,
# E=assigned_url, F=gsc_clicks, G=gsc_impressions, H=gsc_position,
# I=intent, J=forbidden_kw, K=forbidden_reason
CLUSTER_KEYWORDS_COLUMNS = (
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

# opportunity (shared with quick-wins): A=query, B=opportunity_score,
# C=current_position, D=ctr_pct, E=impressions_30d, F=clicks_30d,
# G=potential_clicks, H=assigned_url_action
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

# Defaults for Turkey (TR) — per worker brief.
DEFAULT_LOCATION_CODE = 2792   # Turkey
DEFAULT_LANGUAGE_CODE = "tr"

# DataForSEO returns 2840 = United States, "en" = English. The wrapper
# 1835229 fallback bug returns these even when TR is requested.
US_LOCATION_CODE = 2840
US_LANGUAGE_CODE = "en"

# DFS keyword_overview costs ~1 credit per keyword (cluster_keywords seed
# pricing per §13.4); search_volume is ~0.5 credit per keyword (Google Ads
# wrapper). Used by estimated_credits frontmatter math + preflight.
CREDITS_PER_KEYWORD_OVERVIEW = 1.0
CREDITS_PER_KEYWORD_VOLUME = 0.5

# Direct HTTP API base (workaround C — wrapper bypass).
DFS_API_BASE = "https://api.dataforseo.com/v3"
DFS_OVERVIEW_PATH = "/dataforseo_labs/google/keyword_overview/live"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DfsPullError(Exception):
    """Base class for dfs_pull errors."""


class BudgetError(DfsPullError):
    """Budget pre-flight DURUR — DFS calls would exceed the daily cap."""


class TrWorkaroundFailed(DfsPullError):
    """All TR forwarding workaround methods failed — refuse to write US data
    masquerading as TR."""


class CredentialError(DfsPullError):
    """DATAFORSEO_USERNAME / DATAFORSEO_PASSWORD not set or invalid."""


# ---------------------------------------------------------------------------
# Budget pre-flight (uses scripts.budget.check_budget where available)
# ---------------------------------------------------------------------------

def estimate_credits(
    keyword_count: int,
    *,
    use_overview: bool = True,
    use_volume: bool = True,
) -> float:
    """Estimate DataForSEO credits for a dfs-pull run.

    overview: 1 credit per keyword (labs/google/keyword_overview/live).
    volume:   0.5 credit per keyword (keywords_data/google_ads/search_volume).
    """
    if keyword_count <= 0:
        return 0.0
    total = 0.0
    if use_overview:
        total += keyword_count * CREDITS_PER_KEYWORD_OVERVIEW
    if use_volume:
        total += keyword_count * CREDITS_PER_KEYWORD_VOLUME
    return total


def preflight_budget(
    *,
    estimated_credits: float,
    project_config_path: str | os.PathLike[str],
    events_path: str | os.PathLike[str],
) -> dict:
    """Run the §16.8 budget pre-flight and DURUR if exceeded.

    Returns the parsed budget JSON envelope on PASS. Raises BudgetError on
    FAIL (budget exceeded, or estimate alone would push usage past the
    daily cap).

    The check itself is implemented in scripts/budget/check_budget.py;
    we import the module-level helpers (`_load_budget`, `_sum_last_24h`)
    so we don't have to spawn a subprocess. If the helpers are missing
    (test isolation, namespace package edge case) we treat the import
    failure as a DURUR — the brief is explicit that integration is
    real, not theoretical.
    """
    if _check_budget_mod is None:
        raise BudgetError(
            "scripts.budget.check_budget unavailable — pre-flight integration "
            "requires the module to be importable"
        )

    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)

    try:
        budget = _check_budget_mod._load_budget(cfg_path)  # type: ignore[attr-defined]
    except SystemExit as exc:
        raise BudgetError(
            f"budget pre-flight: project-config unreadable ({cfg_path}): exit={exc.code}"
        ) from exc

    from datetime import datetime, timezone
    used = _check_budget_mod._sum_last_24h(evt_path, datetime.now(timezone.utc))  # type: ignore[attr-defined]

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
        raise BudgetError(
            f"budget pre-flight FAIL: projected={projected:.2f} > "
            f"budget={budget} (used_24h={used}, estimate={estimated_credits})"
        )
    return payload


# ---------------------------------------------------------------------------
# TR forwarding workaround
# ---------------------------------------------------------------------------
#
# Live test 1835229 confirmed: dataforseo-mcp-server@2.8.9 returns
# location_code=2840 (US) and language_code="en" even when the caller
# passes location_code=2792 / language_code="tr". This skill implements
# TWO complementary workarounds (B + C) and a final post-fetch heuristic
# filter (A) so no US data leaks into a TR project sheet.
#
#   A (heuristic filter): post-fetch, drop rows whose serp/snippet
#     evidence is overwhelmingly non-TR. Cheap, partial-coverage.
#   B (alt endpoint):     keywords_data_google_ads_search_volume DOES
#     forward location_code/language_code in 2.8.9 (different code path
#     from labs/keyword_overview). Use it as the PRIMARY signal for
#     volume + competition.
#   C (HTTP bypass):      direct POST to api.dataforseo.com with Basic
#     Auth from DATAFORSEO_USERNAME / DATAFORSEO_PASSWORD. Last resort —
#     honours every parameter because we hit the REST surface directly.
#
# All three methods are independent. If A and B and C all fail to
# return a row that demonstrably honors location_code=2792 →
# TrWorkaroundFailed (DURUR — never silently fall back to US data).
#
# This module exposes the HEURISTICS as pure functions; live MCP /
# HTTP calls are orchestrated by the SKILL body (steps map 1:1).


def detect_response_locale(payload: dict) -> tuple[int | None, str | None]:
    """Pull (location_code, language_code) out of a DFS response envelope.

    Walks the canonical DFS response shape:
        { "tasks": [ { "data": { "location_code": ..., "language_code": ... },
                       "result": [ {"location_code": ...} ] } ] }
    Returns (None, None) if unable to determine.
    """
    if not isinstance(payload, dict):
        return None, None
    tasks = payload.get("tasks") or []
    if not tasks or not isinstance(tasks[0], dict):
        return None, None
    task = tasks[0]
    # First check the echoed task.data (what we *requested*); then result[0]
    # (what was *served*) — the latter is the truth.
    served_loc, served_lang = None, None
    result = task.get("result") or []
    if result and isinstance(result[0], dict):
        served_loc = _safe_int(result[0].get("location_code"))
        served_lang = result[0].get("language_code")
    if served_loc is None:
        data = task.get("data") or {}
        served_loc = _safe_int(data.get("location_code"))
    if served_lang is None:
        data = task.get("data") or {}
        served_lang = data.get("language_code")
    if isinstance(served_lang, str):
        served_lang = served_lang.lower()
    return served_loc, served_lang


def response_honors_tr(
    payload: dict,
    *,
    expected_location: int = DEFAULT_LOCATION_CODE,
    expected_language: str = DEFAULT_LANGUAGE_CODE,
) -> bool:
    """Workaround A — pure function. True iff payload's served locale
    matches the requested TR (location_code + language_code).

    The skill calls this on every fetched payload and DURUR-routes to
    workaround B (alt endpoint) or C (HTTP bypass) when False.
    """
    loc, lang = detect_response_locale(payload)
    if loc is None and lang is None:
        # Empty / malformed — treat as not honoring (caller decides).
        return False
    loc_ok = (loc == expected_location)
    lang_ok = (isinstance(lang, str) and lang.lower() == expected_language.lower())
    return loc_ok and lang_ok


def filter_to_tr_heuristic(
    rows: list[dict],
    *,
    tld_hint: str = ".tr",
    language_hint: str = "tr",
) -> list[dict]:
    """Workaround A heuristic — drop rows whose serp/snippet evidence is
    overwhelmingly non-TR. Two cheap signals:
      1. row['language_code'] != 'tr'  → drop
      2. all serp_info top-3 result domains end with non-.tr TLD → drop

    Pure compute, no I/O. Tradeoff: false negatives on global brand TR
    queries (e.g. .com properties ranking in TR). Skill documents this
    in the TR Workaround section.
    """
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        lang = r.get("language_code")
        if isinstance(lang, str) and lang.lower() != language_hint.lower():
            continue
        serp = r.get("serp_info") or {}
        # When serp_info absent we keep the row (no negative evidence).
        if isinstance(serp, dict):
            top = serp.get("top_results") or serp.get("results") or []
            if isinstance(top, list) and top:
                tlds = []
                for t in top[:3]:
                    if isinstance(t, dict):
                        url = t.get("url") or t.get("domain") or ""
                        if isinstance(url, str) and url:
                            tlds.append(url.lower())
                # Only drop when ALL top-3 are non-.tr (overwhelming
                # negative evidence; a single non-.tr is fine).
                if tlds and all(tld_hint not in u for u in tlds):
                    continue
        out.append(r)
    return out


def build_http_payload_tr(
    keywords: list[str],
    *,
    location_code: int = DEFAULT_LOCATION_CODE,
    language_code: str = DEFAULT_LANGUAGE_CODE,
) -> list[dict]:
    """Workaround C — build the JSON body for a direct HTTP POST to
    /v3/dataforseo_labs/google/keyword_overview/live. Wrapper bypass
    guarantees location_code/language_code are honoured.

    Returns the list-of-tasks payload the DFS REST API expects. The
    skill posts it via requests.post(...) with HTTPBasicAuth.
    """
    if not keywords:
        raise ValueError("keywords list must be non-empty")
    return [{
        "keywords": [str(k) for k in keywords],
        "location_code": int(location_code),
        "language_code": str(language_code),
    }]


def http_credentials_from_env() -> tuple[str, str]:
    """Workaround C — fetch HTTPBasicAuth credentials from env vars.

    Reads DATAFORSEO_USERNAME / DATAFORSEO_PASSWORD. Raises
    CredentialError when either is missing or empty (DURUR — the
    skill must not silently degrade).
    """
    user = os.environ.get("DATAFORSEO_USERNAME", "").strip()
    pwd = os.environ.get("DATAFORSEO_PASSWORD", "").strip()
    if not user or not pwd:
        raise CredentialError(
            "DATAFORSEO_USERNAME and DATAFORSEO_PASSWORD must be set "
            "(see .env.example) for the HTTP TR workaround"
        )
    return user, pwd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VolumeRow:
    keyword: str
    monthly_volume: int | None
    competition: str | None
    cpc: float | None


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


def _intent_label(search_intent: Any) -> str:
    """Map a DFS search_intent block to one of master-excel intent enum
    {Informational, Commercial, Transactional, Navigational}.

    DFS shape: {"main_intent": "informational" | ...} or
    {"primary_intent": "commercial"}.
    """
    if not search_intent:
        return "Informational"
    if isinstance(search_intent, dict):
        main = (
            search_intent.get("main_intent")
            or search_intent.get("primary_intent")
            or ""
        )
    else:
        main = str(search_intent)
    norm = str(main).strip().lower()
    mapping = {
        "informational": "Informational",
        "commercial": "Commercial",
        "transactional": "Transactional",
        "navigational": "Navigational",
    }
    return mapping.get(norm, "Informational")


# ---------------------------------------------------------------------------
# Volume loader (optional Google Ads cross-check)
# ---------------------------------------------------------------------------

def load_volume_index(payload: dict) -> dict[str, VolumeRow]:
    """Index a Google Ads search_volume raw JSON by keyword (lowercase).

    Tolerant to both wrapper-shape ({"tasks":[...]}) and direct-result
    ({"items":[...]}) payloads. Empty dict on missing/malformed.
    """
    if not isinstance(payload, dict):
        return {}
    items: list = []
    tasks = payload.get("tasks")
    if isinstance(tasks, list) and tasks:
        for t in tasks:
            if not isinstance(t, dict):
                continue
            for r in (t.get("result") or []):
                if isinstance(r, dict):
                    # Some DFS endpoints place items inline; others under .items.
                    if r.get("keyword") is not None:
                        items.append(r)
                    inner = r.get("items") or []
                    if isinstance(inner, list):
                        items.extend(x for x in inner if isinstance(x, dict))
    if not items:
        items = [x for x in (payload.get("items") or []) if isinstance(x, dict)]

    out: dict[str, VolumeRow] = {}
    for item in items:
        kw = item.get("keyword")
        if not kw:
            continue
        out[str(kw).strip().lower()] = VolumeRow(
            keyword=str(kw),
            monthly_volume=_safe_int(item.get("search_volume")),
            competition=_safe_str(item.get("competition")) or None,
            cpc=_safe_float(item.get("cpc")),
        )
    return out


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def _opportunity_score(volume: int | None, competition: str | None) -> float:
    """Coarse opportunity score for the opportunity sheet.

    Lacking real position data (DFS keyword_overview is a forward-looking
    signal, not a current-rank signal), we proxy:
        score = monthly_volume × competition_factor

    competition_factor:  LOW=1.0, MEDIUM=0.6, HIGH=0.3  (deterministic).
    """
    if volume is None or volume <= 0:
        return 0.0
    factor = 0.6
    if isinstance(competition, str):
        c = competition.strip().upper()
        if c in ("LOW", "1"):
            factor = 1.0
        elif c in ("MEDIUM", "MED", "2"):
            factor = 0.6
        elif c in ("HIGH", "3"):
            factor = 0.3
    return float(volume) * factor


def transform(
    raw_overview: dict,
    *,
    raw_volume: dict | None = None,
    cluster_default: str = "uncategorized",
    location_code: int = DEFAULT_LOCATION_CODE,
    language_code: str = DEFAULT_LANGUAGE_CODE,
    skip_tr_check: bool = False,
) -> dict:
    """Transform a DataForSEO keyword_overview payload + optional Google
    Ads search_volume payload into schema-shaped cluster_keywords +
    opportunity row lists.

    Args:
        raw_overview: parsed JSON payload from
            mcp__dataforseo__dataforseo_labs_google_keyword_overview (live).
            Must carry tasks[0].result[0].items[*] with keyword + keyword_info.
        raw_volume: optional parsed JSON from
            mcp__dataforseo__keywords_data_google_ads_search_volume (live).
            When present, search_volume here OVERRIDES the overview volume
            (workaround B — alt endpoint forwards TR correctly).
        cluster_default: cluster name to assign when overview rows lack one.
        location_code, language_code: TR defaults; transform refuses to
            emit rows when raw_overview returns a different locale unless
            skip_tr_check=True (used by callers who already ran workaround
            A/B/C and know the data is TR-correct).
        skip_tr_check: bypass the response_honors_tr DURUR (caller signed off).

    Returns:
        {"cluster_keywords": [...], "opportunity": [...], "meta": {...}}.

    Raises:
        ValueError: payload shape unparseable.
        TrWorkaroundFailed: response not TR and skip_tr_check=False.
    """
    if not isinstance(raw_overview, dict):
        raise ValueError(f"raw_overview must be a dict, got {type(raw_overview).__name__}")

    if not skip_tr_check:
        if not response_honors_tr(
            raw_overview,
            expected_location=location_code,
            expected_language=language_code,
        ):
            served_loc, served_lang = detect_response_locale(raw_overview)
            raise TrWorkaroundFailed(
                f"raw_overview locale mismatch: requested location_code="
                f"{location_code}/lang={language_code} but response served "
                f"location_code={served_loc}/lang={served_lang}. "
                "Run TR workaround (alt endpoint or HTTP bypass) before transform."
            )

    volume_index: dict[str, VolumeRow] = {}
    if raw_volume is not None:
        volume_index = load_volume_index(raw_volume)

    items: list[dict] = []
    tasks = raw_overview.get("tasks") or []
    if not isinstance(tasks, list):
        raise ValueError("raw_overview['tasks'] must be a list")
    for t in tasks:
        if not isinstance(t, dict):
            continue
        for r in (t.get("result") or []):
            if not isinstance(r, dict):
                continue
            for it in (r.get("items") or []):
                if isinstance(it, dict):
                    items.append(it)

    cluster_rows: list[dict] = []
    opp_rows: list[dict] = []

    for it in items:
        kw = it.get("keyword")
        if not kw:
            continue
        kw = str(kw)
        kw_key = kw.strip().lower()

        ki = it.get("keyword_info") or {}
        # Volume: prefer explicit Google Ads volume (workaround B trust),
        # fall back to keyword_overview's keyword_info.search_volume.
        vrow = volume_index.get(kw_key)
        if vrow is not None and vrow.monthly_volume is not None:
            volume = vrow.monthly_volume
            competition = vrow.competition or _safe_str(ki.get("competition"))
        else:
            volume = _safe_int(ki.get("search_volume"))
            competition = _safe_str(ki.get("competition"))

        intent = _intent_label(it.get("search_intent_info"))
        score = _opportunity_score(volume, competition)

        cluster_rows.append({
            "cluster": cluster_default,
            "keyword": kw,
            "monthly_volume": int(volume) if volume is not None else 0,
            "data_source": "dfs_keyword_overview",
            "assigned_url": "",
            "gsc_clicks": 0,
            "gsc_impressions": 0,
            "gsc_position": 0.0,
            "intent": intent,
            "forbidden_kw": "",
            "forbidden_reason": "",
        })

        opp_rows.append({
            "query": kw,
            "opportunity_score": round(float(score), 2),
            "current_position": 0.0,
            "ctr_pct": 0.0,
            "impressions_30d": 0,
            "clicks_30d": 0,
            "potential_clicks": 0,
            "assigned_url_action": "DFS:keyword_overview seed (no GSC join yet)",
        })

    # Stable sort: deterministic output across runs.
    cluster_rows.sort(key=lambda r: (-int(r["monthly_volume"]), r["keyword"]))
    opp_rows.sort(key=lambda r: (-float(r["opportunity_score"]), r["query"]))

    # Project to the exact schema column tuple (no extra keys).
    cluster_rows = [
        {k: r[k] for k in CLUSTER_KEYWORDS_COLUMNS}
        for r in cluster_rows
    ]
    opp_rows = [
        {k: r[k] for k in OPPORTUNITY_COLUMNS}
        for r in opp_rows
    ]

    return {
        "cluster_keywords": cluster_rows,
        "opportunity": opp_rows,
        "meta": {
            "input_count": len(items),
            "volume_index_size": len(volume_index),
            "cluster_keywords_count": len(cluster_rows),
            "opportunity_count": len(opp_rows),
            "location_code": location_code,
            "language_code": language_code,
            "tr_check_skipped": bool(skip_tr_check),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="dfs_pull.py",
        description="Transform DataForSEO keyword_overview JSON → schema-shaped rows.",
    )
    p.add_argument("--raw-overview", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_keyword_overview JSON.")
    p.add_argument("--raw-volume", default=None,
                   help="Optional path to keywords_data_google_ads_search_volume JSON.")
    p.add_argument("--location-code", type=int, default=DEFAULT_LOCATION_CODE,
                   help=f"Expected location_code (default: {DEFAULT_LOCATION_CODE} = Turkey).")
    p.add_argument("--language-code", default=DEFAULT_LANGUAGE_CODE,
                   help=f"Expected language_code (default: {DEFAULT_LANGUAGE_CODE!r}).")
    p.add_argument("--cluster", default="uncategorized",
                   help="Cluster name to assign to keyword rows (default: 'uncategorized').")
    p.add_argument("--skip-tr-check", action="store_true",
                   help="Bypass TR locale gate (caller has run TR workaround).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write cluster_keywords.json + opportunity.json here.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    raw_path = Path(args.raw_overview)
    if not raw_path.exists():
        print(f"raw overview JSON not found: {raw_path}", file=sys.stderr)
        return 2
    raw_overview = _read_json(raw_path)

    raw_volume: dict | None = None
    if args.raw_volume:
        vol_path = Path(args.raw_volume)
        if vol_path.exists():
            raw_volume = _read_json(vol_path)

    try:
        result = transform(
            raw_overview,
            raw_volume=raw_volume,
            cluster_default=args.cluster,
            location_code=args.location_code,
            language_code=args.language_code,
            skip_tr_check=args.skip_tr_check,
        )
    except (ValueError, TrWorkaroundFailed) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ck_path = out_dir / "cluster_keywords.json"
        op_path = out_dir / "opportunity.json"
        ck_path.write_text(
            json.dumps(result["cluster_keywords"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        op_path.write_text(
            json.dumps(result["opportunity"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "cluster_keywords_path": str(ck_path.resolve()),
            "opportunity_path": str(op_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CLUSTER_KEYWORDS_COLUMNS",
    "OPPORTUNITY_COLUMNS",
    "DEFAULT_LOCATION_CODE",
    "DEFAULT_LANGUAGE_CODE",
    "US_LOCATION_CODE",
    "US_LANGUAGE_CODE",
    "CREDITS_PER_KEYWORD_OVERVIEW",
    "CREDITS_PER_KEYWORD_VOLUME",
    "DfsPullError",
    "BudgetError",
    "TrWorkaroundFailed",
    "CredentialError",
    "estimate_credits",
    "preflight_budget",
    "detect_response_locale",
    "response_honors_tr",
    "filter_to_tr_heuristic",
    "build_http_payload_tr",
    "http_credentials_from_env",
    "load_volume_index",
    "transform",
    "main",
)
