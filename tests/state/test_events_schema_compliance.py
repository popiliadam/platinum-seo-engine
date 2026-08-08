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
import warnings
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "events.schema.json"


def _validator() -> Draft7Validator:
    """The validator this gate judges rows with — ONE definition, so the
    strictness of the gate and of the fixture can never drift apart.

    Routed through ``build_validator`` (NOT a bare ``Draft7Validator``) so this
    gate is exactly as strict as ``events_writer``: ``format: date-time`` is
    ENFORCED as the UTC ``…Z`` form rather than treated as a bare annotation.
    """
    from scripts.validation.validate_schema import build_validator
    return build_validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


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
    return _validator()


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


def test_compliance_validator_is_as_strict_as_the_writer() -> None:
    """The gate must reject what events_writer would have refused to write.

    A plain ``Draft7Validator`` treats ``format`` as an annotation, so a
    ``+00:00`` timestamp validates — while events_writer, which builds its
    validator through ``validate_schema.build_validator``, enforces the UTC
    ``…Z`` form (rules/time-discipline.md §8.10) and raises. A gate weaker than
    the writer it guards cannot detect a row the writer would never have
    produced: 22 of the 93 rows in the 2026-07 drift carried exactly this shape.
    """
    naive = {
        "schema_version": "1.0",
        "event_kind": "audit",
        "event_id": "drift-probe-0001",
        "timestamp": "2026-07-09T10:50:57.551803+00:00",   # NOT the '…Z' form
        "project_id": "demo-dental",
        "audit_action": "modified",
        "audit_target": "master.xlsx",
        "actor": "probe",
    }
    validator = _validator()
    assert list(validator.iter_errors(naive)), (
        "the compliance validator accepted a non-'Z' timestamp — it is weaker "
        "than events_writer, so it cannot catch a row the writer would reject"
    )
    # Sanity: the same event with the canonical suffix IS accepted, so the
    # assertion above is about the timestamp FORM and nothing else.
    assert not list(validator.iter_errors({**naive, "timestamp": "2026-07-09T10:50:57.551803Z"}))


def test_unbound_workspace_is_reported_as_zero_coverage() -> None:
    """When the workspace is unbound this suite checks NOTHING — say so.

    The previous version of this test asserted the file list was empty and
    passed, which recorded 'no coverage' as a green result. That is how 93
    drifted rows accumulated for a month while the suite reported success.
    """
    if _workspace_root() is not None:
        return
    files = _events_files()
    assert files == [], f"events_files() should be empty when unbound, got {files}"
    warnings.warn(
        "events.jsonl schema compliance NOT CHECKED — PSEO_WORKSPACE_ROOT is "
        "unbound, so this suite contributed zero cases. This is a coverage gap, "
        "not a pass. Bind the workspace to actually measure.",
        UserWarning,
        stacklevel=2,
    )
