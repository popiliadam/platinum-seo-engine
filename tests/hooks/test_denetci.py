"""tests/hooks/test_denetci.py — AMO L3 Stop-hook denetçi (batch 2c).

Coverage matrix:
  - decide() PURE decision matrix (allow / block / flag) for the 6 verdict
    branches + the non-start gate.
  - freshest_fresh_coverage() freshness gate: a fresh record (mtime >= marker)
    is returned, a stale prior-run record (mtime < marker) is ignored, and the
    GREATEST-mtime fresh record wins.
  - main() end-to-end via subprocess (mirrors test_stop_validation): a declared
    intent + fresh incomplete/failed → STDOUT block JSON; + fresh pass → silent;
    + paused → silent stdout, stderr flag; non-start → block with the marker
    command; stop_hook_active=true → no re-block; bogus/empty stdin → exit 0.
  - hooks/stop.json wiring: stop_validation stays FIRST, denetci.py added after.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.hooks.denetci import (
    coverage_dir,
    decide,
    freshest_fresh_coverage,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hooks" / "denetci.py"
STOP_JSON = REPO_ROOT / "hooks" / "stop.json"


# ---------------------------------------------------------------------------
# decide() — pure decision matrix
# ---------------------------------------------------------------------------

def _declared(**overrides: object) -> dict:
    marker = {
        "schema_version": "1.0",
        "session_id": "sess-1",
        "turn_id": "t-1",
        "intent_id": "i-1",
        "status": "declared",
        "declared_at": "2026-06-06T00:00:00",
        "workflow": "monthly",
        "slug": "vento",
        "command": "/pseo-run monthly vento",
    }
    marker.update(overrides)
    return marker


def test_decide_no_marker_allows() -> None:
    """1. marker None → ('allow', None) (nothing owed)."""
    assert decide(None, None) == ("allow", None)


def test_decide_superseded_allows() -> None:
    """2. a superseded marker → ('allow', None) (intent abandoned this turn)."""
    assert decide(_declared(status="superseded"), None) == ("allow", None)


def test_decide_pass_allows() -> None:
    """3. declared + verdict 'pass' → ('allow', None)."""
    assert decide(_declared(), {"verdict": "pass", "steps": []}) == ("allow", None)


def test_decide_incomplete_blocks() -> None:
    """4. declared + 'incomplete' → block; reason carries the --resume fix."""
    action, reason = decide(
        _declared(),
        {"verdict": "incomplete", "steps": [{"name": "fetch_gsc", "status": "missing"}]},
    )
    assert action == "block"
    assert reason is not None
    assert "/pseo-run" in reason and "--resume" in reason


def test_decide_failed_blocks() -> None:
    """5. declared + 'failed' → block; reason has the exact fix command."""
    action, reason = decide(
        _declared(),
        {"verdict": "failed", "steps": [{"name": "score", "status": "failed"}]},
    )
    assert action == "block"
    assert reason is not None
    assert "/pseo-run monthly vento --resume" in reason


def test_decide_paused_flags_not_blocks() -> None:
    """6. declared + 'paused' → flag (allow turn-end), framed as external dep."""
    action, reason = decide(
        _declared(),
        {"verdict": "paused", "steps": [{"name": "fetch_gsc", "status": "running"}]},
    )
    assert action == "flag"
    assert reason is not None
    assert "--resume" in reason
    assert "bağımlılık" in reason or "GSC" in reason


def test_decide_nonstart_blocks_with_marker_command() -> None:
    """7. declared + NO coverage (non-start) → block with marker command + çalışmadı."""
    marker = _declared()
    action, reason = decide(marker, None)
    assert action == "block"
    assert reason is not None
    assert marker["command"] in reason
    assert "çalışmadı" in reason


# ---------------------------------------------------------------------------
# freshest_fresh_coverage() — the mtime freshness gate
# ---------------------------------------------------------------------------

def _write_cov(tmp_path: Path, slug: str, run_id: str, record: dict, mtime: float) -> Path:
    directory = coverage_dir(tmp_path, slug)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run_id}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_freshest_returns_fresh_record(tmp_path: Path) -> None:
    """8a. a coverage file with mtime >= since is returned."""
    since = 1_000_000.0
    _write_cov(tmp_path, "vento", "vento-2026-06-06-ab12",
               {"run_id": "fresh", "verdict": "incomplete"}, since + 100)
    record = freshest_fresh_coverage(tmp_path, "vento", since)
    assert record is not None and record["run_id"] == "fresh"


def test_freshest_ignores_stale_record(tmp_path: Path) -> None:
    """8b. a coverage file with mtime < since is ignored (stale prior pass)."""
    since = 1_000_000.0
    _write_cov(tmp_path, "vento", "vento-2026-06-01-0001",
               {"run_id": "stale", "verdict": "pass"}, since - 100)
    assert freshest_fresh_coverage(tmp_path, "vento", since) is None


def test_freshest_returns_greatest_mtime(tmp_path: Path) -> None:
    """9. among two fresh records the GREATEST mtime wins."""
    since = 1_000_000.0
    _write_cov(tmp_path, "vento", "vento-2026-06-06-aaaa",
               {"run_id": "older", "verdict": "incomplete"}, since + 10)
    _write_cov(tmp_path, "vento", "vento-2026-06-06-bbbb",
               {"run_id": "newer", "verdict": "pass"}, since + 50)
    record = freshest_fresh_coverage(tmp_path, "vento", since)
    assert record is not None and record["run_id"] == "newer"


def test_freshest_missing_dir_is_none(tmp_path: Path) -> None:
    """The coverage dir not existing → None (never raises)."""
    assert freshest_fresh_coverage(tmp_path, "nope", 0.0) is None


# ---------------------------------------------------------------------------
# main() end-to-end (subprocess) — mirrors test_stop_validation
# ---------------------------------------------------------------------------

_SID = "sess-denetci"


def _env(home: Path) -> dict:
    """Clean env: tmp HOME (config.json lookup) + plugin root; strip interference."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PSEO_WORKSPACE_ROOT", "CLAUDE_CODE_SESSION_ID"}
    }
    env["HOME"] = str(home)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    return env


def _world(
    tmp_path: Path,
    *,
    status: str = "declared",
    slug: str = "vento",
    command: str = "/pseo-run monthly vento",
    coverage: dict | None = None,
    run_id: str = "vento-2026-06-06-ab12",
    fresh: bool = True,
) -> Path:
    """Build a tmp HOME+workspace with config, an intent marker, and (optionally)
    a coverage record whose mtime is fresh (>= marker) or stale (< marker)."""
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    cfg = home / ".config" / "pseo"
    cfg.mkdir(parents=True)
    (cfg / "config.json").write_text(
        json.dumps({"workspace_root": str(ws)}), encoding="utf-8"
    )
    sessions = ws / "shared" / "sessions"
    sessions.mkdir(parents=True)
    marker = {
        "schema_version": "1.0",
        "session_id": _SID,
        "turn_id": "t-1",
        "intent_id": "i-1",
        "status": status,
        "declared_at": "2026-06-06T00:00:00",
    }
    if status == "declared":
        marker.update({"workflow": "monthly", "slug": slug, "command": command})
    marker_path = sessions / f"{_SID}.intent.json"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    if coverage is not None:
        base = marker_path.stat().st_mtime
        _write_cov(ws, slug, run_id, coverage, base + (10 if fresh else -100))
    return home


def _run(home: Path, *, stop_hook_active: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"session_id": _SID, "stop_hook_active": stop_hook_active}),
        env=_env(home),
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_main_declared_incomplete_blocks(tmp_path: Path) -> None:
    """10. declared + FRESH incomplete → STDOUT decision=block; exit 0."""
    home = _world(tmp_path, coverage={
        "run_id": "vento-2026-06-06-ab12", "verdict": "incomplete",
        "required_satisfied": False, "steps": [{"name": "fetch_gsc", "status": "missing"}],
    })
    proc = _run(home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["decision"] == "block"
    assert "--resume" in data["reason"]


def test_main_declared_pass_is_silent(tmp_path: Path) -> None:
    """11. declared + FRESH pass → STDOUT empty (allow); exit 0."""
    home = _world(tmp_path, coverage={
        "run_id": "vento-2026-06-06-ab12", "verdict": "pass",
        "required_satisfied": True, "steps": [],
    })
    proc = _run(home)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_main_stop_hook_active_no_reblock(tmp_path: Path) -> None:
    """12. stop_hook_active=true + declared+incomplete → no re-block; exit 0."""
    home = _world(tmp_path, coverage={
        "run_id": "vento-2026-06-06-ab12", "verdict": "incomplete",
        "required_satisfied": False, "steps": [],
    })
    proc = _run(home, stop_hook_active=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_main_nonstart_blocks_with_command(tmp_path: Path) -> None:
    """13. declared marker but NO coverage file → block with the marker command."""
    home = _world(tmp_path, coverage=None)
    proc = _run(home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["decision"] == "block"
    assert "/pseo-run monthly vento" in data["reason"]
    assert "çalışmadı" in data["reason"]


def test_main_paused_flags_to_stderr(tmp_path: Path) -> None:
    """14. paused coverage → STDOUT empty, stderr carries the [denetçi] flag."""
    home = _world(tmp_path, coverage={
        "run_id": "vento-2026-06-06-ab12", "verdict": "paused",
        "required_satisfied": False, "steps": [{"name": "fetch_gsc", "status": "running"}],
    })
    proc = _run(home)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert "[denetçi]" in proc.stderr


def test_main_stale_pass_is_nonstart_block(tmp_path: Path) -> None:
    """Freshness end-to-end: a STALE prior pass must NOT satisfy a fresh intent
    (mtime < marker → ignored → non-start block)."""
    home = _world(tmp_path, fresh=False, coverage={
        "run_id": "vento-2026-06-06-ab12", "verdict": "pass",
        "required_satisfied": True, "steps": [],
    })
    proc = _run(home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["decision"] == "block"
    assert "çalışmadı" in data["reason"]


def test_main_noncrash_empty_stdin(tmp_path: Path) -> None:
    """15a. empty stdin (no workspace) → exit 0, no decision."""
    home = tmp_path / "home"
    home.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input="", env=_env(home),
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_main_noncrash_bogus_payload(tmp_path: Path) -> None:
    """15b. malformed stdin → exit 0, no decision."""
    home = tmp_path / "home"
    home.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input="}{not json", env=_env(home),
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Wiring — stop.json keeps stop_validation FIRST, adds denetci after
# ---------------------------------------------------------------------------

def test_stop_json_wires_denetci_after_validation() -> None:
    spec = json.loads(STOP_JSON.read_text(encoding="utf-8"))
    handler = spec["hooks"]["Stop"][0]
    commands = [c["command"] for c in handler["hooks"]]
    assert "stop_validation.py" in commands[0], "stop_validation must stay FIRST"
    val_idx = next(i for i, c in enumerate(commands) if "stop_validation.py" in c)
    den_idx = next(i for i, c in enumerate(commands) if "denetci.py" in c)
    assert den_idx > val_idx, "denetci.py must be wired AFTER stop_validation.py"
