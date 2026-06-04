"""codex-audit finding 5d: events_writer._events_path only guarded against an
empty project_id, then blindly mkdir'd projects/<id>/_state for ANY string —
so a bad active slug (typo, leading digit) created a ghost project tree, and an
id containing '..' or '/' escaped the projects/ subtree (path traversal).
Validate the id against the canonical slug pattern BEFORE creating anything.
"""
import pytest

from scripts.state import events_writer as ew


@pytest.mark.parametrize("bad", ["../evil", "a/b", "9foo", "Foo", "x_y", ""])
def test_events_path_rejects_invalid_project_id(tmp_path, bad):
    with pytest.raises(ew.EventPathError):
        ew._events_path(bad, tmp_path)
    # and it must NOT have created any directory for the bad id
    assert not (tmp_path / "projects" / bad).exists()


def test_events_path_accepts_valid_slug(tmp_path):
    p = ew._events_path("demo-construction-insaat-tr", tmp_path)
    assert p.name == "events.jsonl"
    assert (tmp_path / "projects" / "demo-construction-insaat-tr" / "_state").is_dir()
