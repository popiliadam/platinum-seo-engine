"""tests/ci/test_run_skill_python.py — run_skill_python helper invariant test."""
import subprocess
import sys
import tempfile
from pathlib import Path


HELPER = Path(__file__).resolve().parents[2] / "scripts/ci/run_skill_python.py"


def _run_helper(skill_md_text: str) -> subprocess.CompletedProcess:
    """Helper: write skill_md_text to temp file, run helper, capture output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tf:
        tf.write(skill_md_text)
        tmp_path = tf.name
    try:
        return subprocess.run(
            [sys.executable, str(HELPER), tmp_path],
            capture_output=True,
            text=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_helper_exists_and_executable():
    assert HELPER.exists(), f"Helper not found: {HELPER}"
    assert HELPER.is_file()


def test_extracts_single_python_block():
    md = "Some text\n\n```python\nprint('hello')\n```\n\nMore text"
    result = _run_helper(md)
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_extracts_multi_block_order_preserved():
    md = """Block 1:
```python
x = 1
```
Block 2:
```python
print(x + 10)  # x from block 1, order-preserved
```
"""
    result = _run_helper(md)
    assert result.returncode == 0
    assert "11" in result.stdout


def test_empty_skill_md_amber_exit_zero():
    """No Python blocks -> AMBER + exit 0 (prompt-only skill semantik)."""
    md = "# Skill prompt\n\nNo code blocks here, just LLM prompt instructions."
    result = _run_helper(md)
    assert result.returncode == 0
    assert "AMBER" in result.stdout or "AMBER" in result.stderr


def test_python_syntax_error_fail_preserved():
    """Python syntax error -> exit non-zero (FAIL preservation)."""
    md = "```python\nthis is not valid python syntax !\n```"
    result = _run_helper(md)
    assert result.returncode != 0


def test_python_runtime_error_fail_preserved():
    """Python runtime error -> exit non-zero (FAIL preservation)."""
    md = "```python\nraise ValueError('intentional fail')\n```"
    result = _run_helper(md)
    assert result.returncode != 0
    assert "ValueError" in result.stderr


def test_stderr_capture():
    md = "```python\nimport sys; print('to stderr', file=sys.stderr)\n```"
    result = _run_helper(md)
    assert "to stderr" in result.stderr


def test_skill_md_path_not_found():
    """Missing path -> exit 2 (usage error)."""
    result = subprocess.run(
        [sys.executable, str(HELPER), "/nonexistent/path/SKILL.md"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
