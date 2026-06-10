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
    gated but ``confirm`` is not), mirroring events_writer._classify_bash_command;
    leading command WRAPPERS (sudo/command/env/time/nohup/…) are unwrapped first so
    a wrapped action (``sudo rm``, ``sudo git push``) is still gated (#10), while a
    loopback request (127.0.0.0/8 · localhost · ::1) is carved out as a local-only,
    non-outward action (#12).
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
import re
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

# Interpreters that can be coaxed into an outbound HTTP WRITE via a one-liner
# (#11). _HTTP_TOKENS only caught curl/wget; a python/node/ruby/perl POST sailed
# past. These are gated ONLY when their source ALSO carries a net-write marker
# (below) — a plain interpreter call stays non-gated (byte-identical to today).
_INTERPRETER_TOKENS = frozenset({
    "python", "python2", "python3", "pythonw",
    "node", "nodejs", "ruby", "perl", "php", "deno", "bun",
})

# An HTTP-capable client referenced in interpreter source (matched case-INSENSITIVELY).
_NET_LIB_MARKERS = (
    # python
    "urlopen", "urllib.request", "urllib2", "urllib3", "requests.", "httpx.",
    "http.client", "httplib", "httpconnection", "httpsconnection",
    # node
    "fetch(", "http.request", "https.request", "axios", "xmlhttprequest",
    "require('http", 'require("http',
    # ruby / perl
    "net::http", "net/http", "lwp", "http::tiny",
)

# A write/POST indicator (matched case-INSENSITIVELY). The lowercase method-call
# forms (.post( / ->post( / ::post) are specific to HTTP client libraries.
_NET_WRITE_MARKERS_CI = (
    "data=", "json=", "body=", "body:", "method=", "method:",
    ".post(", "->post(", ".put(", "->put(", ".patch(", ".delete(",
    ".send(", "::post", "::put",
)

# Uppercase HTTP verbs matched CASE-SENSITIVELY so a word like "compost" /
# "POSTGRES" can never trip the gate on its own (always AND-ed with a net-lib marker).
_NET_WRITE_VERBS_CS = ("POST", "PUT", "PATCH", "DELETE")

# An http(s) URL anywhere in the text (incl. inside a quoted interpreter one-liner,
# where the URL is NOT a standalone shlex token).
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s'\"`)\\]+")

# Leading command WRAPPERS that prefix a real command (`sudo rm …`, `env FOO=bar
# git push`, `timeout 5 curl …`). They are NOT gated themselves, but they MUST be
# unwrapped so the gated command behind them is still classified — otherwise the
# wrapper token sits at tokens[0] and smuggles the action past the gate (#10).
_WRAPPER_TOKENS = frozenset({
    "sudo", "doas", "command", "builtin", "exec", "env", "time",
    "nohup", "setsid", "stdbuf", "nice", "ionice", "timeout", "xargs",
})

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

# git GLOBAL options that CONSUME the next token (so a `push` subcommand can sit
# behind them: `git -C <path> push`). Walking past these to git's real subcommand
# is what lets the gate see a `git push` that is not at tokens[1].
_GIT_GLOBAL_ARG_FLAGS = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
})

# Shell separators that delimit independent commands; classify EACH segment so a
# gated action that is NOT the leading token (`cd x && git push`) is still caught.
# `||` MUST precede `|` in the alternation so the two-char operator wins.
_SEGMENT_SEP_RE = re.compile(r"&&|\|\||;|\n|\|")


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


def _first_url_in_text(text: str) -> str | None:
    """First http(s) URL anywhere in ``text`` — including inside a quoted
    interpreter one-liner, where the URL is not a standalone shlex token."""
    m = _URL_IN_TEXT_RE.search(text)
    return m.group(0) if m else None


def _is_interpreter(bare: str) -> bool:
    """True iff ``bare`` (a path-stripped leading token) names a script interpreter
    (incl. version-suffixed pythons: ``python3``, ``python3.11``)."""
    if bare in _INTERPRETER_TOKENS:
        return True
    return bool(re.fullmatch(r"python[0-9](\.[0-9]+)*", bare))


def _interpreter_net_write(text: str) -> bool:
    """True iff ``text`` (a whole bash command) contains an interpreter one-liner
    HTTP WRITE — i.e. BOTH a net-client marker AND a write/POST indicator (#11).

    Scans the WHOLE command, not a single shell segment: a python one-liner's
    internal ``;``/``&&`` would otherwise fragment the markers across
    :func:`_split_segments` boundaries (``import requests; requests.post(...)``)
    and hide the write. Requiring BOTH markers keeps a plain interpreter call
    (``python3 -c 'print(1)'``) and a GET (``requests.get(url)``) non-gated, while
    over-gating (a ``requests.get(url, data=…)``) is acceptable per the #11 ruling.
    """
    low = text.lower()
    if not any(m in low for m in _NET_LIB_MARKERS):
        return False
    if any(m in low for m in _NET_WRITE_MARKERS_CI):
        return True
    return any(verb in text for verb in _NET_WRITE_VERBS_CS)


def _is_loopback_host(host: str) -> bool:
    """True iff ``host`` addresses THIS machine — a loopback request never leaves
    it, so it is not an OUTWARD action (#12): ``localhost`` / ``*.localhost``
    (RFC 6761), the IPv4 ``127.0.0.0/8`` block, and the IPv6 ``::1``.

    CONSERVATIVE: anything we cannot PROVE is loopback returns False and stays
    gated, so a public POST is never un-gated. The Indexing/IndexNow hosts are
    never loopback, so this can never carve them out either.
    """
    if not host:
        return False
    h = host.strip().lower().strip("[]")  # urlparse strips [] already; be defensive
    if h == "localhost" or h.endswith(".localhost"):
        return True
    if h in ("::1", "0:0:0:0:0:0:0:1"):
        return True
    parts = h.split(".")
    if len(parts) == 4 and parts[0] == "127" and all(
        p.isdigit() and 0 <= int(p) <= 255 for p in parts
    ):
        return True
    return False


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


def _split_segments(command: str) -> list[str]:
    """Split a bash command into segments on shell separators (&& || ; | newline).

    Splits the RAW string then tokenises each segment (NOT shlex over the whole
    line) — same conservative spirit as the leading-token parse: a quoted / heredoc
    separator may over-split, but over-splitting only ever yields MORE segments to
    classify, never fewer, so a gated action is never hidden by it.
    """
    return [seg.strip() for seg in _SEGMENT_SEP_RE.split(command) if seg.strip()]


def _git_push_target(tokens: list[str]) -> str | None:
    """The git-push target (operands joined, or "origin") if these tokens are a
    `git push` — even behind git global flags (`-C <path>`, `-c <kv>`,
    `--git-dir <p>`, …) — else None.

    Walks past git's global options (those that consume the next token are skipped
    in PAIRS) to the first non-flag token: it must be `push`, else this is some
    other git subcommand (`status`, `log`, …) and is NOT gated. tokens[0] is the
    `git` token and is skipped.
    """
    i = 1  # tokens[0] == "git"
    while i < len(tokens):
        tok = tokens[i]
        if tok in _GIT_GLOBAL_ARG_FLAGS:  # global flag that consumes the next token
            i += 2
            continue
        if tok.startswith("-"):           # other global flag (no arg, or --flag=val)
            i += 1
            continue
        if tok != "push":                 # first non-flag token is the subcommand
            return None
        operands = [x for x in tokens[i + 1:] if not x.startswith("-")]
        return " ".join(operands) if operands else "origin"
    return None


def _first_command_anchor(region: list[str]) -> int:
    """Index in ``region`` of the wrapped command after a leading wrapper: the FIRST
    gated-command or wrapper token, else 0 (the region start).

    Scanning for the gated token — rather than precisely modelling every wrapper's
    option grammar — is what keeps the gate CONSERVATIVE across wrappers with
    arg-taking flags or positional args: ``sudo -u u rm x``, ``timeout 5 git push``,
    ``nice -n 10 rm x`` all anchor on the real command. A wrong anchor can only ever
    OVER-gate (acceptable); it can never hide a gated action (under-deny — forbidden).
    """
    for idx, tok in enumerate(region):
        bare = tok.rsplit("/", 1)[-1]
        if (bare in _DELETE_TOKENS or bare == "git" or bare in _HTTP_TOKENS
                or bare in _WRAPPER_TOKENS or _is_interpreter(bare)):
            return idx
    return 0


def _unwrap_wrappers(tokens: list[str]) -> list[str]:
    """Strip leading command-WRAPPER prefixes so ``sudo rm -rf x`` classifies exactly
    like ``rm -rf x`` (#10); returns the wrapped command's tokens.

    A plain command (tokens[0] is not a wrapper) is returned UNCHANGED, so every
    non-wrapped classification stays byte-identical. Nested wrappers (``sudo nohup
    rm``) are peeled iteratively; a small guard bounds pathological nesting.
    Unwrapping only ever EXPOSES a gated command — it never hides one.
    """
    i = 0
    guard = 0
    while i < len(tokens) and guard < 16:
        if tokens[i].rsplit("/", 1)[-1] not in _WRAPPER_TOKENS:
            break
        region = tokens[i + 1:]
        if not region:
            break  # a bare wrapper with nothing after it -> nothing to unwrap
        i = (i + 1) + _first_command_anchor(region)
        guard += 1
    return tokens[i:]


def _classify_segment(segment: str) -> tuple[str, str] | None:
    """Leading-token classify of ONE shell segment -> (action, target) or None.

    Target derivation is DETERMINISTIC so the deny message echoes exactly what the
    operator's /pseo-approve must hash:
      * fs_delete  -> the non-flag operands joined (the path(s) being deleted).
      * git_push   -> the remote+refspec operands joined, or "origin" if bare
        (recognised even behind git global flags, e.g. `git -C <path> push`).
      * net_post / index_update -> the request URL.
    """
    tokens = _unwrap_wrappers(_tokenize(segment))  # peel sudo/env/... wrappers (#10)
    if not tokens:
        return None
    first = tokens[0].rsplit("/", 1)[-1]  # strip any leading path (mirror events_writer)

    if first in _DELETE_TOKENS:
        operands = _operands(tokens, 1)
        return ("fs_delete", " ".join(operands) if operands else segment.strip())

    if first == "git":  # gated iff it is `git push` (even behind global flags)
        tgt = _git_push_target(tokens)
        return ("git_push", tgt) if tgt is not None else None

    if first in _HTTP_TOKENS:
        url = _first_url(tokens)
        host = (urlparse(url).hostname or "").lower() if url else ""
        is_indexing = host == _INDEXING_HOST
        is_indexnow = host.endswith("indexnow.org")
        # Loopback carve-out (#12): a request to THIS machine never leaves it, so a
        # local POST (e.g. the /pseo-status SF-MCP health probe to 127.0.0.1:11435)
        # is NOT an outward action. Guarded by `not is_indexing/indexnow` so the
        # carve-out can never un-gate the public Indexing/IndexNow surfaces (whose
        # hosts are never loopback anyway).
        if _is_loopback_host(host) and not is_indexing and not is_indexnow:
            return None
        if _has_post_flag(tokens) or is_indexing or is_indexnow:
            target = url if url else segment.strip()
            return ("index_update", target) if is_indexing else ("net_post", target)
        return None  # a plain GET curl/wget is not gated

    return None


def _classify_interpreter_net_write(command: str) -> tuple[str, str] | None:
    """(#11) Gate an interpreter one-liner HTTP WRITE — checked at the WHOLE-command
    level so a python ``import x; x.post(…)`` is not hidden by the ``;`` segment split.

    Two conditions, both required (CONSERVATIVE): an interpreter must LEAD at least
    one shell segment (so an interpreter NAME used as a mere argument, or echoed
    text, never trips the gate), AND the whole command must carry an HTTP-client
    marker AND a write/POST indicator. Target = the first URL found in the command
    (often inside the quoted code), or the whole command. A loopback target is
    carved out (#12 applies EQUALLY per the D-C ruling); otherwise routed to
    ``index_update`` when the URL is the Google Indexing host, else ``net_post``.
    """
    leads_interpreter = any(
        (toks := _unwrap_wrappers(_tokenize(seg)))
        and _is_interpreter(toks[0].rsplit("/", 1)[-1])
        for seg in _split_segments(command)
    )
    if not leads_interpreter or not _interpreter_net_write(command):
        return None
    url = _first_url_in_text(command)
    host = (urlparse(url).hostname or "").lower() if url else ""
    is_indexing = host == _INDEXING_HOST
    is_indexnow = host.endswith("indexnow.org")
    # Loopback carve-out (#12) applies EQUALLY to interpreter net-writes (D-C
    # ruling): a one-liner POST to THIS machine (e.g. a python health-probe to the
    # SF-MCP server on 127.0.0.1:11435) never leaves it, so it is not an outward
    # action — mirrors the curl/wget carve-out in _classify_segment. Guarded by
    # `not is_indexing/indexnow` so it can never un-gate the public Indexing/IndexNow
    # surfaces (whose hosts are never loopback anyway).
    if _is_loopback_host(host) and not is_indexing and not is_indexnow:
        return None
    target = url if url else command.strip()
    return ("index_update", target) if is_indexing else ("net_post", target)


def _classify_bash(command: str) -> tuple[str, str] | None:
    """Split on shell separators and classify EACH segment; the FIRST gated wins.

    Segment-splitting catches a gated action that is NOT the leading token of the
    whole command — `cd x && git push`, `ls && curl -X POST …`, `mkdir y; rm -rf z`
    — which the old whole-command leading-token parse waved through. A single
    command (no separator) is ONE segment, so every single-command result is
    UNCHANGED. A multi-gated command (e.g. `git push && rm -rf x`) returns its FIRST
    gated action; the operator approves it, re-runs, and the gate then catches the
    next — each gated action individually consented (iterative approval).

    Interpreter net-writes (#11) are classified FIRST, at the whole-command level,
    because their quoted code routinely contains shell-meta chars (`;`) that would
    fragment the per-segment markers. Plain interpreter calls return None here and
    fall through to the per-segment leading-token parse unchanged.
    """
    interp = _classify_interpreter_net_write(command)
    if interp is not None:
        return interp
    for segment in _split_segments(command):
        hit = _classify_segment(segment)
        if hit is not None:
            return hit
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
    try:
        workspace = workspace_fn()
    except Exception:
        # An unresolvable workspace (e.g. #7 env-vs-config WorkspaceRootConflictError)
        # cannot prove consent → treat as no workspace so a DETECTED gated action
        # fails-CLOSED (deny) below, never escaping to main()'s fail-OPEN except.
        workspace = None
    slug = None
    if workspace is not None and session_id:
        slug = slug_fn(workspace, session_id=session_id, strict=False)
    th = target_hash(target)
    # Fail-CLOSED consent check: a DETECTED gated action whose consent cannot be
    # VERIFIED must DENY. has_consent_fn reads the ledger and RAISES (e.g.
    # ConsentLedgerError on a corrupt consent.jsonl line); that exception must NOT
    # escape to main()'s fail-OPEN except, which would ALLOW the gated action on an
    # unreadable ledger. The resolvers above return None (never raise), so wrapping
    # only the consent lookup is sufficient + precise.
    consent_error = False
    consented = False
    if workspace is not None and slug is not None and session_id:
        try:
            consented = has_consent_fn(
                workspace, slug, session_id=session_id, action=action, target_hash=th
            )
        except Exception:  # ledger unreadable/corrupt -> consent UNVERIFIABLE
            consent_error = True
    if consented:
        return (0, [])  # consented THIS session -> ALLOW

    run_label = "sess-" + (session_id[:8] if session_id else "unknown")
    messages = [
        f"BLOCKED: {action} → {target}  (bu oturumda onay yok)",
        f'İzin vermek için çalıştır:  /pseo-approve {run_label} {action} "{target}"',
    ]
    if consent_error:
        messages.append(
            "⚠️ consent defteri okunamadı/bozuk — onay DOĞRULANAMADI, "
            "güvenli tarafta REDDEDİLDİ."
        )
    return (2, messages)


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
