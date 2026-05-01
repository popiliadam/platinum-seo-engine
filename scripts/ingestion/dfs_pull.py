#!/usr/bin/env python3
"""
dfs_pull.py — pure transform: DataForSEO keyword_overview + Google Ads
search_volume raw JSON → staging JSON (raw inventory).

Reads the raw response of mcp__dataforseo__dataforseo_labs_google_keyword_overview
(primary) plus the optional mcp__dataforseo__keywords_data_google_ads_search_volume
fallback / cross-check, normalises units, applies the TR forwarding
workaround (the dataforseo-mcp-server@2.8.9 wrapper does not always
forward location_code/language_code — see SKILL.md TR Workaround), and
emits a staging-table JSON file shaped after scrapling-ops staging
(SQLite-style table dict: schema_version, tool, columns, rows…).

D-003 routing change (Phase 6 staging-only):
  Previous behaviour: transform produced cluster_keywords/opportunity
  rows that the skill orchestrator wrote into master.xlsx via the
  excel transaction helper.
  Current behaviour:  transform writes a staging JSON file at
  _state/staging/dfs_{tool}_{date}_{slug}.json — Phase 8 cluster-map
  skill consumes the staging JSON and projects it into master.xlsx
  downstream. DataForSEO data is "raw inventory" until the cluster-map
  skill assigns clusters / URLs.

  Rationale: scrapling-ops already uses this staging-only pattern.
  Mirroring it keeps cross-skill output discipline consistent and lets
  drift-check/cluster-map iterate on transformations without re-paying
  DataForSEO credits.

Pure function discipline (mirrors gsc_pull.py):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports.
    Events emission belongs to the skill orchestrator layer, not the
    transform.
  - Idempotent: same input → same output (fetched_at is the only
    intentional source of run-to-run drift, and is overwritten on re-run
    so the staging file is byte-stable across re-runs of the same run).

CLI:
  python3 scripts/ingestion/dfs_pull.py \\
      --raw-overview inbox/dfs/2026-05-01-keyword_overview-{slug}.json \\
      [--raw-volume inbox/dfs/2026-05-01-search_volume-{slug}.json] \\
      [--location-code 2792] \\
      [--language-code tr] \\
      [--project-slug {slug}] \\
      [--date 2026-05-01] \\
      [--staging-dir _state/staging/]

  --output-dir is accepted as a backward-compat alias for --staging-dir.

Stdout: JSON summary {"keyword_overview": {...}, "search_volume": {...},
"meta": {...}} naming the staging files written and basic counts.

Refs: schemas/skill-frontmatter.schema.json (frontmatter contract),
schemas/dataforseo-endpoint-mapping.schema.json (DFS endpoint contract;
cost.credits_per_call), schemas/events.schema.json (source.kind=
dataforseo_mcp; staging-only ⇒ target_excel_sheet=null), spec §13 (DFS
integration), §16.5 (raw JSON inbox + transform stage), §16.8 (budget
pre-flight). Pattern reference: scripts/ingestion/scrapling_ops.py
(staging table + content_hash discipline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
# Constants
# ---------------------------------------------------------------------------

# Staging columns — mirror scrapling-ops staging table conventions
# (id + content_hash + fetched_at envelope) plus the DFS payload fields.
KEYWORD_OVERVIEW_COLUMNS: tuple[str, ...] = (
    "id",
    "keyword",
    "search_volume",
    "cpc",
    "competition",
    "competition_level",
    "search_intent",
    "language_code",
    "location_code",
    "content_hash",
    "fetched_at",
)

SEARCH_VOLUME_COLUMNS: tuple[str, ...] = (
    "id",
    "keyword",
    "search_volume",
    "cpc",
    "competition",
    "competition_level",
    "language_code",
    "location_code",
    "content_hash",
    "fetched_at",
)

#: Schema version embedded in the staging table envelope — bump when the
#: staging shape changes. Mirrors scrapling-ops "1.0".
STAGING_SCHEMA_VERSION: str = "1.0"

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


class StagingSchemaError(DfsPullError):
    """Staging table shape drift (id non-monotonic, content_hash missing,
    columns mismatch). DURUR — manager confirms before re-run."""


# ---------------------------------------------------------------------------
# Response shape normaliser (D-003 root-cause fix)
# ---------------------------------------------------------------------------

def _normalize_dfs_response(
    raw: dict,
    expected_endpoint: str | None = None,
) -> list[dict]:
    """
    Tolerate two DataForSEO response shapes that surface in production:

      - REST envelope (upstream / direct HTTP / well-behaved wrappers):
            {"tasks": [{"result": [{"items": [...]}]}]}
      - Flat wrapper (dataforseo-mcp-server@2.8.9 flattening — live test
        2ea8ea1 confirmed for keyword_overview AND search_volume code paths):
            {"items": [...]}

    Both shapes produce a list of item dicts. ``expected_endpoint`` is
    accepted for forward-compat (callers can pass an endpoint label for
    error messages) but is not used for routing — the shape decides.

    Raises:
        ValueError("Unrecognized DFS response shape") when neither shape
        is recognisable. Pure function — no I/O, no state mutation.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            "Unrecognized DFS response shape: top-level must be a dict, "
            f"got {type(raw).__name__}"
        )

    # 1. REST envelope: tasks[0].result[0].items (preferred — closest to
    #    the upstream DataForSEO REST contract).
    tasks = raw.get("tasks")
    if isinstance(tasks, list) and tasks:
        items: list[dict] = []
        saw_result = False
        for task in tasks:
            if not isinstance(task, dict):
                continue
            result = task.get("result")
            if isinstance(result, list):
                saw_result = True
                for r in result:
                    if not isinstance(r, dict):
                        continue
                    inner = r.get("items")
                    if isinstance(inner, list):
                        items.extend(x for x in inner if isinstance(x, dict))
                    # Some DFS endpoints inline keyword fields directly on
                    # result entries (no .items wrapper) — treat them as
                    # items when they carry a keyword key.
                    if r.get("keyword") is not None:
                        items.append(r)
        if saw_result:
            return items
        # tasks[] present but no result[] — fall through to flat check;
        # if that also fails we raise below.

    # 2. Flat wrapper: top-level items list.
    flat_items = raw.get("items")
    if isinstance(flat_items, list):
        return [x for x in flat_items if isinstance(x, dict)]

    # 3. Neither shape recognised.
    suffix = f" (endpoint={expected_endpoint!r})" if expected_endpoint else ""
    raise ValueError(
        f"Unrecognized DFS response shape{suffix}: expected REST envelope "
        f"`tasks[0].result[0].items` or flat wrapper `items`, "
        f"got top-level keys={sorted(raw.keys())}"
    )


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

    Walks both shapes:
      - REST envelope: tasks[0].data + tasks[0].result[0]
      - Flat wrapper:  top-level location_code/language_code
    Returns (None, None) if unable to determine.
    """
    if not isinstance(payload, dict):
        return None, None

    # Flat-wrapper shortcut: locale fields on the top level.
    flat_loc = _safe_int(payload.get("location_code"))
    flat_lang = payload.get("language_code")
    if flat_loc is not None or isinstance(flat_lang, str):
        if isinstance(flat_lang, str):
            flat_lang = flat_lang.lower()
        # Only short-circuit when there is no nested tasks envelope to
        # check — if both shapes carry locale, the nested one wins
        # because it reflects the SERVED locale, not the requested.

    tasks = payload.get("tasks") or []
    if not tasks or not isinstance(tasks[0], dict):
        # Fall back to flat values when there is no envelope.
        return flat_loc, flat_lang

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

    # Prefer envelope-derived values; fall back to flat when missing.
    if served_loc is None and flat_loc is not None:
        served_loc = flat_loc
    if served_lang is None and isinstance(flat_lang, str):
        served_lang = flat_lang
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
    """Map a DFS search_intent block to a Title-Case label
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


def _utc_iso_microseconds() -> str:
    """UTC ISO 8601 with microsecond precision and explicit '+00:00' offset.

    Brief mandate (D-003): fetched_at = ISO 8601 with microsecond precision
    and `+00:00` timezone (NOT 'Z' suffix — the cluster-map skill in Phase
    8 expects offset-aware parsing).
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _row_content_hash(row: Mapping[str, Any], *, exclude: Sequence[str] = ("id", "content_hash")) -> str:
    """sha256:<hex> of sorted-keys JSON of a row's data fields.

    Excludes ``id`` and ``content_hash`` themselves — the hash is over
    the meaning of the row, not its position in the table. Mirrors
    scrapling-ops _content_hash() shape ("sha256:..." prefix) so
    downstream consumers can detect provider in one regex.
    """
    payload = {k: v for k, v in row.items() if k not in exclude}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Item extractors → staging row builders
# ---------------------------------------------------------------------------

def _build_overview_rows(
    items: Sequence[dict],
    *,
    fetched_at: str,
    expected_location: int,
    expected_language: str,
) -> list[dict]:
    """
    Project DataForSEO keyword_overview items into the staging shape.

    Column order is fixed by KEYWORD_OVERVIEW_COLUMNS. Per-row
    content_hash is computed last so it covers every other field.
    """
    rows: list[dict] = []
    next_id = 1
    for it in items:
        kw = it.get("keyword")
        if not kw:
            continue
        ki = it.get("keyword_info") or {}
        # When the item is itself a flat-wrapper item, the volume and
        # competition fields may sit on the item rather than inside
        # keyword_info. Probe both locations.
        volume = _safe_int(ki.get("search_volume"))
        if volume is None:
            volume = _safe_int(it.get("search_volume"))
        cpc = _safe_float(ki.get("cpc"))
        if cpc is None:
            cpc = _safe_float(it.get("cpc"))
        competition = _safe_float(ki.get("competition"))
        if competition is None:
            competition = _safe_float(it.get("competition"))
        comp_level = _safe_str(ki.get("competition_level")) or _safe_str(it.get("competition_level"))
        if not comp_level:
            comp_level_raw = ki.get("competition") or it.get("competition")
            if isinstance(comp_level_raw, str):
                comp_level = comp_level_raw.strip().upper()

        row_lang = _safe_str(it.get("language_code")) or expected_language
        row_loc = _safe_int(it.get("location_code"))
        if row_loc is None:
            row_loc = expected_location

        partial = {
            "id": next_id,
            "keyword": str(kw),
            "search_volume": volume if volume is not None else 0,
            "cpc": cpc if cpc is not None else 0.0,
            "competition": competition if competition is not None else 0.0,
            "competition_level": comp_level,
            "search_intent": _intent_label(it.get("search_intent_info")),
            "language_code": row_lang,
            "location_code": int(row_loc),
            "fetched_at": fetched_at,
        }
        partial["content_hash"] = _row_content_hash(partial)
        # Project to schema-locked column tuple (exact order, no extras).
        rows.append({k: partial[k] for k in KEYWORD_OVERVIEW_COLUMNS})
        next_id += 1
    return rows


def _build_volume_rows(
    items: Sequence[dict],
    *,
    fetched_at: str,
    expected_location: int,
    expected_language: str,
) -> list[dict]:
    """
    Project Google Ads search_volume items into the staging shape.
    """
    rows: list[dict] = []
    next_id = 1
    for it in items:
        kw = it.get("keyword")
        if not kw:
            continue
        volume = _safe_int(it.get("search_volume"))
        cpc = _safe_float(it.get("cpc"))
        competition = _safe_float(it.get("competition"))
        comp_level = _safe_str(it.get("competition_level"))
        if not comp_level:
            comp_level_raw = it.get("competition")
            if isinstance(comp_level_raw, str):
                comp_level = comp_level_raw.strip().upper()
        row_lang = _safe_str(it.get("language_code")) or expected_language
        row_loc = _safe_int(it.get("location_code"))
        if row_loc is None:
            row_loc = expected_location

        partial = {
            "id": next_id,
            "keyword": str(kw),
            "search_volume": volume if volume is not None else 0,
            "cpc": cpc if cpc is not None else 0.0,
            "competition": competition if competition is not None else 0.0,
            "competition_level": comp_level,
            "language_code": row_lang,
            "location_code": int(row_loc),
            "fetched_at": fetched_at,
        }
        partial["content_hash"] = _row_content_hash(partial)
        rows.append({k: partial[k] for k in SEARCH_VOLUME_COLUMNS})
        next_id += 1
    return rows


# ---------------------------------------------------------------------------
# Staging table envelope
# ---------------------------------------------------------------------------

def _staging_table_dict(
    *,
    tool: str,
    project_slug: str,
    fetched_at: str,
    columns: Sequence[str],
    rows: Sequence[dict],
) -> dict:
    """Render rows as a SQLite-shaped JSON dict (mirrors scrapling-ops)."""
    return {
        "schema_version": STAGING_SCHEMA_VERSION,
        "tool": tool,
        "project_slug": project_slug,
        "fetched_at": fetched_at,
        "row_count": len(rows),
        "columns": list(columns),
        "rows": [dict(r) for r in rows],
    }


def _validate_staging_payload(payload: dict, *, columns: Sequence[str]) -> None:
    """Enforce id monotonicity, content_hash presence, columns equality.

    Raises StagingSchemaError on drift — DURUR per SKILL.md.
    """
    rows = payload.get("rows") or []
    if list(payload.get("columns") or []) != list(columns):
        raise StagingSchemaError(
            f"staging columns drift: expected={list(columns)}, "
            f"got={payload.get('columns')}"
        )
    expected_id = 1
    for r in rows:
        if not isinstance(r, dict):
            raise StagingSchemaError(f"row not a dict: {type(r).__name__}")
        if set(r.keys()) != set(columns):
            raise StagingSchemaError(
                f"row column drift: expected={set(columns)}, got={set(r.keys())}"
            )
        if r.get("id") != expected_id:
            raise StagingSchemaError(
                f"id non-monotonic at row {expected_id}: got id={r.get('id')!r}"
            )
        chash = r.get("content_hash")
        if not (isinstance(chash, str) and chash.startswith("sha256:")):
            raise StagingSchemaError(
                f"content_hash missing/invalid at id={expected_id}: {chash!r}"
            )
        expected_id += 1


def _write_staging_json(payload: dict, output_path: Path) -> Path:
    """Atomic-ish write: tmp file + rename. Overwrites on re-run (idempotent
    by design — same input → same staging file)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    return output_path


def staging_filename(
    *,
    tool: str,
    date: str,
    project_slug: str,
) -> str:
    """Canonical filename: dfs_{tool}_{date}_{slug}.json (mirrors
    scrapling_{date}_{slug}.json convention)."""
    return f"dfs_{tool}_{date}_{project_slug}.json"


# ---------------------------------------------------------------------------
# Core transform — staging-only (D-003)
# ---------------------------------------------------------------------------

def transform(
    raw_overview: dict | None,
    *,
    raw_volume: dict | None = None,
    project_slug: str,
    location_code: int = DEFAULT_LOCATION_CODE,
    language_code: str = DEFAULT_LANGUAGE_CODE,
    skip_tr_check: bool = False,
    fetched_at: str | None = None,
) -> dict:
    """
    Transform DFS keyword_overview + optional Google Ads search_volume
    payloads into staging-table dicts (one per tool).

    Args:
        raw_overview: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_keyword_overview (live).
            Tolerates REST envelope OR flat wrapper (D-003 fix).
            None → emit an empty keyword_overview staging table.
        raw_volume: optional parsed JSON from
            mcp__dataforseo__keywords_data_google_ads_search_volume (live).
            None → no search_volume staging emitted.
        project_slug: project slug, embedded in staging table envelope and
            used by callers when building the staging filename.
        location_code, language_code: TR defaults; transform refuses to
            project rows when raw_overview returns a different locale
            unless skip_tr_check=True.
        skip_tr_check: bypass the response_honors_tr DURUR (caller signed
            off after running A/B/C).
        fetched_at: ISO 8601 timestamp; defaults to now (UTC, microseconds).

    Returns:
        {
          "keyword_overview": <staging dict | None>,
          "search_volume":    <staging dict | None>,
          "meta": {...},
        }

    Raises:
        ValueError:           payload shape unparseable (via _normalize_dfs_response).
        TrWorkaroundFailed:   response not TR and skip_tr_check=False.
        StagingSchemaError:   row shape drift (defensive — should not fire
                              for module-built rows).
    """
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise ValueError("project_slug must be a non-empty string")

    ts = fetched_at or _utc_iso_microseconds()

    # --- keyword_overview ---
    overview_payload: dict | None = None
    overview_count = 0
    if raw_overview is not None:
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

        items = _normalize_dfs_response(
            raw_overview, expected_endpoint="dataforseo_labs_google_keyword_overview"
        )
        rows = _build_overview_rows(
            items,
            fetched_at=ts,
            expected_location=location_code,
            expected_language=language_code,
        )
        overview_payload = _staging_table_dict(
            tool="keyword_overview",
            project_slug=project_slug,
            fetched_at=ts,
            columns=KEYWORD_OVERVIEW_COLUMNS,
            rows=rows,
        )
        _validate_staging_payload(overview_payload, columns=KEYWORD_OVERVIEW_COLUMNS)
        overview_count = len(rows)

    # --- search_volume ---
    volume_payload: dict | None = None
    volume_count = 0
    if raw_volume is not None:
        # search_volume from the keywords_data wrapper code path is TR-
        # honouring even in 2.8.9 (per workaround B); we do not gate it
        # on response_honors_tr (and the brief notes the wrapper flattens
        # this endpoint too — the normaliser handles both shapes).
        items = _normalize_dfs_response(
            raw_volume, expected_endpoint="keywords_data_google_ads_search_volume"
        )
        rows = _build_volume_rows(
            items,
            fetched_at=ts,
            expected_location=location_code,
            expected_language=language_code,
        )
        volume_payload = _staging_table_dict(
            tool="search_volume",
            project_slug=project_slug,
            fetched_at=ts,
            columns=SEARCH_VOLUME_COLUMNS,
            rows=rows,
        )
        _validate_staging_payload(volume_payload, columns=SEARCH_VOLUME_COLUMNS)
        volume_count = len(rows)

    return {
        "keyword_overview": overview_payload,
        "search_volume": volume_payload,
        "meta": {
            "project_slug": project_slug,
            "fetched_at": ts,
            "location_code": location_code,
            "language_code": language_code,
            "tr_check_skipped": bool(skip_tr_check),
            "keyword_overview_row_count": overview_count,
            "search_volume_row_count": volume_count,
        },
    }


def write_staging(
    result: Mapping[str, Any],
    *,
    staging_dir: Path,
    project_slug: str,
    date: str,
) -> dict[str, str]:
    """
    Persist the transform() result to disk as one staging JSON per tool.

    Returns a dict mapping tool name → absolute path string. Tools whose
    payload is None are skipped (no file written, no key returned).
    """
    written: dict[str, str] = {}
    staging_dir = Path(staging_dir)

    for tool, columns in (
        ("keyword_overview", KEYWORD_OVERVIEW_COLUMNS),
        ("search_volume", SEARCH_VOLUME_COLUMNS),
    ):
        payload = result.get(tool)
        if not payload:
            continue
        # Defensive re-validation — never write a drifted file.
        _validate_staging_payload(payload, columns=columns)
        out_path = staging_dir / staging_filename(
            tool=tool, date=date, project_slug=project_slug,
        )
        _write_staging_json(payload, out_path)
        written[tool] = str(out_path.resolve())

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="dfs_pull.py",
        description="Transform DataForSEO keyword_overview / search_volume "
                    "JSON → staging JSON (D-003: staging-only, no Excel write).",
    )
    p.add_argument("--raw-overview", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_keyword_overview JSON.")
    p.add_argument("--raw-volume", default=None,
                   help="Optional path to keywords_data_google_ads_search_volume JSON.")
    p.add_argument("--location-code", type=int, default=DEFAULT_LOCATION_CODE,
                   help=f"Expected location_code (default: {DEFAULT_LOCATION_CODE} = Turkey).")
    p.add_argument("--language-code", default=DEFAULT_LANGUAGE_CODE,
                   help=f"Expected language_code (default: {DEFAULT_LANGUAGE_CODE!r}).")
    p.add_argument("--project-slug", default="run",
                   help="Project slug embedded in staging envelope and filename (default: 'run').")
    p.add_argument("--date", default=None,
                   help="ISO date (YYYY-MM-DD) used in the staging filename; defaults to today UTC.")
    p.add_argument("--skip-tr-check", action="store_true",
                   help="Bypass TR locale gate (caller has run TR workaround).")
    # --staging-dir is the canonical name; --output-dir kept for backward
    # compatibility with the old Excel-temp routing.
    p.add_argument("--staging-dir", "--output-dir", default=None, dest="staging_dir",
                   help="Staging output directory; the file is named "
                        "dfs_{tool}_{date}_{slug}.json. "
                        "(--output-dir is accepted as a legacy alias.)")
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
            project_slug=args.project_slug,
            location_code=args.location_code,
            language_code=args.language_code,
            skip_tr_check=args.skip_tr_check,
        )
    except (ValueError, TrWorkaroundFailed, StagingSchemaError) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    summary: dict[str, Any] = {"meta": result["meta"], "staging_paths": {}}
    if args.staging_dir:
        try:
            written = write_staging(
                result,
                staging_dir=Path(args.staging_dir),
                project_slug=args.project_slug,
                date=date_str,
            )
        except StagingSchemaError as exc:
            print(f"staging validation failed: {exc}", file=sys.stderr)
            return 1
        summary["staging_paths"] = written
    else:
        # No --staging-dir: dump the in-memory staging tables to stdout
        # for piping / inspection. NEVER falls through to writing master.xlsx.
        summary["keyword_overview"] = result["keyword_overview"]
        summary["search_volume"] = result["search_volume"]

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "KEYWORD_OVERVIEW_COLUMNS",
    "SEARCH_VOLUME_COLUMNS",
    "STAGING_SCHEMA_VERSION",
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
    "StagingSchemaError",
    "_normalize_dfs_response",
    "estimate_credits",
    "preflight_budget",
    "detect_response_locale",
    "response_honors_tr",
    "filter_to_tr_heuristic",
    "build_http_payload_tr",
    "http_credentials_from_env",
    "transform",
    "write_staging",
    "staging_filename",
    "main",
)
