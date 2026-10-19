#!/usr/bin/env python3
"""task_noise.py — keep the task generator from producing work nobody does (O-02, O-18, O-19).

Portfolio facts (2026-10): 4,124 generated tasks, 2,811 (68 %) CANCELED;
internal-link tasks 1,531 canceled vs 10 done. Nothing fed those cancellations
back, the generator re-opened tasks on pages changed days earlier, and the
cancel reasons stayed free text nobody read.

``NoiseGate`` decides, for a NEW task the sync is about to append, whether to
drop it — every drop has a named reason that lands in ``dropped_stats``:

* ``cooldown_60d``          (O-18) the url had a task DONE within 60 days of
                             the run — wait for the outcome measurement (O-01).
* ``low_acceptance``        (O-02) the source type has >= 20 cancellations and
                             under 10 % of its closed tasks were done.
* ``previously_canceled``   (O-19) the same url + source was canceled before.

``cancel_standards`` turns the CANCELED rows into the per-project
``seo-standartlari.md`` text: reasons grouped by source; a reason seen 3+ times
is marked as a standing rule.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping

COOLDOWN_DAYS = 60
LOW_ACCEPT_MIN_CANCELED = 20
LOW_ACCEPT_MAX_DONE_SHARE = 0.10
STANDING_RULE_REPEATS = 3

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _d(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or "").strip().upper()


def _url(row: Mapping[str, Any]) -> str:
    return str(row.get("url") or "").strip().rstrip("/").lower()


@dataclass
class NoiseGate:
    run_date: date
    recent_done: set = field(default_factory=set)
    canceled_pairs: set = field(default_factory=set)
    throttled_sources: set = field(default_factory=set)

    @classmethod
    def from_master_task(cls, rows: Iterable[Mapping[str, Any]], run_date: Any) -> "NoiseGate":
        today = _d(run_date) or date.today()
        gate = cls(run_date=today)
        done_by_src: Counter = Counter()
        canceled_by_src: Counter = Counter()
        for r in rows:
            st, src, url = _status(r), str(r.get("primary_source") or ""), _url(r)
            if st == "DONE":
                done_by_src[src] += 1
                dd = _d(r.get("done_date"))
                if url and dd is not None and 0 <= (today - dd).days <= COOLDOWN_DAYS:
                    gate.recent_done.add(url)
            elif st == "CANCELED":
                canceled_by_src[src] += 1
                if url:
                    gate.canceled_pairs.add((src, url))
        for src, canceled in canceled_by_src.items():
            done = done_by_src.get(src, 0)
            if canceled >= LOW_ACCEPT_MIN_CANCELED and done / (done + canceled) < LOW_ACCEPT_MAX_DONE_SHARE:
                gate.throttled_sources.add(src)
        return gate

    def drop_reason(self, primary_source: str, url: str) -> str | None:
        u = str(url or "").strip().rstrip("/").lower()
        if primary_source in self.throttled_sources:
            return "low_acceptance"
        if u and u in self.recent_done:
            return "cooldown_60d"
        if u and (primary_source, u) in self.canceled_pairs:
            return "previously_canceled"
        return None


def _reason(note: Any) -> str:
    text = str(note or "").strip()
    m = re.search(r"(?:iptal|cancel(?:ed)?)\s*[:\-—]\s*(.+)", text, re.IGNORECASE)
    text = (m.group(1) if m else text).strip()
    return " ".join(_WORD.findall(text.casefold())[:8]) or "(gerekçe yok)"


def cancel_standards(rows: Iterable[Mapping[str, Any]], *, project: str) -> str:
    """Markdown for projects/<slug>/seo-standartlari.md from the CANCELED rows."""
    grouped: dict[str, Counter] = defaultdict(Counter)
    missing = 0
    for r in rows:
        if _status(r) != "CANCELED":
            continue
        reason = _reason(r.get("note"))
        if reason == "(gerekçe yok)":
            missing += 1
        grouped[str(r.get("primary_source") or "manual")][reason] += 1
    lines = [f"# SEO standartları — {project}", "",
             "İptal edilen görevlerin gerekçelerinden üretilir (O-19). Görev üreticileri "
             "bu dosyayı okur; 3+ kez tekrar eden gerekçe kalıcı kuraldır.", ""]
    for src in sorted(grouped):
        lines.append(f"## {src}")
        for reason, n in grouped[src].most_common():
            tag = " — **KALICI KURAL**" if n >= STANDING_RULE_REPEATS and reason != "(gerekçe yok)" else ""
            lines.append(f"- {reason} ({n}){tag}")
        lines.append("")
    if missing:
        lines.append(f"> {missing} iptal gerekçesiz — iptal ederken kısa gerekçe yazın "
                     "(`note`: 'iptal: …').")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ("NoiseGate", "cancel_standards", "COOLDOWN_DAYS")
