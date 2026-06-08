"""tests/docs/test_runbook_citations.py — keep the portfolio recovery runbook honest.

The recovery runbook (`docs/RUNBOOK-portfolio-recovery.md`, AMO batch 4e) tells a
non-coder operator the EXACT command to run for each Faz-4 failure mode. It is the
document the shipped `/pseo-run-portfolio` and `/pseo-schedule` commands route the
operator to ("4e recovery runbook"), so a dangling citation there is a dead end.

This is a light citation-EXISTENCE guard, not a linter: every `/pseo-*` command and
every `scripts/...py` path the runbook cites in backticks/fences must resolve to a
real file on disk (`commands/<name>.md` / the script path). It deliberately only
inspects tokens that clearly look like a command or a script path — so prose is
never falsely flagged, and operator/runtime state files (`shared/*.json`,
`shared/cost_ledger.jsonl`, `shared/locks/<slug>.lock`) are not asserted to exist
(they are created at runtime, not shipped). The goal is "no dangling citation".
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_RUNBOOK = _REPO / "docs" / "RUNBOOK-portfolio-recovery.md"

# A /pseo-* slash command token: a leading slash, then lowercase + digits + hyphen.
# Stops at the first space/placeholder, so "/pseo-schedule arm <wf>" -> "pseo-schedule".
_COMMAND_RE = re.compile(r"/pseo-[a-z0-9-]+")
# A slash-form script path: scripts/.../<name>.py.
_SCRIPT_SLASH_RE = re.compile(r"scripts/[A-Za-z0-9_/]+\.py")
# A `python3 -m scripts.pkg.mod` module path (the real cost_ledger CLI form).
_SCRIPT_MODULE_RE = re.compile(r"-m\s+(scripts(?:\.[A-Za-z0-9_]+)+)")


def _code_regions(text: str) -> str:
    """Return only the fenced-code + inline-code text (where citations live).

    Fenced ```...``` blocks are pulled first and blanked out, then single-backtick
    inline spans are pulled from the remainder — so a fence delimiter can never be
    misread as an inline span, and prose outside backticks is ignored (tolerant).
    """
    fenced = re.findall(r"```.*?```", text, flags=re.DOTALL)
    without_fenced = re.sub(r"```.*?```", "\n", text, flags=re.DOTALL)
    inline = re.findall(r"`[^`\n]+`", without_fenced)
    return "\n".join(fenced + inline)


def _command_citations(code_text: str) -> set[str]:
    """Cited command names (without the leading slash), e.g. {'pseo-run-portfolio'}."""
    return {match.lstrip("/").rstrip("-") for match in _COMMAND_RE.findall(code_text)}


def _script_citations(code_text: str) -> set[str]:
    """Cited repo-relative script paths from BOTH the slash form and the `-m` form."""
    paths = set(_SCRIPT_SLASH_RE.findall(code_text))
    for dotted in _SCRIPT_MODULE_RE.findall(code_text):
        paths.add(dotted.replace(".", "/") + ".py")
    return paths


def _missing_commands(names: set[str]) -> set[str]:
    """Command names whose `commands/<name>.md` file is absent."""
    return {name for name in names if not (_REPO / "commands" / f"{name}.md").is_file()}


def _missing_scripts(paths: set[str]) -> set[str]:
    """Cited script paths that are absent on disk."""
    return {path for path in paths if not (_REPO / path).is_file()}


def _runbook_code() -> str:
    return _code_regions(_RUNBOOK.read_text(encoding="utf-8"))


def test_runbook_exists() -> None:
    """The runbook itself must be present (batch 4e deliverable)."""
    assert _RUNBOOK.is_file(), f"missing runbook: {_RUNBOOK}"


def test_runbook_cites_commands_and_scripts() -> None:
    """Non-vacuity guard: extraction must actually find citations, so a broken
    regex can't make the existence checks below pass by matching nothing."""
    code = _runbook_code()
    assert _command_citations(code), "runbook cites no /pseo-* commands — extraction broke?"
    assert _script_citations(code), "runbook cites no scripts/...py paths — extraction broke?"


def test_runbook_command_citations_exist() -> None:
    """Every /pseo-* command the runbook cites must resolve to a commands/<name>.md."""
    missing = _missing_commands(_command_citations(_runbook_code()))
    assert not missing, f"runbook cites command file(s) that do not exist: {sorted(missing)}"


def test_runbook_script_citations_exist() -> None:
    """Every scripts/...py path the runbook cites (slash or `-m` form) must exist."""
    missing = _missing_scripts(_script_citations(_runbook_code()))
    assert not missing, f"runbook cites script path(s) that do not exist: {sorted(missing)}"


def test_guard_detects_dangling_citation() -> None:
    """Teeth: the same helpers MUST flag a dangling command/script citation — proof
    the existence checks above are not vacuous (they would go RED on a typo'd cite)."""
    synthetic = (
        "`/pseo-bogus-command` and `scripts/nope/does_not_exist.py` "
        "and `python3 -m scripts.fake.module usage x y`"
    )
    code = _code_regions(synthetic)

    commands = _command_citations(code)
    assert "pseo-bogus-command" in commands
    assert _missing_commands(commands) == {"pseo-bogus-command"}

    scripts = _script_citations(code)
    assert "scripts/nope/does_not_exist.py" in scripts
    assert "scripts/fake/module.py" in scripts  # the `-m` module form is resolved too
    assert _missing_scripts(scripts) == {
        "scripts/nope/does_not_exist.py",
        "scripts/fake/module.py",
    }
