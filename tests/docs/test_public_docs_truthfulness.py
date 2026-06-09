"""Audit#2 Findings 2/4/5/9/10 (doc side) — public-doc truthfulness guards.

Three contradiction classes the hostile audit caught between the docs and the
runtime/source of truth:

  * F5  — README/INSTALL "verify SF MCP" steps `curl .../mcp/tools`, a route that
          does not exist. SF 24's MCP is Streamable-HTTP (session-based,
          `Mcp-Session-Id`); the canonical probe is `SfMcpClient.health()` in
          `scripts/util/sf_mcp_client.py` (initialize -> notifications/initialized
          -> tools/call). Docs must not advertise the dead route and must point at
          the real client.
  * F10 — README/INSTALL present a concrete SF `allowed_directory` path as if it
          were the default; the real bootstrap/migration default is `None`
          (`migration_0005 ... DEFAULT_SF_MCP["allowed_directory"] = None`), so
          F-15 path isolation is OPT-IN until configured. WORKFLOWS went further
          and falsely claimed the migration *populates* that path.
  * F2/F4/F9 — README/ARCHITECTURE phase tables mark Production (Phase 11) +
          Publishing (Phase 12) "done", and WORKFLOWS marks their skills
          "active", while every one of those skills' frontmatter says `status:
          wip` (runtime deferred). The docs must MATCH the frontmatter — the
          single source of truth — rather than over-advertise.

Each WIP fact is RE-DERIVED from skill frontmatter at test time, so the guard
tracks the runtime instead of a hardcoded snapshot.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_PUBLIC_DOCS = (
    "README.md",
    "docs/INSTALL.md",
    "docs/ARCHITECTURE.md",
    "docs/REFERENCE_INDEX.md",
    "docs/WORKFLOWS.md",
)


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


# --- frontmatter ground truth -----------------------------------------------

def _frontmatter_status(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text
    m = re.search(r"^status:\s*(\S+)", block, re.M)
    return m.group(1) if m else None


def _wip_skills() -> set[str]:
    """Directory names of skills whose frontmatter says status: wip."""
    out: set[str] = set()
    for p in (_ROOT / "skills").rglob("SKILL.md"):
        if _frontmatter_status(p) == "wip":
            out.add(p.parent.name)
    return out


# --- small markdown-row helpers ---------------------------------------------

def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _skill_row(doc: str, skill: str) -> str | None:
    for line in doc.splitlines():
        if re.match(rf"^\|\s*`{re.escape(skill)}`", line):
            return line
    return None


def _phase_row(doc: str, label: str) -> str | None:
    for line in doc.splitlines():
        if line.lstrip().startswith("|") and label in line:
            return line
    return None


# --- F5: obsolete SF probe ---------------------------------------------------

def test_docs_have_no_obsolete_sf_mcp_tools_route() -> None:
    for rel in _PUBLIC_DOCS:
        assert "/mcp/tools" not in _read(rel), (
            f"{rel} still verifies SF MCP via the non-existent '/mcp/tools' route"
        )


def test_sf_verification_points_at_canonical_client() -> None:
    for rel in ("README.md", "docs/INSTALL.md"):
        assert "sf_mcp_client.py" in _read(rel), (
            f"{rel} SF verification must point at the canonical client "
            f"(scripts/util/sf_mcp_client.py), not a bare curl"
        )


# --- F10: SF allowed_directory honesty --------------------------------------

def test_workflows_does_not_claim_migration_populates_sf_path() -> None:
    doc = _read("docs/WORKFLOWS.md")
    assert "allowed_directory=/Users/apple/seo_spider_mcp_server" not in doc, (
        "WORKFLOWS falsely claims migration_0005 populates allowed_directory with "
        "a concrete path; it sets allowed_directory=None"
    )
    assert "allowed_directory=null" in doc, (
        "WORKFLOWS must state the real migration default (allowed_directory=null)"
    )


def test_sf_isolation_documented_as_opt_in() -> None:
    for rel in ("README.md", "docs/INSTALL.md"):
        assert "opt-in" in _read(rel).lower(), (
            f"{rel} must clarify SF F-15 path isolation is opt-in "
            f"(allowed_directory defaults to null) rather than implying a hard default"
        )


# --- F2/F4/F9: status tables match frontmatter ------------------------------

def test_workflows_skill_status_cells_match_frontmatter() -> None:
    doc = _read("docs/WORKFLOWS.md")
    wip = _wip_skills()
    assert wip, "expected at least one wip skill in frontmatter (sanity)"
    for skill in sorted(wip):
        row = _skill_row(doc, skill)
        if row is None:
            continue  # not listed in a status table
        assert _cells(row)[-1] == "wip", (
            f"WORKFLOWS status cell for wip skill {skill!r} must be 'wip', "
            f"got {_cells(row)[-1]!r}"
        )


def test_readme_phase_table_demotes_wip_phases() -> None:
    doc = _read("README.md")
    for label in ("Production Suite", "Publishing + Specialized"):
        row = _phase_row(doc, label)
        assert row is not None, f"README phase row for {label!r} not found"
        assert _cells(row)[2] != "done", (
            f"README Phase {label!r} is marked done while its skills are wip"
        )


def test_architecture_phase_table_demotes_wip_phases() -> None:
    doc = _read("docs/ARCHITECTURE.md")
    for label in ("Production Suite", "Publishing + Specialized"):
        row = _phase_row(doc, label)
        assert row is not None, f"ARCHITECTURE phase row for {label!r} not found"
        assert "tamamlandı" not in _cells(row)[2], (
            f"ARCHITECTURE Phase {label!r} is marked tamamlandı while its skills are wip"
        )
