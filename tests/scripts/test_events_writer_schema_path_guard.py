"""events_writer: the ``schema_path`` override is test-only — and now enforced.

``append_event`` (and every ``append_*`` wrapper) takes ``schema_path`` so a
test can validate against a fixture schema. The docstring said "test-only" but
nothing enforced it: on 2026-08-20 an agent session passed a loosened COPY of
events.schema.json through this parameter and 11 off-schema rows reached a live
ledger with the writer's blessing. Outside a pytest run, any schema other than
the repo's own ``schemas/events.schema.json`` must be refused BEFORE the ledger
is touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.state import events_writer as ew

_REPO = Path(__file__).resolve().parents[2]
_SLUG = "demo-acme"


@pytest.fixture
def loose_schema(tmp_path: Path) -> Path:
    """A loosened events schema — accepts any object, like the 08-20 copy."""
    p = tmp_path / "schemas" / "events.demo.schema.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"$schema": "http://json-schema.org/draft-07/schema#",
                             "type": "object"}), encoding="utf-8")
    return p


def _ledger(ws: Path) -> Path:
    return ws / "projects" / _SLUG / "_state" / "events.jsonl"


def _rows(ws: Path) -> list[str]:
    p = _ledger(ws)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def test_a_foreign_schema_outside_pytest_is_refused(tmp_path, loose_schema, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(ew.EventValidationError, match="schema_path"):
        ew.append_work(project_id=_SLUG, event_type="tech_fix", task_id="T-0001",
                       workspace_root=tmp_path, schema_path=loose_schema,
                       off_schema_field="x")
    assert _rows(tmp_path) == []


def test_a_foreign_schema_is_refused_on_the_run_id_allocating_path(tmp_path, loose_schema, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(ew.EventValidationError, match="schema_path"):
        ew.append_provenance(project_id=_SLUG, source={"kind": "tool_computed"},
                             operation="validate", workspace_root=tmp_path,
                             schema_path=loose_schema)
    assert _rows(tmp_path) == []


def test_a_foreign_schema_is_refused_in_a_real_agent_shaped_process(tmp_path, loose_schema):
    """The 08-20 shape: a plain `python3 -c` (no pytest) passing the copy."""
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env["PYTHONPATH"] = str(_REPO)
    code = (
        "from pathlib import Path\n"
        "from scripts.state import events_writer as ew\n"
        f"ew.append_work(project_id={_SLUG!r}, event_type='tech_fix', task_id='T-0001',\n"
        f"    workspace_root=Path({str(tmp_path)!r}), schema_path=Path({str(loose_schema)!r}),\n"
        "    off_schema_field='x')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(_REPO),
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "schema_path" in proc.stderr
    assert _rows(tmp_path) == []


def test_the_repo_schema_passed_explicitly_is_allowed_outside_pytest(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    ew.append_provenance(project_id=_SLUG, run_id=1, source={"kind": "tool_computed"},
                         operation="validate", workspace_root=tmp_path,
                         schema_path=_REPO / "schemas" / "events.schema.json")
    assert len(_rows(tmp_path)) == 1


def test_the_override_still_works_for_tests(tmp_path, loose_schema):
    """Under pytest the documented test-only override keeps working."""
    assert os.environ.get("PYTEST_CURRENT_TEST")
    ew.append_work(project_id=_SLUG, event_type="tech_fix", task_id="T-0001",
                   workspace_root=tmp_path, schema_path=loose_schema,
                   off_schema_field="x")
    assert len(_rows(tmp_path)) == 1
