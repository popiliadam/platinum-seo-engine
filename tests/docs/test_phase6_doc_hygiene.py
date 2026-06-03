"""tests/docs/test_phase6_doc_hygiene.py — P3-01 + P3-02 doc/repo hygiene locks.

P3-01: three dated SF docs carry earlier SF MCP call shapes. They are kept for
       provenance (label, don't rewrite) but must route the reader to the
       CURRENT SF contract via a top banner.
P3-02: templates/.DS_Store exists locally but is gitignored and never tracked.
       The fix is gitignore + tracked-files-only packaging — NOT deletion.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# Dated SF docs that carry historical call shapes.
_SF_DOCS = (
    "docs/WORKFLOWS.md",
    "docs/superpowers/plans/2026-05-26-sf-mcp-worker-prompts.md",
    "docs/superpowers/specs/2026-05-26-sf-mcp-hybrid-integration-design.md",
)
_CANONICAL_SF_CONTRACT = "commands/pseo-sf-crawl.md"


def _top(rel: str, n: int = 14) -> str:
    return "\n".join((_REPO / rel).read_text(encoding="utf-8").splitlines()[:n])


def test_sf_docs_route_to_canonical_contract() -> None:
    """P3-01: each SF doc's top banner must point to the authoritative SF
    contract (commands/pseo-sf-crawl.md + the sf-crawl-orchestrator SKILL), so
    a reader who lands on the old call shapes is redirected to the live ones."""
    for rel in _SF_DOCS:
        head = _top(rel)
        assert _CANONICAL_SF_CONTRACT in head, (
            f"{rel}: top banner must point to {_CANONICAL_SF_CONTRACT}"
        )
        assert "sf-crawl-orchestrator" in head, (
            f"{rel}: top banner must name the sf-crawl-orchestrator SKILL"
        )


def test_canonical_sf_contract_targets_exist() -> None:
    """The banner pointers must resolve to real files."""
    assert (_REPO / _CANONICAL_SF_CONTRACT).is_file(), _CANONICAL_SF_CONTRACT
    assert (_REPO / "skills/ingestion/sf-crawl-orchestrator/SKILL.md").is_file()


def test_ds_store_is_gitignored_engine_wide() -> None:
    """P3-02: .gitignore must carry an UNANCHORED `.DS_Store` entry so it covers
    every directory (incl. templates/.DS_Store). Combined with git-based plugin
    distribution (tracked files only), macOS cruft can never ship — no rm
    needed."""
    lines = [
        line.strip()
        for line in (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    ]
    assert ".DS_Store" in lines, (
        ".gitignore must contain an unanchored '.DS_Store' entry (engine-wide); "
        "a path-anchored entry would miss templates/.DS_Store"
    )
