"""scripts/ci/run_skill_python.py — Markdown-aware Python block extractor + executor.

Skill SKILL.md body'lerinden ```python ... ``` bloklarini extract eder, sirali
concat eder, subprocess ile execute eder. Skill = SKILL.md text + multi-block
executable Python (line-by-line) — Python module DEGIL (lesson 8 v5 boyut #6,
manager pre-dispatch finding F-14W2-1 Phase 14 W2).

Phase 14 W2 Suleyman Secenek B onayi (helper script abstraction layer, skill
body single source of truth, lesson 31+34 schema-first paterni reuse). Phase
14 W3 pilot E2E'de reusable (init-project -> ingest -> discovery -> planning ->
reporting -> production -> verify governance check'leri).

Note: subprocess.run() is used (NOT shell=True, NOT exec()) — list-arg form is
safe from injection (sys.executable + tmp_path local-only).
"""
import re
import subprocess  # noqa: S404 — list-arg form, no shell injection
import sys
import tempfile
from pathlib import Path


PYTHON_BLOCK_RE = re.compile(
    r"^```python\s*$\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


def extract_python_blocks(skill_md_text: str) -> list[str]:
    """Extract all ```python ... ``` code blocks from SKILL.md body, in order.

    Q-CI-W3-02 auto-prepend: if no block contains the sys.path.insert(0, os.getcwd())
    marker, prepend a multi-line setup block so concat exec resolves scripts.* package
    imports. F-14W3W3α-4 catch: substring-key detection respects multi-line format
    (semicolon-tek-satır format kaçın — see rules/skills.md Section 3).
    """
    blocks = [match.group(1).rstrip() for match in PYTHON_BLOCK_RE.finditer(skill_md_text)]
    if blocks:
        sys_path_marker = "sys.path.insert(0, os.getcwd())"
        if not any(sys_path_marker in b for b in blocks):
            blocks.insert(0, "import os, sys\nsys.path.insert(0, os.getcwd())")
    return blocks


def run_skill_python(skill_md_path: Path) -> int:
    """Extract + concat + execute Python blocks from SKILL.md.

    Returns:
      0 if no Python blocks (AMBER, skill is prompt-only) OR all blocks PASS
      non-zero if any block fails (FAIL preservation, syntax/runtime error)
      2 if SKILL.md path not found
    """
    if not skill_md_path.exists():
        print(f"ERROR: SKILL.md not found: {skill_md_path}", file=sys.stderr)
        return 2

    body = skill_md_path.read_text(encoding="utf-8")
    blocks = extract_python_blocks(body)

    if not blocks:
        print(f"AMBER: No Python blocks in {skill_md_path} (prompt-only skill, exit 0)")
        return 0

    # Concat blocks order-preserved (skill body workflow step-by-step)
    concat_script = "\n\n# --- BLOCK SEPARATOR ---\n\n".join(blocks)

    # Temp file + subprocess for clean isolation (list-arg, no shell)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        tf.write(concat_script)
        tmp_path = tf.name

    try:
        result = subprocess.run(  # noqa: S603 — sys.executable + local tmp_path, no shell
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <SKILL.md path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run_skill_python(Path(sys.argv[1])))
