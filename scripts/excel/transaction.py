#!/usr/bin/env python3
"""
transaction.py — Atomic, schema-validated, backup-protected Excel writer.

Single approved write path for `master.xlsx` (rules/excel-discipline.md +
ADR-009: master excel is schema-generated, never hand-edited). 19 sheets
defined in schemas/master-excel.schema.json.

Discipline: atomic write (tempfile + os.fsync + os.replace + dir fsync);
backup-then-write to `{ws}/projects/{slug}/_state/backups/master/
master-{ISO}.xlsx` with FIFO keep-7 rotation; lock on sentinel
`_state/excel.lock` via fcntl.flock(LOCK_EX|LOCK_NB) (NOT on the xlsx
itself — openpyxl re-opens it); 3-layer schema validation (sheet exists
→ per-row jsonschema synthesized from required_columns+definitions
ADR-018 → formula_policy '=' prefix); cell length cap 32767; master_task
gated by allowed_writers; AFTER write emit provenance event via
events_writer.append_provenance(operation="project_excel"). Plugin-
agnostik (no slug literals).

Public API: write/append/update (no delete — rules/append-only-state.md).

Refs: spec §3 + §8.5; schemas/master-excel.schema.json (definitions,
formula_policy, allowed_writers); rules/excel-discipline, schema-first,
append-only-state, single-source-of-truth; ADR-009, ADR-012, ADR-018,
ADR-021.
Imports events_writer one-way; never imported by it.
"""

from __future__ import annotations

import fcntl
import functools
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook import Workbook

from scripts.state import events_writer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "master-excel.schema.json"

_BACKUPS_KEEP = 7
_EXCEL_CELL_MAX_CHARS = 32_767  # openpyxl/Excel hard limit
_LOCK_STALE_SECONDS = 5 * 60  # 5 minutes

# JSON-schema "type" → Python type tuple acceptable by openpyxl-bound rows.
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),         # bool is subclass of int — handled separately
    "number": (int, float),
    "boolean": (bool,),
    "date": (str,),            # we store ISO 8601 strings (rules/time-discipline.md)
}

# ---------------------------------------------------------------------------
# WRITER_REGISTRY — per-sheet allowed-writer convention (LC-1, Q-W3W2B-WRITER-01)
# ---------------------------------------------------------------------------
#
# Codifies which writer identity is *expected* to author each logical sheet.
# `master_task` mirrors schemas/master-excel.schema.json `allowed_writers`
# (the only sheet with a HARD schema-level gate); every other sheet carries
# allowed_writers=None in the schema (no hard gate) and historically accepted
# arbitrary writer strings — `_check_writer_scope` is vacuous when
# allowed_writers is None — so the producing-skill convention was lost.
#
# v1.9 = OPT-IN / ADVISORY ONLY. WRITER_REGISTRY does NOT gate writes; the
# write/append/update path is intentionally UNCHANGED (spec Risk R6 — must not
# break existing transaction.py callers). `writer_registry_status()` is the
# opt-in surface: a caller (or v2.0 enforcement) may consult it to emit a
# warning when a writer is off-convention. Enforcement is reserved for v2.0.
WRITER_REGISTRY_ENFORCEMENT: bool = False  # v1.9 OPT-IN (advisory); v2.0 flips

WRITER_REGISTRY: dict[str, frozenset[str]] = {
    # Hard-gated sheet — mirrors master-excel.schema.json allowed_writers.
    "master_task":      frozenset({"human", "dashboard_refresh", "done_protocol", "master_task_sync"}),
    # KPI projection sheet — refreshed by the dashboard projector.
    "dashboard":        frozenset({"dashboard_refresh"}),
    # Planning sheets.
    "topical_map":      frozenset({"topical-map"}),
    "cluster_keywords": frozenset({"cluster-map"}),
    "cannibalization":  frozenset({"cannibalization"}),
    "quick_wins":       frozenset({"quick-wins"}),
    "opportunity":      frozenset({"quick-wins"}),
    "new_content_plan": frozenset({"new-content-plan"}),
    "content_improve":  frozenset({"content-remediation"}),
    "content_decay":    frozenset({"content-decay"}),
    # Ingestion / audit sheets.
    "gsc_performance":  frozenset({"gsc-pull"}),
    "on_page_audit":    frozenset({"on-page-audit"}),
    "tech_seo":         frozenset({"tech-audit"}),
    "gbp_audit":        frozenset({"gbp-audit"}),
    "schema":           frozenset({"schema-audit"}),
    "crawl_sitemap":    frozenset({"sf-import"}),
    "robots_txt":       frozenset({"tech-audit"}),
    "redirect_404":     frozenset({"sf-import"}),
    "completed_work":   frozenset({"done-protocol"}),
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TransactionError(Exception):
    """Base class for all transaction.py errors."""


class SchemaSheetMismatchError(TransactionError):
    """The requested sheet is not declared in master-excel.schema.json."""


class RowSchemaError(TransactionError):
    """A row failed per-column schema validation."""


class FormulaPolicyViolation(TransactionError):
    """A cell value starts with '=' — formulas are forbidden (formula_policy)."""


class CellValueTooLongError(TransactionError):
    """A cell value exceeds Excel's 32,767-character cap."""


class LockHeldError(TransactionError):
    """Another writer currently holds the excel.lock sentinel."""


class BackupDirUnwritableError(TransactionError):
    """Cannot create or write into the backups/master/ directory."""


class WorkbookLockedByExcelError(TransactionError):
    """The workbook is open in Excel/LibreOffice (~$ lockfile present)."""


class WorkbookCorruptError(TransactionError):
    """openpyxl could not parse the workbook on read."""


class WriterScopeError(TransactionError):
    """master_task write attempted with missing/disallowed writer identity."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WriteResult:
    workbook_path: Path
    sheet: str
    rows_affected: int
    backup_path: Path
    event_id: str  # provenance event_id emitted post-write


# ---------------------------------------------------------------------------
# Internals — schema loading + per-sheet validator synthesis
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


@functools.lru_cache(maxsize=4)
def _load_schema(schema_path: str) -> dict:
    p = Path(schema_path)
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_definition_ref(schema: dict, ref: str) -> dict:
    """Resolve '#/definitions/<name>' against the master-excel schema."""
    if not ref.startswith("#/definitions/"):
        raise RowSchemaError(f"unsupported $ref form: {ref!r}")
    name = ref.split("/", 2)[2]
    defs = schema.get("definitions") or {}
    if name not in defs:
        raise RowSchemaError(f"definition not found: {name!r} (ADR-018)")
    return defs[name]


def _build_row_validator(schema: dict, sheet: str) -> Draft7Validator:
    """Synthesize a Draft7 validator for a single row of the named sheet."""
    sheets = schema.get("sheets") or {}
    if sheet not in sheets:
        raise SchemaSheetMismatchError(
            f"sheet {sheet!r} not declared in master-excel.schema.json"
        )
    sdef = sheets[sheet]
    cols = sdef.get("required_columns") or []
    if not cols:
        # Sheets like 'dashboard' use required_cells (KPI projection) — not
        # supported by row-style write/append/update. Caller must use a
        # different code path for KPI projection writes.
        raise SchemaSheetMismatchError(
            f"sheet {sheet!r} has no required_columns (use KPI projection)"
        )

    properties: dict[str, Any] = {}
    required: list[str] = []
    for col in cols:
        name = col["name"]
        required.append(name)
        prop: dict[str, Any] = {}
        ctype = col.get("type")
        cenum = col.get("enum")
        cref = col.get("ref")
        if cref:
            ref_def = _resolve_definition_ref(schema, cref)
            prop.update(ref_def)
        elif cenum:
            prop["type"] = "string"
            prop["enum"] = list(cenum)
        elif ctype:
            # Allow None as well (sparse columns are common in Excel land).
            json_types = {
                "integer": "integer",
                "number":  "number",
                "boolean": "boolean",
                "date":    "string",
            }.get(ctype)
            if json_types is None:
                prop["type"] = "string"
            else:
                prop["type"] = [json_types, "null"]
        else:
            prop["type"] = ["string", "null"]
        properties[name] = prop

    row_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": True,  # per-row dicts may carry extras; primary check is required+typed
        "required": required,
        "properties": properties,
    }
    return Draft7Validator(row_schema)


# ---------------------------------------------------------------------------
# Internals — formula policy + cell length checks
# ---------------------------------------------------------------------------

def _check_formula_policy(rows: list[dict]) -> None:
    for idx, row in enumerate(rows):
        for k, v in row.items():
            if isinstance(v, str) and v.lstrip().startswith("="):
                raise FormulaPolicyViolation(
                    f"row {idx} field {k!r}: formula prefix '=' forbidden"
                )


def _check_cell_lengths(rows: list[dict]) -> None:
    for idx, row in enumerate(rows):
        for k, v in row.items():
            if isinstance(v, str) and len(v) > _EXCEL_CELL_MAX_CHARS:
                raise CellValueTooLongError(
                    f"row {idx} field {k!r}: {len(v)} chars > {_EXCEL_CELL_MAX_CHARS}"
                )


def _validate_rows(rows: list[dict], validator: Draft7Validator) -> None:
    for idx, row in enumerate(rows):
        errors = sorted(validator.iter_errors(row), key=lambda e: e.path)
        if errors:
            err: _JSValidationError = errors[0]
            loc = "/".join(str(p) for p in err.absolute_path) or "<row>"
            raise RowSchemaError(f"row {idx} {loc}: {err.message}")


# ---------------------------------------------------------------------------
# Internals — lock sentinel
# ---------------------------------------------------------------------------

def _state_dir(state_root: Path | None, workbook_path: Path, project_slug: str) -> Path:
    """
    Resolve {ws}/projects/{slug}/_state/. If state_root explicitly given,
    use it directly (test convenience). Else derive from workbook_path:
    walk up to find projects/{slug}/_state/.
    """
    if state_root is not None:
        sd = Path(state_root)
        sd.mkdir(parents=True, exist_ok=True)
        return sd
    # Default: workbook_path is .../projects/{slug}/{filename}.xlsx
    sd = workbook_path.parent / "_state"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def _read_sentinel(lock_path: Path) -> tuple[int | None, str | None]:
    if not lock_path.exists():
        return None, None
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        obj = json.loads(raw)
        return obj.get("pid"), obj.get("ts")
    except (OSError, json.JSONDecodeError, ValueError):
        return None, None


def _is_stale(pid: int | None, ts: str | None) -> bool:
    if pid is None or ts is None:
        # Corrupt sentinel = stale.
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # No process with that PID → stale.
        return True
    except PermissionError:
        # Process exists but is not ours; not stale.
        pid_alive = True
    else:
        pid_alive = True
    if not pid_alive:  # pragma: no cover (ProcessLookupError handled above)
        return True
    # Age check.
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return True
    age = (datetime.now(timezone.utc) - when).total_seconds()
    return age > _LOCK_STALE_SECONDS


def _acquire_lock(lock_path: Path) -> int:
    """Acquire excel.lock via flock(LOCK_EX|LOCK_NB). Returns fd to hold."""
    # First, stale reclaim. Sentinel content is informational; flock provides
    # the actual mutual exclusion below.
    pid, ts = _read_sentinel(lock_path)
    if pid is not None and _is_stale(pid, ts):
        try:
            lock_path.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass

    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise LockHeldError(f"another writer holds {lock_path}") from exc
    except OSError as exc:
        os.close(fd)
        raise LockHeldError(f"flock failed on {lock_path}: {exc}") from exc

    # Refresh sentinel content for the holder. Truncate + rewrite is OK:
    # this file is informational, not the durability target.
    payload = json.dumps({
        "pid": os.getpid(),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }, separators=(",", ":")).encode("utf-8") + b"\n"
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload)
        os.fsync(fd)
    except OSError:  # pragma: no cover (informational, not blocking)
        pass
    return fd


def _release_lock(fd: int, lock_path: Path) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:  # pragma: no cover
        pass
    try:
        os.close(fd)
    except OSError:  # pragma: no cover
        pass
    # Best-effort sentinel cleanup; OK if it lingers (next writer reclaims).
    try:
        lock_path.unlink()
    except FileNotFoundError:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Internals — backup + atomic save
# ---------------------------------------------------------------------------

def _iso_compact() -> str:
    """Backup-friendly UTC timestamp: 2026-04-30T12-00-00-123456Z (lex-sortable)."""
    now = datetime.now(timezone.utc)
    # Substitute ':' with '-' so it's a valid filename on every OS.
    return now.strftime("%Y-%m-%dT%H-%M-%S-%fZ")


def _backup(target: Path, state_dir: Path) -> Path:
    backup_dir = state_dir / "backups" / "master"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupDirUnwritableError(f"cannot create {backup_dir}: {exc}") from exc

    if not target.exists():
        # First-write case: there is nothing to back up. Touch a marker
        # so the rotation invariant ("a backup precedes every write") is
        # satisfied. Marker has the same name shape so it sorts naturally.
        marker = backup_dir / f"master-{_iso_compact()}.empty"
        marker.write_bytes(b"")
        return marker

    bp = backup_dir / f"master-{_iso_compact()}.xlsx"
    try:
        shutil.copy2(target, bp)
    except OSError as exc:
        raise BackupDirUnwritableError(f"cannot copy {target} → {bp}: {exc}") from exc
    return bp


def _rotate_backups(state_dir: Path) -> None:
    backup_dir = state_dir / "backups" / "master"
    if not backup_dir.is_dir():
        return
    # Lex-sort by name; timestamps are lex-sortable.
    files = sorted(p for p in backup_dir.iterdir() if p.is_file())
    excess = len(files) - _BACKUPS_KEEP
    if excess <= 0:
        return
    for old in files[:excess]:
        try:
            old.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass


def _atomic_save(wb: Workbook, target: Path) -> None:
    """Save wb to a sibling tempfile, fsync, then os.replace target."""
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".master-", suffix=".xlsx.tmp", dir=str(parent)
    )
    tmp_path = Path(tmp_name)
    try:
        os.close(tmp_fd)  # openpyxl re-opens the path
        wb.save(str(tmp_path))
        # Re-open the file just to fsync the data we wrote.
        with tmp_path.open("rb") as fh:
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(target))
    except Exception:
        # Cleanup leftover tempfile on failure (do NOT swallow the error).
        try:
            tmp_path.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass
        raise

    # Parent dir fsync — durability of the rename.
    try:
        dir_fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:  # pragma: no cover (best-effort, not all FS support it)
        pass


def _excel_lockfile_present(target: Path) -> bool:
    """Detect Excel/LibreOffice owner-lock sidecar (~$Filename.xlsx)."""
    sidecar = target.parent / f"~${target.name}"
    return sidecar.exists()


def _load_or_new(target: Path) -> Workbook:
    """Load an existing wb or create a new one. Wraps openpyxl exceptions."""
    if not target.exists():
        return Workbook()
    if _excel_lockfile_present(target):
        raise WorkbookLockedByExcelError(
            f"workbook {target} appears open in Excel/LibreOffice "
            f"(found ~${target.name})"
        )
    try:
        return load_workbook(str(target))
    except InvalidFileException as exc:
        raise WorkbookCorruptError(f"cannot parse {target}: {exc}") from exc
    except OSError as exc:
        raise WorkbookCorruptError(f"cannot read {target}: {exc}") from exc


def _check_writer_scope(schema: dict, sheet: str, writer: str | None) -> None:
    sdef = schema.get("sheets", {}).get(sheet, {})
    allowed = sdef.get("allowed_writers")
    if allowed is None:
        return
    if writer is None:
        raise WriterScopeError(
            f"sheet {sheet!r} requires writer arg (allowed: {allowed})"
        )
    if writer not in allowed:
        raise WriterScopeError(
            f"writer {writer!r} not in allowed_writers for {sheet!r}: {allowed}"
        )


def writer_registry_status(
    sheet: str,
    writer: str | None,
    *,
    enforce: bool = WRITER_REGISTRY_ENFORCEMENT,
) -> str:
    """Advisory per-sheet writer-convention check (LC-1, Q-W3W2B-WRITER-01).

    Returns:
        "ok"           — writer is registered for the sheet, OR the sheet is
                         not in WRITER_REGISTRY, OR writer is None (vacuous).
        "unregistered" — the sheet IS in WRITER_REGISTRY but `writer` is not
                         an allowed writer for it. A warning is logged.

    v1.9 contract: ADVISORY ONLY — NEVER raises and NEVER gates a write (spec
    Risk R6). `enforce` defaults to WRITER_REGISTRY_ENFORCEMENT (False in
    v1.9) and is reserved for v2.0; even when True it currently only escalates
    the log marker. The sole HARD write gate remains `_check_writer_scope`
    (schema allowed_writers). transaction.write/append/update do NOT call this
    helper — opting in is the caller's choice.
    """
    allowed = WRITER_REGISTRY.get(sheet)
    if allowed is None or writer is None or writer in allowed:
        return "ok"
    msg = (
        f"writer {writer!r} off-convention for sheet {sheet!r} "
        f"(WRITER_REGISTRY allows {sorted(allowed)}) — advisory "
        f"(LC-1 OPT-IN; enforcement reserved v2.0)"
    )
    _log(f"WARNING{' [enforce]' if enforce else ''}: {msg}")
    return "unregistered"


# ---------------------------------------------------------------------------
# Internals — sheet I/O (header detection + row write)
# ---------------------------------------------------------------------------

def _ordered_columns(schema: dict, sheet: str) -> list[dict]:
    return list(schema["sheets"][sheet]["required_columns"])


def _ensure_sheet_with_header(wb: Workbook, sheet: str, columns: list[dict]) -> None:
    """Create the sheet if missing; ensure row 1 has the header in column order."""
    if sheet in wb.sheetnames:
        ws = wb[sheet]
    else:
        # Drop a bare "Sheet" if it's the only one and we're adding the first.
        ws = wb.create_sheet(sheet)
        if "Sheet" in wb.sheetnames and wb["Sheet"].max_row == 1 and wb["Sheet"].max_column == 1 and wb["Sheet"]["A1"].value is None:
            del wb["Sheet"]
    # Always (re)write the header row in canonical order.
    header_names = [c["name"] for c in columns]
    for col_idx, name in enumerate(header_names, start=1):
        ws.cell(row=1, column=col_idx, value=name)


def _row_to_tuple(row: dict, columns: list[dict]) -> tuple:
    return tuple(row.get(col["name"]) for col in columns)


def _next_data_row(ws) -> int:
    """First empty row after the existing data block."""
    return (ws.max_row or 1) + 1


# ---------------------------------------------------------------------------
# Public API — write / append / update
# ---------------------------------------------------------------------------

def write(
    workbook_path: Path | str,
    sheet: str,
    rows: list[dict],
    project_slug: str,
    *,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
    writer: str | None = None,
) -> WriteResult:
    """
    Append-and-replace write: appends `rows` to `sheet`, atomically.

    The 'replace' aspect is not destructive: existing rows are preserved.
    Use update() for in-place mutation. The function name 'write' is
    retained for back-compat with the brief.
    """
    return _write_or_append(
        workbook_path, sheet, rows, project_slug,
        schema_path=schema_path, state_root=state_root, writer=writer,
        mode="append",
    )


def append(
    workbook_path: Path | str,
    sheet: str,
    rows: list[dict],
    project_slug: str,
    *,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
    writer: str | None = None,
) -> WriteResult:
    """Append rows to the bottom of `sheet`. Alias for write(mode='append')."""
    return _write_or_append(
        workbook_path, sheet, rows, project_slug,
        schema_path=schema_path, state_root=state_root, writer=writer,
        mode="append",
    )


def update(
    workbook_path: Path | str,
    sheet: str,
    where: dict,
    set_: dict,
    project_slug: str,
    *,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
    writer: str | None = None,
) -> WriteResult:
    """
    Update existing rows where every key/value in `where` matches; apply
    `set_` to those rows. Returns rows_affected = number of matched rows.

    Raises if no rows match (callers should append() instead of silently
    failing). Schema-validates the resulting row(s) end-to-end.
    """
    workbook_path = Path(workbook_path)
    schema_p = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
    schema = _load_schema(str(schema_p))

    if sheet not in (schema.get("sheets") or {}):
        raise SchemaSheetMismatchError(f"sheet {sheet!r} not in schema")
    columns = _ordered_columns(schema, sheet)
    _check_writer_scope(schema, sheet, writer)

    # Lock + load.
    state_dir = _state_dir(
        Path(state_root) if state_root else None, workbook_path, project_slug
    )
    lock_path = state_dir / "excel.lock"
    fd = _acquire_lock(lock_path)
    try:
        wb = _load_or_new(workbook_path)
        _ensure_sheet_with_header(wb, sheet, columns)
        ws = wb[sheet]

        col_index = {c["name"]: idx for idx, c in enumerate(columns, start=1)}
        affected_rows: list[dict] = []
        # Walk data rows starting from row 2.
        for row_idx in range(2, (ws.max_row or 1) + 1):
            current = {
                c["name"]: ws.cell(row=row_idx, column=col_index[c["name"]]).value
                for c in columns
            }
            if all(current.get(k) == v for k, v in where.items()):
                merged = {**current, **set_}
                affected_rows.append(merged)
                # Validate the merged row before flushing.
                validator = _build_row_validator(schema, sheet)
                _validate_rows([merged], validator)
                _check_formula_policy([merged])
                _check_cell_lengths([merged])
                # Apply mutation to ws cells.
                for k, v in set_.items():
                    if k not in col_index:
                        raise RowSchemaError(f"unknown column in set_: {k!r}")
                    ws.cell(row=row_idx, column=col_index[k], value=v)

        if not affected_rows:
            raise RowSchemaError(
                f"update matched 0 rows in {sheet!r} for where={where!r}"
            )

        backup_path = _backup(workbook_path, state_dir)
        _atomic_save(wb, workbook_path)
        _rotate_backups(state_dir)
    finally:
        _release_lock(fd, lock_path)

    event_id = _emit_provenance(
        project_slug=project_slug,
        sheet=sheet,
        rows_affected=len(affected_rows),
        state_root=state_dir.parent,  # _state lives at projects/{slug}/_state
        operation="project_excel",
    )
    return WriteResult(
        workbook_path=workbook_path,
        sheet=sheet,
        rows_affected=len(affected_rows),
        backup_path=backup_path,
        event_id=event_id,
    )


# ---------------------------------------------------------------------------
# Internals — core write/append driver
# ---------------------------------------------------------------------------

def _write_or_append(
    workbook_path: Path | str,
    sheet: str,
    rows: list[dict],
    project_slug: str,
    *,
    schema_path: Path | str | None,
    state_root: Path | str | None,
    writer: str | None,
    mode: str,
) -> WriteResult:
    if mode != "append":
        raise TransactionError(f"unsupported mode: {mode!r}")

    workbook_path = Path(workbook_path)
    schema_p = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
    schema = _load_schema(str(schema_p))

    # 1. Schema layer: sheet exists.
    if sheet not in (schema.get("sheets") or {}):
        raise SchemaSheetMismatchError(f"sheet {sheet!r} not in schema")
    columns = _ordered_columns(schema, sheet)

    # 2. Writer scope (master_task only, currently).
    _check_writer_scope(schema, sheet, writer)

    # 3. Per-row schema validation.
    validator = _build_row_validator(schema, sheet)
    if not isinstance(rows, list):
        raise RowSchemaError("rows must be a list of dicts")
    _validate_rows(rows, validator)

    # 4. Formula policy + cell length cap.
    _check_formula_policy(rows)
    _check_cell_lengths(rows)

    # 5. Lock + load + write under flock.
    state_dir = _state_dir(
        Path(state_root) if state_root else None, workbook_path, project_slug
    )
    lock_path = state_dir / "excel.lock"
    fd = _acquire_lock(lock_path)
    try:
        wb = _load_or_new(workbook_path)
        _ensure_sheet_with_header(wb, sheet, columns)
        ws = wb[sheet]

        # Append rows in canonical column order.
        write_row = _next_data_row(ws)
        col_index = {c["name"]: idx for idx, c in enumerate(columns, start=1)}
        for row in rows:
            for k, v in row.items():
                if k not in col_index:
                    # Validator allowed this key (additionalProperties:true);
                    # we still skip writing it because it has no column.
                    continue
                ws.cell(row=write_row, column=col_index[k], value=v)
            write_row += 1

        # 6. Backup → atomic save → rotation. Order matters: backup must
        # complete before save, save must complete before rotation prunes.
        backup_path = _backup(workbook_path, state_dir)
        _atomic_save(wb, workbook_path)
        _rotate_backups(state_dir)
    finally:
        _release_lock(fd, lock_path)

    # 7. Emit provenance event into events.jsonl. Failure to emit does not
    # roll back the write — Excel is on disk, the lack of an event is its
    # own anomaly, surfaced via the raised exception.
    event_id = _emit_provenance(
        project_slug=project_slug,
        sheet=sheet,
        rows_affected=len(rows),
        state_root=state_dir.parent,
        operation="project_excel",
    )

    return WriteResult(
        workbook_path=workbook_path,
        sheet=sheet,
        rows_affected=len(rows),
        backup_path=backup_path,
        event_id=event_id,
    )


# ---------------------------------------------------------------------------
# Internals — event emission helper
# ---------------------------------------------------------------------------

def _emit_provenance(
    *,
    project_slug: str,
    sheet: str,
    rows_affected: int,
    state_root: Path,
    operation: str,
) -> str:
    """
    Emit a provenance event recording the write. The events_writer module
    resolves the events.jsonl path from {workspace_root}/projects/{slug}/_state/.
    state_root here is the project directory — its parent is `projects/`,
    grandparent is the workspace root expected by events_writer.
    """
    workspace_root = state_root.parent.parent  # projects/<slug> → projects → workspace
    run_id = events_writer.next_run_id(project_slug, workspace_root=workspace_root)
    # source.kind enum (events.schema): manual | tool_computed | sf_csv | *_mcp.
    # An Excel projection by transaction.py is internally tool_computed —
    # it's the engine writing structured output, not a human key-by-key edit.
    result = events_writer.append_provenance(
        project_id=project_slug,
        run_id=run_id,
        source={"kind": "tool_computed"},
        operation=operation,
        target_excel_sheet=sheet,
        rows_written=rows_affected,
        workspace_root=workspace_root,
    )
    return result.event_id


# ---------------------------------------------------------------------------
# Module export list
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "WriteResult",
    "TransactionError",
    "SchemaSheetMismatchError",
    "RowSchemaError",
    "FormulaPolicyViolation",
    "CellValueTooLongError",
    "LockHeldError",
    "BackupDirUnwritableError",
    "WorkbookLockedByExcelError",
    "WorkbookCorruptError",
    "WriterScopeError",
    "WRITER_REGISTRY",
    "WRITER_REGISTRY_ENFORCEMENT",
    "writer_registry_status",
    "write",
    "append",
    "update",
)
