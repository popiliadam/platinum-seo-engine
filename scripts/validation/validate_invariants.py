#!/usr/bin/env python3
"""
validate_invariants.py — 20 hand-coded invariant rules for drift-check.

Owned by `skills/governance/drift-check/SKILL.md`. Read-only governance:
loads `master.xlsx` (data_only=True, read_only=True) plus _state side
files (events.jsonl, workflows/*.json, backups/) and evaluates the 20
invariants enumerated in §17.2 + the F-08 quick-wins URL subset rule.

Each rule is a small Python function. NO DSL — that is a Phase 6+
refactor candidate. The intent now is auditable, hand-verifiable
governance: every rule is one short function, every function returns
the same shape:

    {
        "id":        "F-XX",
        "severity":  "CRITICAL|HIGH|MEDIUM",
        "verdict":   "PASS|FAIL|SKIP",
        "evidence":  "human-readable one-liner",
        "rule":      "rule body verbatim",
        "category":  "csr_foundation|csr_data|...",
        "auto_repair_available": bool,
        "manual_triage": bool,                  # F-15-style routing
        "affected_sheets": [...],               # optional
        "sample_violations": [...],             # optional, ≤ 20
        "affected_rows": int,                   # optional
    }

Aggregation per §17.2:
  - any FAIL with severity CRITICAL  → overall RED
  - any FAIL with severity HIGH      → overall RED, UNLESS manual_triage
                                       routes it to AMBER
  - any FAIL with severity MEDIUM    → overall AMBER
  - any SKIP                         → overall AMBER (not RED)
  - all PASS                         → overall GREEN

The aggregator also produces a schema-valid `consistency-report.json`
ready to be persisted by drift-check step 5.

Refs:
  - schemas/master-excel.schema.json (definitions: statusEnum,
    severityEnum; per-sheet column shape)
  - schemas/events.schema.json (event_kind=audit + run_id integer)
  - schemas/workflow-run.schema.json (schema_version const "1.0",
    run_id pattern)
  - schemas/consistency-report.schema.json (output shape)
  - schemas/cross-sheet-invariants.json (rule registry)
  - rules/excel-discipline.md (master.xlsx never mutated outside
    transaction.py)
  - ADR-018 (statusEnum 7-value), ADR-019 (workflow schema_version),
    ADR-020 (event_kind=workflow), ADR-021 (_state path).
"""

from __future__ import annotations

import functools
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MASTER_EXCEL_SCHEMA = _REPO_ROOT / "schemas" / "master-excel.schema.json"
_CONSISTENCY_REPORT_SCHEMA = _REPO_ROOT / "schemas" / "consistency-report.schema.json"

_STATUS_ENUM_7: frozenset[str] = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})
_SEVERITY_ENUM_4: frozenset[str] = frozenset({
    "LOW", "MEDIUM", "HIGH", "CRITICAL",
})

_WORKFLOW_SCHEMA_VERSION = "1.0"
_WORKFLOW_RUN_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]*-\d{4}-\d{2}-\d{2}-[a-f0-9]{4}$"
)

_EVENTS_MAX_LINE_BYTES = 64 * 1024
_EXCEL_CELL_MAX_CHARS = 32_767
_BACKUP_KEEP_LIMIT = 7
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign",
                    "utm_term", "utm_content", "gclid", "fbclid"}

_SAMPLE_CAP = 20  # consistency-report.schema.json sample_violations.maxItems


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DriftCheckError(Exception):
    """Base class for drift-check evaluator errors."""


class UnknownRuleError(DriftCheckError):
    """Aggregator received an unknown rule id."""


class ConsistencyReportInvalidError(DriftCheckError):
    """Built consistency-report failed schema validation."""


# ---------------------------------------------------------------------------
# Workbook helpers (read-only)
# ---------------------------------------------------------------------------

def _has_sheet(workbook: Any, name: str) -> bool:
    try:
        return name in workbook.sheetnames
    except Exception:
        return False


def _resolve_header_row(workbook: Any, sheet: str) -> int:
    """Phase 14 W3-W2-C-a: resolve the effective header row for `sheet` by
    consulting `schemas/master-excel.schema.json` first, falling back to row 1.

    Logic:
      1. If schema declares `sheets[sheet].header_row` as an int and the
         workbook's row at that index has at least one non-None cell whose
         text matches one of the schema's `required_columns`, trust schema.
      2. Otherwise (legacy / synthetic test workbook with header at row 1),
         return 1.

    This keeps existing tests (header at row 1) PASS while enabling W1
    bootstrap workbooks (header at row 3/4/5 per schema) to validate
    without 4 mechanical header-parse FAILs (F-01/F-05/F-17/F-18).
    """
    try:
        schema = _load_master_excel_schema()
    except Exception:
        return 1
    sdef = schema.get("sheets", {}).get(sheet) or {}
    hr = sdef.get("header_row")
    if not isinstance(hr, int) or hr <= 0:
        return 1
    required = sdef.get("required_columns") or []
    if not required:
        return 1
    if not _has_sheet(workbook, sheet):
        return 1
    ws = workbook[sheet]
    try:
        # Probe the schema-declared header row using openpyxl's read-only
        # iter_rows (min_row/max_row inclusive, 1-indexed).
        probe = next(ws.iter_rows(min_row=hr, max_row=hr, values_only=True))
    except (StopIteration, Exception):
        return 1
    if probe is None:
        return 1
    # required_columns entries are dicts ({"col","name",...}); extract name.
    def _col_name(c: Any) -> str:
        if isinstance(c, dict):
            return str(c.get("name") or "").strip()
        return str(c).strip()

    required_set = {n for n in (_col_name(c) for c in required) if n}
    probe_set = {str(c).strip() for c in probe if c is not None}
    # Require at least 50% header match to trust schema header_row.
    if required_set and probe_set:
        overlap = len(required_set & probe_set)
        if overlap >= max(1, len(required_set) // 2):
            return hr
    return 1


def _iter_rows_as_dicts(workbook: Any, sheet: str) -> list[dict]:
    """Read sheet header row + data rows; return list of dicts keyed
    by header column name. Returns [] if sheet missing or has 0 data rows.
    Read-only friendly (uses iter_rows + values_only=True).

    Phase 14 W3-W2-C-a: header row is resolved via `_resolve_header_row`
    (schema authority dynamic, fallback to row 1)."""
    if not _has_sheet(workbook, sheet):
        return []
    ws = workbook[sheet]
    header_row_idx = _resolve_header_row(workbook, sheet)
    try:
        header_tuple = next(ws.iter_rows(
            min_row=header_row_idx, max_row=header_row_idx, values_only=True))
    except StopIteration:
        return []
    if header_tuple is None:
        return []
    headers = [str(h) if h is not None else "" for h in header_tuple]
    out: list[dict] = []
    for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
        if row is None:
            continue
        if all(c is None for c in row):
            continue
        d: dict[str, Any] = {}
        for i, val in enumerate(row):
            key = headers[i] if i < len(headers) else f"col_{i}"
            d[key] = val
        out.append(d)
    return out


def _normalize_url(raw: Any) -> str:
    """D-03 idempotent URL normalize. Mirrors quickwins_transform.normalize_url
    spec (lowercase scheme+host, strip default ports, drop fragment, sort+
    filter query, trailing slash collapse except root). Inputs that aren't
    str-shaped are returned as the empty string so callers can detect drift."""
    if not isinstance(raw, str) or not raw:
        return ""
    parts = urlsplit(raw.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    host = netloc
    port = ""
    if ":" in netloc and not netloc.endswith("]"):
        host, _, port = netloc.rpartition(":")
    host = host.lower()
    try:
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        pass
    default_ports = {"http": "80", "https": "443"}
    if port and port == default_ports.get(scheme):
        port = ""
    netloc = host + (f":{port}" if port else "")
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in _TRACKING_PARAMS
    ]
    pairs.sort()
    query = urlencode(pairs)
    return urlunsplit((scheme, netloc, path, query, ""))


# ---------------------------------------------------------------------------
# Workspace path helpers
# ---------------------------------------------------------------------------

def _resolve_workspace_root(workspace_root: Path | None) -> Path:
    if workspace_root is not None:
        return Path(workspace_root)
    env = os.getenv("PSEO_WORKSPACE_ROOT")
    if env:
        return Path(env)
    raise DriftCheckError(
        "workspace_root not provided and PSEO_WORKSPACE_ROOT not set"
    )


def _project_dir(project_slug: str, workspace_root: Path | None) -> Path:
    return _resolve_workspace_root(workspace_root) / "projects" / project_slug


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------

def _make_result(
    *, id_: str, severity: str, verdict: str, evidence: str,
    rule: str, category: str,
    auto_repair_available: bool = False,
    manual_triage: bool = False,
    affected_sheets: list[str] | None = None,
    sample_violations: list[str] | None = None,
    affected_rows: int | None = None,
) -> dict:
    out: dict[str, Any] = {
        "id": id_,
        "severity": severity,
        "verdict": verdict,
        "evidence": evidence,
        "rule": rule,
        "category": category,
        "auto_repair_available": auto_repair_available,
        "manual_triage": manual_triage,
    }
    if affected_sheets:
        out["affected_sheets"] = affected_sheets
    if sample_violations is not None:
        out["sample_violations"] = sample_violations[:_SAMPLE_CAP]
    if affected_rows is not None:
        out["affected_rows"] = affected_rows
    return out


# ---------------------------------------------------------------------------
# CRITICAL (5)
# ---------------------------------------------------------------------------

def check_F_01(workbook: Any, project_slug: str, **_) -> dict:
    """master_task.status ⊆ statusEnum 7-value."""
    rule = "master_task.status ⊆ statusEnum {TODO,ONGOING,EXISTS,DONE,BLOCKED,DEFERRED,CANCELED}"
    if not _has_sheet(workbook, "master_task"):
        return _make_result(
            id_="F-01", severity="CRITICAL", verdict="SKIP",
            evidence="master_task sheet missing — pilot wb may be sparse",
            rule=rule, category="csr_foundation",
            affected_sheets=["master_task"],
        )
    rows = _iter_rows_as_dicts(workbook, "master_task")
    bad: list[str] = []
    for r in rows:
        s = r.get("status")
        if s is None:
            continue
        if str(s) not in _STATUS_ENUM_7:
            bad.append(str(s))
    if bad:
        return _make_result(
            id_="F-01", severity="CRITICAL", verdict="FAIL",
            evidence=f"{len(bad)} master_task.status values outside 7-value enum",
            rule=rule, category="csr_foundation",
            affected_sheets=["master_task"],
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-01", severity="CRITICAL", verdict="PASS",
        evidence=f"all {len(rows)} master_task.status values within 7-value enum",
        rule=rule, category="csr_foundation",
        affected_sheets=["master_task"],
    )


def _check_no_excel_formula(workbook: Any, project_slug: str, *,
                            id_: str, formula_token: str) -> dict:
    """F-02/F-03/F-04: ensure dashboard sheet has no live Excel formula
    of the given token. Read-only mode returns None or strings; data_only
    cached values are not formulas. We sniff for a leading '=' + token."""
    rule = f"dashboard sheet contains no live `={formula_token}(...)` formulas"
    if not _has_sheet(workbook, "dashboard"):
        return _make_result(
            id_=id_, severity="CRITICAL", verdict="SKIP",
            evidence="dashboard sheet missing — pilot wb may be sparse",
            rule=rule, category="csr_foundation",
            affected_sheets=["dashboard"],
        )
    ws = workbook["dashboard"]
    bad: list[str] = []
    for row in ws.iter_rows(values_only=True):
        if row is None:
            continue
        for cell in row:
            if isinstance(cell, str) and cell.startswith("=" + formula_token):
                bad.append(cell)
                if len(bad) >= _SAMPLE_CAP:
                    break
        if len(bad) >= _SAMPLE_CAP:
            break
    if bad:
        return _make_result(
            id_=id_, severity="CRITICAL", verdict="FAIL",
            evidence=f"{len(bad)} `={formula_token}(...)` formula cells found in dashboard",
            rule=rule, category="csr_foundation",
            affected_sheets=["dashboard"],
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_=id_, severity="CRITICAL", verdict="PASS",
        evidence=f"no `={formula_token}(...)` formulas detected in dashboard",
        rule=rule, category="csr_foundation",
        affected_sheets=["dashboard"],
    )


def check_F_02(workbook: Any, project_slug: str, **_) -> dict:
    return _check_no_excel_formula(workbook, project_slug,
                                    id_="F-02", formula_token="COUNTIF")


def check_F_03(workbook: Any, project_slug: str, **_) -> dict:
    return _check_no_excel_formula(workbook, project_slug,
                                    id_="F-03", formula_token="SUMIF")


def check_F_04(workbook: Any, project_slug: str, **_) -> dict:
    return _check_no_excel_formula(workbook, project_slug,
                                    id_="F-04", formula_token="AVERAGEIF")


def check_F_05(workbook: Any, project_slug: str, **_) -> dict:
    """schema_version field per-sheet present: every present sheet has a
    header row whose column count matches the master-excel schema's
    required_columns.

    Phase 14 W3-W2-C-a: header row index resolved via schema authority
    (`_resolve_header_row`) — fallback to row 1 for legacy/synthetic
    workbooks. Eliminates the 4 mechanical header-parse FAILs
    (F-01/F-05/F-17/F-18) seen on W1 bootstrap workspace master.xlsx where
    sheets use header_row=3/4/5 per schema."""
    rule = "every sheet present in workbook matches its master-excel.schema header column count"
    schema = _load_master_excel_schema()
    sheets_def = schema.get("sheets", {})
    bad: list[str] = []
    checked = 0
    for sheet_name in workbook.sheetnames:
        sdef = sheets_def.get(sheet_name)
        if not sdef:
            continue  # unknown sheet — outside this check's scope
        required = sdef.get("required_columns")
        if not required:
            continue  # dashboard uses required_cells, not required_columns
        ws = workbook[sheet_name]
        header_row_idx = _resolve_header_row(workbook, sheet_name)
        try:
            header = next(ws.iter_rows(
                min_row=header_row_idx, max_row=header_row_idx,
                values_only=True))
        except StopIteration:
            bad.append(f"{sheet_name}: no header row at row {header_row_idx}")
            continue
        if header is None:
            bad.append(f"{sheet_name}: no header row at row {header_row_idx}")
            continue
        n_header = sum(1 for h in header if h is not None)
        if n_header != len(required):
            bad.append(f"{sheet_name}: header at row {header_row_idx} has "
                       f"{n_header} cols, schema requires {len(required)}")
        checked += 1
    if checked == 0:
        return _make_result(
            id_="F-05", severity="CRITICAL", verdict="SKIP",
            evidence="no schema-known sheets found (pilot wb sparse)",
            rule=rule, category="schema_validation",
        )
    if bad:
        return _make_result(
            id_="F-05", severity="CRITICAL", verdict="FAIL",
            evidence=f"{len(bad)}/{checked} sheets fail schema column count",
            rule=rule, category="schema_validation",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-05", severity="CRITICAL", verdict="PASS",
        evidence=f"all {checked} schema-known sheets match column count",
        rule=rule, category="schema_validation",
    )


# ---------------------------------------------------------------------------
# HIGH (10)
# ---------------------------------------------------------------------------

def check_F_08(workbook: Any, project_slug: str, **_) -> dict:
    """quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url).

    F2 flag: pilot wb is sparse (sf-import has not yet populated
    crawl_sitemap; gsc_performance also absent). When BOTH reference
    sheets are missing we promote this from RED to AMBER via the
    manual_triage routing. Wave 2 closeout will re-evaluate after
    sf-import (W-R) completes.
    """
    rule = "quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url)"
    if not _has_sheet(workbook, "quick_wins"):
        return _make_result(
            id_="F-08", severity="HIGH", verdict="SKIP",
            evidence="quick_wins sheet missing — nothing to check",
            rule=rule, category="csr_foundation",
            affected_sheets=["quick_wins"],
        )
    has_sitemap = _has_sheet(workbook, "crawl_sitemap")
    has_perf = _has_sheet(workbook, "gsc_performance")
    # F2 flag (sparse-pilot tolerance): if EITHER reference sheet is
    # missing, F-08 cannot be authoritatively evaluated. Route through
    # manual_triage so the aggregator surfaces AMBER (not RED) and the
    # Wave 2 closeout (sf-import + gsc_performance loader complete) can
    # re-run drift-check for an authoritative GREEN/RED.
    pilot_sparse = not (has_sitemap and has_perf)
    qw_rows = _iter_rows_as_dicts(workbook, "quick_wins")
    qw_urls = {_normalize_url(r.get("url")) for r in qw_rows
               if r.get("url") is not None}
    qw_urls.discard("")
    ref_urls: set[str] = set()
    if has_sitemap:
        for r in _iter_rows_as_dicts(workbook, "crawl_sitemap"):
            # crawl_sitemap layout uses "value" col for URL per schema (cat/metric/value).
            for key in ("url", "value"):
                v = r.get(key)
                if v is not None:
                    n = _normalize_url(v)
                    if n:
                        ref_urls.add(n)
                    break
    if has_perf:
        for r in _iter_rows_as_dicts(workbook, "gsc_performance"):
            v = r.get("url")
            if v is not None:
                n = _normalize_url(v)
                if n:
                    ref_urls.add(n)
    orphans = sorted(qw_urls - ref_urls)
    if orphans:
        evidence = (
            f"{len(orphans)} quick_wins URLs not in "
            f"(crawl_sitemap ∪ gsc_performance)"
        )
        if pilot_sparse:
            evidence += (
                " — pilot wb sparse (has_sitemap="
                f"{has_sitemap}, has_perf={has_perf}); routed to "
                "AMBER via manual_triage (F2 flag, re-eval after sf-import)"
            )
        return _make_result(
            id_="F-08", severity="HIGH", verdict="FAIL",
            evidence=evidence,
            rule=rule, category="csr_foundation",
            affected_sheets=["quick_wins", "crawl_sitemap", "gsc_performance"],
            manual_triage=pilot_sparse,
            sample_violations=orphans,
            affected_rows=len(orphans),
        )
    return _make_result(
        id_="F-08", severity="HIGH", verdict="PASS",
        evidence=f"all {len(qw_urls)} quick_wins URLs covered by reference sheets",
        rule=rule, category="csr_foundation",
        affected_sheets=["quick_wins", "crawl_sitemap", "gsc_performance"],
    )


def check_F_09(workbook: Any, project_slug: str, **_) -> dict:
    """master_task.task_id unique."""
    rule = "master_task.task_id is unique across all rows"
    if not _has_sheet(workbook, "master_task"):
        return _make_result(
            id_="F-09", severity="HIGH", verdict="SKIP",
            evidence="master_task sheet missing",
            rule=rule, category="csr_foundation",
            affected_sheets=["master_task"],
        )
    rows = _iter_rows_as_dicts(workbook, "master_task")
    seen: dict[str, int] = {}
    dups: list[str] = []
    for r in rows:
        tid = r.get("task_id")
        if tid is None:
            continue
        s = str(tid)
        seen[s] = seen.get(s, 0) + 1
    for k, v in seen.items():
        if v > 1:
            dups.append(f"{k}×{v}")
    if dups:
        return _make_result(
            id_="F-09", severity="HIGH", verdict="FAIL",
            evidence=f"{len(dups)} duplicate task_id values",
            rule=rule, category="csr_foundation",
            affected_sheets=["master_task"],
            sample_violations=dups,
            affected_rows=len(dups),
        )
    return _make_result(
        id_="F-09", severity="HIGH", verdict="PASS",
        evidence=f"{len(seen)} unique task_id values across {len(rows)} rows",
        rule=rule, category="csr_foundation",
        affected_sheets=["master_task"],
    )


def check_F_10(workbook: Any, project_slug: str, **_) -> dict:
    """quick_wins.url D-03 normalize idempotent."""
    rule = "url_normalizer(x) == x for every quick_wins.url (D-03 idempotent)"
    if not _has_sheet(workbook, "quick_wins"):
        return _make_result(
            id_="F-10", severity="HIGH", verdict="SKIP",
            evidence="quick_wins sheet missing",
            rule=rule, category="url_normalization",
            affected_sheets=["quick_wins"],
        )
    rows = _iter_rows_as_dicts(workbook, "quick_wins")
    drift: list[str] = []
    n_total = 0
    for r in rows:
        u = r.get("url")
        if not isinstance(u, str) or not u:
            continue
        n_total += 1
        n1 = _normalize_url(u)
        n2 = _normalize_url(n1)
        if u != n1 or n1 != n2:
            drift.append(f"{u} -> {n1}")
    if drift:
        return _make_result(
            id_="F-10", severity="HIGH", verdict="FAIL",
            evidence=f"{len(drift)} quick_wins URLs not idempotent under D-03",
            rule=rule, category="url_normalization",
            affected_sheets=["quick_wins"],
            sample_violations=drift,
            affected_rows=len(drift),
        )
    return _make_result(
        id_="F-10", severity="HIGH", verdict="PASS",
        evidence=f"all {n_total} quick_wins URLs are D-03 idempotent",
        rule=rule, category="url_normalization",
        affected_sheets=["quick_wins"],
    )


def check_F_11(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """workflow-run schema_version "1.0" across all _state/workflows/*.json."""
    rule = 'every _state/workflows/*.json has schema_version == "1.0"'
    pdir = _project_dir(project_slug, workspace_root)
    wf_dir = pdir / "_state" / "workflows"
    if not wf_dir.is_dir():
        return _make_result(
            id_="F-11", severity="HIGH", verdict="SKIP",
            evidence="_state/workflows/ directory missing — no workflow runs yet",
            rule=rule, category="schema_validation",
        )
    bad: list[str] = []
    n = 0
    for p in sorted(wf_dir.glob("*.json")):
        n += 1
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bad.append(f"{p.name}: unreadable")
            continue
        sv = obj.get("schema_version")
        if sv != _WORKFLOW_SCHEMA_VERSION:
            bad.append(f"{p.name}: schema_version={sv!r}")
    if n == 0:
        return _make_result(
            id_="F-11", severity="HIGH", verdict="SKIP",
            evidence="no workflow run files present",
            rule=rule, category="schema_validation",
        )
    if bad:
        return _make_result(
            id_="F-11", severity="HIGH", verdict="FAIL",
            evidence=f"{len(bad)}/{n} workflow runs have wrong schema_version",
            rule=rule, category="schema_validation",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-11", severity="HIGH", verdict="PASS",
        evidence=f"all {n} workflow runs have schema_version 1.0",
        rule=rule, category="schema_validation",
    )


def check_F_12(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """events.jsonl append-only — read previous-snapshot line count from
    a sidecar `_state/events.snapshot.json` if present; if not, assume
    monotonic and PASS, but record the current line count for next run."""
    rule = "events.jsonl line count is monotonically non-decreasing"
    pdir = _project_dir(project_slug, workspace_root)
    events_path = pdir / "_state" / "events.jsonl"
    if not events_path.exists():
        return _make_result(
            id_="F-12", severity="HIGH", verdict="SKIP",
            evidence="events.jsonl missing — no events emitted yet",
            rule=rule, category="row_count_integrity",
        )
    cur_lines = sum(1 for _ in events_path.open("r", encoding="utf-8")
                    if _.strip())
    snap_path = pdir / "_state" / "events.snapshot.json"
    prev_lines = 0
    if snap_path.exists():
        try:
            prev_lines = int(json.loads(snap_path.read_text("utf-8")).get("lines", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            prev_lines = 0
    if cur_lines < prev_lines:
        return _make_result(
            id_="F-12", severity="HIGH", verdict="FAIL",
            evidence=f"events.jsonl shrank: {prev_lines} → {cur_lines}",
            rule=rule, category="row_count_integrity",
            affected_rows=prev_lines - cur_lines,
        )
    return _make_result(
        id_="F-12", severity="HIGH", verdict="PASS",
        evidence=f"events.jsonl line count {cur_lines} ≥ snapshot {prev_lines}",
        rule=rule, category="row_count_integrity",
    )


def check_F_13(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """provenance.run_id integer (per events.schema)."""
    rule = "every event_kind=provenance row has run_id of integer type"
    pdir = _project_dir(project_slug, workspace_root)
    events_path = pdir / "_state" / "events.jsonl"
    if not events_path.exists():
        return _make_result(
            id_="F-13", severity="HIGH", verdict="SKIP",
            evidence="events.jsonl missing",
            rule=rule, category="schema_validation",
        )
    bad: list[str] = []
    n_prov = 0
    for line in events_path.open("r", encoding="utf-8"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("event_kind") != "provenance":
            continue
        n_prov += 1
        rid = obj.get("run_id")
        if not isinstance(rid, int) or isinstance(rid, bool):
            bad.append(f"event_id={obj.get('event_id')!r} run_id={rid!r}")
    if bad:
        return _make_result(
            id_="F-13", severity="HIGH", verdict="FAIL",
            evidence=f"{len(bad)}/{n_prov} provenance events have non-int run_id",
            rule=rule, category="schema_validation",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-13", severity="HIGH", verdict="PASS",
        evidence=f"all {n_prov} provenance events have integer run_id",
        rule=rule, category="schema_validation",
    )


def check_F_14(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """workflow.workflow_run_id pattern (per events.schema)."""
    rule = "every event_kind=workflow row has workflow_run_id matching {slug}-YYYY-MM-DD-{hash4}"
    pdir = _project_dir(project_slug, workspace_root)
    events_path = pdir / "_state" / "events.jsonl"
    if not events_path.exists():
        return _make_result(
            id_="F-14", severity="HIGH", verdict="SKIP",
            evidence="events.jsonl missing",
            rule=rule, category="schema_validation",
        )
    bad: list[str] = []
    n_wf = 0
    for line in events_path.open("r", encoding="utf-8"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("event_kind") != "workflow":
            continue
        n_wf += 1
        wri = obj.get("workflow_run_id")
        if not isinstance(wri, str) or not _WORKFLOW_RUN_ID_PATTERN.match(wri):
            bad.append(f"event_id={obj.get('event_id')!r} workflow_run_id={wri!r}")
    if bad:
        return _make_result(
            id_="F-14", severity="HIGH", verdict="FAIL",
            evidence=f"{len(bad)}/{n_wf} workflow events have malformed workflow_run_id",
            rule=rule, category="schema_validation",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-14", severity="HIGH", verdict="PASS",
        evidence=f"all {n_wf} workflow events have well-formed workflow_run_id",
        rule=rule, category="schema_validation",
    )


def check_F_15(workbook: Any, project_slug: str, **_) -> dict:
    """Manual triage placeholder — populates manual_review_required[]
    when cannibalization sheet has rows AND any AMBER routing condition
    is detected. Always classified as HIGH+manual_triage so the
    aggregator routes to AMBER (NOT RED). Per §9.3 F-15 requires human
    decision (intent-matrix overlap)."""
    rule = "cannibalization intent çakışması intent-matrix.json ile tutarlı (manual triage)"
    if not _has_sheet(workbook, "cannibalization"):
        return _make_result(
            id_="F-15", severity="HIGH", verdict="SKIP",
            evidence="cannibalization sheet missing — no manual triage required",
            rule=rule, category="csr_foundation",
            affected_sheets=["cannibalization"],
            manual_triage=True,
        )
    rows = _iter_rows_as_dicts(workbook, "cannibalization")
    if not rows:
        return _make_result(
            id_="F-15", severity="HIGH", verdict="PASS",
            evidence="cannibalization sheet present but empty — nothing to triage",
            rule=rule, category="csr_foundation",
            affected_sheets=["cannibalization"],
            manual_triage=True,
        )
    samples = []
    for r in rows[:_SAMPLE_CAP]:
        pair = r.get("conflict_pair") or r.get("pair") or "?"
        samples.append(str(pair))
    return _make_result(
        id_="F-15", severity="HIGH", verdict="FAIL",
        evidence=f"{len(rows)} cannibalization rows require manual intent-matrix triage",
        rule=rule, category="csr_foundation",
        affected_sheets=["cannibalization"],
        manual_triage=True,
        sample_violations=samples,
        affected_rows=len(rows),
    )


def check_F_16(workbook: Any, project_slug: str, **_) -> dict:
    """quick_wins.url ⊆ opportunity URL set (cross-sheet foreign key).

    opportunity.assigned_url_action stores `url | action` — we extract
    the URL prefix before normalizing.
    """
    rule = "quick_wins.url ⊆ opportunity.assigned_url_action URL set"
    if not (_has_sheet(workbook, "quick_wins") and _has_sheet(workbook, "opportunity")):
        return _make_result(
            id_="F-16", severity="HIGH", verdict="SKIP",
            evidence="quick_wins or opportunity sheet missing",
            rule=rule, category="csr_foundation",
            affected_sheets=["quick_wins", "opportunity"],
        )
    qw_urls = set()
    for r in _iter_rows_as_dicts(workbook, "quick_wins"):
        u = r.get("url")
        if isinstance(u, str) and u:
            qw_urls.add(_normalize_url(u))
    qw_urls.discard("")

    opp_urls = set()
    for r in _iter_rows_as_dicts(workbook, "opportunity"):
        au = r.get("assigned_url_action")
        if isinstance(au, str) and au:
            url_part = au.split("|", 1)[0].strip()
            if url_part:
                opp_urls.add(_normalize_url(url_part))
    opp_urls.discard("")

    orphans = sorted(qw_urls - opp_urls)
    if orphans:
        return _make_result(
            id_="F-16", severity="HIGH", verdict="FAIL",
            evidence=f"{len(orphans)} quick_wins URLs not present in opportunity",
            rule=rule, category="csr_foundation",
            affected_sheets=["quick_wins", "opportunity"],
            sample_violations=orphans,
            affected_rows=len(orphans),
        )
    return _make_result(
        id_="F-16", severity="HIGH", verdict="PASS",
        evidence=f"all {len(qw_urls)} quick_wins URLs covered by opportunity",
        rule=rule, category="csr_foundation",
        affected_sheets=["quick_wins", "opportunity"],
    )


def check_F_17(workbook: Any, project_slug: str, **_) -> dict:
    """severity column ⊆ severityEnum 4-value (LOW/MEDIUM/HIGH/CRITICAL).

    Scans every sheet that the master-excel schema marks as carrying a
    severity-typed column (priority/level/impact with $ref severityEnum).
    """
    rule = "every severity-typed cell ∈ severityEnum {LOW,MEDIUM,HIGH,CRITICAL}"
    schema = _load_master_excel_schema()
    sheets_def = schema.get("sheets", {})
    severity_columns: list[tuple[str, str]] = []  # (sheet, col_name)
    for sheet, sdef in sheets_def.items():
        for col in sdef.get("required_columns", []):
            ref = col.get("ref")
            if ref and ref.endswith("/severityEnum"):
                severity_columns.append((sheet, col["name"]))

    bad: list[str] = []
    n_checked = 0
    affected_sheets: set[str] = set()
    for sheet, col_name in severity_columns:
        if not _has_sheet(workbook, sheet):
            continue
        for r in _iter_rows_as_dicts(workbook, sheet):
            v = r.get(col_name)
            if v is None or v == "":
                continue
            n_checked += 1
            if str(v).upper() not in _SEVERITY_ENUM_4:
                bad.append(f"{sheet}.{col_name}={v!r}")
                affected_sheets.add(sheet)
    if n_checked == 0:
        return _make_result(
            id_="F-17", severity="HIGH", verdict="SKIP",
            evidence="no severity-typed cells found across present sheets",
            rule=rule, category="csr_data",
        )
    if bad:
        return _make_result(
            id_="F-17", severity="HIGH", verdict="FAIL",
            evidence=f"{len(bad)}/{n_checked} severity cells outside 4-value enum",
            rule=rule, category="csr_data",
            affected_sheets=sorted(affected_sheets),
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-17", severity="HIGH", verdict="PASS",
        evidence=f"all {n_checked} severity cells within 4-value enum",
        rule=rule, category="csr_data",
    )


# ---------------------------------------------------------------------------
# MEDIUM (5)
# ---------------------------------------------------------------------------

def check_F_18(workbook: Any, project_slug: str, **_) -> dict:
    """master_task.created_at (col K) parses as ISO 8601."""
    rule = "every master_task.created_date is ISO 8601 parseable"
    if not _has_sheet(workbook, "master_task"):
        return _make_result(
            id_="F-18", severity="MEDIUM", verdict="SKIP",
            evidence="master_task sheet missing",
            rule=rule, category="csr_data",
            affected_sheets=["master_task"],
        )
    rows = _iter_rows_as_dicts(workbook, "master_task")
    bad: list[str] = []
    n = 0
    for r in rows:
        v = r.get("created_date")
        if v is None or v == "":
            continue
        n += 1
        if isinstance(v, datetime):
            continue  # openpyxl already parsed it
        try:
            datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            bad.append(f"row_value={v!r}")
    if bad:
        return _make_result(
            id_="F-18", severity="MEDIUM", verdict="FAIL",
            evidence=f"{len(bad)}/{n} master_task.created_date values not ISO 8601",
            rule=rule, category="csr_data",
            affected_sheets=["master_task"],
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-18", severity="MEDIUM", verdict="PASS",
        evidence=f"all {n} master_task.created_date values parse as ISO 8601",
        rule=rule, category="csr_data",
        affected_sheets=["master_task"],
    )


def check_F_19(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """Optional field default present: project.config.json carries
    locale + market keys (so downstream skills don't drop into None
    branches). Defaults are dotted: defaults.locale / defaults.market
    OR root-level locale / market."""
    rule = "project.config.json declares locale + market (root or defaults.*)"
    pdir = _project_dir(project_slug, workspace_root)
    cfg_path = pdir / "project.config.json"
    if not cfg_path.exists():
        return _make_result(
            id_="F-19", severity="MEDIUM", verdict="SKIP",
            evidence=f"{cfg_path.name} missing",
            rule=rule, category="schema_validation",
        )
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _make_result(
            id_="F-19", severity="MEDIUM", verdict="FAIL",
            evidence=f"project.config.json unparseable: {exc}",
            rule=rule, category="schema_validation",
        )
    defaults = cfg.get("defaults") or {}
    has_locale = bool(cfg.get("locale") or defaults.get("locale"))
    has_market = bool(cfg.get("market") or defaults.get("market"))
    missing = [
        k for k, ok in (("locale", has_locale), ("market", has_market))
        if not ok
    ]
    if missing:
        return _make_result(
            id_="F-19", severity="MEDIUM", verdict="FAIL",
            evidence=f"project.config.json missing keys: {missing}",
            rule=rule, category="schema_validation",
            sample_violations=missing,
        )
    return _make_result(
        id_="F-19", severity="MEDIUM", verdict="PASS",
        evidence="project.config.json declares both locale and market",
        rule=rule, category="schema_validation",
    )


def check_F_20(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """events.jsonl per-line size <64 KB cap."""
    rule = "every events.jsonl line is < 64 KiB (events_writer cap)"
    pdir = _project_dir(project_slug, workspace_root)
    events_path = pdir / "_state" / "events.jsonl"
    if not events_path.exists():
        return _make_result(
            id_="F-20", severity="MEDIUM", verdict="SKIP",
            evidence="events.jsonl missing",
            rule=rule, category="row_count_integrity",
        )
    bad: list[str] = []
    n = 0
    with events_path.open("rb") as fh:
        for i, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            n += 1
            if len(line) > _EVENTS_MAX_LINE_BYTES:
                bad.append(f"line {i}: {len(line)} bytes")
    if bad:
        return _make_result(
            id_="F-20", severity="MEDIUM", verdict="FAIL",
            evidence=f"{len(bad)}/{n} events.jsonl lines exceed 64 KiB cap",
            rule=rule, category="row_count_integrity",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-20", severity="MEDIUM", verdict="PASS",
        evidence=f"all {n} events.jsonl lines under 64 KiB cap",
        rule=rule, category="row_count_integrity",
    )


def check_F_21(workbook: Any, project_slug: str, **_) -> dict:
    """Every cell value <32767 chars (Excel hard limit)."""
    rule = "every cell value < 32767 chars (Excel/openpyxl hard limit)"
    bad: list[str] = []
    n_cells = 0
    for sheet_name in workbook.sheetnames:
        ws = workbook[sheet_name]
        for row in ws.iter_rows(values_only=True):
            if row is None:
                continue
            for cell in row:
                if cell is None:
                    continue
                n_cells += 1
                if isinstance(cell, str) and len(cell) >= _EXCEL_CELL_MAX_CHARS:
                    bad.append(f"{sheet_name}: {len(cell)} chars")
                    if len(bad) >= _SAMPLE_CAP:
                        break
            if len(bad) >= _SAMPLE_CAP:
                break
        if len(bad) >= _SAMPLE_CAP:
            break
    if bad:
        return _make_result(
            id_="F-21", severity="MEDIUM", verdict="FAIL",
            evidence=f"{len(bad)} cells at/over 32767 char Excel limit",
            rule=rule, category="schema_validation",
            sample_violations=bad,
            affected_rows=len(bad),
        )
    return _make_result(
        id_="F-21", severity="MEDIUM", verdict="PASS",
        evidence=f"all {n_cells} non-null cells within 32767 char limit",
        rule=rule, category="schema_validation",
    )


def check_F_22(workbook: Any, project_slug: str, *,
               workspace_root: Path | None = None, **_) -> dict:
    """backup directory FIFO 7 (transaction.py keep-7 rotation).

    auto_repair_available=True — exceeding the cap is mechanically
    fixable by deleting oldest backups.
    """
    rule = "_state/backups/master keeps at most 7 .xlsx backups (FIFO)"
    pdir = _project_dir(project_slug, workspace_root)
    backups_dir = pdir / "_state" / "backups" / "master"
    if not backups_dir.is_dir():
        return _make_result(
            id_="F-22", severity="MEDIUM", verdict="SKIP",
            evidence="backups dir missing — no writes have occurred",
            rule=rule, category="file_hash_integrity",
            auto_repair_available=True,
        )
    backups = sorted(backups_dir.glob("master-*.xlsx"))
    n = len(backups)
    if n > _BACKUP_KEEP_LIMIT:
        return _make_result(
            id_="F-22", severity="MEDIUM", verdict="FAIL",
            evidence=f"{n} backups present, FIFO cap is {_BACKUP_KEEP_LIMIT}",
            rule=rule, category="file_hash_integrity",
            auto_repair_available=True,
            affected_rows=n - _BACKUP_KEEP_LIMIT,
            sample_violations=[p.name for p in backups[:_SAMPLE_CAP]],
        )
    return _make_result(
        id_="F-22", severity="MEDIUM", verdict="PASS",
        evidence=f"{n} backups within FIFO cap {_BACKUP_KEEP_LIMIT}",
        rule=rule, category="file_hash_integrity",
        auto_repair_available=True,
    )


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

_RULE_FUNCTIONS = (
    # CRITICAL
    check_F_01, check_F_02, check_F_03, check_F_04, check_F_05,
    # HIGH
    check_F_08, check_F_09, check_F_10, check_F_11, check_F_12,
    check_F_13, check_F_14, check_F_15, check_F_16, check_F_17,
    # MEDIUM
    check_F_18, check_F_19, check_F_20, check_F_21, check_F_22,
)


def evaluate_all(workbook: Any, project_slug: str, *,
                 workspace_root: Path | None = None) -> list[dict]:
    """Run every rule function, return list of result dicts in
    declaration order. Each function may raise; caller handles DURUR-3."""
    out: list[dict] = []
    for fn in _RULE_FUNCTIONS:
        result = fn(workbook, project_slug, workspace_root=workspace_root)
        out.append(result)
    return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

_VALID_RULE_IDS: frozenset[str] = frozenset(
    fn.__name__.replace("check_", "").replace("_", "-")
    for fn in _RULE_FUNCTIONS
)


def aggregate_verdicts(rule_results: list[dict]) -> dict:
    """Aggregate per §17.2 verdict logic. Returns a small summary dict.

    Raises UnknownRuleError if a result.id is outside the registered set
    — that would mean the caller injected a synthetic rule outside the
    20-rule contract.
    """
    pass_count = warn_count = fail_count = 0
    overall = "GREEN"
    manual_review_required: list[str] = []
    auto_repair_available: list[str] = []

    saw_red = False
    saw_amber = False

    for r in rule_results:
        rid = r.get("id")
        if rid not in _VALID_RULE_IDS:
            raise UnknownRuleError(
                f"unknown rule id {rid!r} — outside 20-rule registry"
            )
        verdict = r.get("verdict")
        severity = r.get("severity", "MEDIUM")
        manual = bool(r.get("manual_triage"))
        repair = bool(r.get("auto_repair_available"))
        if repair:
            auto_repair_available.append(rid)

        if verdict == "PASS":
            pass_count += 1
        elif verdict == "SKIP":
            warn_count += 1
            saw_amber = True
        elif verdict == "FAIL":
            fail_count += 1
            if manual:
                # F-15-style routing: stay AMBER, surface for human triage.
                saw_amber = True
                manual_review_required.append(rid)
            elif severity in ("CRITICAL", "HIGH"):
                saw_red = True
            else:  # MEDIUM/LOW
                saw_amber = True
        else:
            # Defensive: unknown verdict is treated as AMBER skip.
            warn_count += 1
            saw_amber = True

    if saw_red:
        overall = "RED"
    elif saw_amber:
        overall = "AMBER"
    else:
        overall = "GREEN"

    return {
        "overall": overall,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "total": len(rule_results),
        "manual_review_required": manual_review_required,
        "auto_repair_available": auto_repair_available,
    }


# ---------------------------------------------------------------------------
# Consistency-report builder
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=2)
def _load_schema_cached(schema_path: str) -> dict:
    return json.loads(Path(schema_path).read_text(encoding="utf-8"))


def _load_master_excel_schema() -> dict:
    return _load_schema_cached(str(_MASTER_EXCEL_SCHEMA))


def _load_consistency_report_schema() -> dict:
    return _load_schema_cached(str(_CONSISTENCY_REPORT_SCHEMA))


def _verdict_to_check_verdict(verdict: str) -> str:
    """Map our internal PASS/FAIL/SKIP to the schema's PASS/WARN/FAIL."""
    if verdict == "PASS":
        return "PASS"
    if verdict == "FAIL":
        return "FAIL"
    return "WARN"  # SKIP and unknown -> WARN


def build_consistency_report(
    *,
    rule_results: list[dict],
    aggregation: dict,
    project_id: str,
    report_id: int,
    generated_at: str,
    run_id: int | None = None,
    notes: str | None = None,
) -> dict:
    """Assemble + schema-validate a consistency-report.json payload.

    Raises ConsistencyReportInvalidError on schema failure (DURUR-6).
    """
    by_category: dict[str, dict[str, int]] = {}
    checks: list[dict] = []
    for r in rule_results:
        check_verdict = _verdict_to_check_verdict(r.get("verdict", "SKIP"))
        # Re-route F-15-style manual triage so the schema-level check
        # records WARN (not FAIL) — keeps the per-row severity but the
        # verdict reflects the routing decision.
        if r.get("manual_triage") and check_verdict == "FAIL":
            check_verdict = "WARN"
        check: dict[str, Any] = {
            "check_id": r["id"],
            "category": r.get("category", "csr_foundation"),
            "verdict": check_verdict,
        }
        if "severity" in r:
            check["severity"] = r["severity"]
        if "rule" in r:
            check["rule"] = r["rule"]
        if "evidence" in r:
            check["details"] = r["evidence"]
        if "affected_sheets" in r:
            check["affected_sheets"] = r["affected_sheets"]
        if "sample_violations" in r:
            check["sample_violations"] = r["sample_violations"][:_SAMPLE_CAP]
        if "affected_rows" in r:
            check["affected_rows"] = r["affected_rows"]
        if r.get("auto_repair_available"):
            check["auto_repair_available"] = True
        checks.append(check)

        cat = check["category"]
        bucket = by_category.setdefault(cat, {"pass": 0, "warn": 0, "fail": 0})
        if check_verdict == "PASS":
            bucket["pass"] += 1
        elif check_verdict == "WARN":
            bucket["warn"] += 1
        else:
            bucket["fail"] += 1

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "report_id": report_id,
        "generated_at": generated_at,
        "project_id": project_id,
        "verdict": aggregation["overall"],
        "checks": checks,
        "summary": {
            "total_checks": aggregation["total"],
            "pass_count": aggregation["pass_count"],
            "warn_count": aggregation["warn_count"],
            "fail_count": aggregation["fail_count"],
            "by_category": by_category,
        },
    }
    if run_id is not None:
        report["run_id"] = run_id
    if aggregation.get("manual_review_required"):
        report["manual_review_required"] = aggregation["manual_review_required"]
    if aggregation.get("auto_repair_available"):
        report["auto_repair_performed"] = []  # nothing performed; flag presence
    if notes:
        report["notes"] = notes

    schema = _load_consistency_report_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda e: e.path)
    if errors:
        msgs = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"{loc}: {err.message}")
        raise ConsistencyReportInvalidError("; ".join(msgs))
    return report


# ---------------------------------------------------------------------------
# Module export list
# ---------------------------------------------------------------------------

__all__: Iterable[str] = (
    "DriftCheckError",
    "UnknownRuleError",
    "ConsistencyReportInvalidError",
    "evaluate_all",
    "aggregate_verdicts",
    "build_consistency_report",
    "check_F_01", "check_F_02", "check_F_03", "check_F_04", "check_F_05",
    "check_F_08", "check_F_09", "check_F_10", "check_F_11", "check_F_12",
    "check_F_13", "check_F_14", "check_F_15", "check_F_16", "check_F_17",
    "check_F_18", "check_F_19", "check_F_20", "check_F_21", "check_F_22",
)
