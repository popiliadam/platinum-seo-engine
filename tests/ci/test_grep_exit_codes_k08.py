"""K-08 — a failing grep tool must fail the step, not pass it.

`! git grep …` read every non-zero exit as PASS: a broken regex (exit 2) or a
git error (128) passed, and `!` disables `set -e`. The wrapper and CI step 5
now read the exit code explicitly.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_git_error_fails_the_wrapper(tmp_path: Path) -> None:
    # Same layout, but NOT a git repository -> git grep exits 128.
    for rel in ("scripts/ci/check_secrets.sh", "scripts/security/check_secrets.sh"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    proc = subprocess.run(["bash", str(tmp_path / "scripts/ci/check_secrets.sh")],
                          capture_output=True, text=True, cwd=tmp_path, timeout=120)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "git grep itself failed" in proc.stderr


def test_wrapper_has_no_negated_grep() -> None:
    text = (ROOT / "scripts/ci/check_secrets.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "! git grep" not in code and "rc=$?" in code


def test_ci_step_5_reads_the_exit_code() -> None:
    cfg = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    step = next(s for s in cfg["jobs"]["ci"]["steps"] if s.get("name") == "5. plugin-agnostik-grep")
    assert "! grep" not in step["run"] and 'rc=$?' in step["run"]


def test_ci_pytest_has_a_coverage_floor() -> None:
    """K-15: a coverage drop below the floor fails CI step 4."""
    cfg = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    step = next(s for s in cfg["jobs"]["ci"]["steps"] if s.get("name") == "4. pytest")
    assert "--cov-fail-under=" in step["run"]
    lock = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    assert "pytest-cov==" in lock and "coverage==" in lock
