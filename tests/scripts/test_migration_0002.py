"""tests/scripts/test_migration_0002.py — Migration 0002 (project.config.json
1.1 → 1.2) — Phase 11 W-F1 cascade fix (singular ``profile`` optional
field NOT auto-injected).

Coverage (D-01 v1.5-Phase-2 Tier 2):
  1. Pure 1.1 doc bumps to 1.2 with no surprise ``profile`` injection.
  2. Idempotent — re-running on a 1.2 doc returns it unchanged.
  3. Refuses out-of-range versions (1.0 / 1.3 / 2.0 / draft / None).
  4. CLI dry-run prints migrated JSON to stdout, no filesystem write.
  5. CLI in-place write produces .bak backup.
  6. CLI explicit --out path skips .bak side-effect.

Pattern reuse: tests/scripts/test_migration_0001.py + test_migration_0003.py.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO / "scripts" / "migrations" / "0002_project_config_1.1_to_1.2.py"


@pytest.fixture(scope="module")
def migration_module():
    spec = importlib.util.spec_from_file_location("m_0002", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# migrate() pure function tests
# ---------------------------------------------------------------------------

def test_pure_1_1_doc_bumps_to_1_2(migration_module) -> None:
    """A 1.1 doc gets schema_version flipped; ``profile`` is NOT auto-injected."""
    doc = {
        "schema_version": "1.1",
        "project_id": "alpha",
        "profiles": ["ymyl"],
    }
    out = migration_module.migrate(doc)
    assert out["schema_version"] == "1.2"
    assert out["project_id"] == "alpha"
    assert out["profiles"] == ["ymyl"]
    # Additive contract: singular `profile` is consumer-injected by skills,
    # not by the migration step (truly additive — no surprise default writes).
    assert "profile" not in out


def test_idempotent_on_1_2(migration_module) -> None:
    """Re-running on a 1.2 doc returns it unchanged."""
    doc = {"schema_version": "1.2", "project_id": "beta", "profile": "ymyl"}
    out = migration_module.migrate(doc)
    assert out == doc


def test_refuses_out_of_range_version(migration_module) -> None:
    """1.0 / 1.3 / 2.0 / draft / None — silent rewrite forbidden."""
    for sv in ("1.0", "1.3", "2.0", "draft", None):
        with pytest.raises(ValueError, match="expected schema_version '1.1'"):
            migration_module.migrate({"schema_version": sv})


def test_returns_new_dict_does_not_mutate(migration_module) -> None:
    """Migrate returns a NEW dict; input is not mutated."""
    doc = {"schema_version": "1.1", "project_id": "gamma"}
    snapshot = dict(doc)
    out = migration_module.migrate(doc)
    assert doc == snapshot, "input dict mutated — immutability breach"
    assert out is not doc


# ---------------------------------------------------------------------------
# CLI tests (subprocess)
# ---------------------------------------------------------------------------

def _write_input(tmp_path: Path, doc: dict) -> Path:
    in_path = tmp_path / "project.config.json"
    in_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return in_path


def test_cli_dry_run_prints_to_stdout(tmp_path: Path) -> None:
    """--dry-run: migrated JSON to stdout, NO filesystem write."""
    in_path = _write_input(tmp_path, {"schema_version": "1.1"})
    snapshot = in_path.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path), "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["schema_version"] == "1.2"
    assert in_path.read_text(encoding="utf-8") == snapshot
    assert not in_path.with_suffix(".json.bak").exists()


def test_cli_in_place_writes_bak(tmp_path: Path) -> None:
    """In-place write creates a .bak with the original content."""
    original = {"schema_version": "1.1", "project_id": "delta"}
    in_path = _write_input(tmp_path, original)
    subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path)],
        capture_output=True, text=True, check=True,
    )
    bak_path = in_path.with_suffix(".json.bak")
    assert bak_path.exists(), "in-place migration must produce .bak"
    bak_doc = json.loads(bak_path.read_text(encoding="utf-8"))
    assert bak_doc == original
    new_doc = json.loads(in_path.read_text(encoding="utf-8"))
    assert new_doc["schema_version"] == "1.2"


def test_cli_explicit_out_skips_bak(tmp_path: Path) -> None:
    """--out PATH writes to the new path; no .bak side-effect on input."""
    in_path = _write_input(tmp_path, {"schema_version": "1.1"})
    out_path = tmp_path / "migrated.json"
    subprocess.run(
        [sys.executable, str(MIGRATION_PATH),
         "--in", str(in_path), "--out", str(out_path)],
        capture_output=True, text=True, check=True,
    )
    assert out_path.exists()
    assert not in_path.with_suffix(".json.bak").exists()
    assert json.loads(in_path.read_text(encoding="utf-8"))["schema_version"] == "1.1"


def test_cli_missing_input_returns_2(tmp_path: Path) -> None:
    """Missing input returns exit code 2."""
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH),
         "--in", str(tmp_path / "nonexistent.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_cli_out_of_range_returns_3(tmp_path: Path) -> None:
    """Out-of-range source version returns exit code 3."""
    in_path = _write_input(tmp_path, {"schema_version": "2.0"})
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path), "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 3
