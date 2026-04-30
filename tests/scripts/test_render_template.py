"""Smoke tests for scripts/reporting/render_template.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "reporting" / "render_template.py"


def _run(template: Path, data: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(template), str(data)],
        capture_output=True,
        text=True,
    )


def test_substitution_happy_path(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl.md"
    tpl.write_text("# Report for $project\n\nClicks: $clicks\n", encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"project": "demo-dental", "clicks": 1234}), encoding="utf-8")
    result = _run(tpl, data)
    assert result.returncode == 0, result.stderr
    assert "Report for demo-dental" in result.stdout
    assert "Clicks: 1234" in result.stdout


def test_missing_key_errors(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl.md"
    tpl.write_text("Hello $name, your score is $score.\n", encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"name": "Suleyman"}), encoding="utf-8")  # score missing
    result = _run(tpl, data)
    assert result.returncode == 1
    assert "missing key" in result.stderr
    assert "score" in result.stderr
