"""tests/scripts/test_path_canonical.py — project.config.json path canonical (ADR-033).

Canonical location is `projects/{slug}/project.config.json` — no `config/`
subfolder, no hyphenated `project-config.json` variant. This test greps the
plugin tree for the two forbidden patterns; any reintroduction fails the
suite.

Excluded paths:
  - .git/, __pycache__/, *.pyc — VCS / Python bytecode noise.
  - docs/CONTEXT_LEDGER.md, docs/DECISIONS.md, docs/DECISIONS_ARCHIVE.md,
    docs/OPEN_QUESTIONS.md — historical narrative + ADRs that document the
    rename; preserves the audit trail.
  - docs/superpowers/plans/ — past planning docs reference the previous layout.
  - This test file itself (the patterns appear inside the regex strings).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Two forbidden forms.  Both are word-style patterns (regex applied per line).
FORBIDDEN_PATTERNS = (
    re.compile(r"projects/\{slug\}/config/project\.config\.json"),
    re.compile(r"\bproject-config\.json\b"),
)

# Files / directories whose contents are exempt from the sweep.
EXEMPT_PARTS = (
    ".git",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
)
EXEMPT_RELATIVE_PATHS = {
    Path("docs/CONTEXT_LEDGER.md"),
    Path("docs/DECISIONS.md"),
    Path("docs/DECISIONS_ARCHIVE.md"),
    Path("docs/OPEN_QUESTIONS.md"),
    Path("tests/scripts/test_path_canonical.py"),
}
EXEMPT_PREFIXES = (Path("docs/superpowers/plans"),)

TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".sh", ".txt", ".toml"}


def _iter_text_files() -> list[Path]:
    files = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXEMPT_PARTS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(REPO)
        if rel in EXEMPT_RELATIVE_PATHS:
            continue
        if any(rel.is_relative_to(prefix) for prefix in EXEMPT_PREFIXES):
            continue
        files.append(path)
    return files


@pytest.mark.parametrize(
    "pattern",
    FORBIDDEN_PATTERNS,
    ids=lambda p: p.pattern,
)
def test_no_drift_pattern(pattern: re.Pattern[str]) -> None:
    """No file under the engine root may use a forbidden project.config.json
    path form.  Canonical is `projects/{slug}/project.config.json` (ADR-033)."""
    hits: list[str] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = path.relative_to(REPO)
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    assert not hits, (
        "ADR-033 drift detected — forbidden pattern reintroduced.\n"
        + "\n".join(hits[:20])
        + ("\n...(truncated)" if len(hits) > 20 else "")
    )
