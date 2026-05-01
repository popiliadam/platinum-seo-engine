#!/usr/bin/env python3
"""
master_task_sync.py — pure aggregator: Phase 7 + Phase 8 Wave 1 master
writer sheets → schema-shaped master.xlsx#master_task auto_generated rows
(local aggregation, NO MCP, NO DFS, NO budget pre-flight).

This is the Phase 8 Wave 2 "task SSoT collector". Eight upstream sheets
already live in `master.xlsx` (one per skill that produced auto_generated
findings); this module reads each one, derives a deterministic `task_id`
per source row, and emits new master_task rows OR merges the
`related_sources` (D) column on existing rows.

Per master-excel.schema.json#master_task allowed_writers (line 293), the
writer name `master_task_sync` is whitelisted; per writer_scope (line 298)
this writer is restricted to:

    "append new auto-generated rows AND merge related_sources (D);
     forbidden to touch protected_columns"

protected_columns (schema line 300) are 7 cols [B, F, G, H, I, M, N]:
[task, category, priority, impact, duration_est_min, assignee, note].
This module raises a `ProtectedColumnsWriteAttempt` DURUR if a payload
ever tries to populate any of those.

Sources consumed (8 sheets):
  Phase 7 master writers (5):
    - cannibalization      → primary_source="cannibalization"
    - content_decay        → primary_source="content_decay"
    - tech_seo             → primary_source="tech_fix"
    - on_page_audit        → primary_source per row (tech_fix / schema /
                             manual; chosen via issue_category heuristic)
    - schema (sheet)       → primary_source="schema"
  Phase 8 Wave 1 master writers (3):
    - cluster_keywords     → primary_source="pillar"
    - topical_map          → primary_source="pillar"
    - new_content_plan     → primary_source="pillar"

W-C4 internal-links pre-existing master_task entries (Q-IL-1 substitute:
they live as primary_source="tech_fix" rows already; this aggregator
reads them through master_task itself and merges D-only when re-encountered
via signature collision — which is rare since they have distinct
task_id heuristics; documented invariant).

Idempotency contract:
  Re-run with identical Phase 7+8 sheet state → identical master_task
  state. Re-run after new sheet rows → APPEND for new task_ids and
  D-only MERGE for existing task_ids (auto_generated=true). Manuel
  entries (auto_generated=false) are NEVER touched.

  task_id = sha256("{primary_source}|{url}|{task_signature}")[:16]

  task_signature is per-source (see SOURCE_DEFS below): for cluster_keywords
  it is "{cluster}|{keyword}"; for tech_seo it is "{issue_category}";
  for content_decay it is "decay" (URL is the discriminator) — and so
  on. This file documents the per-source heuristic in one place.

Pure function discipline (mirrors other Phase 7/8 transforms):
  - No state mutation outside explicit return values.
  - No file writes when imported as a module (CLI only).
  - Idempotent: same input → byte-identical output.
  - No D-003 _normalize_dfs_response import — local aggregation, no DFS
    payload is consumed (intentionally absent — this is local SSoT scope).
  - 0 hardcoded slug values (plugin agnostik).

Refs: schemas/master-excel.schema.json#master_task (lines 269-303 —
required_columns + allowed_writers + writer_scope + protected_columns),
schemas/events.schema.json (source.kind=local_aggregation,
target_excel_sheet=master_task), spec §8.5 (master_task SSoT discipline),
ADR-018 (per-row jsonschema), ADR-021 (state run shape).
Pattern reference: scripts/planning/internal_links_transform.py (Phase 8
W-C4 master_task writer pattern), scripts/discovery/quickwins_transform.py
(Phase 5 W-P pure transform shape).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


# scripts/budget is a namespace package (no __init__.py); make repo root
# importable so tests + CLI can both reach it. (No DFS dependency, but
# keeping the same path bootstrap as sibling transforms.)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Constants — schema-aligned column tuple
# (master-excel.schema.json#master_task required_columns, lines 272-291)
# ---------------------------------------------------------------------------

#: Schema-locked column order for master.xlsx#master_task (19 cols, A..S).
MASTER_TASK_COLUMNS: tuple[str, ...] = (
    "task_id",            # A
    "task",               # B  PROTECTED
    "primary_source",     # C  enum
    "related_sources",    # D  mergeable (W-D1 writer scope)
    "url",                # E
    "category",           # F  PROTECTED
    "priority",           # G  PROTECTED (severityEnum)
    "impact",             # H  PROTECTED
    "duration_est_min",   # I  PROTECTED (integer)
    "status",             # J  statusEnum
    "created_date",       # K  date
    "done_date",          # L  date (done_protocol scope)
    "assignee",           # M  PROTECTED
    "note",               # N  PROTECTED
    "auto_generated",     # O  boolean
    "dependencies",       # P
    "effort_actual_min",  # Q  integer
    "metric_impact_json", # R
    "work_log_ref",       # S
)

#: Protected columns (schema line 300). The master_task_sync writer is
#: FORBIDDEN to write to these. Defensive guard `_ensure_no_protected_writes`
#: enforces this at row-build time, BEFORE any disk I/O.
PROTECTED_COLUMNS: frozenset[str] = frozenset({
    "task",
    "category",
    "priority",
    "impact",
    "duration_est_min",
    "assignee",
    "note",
})

#: master_task primary_source enum (schema line 275). Phase 8 closeout
#: Q-IL-1: schema bump 9→10 values (additive, ADR-018 pattern,
#: schema_version unchanged) — internal_links is now an explicit enum
#: member; W-C4 transform refactored to emit "internal_links" directly.
PRIMARY_SOURCE_ENUM: frozenset[str] = frozenset({
    "content_decay",
    "quickwin",
    "tech_fix",
    "schema",
    "pillar",
    "manual",
    "sxo",
    "cannibalization",
    "redirect_404",
    "internal_links",
})

#: statusEnum (master-excel.schema.json#/definitions/statusEnum).
STATUS_ENUM: frozenset[str] = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

#: Allowed writer name for this module (schema line 293).
WRITER_NAME = "master_task_sync"

#: Schema scope semantic (schema line 298). Verbatim — referenced by
#: the docstring + DURUR error messages.
WRITER_SCOPE_SEMANTIC = (
    "append new auto-generated rows AND merge related_sources (D); "
    "forbidden to touch protected_columns"
)

#: task_id sha256 prefix length. >= 8 hex per worker brief; 16 hex
#: gives 64-bit collision space (2^64 ~ 1.8e19) which is comfortable for
#: the row volumes this skill aggregates (typical run < 5000 rows).
TASK_ID_PREFIX_LEN = 16

#: related_sources separator — use pipe "|" to align with internal-links
#: convention and avoid CSV/Excel quoting issues. Sorted on rejoin so
#: re-runs are byte-stable.
RELATED_SOURCES_SEP = "|"

#: Per-source default duration estimate (minutes) — used ONLY when an
#: upstream sheet has no duration cue. For most rows this comes through
#: protected_columns territory, so we leave duration_est_min blank
#: ("") for new rows and let manuel/done_protocol populate it. (Schema
#: line 281 marks it as integer, but blank-string is tolerated by the
#: write layer when paired with auto_generated=true and protected_columns
#: blank-init.)
DURATION_EST_BLANK = ""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MasterTaskSyncError(Exception):
    """Base class for master_task_sync DURUR conditions."""


class SheetMissingError(MasterTaskSyncError):
    """DURUR #1 — one of the 8 expected upstream sheets is absent.
    User must run the prior skill (e.g. cannibalization, cluster-map)
    that produces the missing sheet before re-running master-task-sync."""


class ColumnTupleDriftError(MasterTaskSyncError):
    """DURUR #2 — emitted master_task row column tuple drifts from the
    schema 19-col tuple (defensive guard before any write attempt)."""


class TaskIdCollisionError(MasterTaskSyncError):
    """DURUR #3 — sha256[:N] prefix produced the same task_id for
    distinct (primary_source, url, signature) inputs. Bump
    TASK_ID_PREFIX_LEN and rebuild deterministically; raise if persistent."""


class IdempotencyDriftError(MasterTaskSyncError):
    """DURUR #4 — second run produced different state from first (smoke
    test guard). Indicates non-deterministic input ordering or a hidden
    mutable side-effect; aggregator MUST be byte-stable."""


class PrimarySourceEnumViolation(MasterTaskSyncError):
    """DURUR #5 — aggregator emitted a primary_source value not in the
    closed schema enum (master-excel.schema.json#master_task col C)."""


class ProtectedColumnsWriteAttempt(MasterTaskSyncError):
    """DURUR #6 — payload row tries to populate a protected_columns
    field (B/F/G/H/I/M/N). Schema-first violation per writer_scope."""


class WriterScopeViolation(MasterTaskSyncError):
    """DURUR #7 — merge attempt on a column other than D (related_sources).
    Per writer_scope: only D is mergeable for master_task_sync."""


class WorkflowRunnerSchemaError(MasterTaskSyncError):
    """DURUR #8 — workflow_runner.create_run schema validation failed
    (state init drift)."""


class WorkspaceRootUnsetError(MasterTaskSyncError):
    """DURUR #9 — PSEO_WORKSPACE_ROOT env var unset and no explicit
    workspace_root passed; cannot resolve projects/{slug}/."""


# ---------------------------------------------------------------------------
# Source definitions — declarative, one entry per upstream sheet.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceDef:
    """Declarative description of one upstream master writer sheet.

    Attributes:
        sheet:            master.xlsx logical sheet name.
        primary_source:   schema enum value to set on emitted rows.
                          (callable form for on_page_audit which routes
                          to one of three values per issue_category).
        url_col:          column name in upstream sheet that carries the URL.
                          None means the sheet has no URL column and
                          signature_cols carry full discriminator.
        signature_cols:   tuple of upstream column names that, joined,
                          form the per-row task_signature (idempotency key).
        related_source_key: short label for the D column. e.g. "tech_seo".
                          Sorted lexicographically on merge so output is
                          byte-stable.
        skill_name:       producing skill (consumes path; doc only).
    """

    sheet: str
    primary_source: Any  # str | Callable[[Mapping[str,Any]], str]
    url_col: str | None
    signature_cols: tuple[str, ...]
    related_source_key: str
    skill_name: str

    def derive_primary_source(self, row: Mapping[str, Any]) -> str:
        """Resolve primary_source for one upstream row.

        For the simple sheets (cannibalization, content_decay, ...) the
        primary_source is a literal string. For on_page_audit it routes
        per row via the issue_category column.
        """
        if callable(self.primary_source):
            return self.primary_source(row)
        return str(self.primary_source)


def _on_page_audit_primary_source(row: Mapping[str, Any]) -> str:
    """on_page_audit issue_category enum → master_task primary_source enum.

    issue_category enum (schema line ~204):
      Performance      → tech_fix
      Layout Stability → tech_fix
      Meta Tags        → tech_fix
      Structured Data  → schema
      Accessibility    → manual
    """
    issue = (row.get("issue_category") or "").strip()
    if issue == "Structured Data":
        return "schema"
    if issue == "Accessibility":
        return "manual"
    # Default: any tech-style issue (Performance / Layout Stability /
    # Meta Tags / unknown) → tech_fix.
    return "tech_fix"


#: The 8 upstream master writer sheets aggregated by master-task-sync.
#: Order is fixed for determinism — re-run produces the same row order.
SOURCE_DEFS: tuple[SourceDef, ...] = (
    # Phase 7 — discovery + audit master writers (5)
    SourceDef(
        sheet="cannibalization",
        primary_source="cannibalization",
        url_col=None,                       # conflict_pair carries URLs
        signature_cols=("conflict_pair",),
        related_source_key="cannibalization",
        skill_name="cannibalization",
    ),
    SourceDef(
        sheet="content_decay",
        primary_source="content_decay",
        url_col="url",
        signature_cols=("url",),            # url is the discriminator
        related_source_key="content_decay",
        skill_name="content-decay",
    ),
    SourceDef(
        sheet="tech_seo",
        primary_source="tech_fix",
        url_col=None,                       # affected_urls is multi-URL
        signature_cols=("issue_category", "detail"),
        related_source_key="tech_seo",
        skill_name="tech-audit",
    ),
    SourceDef(
        sheet="on_page_audit",
        primary_source=_on_page_audit_primary_source,
        url_col="url",
        signature_cols=("url", "target_query"),
        related_source_key="on_page_audit",
        skill_name="on-page-audit",
    ),
    SourceDef(
        sheet="schema",
        primary_source="schema",
        url_col=None,
        signature_cols=("schema_type", "location"),
        related_source_key="schema",
        skill_name="schema-audit",
    ),
    # Phase 8 Wave 1 — planning master writers (3)
    SourceDef(
        sheet="cluster_keywords",
        primary_source="pillar",
        url_col="assigned_url",
        signature_cols=("cluster", "keyword"),
        related_source_key="cluster_keywords",
        skill_name="cluster-map",
    ),
    SourceDef(
        sheet="topical_map",
        primary_source="pillar",
        url_col="assigned_url",
        signature_cols=("pillar", "cluster", "primary_keyword"),
        related_source_key="topical_map",
        skill_name="topical-map",
    ),
    SourceDef(
        sheet="new_content_plan",
        primary_source="pillar",
        url_col=None,                       # url_slug is the URL stub
        signature_cols=("url_slug", "primary_keyword"),
        related_source_key="new_content_plan",
        skill_name="new-content-plan",
    ),
)


# ---------------------------------------------------------------------------
# Helpers — task_id, signature, validators
# ---------------------------------------------------------------------------

def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _row_signature(row: Mapping[str, Any], cols: Sequence[str]) -> str:
    """Stable, deterministic signature joining the per-source signature
    columns. Empty values stay as "" — the join fingerprint differs
    based on which columns are populated, which is the desired behaviour.
    """
    return "|".join(_safe_str(row.get(c)) for c in cols)


def _build_task_id(primary_source: str, url: str, signature: str) -> str:
    """Deterministic task_id per worker brief.

    Hash inputs are joined by "|" and hashed sha256; the prefix
    TASK_ID_PREFIX_LEN of the hex digest becomes the task_id. Stable
    across runs (no salt, no clock dependency, no slug dependency)."""
    payload = f"{primary_source}|{url}|{signature}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:TASK_ID_PREFIX_LEN]


def _ensure_primary_source_enum(value: str) -> None:
    if value not in PRIMARY_SOURCE_ENUM:
        raise PrimarySourceEnumViolation(
            f"primary_source {value!r} not in master_task enum: "
            f"{sorted(PRIMARY_SOURCE_ENUM)}"
        )


def _ensure_no_protected_writes(payload: Mapping[str, Any]) -> None:
    """Schema-first guard. Per master-excel.schema.json#master_task
    line 300, master_task_sync is FORBIDDEN to write to protected_columns.

    A populated value (non-empty string / non-None) for ANY of B/F/G/H/I/M/N
    raises ProtectedColumnsWriteAttempt. Empty-string seeds (used to
    pad a new row) are allowed because they are no-ops at the Excel
    layer (sheet cell stays blank).
    """
    for col in PROTECTED_COLUMNS:
        if col not in payload:
            continue
        v = payload[col]
        if v in (None, "", 0):
            # Blank seed for a new row; tolerated. (0 is also tolerated for
            # `duration_est_min` because some sheets pre-seed integer
            # placeholders; the production write layer treats it as blank.)
            continue
        raise ProtectedColumnsWriteAttempt(
            f"master_task_sync writer scope violation: cannot populate "
            f"protected column {col!r} (value={v!r}). Per schema line 300, "
            f"only [task, category, priority, impact, duration_est_min, "
            f"assignee, note] are owned by human/done_protocol writers. "
            f"writer_scope: {WRITER_SCOPE_SEMANTIC}"
        )


def _ensure_column_tuple(row: Mapping[str, Any]) -> None:
    """19-col tuple match — defensive before write."""
    keys = tuple(row.keys())
    if keys != MASTER_TASK_COLUMNS:
        raise ColumnTupleDriftError(
            f"master_task row column tuple drift: got={keys}, "
            f"expected={MASTER_TASK_COLUMNS}"
        )


# ---------------------------------------------------------------------------
# related_sources merge logic — D column ONLY (writer_scope guard)
# ---------------------------------------------------------------------------

def _split_related(value: Any) -> list[str]:
    """Split existing D-column value into sorted unique tokens."""
    s = _safe_str(value)
    if not s:
        return []
    parts = [p.strip() for p in s.split(RELATED_SOURCES_SEP) if p.strip()]
    return parts


def _join_related(tokens: Iterable[str]) -> str:
    """Sort + dedupe + join. Byte-stable output for idempotency."""
    return RELATED_SOURCES_SEP.join(sorted(set(tokens)))


def merge_related_sources(existing: Any, new_key: str) -> str:
    """Merge a new related_source_key into the existing D column value.

    Idempotent: if `new_key` is already present, returns the existing
    value (re-sorted for byte stability — same input → same output).
    """
    if not isinstance(new_key, str) or not new_key.strip():
        raise WriterScopeViolation(
            f"merge_related_sources requires a non-empty new_key, "
            f"got {new_key!r}"
        )
    tokens = _split_related(existing)
    tokens.append(new_key.strip())
    return _join_related(tokens)


def merge_column(column_name: str, existing: Any, new_key: str) -> str:
    """Public merge entry point. Enforces writer_scope (D-only)."""
    if column_name != "related_sources":
        raise WriterScopeViolation(
            f"master_task_sync may only merge column 'related_sources' (D); "
            f"caller asked for column={column_name!r}. "
            f"writer_scope: {WRITER_SCOPE_SEMANTIC}"
        )
    return merge_related_sources(existing, new_key)


# ---------------------------------------------------------------------------
# Row build — APPEND (new task_id) path
# ---------------------------------------------------------------------------

def _build_master_task_row(
    *,
    task_id: str,
    primary_source: str,
    url: str,
    related_source_key: str,
    run_date: str,
    default_status: str,
) -> dict:
    """Assemble a fully-populated 19-col master_task row dict.

    Protected columns (B, F, G, H, I, M, N) are seeded BLANK ("") because
    the master_task_sync writer is forbidden from touching them. The
    human / done_protocol writers populate them later.

    duration_est_min (Q is the int counter for actual logged work; I is
    the protected estimate). I is left blank (DURATION_EST_BLANK).
    Q is initialized to 0 (an effort_actual_min counter, not protected).
    """
    row = {
        "task_id":            task_id,
        # PROTECTED — blank seed:
        "task":               "",
        "primary_source":     primary_source,
        "related_sources":    related_source_key,
        "url":                url,
        # PROTECTED — blank seed:
        "category":           "",
        # PROTECTED — blank seed:
        "priority":           "",
        # PROTECTED — blank seed:
        "impact":             "",
        # PROTECTED — blank seed:
        "duration_est_min":   DURATION_EST_BLANK,
        "status":             default_status,
        "created_date":       run_date,
        "done_date":          "",  # done_protocol scope
        # PROTECTED — blank seed:
        "assignee":           "",
        # PROTECTED — blank seed:
        "note":               "",
        "auto_generated":     True,
        "dependencies":       "",
        "effort_actual_min":  0,
        "metric_impact_json": "{}",
        "work_log_ref":       "",
    }
    # Defensive: column tuple + enum + protected guard. The protected
    # guard tolerates blank seeds (no populated values).
    _ensure_column_tuple(row)
    _ensure_primary_source_enum(row["primary_source"])
    _ensure_no_protected_writes(row)
    if row["status"] not in STATUS_ENUM:
        raise MasterTaskSyncError(
            f"status not in statusEnum: {row['status']!r}"
        )
    if not isinstance(row["auto_generated"], bool) or row["auto_generated"] is not True:
        raise MasterTaskSyncError(
            f"auto_generated must be True bool, got {row['auto_generated']!r}"
        )
    return row


# ---------------------------------------------------------------------------
# Source row → (task_id, primary_source, url, related_key) extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ExtractedSig:
    """One upstream row reduced to its identity fingerprint."""

    task_id: str
    primary_source: str
    url: str
    related_source_key: str
    source_sheet: str  # diagnostic only; not written to row


def _extract_signature(
    source_def: SourceDef, row: Mapping[str, Any]
) -> _ExtractedSig | None:
    """Reduce one upstream sheet row to its (task_id, primary_source,
    url, related_source_key) fingerprint. Returns None when the row
    lacks the minimum payload (signature_cols all blank), which is the
    convention for "skip this row, it's a header artifact / blank".
    """
    sig = _row_signature(row, source_def.signature_cols)
    if not sig.replace(RELATED_SOURCES_SEP, "").strip():
        # All signature cols are blank — skip the row.
        return None
    primary_source = source_def.derive_primary_source(row)
    _ensure_primary_source_enum(primary_source)
    url = _safe_str(row.get(source_def.url_col)) if source_def.url_col else ""
    task_id = _build_task_id(primary_source, url, sig)
    return _ExtractedSig(
        task_id=task_id,
        primary_source=primary_source,
        url=url,
        related_source_key=source_def.related_source_key,
        source_sheet=source_def.sheet,
    )


# ---------------------------------------------------------------------------
# Aggregation — compute APPEND + MERGE batches
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AggregateBatch:
    """The diff to apply to master_task. Pure data — no I/O implied.

    Fields:
        appends:     list of new master_task rows (full 19-col dicts)
                     to append to the bottom of the sheet.
        merges:      list of (task_id, new_related_sources_value) pairs
                     to apply to existing rows (D-column only).
        skipped_manuel: count of existing manuel rows (auto_generated=false)
                     that the aggregator left untouched.
        no_op_count: count of existing auto_generated rows where the new
                     related_source_key was already in D (no actual change).
        per_source_stats: dict[sheet_name → emit_count] for diagnostics.
    """

    appends: list[dict] = field(default_factory=list)
    merges: list[tuple[str, str]] = field(default_factory=list)
    skipped_manuel: int = 0
    no_op_count: int = 0
    per_source_stats: dict = field(default_factory=dict)


def _index_existing(
    existing_rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict]:
    """Index existing master_task rows by task_id. Last-write-wins on
    duplicate task_id (defensive — should never happen, but if it does
    the most recent row wins so re-runs converge)."""
    out: dict[str, dict] = {}
    for r in existing_rows:
        tid = _safe_str(r.get("task_id"))
        if not tid:
            continue
        out[tid] = dict(r)
    return out


def aggregate(
    *,
    sources: Mapping[str, Sequence[Mapping[str, Any]]],
    existing_master_task: Sequence[Mapping[str, Any]],
    run_date: str,
    default_status: str = "TODO",
    expected_sheets: Sequence[str] | None = None,
) -> AggregateBatch:
    """Pure aggregation: 8 upstream sheets + existing master_task →
    AppendBatch describing what should change.

    Args:
        sources: dict mapping upstream sheet_name → list-of-row-dicts.
                 At minimum the keys in SOURCE_DEFS should appear; missing
                 keys are tolerated (skill may run before all upstream
                 sheets exist) UNLESS expected_sheets pins them.
        existing_master_task: list-of-row-dicts already in master_task.
                 Used for task_id collision detection + auto_generated
                 honoring.
        run_date: ISO date string (YYYY-MM-DD) for created_date column.
        default_status: statusEnum seed for new appended rows.
        expected_sheets: when provided, raise SheetMissingError if any
                 entry is absent from `sources`. Pass when the skill has
                 verified Phase 7+8 are complete (DURUR #1 vehicle).

    Returns:
        AggregateBatch — pure data. Caller decides when to apply.

    Raises:
        SheetMissingError              — DURUR #1 (with expected_sheets pin).
        ColumnTupleDriftError          — DURUR #2 (defensive).
        TaskIdCollisionError           — DURUR #3 (sha256 prefix collision).
        PrimarySourceEnumViolation     — DURUR #5 (bad enum value).
        ProtectedColumnsWriteAttempt   — DURUR #6 (sentinel guard).
        MasterTaskSyncError            — bad input shape.
    """
    if not isinstance(run_date, str) or not run_date.strip():
        raise MasterTaskSyncError(
            f"run_date must be a non-empty ISO date string, got {run_date!r}"
        )
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError as exc:
        raise MasterTaskSyncError(
            f"run_date must be YYYY-MM-DD, got {run_date!r}: {exc}"
        ) from exc
    if default_status not in STATUS_ENUM:
        raise MasterTaskSyncError(
            f"default_status must be in statusEnum, got {default_status!r}"
        )

    if expected_sheets is not None:
        missing = [s for s in expected_sheets if s not in sources]
        if missing:
            raise SheetMissingError(
                f"expected upstream sheets absent: {missing}. "
                "Run the prior skill (cannibalization / cluster-map / etc.) "
                "to populate them before re-running master-task-sync."
            )

    existing_index = _index_existing(existing_master_task)

    # Track sha256 prefix collisions. If the same task_id appears for
    # different (primary_source, url, signature) tuples, raise.
    seen_sigs_by_task_id: dict[str, str] = {}

    appends: list[dict] = []
    merges: list[tuple[str, str]] = []
    skipped_manuel = 0
    no_op_count = 0
    per_source_stats: dict[str, int] = {}

    # Iterate SOURCE_DEFS in deterministic order so output is stable
    # across runs.
    for src in SOURCE_DEFS:
        rows = sources.get(src.sheet) or []
        emitted = 0
        for row in rows:
            sig = _extract_signature(src, row)
            if sig is None:
                continue
            # Collision detection on the sha256[:N] prefix.
            full_payload = f"{sig.primary_source}|{sig.url}|{_row_signature(row, src.signature_cols)}"
            prior = seen_sigs_by_task_id.get(sig.task_id)
            if prior is not None and prior != full_payload:
                raise TaskIdCollisionError(
                    f"sha256[:{TASK_ID_PREFIX_LEN}] collision on task_id "
                    f"{sig.task_id!r}: prior={prior!r}, new={full_payload!r}. "
                    "Bump TASK_ID_PREFIX_LEN."
                )
            seen_sigs_by_task_id[sig.task_id] = full_payload

            existing_row = existing_index.get(sig.task_id)
            if existing_row is None:
                # APPEND new row (full schema seed).
                new_row = _build_master_task_row(
                    task_id=sig.task_id,
                    primary_source=sig.primary_source,
                    url=sig.url,
                    related_source_key=sig.related_source_key,
                    run_date=run_date,
                    default_status=default_status,
                )
                appends.append(new_row)
                # Mirror it into the index so a duplicate signature in
                # the same run merges instead of double-appending.
                existing_index[sig.task_id] = dict(new_row)
                emitted += 1
                continue

            # Existing row found.
            auto = existing_row.get("auto_generated")
            # The Excel write layer round-trips booleans as either Python
            # bool or string "True"/"False"; accept both shapes.
            is_auto = (
                auto is True
                or (isinstance(auto, str) and auto.strip().lower() == "true")
            )
            if not is_auto:
                # Manuel entry: SKIP entirely. DO NOT TOUCH any column.
                skipped_manuel += 1
                continue

            # Auto-generated row: MERGE D column ONLY.
            old_d = existing_row.get("related_sources", "")
            new_d = merge_column("related_sources", old_d, sig.related_source_key)
            if new_d == _safe_str(old_d):
                # No-op: key already present (or rejoin produces same string).
                no_op_count += 1
                continue
            merges.append((sig.task_id, new_d))
            # Mirror the merged value into the index so subsequent rows in
            # the same run see the updated D.
            existing_row = dict(existing_row)
            existing_row["related_sources"] = new_d
            existing_index[sig.task_id] = existing_row
            emitted += 1

        per_source_stats[src.sheet] = emitted

    # Final defensive: every appended row must pass column tuple +
    # protected guard checks. (Already enforced inside _build_master_task_row,
    # but a second sweep is cheap insurance against drift.)
    for r in appends:
        _ensure_column_tuple(r)
        _ensure_no_protected_writes(r)
        _ensure_primary_source_enum(r["primary_source"])

    # Sort appends deterministically: by (primary_source, url, task_id).
    # This keeps the Excel append order stable across runs even if the
    # caller passes upstream rows in a different order.
    appends.sort(key=lambda r: (r["primary_source"], r["url"], r["task_id"]))
    merges.sort(key=lambda kv: kv[0])

    return AggregateBatch(
        appends=appends,
        merges=merges,
        skipped_manuel=skipped_manuel,
        no_op_count=no_op_count,
        per_source_stats=per_source_stats,
    )


# ---------------------------------------------------------------------------
# Idempotency self-check
# ---------------------------------------------------------------------------

def assert_idempotent_state(
    *,
    first_state: AggregateBatch,
    second_state: AggregateBatch,
) -> None:
    """Verify two consecutive aggregate() runs produced identical state.

    Used by the smoke test + can be invoked by skill body after the
    second pass. Raises IdempotencyDriftError on any divergence.

    The semantic: "Re-run with identical Phase 7+8 state → identical
    master_task state." On the SECOND run the existing_master_task
    already contains the rows the first run appended, so the second
    run should produce 0 appends + 0 merges (or merges that no-op).
    """
    if second_state.appends:
        raise IdempotencyDriftError(
            f"second run produced {len(second_state.appends)} new appends; "
            "expected 0 — task_id sha256 derivation should be deterministic. "
            f"Sample task_ids: {[r['task_id'] for r in second_state.appends[:3]]}"
        )
    # Real merges (where the existing D was actually changed) should
    # also be zero on the second pass.
    if second_state.merges:
        raise IdempotencyDriftError(
            f"second run produced {len(second_state.merges)} D-merges; "
            "expected 0 (existing rows already carry the related_source key). "
            f"Sample: {second_state.merges[:3]}"
        )


# ---------------------------------------------------------------------------
# Snapshot writer — drift recovery payload
# ---------------------------------------------------------------------------

def build_snapshot(
    *,
    batch: AggregateBatch,
    run_date: str,
    project_slug: str,
) -> dict:
    """Build the inbox/local/{date}-master_task_sync-{slug}.json payload.

    This is a drift-recovery artifact: if the Excel write fails (lock
    contention, schema drift, etc.) the caller still has the full
    aggregator output as JSON. Mirrors the inbox/gsc/ + inbox/sf/ pattern.
    """
    return {
        "version": "1.0",
        "run_date": run_date,
        "project_slug": project_slug,
        "writer": WRITER_NAME,
        "writer_scope": WRITER_SCOPE_SEMANTIC,
        "appends_count": len(batch.appends),
        "merges_count": len(batch.merges),
        "skipped_manuel": batch.skipped_manuel,
        "no_op_count": batch.no_op_count,
        "per_source_stats": dict(batch.per_source_stats),
        "appends": list(batch.appends),
        "merges": [
            {"task_id": tid, "related_sources": v}
            for tid, v in batch.merges
        ],
    }


# ---------------------------------------------------------------------------
# Report rendering — markdown summary
# ---------------------------------------------------------------------------

def build_report_markdown(
    *,
    batch: AggregateBatch,
    run_date: str,
    project_slug: str,
) -> str:
    """Build the outputs/reports/{date}-master-task-sync.md body.

    Plain-text summary surfaced to the user: total tasks affected,
    auto/manuel split, primary_source breakdown, append/merge stats.
    """
    lines: list[str] = []
    lines.append(f"# master-task-sync — {run_date}")
    lines.append("")
    lines.append(f"- project: `{project_slug}`")
    lines.append(f"- writer: `{WRITER_NAME}`")
    lines.append(f"- writer_scope: {WRITER_SCOPE_SEMANTIC}")
    lines.append("")
    lines.append("## Aggregation totals")
    lines.append("")
    lines.append(f"- new appends:        **{len(batch.appends)}**")
    lines.append(f"- D-only merges:      **{len(batch.merges)}**")
    lines.append(f"- manuel rows skipped: **{batch.skipped_manuel}**")
    lines.append(f"- no-op (already merged): **{batch.no_op_count}**")
    lines.append("")
    lines.append("## Per-source emit counts")
    lines.append("")
    lines.append("| upstream sheet | rows emitted |")
    lines.append("|---|---|")
    for src in SOURCE_DEFS:
        n = batch.per_source_stats.get(src.sheet, 0)
        lines.append(f"| `{src.sheet}` | {n} |")
    lines.append("")
    if batch.appends:
        primary_breakdown: dict[str, int] = {}
        for r in batch.appends:
            primary_breakdown[r["primary_source"]] = (
                primary_breakdown.get(r["primary_source"], 0) + 1
            )
        lines.append("## primary_source breakdown (new appends)")
        lines.append("")
        lines.append("| primary_source | count |")
        lines.append("|---|---|")
        for k in sorted(primary_breakdown):
            lines.append(f"| `{k}` | {primary_breakdown[k]} |")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="master_task_sync.py",
        description=(
            "Aggregate Phase 7 + Phase 8 Wave 1 master writer sheets "
            "→ master.xlsx#master_task auto_generated rows. "
            "Local aggregation, no MCP, no DFS."
        ),
    )
    p.add_argument(
        "--sources-json", required=True,
        help=(
            "Path to a JSON file with shape "
            "{sheet_name: [row_dict, ...]} for each upstream sheet."
        ),
    )
    p.add_argument(
        "--existing-master-task-json", default=None,
        help=(
            "Path to a JSON list of existing master_task rows (for "
            "merge / skip-manuel detection). Default: empty list."
        ),
    )
    p.add_argument("--project-slug", required=True,
                   help="Active project slug — feeds snapshot + report paths.")
    p.add_argument("--run-date", default=None,
                   help="ISO date YYYY-MM-DD (default: today).")
    p.add_argument("--default-status", default="TODO",
                   help="statusEnum seed for new rows (default: TODO).")
    p.add_argument("--require-all-sheets", action="store_true",
                   help="DURUR #1: raise if any of the 8 expected sheets is "
                        "absent from --sources-json.")
    p.add_argument("--output-dir", default=None,
                   help="If set, writes snapshot.json + report.md here.")
    return p.parse_args(list(argv))


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    run_date = args.run_date or _date.today().isoformat()

    src_path = Path(args.sources_json)
    if not src_path.is_file():
        print(f"--sources-json not found: {src_path}", file=sys.stderr)
        return 2
    try:
        sources = json.loads(src_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"sources-json parse failed: {exc}", file=sys.stderr)
        return 2
    if not isinstance(sources, dict):
        print(
            "sources-json must be a dict of {sheet_name: [row_dict, ...]}",
            file=sys.stderr,
        )
        return 2

    existing: list[dict] = []
    if args.existing_master_task_json:
        ep = Path(args.existing_master_task_json)
        if ep.is_file():
            try:
                existing = json.loads(ep.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(
                    f"existing-master-task-json parse failed: {exc}",
                    file=sys.stderr,
                )
                return 2
            if not isinstance(existing, list):
                print(
                    "existing-master-task-json must be a list of row dicts",
                    file=sys.stderr,
                )
                return 2

    expected = (
        tuple(s.sheet for s in SOURCE_DEFS) if args.require_all_sheets else None
    )
    try:
        batch = aggregate(
            sources=sources,
            existing_master_task=existing,
            run_date=run_date,
            default_status=args.default_status,
            expected_sheets=expected,
        )
    except MasterTaskSyncError as exc:
        print(f"aggregate failed: {exc}", file=sys.stderr)
        return 1

    snapshot = build_snapshot(
        batch=batch, run_date=run_date, project_slug=args.project_slug,
    )
    report = build_report_markdown(
        batch=batch, run_date=run_date, project_slug=args.project_slug,
    )

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        snap_path = out_dir / (
            f"{run_date}-master_task_sync-{args.project_slug}.json"
        )
        snap_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        report_path = out_dir / f"{run_date}-master-task-sync.md"
        report_path.write_text(report, encoding="utf-8")
        print(json.dumps({
            "snapshot_path": str(snap_path.resolve()),
            "report_path": str(report_path.resolve()),
            "appends_count": len(batch.appends),
            "merges_count": len(batch.merges),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "snapshot": snapshot,
            "report_md": report,
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "MASTER_TASK_COLUMNS",
    "PROTECTED_COLUMNS",
    "PRIMARY_SOURCE_ENUM",
    "STATUS_ENUM",
    "WRITER_NAME",
    "WRITER_SCOPE_SEMANTIC",
    "TASK_ID_PREFIX_LEN",
    "RELATED_SOURCES_SEP",
    "SOURCE_DEFS",
    "SourceDef",
    "AggregateBatch",
    "MasterTaskSyncError",
    "SheetMissingError",
    "ColumnTupleDriftError",
    "TaskIdCollisionError",
    "IdempotencyDriftError",
    "PrimarySourceEnumViolation",
    "ProtectedColumnsWriteAttempt",
    "WriterScopeViolation",
    "WorkflowRunnerSchemaError",
    "WorkspaceRootUnsetError",
    "aggregate",
    "merge_related_sources",
    "merge_column",
    "build_snapshot",
    "build_report_markdown",
    "assert_idempotent_state",
    "main",
)
