"""Audit#2 Finding 1 + cross-cutting gap #1 (`test_public_docs_counts_match_filesystem`).

Batch-E locked the README counts/version against ground truth
(`test_readme_counts_match_filesystem.py`). This test EXTENDS that guarantee to
the other four public docs that carry machine-checkable capability counts:

  * `docs/INSTALL.md`        — status banner (command count + version)
  * `docs/ARCHITECTURE.md`   — engine version, v1 acceptance criteria
                               (command / schema / CSR counts), manifest section
  * `docs/REFERENCE_INDEX.md`— skill-catalog Q&A line (skill + command count)
  * `docs/WORKFLOWS.md`      — catalog header (skill count)

Ground truth is the filesystem (`commands/`, `skills/`, `schemas/`),
`.claude-plugin/plugin.json` (version), and the two invariant registries
(`schemas/cross-sheet-invariants.json` rules = declared CSR;
`scripts.validation.validate_invariants._RULE_FUNCTIONS` = implemented CSR) —
the SAME single source of truth `test_count_consistency.py` already locks the
manifests against. Add a command/skill/schema, bump the version, or land an
invariant, and every doc cite must move with it or this test fails.

The ARCHITECTURE per-phase "Skill Sayısı" column (a HISTORICAL per-phase
delivery log, reconciled by the +gbp-audit/+sf-crawl-orchestrator narrative) is
intentionally NOT asserted here — it is a different metric from the current
category totals and would be wrong to overwrite with live numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import validate_invariants

_ROOT = Path(__file__).resolve().parents[2]


# --- ground-truth counters (same convention as test_count_consistency.py) ----

def _n_commands() -> int:
    return len(list((_ROOT / "commands").glob("*.md")))


def _n_skills() -> int:
    return len(list((_ROOT / "skills").rglob("SKILL.md")))


def _n_schemas() -> int:
    return len(list((_ROOT / "schemas").glob("*.json")))


def _plugin_version() -> str:
    data = json.loads((_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return data["version"]


def _declared_csr() -> int:
    data = json.loads((_ROOT / "schemas" / "cross-sheet-invariants.json").read_text(encoding="utf-8"))
    return len(data["rules"])


def _implemented_csr() -> int:
    return len(validate_invariants._RULE_FUNCTIONS)


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


# --- INSTALL ----------------------------------------------------------------

def test_install_cites_command_count_and_version() -> None:
    doc = _read("docs/INSTALL.md")
    assert f"{_n_commands()} slash commands" in doc, "INSTALL banner must cite live command count"
    assert f"v{_plugin_version()}" in doc, "INSTALL banner must cite plugin.json version"


def test_install_has_no_stale_command_count() -> None:
    doc = _read("docs/INSTALL.md")
    assert "24 slash commands" not in doc


# --- ARCHITECTURE -----------------------------------------------------------

def test_architecture_cites_live_version() -> None:
    doc = _read("docs/ARCHITECTURE.md")
    assert f"v{_plugin_version()}" in doc, "ARCHITECTURE must cite the live engine version"
    assert "v1.9.4" not in doc, "stale 'engine v1.9.4' must be gone"


def test_architecture_cites_command_and_schema_counts() -> None:
    doc = _read("docs/ARCHITECTURE.md")
    assert f"{_n_commands()} command" in doc, "ARCHITECTURE must cite live command count"
    assert f"{_n_schemas()} schema" in doc, "ARCHITECTURE must cite live schema count"
    # stale live counts gone (per-phase historical Skill Sayısı column is a
    # different metric and is intentionally not swept).
    assert "18 command" not in doc
    assert "21 schema" not in doc


def test_architecture_cites_csr_declared_and_implemented() -> None:
    doc = _read("docs/ARCHITECTURE.md")
    assert f"{_declared_csr()} declared" in doc, "ARCHITECTURE must cite live declared CSR count"
    assert f"{_implemented_csr()} implemented" in doc, "ARCHITECTURE must cite live implemented CSR count"
    assert "31 declared" not in doc
    assert "24 implemented" not in doc


# --- REFERENCE_INDEX --------------------------------------------------------

def test_reference_index_cites_skill_and_command_counts() -> None:
    doc = _read("docs/REFERENCE_INDEX.md")
    assert f"{_n_skills()} skills" in doc
    assert f"{_n_commands()} commands" in doc
    assert "18 commands" not in doc


# --- WORKFLOWS --------------------------------------------------------------

def test_workflows_cites_skill_count() -> None:
    doc = _read("docs/WORKFLOWS.md")
    assert f"{_n_skills()} skill" in doc
