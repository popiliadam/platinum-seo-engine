"""K-07 — the glossary step reports what it computes and can go red."""
from __future__ import annotations

from pathlib import Path

import yaml

from scripts.ci import glossary_gate as gg

ROOT = Path(__file__).resolve().parents[2]
SPEC = "## 20. Glossary\n- **Skill:** a capability\n- **Pilot Proje:** the pilot\n## 21. Next\n"
GLOSS = "# Glossary\n- **Skill** — x\n- **Pilot Project** — y\n"


def test_clean_inputs_pass() -> None:
    rep = gg.evaluate(GLOSS, SPEC, "see GLOSSARY.md", "a skill and the pilot project")
    assert rep["problems"] == []


def test_invented_term_is_an_orphan_and_turns_red() -> None:
    gloss = GLOSS + "- **Quantum Funnel** — invented\n- **Hyper Silo** — invented\n"
    rep = gg.evaluate(gloss, SPEC, "see GLOSSARY.md", "a skill and the pilot project")
    assert rep["orphans"] == ["Hyper Silo", "Quantum Funnel"] and rep["problems"]


def test_spec_term_missing_from_glossary_is_red() -> None:
    rep = gg.evaluate("# Glossary\n- **Skill** — x\n", SPEC, "GLOSSARY.md", "skill")
    assert rep["missing_from_glossary"] == ["Pilot Project"]


def test_lost_reference_index_link_is_red() -> None:
    assert gg.evaluate(GLOSS, SPEC, "no link", "skill pilot project")["problems"]


def test_repo_passes_and_ci_runs_the_gate() -> None:
    assert gg.main() == 0
    cfg = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    step = next(s for s in cfg["jobs"]["ci"]["steps"] if s.get("name") == "3. glossary-audit")
    assert step["run"].strip() == "python3 scripts/ci/glossary_gate.py"
