#!/usr/bin/env python3
"""task_outcome.py — did a finished task actually move its page? (O-01)

Every DONE master_task row has a url and a done_date, but nothing ever pulled
GSC for that url afterwards: 1,163 finished tasks, ~4 with an "after" value.
intervention_outcome.py (R-138) covers quick-wins cohorts only and never ran.

This module generalises R-138 to every task type:

* windows  — ``before`` = 28 days ending the day before done_date,
             ``after_28`` = days 1-28 after, ``after_56`` = days 29-56 after.
             A window is due once its end is ``GSC_LAG_DAYS`` in the past.
* control  — for each task, up to ``CONTROL_SIZE`` URLs from gsc_performance
             with NO task done within ±``CONTROL_QUIET_DAYS`` of its done_date,
             picked deterministically; they get the same windows.
* ledger   — ``_state/metrics/task_outcomes.jsonl``, append-only, one line per
             (task, url, group, window) measurement.
* summary  — per primary_source: median Δclicks % treated vs control and the
             difference in percentage points; |diff| < 10 pp or n < 30 is
             ``indistinguishable`` / directional only (R-138 honesty rules).

The GSC calls happen in the skill (mcp__gsc__search_analytics with pageFilter);
this module only plans them, records answers and summarises. Pure functions
take ``today`` as an argument (rules/time-discipline.md).

CLI:
  task_outcome.py plan    --project SLUG --today YYYY-MM-DD [--workspace-root W]
  task_outcome.py record  --project SLUG --responses answers.json
  task_outcome.py summary --project SLUG
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.util.gsc_window import GSC_LAG_DAYS, GSC_ROW_LIMIT, truncation  # noqa: E402
from scripts.util.url_normalize import normalize_url  # noqa: E402

WINDOW_DAYS = 28
WINDOWS = ("before", "after_28", "after_56")
CONTROL_SIZE = 5
CONTROL_QUIET_DAYS = 60
THRESHOLD_PP = 10.0
MIN_N_FOR_VERDICT = 30
LEDGER_REL = Path("_state") / "metrics" / "task_outcomes.jsonl"


@dataclass(frozen=True)
class Request:
    task_id: str
    url: str
    primary_source: str
    group: str        # treated | control
    window: str       # before | after_28 | after_56
    start: str
    end: str

    def key(self) -> tuple:
        return (self.task_id, self.url, self.group, self.window)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _norm(url: Any) -> str | None:
    try:
        return normalize_url(str(url)) if url else None
    except ValueError:
        return None


def window_bounds(done: date, window: str) -> tuple[date, date]:
    if window == "before":
        return done - timedelta(days=WINDOW_DAYS), done - timedelta(days=1)
    if window == "after_28":
        return done + timedelta(days=1), done + timedelta(days=WINDOW_DAYS)
    if window == "after_56":
        return done + timedelta(days=WINDOW_DAYS + 1), done + timedelta(days=2 * WINDOW_DAYS)
    raise ValueError(f"unknown window {window!r}")


def _done_tasks(tasks: Iterable[Mapping[str, Any]]) -> list[tuple[str, str, str, date]]:
    out = []
    for t in tasks:
        if str(t.get("status") or "").upper() != "DONE":
            continue
        done, url = _as_date(t.get("done_date")), _norm(t.get("url"))
        if done is None or url is None:
            continue
        out.append((str(t.get("task_id") or ""), url, str(t.get("primary_source") or "manual"), done))
    return out


def control_urls(candidates: Iterable[str], tasks: Iterable[Mapping[str, Any]], *,
                 task_id: str, done: date, size: int = CONTROL_SIZE) -> list[str]:
    """URLs untouched within ±CONTROL_QUIET_DAYS of ``done`` (deterministic pick)."""
    busy = {u for _tid, u, _src, d in _done_tasks(tasks)
            if abs((d - done).days) <= CONTROL_QUIET_DAYS}
    pool = sorted({u for u in (_norm(c) for c in candidates) if u and u not in busy})
    pool.sort(key=lambda u: hashlib.sha256(f"{task_id}|{u}".encode()).hexdigest())
    return pool[:size]


def read_ledger(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError:
        return []
    out = []
    for line in lines:
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def due_requests(tasks: Sequence[Mapping[str, Any]], gsc_urls: Sequence[str],
                 ledger: Sequence[Mapping[str, Any]], *, today: date) -> list[Request]:
    """Every (task, url, group, window) measurement that is due and not yet recorded."""
    have = {(r.get("task_id"), r.get("url"), r.get("group"), r.get("window")) for r in ledger}
    cutoff = today - timedelta(days=GSC_LAG_DAYS)
    out: list[Request] = []
    for task_id, url, source, done in _done_tasks(tasks):
        groups = [("treated", url)] + [("control", c) for c in control_urls(
            gsc_urls, tasks, task_id=task_id, done=done)]
        for window in WINDOWS:
            start, end = window_bounds(done, window)
            if end > cutoff:
                continue
            for group, u in groups:
                req = Request(task_id, u, source, group, window, start.isoformat(), end.isoformat())
                if req.key() not in have:
                    out.append(req)
    return out


def measurement_row(req: Mapping[str, Any], payload: Mapping[str, Any] | None, *,
                    measured_at: str) -> dict:
    """One ledger line from a GSC answer (no rows = 0 clicks/impressions, position None)."""
    rows = (payload or {}).get("rows") or []
    clicks = sum(int(r.get("clicks") or 0) for r in rows)
    imps = sum(int(r.get("impressions") or 0) for r in rows)
    weighted = sum(float(r.get("position") or 0) * int(r.get("impressions") or 0)
                   for r in rows if r.get("position"))
    pos_weight = sum(int(r.get("impressions") or 0) for r in rows if r.get("position"))
    return {**{k: req[k] for k in ("task_id", "url", "primary_source", "group", "window", "start", "end")},
            "clicks": clicks, "impressions": imps,
            "position": round(weighted / pos_weight, 2) if pos_weight else None,
            "measured_at": measured_at}


def fetch_windows(reqs: Sequence[Request]) -> list[dict]:
    """Distinct (start, end) windows to pull ONCE each with ``dimensions=["page"]``.

    714 per-URL calls for rkturizm-tr collapse to one call per distinct window.
    """
    seen = sorted({(r.start, r.end) for r in reqs})
    return [{"startDate": s, "endDate": e, "dimensions": "page", "rowLimit": GSC_ROW_LIMIT}
            for s, e in seen]


def rows_from_window_payloads(reqs: Sequence[Request],
                              payloads: Mapping[tuple[str, str], Mapping[str, Any]], *,
                              measured_at: str) -> list[dict]:
    """Ledger lines for every request whose window payload is present.

    Each payload is a ``dimensions=["page"]`` answer; a request's page rows are
    the rows whose normalized page equals its url (none → zero clicks). A window
    that was not fetched yields NO line — never a fabricated zero.
    """
    by_window: dict[tuple[str, str], dict[str, list[dict]]] = {}
    for key, payload in payloads.items():
        if truncation(payload or {})["truncated"]:
            # a capped answer would record missing pages as zero clicks in an
            # append-only ledger — skip the window, it stays due (review fix)
            continue
        idx: dict[str, list[dict]] = {}
        for row in (payload or {}).get("rows") or []:
            keys = row.get("keys") or []
            page = _norm(keys[0]) if keys else None
            if page:
                idx.setdefault(page, []).append(row)
        by_window[key] = idx
    out = []
    for r in reqs:
        idx = by_window.get((r.start, r.end))
        if idx is None:
            continue
        out.append(measurement_row(r.__dict__, {"rows": idx.get(r.url, [])}, measured_at=measured_at))
    return out


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Append-only (O_APPEND + flock + fsync) — never rewrite measurements."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


def _pct(after: float, before: float) -> float | None:
    if before == 0:
        return None
    return (after - before) / before * 100.0


def summarize(ledger: Sequence[Mapping[str, Any]], *, after_window: str = "after_28") -> list[dict]:
    """Per primary_source: treated vs control median Δclicks % and the pp difference."""
    by_key: dict[tuple, dict] = {}
    for r in ledger:
        by_key.setdefault((r["task_id"], r["url"], r["group"]), {})[r["window"]] = r
    per_source: dict[str, dict[str, list[float]]] = {}
    pos_delta: dict[str, list[float]] = {}
    covered: dict[str, set] = {}
    for (task_id, _url, group), w in by_key.items():
        b, a = w.get("before"), w.get(after_window)
        if not b or not a:
            continue
        src = b.get("primary_source") or "manual"
        d = _pct(a["clicks"], b["clicks"])
        if d is not None:
            per_source.setdefault(src, {"treated": [], "control": []})[group].append(d)
        if group == "treated":
            covered.setdefault(src, set()).add(task_id)
            if a.get("position") is not None and b.get("position") is not None:
                pos_delta.setdefault(src, []).append(a["position"] - b["position"])
    out = []
    for src in sorted(set(per_source) | set(covered)):
        t = per_source.get(src, {}).get("treated", [])
        c = per_source.get(src, {}).get("control", [])
        diff = round(median(t) - median(c), 2) if t and c else None
        n = len(covered.get(src, ()))
        if diff is None:
            verdict = "insufficient_data"
        elif abs(diff) < THRESHOLD_PP:
            verdict = "indistinguishable"
        else:
            verdict = "engine_positive" if diff > 0 else "engine_negative"
        out.append({
            "primary_source": src, "tasks_measured": n,
            "treated_median_clicks_delta_pct": round(median(t), 2) if t else None,
            "control_median_clicks_delta_pct": round(median(c), 2) if c else None,
            "difference_pp": diff, "median_position_delta": round(median(pos_delta[src]), 2) if pos_delta.get(src) else None,
            "verdict": verdict,
            "caveat": "directional only (n<30)" if n < MIN_N_FOR_VERDICT else "",
        })
    return out


def coverage(tasks: Sequence[Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]], *,
             today: date) -> dict:
    """Share of DONE tasks old enough for after_28 that have before + after_28."""
    cutoff = today - timedelta(days=GSC_LAG_DAYS)
    eligible = [tid for tid, _u, _s, d in _done_tasks(tasks)
                if window_bounds(d, "after_28")[1] <= cutoff]
    have = {(r["task_id"], r["window"]) for r in ledger if r.get("group") == "treated"}
    measured = [tid for tid in eligible if (tid, "before") in have and (tid, "after_28") in have]
    return {"eligible": len(eligible), "measured": len(measured),
            "share": round(len(measured) / len(eligible), 3) if eligible else None}


# --- CLI ---------------------------------------------------------------------------

def _project_dir(slug: str, ws: str | None) -> Path:
    from scripts.state.session_binding import resolve_workspace_root
    root = Path(ws) if ws else resolve_workspace_root()
    if root is None:
        raise SystemExit("no workspace root — set PSEO_WORKSPACE_ROOT")
    return Path(root) / "projects" / slug


def _sheet(project: Path, sheet: str) -> list[dict]:
    from scripts.reporting.monthly_report import read_workbook
    return read_workbook(workbook_path=project / "master.xlsx", sheets=[sheet])[sheet]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="task_outcome.py")
    ap.add_argument("cmd", choices=("plan", "record", "summary"))
    ap.add_argument("--project", required=True)
    ap.add_argument("--workspace-root")
    ap.add_argument("--today")
    ap.add_argument("--responses",
                    help="JSON list of {startDate, endDate, payload} — one dimensions=page "
                         "answer per window listed by `plan`")
    args = ap.parse_args(argv)
    project = _project_dir(args.project, args.workspace_root)
    ledger_path = project / LEDGER_REL
    ledger = read_ledger(ledger_path)
    today = _as_date(args.today) if args.today else date.today()
    tasks = _sheet(project, "master_task")
    gsc_urls = [r.get("url") for r in _sheet(project, "gsc_performance") if r.get("url")]
    reqs = due_requests(tasks, gsc_urls, ledger, today=today)
    if args.cmd == "plan":
        print(json.dumps({"fetch": fetch_windows(reqs), "measurements_due": len(reqs),
                          "coverage": coverage(tasks, ledger, today=today)}, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "record":
        answers = json.loads(Path(args.responses).read_text(encoding="utf-8"))
        payloads = {(a["startDate"], a["endDate"]): a.get("payload") for a in answers}
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = rows_from_window_payloads(reqs, payloads, measured_at=now)
        append_rows(ledger_path, rows)
        print(f"recorded {len(rows)} measurement(s) → {ledger_path}")
        return 0
    print(json.dumps(summarize(ledger), ensure_ascii=False, indent=1))
    return 0


__all__ = ("Request", "window_bounds", "control_urls", "due_requests", "measurement_row",
           "append_rows", "read_ledger", "summarize", "coverage")


if __name__ == "__main__":
    sys.exit(main())
