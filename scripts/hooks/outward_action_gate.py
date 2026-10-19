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

Wired as a SECOND PreToolUse block (matcher ``Bash|mcp__.*gsc__submit_sitemap``,
which covers both the direct and the plugin-namespaced tool name);
the existing block is untouched. Hooks compose — a Bash call fires both blocks and
either can deny. READ-ONLY: the gate writes no state.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
from scripts.state.outward_log import append_outward  # noqa: E402
from scripts.state.session_binding import (  # noqa: E402
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
)

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

_MCP_SUBMIT_TOOL = "mcp__gsc__submit_sitemap"

# The approval command as the harness REGISTERS it: a plugin command is only
# reachable under its namespaced name (`<plugin.json name>:<command file stem>`).
# The bare `/pseo-approve` the hint used to print answered "Unknown command".
_APPROVE_COMMAND = "/platinum-seo-engine:pseo-approve"

# The SAME server is exposed under two different tool names depending on how it
# resolves: `mcp__gsc__submit_sitemap` directly, and
# `mcp__plugin_platinum-seo-engine_gsc__submit_sitemap` through the plugin. Both
# have been observed live, in different sessions, from this one .mcp.json entry —
# the naming is not under this project's control.
#
# An exact-literal match therefore gates the submission in some sessions and not
# in others, and the ungated session is the silent one: a hook that never matches
# and a hook that always allows look identical from outside. Matching the suffix
# covers both forms and cannot drift again when namespacing changes.
_MCP_SUBMIT_SUFFIX = "gsc__submit_sitemap"


def _is_mcp_submit_tool(tool_name) -> bool:
    """True for every naming form of the gated sitemap-submit tool."""
    return (
        isinstance(tool_name, str)
        and tool_name.startswith("mcp__")
        and tool_name.endswith(_MCP_SUBMIT_SUFFIX)
    )


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

# G-01 tier table (data, not code): which gated actions run freely, which run and
# are logged, which need a consent the USER typed. See consent_policy.json.
_POLICY = json.loads(
    Path(__file__).with_name("consent_policy.json").read_text(encoding="utf-8")
)
_DESTRUCTIVE_PUSH_FLAGS = frozenset(_POLICY["destructive_push_flags"])

TIER_FREE = "serbest"
TIER_LOGGED = "kayitli"
TIER_CONSENT = "onayli"
_TIER_RANK = {TIER_FREE: 0, TIER_LOGGED: 1, TIER_CONSENT: 2}


@dataclass(frozen=True)
class Hit:
    """One gated action found in a tool call, with its consent tier."""

    action: str
    target: str
    tier: str


# ---------------------------------------------------------------------------
# PURE classification (no IO; the heart, fully unit-tested)
# ---------------------------------------------------------------------------

# An UNQUOTED shell redirection operator, with its optional fd / `&` prefix.
# Longest operators first so `>>` / `>&` win over `>`.
_REDIR_OP_RE = re.compile(r"(?:\d+|&)?(?:>>|>&|>\||<<<|<<-|<<|<>|<&|>|<)")


def _is_span_start(s: str, i: int) -> bool:
    """A quote, a backtick, ``$(``/``${`` or a process substitution ``<(``/``>(``."""
    nxt = s[i + 1:i + 2]
    return s[i] in "'\"`" or (s[i] == "$" and nxt in ("(", "{")) or (
        s[i] in "<>" and nxt == "(")


def _span_end(s: str, i: int) -> int:
    """End index of the span opened at ``s[i]`` (see _is_span_start). Its content
    is copied verbatim — a ``<``/``>`` inside it is NOT a redirection.
    Unterminated -> end of string."""
    n = len(s)
    if s[i] == "'":
        j = s.find("'", i + 1)
        return n if j < 0 else j + 1
    if s[i] in '"`':
        j = i + 1
        while j < n and s[j] != s[i]:
            j += 2 if s[j] == "\\" else 1
        return min(j + 1, n)
    opener = s[i + 1]
    closer = ")" if opener == "(" else "}"
    depth, j = 0, i + 1
    while j < n:
        if _is_span_start(s, j) and s[j] not in "<>$":
            j = _span_end(s, j)
            continue
        if s[j] == opener:
            depth += 1
        elif s[j] == closer:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _strip_redirections(segment: str) -> str:
    """Remove UNQUOTED redirections (``2>&1``, ``>/dev/null``, ``< in``, ``&>f``…)
    and their operand word — exactly what the shell removes before building argv.

    A redirection is never an argument of the command (``rm a 2>/dev/null``
    deletes only ``a``), so keeping it in the target made the consent the operator
    gave for the real object (``origin main``) unmatchable on the re-run
    (``origin main 2>&1``). Quoted / escaped / expansion-embedded ``<`` ``>`` are
    filenames or code, NOT operators, and are copied verbatim: ``rm a ">" b``
    keeps ``a > b``, so a consent for ``a`` can never cover deleting ``b``.
    """
    out: list[str] = []
    i, n = 0, len(segment)
    word_start = True
    while i < n:
        c = segment[i]
        if _is_span_start(segment, i):
            j = _span_end(segment, i)
            out.append(segment[i:j])
            i, word_start = j, False
            continue
        if c == "\\":
            out.append(segment[i:i + 2])
            i, word_start = i + 2, False
            continue
        is_op_char = c in "<>" or (c == "&" and segment[i + 1:i + 2] == ">")
        m = _REDIR_OP_RE.match(segment, i) if (word_start or is_op_char) else None
        if m is None:
            out.append(c)
            word_start = c in " \t"
            i += 1
            continue
        i = m.end()
        while i < n and segment[i] in " \t":
            i += 1
        while i < n and segment[i] not in " \t<>":  # the operand word
            if _is_span_start(segment, i):
                i = _span_end(segment, i)
            else:
                i += 2 if segment[i] == "\\" else 1
        out.append(" ")
        word_start = True
    return "".join(out)


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
        rest = tokens[i + 1:]
        # Destructive flags stay IN the target (G-09): consent for a plain
        # `git push origin main` must not also cover `--force` / `--delete`.
        destructive = [x for x in rest if _is_destructive_push_flag(x)]
        operands = [x for x in rest if not x.startswith("-")]
        target = " ".join(operands) if operands else "origin"
        return " ".join([*destructive, target]) if destructive else target
    return None


def _is_destructive_push_flag(tok: str) -> bool:
    """--force / --delete / --mirror …, their ``=value`` forms, and short ``-f``/``-d``
    even when combined (``-uf``)."""
    if tok in _DESTRUCTIVE_PUSH_FLAGS or tok.split("=", 1)[0] in _DESTRUCTIVE_PUSH_FLAGS:
        return True
    return (
        tok.startswith("-") and not tok.startswith("--") and len(tok) > 2
        and any(ch in tok[1:] for ch in "fd")
    )


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
    # Redirections are not argv: drop them before deriving the target, then peel
    # sudo/env/... wrappers (#10).
    tokens = _unwrap_wrappers(_tokenize(_strip_redirections(segment)))
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
    never bricks a command. The MCP sitemap-submit tool is ALWAYS classified (it is
    an outward submission to Google); its target is the feedpath (the sitemap being
    submitted), falling back to siteUrl. Returns the FIRST gated action; ``assess_all``
    returns every one with its tier.
    """
    if _is_mcp_submit_tool(tool_name):
        ti = tool_input if isinstance(tool_input, dict) else {}
        return ("mcp_submit", ti.get("feedpath") or ti.get("siteUrl") or "")
    command = _bash_command(tool_name, tool_input)
    return _classify_bash(command) if command else None


def _bash_command(tool_name: str, tool_input) -> str | None:
    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    return command if isinstance(command, str) and command.strip() else None


# ---------------------------------------------------------------------------
# PURE tiering (G-01) — consent_policy.json decides; no IO beyond that table
# ---------------------------------------------------------------------------

def _host_matches(host: str, suffixes) -> bool:
    return any(host == sfx or host.endswith("." + sfx) for sfx in suffixes)


def _post_tier(action: str, target: str, text: str) -> str:
    """index_update / net_post: IndexNow + Indexing URL_UPDATED free, known SEO APIs
    logged, URL_DELETED and every other host need consent."""
    if any(marker in text for marker in _POLICY["consent_body_markers"]):
        return TIER_CONSENT
    host = (urlparse(target).hostname or "").lower() if "://" in target else ""
    if _host_matches(host, _POLICY["free_post_host_suffixes"]):
        return TIER_FREE
    if _host_matches(host, _POLICY["logged_post_host_suffixes"]):
        return TIER_LOGGED
    return TIER_CONSENT


def _push_tier(target: str) -> str:
    """Destructive flags / ``+ref`` / ``:ref`` need consent; a push that is or may
    be to a protected branch (bare push, remote only) is logged; others are free."""
    parts = target.split()
    if any(_is_destructive_push_flag(x) for x in parts):
        return TIER_CONSENT
    refspecs = parts[1:]  # parts[0] is the remote
    if any(r.startswith(("+", ":")) for r in refspecs):
        return TIER_CONSENT
    if not refspecs:
        return TIER_LOGGED  # current branch unknown — could be main
    protected = set(_POLICY["protected_branches"])
    if any(r.rsplit(":", 1)[-1].removeprefix("refs/heads/") in protected for r in refspecs):
        return TIER_LOGGED
    return TIER_FREE


def _path_segments(path: str) -> list[str]:
    return [seg for seg in path.split("/") if seg not in ("", ".")]


def _is_protected_path(path: str) -> bool:
    """master.xlsx / ledgers / _state / backups / a projects/<slug> folder itself."""
    segs = _path_segments(path)
    if not segs:
        return False
    name = segs[-1]
    if name in _POLICY["protected_names"] or name.endswith(
        tuple(_POLICY["protected_name_suffixes"])
    ):
        return True
    for i, seg in enumerate(segs):
        if seg == "_state":
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if nxt not in _POLICY["temp_state_subdirs"]:
                return True
        elif seg == "backups":
            return True
    # the project folder itself (…/projects/<slug>), or the projects/ dir
    return segs[-1] == "projects" or (len(segs) >= 2 and segs[-2] == "projects")


def _is_temp_path(path: str) -> bool:
    if path.startswith(tuple(_POLICY["temp_path_prefixes"])):
        return True
    if path.endswith(tuple(_POLICY["temp_suffixes"])):
        return True
    segs = _path_segments(path)
    if any(seg in _POLICY["temp_path_segments"] for seg in segs):
        return True
    return any(
        seg == "_state" and i + 1 < len(segs) and segs[i + 1] in _POLICY["temp_state_subdirs"]
        for i, seg in enumerate(segs)
    )


def _is_recursive_delete(tokens: list[str]) -> bool:
    return any(
        tok == "--recursive"
        or (tok.startswith("-") and not tok.startswith("--") and ("r" in tok or "R" in tok))
        for tok in tokens[1:]
    )


def _delete_tier(tokens: list[str]) -> str:
    """Protected data needs consent; temp/output paths are free; any other bulk
    (recursive) delete needs consent; a single other file is logged."""
    operands = _operands(tokens, 1)
    if any(_is_protected_path(op) for op in operands):
        return TIER_CONSENT
    if operands and all(_is_temp_path(op) for op in operands):
        return TIER_FREE
    if _is_recursive_delete(tokens):
        return TIER_CONSENT
    return TIER_LOGGED


def _segment_hit(segment: str) -> Hit | None:
    hit = _classify_segment(segment)
    if hit is None:
        return None
    action, target = hit
    if action == "fs_delete":
        tokens = _unwrap_wrappers(_tokenize(_strip_redirections(segment)))
        return Hit(action, target, _delete_tier(tokens))
    if action == "git_push":
        return Hit(action, target, _push_tier(target))
    return Hit(action, target, _post_tier(action, target, segment))


def assess_all(tool_name: str, tool_input) -> list[Hit]:
    """EVERY gated action in the call, each with its tier (G-01).

    A command is judged by all of its gated segments: a free first segment must
    never wave through a critical one chained behind it.
    """
    if _is_mcp_submit_tool(tool_name):
        action, target = classify(tool_name, tool_input)
        return [Hit(action, target, TIER_FREE)]
    command = _bash_command(tool_name, tool_input)
    if command is None:
        return []
    hits: list[Hit] = []
    interp = _classify_interpreter_net_write(command)
    if interp is not None:
        hits.append(Hit(*interp, _post_tier(*interp, command)))
    for segment in _split_segments(command):
        hit = _segment_hit(segment)
        if hit is not None:
            hits.append(hit)
    return hits


def assess(tool_name: str, tool_input) -> Hit | None:
    """The single highest-tier gated action of the call (or None)."""
    hits = assess_all(tool_name, tool_input)
    return max(hits, key=lambda h: _TIER_RANK[h.tier]) if hits else None


# ---------------------------------------------------------------------------
# Consent forgery (G-01): the model may READ the ledger, never write it
# ---------------------------------------------------------------------------

_LEDGER_NAME = "consent.jsonl"
_READ_ONLY_TOKENS = frozenset({
    "cat", "head", "tail", "less", "more", "grep", "rg", "wc", "jq", "ls", "stat",
    "file", "sha256sum", "shasum", "md5", "md5sum", "diff", "cmp", "echo", "printf",
})
_LEDGER_REDIRECT_RE = re.compile(r">\s*\S*" + re.escape(_LEDGER_NAME))
_FILE_EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


def is_consent_forgery(tool_name: str, tool_input) -> bool:
    """True when the call would write consent itself instead of the user granting it.

    Covers the recorder CLI / ``append_consent`` from any shell, any non-read-only
    command or redirect touching ``consent.jsonl``, and the file-edit tools on it.
    """
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool_name in _FILE_EDIT_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        return isinstance(path, str) and Path(path).name == _LEDGER_NAME
    command = _bash_command(tool_name, tool_input)
    if command is None:
        return False
    if "consent_ledger" in command and ("approve" in command or "append_consent" in command):
        return True
    if _LEDGER_NAME not in command:
        return False
    if _LEDGER_REDIRECT_RE.search(command):
        return True
    for segment in _split_segments(command):
        if _LEDGER_NAME not in segment:
            continue
        tokens = _unwrap_wrappers(_tokenize(segment))
        if tokens and tokens[0].rsplit("/", 1)[-1] not in _READ_ONLY_TOKENS:
            return True
    return False


_FORGERY_MESSAGES = [
    "BLOCKED: onay defterine (consent.jsonl) model yazamaz.",
    "Onay yalnız Claude sohbetine SENİN yazdığın mesajla kaydedilir:  "
    f"{_APPROVE_COMMAND} <run_id> <action> <target>   ya da   onay: <action> <target>",
]


# ---------------------------------------------------------------------------
# Decision (IO via injected resolvers; fail-OPEN non-gated, fail-CLOSED gated)
# ---------------------------------------------------------------------------

def _log_logged_hits(
    hits: list[Hit], *, workspace, session_id: str | None, log_fn, slug_fn,
) -> None:
    """Best-effort outward.jsonl lines for the logged-tier hits — never raises, and
    writes nothing for an unbound session (G-05: never active.json's project)."""
    logged = [h for h in hits if h.tier == TIER_LOGGED]
    if not logged or workspace is None or not session_id:
        return
    try:
        slug = slug_fn(workspace, session_id=session_id, strict=True)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for hit in logged:
            log_fn(workspace, slug, session_id=session_id, action=hit.action,
                   target=hit.target, now_iso=now_iso)
    except Exception as exc:  # a log hiccup must never block a logged action
        _emit(f"WARNING outward log not written: {exc!r}")


def evaluate(
    payload: dict,
    *,
    has_consent_fn=has_session_consent,
    session_id_fn=current_session_id,
    workspace_fn=resolve_workspace_root,
    slug_fn=resolve_session_project,
    log_fn=append_outward,
) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` — 0 allows the tool, 2 denies it.

    Consent forgery -> DENY. No gated action -> (0, []) BEFORE any resolution, so a
    plain command is never bricked. Otherwise every gated action is tiered (G-01):
    free ones pass, logged ones pass and get an outward.jsonl line, and each
    consent-tier one passes only if THIS session's bound project holds a matching
    consent; the first without one is DENIED (fail-closed) with the copy-paste fix.
    """
    if not isinstance(payload, dict):
        return (0, [])
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if is_consent_forgery(tool_name, tool_input):
        return (2, list(_FORGERY_MESSAGES))
    hits = assess_all(tool_name, tool_input)
    if not hits:
        return (0, [])  # not gated -> ALLOW

    session_id = session_id_fn(payload)
    try:
        workspace = workspace_fn()
    except Exception:
        # An unresolvable workspace (e.g. #7 env-vs-config WorkspaceRootConflictError)
        # cannot prove consent → treat as no workspace so a DETECTED gated action
        # fails-CLOSED (deny) below, never escaping to main()'s fail-OPEN except.
        workspace = None

    for hit in hits:
        if hit.tier == TIER_CONSENT:
            denied = _consent_denial(
                hit, workspace=workspace, session_id=session_id,
                has_consent_fn=has_consent_fn, slug_fn=slug_fn,
            )
            if denied is not None:
                return (2, denied)
    _log_logged_hits(hits, workspace=workspace, session_id=session_id,
                     log_fn=log_fn, slug_fn=slug_fn)
    return (0, [])


def _consent_denial(
    hit: Hit, *, workspace, session_id: str | None, has_consent_fn, slug_fn,
) -> list[str] | None:
    """None if THIS session consented to ``hit``; else the deny messages."""
    slug = None
    if workspace is not None and session_id:
        slug = slug_fn(workspace, session_id=session_id, strict=False)
    th = target_hash(hit.target)
    # Fail-CLOSED consent check: a DETECTED gated action whose consent cannot be
    # VERIFIED must DENY. has_consent_fn reads the ledger and RAISES (e.g.
    # ConsentLedgerError on a corrupt consent.jsonl line); that exception must NOT
    # escape to main()'s fail-OPEN except, which would ALLOW the gated action on an
    # unreadable ledger. The resolvers above return None (never raise), so wrapping
    # only the consent lookup is sufficient + precise.
    consent_error = False
    if workspace is not None and slug is not None and session_id:
        try:
            if has_consent_fn(
                workspace, slug, session_id=session_id, action=hit.action, target_hash=th
            ):
                return None  # consented THIS session -> ALLOW
        except Exception:  # ledger unreadable/corrupt -> consent UNVERIFIABLE
            consent_error = True

    run_label = "sess-" + (session_id[:8] if session_id else "unknown")
    # The target is shell-quoted (single quotes) because the command text-substitutes
    # it into a shell block: inside "…" a `$T` would expand and a `"` would split it,
    # so the recorded hash would no longer be the one the gate checks.
    messages = [
        f"BLOCKED: {hit.action} → {hit.target}  (bu oturumda onay yok)",
        f"İzin vermek için Claude sohbetine yaz (terminale değil):  "
        f"{_APPROVE_COMMAND} {run_label} {hit.action} {shlex.quote(hit.target)}",
    ]
    if consent_error:
        messages.append(
            "⚠️ consent defteri okunamadı/bozuk — onay DOĞRULANAMADI, "
            "güvenli tarafta REDDEDİLDİ."
        )
    return messages


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
