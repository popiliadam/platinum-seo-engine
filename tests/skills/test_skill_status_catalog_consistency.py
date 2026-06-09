"""tests/skills/test_skill_status_catalog_consistency.py — Audit#2 F9 + status catalog.

Two concerns, both about *truth-in-advertising* for a skill's lifecycle:

  1. F9 — monitoring-weekly carried frontmatter ``status: active`` while its body
     admits two of its reported outputs (GSC week-over-week delta + budget burn)
     are PLACEHOLDER strings deferred to Phase 14+, not computed. A skill that
     advertises ``active`` must not silently ship placeholder outputs. Operator
     decision: demote-to-wip (honest). This file locks that demotion AND that the
     honesty rationale (the body STILL openly declares the deferral) stays true.

  2. CATALOG PARITY — a skill's frontmatter ``status:`` is the source of truth;
     the human-facing catalog (docs/WORKFLOWS.md status column) must not over-claim
     a more production-ready lifecycle than the frontmatter. This is the integration
     guard: it goes green once BOTH the frontmatter (this worker) and the docs table
     (the DOCS worker, who owns docs/WORKFLOWS.md) agree.

     ⚠️ SOLO-RUN NOTE (attribute, do not silence): during the SKILLS-SCRIPTS
     worker's solo run the doc side LAGS — docs/WORKFLOWS.md still lists several
     wip-in-frontmatter skills as ``active`` (a PRE-EXISTING drift, plus
     monitoring-weekly once this worker demotes it). docs/WORKFLOWS.md is the DOCS
     worker's file (forbidden to this worker), so the catalog-parity test is
     EXPECTED to be red here and flips green when the combined tree carries both
     halves. The drift list is printed verbatim so the cause is unambiguous.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
WORKFLOWS = ROOT / "docs" / "WORKFLOWS.md"

_VALID_STATUS = {"active", "wip", "deprecated"}
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# A WORKFLOWS catalog row: | `skill-name` | "...trigger..." | status |
_CATALOG_ROW_RE = re.compile(r"`([a-z][a-z0-9-]*)`")


def _skill_files() -> list[Path]:
    return sorted(SKILLS.glob("**/SKILL.md"))


def _frontmatter_status() -> dict[str, str]:
    """name -> frontmatter status, for every skill on disk."""
    out: dict[str, str] = {}
    for path in _skill_files():
        m = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        name, status = fm.get("name"), fm.get("status")
        if isinstance(name, str) and isinstance(status, str):
            out[name] = status
    return out


def _workflows_catalog_status() -> dict[str, str]:
    """name -> status, parsed from the docs/WORKFLOWS.md catalog table rows."""
    out: dict[str, str] = {}
    if not WORKFLOWS.exists():
        return out
    for line in WORKFLOWS.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        statuses = [c for c in cells if c in _VALID_STATUS]
        name_match = _CATALOG_ROW_RE.search(line)
        if name_match and len(statuses) == 1:
            out[name_match.group(1)] = statuses[0]
    return out


# ---------------------------------------------------------------------------
# F9 — monitoring-weekly demoted to wip (self-contained; green in solo run)
# ---------------------------------------------------------------------------

def test_monitoring_weekly_demoted_to_wip_with_honest_body() -> None:
    """F9: monitoring-weekly must be ``status: wip`` because its body openly
    admits the GSC delta + budget-burn outputs are Phase-14+ PLACEHOLDERS, not
    computed. Asserts BOTH the demotion AND that the honesty rationale holds (the
    placeholder admission is still present — a demote without the honest body
    would just be hiding the lie differently)."""
    path = SKILLS / "reporting" / "monitoring-weekly" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    fm = yaml.safe_load(_FRONTMATTER_RE.match(text).group(1))

    assert fm["status"] == "wip", (
        "monitoring-weekly must be demoted to status: wip — its GSC week-over-week "
        "delta and budget-burn outputs are Phase-14+ placeholders, not computed "
        f"(got status={fm['status']!r})"
    )
    # The honest body must STILL declare the deferral (so wip is justified).
    body = text[_FRONTMATTER_RE.match(text).end():]
    assert "PLACEHOLDER" in body, (
        "monitoring-weekly body must keep the honest PLACEHOLDER deferral note"
    )
    assert re.search(r"Phase 14\+", body), (
        "monitoring-weekly body must name the Phase-14+ deferral target"
    )


# ---------------------------------------------------------------------------
# CATALOG PARITY — frontmatter status must not be over-claimed by WORKFLOWS.md
# (integration guard; SOLO-RUN red is doc-lag — see module docstring)
# ---------------------------------------------------------------------------

def test_skill_frontmatter_status_matches_workflows_catalog() -> None:
    """Every skill listed in docs/WORKFLOWS.md must carry the same lifecycle
    status as its SKILL.md frontmatter (frontmatter is the source of truth)."""
    fm = _frontmatter_status()
    catalog = _workflows_catalog_status()
    assert catalog, "docs/WORKFLOWS.md parsed no catalog status rows"

    drift = [
        (name, f"WORKFLOWS={catalog[name]}", f"frontmatter={fm[name]}")
        for name in sorted(catalog)
        if name in fm and catalog[name] != fm[name]
    ]
    assert not drift, (
        "Skill lifecycle status drifts between docs/WORKFLOWS.md and SKILL.md "
        "frontmatter (frontmatter wins — the doc catalog must be demoted to "
        "match). Integration guard: this is red during the SKILLS-SCRIPTS solo "
        "run because docs/WORKFLOWS.md is the DOCS worker's file:\n"
        + "\n".join(f"  {n}: {a} != {b}" for n, a, b in drift)
    )
