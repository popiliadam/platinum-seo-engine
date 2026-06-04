"""tests/hooks/test_validate_content_write.py — PreToolUse content gate.

The hook runs ``content_validator`` at the Write boundary: a RED verdict on a
generated blog HTML write exits 2 (Claude Code blocks the tool call); anything
else exits 0. Path filtering, the Write/Edit split, and fail-open behaviour are
the contract.

Design ref: docs/superpowers/specs/2026-06-04-content-validator-design.md §7.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hooks.validate_content_write import evaluate, is_content_html_path

_REPO = Path(__file__).resolve().parents[2]
_HOOK = _REPO / "scripts" / "hooks" / "validate_content_write.py"

_CONTENT_PATH = "projects/eykom/outputs/blog/klima-montaji/article.html"


def _payload(tool: str, file_path: str, **content: str) -> dict:
    tool_input = {"file_path": file_path}
    tool_input.update(content)
    return {"tool_name": tool, "tool_input": tool_input}


# --------------------------------------------------------------------------
# Path classification — only the live published HTML surface is validated.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        ("outputs/blog/x/article.html", True),
        ("/a/b/projects/foo/outputs/content/drafts/y.html", True),
        ("projects/foo/outputs/blog/z/article.html", True),
        ("scripts/foo.py", False),
        ("outputs/reports/2026-06-monthly.html", False),
        ("templates/content/new-blog.template.html", False),
        ("projects/foo/outputs/blog/z/upload-instructions.md", False),
    ],
)
def test_is_content_html_path(path: str, expected: bool) -> None:
    assert is_content_html_path(path) is expected


# --------------------------------------------------------------------------
# evaluate() — (exit_code, messages); 2 = block, 0 = allow.
# --------------------------------------------------------------------------

def test_write_with_disclosure_blocks() -> None:
    code, msgs = evaluate(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>written by AI</p></article>',
        )
    )
    assert code == 2
    assert any("AI-disclosure" in m for m in msgs)


def test_write_clean_content_allows() -> None:
    code, _ = evaluate(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>Temiz içerik.</p></article>',
        )
    )
    assert code == 0


def test_write_to_non_content_path_skips() -> None:
    code, msgs = evaluate(
        _payload("Write", "scripts/foo.py", content="written by AI")
    )
    assert code == 0
    assert msgs == []


def test_edit_injecting_disclosure_blocks() -> None:
    code, _ = evaluate(
        _payload("Edit", _CONTENT_PATH, new_string="<p>This was written by AI.</p>")
    )
    assert code == 2


def test_edit_with_non_pse_class_does_not_block() -> None:
    """R-61 needs the whole document; on an Edit fragment it must NOT block —
    only the fragment-safe RED rules apply (C1)."""
    code, _ = evaluate(
        _payload("Edit", _CONTENT_PATH, new_string='<div class="highlight">x</div>')
    )
    assert code == 0


def test_bash_tool_skips() -> None:
    code, msgs = evaluate(
        {"tool_name": "Bash", "tool_input": {"command": "echo written by AI"}}
    )
    assert code == 0
    assert msgs == []


def test_malformed_payload_fails_open() -> None:
    code, _ = evaluate("not a dict")  # type: ignore[arg-type]
    assert code == 0


# --------------------------------------------------------------------------
# Subprocess smoke — proves the stdin → exit-code wiring main() relies on.
# --------------------------------------------------------------------------

def test_subprocess_stdin_blocks_on_disclosure() -> None:
    payload = json.dumps(
        _payload(
            "Write",
            _CONTENT_PATH,
            content='<article class="pse-blog-post"><p>written by AI</p></article>',
        )
    )
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=payload,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2
