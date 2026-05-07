#!/usr/bin/env python3
"""
internal_links_transform.py — pure transform: Screaming Frog inlinks /
outlinks / internal_all CSV exports → schema-shaped master.xlsx#master_task
auto_generated rows (Option A: SSoT extension; no schema bump).

Reads up to three SF CSVs from `projects/{slug}/sf-exports/{date}/raw/`:
  - internal_all.csv      (URL inventory + status code per URL)
  - all_inlinks.csv       (Source → Destination + Anchor edges)
  - all_outlinks.csv      (per-page outlink targets — optional, not needed
                          for orphan/broken/redirect detection but parsed
                          for completeness when supplied)

The transform aggregates four planning signals per URL:
  1. Orphan pages         — URL present in internal_all with 0 inlinks.
  2. Broken internal links— Inlink edges whose Destination Status Code
                            is 4xx / 5xx (excluding 2xx and intended 3xx
                            chains; chains are bucketed separately).
  3. Redirect chains      — Inlink chains where Destination Status Code
                            is 3xx (stored as a hop, plus aggregated to
                            redirect_chains canonicalName when present).
  4. Anchor distribution  — Per Destination URL, the count of distinct
                            inbound anchor texts (low diversity → flag
                            for over-anchor risk).

Each signal row maps 1:1 to a master_task entry with `auto_generated=true`,
schema-locked to the 19 columns in master-excel.schema.json#master_task.
The `primary_source` column is set to "internal_links" (master_task col C
enum, Phase 8 closeout Q-IL-1 schema bump applied — internal_links is now
an explicit enum member alongside tech_fix/schema/pillar/etc.).

Pure function discipline (mirrors quickwins_transform + cannibalization):
  - No state mutation.
  - No file writes when imported as a module (CLI only).
  - Idempotent: same input → byte-identical output.
  - No D-003 _normalize_dfs_response import — SF CSV path only.
  - Optional DFS path (--use-dfs flag) exposes preflight_budget() but
    the default flow is no-cost.

CLI:
  python3 scripts/planning/internal_links_transform.py \\
      --raw-dir projects/{slug}/sf-exports/{date}/raw/ \\
      [--default-status TODO] \\
      [--max-entries 500] \\
      [--output-dir _state/transform/{run_id}/]

Refs: schemas/master-excel.schema.json (master_task required_columns +
statusEnum + severityEnum + primary_source enum), schemas/events.schema.json
(source.kind=sf_csv, target_excel_sheet=master_task), schemas/sf-export-mapping.schema.json
(canonicalName enum for SF reports), schemas/sf-required-reports.schema.json
(Tier 1 inlinks/outlinks placement), spec §6 (SF ingest discipline) +
§16.5 (raw CSV envelope discipline) + §16.8 (DFS budget pre-flight, opt).
Pattern reference: scripts/discovery/cannibalization_transform.py (URL
normalization D-03 + RowSchemaError discipline) + scripts/discovery/
tech_audit_transform.py (budget pre-flight subprocess wrapper, optional
DFS flag).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
# scripts/budget is a namespace package (no __init__.py); make repo root
# importable so tests + CLI can both reach it.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Canonical D-03 URL normalize (K-01 dedup, v1.5-Phase-1 Tier 1).
from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation above)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)


# ---------------------------------------------------------------------------
# Constants — schema-aligned column tuple
# (master-excel.schema.json#master_task required_columns)
# ---------------------------------------------------------------------------

#: Schema-locked column order for master.xlsx#master_task (19 cols, A..S).
MASTER_TASK_COLUMNS: tuple[str, ...] = (
    "task_id",
    "task",
    "primary_source",
    "related_sources",
    "url",
    "category",
    "priority",
    "impact",
    "duration_est_min",
    "status",
    "created_date",
    "done_date",
    "assignee",
    "note",
    "auto_generated",
    "dependencies",
    "effort_actual_min",
    "metric_impact_json",
    "work_log_ref",
)

#: master_task primary_source enum (master-excel.schema.json#master_task col C).
#: Phase 8 closeout Q-IL-1: schema enum bump 9→10 values (additive, ADR-018
#: pattern, schema_version unchanged) — internal_links is now an explicit
#: enum member; W-C4 Wave 1 used "tech_fix" as substitute pre-bump.
PRIMARY_SOURCE_INTERNAL_LINKS = "internal_links"

#: statusEnum (master-excel.schema.json#/definitions/statusEnum).
STATUS_ENUM = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

#: severityEnum (master-excel.schema.json#/definitions/severityEnum) — used
#: for the `priority` master_task column.
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
SEVERITY_ENUM: tuple[str, ...] = (
    SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
)
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ENUM)}

#: Source-field convention for auto_generated entries: the analysis kind
#: (internal-links + sub-finding) goes into the `note` column as a
#: machine-parseable prefix (`[internal-links/{kind}]`). The schema
#: `primary_source` column carries the enum value (internal_links); the
#: detailed analysis lineage lives in note + metric_impact_json.
NOTE_PREFIX = "[internal-links"
KIND_ORPHAN = "orphan-page"
KIND_BROKEN = "broken-link"
KIND_REDIRECT_CHAIN = "redirect-chain"
KIND_ANCHOR_DIVERSITY = "anchor-diversity"

#: Default cap on emitted entries — DoS / Excel readability protection.
#: Manager review is flagged if a run hits this cap (DURUR #7).
DEFAULT_MAX_ENTRIES = 500

#: Default duration estimates per finding kind (minutes).
DURATION_BY_KIND: Mapping[str, int] = {
    KIND_ORPHAN: 30,
    KIND_BROKEN: 15,
    KIND_REDIRECT_CHAIN: 20,
    KIND_ANCHOR_DIVERSITY: 25,
}

#: Anchor diversity threshold — a destination URL with >= this many
#: distinct anchor texts is healthy; below it (and with significant
#: inbound count) → flag for diversification.
ANCHOR_DIVERSITY_MIN_INBOUND = 5
ANCHOR_DIVERSITY_DISTINCT_THRESHOLD = 2

#: Optional DFS path credit estimate (per URL).
DFS_CREDITS_PER_URL = 3   # on_page_content_parsing per worker brief / spec §11.6

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InternalLinksError(Exception):
    """Base class for internal_links_transform DURUR conditions."""


class SFDataMissingError(InternalLinksError):
    """DURUR #1 — sf-exports/{date}/raw/ directory missing or empty.
    Skill must point user to run sf-import first, NOT silently exit."""


class CSVParseError(InternalLinksError):
    """DURUR #2 — all_inlinks.csv (or peer) header mismatch / encoding bad."""


class RowSchemaError(InternalLinksError):
    """DURUR #4 — emitted master_task row drifts from the 19-col schema."""


class MaxEntriesExceededError(InternalLinksError):
    """DURUR #7 — auto_generated entries > max_entries; manager flag for batching."""


class BudgetExceededError(InternalLinksError):
    """DURUR #6 — optional DFS path budget pre-flight failed."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant — same shape as cannibalization)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into
    :class:`InternalLinksError` so call-site DURUR semantics stay
    backward-compatible after K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise InternalLinksError(str(exc)) from exc


# ---------------------------------------------------------------------------
# SF CSV parsing — header tolerance + safe coerce
# ---------------------------------------------------------------------------

#: Canonical header keys the transform looks for. SF sometimes adds /
#: removes columns across versions; we tolerate header presence-of-set.
_INTERNAL_ALL_HEADERS_REQUIRED = ("Address",)
_INTERNAL_ALL_HEADERS_OPTIONAL = (
    "Status Code", "Status", "Indexability", "Inlinks",
)
_INLINKS_HEADERS_REQUIRED = ("Source", "Destination")
_INLINKS_HEADERS_OPTIONAL = (
    "Status Code", "Anchor", "Type", "Follow", "Link Position",
)


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(round(float(s)))
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _read_csv(
    path: Path,
    *,
    required_headers: Sequence[str],
    label: str,
) -> list[dict]:
    """Parse a SF CSV. Tolerates UTF-8 BOM + CR/LF + missing optional
    columns. Refuses to parse if any required header is absent.

    Raises CSVParseError on header mismatch or encoding failure.
    Empty file (header only, 0 data rows) is OK — returns empty list.
    """
    if not path.is_file():
        raise CSVParseError(f"{label} CSV not found: {path}")

    # SF exports default to UTF-16 with BOM; modern versions write UTF-8.
    # Try UTF-8 first; fall back to UTF-16 with BOM detection.
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-16")
        except UnicodeDecodeError as exc:
            raise CSVParseError(
                f"{label} CSV encoding not UTF-8/UTF-16: {path} ({exc})"
            ) from exc

    # csv.DictReader with sniffed dialect (SF uses comma-delim by default
    # but switches to semicolon under some locales). Sniff the first
    # non-empty line; default to excel dialect if sniff fails.
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    headers = reader.fieldnames or []
    missing = [h for h in required_headers if h not in headers]
    if missing:
        raise CSVParseError(
            f"{label} CSV header mismatch (missing required: {missing}): "
            f"got {headers}"
        )
    return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# SF data containers — frozen, dict-friendly
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SFInternalRow:
    """One row from internal_all.csv (URL inventory)."""

    url: str            # normalized
    status_code: int | None
    indexability: str   # raw SF label, lowercase
    sf_inlinks_count: int | None  # SF's own inlinks counter, when present


@dataclass(frozen=True)
class SFInlinkEdge:
    """One row from all_inlinks.csv (Source → Destination edge)."""

    source: str         # normalized
    destination: str    # normalized
    status_code: int | None
    anchor: str
    link_position: str  # navigation/header/content/footer/sidebar — raw label


@dataclass(frozen=True)
class _Finding:
    """Pre-row finding bundle — kind, url, severity, detail label."""

    kind: str           # KIND_ORPHAN / KIND_BROKEN / KIND_REDIRECT_CHAIN / KIND_ANCHOR_DIVERSITY
    url: str            # primary URL the task targets
    severity: str       # SEVERITY_ENUM value
    label: str          # short human label for `task` column
    note_detail: str    # extra detail for `note` column (post-prefix)
    metric: dict        # diagnostic metrics (-> metric_impact_json)


def _parse_internal_all(rows: Sequence[dict]) -> list[SFInternalRow]:
    """internal_all.csv → list[SFInternalRow]. Skip rows with empty URL."""
    out: list[SFInternalRow] = []
    for raw in rows:
        url_raw = _safe_str(raw.get("Address"))
        if not url_raw:
            continue
        try:
            url_n = normalize_url(url_raw)
        except InternalLinksError:
            continue
        sc = _safe_int(raw.get("Status Code"))
        idx = _safe_str(raw.get("Indexability")).lower()
        sf_inl = _safe_int(raw.get("Inlinks"))
        out.append(SFInternalRow(
            url=url_n,
            status_code=sc,
            indexability=idx,
            sf_inlinks_count=sf_inl,
        ))
    return out


def _parse_inlinks(rows: Sequence[dict]) -> list[SFInlinkEdge]:
    """all_inlinks.csv → list[SFInlinkEdge]. Skip malformed rows."""
    out: list[SFInlinkEdge] = []
    for raw in rows:
        src_raw = _safe_str(raw.get("Source"))
        dst_raw = _safe_str(raw.get("Destination"))
        if not src_raw or not dst_raw:
            continue
        try:
            src_n = normalize_url(src_raw)
            dst_n = normalize_url(dst_raw)
        except InternalLinksError:
            continue
        sc = _safe_int(raw.get("Status Code"))
        anchor = _safe_str(raw.get("Anchor"))
        pos = _safe_str(raw.get("Link Position")).lower()
        out.append(SFInlinkEdge(
            source=src_n,
            destination=dst_n,
            status_code=sc,
            anchor=anchor,
            link_position=pos,
        ))
    return out


# ---------------------------------------------------------------------------
# Detection rules — pure
# ---------------------------------------------------------------------------

def _detect_orphans(
    internal_rows: Sequence[SFInternalRow],
    edges: Sequence[SFInlinkEdge],
) -> list[_Finding]:
    """Orphan: URL in internal_all that appears 0 times as Destination
    in any inlink edge. SF's own `Inlinks` count is preferred when
    populated (column may be missing in older SF exports — fall back to
    edge-based count).

    Self-links (Source == Destination) are NOT counted as inbound.
    Only 200-status URLs are surfaced; 4xx/5xx orphans are uninteresting
    (fix the broken page first, not its discoverability).
    """
    inbound_by_url: dict[str, int] = {}
    for e in edges:
        if e.source == e.destination:
            continue
        inbound_by_url[e.destination] = inbound_by_url.get(e.destination, 0) + 1

    out: list[_Finding] = []
    for r in internal_rows:
        if r.status_code is not None and r.status_code != 200:
            continue
        if r.indexability and "non-indexable" in r.indexability:
            continue
        # Prefer SF's own counter when present; fall back to edges.
        if r.sf_inlinks_count is not None:
            inbound = r.sf_inlinks_count
        else:
            inbound = inbound_by_url.get(r.url, 0)
        if inbound > 0:
            continue
        out.append(_Finding(
            kind=KIND_ORPHAN,
            url=r.url,
            severity=SEVERITY_HIGH,
            label=f"Orphan page (no internal inlinks): {r.url}",
            note_detail="0 internal inbound links; add from topic-related parents",
            metric={
                "inbound_count": 0,
                "status_code": r.status_code,
                "indexability": r.indexability,
            },
        ))
    return out


def _detect_broken_links(edges: Sequence[SFInlinkEdge]) -> list[_Finding]:
    """Broken: edges where Status Code is 4xx or 5xx.

    Rows are aggregated per Destination (one finding per broken target,
    listing how many inbound sources reference it).
    """
    by_dest: dict[str, list[SFInlinkEdge]] = {}
    for e in edges:
        if e.status_code is None:
            continue
        if 400 <= e.status_code < 600:
            by_dest.setdefault(e.destination, []).append(e)

    out: list[_Finding] = []
    for dest, eds in sorted(by_dest.items()):
        sources = sorted({e.source for e in eds})
        sample = sources[:3]
        # Severity by status code class: 5xx > 4xx; 404 specifically is HIGH
        # but 403/401/410 are also covered here.
        sc = eds[0].status_code or 0
        if 500 <= sc < 600:
            sev = SEVERITY_CRITICAL
        elif sc == 404:
            sev = SEVERITY_HIGH
        else:
            sev = SEVERITY_MEDIUM
        out.append(_Finding(
            kind=KIND_BROKEN,
            url=dest,
            severity=sev,
            label=f"Broken internal link → {sc}: {dest}",
            note_detail=(
                f"{len(eds)} inbound edge(s) hit {sc}; "
                f"sample sources: {', '.join(sample)}"
            ),
            metric={
                "destination": dest,
                "status_code": sc,
                "inbound_count": len(eds),
                "source_sample": sample,
            },
        ))
    return out


def _detect_redirect_chains(edges: Sequence[SFInlinkEdge]) -> list[_Finding]:
    """Redirect chain: edges where Status Code is 3xx.

    Same aggregation as broken links — one finding per redirect target,
    listing inbound count + sample sources.
    """
    by_dest: dict[str, list[SFInlinkEdge]] = {}
    for e in edges:
        if e.status_code is None:
            continue
        if 300 <= e.status_code < 400:
            by_dest.setdefault(e.destination, []).append(e)

    out: list[_Finding] = []
    for dest, eds in sorted(by_dest.items()):
        sources = sorted({e.source for e in eds})
        sample = sources[:3]
        sc = eds[0].status_code or 0
        # 301 = permanent (LOW once redirect target is healthy);
        # 302/307 are HIGHER because they signal not-yet-finalized intent.
        if sc in (302, 307):
            sev = SEVERITY_MEDIUM
        else:
            sev = SEVERITY_LOW
        out.append(_Finding(
            kind=KIND_REDIRECT_CHAIN,
            url=dest,
            severity=sev,
            label=f"Internal redirect chain → {sc}: {dest}",
            note_detail=(
                f"{len(eds)} inbound edge(s) hit {sc} (redirect); "
                f"update sources to point at final URL. "
                f"Sample: {', '.join(sample)}"
            ),
            metric={
                "destination": dest,
                "status_code": sc,
                "inbound_count": len(eds),
                "source_sample": sample,
            },
        ))
    return out


def _detect_anchor_diversity(edges: Sequence[SFInlinkEdge]) -> list[_Finding]:
    """Anchor distribution: per-destination, count distinct non-empty
    anchor texts. Destinations with significant inbound count
    (>= ANCHOR_DIVERSITY_MIN_INBOUND) but only 1 distinct anchor are
    flagged for diversification (over-anchoring risk).
    """
    by_dest: dict[str, list[str]] = {}
    for e in edges:
        if e.status_code is not None and not (200 <= e.status_code < 300):
            continue
        anchor = e.anchor.strip().lower()
        if not anchor:
            continue
        by_dest.setdefault(e.destination, []).append(anchor)

    out: list[_Finding] = []
    for dest, anchors in sorted(by_dest.items()):
        if len(anchors) < ANCHOR_DIVERSITY_MIN_INBOUND:
            continue
        distinct = sorted(set(anchors))
        if len(distinct) >= ANCHOR_DIVERSITY_DISTINCT_THRESHOLD:
            continue
        # Only one distinct anchor across many inbound edges → flag.
        out.append(_Finding(
            kind=KIND_ANCHOR_DIVERSITY,
            url=dest,
            severity=SEVERITY_LOW,
            label=f"Low anchor diversity (1 anchor × {len(anchors)} inbounds): {dest}",
            note_detail=(
                f"All {len(anchors)} inbound anchors use the same text "
                f"({distinct[0]!r}); diversify to reduce over-anchor risk"
            ),
            metric={
                "destination": dest,
                "inbound_count": len(anchors),
                "distinct_anchor_count": len(distinct),
                "anchor_sample": distinct[0],
            },
        ))
    return out


# ---------------------------------------------------------------------------
# master_task row build
# ---------------------------------------------------------------------------

def _severity_to_priority(severity: str) -> str:
    """severityEnum value → priority enum value (same severityEnum)."""
    if severity not in SEVERITY_ENUM:
        return SEVERITY_LOW
    return severity


def _build_task_id(slug: str, run_date: str, kind: str, url: str, idx: int) -> str:
    """Deterministic task_id: '{slug}-{date}-IL-{kind}-{idx:03d}'.
    Slug-agnostic — caller passes whatever slug is active."""
    safe_slug = slug.strip().lower() or "project"
    safe_kind = kind.replace("_", "-")
    return f"{safe_slug}-{run_date}-il-{safe_kind}-{idx:03d}"


def _build_master_task_row(
    finding: _Finding,
    *,
    project_slug: str,
    run_date: str,
    idx: int,
    default_status: str,
) -> dict:
    """Convert a _Finding into a schema-shaped master_task row dict."""
    note_kind = (
        f"{NOTE_PREFIX}/{finding.kind}] {finding.note_detail}"
    )
    metric_json = json.dumps(
        {
            "kind": finding.kind,
            "source": "internal-links",
            **finding.metric,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    row = {
        "task_id": _build_task_id(project_slug, run_date, finding.kind, finding.url, idx),
        "task": finding.label,
        "primary_source": PRIMARY_SOURCE_INTERNAL_LINKS,
        "related_sources": "internal-links",
        "url": finding.url,
        "category": "internal-links",
        "priority": _severity_to_priority(finding.severity),
        "impact": finding.severity,
        "duration_est_min": int(DURATION_BY_KIND.get(finding.kind, 20)),
        "status": default_status,
        "created_date": run_date,
        "done_date": "",
        "assignee": "",
        "note": note_kind,
        "auto_generated": True,
        "dependencies": "",
        "effort_actual_min": 0,
        "metric_impact_json": metric_json,
        "work_log_ref": "",
    }
    _validate_row(row)
    return row


def _validate_row(row: dict) -> None:
    """Defensive row validator — column tuple match + enum value checks."""
    if tuple(row.keys()) != MASTER_TASK_COLUMNS:
        raise RowSchemaError(
            f"master_task row column drift: got={tuple(row.keys())}, "
            f"expected={MASTER_TASK_COLUMNS}"
        )
    if row["primary_source"] != PRIMARY_SOURCE_INTERNAL_LINKS:
        raise RowSchemaError(
            f"primary_source must be {PRIMARY_SOURCE_INTERNAL_LINKS!r}, "
            f"got {row['primary_source']!r}"
        )
    if row["status"] not in STATUS_ENUM:
        raise RowSchemaError(
            f"status not in statusEnum: {row['status']!r}"
        )
    if row["priority"] not in SEVERITY_ENUM:
        raise RowSchemaError(
            f"priority not in severityEnum: {row['priority']!r}"
        )
    if row["impact"] not in SEVERITY_ENUM:
        raise RowSchemaError(
            f"impact not in severityEnum: {row['impact']!r}"
        )
    if not isinstance(row["auto_generated"], bool) or row["auto_generated"] is not True:
        raise RowSchemaError(
            f"auto_generated must be True boolean, got {row['auto_generated']!r}"
        )
    if not isinstance(row["duration_est_min"], int):
        raise RowSchemaError(
            f"duration_est_min must be int, got {type(row['duration_est_min']).__name__}"
        )
    if not isinstance(row["effort_actual_min"], int):
        raise RowSchemaError(
            f"effort_actual_min must be int, got {type(row['effort_actual_min']).__name__}"
        )


# ---------------------------------------------------------------------------
# Optional DFS budget pre-flight (subprocess wrapper, mirror tech_audit)
# ---------------------------------------------------------------------------

def estimate_credits(url_count: int, *, use_dfs: bool = False) -> int:
    """Conservative DFS credit estimate when --use-dfs is requested.
    Default flow uses 0 credits (no paid MCP)."""
    if not use_dfs or url_count <= 0:
        return 0
    return url_count * DFS_CREDITS_PER_URL


def preflight_budget(
    *,
    estimated_credits: int,
    project_config_path: str | Path,
    events_path: str | Path,
    check_budget_script: str | Path | None = None,
) -> dict:
    """Run §16.8 budget pre-flight and DURUR if exceeded.

    Subprocess-based: invokes scripts/budget/check_budget.py and parses
    its stdout JSON envelope. Forward-looking: fails when
    `actual + estimate > budget`. Mirrors tech_audit_transform.preflight_budget
    so the skill layer can route awaiting_approval per ADR-016 / spec §10.
    """
    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)
    script = (
        Path(check_budget_script) if check_budget_script
        else _REPO_ROOT / "scripts" / "budget" / "check_budget.py"
    )
    if not script.exists():
        raise BudgetExceededError(f"budget pre-flight script missing: {script}")

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
# Core transform
# ---------------------------------------------------------------------------

def transform(
    *,
    internal_all_rows: Sequence[dict] | None,
    inlinks_rows: Sequence[dict] | None,
    project_slug: str,
    run_date: str,
    default_status: str = "TODO",
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> dict:
    """Pure transform: parsed SF CSV row dicts → master_task auto_generated rows.

    Args:
        internal_all_rows: list-of-dicts shape from internal_all.csv (DictReader).
            None → orphan detection skipped (transform tolerates partial input).
        inlinks_rows: list-of-dicts shape from all_inlinks.csv (DictReader).
            None → broken/redirect/anchor detection skipped.
        project_slug: required for task_id construction; no defaulting.
        run_date: ISO date string (YYYY-MM-DD) — created_date column.
        default_status: statusEnum seed for the status column.
        max_entries: hard cap on emitted rows (DURUR #7 vehicle).

    Returns:
        {
          "master_task": [<row>, ...],   # schema-shaped, sorted
          "meta": {
             "internal_url_count": int,
             "inlink_edge_count": int,
             "orphan_count": int,
             "broken_count": int,
             "redirect_chain_count": int,
             "anchor_diversity_count": int,
             "row_count": int,
             "max_entries": int,
             "default_status": str,
             "run_date": str,
             "project_slug": str,
          },
        }

    Raises:
        InternalLinksError    — bad project_slug / run_date / default_status.
        RowSchemaError        — emitted row drift (defensive).
        MaxEntriesExceededError — DURUR #7 (>max_entries).
    """
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise InternalLinksError(
            f"project_slug must be a non-empty string, got {project_slug!r}"
        )
    if not isinstance(run_date, str) or not run_date.strip():
        raise InternalLinksError(
            f"run_date must be a non-empty ISO date string, got {run_date!r}"
        )
    # Validate run_date is parseable as YYYY-MM-DD.
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError as exc:
        raise InternalLinksError(
            f"run_date must be YYYY-MM-DD, got {run_date!r}: {exc}"
        ) from exc
    if default_status not in STATUS_ENUM:
        raise InternalLinksError(
            f"default_status must be in statusEnum, got {default_status!r}"
        )
    if not isinstance(max_entries, int) or max_entries < 1:
        raise InternalLinksError(
            f"max_entries must be a positive int, got {max_entries!r}"
        )

    internal: list[SFInternalRow] = (
        _parse_internal_all(internal_all_rows) if internal_all_rows else []
    )
    edges: list[SFInlinkEdge] = (
        _parse_inlinks(inlinks_rows) if inlinks_rows else []
    )

    # Run detectors. Orphan detection requires internal_all; broken /
    # redirect / anchor detectors run off inlinks (edges) alone.
    orphans = _detect_orphans(internal, edges) if internal else []
    broken = _detect_broken_links(edges)
    chains = _detect_redirect_chains(edges)
    anchors = _detect_anchor_diversity(edges)

    findings: list[_Finding] = [*orphans, *broken, *chains, *anchors]

    # Sort findings by (severity rank asc, kind, url) for determinism.
    findings.sort(key=lambda f: (
        _SEVERITY_RANK.get(f.severity, 99),
        f.kind,
        f.url,
    ))

    if len(findings) > max_entries:
        raise MaxEntriesExceededError(
            f"emitted {len(findings)} entries exceeds max_entries={max_entries}; "
            "split run by sub-folder or batch by kind. "
            "(Phase 8 Wave 1: surface to manager for batching review.)"
        )

    rows: list[dict] = []
    for idx, f in enumerate(findings, start=1):
        rows.append(_build_master_task_row(
            f,
            project_slug=project_slug,
            run_date=run_date,
            idx=idx,
            default_status=default_status,
        ))

    # D-03 idempotency self-check — every URL on every emitted row must
    # round-trip through normalize_url unchanged.
    for r in rows:
        u = r["url"]
        if normalize_url(u) != u:
            raise RowSchemaError(
                f"URL normalization drift on emitted row: {u!r} not idempotent; "
                "D-03 invariant broken"
            )

    return {
        "master_task": rows,
        "meta": {
            "internal_url_count": len(internal),
            "inlink_edge_count": len(edges),
            "orphan_count": len(orphans),
            "broken_count": len(broken),
            "redirect_chain_count": len(chains),
            "anchor_diversity_count": len(anchors),
            "row_count": len(rows),
            "max_entries": int(max_entries),
            "default_status": default_status,
            "run_date": run_date,
            "project_slug": project_slug,
        },
    }


# ---------------------------------------------------------------------------
# Disk I/O — read SF CSVs from a raw_dir
# ---------------------------------------------------------------------------

def load_sf_csvs(
    raw_dir: str | Path,
) -> tuple[list[dict] | None, list[dict] | None, list[dict] | None]:
    """Load (internal_all, all_inlinks, all_outlinks) row lists from a
    raw_dir. Missing files return None. Missing raw_dir or no SF CSVs at
    all → SFDataMissingError.
    """
    rd = Path(raw_dir)
    if not rd.is_dir():
        raise SFDataMissingError(
            f"sf-exports raw_dir not found: {rd}. "
            "Run sf-import skill first to populate "
            "projects/{slug}/sf-exports/{date}/raw/."
        )

    found_any = False
    internal_path = rd / "internal_all.csv"
    inlinks_path = rd / "all_inlinks.csv"
    outlinks_path = rd / "all_outlinks.csv"

    internal_rows: list[dict] | None = None
    if internal_path.is_file():
        internal_rows = _read_csv(
            internal_path,
            required_headers=_INTERNAL_ALL_HEADERS_REQUIRED,
            label="internal_all",
        )
        found_any = True

    inlinks_rows: list[dict] | None = None
    if inlinks_path.is_file():
        inlinks_rows = _read_csv(
            inlinks_path,
            required_headers=_INLINKS_HEADERS_REQUIRED,
            label="all_inlinks",
        )
        found_any = True

    outlinks_rows: list[dict] | None = None
    if outlinks_path.is_file():
        outlinks_rows = _read_csv(
            outlinks_path,
            required_headers=_INLINKS_HEADERS_REQUIRED,
            label="all_outlinks",
        )
        found_any = True

    if not found_any:
        raise SFDataMissingError(
            f"no SF CSVs found in {rd} "
            "(expected at least one of: internal_all.csv, all_inlinks.csv, "
            "all_outlinks.csv). Run sf-import first."
        )

    return internal_rows, inlinks_rows, outlinks_rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="internal_links_transform.py",
        description=(
            "Transform SF inlinks/outlinks/internal_all CSVs → "
            "master.xlsx#master_task auto_generated rows (Option A)."
        ),
    )
    p.add_argument("--raw-dir", required=True,
                   help="Path to projects/{slug}/sf-exports/{date}/raw/.")
    p.add_argument("--project-slug", required=True,
                   help="Active project slug — feeds task_id + meta.")
    p.add_argument("--run-date", default=None,
                   help="ISO date YYYY-MM-DD (default: today, UTC).")
    p.add_argument("--default-status", default="TODO",
                   help="statusEnum seed value (default: TODO).")
    p.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES,
                   help=f"DURUR #7 cap (default: {DEFAULT_MAX_ENTRIES}).")
    p.add_argument("--use-dfs", action="store_true",
                   help="Optional: enrich via DFS on_page_content_parsing "
                        "(triggers budget pre-flight, paid MCP).")
    p.add_argument("--project-config", default=None,
                   help="Path to project.config.json (required when --use-dfs).")
    p.add_argument("--events", default=None,
                   help="Path to events.jsonl (required when --use-dfs).")
    p.add_argument("--output-dir", default=None,
                   help="If set, writes master_task.json into this directory.")
    return p.parse_args(list(argv))


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    raw_dir = Path(args.raw_dir)
    run_date = args.run_date or _date.today().isoformat()

    try:
        internal_rows, inlinks_rows, _outlinks = load_sf_csvs(raw_dir)
    except (SFDataMissingError, CSVParseError) as exc:
        print(f"sf data load failed: {exc}", file=sys.stderr)
        return 2

    # Optional DFS path — pre-flight only; the actual MCP call runs in the
    # skill layer (transform stays pure).
    if args.use_dfs:
        if not args.project_config or not args.events:
            print(
                "--use-dfs requires --project-config and --events paths",
                file=sys.stderr,
            )
            return 2
        url_count = (
            sum(1 for r in (internal_rows or []) if r.get("Address"))
        )
        estimate = estimate_credits(url_count, use_dfs=True)
        try:
            preflight_budget(
                estimated_credits=estimate,
                project_config_path=args.project_config,
                events_path=args.events,
            )
        except BudgetExceededError as exc:
            print(f"budget pre-flight FAIL: {exc}", file=sys.stderr)
            return 1

    try:
        result = transform(
            internal_all_rows=internal_rows,
            inlinks_rows=inlinks_rows,
            project_slug=args.project_slug,
            run_date=run_date,
            default_status=args.default_status,
            max_entries=args.max_entries,
        )
    except (
        InternalLinksError,
        RowSchemaError,
        MaxEntriesExceededError,
    ) as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "master_task.json"
        out_path.write_text(
            json.dumps(result["master_task"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "master_task_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "MASTER_TASK_COLUMNS",
    "PRIMARY_SOURCE_INTERNAL_LINKS",
    "STATUS_ENUM",
    "SEVERITY_ENUM",
    "SEVERITY_CRITICAL",
    "SEVERITY_HIGH",
    "SEVERITY_MEDIUM",
    "SEVERITY_LOW",
    "DURATION_BY_KIND",
    "DEFAULT_MAX_ENTRIES",
    "DFS_CREDITS_PER_URL",
    "KIND_ORPHAN",
    "KIND_BROKEN",
    "KIND_REDIRECT_CHAIN",
    "KIND_ANCHOR_DIVERSITY",
    "NOTE_PREFIX",
    "InternalLinksError",
    "SFDataMissingError",
    "CSVParseError",
    "RowSchemaError",
    "MaxEntriesExceededError",
    "BudgetExceededError",
    "SFInternalRow",
    "SFInlinkEdge",
    "normalize_url",
    "load_sf_csvs",
    "estimate_credits",
    "preflight_budget",
    "transform",
    "main",
)
