"""tests/docs/test_fix_n_hygiene.py — unified-FIX-N hygiene pack pins (2026-06-10).

Pins the Wave-6 FIX-N hygiene contract so none of it silently regresses:

  * `.gitignore` blankets the `.claude/` runtime cache (worktrees, plugin
    state, settings.local.json) — conftest.py already excludes it from pytest
    collection; git must stop seeing it too.
  * `.env.example` documents WHERE each credential comes from — the
    HIGGSFIELD_API_KEY entry carries its source URL like the other entries.
  * The 2026-06-03 Codex cross-repo audit handoff lives under `docs/audits/`
    (it shipped as a root-level `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`); the one
    live reference (RELEASE_NOTES_v1.9.5.md) points at the new home while
    keeping the historical filename as narrative.
  * `docs/RELEASE_NOTES_gap-note.md` explains the v1.2.0 / v1.9.1 / v1.9.2
    release-notes numbering gaps from git evidence (none of the three was
    ever tagged; per-version stubs are only owed to tagged releases).
  * `docs/superpowers/specs/2026-06-10-log-file-analysis-feasibility.md`
    records the GAP-A4 spec-only deferral with explicit re-open triggers.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

_HANDOFF_NEW = (
    _REPO / "docs" / "audits" / "2026-06-03_codex_cross_repo_audit_handoff.md"
)
_GAP_NOTE = _REPO / "docs" / "RELEASE_NOTES_gap-note.md"
_DEFERRAL_SPEC = (
    _REPO
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-06-10-log-file-analysis-feasibility.md"
)


def test_gitignore_blankets_claude_runtime_dir() -> None:
    """`.claude/` holds operator-local runtime artefacts (worktrees, plugin
    cache, settings.local.json). conftest.py already keeps pytest out of it;
    git must ignore the whole directory, not just settings.local.json."""
    lines = [
        line.strip()
        for line in (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    ]
    assert ".claude/" in lines, (
        ".gitignore must carry a blanket '.claude/' entry (runtime cache; "
        "the tracked plugin manifest lives in .claude-plugin/, which this "
        "entry does not touch)"
    )


def test_env_example_higgsfield_key_documents_source_url() -> None:
    """Every credential entry in .env.example names where to obtain it; the
    HIGGSFIELD_API_KEY entry must carry its source URL like the others."""
    text = (_REPO / ".env.example").read_text(encoding="utf-8")
    assert "HIGGSFIELD_API_KEY" in text
    assert "https://app.higgsfield.ai" in text, (
        ".env.example HIGGSFIELD_API_KEY entry must keep its source-URL "
        "comment line (match the GOOGLE_APPLICATION_CREDENTIALS / DATAFORSEO "
        "entry style)"
    )


def test_audit_handoff_moved_under_docs_audits() -> None:
    """The Codex 2026-06-03 cross-repo audit handoff is an audit artefact —
    it belongs in docs/audits/ with the other dated audit reports, not at the
    repo root."""
    assert not (_REPO / "AUDIT_FINDINGS_FOR_CLAUDE_CODE.md").exists(), (
        "root AUDIT_FINDINGS_FOR_CLAUDE_CODE.md must be moved (git mv) to "
        "docs/audits/2026-06-03_codex_cross_repo_audit_handoff.md"
    )
    assert _HANDOFF_NEW.is_file(), f"{_HANDOFF_NEW} missing"
    head = _HANDOFF_NEW.read_text(encoding="utf-8").splitlines()[:5]
    assert any("Audit Handoff" in line for line in head), (
        "moved file must still be the 2026-06-03 audit handoff document"
    )


def test_release_notes_v195_cites_moved_handoff_path() -> None:
    """RELEASE_NOTES_v1.9.5.md is the one live reference to the handoff file;
    after the move it must point at the new path (the historical filename may
    stay as narrative — same principle as the template-refs historical
    exemptions)."""
    text = (_REPO / "docs" / "RELEASE_NOTES_v1.9.5.md").read_text(encoding="utf-8")
    assert "docs/audits/2026-06-03_codex_cross_repo_audit_handoff.md" in text, (
        "RELEASE_NOTES_v1.9.5.md must cite the handoff's post-move path"
    )


def test_release_notes_gap_note_explains_untagged_numbers() -> None:
    """v1.2.0 / v1.9.1 / v1.9.2 have no docs/RELEASE_NOTES_* file. None of the
    three was ever git-tagged, so per-version stubs are not owed — ONE
    consolidated gap-note records the evidence instead (never invent
    content)."""
    text = _GAP_NOTE.read_text(encoding="utf-8")
    for version in ("1.2.0", "1.9.1", "1.9.2"):
        assert version in text, f"gap-note must cover v{version}"
    # The two real-but-untagged releases are documented inside the v1.9.3
    # consolidating notes — the gap-note must route the reader there with the
    # actual commit evidence.
    assert "RELEASE_NOTES_v1.9.3.md" in text
    assert "c6c0268" in text and "65c5c52" in text
    # The filename must stay OUTSIDE the RELEASE_NOTES_v*.md glob —
    # tests/ci/test_version_sync.py derives the latest release version from
    # that glob and a v-prefixed gap-note would corrupt the comparison.
    assert not _GAP_NOTE.match("RELEASE_NOTES_v*.md")


def test_log_file_analysis_deferral_spec_exists_with_triggers() -> None:
    """GAP-A4 verdict is a spec-only deferral: the doc must carry the verdict,
    the three re-open triggers, and the zero-credit approximation path."""
    text = _DEFERRAL_SPEC.read_text(encoding="utf-8")
    for trigger in ("T1", "T2", "T3"):
        assert trigger in text, f"build trigger {trigger} missing"
    assert "lastCrawlTime" in text, (
        "the gsc__index_inspect lastCrawlTime approximation path must be "
        "recorded"
    )
    assert "Crawl Stats" in text
    assert "defer" in text.lower(), "the do-NOT-build deferral verdict must be explicit"
