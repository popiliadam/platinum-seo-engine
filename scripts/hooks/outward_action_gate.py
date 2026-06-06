#!/usr/bin/env python3
"""outward_action_gate.py — AMO PreToolUse outward-action consent gate (batch 2b).

AMO's smart-autonomy promise is safe ONLY because irreversible / outward actions
are machine-DENIED unless the operator consented (spec G4). Batch 2a built the
consent ledger (`projects/{slug}/_state/consent.jsonl`, append-only + hash-chained)
and the `/pseo-approve` command; THIS is the enforcement half. Before a gated
action runs, the gate classifies it, hashes its concrete target, and DENIES it
(``sys.exit(2)``) unless the session's bound project's ledger holds an INTACT-chain
consent entry FOR THIS SESSION.

PER-SESSION consent (the operator-chosen model): a pending (action, target) is
ALLOWED iff an INTACT-chain entry has ``session_id == THIS session`` AND
``action == this action`` AND ``target_hash == sha256 of this target``. A consent
from a DIFFERENT session (or a tampered chain) does NOT authorize. run_id is NOT
used for matching (audit provenance only), so the gate stays READ-ONLY.

The six gated classes (the 2a `action` enum; dfs_oversized is deferred):
  git_push · fs_delete · net_post · mcp_submit · index_update

Three layers:
  * classify() — PURE, no IO. CONSERVATIVE: only a CLEAR match returns an action;
    a non-gated command returns None and is NEVER blocked (only a positive
    classification can reach a deny). Leading-token bash parse (so ``rm`` is
    gated but ``confirm`` is not), mirroring events_writer._classify_bash_command.
  * evaluate() — gated + matching same-session consent -> allow; gated +
    no/other-session/tampered/unresolvable consent -> DENY (fail-closed).
  * main() — fail-OPEN on the non-gated path (a parser bug must never brick plain
    Bash) but fail-CLOSED on the gated path; mirrors validate_content_write.py.

Deny UX (so a non-coder never guesses): the stderr deny echoes the EXACT
copy-paste approval command with the SAME target string the gate hashed via
consent_ledger.target_hash (writer/gate parity):
    BLOCKED: {action} → {target}  (bu oturumda onay yok)
    İzin vermek için çalıştır:  /pseo-approve sess-{first8 of session_id} {action} "{target}"

Wired as a SECOND PreToolUse block (matcher ``Bash|mcp__gsc__submit_sitemap``);
the existing block is untouched. Hooks compose — a Bash call fires both blocks and
either can deny. READ-ONLY: the gate writes no state.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

# Make ``scripts.*`` importable when run as a bare hook subprocess (mirrors
# validate_content_write.py / denetci.py — do NOT rely on cwd).
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.state.consent_ledger import (  # noqa: E402
    has_session_consent,
    target_hash,
)
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
)

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

_MCP_SUBMIT_TOOL = "mcp__gsc__submit_sitemap"

# Leading bash tokens that delete irreversibly (mirror events_writer._BASH_DELETE_TOKENS).
_DELETE_TOKENS = frozenset({"rm", "rmdir", "unlink", "shred"})
# Leading bash tokens that make an outbound HTTP request.
_HTTP_TOKENS = frozenset({"curl", "wget"})

# A POST to this host is the Google Indexing-API URL_UPDATED surface (index_update);
# any other outbound POST is net_post.
_INDEXING_HOST = "indexing.googleapis.com"

# Flags whose presence means a curl/wget carries an outbound body (-> a POST).
# Case-sensitive: curl's short flags are case-sensitive (-d data, -F form, -X method).
_POST_DATA_FLAGS = frozenset({
    "-d", "--data", "--data-raw", "--data-binary", "--data-ascii",
    "--data-urlencode", "-F", "--form",
    "--post-data", "--post-file",  # wget
})


# ---------------------------------------------------------------------------
# PURE classification (no IO; the heart, fully unit-tested)
# ---------------------------------------------------------------------------

def _tokenize(command: str) -> list[str]:
    """shlex-split (strips quotes) with a str.split fallback on malformed quoting."""
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _first_url(tokens: list[str]) -> str | None:
    """The first http(s):// token, else None (quotes already stripped by shlex)."""
    for tok in tokens:
        if tok.startswith("http://") or tok.startswith("https://"):
            return tok
    return None


def _has_post_flag(tokens: list[str]) -> bool:
    """True iff the tokens carry an outbound POST body marker (curl/wget)."""
    for i, tok in enumerate(tokens):
        if tok in _POST_DATA_FLAGS:
            return True
        if tok.startswith(("--data", "--post-data", "--post-file")):  # --data=… glued
            return True
        if tok.startswith("-d") and not tok.startswith("--") and len(tok) > 2:  # -d<data>
            return True
        if tok in ("-X", "--request") and i + 1 < len(tokens) and tokens[i + 1].upper() == "POST":
            return True
        if tok.startswith("--request=") and tok.split("=", 1)[1].upper() == "POST":
            return True
        if tok.startswith("-X") and len(tok) > 2 and tok[2:].upper() == "POST":  # -XPOST
            return True
    return False


def _operands(tokens: list[str], start: int) -> list[str]:
    """Non-flag tokens from ``start`` onward (the path / remote / refspec operands)."""
    return [tok for tok in tokens[start:] if not tok.startswith("-")]


def _classify_bash(command: str) -> tuple[str, str] | None:
    """Leading-token bash classify -> (action, target) or None (conservative).

    Target derivation is DETERMINISTIC so the deny message echoes exactly what the
    operator's /pseo-approve must hash:
      * fs_delete  -> the non-flag operands joined (the path(s) being deleted).
      * git_push   -> the remote+refspec operands joined, or "origin" if bare.
      * net_post / index_update -> the request URL.
    """
    tokens = _tokenize(command)
    if not tokens:
        return None
    first = tokens[0].rsplit("/", 1)[-1]  # strip any leading path (mirror events_writer)

    if first in _DELETE_TOKENS:
        operands = _operands(tokens, 1)
        return ("fs_delete", " ".join(operands) if operands else command.strip())

    if first == "git" and len(tokens) >= 2 and tokens[1] == "push":
        operands = _operands(tokens, 2)  # --dry-run is a flag -> ignored here
        return ("git_push", " ".join(operands) if operands else "origin")

    if first in _HTTP_TOKENS:
        url = _first_url(tokens)
        host = (urlparse(url).hostname or "").lower() if url else ""
        is_indexing = host == _INDEXING_HOST
        is_indexnow = host.endswith("indexnow.org")
        if _has_post_flag(tokens) or is_indexing or is_indexnow:
            target = url if url else command.strip()
            return ("index_update", target) if is_indexing else ("net_post", target)
        return None  # a plain GET curl/wget is not gated

    return None


def classify(tool_name: str, tool_input: dict) -> tuple[str, str] | None:
    """(tool_name, tool_input) -> (action, target) for a CLEARLY gated action, else None.

    CONSERVATIVE — ambiguity / a non-gated tool returns None so the non-gated path
    never bricks a command. The MCP sitemap-submit tool is ALWAYS gated (it is an
    outward submission to Google); its target is the feedpath (the sitemap being
    submitted), falling back to siteUrl.
    """
    if tool_name == _MCP_SUBMIT_TOOL:
        ti = tool_input if isinstance(tool_input, dict) else {}
        return ("mcp_submit", ti.get("feedpath") or ti.get("siteUrl") or "")
    if tool_name == "Bash":
        if not isinstance(tool_input, dict):
            return None
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        return _classify_bash(command)
    return None


# ---------------------------------------------------------------------------
# Decision (IO via injected resolvers; fail-OPEN non-gated, fail-CLOSED gated)
# ---------------------------------------------------------------------------

def evaluate(
    payload: dict,
    *,
    has_consent_fn=has_session_consent,
    session_id_fn=current_session_id,
    workspace_fn=resolve_workspace_root,
    slug_fn=resolve_session_project,
) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` — 0 allows the tool, 2 denies it.

    Non-gated (classify None) -> (0, []) BEFORE any resolution, so a plain command
    is never bricked. Gated -> allowed iff THIS session's bound project consented
    to (action, target); otherwise DENY (fail-closed) with the copy-paste fix. An
    unresolvable session/workspace/slug cannot prove consent -> deny.
    """
    if not isinstance(payload, dict):
        return (0, [])
    gated = classify(payload.get("tool_name") or "", payload.get("tool_input"))
    if gated is None:
        return (0, [])  # not gated -> ALLOW
    action, target = gated

    session_id = session_id_fn(payload)
    workspace = workspace_fn()
    slug = None
    if workspace is not None and session_id:
        slug = slug_fn(workspace, session_id=session_id, strict=False)
    th = target_hash(target)
    allowed = bool(
        workspace is not None
        and slug is not None
        and session_id
        and has_consent_fn(
            workspace, slug, session_id=session_id, action=action, target_hash=th
        )
    )
    if allowed:
        return (0, [])  # consented THIS session -> ALLOW

    run_label = "sess-" + (session_id[:8] if session_id else "unknown")
    return (2, [
        f"BLOCKED: {action} → {target}  (bu oturumda onay yok)",
        f'İzin vermek için çalıştır:  /pseo-approve {run_label} {action} "{target}"',
    ])


# ---------------------------------------------------------------------------
# main — never bricks NON-gated work; preserves the DENY code on emit failure
# ---------------------------------------------------------------------------

def _emit(message: str) -> None:
    """Best-effort stderr write that NEVER raises (so it can't flip a deny to allow)."""
    line = f"[gate] {message}\n"
    try:
        sys.stderr.write(line)
    except Exception:  # pragma: no cover - exotic stderr encoding
        try:
            sys.stderr.buffer.write(line.encode("utf-8", "replace"))
        except Exception:
            pass


def main() -> int:
    """Read the PreToolUse stdin payload and emit the gate decision.

    Fail-OPEN on an internal error (unreadable stdin / a classify crash) because
    reaching that branch means NO gated action was confirmed — a gate bug must not
    brick non-gated work (mirrors validate_content_write.py). The gated decision is
    computed first and the deny code is returned even if message emission fails, so
    the gated path stays fail-CLOSED.
    """
    try:
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
        code, messages = evaluate(payload)
    except Exception as exc:  # no confirmed gated action -> allow + a loud warning
        _emit(f"WARNING internal error, allowing (fail-open): {exc!r}")
        return 0
    for message in messages:
        _emit(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
