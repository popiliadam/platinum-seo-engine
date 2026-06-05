"""Smoke tests for scripts/reporting/render_template.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "reporting" / "render_template.py"

sys.path.insert(0, str(REPO))
from scripts.reporting import render_template  # noqa: E402


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


# ---------------------------------------------------------------------------
# render() wrapper — the programmatic API the ingestion-skill bodies call
# (sf-crawl-orchestrator Step 8). B3-01: the function the SKILL.md documented
# did not exist (AttributeError at runtime). These tests lock its contract.
# ---------------------------------------------------------------------------

def test_render_writes_output_and_returns_path(tmp_path: Path) -> None:
    """render(template_path, output_path, variables) substitutes the supplied
    $vars, writes the rendered Markdown to output_path, and returns that Path."""
    tpl = tmp_path / "report.template.md"
    tpl.write_text("# $title\n\nRows: $rows / Run: $run_id\n", encoding="utf-8")
    out = tmp_path / "nested" / "out" / "2026-06-05-report.md"  # parents missing on purpose

    returned = render_template.render(
        template_path=tpl,
        output_path=out,
        variables={"title": "SF Crawl", "rows": 24, "run_id": "abc-001"},
    )

    assert returned == out, "render() must return the output Path"
    assert out.exists(), "render() must create parent dirs and write the file"
    body = out.read_text(encoding="utf-8")
    assert "# SF Crawl" in body
    assert "Rows: 24 / Run: abc-001" in body  # non-str values stringified


def test_render_leaves_unsupplied_tokens_verbatim(tmp_path: Path) -> None:
    """The wrapper is called at the FINAL step of an expensive crawl; a missing
    cosmetic token must NOT discard a completed run. render() uses
    safe_substitute, so an unsupplied $token is left visible, not raised."""
    tpl = tmp_path / "t.md"
    tpl.write_text("$present and $absent\n", encoding="utf-8")
    out = tmp_path / "o.md"

    render_template.render(template_path=tpl, output_path=out,
                           variables={"present": "HERE"})

    body = out.read_text(encoding="utf-8")
    assert "HERE and $absent" in body, "unsupplied token must remain verbatim"
