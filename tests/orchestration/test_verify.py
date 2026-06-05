"""Unit tests for scripts/orchestration/verify.py — the raw-drop gate (AMO 1b).

verify_raw_drop is the identity + content + freshness gate the orchestrator spine
runs on a model-dropped raw artifact BEFORE the pure transform + commit. Each
failure mode RETURNS a stable reason code (never raises for an expected bad
drop) so the coverage record + denetçi can key on it. silent_skip_exceeds is the
high-silent-skip gate from spec section 7-1b.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.orchestration.verify import (
    VerifyResult,
    silent_skip_exceeds,
    verify_raw_drop,
)

NOW = 1_750_000_000  # fixed canned epoch — pure/deterministic, no wall clock
RUN_ID = "demo-furniture-2026-06-05-a1b2"
SLUG = "demo-furniture"
SITE = "https://demo-furniture.example"
WINDOW = "2026-05"
TOOL = "mcp__gsc__search_analytics"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _write_drop(
    path: Path,
    *,
    run_id: str = RUN_ID,
    slug: str = SLUG,
    site_url: str = SITE,
    window: str = WINDOW,
    tool: str = TOOL,
    rows: list[dict] | None = None,
    declared_count: int | None = None,
    fetched_at: str | None = None,
    mtime: float = NOW - 60,
) -> Path:
    rows = [{"q": f"kw{i}"} for i in range(3)] if rows is None else rows
    drop = {
        "provenance": {
            "run_id": run_id,
            "slug": slug,
            "site_url": site_url,
            "window": window,
            "tool": tool,
            "fetched_at": _iso(NOW - 60) if fetched_at is None else fetched_at,
            "declared_count": len(rows) if declared_count is None else declared_count,
        },
        "rows": rows,
    }
    path.write_text(json.dumps(drop), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _verify(path: Path, **overrides) -> VerifyResult:
    kwargs = dict(expected_run_id=RUN_ID, expected_slug=SLUG, now_epoch=NOW)
    kwargs.update(overrides)
    return verify_raw_drop(path, **kwargs)


# --- valid -----------------------------------------------------------------

def test_valid_drop_passes(tmp_path: Path) -> None:
    vr = _verify(_write_drop(tmp_path / "drop.json"))
    assert vr.ok is True
    assert vr.reason is None
    assert vr.input_count == 3
    assert vr.rows == [{"q": "kw0"}, {"q": "kw1"}, {"q": "kw2"}]


def test_valid_drop_with_z_suffix_fetched_at(tmp_path: Path) -> None:
    # The model may stamp fetched_at with a trailing 'Z'; the gate must parse it.
    z = datetime.fromtimestamp(NOW - 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vr = _verify(_write_drop(tmp_path / "drop.json", fetched_at=z))
    assert vr.ok is True


def test_optional_expectations_skipped_when_none(tmp_path: Path) -> None:
    # site_url/window/tool differ from the drop but expectations are None -> not checked.
    p = _write_drop(tmp_path / "d.json", site_url="https://other", window="zz", tool="tt")
    assert _verify(p).ok is True


# --- failure modes (each isolates ONE defect) ------------------------------

def test_missing_file(tmp_path: Path) -> None:
    vr = _verify(tmp_path / "nope.json")
    assert vr.ok is False and vr.reason == "missing_file"
    assert vr.rows is None


def test_parse_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    os.utime(p, (NOW - 60, NOW - 60))
    vr = _verify(p)
    assert vr.ok is False and vr.reason == "parse_error"


def test_not_an_object_is_parse_error(tmp_path: Path) -> None:
    p = tmp_path / "arr.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    os.utime(p, (NOW - 60, NOW - 60))
    vr = _verify(p)
    assert vr.ok is False and vr.reason == "parse_error"


def test_no_provenance(tmp_path: Path) -> None:
    p = tmp_path / "np.json"
    p.write_text(json.dumps({"rows": []}), encoding="utf-8")
    os.utime(p, (NOW - 60, NOW - 60))
    vr = _verify(p)
    assert vr.ok is False and vr.reason == "no_provenance"


def test_missing_rows_is_parse_error(tmp_path: Path) -> None:
    p = tmp_path / "nr.json"
    p.write_text(json.dumps({"provenance": {"run_id": RUN_ID, "slug": SLUG}}), encoding="utf-8")
    os.utime(p, (NOW - 60, NOW - 60))
    vr = _verify(p)
    assert vr.ok is False and vr.reason == "parse_error"


def test_run_id_mismatch(tmp_path: Path) -> None:
    vr = _verify(_write_drop(tmp_path / "d.json", run_id="other-2026-06-05-9999"))
    assert vr.ok is False and vr.reason == "run_id_mismatch"


def test_slug_mismatch(tmp_path: Path) -> None:
    vr = _verify(_write_drop(tmp_path / "d.json", slug="other"))
    assert vr.ok is False and vr.reason == "slug_mismatch"


def test_site_url_mismatch(tmp_path: Path) -> None:
    p = _write_drop(tmp_path / "d.json", site_url="https://wrong")
    vr = _verify(p, expected_site_url=SITE)
    assert vr.ok is False and vr.reason == "site_url_mismatch"


def test_window_mismatch(tmp_path: Path) -> None:
    p = _write_drop(tmp_path / "d.json", window="2026-04")
    vr = _verify(p, expected_window=WINDOW)
    assert vr.ok is False and vr.reason == "window_mismatch"


def test_tool_mismatch(tmp_path: Path) -> None:
    p = _write_drop(tmp_path / "d.json", tool="mcp__other__x")
    vr = _verify(p, expected_tool=TOOL)
    assert vr.ok is False and vr.reason == "tool_mismatch"


def test_stale_by_old_mtime(tmp_path: Path) -> None:
    # fresh fetched_at, but the file's mtime is older than max_age -> stale.
    vr = _verify(_write_drop(tmp_path / "d.json", mtime=NOW - 200_000))
    assert vr.ok is False and vr.reason == "stale"


def test_stale_by_old_fetched_at(tmp_path: Path) -> None:
    # fresh mtime, but provenance.fetched_at is older than max_age -> stale.
    p = _write_drop(tmp_path / "d.json", fetched_at=_iso(NOW - 200_000), mtime=NOW - 60)
    assert _verify(p).reason == "stale"


def test_truncated(tmp_path: Path) -> None:
    # declared_count 5 but only 3 rows present.
    vr = _verify(_write_drop(tmp_path / "d.json", declared_count=5))
    assert vr.ok is False and vr.reason == "truncated"


# --- silent-skip gate ------------------------------------------------------

def test_silent_skip_exceeds_true() -> None:
    assert silent_skip_exceeds(100, 40) is True  # (100-40)/100 = 0.6 > 0.5


def test_silent_skip_exceeds_false_under_ratio() -> None:
    assert silent_skip_exceeds(100, 60) is False  # 0.4 < 0.5


def test_silent_skip_exceeds_zero_input() -> None:
    assert silent_skip_exceeds(0, 0) is False
