"""Independent-review follow-ups to the consent gate (wave 1).

1. A malformed URL must not crash classification into an ALLOW.
2. Shell block keywords (do / then / else / if / while …) must not hide a command.
3. Command substitution $( … ) / backticks is classified too.
4. URL_DELETED sent to the Indexing API from a body FILE or stdin needs consent.
5. wget -T (timeout) / -d (debug) are not uploads.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from scripts.hooks import outward_action_gate as gate

PUBLISH = "https://indexing.googleapis.com/v3/urlNotifications:publish"


def _tier(cmd: str, cwd: str | None = None) -> str | None:
    hit = gate.assess("Bash", {"command": cmd})
    return hit.tier if hit else None


def _main(monkeypatch, cmd: str) -> int:
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "s"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return gate.main()


@pytest.mark.parametrize("cmd", [
    "curl http://[ ; git push --force origin main",
    "curl -d x http://[ ; rm -rf projects/foo/_state",
])
def test_malformed_url_does_not_open_the_gate(monkeypatch, cmd: str) -> None:
    assert _main(monkeypatch, cmd) == 2


@pytest.mark.parametrize("cmd", [
    'for p in projects/*; do rm -rf "$p"; done',
    "if true; then git push --force origin main; fi",
    "while read f; do rm -rf projects/x; done",
    "if false; then :; else git push --force origin main; fi",
    "out=$(git push --force origin main)",
    'echo "$(rm -rf projects/foo)"',
    "echo `git push --force origin main`",
])
def test_block_keywords_and_substitutions_are_seen(cmd: str) -> None:
    assert _tier(cmd) == "onayli", cmd


def test_url_deleted_in_a_body_file_needs_consent(tmp_path: Path) -> None:
    body = tmp_path / "payload.json"
    body.write_text(json.dumps({"url": "https://x.test/a", "type": "URL_DELETED"}))
    assert _tier(f"curl -X POST {PUBLISH} -d @{body}") == "onayli"


def test_url_updated_in_a_body_file_stays_free(tmp_path: Path) -> None:
    body = tmp_path / "payload.json"
    body.write_text(json.dumps({"url": "https://x.test/a", "type": "URL_UPDATED"}))
    assert _tier(f"curl -X POST {PUBLISH} -d @{body}") == "serbest"


def test_unreadable_body_file_to_indexing_needs_consent() -> None:
    assert _tier(f"curl -X POST {PUBLISH} -d @/nonexistent/payload.json") == "onayli"


def test_url_deleted_in_a_heredoc_needs_consent() -> None:
    cmd = (f"curl -X POST {PUBLISH} -d @- <<'EOF'\n"
           '{"url": "https://x.test/a", "type": "URL_DELETED"}\nEOF')
    assert _tier(cmd) == "onayli"


@pytest.mark.parametrize("cmd", ["wget -T 30 https://example.com/page", "wget -d https://example.com/page"])
def test_wget_timeout_and_debug_are_not_uploads(cmd: str) -> None:
    assert _tier(cmd) is None
