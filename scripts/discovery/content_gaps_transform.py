#!/usr/bin/env python3
"""
content_gaps_transform.py — pure transform: DataForSEO keyword_ideas +
related_keywords (+ optional content_analysis_search) raw JSON →
staging JSON (candidate inventory for Phase 8 cluster-map / new-content-plan).

Reads raw responses of:
  - mcp__dataforseo__dataforseo_labs_google_keyword_ideas    (REQUIRED)
  - mcp__dataforseo__dataforseo_labs_google_related_keywords (REQUIRED)
  - mcp__dataforseo__content_analysis_search                 (optional)

Tolerates BOTH DFS response shapes via
``scripts.ingestion.dfs_pull._normalize_dfs_response`` (D-003 root-cause
fix — REST envelope ``tasks[0].result[0].items`` AND flat wrapper
``items``). The function is IMPORTED — never copied — so any future shape
fix in dfs_pull is inherited automatically. Same for ``StagingSchemaError``.

Pure function discipline (mirrors dfs_pull.py + cannibalization_transform.py):
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - No master.xlsx writes from this module. No scripts.excel imports.
    Phase 8 cluster-map / new-content-plan skill consumes staging JSON
    and projects to master.xlsx downstream (D-003 staging-only routing).
  - Idempotent: same input → same output. ``fetched_at`` is the only
    intentional source of run-to-run drift, and is overwritten on re-run
    so the staging file is byte-stable across re-runs of the same run.

Output staging files (one per MCP tool present):
  _state/staging/content_gaps_keyword_ideas_{date}_{slug}.json
  _state/staging/content_gaps_related_keywords_{date}_{slug}.json
  _state/staging/content_gaps_content_analysis_search_{date}_{slug}.json

CLI:
  python3 scripts/discovery/content_gaps_transform.py \\
      --raw-keyword-ideas    inbox/dfs/{date}-keyword_ideas-gaps-{slug}.json \\
      --raw-related-keywords inbox/dfs/{date}-related_keywords-gaps-{slug}.json \\
      [--raw-content-analysis-search inbox/dfs/{date}-content_analysis_search-gaps-{slug}.json] \\
      [--seed-keyword "<seed>"] \\
      [--keyword-cap 5000] \\
      [--project-slug {slug}] \\
      [--date 2026-05-01] \\
      [--staging-dir _state/staging/]

Stdout: JSON summary (staging file paths + meta + per-tool row counts).

Refs: schemas/skill-frontmatter.schema.json (frontmatter contract),
schemas/events.schema.json (source.kind=dataforseo_mcp; staging-only ⇒
target_excel_sheet=null), spec §11.6 (DFS keyword discovery), §16.5 (raw
JSON inbox + transform stage), §16.8 (budget pre-flight). Pattern
reference: scripts/ingestion/dfs_pull.py (staging table + content_hash
discipline + _normalize_dfs_response shape adapter).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# scripts/budget + scripts/ingestion are namespace packages; ensure repo
# root on sys.path so absolute imports resolve when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (NOT copy): _normalize_dfs_response + StagingSchemaError
# are owned by scripts.ingestion.dfs_pull. We REUSE them so any shape /
# error-class evolution is inherited automatically — Phase 6 D-003 lesson.
from scripts.ingestion.dfs_pull import (   # noqa: E402  (sys.path mutation above)
    _normalize_dfs_response,
    StagingSchemaError,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Staging columns — mirror dfs_pull staging-table conventions
#: (id + content_hash + fetched_at envelope) plus the gap-specific payload.
CONTENT_GAPS_COLUMNS: tuple[str, ...] = (
    "id",
    "keyword",
    "search_volume",
    "keyword_difficulty",
    "competition",
    "cpc",
    "gap_score",
    "source",
    "seed_keyword",
    "content_hash",
    "fetched_at",
)

#: Schema version embedded in the staging table envelope. Mirrors dfs-pull "1.0".
STAGING_SCHEMA_VERSION: str = "1.0"

#: Source labels — one per MCP tool we project. Used in the row.source field
#: AND in the staging filename (content_gaps_{tool}_{date}_{slug}.json).
SOURCE_KEYWORD_IDEAS: str = "keyword_ideas"
SOURCE_RELATED_KEYWORDS: str = "related_keywords"
SOURCE_CONTENT_ANALYSIS_SEARCH: str = "content_analysis_search"

#: DoS guard — refuse to project more than this many candidates per MCP tool
#: even when the API returns a giant page. Configurable via --keyword-cap.
DEFAULT_KEYWORD_CAP: int = 5000

#: Path to the canonical budget pre-flight script (subprocess wrapper paterni
#: from W-A3/W-A4). Skill-orchestrator invokes this before any paid call.
BUDGET_CHECK_SCRIPT: Path = _REPO_ROOT / "scripts" / "budget" / "check_budget.py"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ContentGapsError(Exception):
    """Base class for content_gaps_transform errors."""


class BudgetExceededError(ContentGapsError):
    """Budget pre-flight DURUR — projected DFS spend exceeds the daily cap."""


class KeywordCapExceededError(ContentGapsError):
    """DoS guard DURUR — MCP returned more candidates than the cap allows."""


class NoCandidatesError(ContentGapsError):
    """Both required MCP responses produced 0 candidate rows. DURUR — the
    skill must surface this rather than silently emit empty staging."""


# Re-export StagingSchemaError so callers can ``except`` it without
# importing dfs_pull directly. The IDENTITY (``is``) is preserved — see
# the import-discipline test.
__all_errors__ = (
    "ContentGapsError",
    "BudgetExceededError",
    "KeywordCapExceededError",
    "NoCandidatesError",
    "StagingSchemaError",
)


# ---------------------------------------------------------------------------
# Helpers — type coercion (mirrors dfs_pull patterns)
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
    """UTC ISO 8601 with microsecond precision and explicit '+00:00' offset.

    Mirrors dfs_pull._utc_iso_microseconds() exactly so cluster-map (Phase 8)
    can parse a single timestamp shape across all DFS-derived staging files.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _row_content_hash(
    row: Mapping[str, Any],
    *,
    exclude: Sequence[str] = ("id", "content_hash"),
) -> str:
    """sha256:<hex> of sorted-keys JSON of a row's data fields.

    Excludes ``id`` and ``content_hash`` themselves — the hash is over the
    meaning of the row, not its position in the table. Mirrors
    scrapling-ops + dfs_pull hash shape ("sha256:..." prefix) so downstream
    consumers can detect the provider in one regex.
    """
    payload = {k: v for k, v in row.items() if k not in exclude}
    blob = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    digest = hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Budget pre-flight (subprocess wrapper paterni — W-A3/W-A4)
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

    Raises BudgetExceededError when the subprocess exits non-zero — that is
    the canonical "budget would be exceeded by this run" signal per
    §16.8 + W-A3/W-A4. Stderr is preserved on the exception for manager
    diagnostics.
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
# Gap score
# ---------------------------------------------------------------------------

def _normalize_competition(comp: Any) -> float:
    """Map a DFS competition signal into [0.0, 1.0].

    Tolerates two shapes that surface in production:
      - numeric ``competition`` / ``competition_index`` (already 0..1, or 0..100)
      - string ``competition_level`` ∈ {LOW, MEDIUM, HIGH}
    """
    # Numeric path.
    num = _safe_float(comp)
    if num is not None:
        # DFS competition_index sometimes lands in 0..100; collapse safely.
        if num > 1.0:
            return max(0.0, min(1.0, num / 100.0))
        return max(0.0, min(1.0, num))
    # String path.
    if isinstance(comp, str):
        token = comp.strip().upper()
        return {"LOW": 0.2, "MEDIUM": 0.55, "HIGH": 0.9}.get(token, 0.5)
    # Unknown → mid-band default (avoid div-by-zero in downstream scoring).
    return 0.5


def gap_score(
    *,
    search_volume: int | float | None,
    keyword_difficulty: int | float | None,
    competition: Any,
) -> float:
    """Heuristic content-gap opportunity score.

    Formula (deterministic, monotonic in volume; inverse in difficulty +
    competition):

        gap_score = (volume / (1 + difficulty)) * (1 - competition_norm)

    where ``competition_norm`` ∈ [0, 1] via ``_normalize_competition``.

    Pluggable: callers may replace this with a custom scorer; the staging
    column stays ``gap_score`` regardless. Result is rounded to 4 decimals
    for staging idempotency (avoids float-format drift between Python
    versions).
    """
    vol = _safe_float(search_volume)
    if vol is None or vol <= 0:
        return 0.0
    diff = _safe_float(keyword_difficulty)
    if diff is None:
        diff = 0.0
    diff = max(0.0, diff)
    comp_norm = _normalize_competition(competition)
    score = (vol / (1.0 + diff)) * (1.0 - comp_norm)
    return round(score, 4)


# ---------------------------------------------------------------------------
# Item extractor — DFS keyword_ideas / related_keywords / content_analysis_search
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Candidate:
    """Internal candidate before staging-row projection."""
    keyword: str
    search_volume: int
    keyword_difficulty: float
    competition: float
    cpc: float
    source: str
    seed_keyword: str


def _extract_candidate(
    item: Mapping[str, Any],
    *,
    source: str,
    seed_keyword: str,
) -> _Candidate | None:
    """Pull a candidate out of a single normalized DFS item dict.

    DFS shapes accommodated:
      - keyword_ideas:    keyword on top, keyword_info.{search_volume, cpc,
                          competition, competition_level}, keyword_properties.
                          {keyword_difficulty}.
      - related_keywords: nested under keyword_data.{keyword,keyword_info,...}
                          OR flat (when wrapper has already flattened).
      - content_analysis_search: ``keyword`` + free-form fields; volume /
                          difficulty often absent — defaults to 0.
    """
    if not isinstance(item, dict):
        return None

    # related_keywords nests the candidate under 'keyword_data'; unwrap once.
    payload = item.get("keyword_data") if isinstance(item.get("keyword_data"), dict) else item

    keyword = payload.get("keyword") or item.get("keyword")
    if not keyword or not isinstance(keyword, str) or not keyword.strip():
        return None

    ki = payload.get("keyword_info") or {}
    if not isinstance(ki, dict):
        ki = {}

    kp = payload.get("keyword_properties") or {}
    if not isinstance(kp, dict):
        kp = {}

    volume = _safe_int(ki.get("search_volume"))
    if volume is None:
        volume = _safe_int(payload.get("search_volume"))
    if volume is None:
        volume = _safe_int(item.get("search_volume"))
    if volume is None:
        volume = 0

    cpc = _safe_float(ki.get("cpc"))
    if cpc is None:
        cpc = _safe_float(payload.get("cpc"))
    if cpc is None:
        cpc = _safe_float(item.get("cpc"))
    if cpc is None:
        cpc = 0.0

    # Competition as float / index / level — keep both numeric and string
    # paths reachable for the gap_score normaliser.
    competition_raw: Any = ki.get("competition")
    if competition_raw is None:
        competition_raw = ki.get("competition_level")
    if competition_raw is None:
        competition_raw = payload.get("competition")
    if competition_raw is None:
        competition_raw = item.get("competition")
    competition_value = _normalize_competition(competition_raw)

    # keyword_difficulty surfaces as 0..100 from labs endpoints; default 0.
    diff = _safe_float(kp.get("keyword_difficulty"))
    if diff is None:
        diff = _safe_float(ki.get("keyword_difficulty"))
    if diff is None:
        diff = _safe_float(payload.get("keyword_difficulty"))
    if diff is None:
        diff = _safe_float(item.get("keyword_difficulty"))
    if diff is None:
        diff = 0.0

    return _Candidate(
        keyword=keyword.strip(),
        search_volume=int(volume),
        keyword_difficulty=float(diff),
        competition=float(competition_value),
        cpc=float(cpc),
        source=source,
        seed_keyword=seed_keyword,
    )


def _build_rows(
    items: Sequence[Mapping[str, Any]],
    *,
    source: str,
    seed_keyword: str,
    fetched_at: str,
) -> list[dict]:
    """Project DFS items into staging rows. Sort by gap_score desc.

    Column order is fixed by ``CONTENT_GAPS_COLUMNS``. Per-row content_hash
    is computed last so it covers every other field.
    """
    candidates: list[tuple[float, _Candidate]] = []
    for it in items:
        cand = _extract_candidate(it, source=source, seed_keyword=seed_keyword)
        if cand is None:
            continue
        score = gap_score(
            search_volume=cand.search_volume,
            keyword_difficulty=cand.keyword_difficulty,
            competition=cand.competition,
        )
        candidates.append((score, cand))

    # Stable sort: gap_score desc, then keyword asc for determinism.
    candidates.sort(key=lambda kv: (-kv[0], kv[1].keyword))

    rows: list[dict] = []
    for next_id, (score, cand) in enumerate(candidates, start=1):
        partial = {
            "id": next_id,
            "keyword": cand.keyword,
            "search_volume": int(cand.search_volume),
            "keyword_difficulty": round(float(cand.keyword_difficulty), 4),
            "competition": round(float(cand.competition), 4),
            "cpc": round(float(cand.cpc), 4),
            "gap_score": float(score),
            "source": cand.source,
            "seed_keyword": cand.seed_keyword,
            "fetched_at": fetched_at,
        }
        partial["content_hash"] = _row_content_hash(partial)
        # Project to schema-locked column tuple (exact order, no extras).
        rows.append({k: partial[k] for k in CONTENT_GAPS_COLUMNS})
    return rows


# ---------------------------------------------------------------------------
# Staging table envelope (mirrors dfs_pull._staging_table_dict)
# ---------------------------------------------------------------------------

def _staging_table_dict(
    *,
    tool: str,
    project_slug: str,
    fetched_at: str,
    seed_keyword: str,
    columns: Sequence[str],
    rows: Sequence[dict],
) -> dict:
    """Render rows as a SQLite-shaped JSON dict (mirrors dfs_pull/scrapling-ops)."""
    return {
        "schema_version": STAGING_SCHEMA_VERSION,
        "tool": tool,
        "project_slug": project_slug,
        "seed_keyword": seed_keyword,
        "fetched_at": fetched_at,
        "row_count": len(rows),
        "columns": list(columns),
        "rows": [dict(r) for r in rows],
    }


def _validate_staging_payload(
    payload: dict,
    *,
    columns: Sequence[str],
) -> None:
    """Enforce id monotonicity, content_hash presence, columns equality.

    Raises ``StagingSchemaError`` (imported from scripts.ingestion.dfs_pull)
    on drift — the same exception class dfs-pull uses, so the cluster-map
    skill catches one type for both ingestion paths.
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
    """Atomic-ish write: tmp file + rename. Overwrites on re-run."""
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
    """Canonical filename: content_gaps_{tool}_{date}_{slug}.json."""
    return f"content_gaps_{tool}_{date}_{project_slug}.json"


# ---------------------------------------------------------------------------
# Core transform — staging-only (D-003)
# ---------------------------------------------------------------------------

def transform(
    *,
    raw_keyword_ideas: dict | None,
    raw_related_keywords: dict | None,
    raw_content_analysis_search: dict | None = None,
    project_slug: str,
    seed_keyword: str,
    keyword_cap: int = DEFAULT_KEYWORD_CAP,
    fetched_at: str | None = None,
) -> dict:
    """
    Transform DFS keyword discovery payloads into staging-table dicts
    (one per MCP tool present).

    Args:
        raw_keyword_ideas: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_keyword_ideas.
            REQUIRED at the skill level, but pass ``None`` here to indicate
            an empty / absent fetch (the meta block will reflect 0 rows).
            Tolerates REST envelope OR flat wrapper (D-003 fix).
        raw_related_keywords: parsed JSON from
            mcp__dataforseo__dataforseo_labs_google_related_keywords.
            REQUIRED at the skill level (same semantics as above).
        raw_content_analysis_search: optional parsed JSON from
            mcp__dataforseo__content_analysis_search.
        project_slug: project slug, embedded in staging table envelope and
            used by callers when building the staging filename.
        seed_keyword: the seed keyword that drove the fetches; embedded in
            every emitted row for traceability (Phase 8 cluster-map joins
            on this).
        keyword_cap: DoS guard; if any tool's normalized item list exceeds
            this count → KeywordCapExceededError.
        fetched_at: ISO 8601 timestamp; defaults to now (UTC, microseconds).

    Returns:
        {
          "keyword_ideas":            <staging dict | None>,
          "related_keywords":         <staging dict | None>,
          "content_analysis_search":  <staging dict | None>,
          "meta": {...},
        }

    Raises:
        ValueError:                 project_slug/seed_keyword empty.
        KeywordCapExceededError:    raw items list exceeds keyword_cap.
        ValueError:                 _normalize_dfs_response shape unparseable
                                    (propagates from dfs_pull).
        StagingSchemaError:         row shape drift (defensive).
        NoCandidatesError:          both required tools produced 0 rows.
    """
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise ValueError("project_slug must be a non-empty string")
    if not isinstance(seed_keyword, str) or not seed_keyword.strip():
        raise ValueError("seed_keyword must be a non-empty string")
    if not isinstance(keyword_cap, int) or keyword_cap <= 0:
        raise ValueError(f"keyword_cap must be a positive int, got {keyword_cap!r}")

    ts = fetched_at or _utc_iso_microseconds()
    seed = seed_keyword.strip()
    slug = project_slug.strip()

    def _project(
        raw: dict | None,
        *,
        source: str,
        endpoint_label: str,
    ) -> tuple[dict | None, int]:
        if raw is None:
            return None, 0
        items = _normalize_dfs_response(raw, expected_endpoint=endpoint_label)
        if len(items) > keyword_cap:
            raise KeywordCapExceededError(
                f"{source}: MCP returned {len(items)} candidates > "
                f"keyword_cap={keyword_cap}; refusing to project (DoS guard)"
            )
        rows = _build_rows(
            items, source=source, seed_keyword=seed, fetched_at=ts,
        )
        payload = _staging_table_dict(
            tool=source,
            project_slug=slug,
            fetched_at=ts,
            seed_keyword=seed,
            columns=CONTENT_GAPS_COLUMNS,
            rows=rows,
        )
        _validate_staging_payload(payload, columns=CONTENT_GAPS_COLUMNS)
        return payload, len(rows)

    ideas_payload, ideas_count = _project(
        raw_keyword_ideas,
        source=SOURCE_KEYWORD_IDEAS,
        endpoint_label="dataforseo_labs_google_keyword_ideas",
    )
    related_payload, related_count = _project(
        raw_related_keywords,
        source=SOURCE_RELATED_KEYWORDS,
        endpoint_label="dataforseo_labs_google_related_keywords",
    )
    cas_payload, cas_count = _project(
        raw_content_analysis_search,
        source=SOURCE_CONTENT_ANALYSIS_SEARCH,
        endpoint_label="content_analysis_search",
    )

    # No-candidate DURUR — both REQUIRED tools produced 0 rows.
    # (Optional content_analysis_search is excluded from this gate.)
    if (
        raw_keyword_ideas is not None
        and raw_related_keywords is not None
        and ideas_count == 0
        and related_count == 0
    ):
        raise NoCandidatesError(
            "both mcp__dataforseo__dataforseo_labs_google_keyword_ideas AND "
            "mcp__dataforseo__dataforseo_labs_google_related_keywords "
            "produced 0 candidate rows for "
            f"seed_keyword={seed!r} (slug={slug!r})"
        )

    return {
        SOURCE_KEYWORD_IDEAS: ideas_payload,
        SOURCE_RELATED_KEYWORDS: related_payload,
        SOURCE_CONTENT_ANALYSIS_SEARCH: cas_payload,
        "meta": {
            "project_slug": slug,
            "seed_keyword": seed,
            "fetched_at": ts,
            "keyword_cap": int(keyword_cap),
            f"{SOURCE_KEYWORD_IDEAS}_row_count": ideas_count,
            f"{SOURCE_RELATED_KEYWORDS}_row_count": related_count,
            f"{SOURCE_CONTENT_ANALYSIS_SEARCH}_row_count": cas_count,
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

    for tool in (
        SOURCE_KEYWORD_IDEAS,
        SOURCE_RELATED_KEYWORDS,
        SOURCE_CONTENT_ANALYSIS_SEARCH,
    ):
        payload = result.get(tool)
        if not payload:
            continue
        # Defensive re-validation — never write a drifted file.
        _validate_staging_payload(payload, columns=CONTENT_GAPS_COLUMNS)
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
        prog="content_gaps_transform.py",
        description=(
            "Transform DataForSEO keyword_ideas / related_keywords / "
            "content_analysis_search JSON → staging JSON (D-003: staging-"
            "only, no Excel write). Phase 8 cluster-map / new-content-plan "
            "skill consumes the staging output."
        ),
    )
    p.add_argument("--raw-keyword-ideas", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_keyword_ideas JSON.")
    p.add_argument("--raw-related-keywords", required=True,
                   help="Path to raw mcp__dataforseo__dataforseo_labs_google_related_keywords JSON.")
    p.add_argument("--raw-content-analysis-search", default=None,
                   help="Optional path to mcp__dataforseo__content_analysis_search JSON.")
    p.add_argument("--seed-keyword", required=True,
                   help="The seed keyword that drove the fetches (embedded in every row).")
    p.add_argument("--keyword-cap", type=int, default=DEFAULT_KEYWORD_CAP,
                   help=f"DoS guard: refuse to project more than N items per tool "
                        f"(default: {DEFAULT_KEYWORD_CAP}).")
    p.add_argument("--project-slug", default="run",
                   help="Project slug embedded in staging envelope and filename "
                        "(default: 'run').")
    p.add_argument("--date", default=None,
                   help="ISO date (YYYY-MM-DD) used in the staging filename; "
                        "defaults to today UTC.")
    p.add_argument("--staging-dir", default=None,
                   help="Staging output directory; the file is named "
                        "content_gaps_{tool}_{date}_{slug}.json.")
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

    raw_cas: dict | None = None
    if args.raw_content_analysis_search:
        cas_path = Path(args.raw_content_analysis_search)
        if cas_path.exists():
            raw_cas = _read_json(cas_path)

    try:
        result = transform(
            raw_keyword_ideas=raw_ideas,
            raw_related_keywords=raw_related,
            raw_content_analysis_search=raw_cas,
            project_slug=args.project_slug,
            seed_keyword=args.seed_keyword,
            keyword_cap=args.keyword_cap,
        )
    except (
        ValueError,
        StagingSchemaError,
        KeywordCapExceededError,
        NoCandidatesError,
    ) as exc:
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
        summary[SOURCE_KEYWORD_IDEAS] = result[SOURCE_KEYWORD_IDEAS]
        summary[SOURCE_RELATED_KEYWORDS] = result[SOURCE_RELATED_KEYWORDS]
        summary[SOURCE_CONTENT_ANALYSIS_SEARCH] = result[SOURCE_CONTENT_ANALYSIS_SEARCH]

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "CONTENT_GAPS_COLUMNS",
    "STAGING_SCHEMA_VERSION",
    "SOURCE_KEYWORD_IDEAS",
    "SOURCE_RELATED_KEYWORDS",
    "SOURCE_CONTENT_ANALYSIS_SEARCH",
    "DEFAULT_KEYWORD_CAP",
    "BUDGET_CHECK_SCRIPT",
    "ContentGapsError",
    "BudgetExceededError",
    "KeywordCapExceededError",
    "NoCandidatesError",
    "StagingSchemaError",          # re-exported from scripts.ingestion.dfs_pull
    "_normalize_dfs_response",     # re-exported (IDENTITY preserved) for callers
    "preflight_budget",
    "gap_score",
    "transform",
    "write_staging",
    "staging_filename",
    "main",
)
