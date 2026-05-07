#!/usr/bin/env python3
"""portfolio_monthly_roundup.py — Phase 9 W-E5 reporting transform.

Multi-project LOCAL aggregator for the MONTHLY cadence. READ-ONLY:
events.jsonl (work-kind, 30d) + master.xlsx#dashboard KPIs +
master.xlsx#completed_work category split + EditorialOverrides
precedence. Outputs: master.xlsx#none + projects/_portfolio/
outputs/reports/{date}-portfolio-monthly-roundup.md + inbox/local/
{date}-portfolio-monthly-roundup.json. Mirrors W-E3+W-E4+W-D1.
Schema: portfolio-config v1.1 + monthly-report v1.0 (7-sec subset).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DAY_OF_MONTH_MIN, DAY_OF_MONTH_MAX = 1, 31
HOUR_MIN, HOUR_MAX = 0, 23
SLA_MIN_DAYS, SLA_MAX_DAYS = 1, 30
PRIORITY_MIN, PRIORITY_MAX = 1, 10
ACTIVE_PROJECTS_MAX = 8
OVERRIDE_RATIONALE_MIN_LEN = 10
DELTA_WINDOW_DAYS = 30
WRITER_NAME = "portfolio_monthly_roundup"
DEFAULT_CADENCE = "monthly"
ALLOWED_CADENCE: tuple[str, ...] = ("weekly", "biweekly", "monthly")

DASHBOARD_KPI_CELLS: tuple[tuple[str, str], ...] = (
    ("R10", "total_pillars"),
    ("R47", "master_task_total"), ("R48", "master_task_done"),
    ("R49", "master_task_todo"), ("R50", "master_task_ongoing"),
    ("R51", "cannibalization_count"), ("R52", "quick_wins_count"),
    ("R59", "last_audit_date"),
)

COMPLETED_CATEGORY_TO_SECTION: Mapping[str, str] = {
    "tech_seo": "tech_seo_done", "tech_fix": "tech_seo_done",
    "schema_fix": "tech_seo_done",
    "content_revise": "content_revised",
    "content_new": "new_content", "pillar_launch": "new_content",
}

MONTHLY_SECTIONS_SUBSET: tuple[str, ...] = (
    "exec_summary", "keywords_up", "pages_up",
    "tech_seo_done", "content_revised", "new_content", "next_month_plan",
)

class PortfolioMonthlyRoundupError(Exception): pass
class PortfolioConfigMissingError(PortfolioMonthlyRoundupError): pass
class PortfolioConfigInvalidError(PortfolioMonthlyRoundupError): pass
class PortfolioConfigSchemaError(PortfolioMonthlyRoundupError): pass
class ActiveProjectsCeilingError(PortfolioMonthlyRoundupError): pass
class ReadOnlyContractViolation(PortfolioMonthlyRoundupError): pass
class WorkspaceRootUnsetError(PortfolioMonthlyRoundupError): pass
class EditorialOverrideRationaleError(PortfolioMonthlyRoundupError): pass
class PeriodEndParseError(PortfolioMonthlyRoundupError): pass

@dataclass(frozen=True)
class ResolvedOverrides:
    has_override: bool; effective_priority: int; effective_cadence: str
    effective_sla_days: int; override_rationale: str; ramp_plan: str

@dataclass(frozen=True)
class ProjectRollup:
    slug: str; display_name: str; workspace_path: str
    master_xlsx_path: str | None; overrides: ResolvedOverrides
    kpis: dict; completed_counts: dict; work_events: int
    warnings: list = field(default_factory=list)

@dataclass(frozen=True)
class PortfolioMonthlyRoundup:
    period_start: str; period_end: str; generated_at: str
    portfolio_id: str; display_name: str
    projects: tuple[ProjectRollup, ...]
    totals_tasks_done: int; totals_new_content: int
    totals_content_revised: int; totals_tech_seo_done: int
    totals_work_events: int; skipped_projects: int

def _validate_cadence_monthly(cadence: Mapping[str, Any]) -> None:
    if not isinstance(cadence, Mapping):
        raise PortfolioConfigSchemaError("cadence must be an object")
    mr = cadence.get("monthly_roundup")
    if not isinstance(mr, Mapping):
        raise PortfolioConfigSchemaError("cadence.monthly_roundup required (object)")
    dom, hour = mr.get("day_of_month"), mr.get("hour")
    if not isinstance(dom, int) or dom < DAY_OF_MONTH_MIN or dom > DAY_OF_MONTH_MAX:
        raise PortfolioConfigSchemaError(
            f"cadence.monthly_roundup.day_of_month={dom!r} not in "
            f"[{DAY_OF_MONTH_MIN}, {DAY_OF_MONTH_MAX}]")
    if not isinstance(hour, int) or hour < HOUR_MIN or hour > HOUR_MAX:
        raise PortfolioConfigSchemaError(
            f"cadence.monthly_roundup.hour={hour!r} not in [{HOUR_MIN}, {HOUR_MAX}]")

def validate_portfolio_config_for_roundup(
    config: Mapping[str, Any], schema: Mapping[str, Any] | None = None,
) -> None:
    """Optional Draft7 + domain validation."""
    if schema is not None:
        try: from jsonschema import Draft7Validator
        except ImportError as exc:  # pragma: no cover
            raise PortfolioConfigInvalidError("jsonschema required") from exc
        errs = sorted(Draft7Validator(dict(schema)).iter_errors(dict(config)),
                      key=lambda e: list(e.absolute_path))
        if errs:
            raise PortfolioConfigInvalidError(
                "portfolio.config.json failed Draft 7 validation: "
                + "; ".join(f"{list(e.absolute_path)}: {e.message}" for e in errs))
    active = list(config.get("active_projects") or [])
    if len(active) > ACTIVE_PROJECTS_MAX:
        raise ActiveProjectsCeilingError(
            f"active_projects has {len(active)} entries; ceiling is "
            f"{ACTIVE_PROJECTS_MAX} (schema maxItems).")
    cq = config.get("cross_query") or {}
    if "read_only" in cq and cq.get("read_only") is not True:
        raise ReadOnlyContractViolation(
            f"cross_query.read_only must be true (schema const), got {cq.get('read_only')!r}.")

def _check_int_range(name: str, val: Any, lo: int, hi: int) -> int:
    if not isinstance(val, int) or val < lo or val > hi:
        raise PortfolioConfigSchemaError(
            f"editorial_overrides.{name}={val!r} not in [{lo}, {hi}]"
        )
    return val

def resolve_editorial_overrides(
    entry: Mapping[str, Any], *, portfolio_sla_days: int,
) -> ResolvedOverrides:
    """Apply EditorialOverrides on top of ActiveProjectEntry defaults.
    override_rationale minLength 10 mandatory when any override set."""
    base_priority = int(entry.get("priority") or PRIORITY_MAX)
    eo = entry.get("editorial_overrides")
    if not isinstance(eo, Mapping):
        return ResolvedOverrides(False, base_priority, DEFAULT_CADENCE,
                                 portfolio_sla_days, "", "")
    has_field = any(k in eo for k in ("sla_days", "priority", "cadence"))
    rationale = eo.get("override_rationale", "")
    rationale = rationale.strip() if isinstance(rationale, str) else ""
    eff_priority = (_check_int_range("priority", eo.get("priority"),
                                     PRIORITY_MIN, PRIORITY_MAX)
                    if "priority" in eo else base_priority)
    eff_cadence = DEFAULT_CADENCE
    if "cadence" in eo:
        c = eo.get("cadence")
        if c not in ALLOWED_CADENCE:
            raise PortfolioConfigSchemaError(
                f"editorial_overrides.cadence={c!r} not in {ALLOWED_CADENCE}")
        eff_cadence = c
    eff_sla = (_check_int_range("sla_days", eo.get("sla_days"),
                                SLA_MIN_DAYS, SLA_MAX_DAYS)
               if "sla_days" in eo else portfolio_sla_days)
    if has_field and len(rationale) < OVERRIDE_RATIONALE_MIN_LEN:
        raise EditorialOverrideRationaleError(
            f"editorial_overrides has override field(s) but "
            f"override_rationale is {len(rationale)} chars; minLength "
            f"is {OVERRIDE_RATIONALE_MIN_LEN}.")
    ramp = eo.get("ramp_plan", "")
    ramp = ramp.strip() if isinstance(ramp, str) else ""
    return ResolvedOverrides(has_field, eff_priority, eff_cadence,
                             eff_sla, rationale, ramp)

def _parse_iso_date(value: str) -> _date:
    if not isinstance(value, str) or not value:
        raise PeriodEndParseError(f"period_end must be non-empty ISO date, got {value!r}")
    try: return _date.fromisoformat(value)
    except ValueError as exc:
        raise PeriodEndParseError(f"period_end {value!r} not valid ISO date: {exc}") from exc

def _parse_iso_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PortfolioMonthlyRoundupError(f"timestamp must be non-empty ISO, got {value!r}")
    raw = value.strip()
    if raw.endswith("Z"): raw = raw[:-1] + "+00:00"
    try: dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise PortfolioMonthlyRoundupError(f"timestamp {value!r} not ISO-8601: {exc}") from exc
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def resolve_period_end(
    cadence: Mapping[str, Any], *, today: _date, explicit: str | None = None,
) -> _date:
    """Most recent occurrence of cadence.monthly_roundup.day_of_month
    on or before today; explicit override wins."""
    if explicit is not None: return _parse_iso_date(explicit)
    _validate_cadence_monthly(cadence)
    target_dom = cadence["monthly_roundup"]["day_of_month"]
    for back in range(0, 32):
        candidate = today - timedelta(days=back)
        if candidate.day == target_dom: return candidate
    raise PeriodEndParseError(
        f"could not resolve period_end for day_of_month={target_dom!r}")

def read_events_in_window(
    events_path: Path, *, window_start: datetime, window_end: datetime,
    event_kind: str = "work",
) -> list[dict[str, Any]]:
    """Read events.jsonl, return matching entries. Empty/missing -> []."""
    if not events_path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line: continue
        try: evt = json.loads(line)
        except json.JSONDecodeError: continue
        if not isinstance(evt, dict): continue
        if evt.get("event_kind") != event_kind: continue
        ts_raw = evt.get("timestamp")
        if not isinstance(ts_raw, str): continue
        try: ts = _parse_iso_timestamp(ts_raw)
        except PortfolioMonthlyRoundupError: continue
        if window_start <= ts <= window_end:
            out.append(evt)
    return out

def read_dashboard_kpis(workbook_path: Path) -> dict[str, Any]:
    """Read 8 dashboard KPI cells. READ-ONLY."""
    seed = {kpi: "" for _cell, kpi in DASHBOARD_KPI_CELLS}
    if not workbook_path.exists(): return seed
    try: from openpyxl import load_workbook  # type: ignore[import-not-found]
    except ImportError: return seed  # pragma: no cover
    out: dict[str, Any] = dict(seed)
    wb = load_workbook(filename=str(workbook_path), read_only=True, data_only=True)
    try:
        if "dashboard" not in wb.sheetnames: return seed
        ws = wb["dashboard"]
        for cell, kpi in DASHBOARD_KPI_CELLS:
            v = ws[cell].value
            if v is None: out[kpi] = ""
            elif isinstance(v, _date): out[kpi] = v.isoformat()
            else: out[kpi] = str(v).strip()
    finally:
        wb.close()
    return out

def read_completed_work_window(
    workbook_path: Path, *, window_start: _date, window_end: _date,
) -> dict[str, int]:
    """Bucket completed_work rows in window into monthly-report sections.
    READ-ONLY. data_start_row=5; cols A-F per master-excel schema."""
    counts = {"tech_seo_done": 0, "content_revised": 0, "new_content": 0}
    if not workbook_path.exists(): return counts
    try: from openpyxl import load_workbook  # type: ignore[import-not-found]
    except ImportError: return counts  # pragma: no cover
    wb = load_workbook(filename=str(workbook_path), read_only=True, data_only=True)
    try:
        if "completed_work" not in wb.sheetnames: return counts
        for row in wb["completed_work"].iter_rows(
                min_row=5, min_col=1, max_col=6, values_only=True):
            if row is None: continue
            row_date = _coerce_date_cell(row[3]) if len(row) > 3 else None
            row_category = (str(row[4]).strip() if len(row) > 4
                            and isinstance(row[4], str) else "")
            if row_date is None or not row_category: continue
            if not (window_start <= row_date <= window_end): continue
            section = COMPLETED_CATEGORY_TO_SECTION.get(row_category)
            if section is not None:
                counts[section] += 1
    finally:
        wb.close()
    return counts

def _coerce_date_cell(value: Any) -> _date | None:
    if value is None or value == "": return None
    if isinstance(value, datetime): return value.date()
    if isinstance(value, _date): return value
    if not isinstance(value, str): return None
    try: return _date.fromisoformat(value.strip())
    except ValueError: return None

def _resolve_workspace_root(workspace_root: Path | str | None) -> Path:
    if workspace_root is not None:
        return Path(workspace_root).expanduser().resolve()
    env_val = os.environ.get("PSEO_WORKSPACE_ROOT")
    if env_val:
        return Path(env_val).expanduser().resolve()
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        if (parent / ".pse-workspace").exists(): return parent
    raise WorkspaceRootUnsetError(
        "PSEO_WORKSPACE_ROOT env unset, no workspace_root passed, "
        "and no .pse-workspace marker found."
    )

def _safe_int(v: Any) -> int:
    s = str(v).strip()
    if not s: return 0
    try: return int(float(s))
    except (TypeError, ValueError): return 0

def aggregate_project(
    *, entry: Mapping[str, Any], workspace_root: Path,
    portfolio_sla_days: int, period_start: _date, period_end: _date,
    now: datetime,
) -> ProjectRollup:
    """Compute one project's 30-day monthly rollup. READ-ONLY."""
    slug = entry.get("slug")
    if not isinstance(slug, str) or not slug:
        raise PortfolioConfigSchemaError(
            f"active_projects[].slug must be non-empty string, got {slug!r}")
    display_name = str(entry.get("display_name") or slug)
    workspace_path = str(entry.get("workspace_path") or slug)
    overrides = resolve_editorial_overrides(entry, portfolio_sla_days=portfolio_sla_days)
    p = Path(workspace_path).expanduser()
    if p.is_absolute():
        project_root = p
    else:
        candidate = workspace_root / "projects" / slug
        project_root = candidate if candidate.exists() else (workspace_root / workspace_path)
    master_xlsx = project_root / "master.xlsx"
    ws_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    we_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=timezone.utc)
    warnings: list = []
    if not master_xlsx.exists():
        warnings.append(f"master.xlsx not found at {master_xlsx}")
    events = read_events_in_window(
        project_root / "_state" / "events.jsonl",
        window_start=ws_dt, window_end=we_dt, event_kind="work")
    kpis = read_dashboard_kpis(master_xlsx)
    completed = read_completed_work_window(
        master_xlsx, window_start=period_start, window_end=period_end)
    return ProjectRollup(
        slug=slug, display_name=display_name, workspace_path=workspace_path,
        master_xlsx_path=str(master_xlsx) if master_xlsx.exists() else None,
        overrides=overrides, kpis=kpis, completed_counts=completed,
        work_events=len(events), warnings=warnings)

def build_portfolio_roundup(
    *, portfolio_config: Mapping[str, Any], workspace_root: Path,
    now: datetime, period_end: str | None = None,
) -> PortfolioMonthlyRoundup:
    """Top-level pure aggregator. Idempotent."""
    if not isinstance(portfolio_config, Mapping):
        raise PortfolioConfigSchemaError("portfolio_config must be a JSON object")
    cadence = portfolio_config.get("cadence")
    if cadence is None:
        raise PortfolioConfigSchemaError("portfolio.config.json missing 'cadence'")
    sla = portfolio_config.get("slas") or {}
    portfolio_sla_days = int(sla.get("weekly_sync_max_days") or 7)
    if portfolio_sla_days < SLA_MIN_DAYS or portfolio_sla_days > SLA_MAX_DAYS:
        raise PortfolioConfigSchemaError(
            f"slas.weekly_sync_max_days={portfolio_sla_days!r} not in "
            f"[{SLA_MIN_DAYS}, {SLA_MAX_DAYS}]")
    projects_in = portfolio_config.get("active_projects")
    if not isinstance(projects_in, list) or not projects_in:
        raise PortfolioConfigSchemaError(
            "portfolio.config.json active_projects must be non-empty list")
    if len(projects_in) > ACTIVE_PROJECTS_MAX:
        raise ActiveProjectsCeilingError(
            f"active_projects has {len(projects_in)} entries; ceiling is "
            f"{ACTIVE_PROJECTS_MAX}.")
    period_end_d = resolve_period_end(cadence, today=now.date(), explicit=period_end)
    period_start_d = period_end_d - timedelta(days=DELTA_WINDOW_DAYS - 1)
    rollups: list[ProjectRollup] = []
    skipped = 0
    for entry in projects_in:
        if not isinstance(entry, Mapping):
            raise PortfolioConfigSchemaError(
                f"active_projects entry must be object, got {type(entry).__name__}")
        rollup = aggregate_project(
            entry=entry, workspace_root=workspace_root,
            portfolio_sla_days=portfolio_sla_days,
            period_start=period_start_d, period_end=period_end_d, now=now)
        rollups.append(rollup)
        if rollup.master_xlsx_path is None: skipped += 1
    rollups.sort(key=lambda r: (r.overrides.effective_priority, r.slug))
    pid = str(portfolio_config.get("portfolio_id") or "")
    return PortfolioMonthlyRoundup(
        period_start=period_start_d.isoformat(),
        period_end=period_end_d.isoformat(),
        generated_at=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        portfolio_id=pid,
        display_name=str(portfolio_config.get("display_name") or pid),
        projects=tuple(rollups),
        totals_tasks_done=sum(_safe_int(r.kpis.get("master_task_done")) for r in rollups),
        totals_new_content=sum(r.completed_counts.get("new_content", 0) for r in rollups),
        totals_content_revised=sum(r.completed_counts.get("content_revised", 0) for r in rollups),
        totals_tech_seo_done=sum(r.completed_counts.get("tech_seo_done", 0) for r in rollups),
        totals_work_events=sum(r.work_events for r in rollups),
        skipped_projects=skipped)

def render_projects_kpi_table(roundup: PortfolioMonthlyRoundup) -> str:
    header = ("| slug | priority | cadence | tasks_done | new_content | "
              "content_revised | tech_seo_done | work_events |\n"
              "|---|---:|---|---:|---:|---:|---:|---:|")
    if not roundup.projects:
        return header + "\n| _(no active projects)_ | - | - | 0 | 0 | 0 | 0 | 0 |"
    lines = [header]
    for r in roundup.projects:
        td = r.kpis.get("master_task_done")
        td_str = str(td) if td not in ("", None) else "0"
        cc = r.completed_counts
        lines.append(
            f"| {r.slug} | {r.overrides.effective_priority} | "
            f"{r.overrides.effective_cadence} | {td_str} | "
            f"{cc.get('new_content', 0)} | {cc.get('content_revised', 0)} | "
            f"{cc.get('tech_seo_done', 0)} | {r.work_events} |")
    return "\n".join(lines)

def render_editorial_overrides_notes(roundup: PortfolioMonthlyRoundup) -> str:
    overridden = [r for r in roundup.projects if r.overrides.has_override]
    if not overridden:
        return "_(no per-project EditorialOverrides active)_"
    parts: list[str] = []
    for r in overridden:
        o = r.overrides
        ramp_str = f" — ramp_plan: {o.ramp_plan}" if o.ramp_plan else ""
        parts.append(
            f"- **{r.slug}** (priority={o.effective_priority}, "
            f"cadence={o.effective_cadence}, sla_days={o.effective_sla_days}): "
            f"{o.override_rationale}{ramp_str}")
    return "\n".join(parts)

def render_totals_summary(roundup: PortfolioMonthlyRoundup) -> str:
    return (
        f"Toplam tasks_done={roundup.totals_tasks_done}, "
        f"new_content={roundup.totals_new_content}, "
        f"content_revised={roundup.totals_content_revised}, "
        f"tech_seo_done={roundup.totals_tech_seo_done}, "
        f"work_events={roundup.totals_work_events} "
        f"(skipped={roundup.skipped_projects}, projects={len(roundup.projects)})")

def build_template_vars(
    roundup: PortfolioMonthlyRoundup, *, scope: str = "portfolio",
) -> dict[str, str]:
    return {
        "period_start": roundup.period_start, "period_end": roundup.period_end,
        "generated_at": roundup.generated_at, "scope": scope,
        "portfolio_id": roundup.portfolio_id,
        "display_name": roundup.display_name,
        "projects_count": str(len(roundup.projects)),
        "skipped_projects": str(roundup.skipped_projects),
        "projects_kpi_table": render_projects_kpi_table(roundup),
        "editorial_overrides_notes": render_editorial_overrides_notes(roundup),
        "totals_summary": render_totals_summary(roundup),
        "totals_tasks_done": str(roundup.totals_tasks_done),
        "totals_new_content": str(roundup.totals_new_content),
        "totals_content_revised": str(roundup.totals_content_revised),
        "totals_tech_seo_done": str(roundup.totals_tech_seo_done),
        "totals_work_events": str(roundup.totals_work_events)}

def build_snapshot(roundup: PortfolioMonthlyRoundup) -> dict[str, Any]:
    return {
        "writer": WRITER_NAME, "period_start": roundup.period_start,
        "period_end": roundup.period_end, "generated_at": roundup.generated_at,
        "portfolio_id": roundup.portfolio_id, "display_name": roundup.display_name,
        "skipped_projects": roundup.skipped_projects,
        "totals": {
            "tasks_done": roundup.totals_tasks_done,
            "new_content": roundup.totals_new_content,
            "content_revised": roundup.totals_content_revised,
            "tech_seo_done": roundup.totals_tech_seo_done,
            "work_events": roundup.totals_work_events,
        },
        "monthly_sections_subset": list(MONTHLY_SECTIONS_SUBSET),
        "projects": [{
            "slug": r.slug, "display_name": r.display_name,
            "workspace_path": r.workspace_path,
            "master_xlsx_path": r.master_xlsx_path,
            "kpis": dict(r.kpis), "completed_counts": dict(r.completed_counts),
            "work_events": r.work_events,
            "overrides_resolved": {
                "has_override": r.overrides.has_override,
                "effective_priority": r.overrides.effective_priority,
                "effective_cadence": r.overrides.effective_cadence,
                "effective_sla_days": r.overrides.effective_sla_days,
                "override_rationale": r.overrides.override_rationale,
                "ramp_plan": r.overrides.ramp_plan,
            },
            "warnings": list(r.warnings),
        } for r in roundup.projects],
    }

def render_roundup_markdown(
    *, roundup: PortfolioMonthlyRoundup, template_path: Path,
) -> str:
    """Render Markdown via string.Template (matches render_template.py)."""
    from string import Template
    if not template_path.exists():
        raise PortfolioMonthlyRoundupError(f"template not found: {template_path}")
    tpl = Template(template_path.read_text(encoding="utf-8"))
    try: return tpl.safe_substitute(build_template_vars(roundup))
    except KeyError as exc:
        raise PortfolioMonthlyRoundupError(
            f"template references unknown variable: {exc.args[0]}") from exc

#: Patterns assembled at runtime so the literals do not appear verbatim
#: in the source (the self-check below greps the file).
_FORBIDDEN_WRITE_PATTERNS: tuple[str, ...] = (
    "." + "save(",
    "." + "delete(",
    "transaction" + "." + "append(",
    "transaction" + "." + "update(",
    "transaction" + "." + "delete(",
    "events_writer" + "." + "append",
)

def assert_read_only_module() -> None:
    """Verify this module's source has no write call sites. Used by gate #11."""
    src = Path(__file__).read_text(encoding="utf-8")
    hits = [p for p in _FORBIDDEN_WRITE_PATTERNS if p in src]
    if hits:
        raise ReadOnlyContractViolation(
            f"portfolio_monthly_roundup source contains forbidden write patterns: {hits}."
        )

def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build portfolio monthly roundup (READ-ONLY).")
    parser.add_argument("--portfolio-config", required=True)
    parser.add_argument("--workspace-root", default=None)
    parser.add_argument("--period-end", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--template", default=None)
    parser.add_argument("--now", default=None)
    args = parser.parse_args(argv)
    cfg_path = Path(args.portfolio_config)
    if not cfg_path.exists():
        print(f"portfolio.config.json not found: {cfg_path}", file=sys.stderr); return 2
    try:
        portfolio_config = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"portfolio.config.json read failed: {exc}", file=sys.stderr); return 2
    schema_path = _REPO_ROOT / "schemas" / "portfolio-config.schema.json"
    schema = None
    if schema_path.is_file():
        try: schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError): schema = None
    try:
        validate_portfolio_config_for_roundup(portfolio_config, schema)
    except (PortfolioConfigInvalidError, ActiveProjectsCeilingError,
            ReadOnlyContractViolation, PortfolioConfigSchemaError) as exc:
        print(f"config validation failed: {exc}", file=sys.stderr); return 1
    workspace_root = _resolve_workspace_root(args.workspace_root)
    now = _parse_iso_timestamp(args.now) if args.now else _now_utc()
    roundup = build_portfolio_roundup(
        portfolio_config=portfolio_config, workspace_root=workspace_root,
        now=now, period_end=args.period_end,
    )
    out_dir = Path(args.output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    snap_path = out_dir / f"{roundup.period_end}-portfolio-monthly-roundup.json"
    snap_path.write_text(json.dumps(build_snapshot(roundup), ensure_ascii=False,
                                    indent=2, sort_keys=True), encoding="utf-8")
    template_path = (Path(args.template) if args.template
                     else _REPO_ROOT / "templates" / "reports"
                     / "portfolio-monthly-roundup.template.md")
    report_path = out_dir / f"{roundup.period_end}-portfolio-monthly-roundup.md"
    report_path.write_text(
        render_roundup_markdown(roundup=roundup, template_path=template_path),
        encoding="utf-8",
    )
    print(json.dumps({
        "writer": WRITER_NAME, "report_path": str(report_path),
        "snapshot_path": str(snap_path),
        "period_start": roundup.period_start, "period_end": roundup.period_end,
        "totals_tasks_done": roundup.totals_tasks_done,
        "totals_new_content": roundup.totals_new_content,
        "totals_content_revised": roundup.totals_content_revised,
        "totals_tech_seo_done": roundup.totals_tech_seo_done,
        "totals_work_events": roundup.totals_work_events,
        "skipped_projects": roundup.skipped_projects,
    }, ensure_ascii=False))
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

# __all__ omitted to keep transform <600 lines (ADR-027); public API is
# every top-level non-underscore symbol (test imports rely on this).
