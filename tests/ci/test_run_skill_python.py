"""tests/ci/test_run_skill_python.py — run_skill_python helper invariant test."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


HELPER = Path(__file__).resolve().parents[2] / "scripts/ci/run_skill_python.py"


def _load_helper_module():
    """Load run_skill_python module dynamically for in-process function testing."""
    spec = importlib.util.spec_from_file_location("run_skill_python_helper", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# Q-CI-W3-02 substring-key auto-prepend tests (Phase 14 W3-W3-α).
# Helper detects sys.path.insert(0, os.getcwd()) marker in any block; if missing,
# prepends a multi-line setup block (NOT semicolon-tek-satır format —
# rules/skills.md Section 3 KRİTİK respect).

def test_auto_prepend_skips_when_marker_exists():
    """Q-CI-W3-02: if marker present (multi-line format), skip prepend."""
    helper = _load_helper_module()
    skill_md_with_marker = """```python
import os, sys
sys.path.insert(0, os.getcwd())
print("hello")
```
"""
    blocks = helper.extract_python_blocks(skill_md_with_marker)
    assert len(blocks) == 1, f"expected 1 block (no prepend), got {len(blocks)}"
    # Single block contains marker — no helper-injected prepend block.
    assert "sys.path.insert(0, os.getcwd())" in blocks[0]


def test_auto_prepend_when_marker_missing():
    """Q-CI-W3-02: if marker absent, prepend multi-line setup block."""
    helper = _load_helper_module()
    skill_md_without_marker = """```python
print("hello")
```
"""
    blocks = helper.extract_python_blocks(skill_md_without_marker)
    assert len(blocks) == 2, f"expected 2 blocks (1 prepend + 1 original), got {len(blocks)}"
    # Prepend block is first, multi-line format (newline between import + sys.path call).
    assert "sys.path.insert(0, os.getcwd())" in blocks[0]
    assert "import os, sys\n" in blocks[0]


def test_auto_prepend_multi_line_format_respect():
    """Q-CI-W3-02 + F-14W3W3α-4 catch: prepended block is multi-line, NOT semicolon."""
    helper = _load_helper_module()
    blocks = helper.extract_python_blocks("```python\nprint('x')\n```")
    # Prepend block must be multi-line (rules/skills.md Section 3 KRİTİK).
    assert blocks[0] == "import os, sys\nsys.path.insert(0, os.getcwd())"
    # Semicolon-tek-satır format YASAK in prepend.
    assert ";" not in blocks[0]


def test_no_prepend_for_empty_skill():
    """Empty skill (no Python blocks) gets no prepend (AMBER prompt-only)."""
    helper = _load_helper_module()
    blocks = helper.extract_python_blocks("# Just markdown text, no code blocks")
    assert blocks == [], "empty skill should produce empty block list (no spurious prepend)"
