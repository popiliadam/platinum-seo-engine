"""tests/state/test_events_schema_compliance.py — events.jsonl strict schema
compliance (ADR-031).

Future invariant: every row in `_state/events.jsonl` MUST validate against
`schemas/events.schema.json`. Legacy non-conforming rows live in
`events.jsonl.legacy` (READ-ONLY archive) and are skipped here.

The test is parameterized by the workspace root from PSEO_WORKSPACE_ROOT.
When the workspace is unbound (engine-only CI), the test SKIPs cleanly so
the engine repo's pytest baseline isn't dependent on a workspace fixture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "events.schema.json"


def _workspace_root() -> Path | None:
    raw = os.environ.get("PSEO_WORKSPACE_ROOT")
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.exists() else None


def _events_files() -> list[Path]:
    """Find all _state/events.jsonl files inside the bound workspace."""
    root = _workspace_root()
    if root is None:
        return []
    projects = root / "projects"
    if not projects.exists():
        return []
    files = []
    for project_dir in projects.iterdir():
        candidate = project_dir / "_state" / "events.jsonl"
        if candidate.exists():
            files.append(candidate)
    return files


@pytest.fixture(scope="module")
def schema() -> Draft7Validator:
    return Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("events_path", _events_files(), ids=lambda p: str(p.relative_to(p.parents[3])) if p else "<none>")
def test_events_jsonl_strict(events_path: Path, schema: Draft7Validator) -> None:
    """Every row in events.jsonl must validate against events.schema.json
    (ADR-031). events.jsonl.legacy is intentionally excluded — that's the
    archive for pre-migration rows."""
    failures = []
    for lineno, raw in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"L{lineno}: json-decode {exc.msg}")
            continue
        errors = list(schema.iter_errors(event))
        if errors:
            joined = "; ".join(e.message[:120] for e in errors[:2])
            failures.append(f"L{lineno}: {joined}")
    assert not failures, (
        f"{events_path}: schema violations after ADR-031 migration:\n  "
        + "\n  ".join(failures[:10])
        + (f"\n  ...({len(failures) - 10} more)" if len(failures) > 10 else "")
    )


def test_legacy_archive_is_optional(schema: Draft7Validator) -> None:
    """events.jsonl.legacy may exist (post-ADR-031 migration); when it
    does, its rows are NOT validated — they are archived for audit-trail
    fidelity. This test simply confirms presence/absence is acceptable."""
    root = _workspace_root()
    if root is None:
        pytest.skip("workspace not bound")
    archives = list(root.rglob("events.jsonl.legacy"))
    # No assertion on contents — archives are deliberately schema-divergent.
    # Just make sure we can read each file without error.
    for arc in archives:
        text = arc.read_text(encoding="utf-8")
        assert isinstance(text, str)


def test_skip_when_workspace_unbound() -> None:
    """Sentinel test: when PSEO_WORKSPACE_ROOT is unset, the parametrized
    suite contributes zero cases (graceful no-op for engine-only CI)."""
    if _workspace_root() is None:
        files = _events_files()
        assert files == [], f"events_files() should be empty when unbound, got {files}"
