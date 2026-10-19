"""V-13: a JSONL line holding U+2028 / U+2029 / U+0085 must stay ONE line.

json.dumps(ensure_ascii=False) does not escape these characters, and they occur
in scraped titles. str.splitlines() splits on them, so a reader saw two broken
halves; the legacy-events migration then archived both as invalid and dropped
the event from the main log. Readers split on "\\n" only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.state import events_writer, migrate_legacy_events

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("sep", [" ", " ", "\u0085"])
def test_migration_keeps_an_event_with_a_unicode_line_separator(tmp_path: Path, sep: str) -> None:
    (tmp_path / "projects" / "demo" / "_state").mkdir(parents=True)
    events_writer.append_audit(
        project_id="demo", audit_action="modified",
        audit_target=f"page title one{sep}two", actor="test", workspace_root=tmp_path,
    )
    path = tmp_path / "projects" / "demo" / "_state" / "events.jsonl"
    passed, failed = migrate_legacy_events._classify_lines(
        path, migrate_legacy_events._load_schema()
    )
    assert failed == []
    assert [json.loads(line)["audit_target"] for line in passed] == [f"page title one{sep}two"]


def test_no_jsonl_reader_uses_splitlines() -> None:
    """Guard: the readers fixed here must not drift back."""
    offenders = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ".jsonl" not in text:
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            if re.search(r"read_text\([^)]*\)\.splitlines\(\)|\b(text|raw)\.splitlines\(\)", line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert offenders == []
