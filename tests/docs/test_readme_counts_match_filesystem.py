"""Batch-E finding 15 — README count/version drift guard.

The README accumulated stale capability counts and a stale version banner while
the canonical manifests (.claude-plugin/plugin.json + marketplace.json) and the
filesystem moved on:

  * "18 slash commands" / "18 slash cmds" / "24 commands"  vs  25 commands on disk
  * "21 schemas" / "21 JSON"                                vs  27 schemas/ *.json
  * "1,100+ pytest tests"                                   vs  a ~2.4k suite
  * "Current: v1.9.5"                                       vs  plugin.json 2.0.0

Like test_count_consistency.py (which locks the *manifests*), this test reads
GROUND TRUTH — filesystem globs for counts, plugin.json for the version — so
every count/version snippet in the README self-reconciles. Add a command, a
skill, a schema, or bump the version, and the matching README cite must move
with it or this test fails. The volatile pytest count is deliberately NOT
re-locked to a number (it rots every release — see
test_marketplace_no_hardcoded_pytest_count.py); the README must phrase the test
suite count-free instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_README = (_ROOT / "README.md").read_text(encoding="utf-8")


# --- ground-truth counters (same convention as test_count_consistency.py) ----

def _n_commands() -> int:
    return len(list((_ROOT / "commands").glob("*.md")))


def _n_skills() -> int:
    return len(list((_ROOT / "skills").rglob("SKILL.md")))


def _n_schemas() -> int:
    return len(list((_ROOT / "schemas").glob("*.json")))


def _n_schema_files() -> int:
    return len(list((_ROOT / "schemas").glob("*.schema.json")))


def _n_hooks() -> int:
    return len(list((_ROOT / "hooks").glob("*.json")))


def _plugin_version() -> str:
    data = json.loads((_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return data["version"]


# --- counts present and correct ---------------------------------------------

def test_readme_command_counts_match_filesystem() -> None:
    n = _n_commands()
    # status banner ("· 25 commands ·"), prose ("25 slash commands"),
    # architecture diagram ("25 slash cmds")
    assert f"{n} commands" in _README, f"status banner must cite {n} commands"
    assert f"{n} slash commands" in _README, f"prose must cite {n} slash commands"
    assert f"{n} slash cmds" in _README, f"diagram must cite {n} slash cmds"


def test_readme_skill_count_matches_filesystem() -> None:
    assert f"{_n_skills()} skills" in _README


def test_readme_schema_counts_match_filesystem() -> None:
    total, files = _n_schemas(), _n_schema_files()
    assert f"{total} schemas" in _README, f"must cite {total} schemas"
    assert f"{total} JSON" in _README, f"diagram must cite {total} JSON Schemas"
    # the breakdown line: "<files> *.schema.json + cross-sheet-invariants.json"
    assert f"{files} `*.schema.json`" in _README, (
        f"schema breakdown must cite {files} *.schema.json files"
    )


def test_readme_hook_count_matches_filesystem() -> None:
    assert f"{_n_hooks()} hooks" in _README


def test_readme_version_matches_plugin_json() -> None:
    version = _plugin_version()
    status = [ln for ln in _README.splitlines() if ln.startswith("> Status:")]
    current = [ln for ln in _README.splitlines() if "**Current:**" in ln]
    assert status and f"v{version}" in status[0], (
        f"status banner must cite v{version} (plugin.json version)"
    )
    assert current and f"v{version}" in current[0], (
        f"'Current:' line must cite v{version} (plugin.json version)"
    )
    assert f"RELEASE_NOTES_v{version}.md" in _README, (
        f"'Latest release' link must point at RELEASE_NOTES_v{version}.md"
    )


# --- stale snippets must be gone ---------------------------------------------

def test_readme_has_no_stale_counts() -> None:
    for stale in ("18 slash commands", "18 slash cmds", "24 commands",
                  "21 schemas", "21 JSON"):
        assert stale not in _README, f"stale count still present: {stale!r}"


def test_readme_does_not_hardcode_a_pytest_count() -> None:
    # The pytest total is volatile and rots every release; the README must phrase
    # it count-free (no "1,100+ pytest tests" / "N,NNN pytest tests").
    assert "1,100+" not in _README
    assert not re.search(r"[\d,]{3,}\+?\s+pytest", _README), (
        "Remove the hardcoded pytest count from the README — phrase the suite "
        "count-free so it does not rot every release."
    )
