"""O-02 / O-18 / O-19 — the task generator stops producing work nobody does."""
from __future__ import annotations

from scripts.planning import master_task_sync as mts
from scripts.planning.task_noise import NoiseGate, cancel_standards

RUN = "2026-10-19"


def _t(i, src, status, url="", done=None, note=""):
    return {"task_id": f"T-{i:05d}", "primary_source": src, "status": status, "url": url,
            "done_date": done, "note": note, "auto_generated": True}


def test_cooldown_after_recent_done() -> None:
    gate = NoiseGate.from_master_task([_t(1, "quickwin", "DONE", "https://x.test/a/", "2026-09-30")], RUN)
    assert gate.drop_reason("tech_fix", "https://x.test/a") == "cooldown_60d"
    old = NoiseGate.from_master_task([_t(1, "quickwin", "DONE", "https://x.test/a", "2026-06-01")], RUN)
    assert old.drop_reason("tech_fix", "https://x.test/a") is None


def test_low_acceptance_source_is_throttled() -> None:
    rows = [_t(i, "internal_links", "CANCELED", f"https://x.test/{i}") for i in range(25)]
    rows += [_t(100, "internal_links", "DONE", "https://x.test/d", "2026-01-01")]
    gate = NoiseGate.from_master_task(rows, RUN)
    assert gate.drop_reason("internal_links", "https://x.test/new") == "low_acceptance"
    assert gate.drop_reason("quickwin", "https://x.test/new") is None


def test_previously_canceled_same_url_and_source() -> None:
    gate = NoiseGate.from_master_task([_t(1, "schema", "CANCELED", "https://x.test/p")], RUN)
    assert gate.drop_reason("schema", "https://x.test/p") == "previously_canceled"
    assert gate.drop_reason("quickwin", "https://x.test/p") is None


def test_sync_reports_the_drops_instead_of_appending() -> None:
    existing = [_t(1, "content_decay", "DONE", "https://x.test/old", "2026-10-01")]
    sources = {"content_decay": [{"url": "https://x.test/old", "trend": "DECAY", "action": "revise"}]}
    batch = mts.aggregate(sources=sources, existing_master_task=existing, run_date=RUN)
    assert batch.appends == []
    assert batch.dropped_stats.get("content_decay", {}).get("cooldown_60d") == 1


def test_cancel_standards_marks_repeated_reasons() -> None:
    rows = [_t(i, "internal_links", "CANCELED", note="iptal: sayfa zaten link alıyor") for i in range(3)]
    rows.append(_t(9, "schema", "CANCELED", note=""))
    md = cancel_standards(rows, project="demo")
    assert "## internal_links" in md and "sayfa zaten link alıyor (3) — **KALICI KURAL**" in md
    assert "1 iptal gerekçesiz" in md
