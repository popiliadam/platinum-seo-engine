"""tests/scripts/test_template_refs.py — template reference existence invariant.

Every explicit ``templates/<subdir>/<name>.template.md`` reference under
``commands/`` , ``skills/`` , ``scripts/`` , and ``rules/`` MUST resolve
to a file on disk (Wave 3 — Codex broken-ref sweep, ADR-036 release prep).

Forbidden patterns (catches a known drift case):
  - bare ``monthly.template.md`` — alias collision; canonical is
    ``monthly-report.template.md``.

Exempt paths (historical narrative + spec docs):
  - ``docs/CONTEXT_LEDGER.md``, ``docs/PHASE_STATUS.md``,
    ``docs/DECISIONS.md``, ``docs/DECISIONS_ARCHIVE.md``,
    ``docs/OPEN_QUESTIONS.md``
  - ``docs/superpowers/`` subtree (specs + plans)
  - the ``templates/`` directory itself (the files reference each
    other in headers / metadata)
  - this test file
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "templates"

EXPLICIT_REF = re.compile(r"templates/([a-z]+)/([a-zA-Z0-9_-]+)\.template\.(md|html)")
BARE_FORBIDDEN = (
    # canonical is monthly-report.template.md
    re.compile(r"\bmonthly\.template\.md\b"),
)

EXEMPT_RELATIVE_PATHS = {
    Path("docs/CONTEXT_LEDGER.md"),
    Path("docs/PHASE_STATUS.md"),
    Path("docs/DECISIONS.md"),
    Path("docs/DECISIONS_ARCHIVE.md"),
    Path("docs/OPEN_QUESTIONS.md"),
    Path("tests/scripts/test_template_refs.py"),
}
# Historical release notes describe past drift fixes by name; bare aliases
# show up as historical narrative, not active references.  Same exclusion
# pattern as CONTEXT_LEDGER / PHASE_STATUS.
EXEMPT_GLOB_RELATIVE = ("docs/RELEASE_NOTES_v*.md",)
EXEMPT_PREFIXES = (
    Path("docs/superpowers"),
    Path("templates"),
    Path(".git"),
    Path(".claude"),
    Path("__pycache__"),
    Path("node_modules"),
    Path(".pytest_cache"),
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".sh", ".txt", ".toml"}


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(REPO)
        if rel in EXEMPT_RELATIVE_PATHS:
            continue
        if any(rel.is_relative_to(prefix) for prefix in EXEMPT_PREFIXES):
            continue
        if any(rel.match(pat) for pat in EXEMPT_GLOB_RELATIVE):
            continue
        files.append(path)
    return files


def test_templates_directory_present() -> None:
    """Sanity: templates/ root + reports + content subdirs exist."""
    assert TEMPLATES.is_dir(), f"{TEMPLATES} missing"
    assert (TEMPLATES / "reports").is_dir(), "templates/reports missing"
    assert (TEMPLATES / "content").is_dir(), "templates/content missing"


def test_explicit_template_refs_resolve() -> None:
    """Every ``templates/<subdir>/<name>.template.<md|html>`` ref must exist."""
    missing: list[str] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in EXPLICIT_REF.finditer(line):
                subdir, name, suffix = m.group(1), m.group(2), m.group(3)
                target = TEMPLATES / subdir / f"{name}.template.{suffix}"
                if not target.is_file():
                    rel = path.relative_to(REPO)
                    missing.append(
                        f"{rel}:{lineno}: -> {target.relative_to(REPO)} not found"
                    )
    assert not missing, (
        "Broken template references — every explicit "
        "templates/<subdir>/<name>.template.{md|html} ref must resolve.\n"
        + "\n".join(missing[:30])
        + ("\n...(truncated)" if len(missing) > 30 else "")
    )


@pytest.mark.parametrize("pattern", BARE_FORBIDDEN, ids=lambda p: p.pattern)
def test_no_forbidden_bare_alias(pattern: re.Pattern[str]) -> None:
    """Disallow known stale aliases (e.g., bare ``monthly.template.md``)."""
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
        f"Forbidden bare alias `{pattern.pattern}` reintroduced.\n"
        + "\n".join(hits)
    )
