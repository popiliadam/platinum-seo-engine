"""tests/scripts/test_migration_0001.py — Migration 0001 (project.config.json
1.0 → 1.1) — Phase 10 additive bump (content_settings + brand_identity
optional extension).

Coverage (D-01 v1.5-Phase-2 Tier 2):
  1. Pure 1.0 doc bumps to 1.1 with no surprise field injection (additive).
  2. Idempotent — re-running on a 1.1 doc returns it unchanged.
  3. Refuses out-of-range versions (1.2 / 2.0 / draft / None) — silent
     rewrite forbidden per rules/schema-versioning-discipline.md.
  4. CLI dry-run prints migrated JSON to stdout, no filesystem write.
  5. CLI in-place write produces .bak backup (append-only-state mirror).
  6. CLI explicit --out path skips .bak side-effect.

Pattern reuse: tests/scripts/test_migration_0003.py (Phase 13) —
``importlib.util.spec_from_file_location`` because numeric-prefix
filenames (``0001_...``) are not valid Python module identifiers.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO / "scripts" / "migrations" / "0001_project_config_1.0_to_1.1.py"


@pytest.fixture(scope="module")
def migration_module():
    spec = importlib.util.spec_from_file_location("m_0001", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# migrate() pure function tests
# ---------------------------------------------------------------------------

def test_pure_1_0_doc_bumps_to_1_1(migration_module) -> None:
    """A 1.0 doc gets schema_version flipped; other fields untouched.
    Additive contract: no surprise field injection."""
    doc = {
        "schema_version": "1.0",
        "project_id": "alpha",
        "domain": "https://example.com/",
    }
    out = migration_module.migrate(doc)
    assert out["schema_version"] == "1.1"
    assert out["project_id"] == "alpha"
    assert out["domain"] == "https://example.com/"
    # Additive contract: no auto-injected fields
    assert "content_settings" not in out
    assert "brand_identity" not in out


def test_idempotent_on_1_1(migration_module) -> None:
    """Re-running on a 1.1 doc returns it unchanged."""
    doc = {"schema_version": "1.1", "project_id": "beta"}
    out = migration_module.migrate(doc)
    assert out == doc


def test_refuses_out_of_range_version(migration_module) -> None:
    """1.2 / 2.0 / draft / None — silent rewrite forbidden."""
    for sv in ("1.2", "2.0", "draft", None):
        with pytest.raises(ValueError, match="expected schema_version '1.0'"):
            migration_module.migrate({"schema_version": sv})


def test_returns_new_dict_does_not_mutate(migration_module) -> None:
    """Migrate returns a NEW dict; input is not mutated."""
    doc = {"schema_version": "1.0", "project_id": "gamma"}
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
    in_path = _write_input(tmp_path, {"schema_version": "1.0"})
    snapshot = in_path.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path), "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["schema_version"] == "1.1"
    # File untouched
    assert in_path.read_text(encoding="utf-8") == snapshot
    # No .bak written
    assert not in_path.with_suffix(".json.bak").exists()


def test_cli_in_place_writes_bak(tmp_path: Path) -> None:
    """In-place write creates a .bak with the original content."""
    original = {"schema_version": "1.0", "project_id": "delta"}
    in_path = _write_input(tmp_path, original)
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path)],
        capture_output=True, text=True, check=True,
    )
    bak_path = in_path.with_suffix(".json.bak")
    assert bak_path.exists(), "in-place migration must produce .bak"
    bak_doc = json.loads(bak_path.read_text(encoding="utf-8"))
    assert bak_doc == original, ".bak must hold the original pre-migration content"
    new_doc = json.loads(in_path.read_text(encoding="utf-8"))
    assert new_doc["schema_version"] == "1.1"


def test_cli_explicit_out_skips_bak(tmp_path: Path) -> None:
    """--out PATH writes to the new path; no .bak side-effect on input."""
    in_path = _write_input(tmp_path, {"schema_version": "1.0"})
    out_path = tmp_path / "migrated.json"
    subprocess.run(
        [sys.executable, str(MIGRATION_PATH),
         "--in", str(in_path), "--out", str(out_path)],
        capture_output=True, text=True, check=True,
    )
    assert out_path.exists()
    assert not in_path.with_suffix(".json.bak").exists()
    # Input file is not modified
    assert json.loads(in_path.read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_cli_missing_input_returns_2(tmp_path: Path) -> None:
    """Missing input returns exit code 2 (DURUR)."""
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH),
         "--in", str(tmp_path / "nonexistent.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_cli_out_of_range_returns_3(tmp_path: Path) -> None:
    """Out-of-range source version returns exit code 3 (refuses)."""
    in_path = _write_input(tmp_path, {"schema_version": "2.0"})
    result = subprocess.run(
        [sys.executable, str(MIGRATION_PATH), "--in", str(in_path), "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 3
