"""codex-audit finding 5 (a+b): /pseo-active must not (a) write the active
marker when the target project's config is missing, and (b) accept a slug that
starts with a digit — the schema's project_id pattern requires a letter start
(^[a-z][a-z0-9-]*$), so the command's looser regex could set a marker the schema
would reject. These static assertions lock both behaviours in the command body.
"""
from pathlib import Path

CMD = (Path(__file__).resolve().parents[2] / "commands" / "pseo-active.md").read_text("utf-8")


def test_slug_regex_requires_letter_start():
    # must match the schema's ^[a-z][a-z0-9-]*$ — no leading-digit slugs
    assert "[a-z0-9][a-z0-9-]*" not in CMD, "command still allows a leading-digit slug"
    assert "[a-z][a-z0-9-]*" in CMD, "command must use the letter-start slug regex"


def test_missing_config_aborts_without_writing_marker():
    # the missing-config branch must abort, not warn-and-continue
    assert "yine de marker" not in CMD, "missing-config branch still writes the marker anyway"
    assert "exit 1" in CMD, "missing-config branch must abort with exit 1"
