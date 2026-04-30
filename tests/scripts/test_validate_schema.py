"""Smoke tests for scripts/validation/validate_schema.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "validate_schema.py"

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}


def _run(data_path: Path, schema_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(data_path), str(schema_path)],
        capture_output=True,
        text=True,
    )


def _write(tmp_path: Path, name: str, payload: object) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_valid_data_exits_zero(tmp_path: Path) -> None:
    schema_path = _write(tmp_path, "schema.json", SCHEMA)
    data_path = _write(tmp_path, "data.json", {"name": "Suleyman", "age": 40})
    result = _run(data_path, schema_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_invalid_data_exits_one_with_stderr(tmp_path: Path) -> None:
    schema_path = _write(tmp_path, "schema.json", SCHEMA)
    data_path = _write(tmp_path, "data.json", {"name": "x", "age": -5})
    result = _run(data_path, schema_path)
    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "validation failed" in result.stderr
