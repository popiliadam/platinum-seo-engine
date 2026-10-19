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
_CONSENT_MAX_AGE_SECONDS = float(_POLICY["consent_max_age_hours"]) * 3600


def _ledger():
    """The consent ledger, imported lazily (G-03): it needs jsonschema, and an
    import failure at hook start-up made the hook exit 1 — which Claude Code
    treats as ALLOW. Classification stays stdlib-only; only the consent check
    needs the ledger, and main() turns a failure there into a DENY."""
    from scripts.state import consent_ledger
    return consent_ledger
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


def _host(url: str) -> str:
    """Lower-cased host of ``url``, or "" when it cannot be parsed (``http://[``):
    an unknown host is never loopback and never on a free/logged list, so a
    malformed URL fails CLOSED instead of crashing the gate into an allow."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


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


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BODY_FLAGS = frozenset({"--json", "--upload-file", "-T", "--body-data", "--body-file"})


def _has_post_flag(tokens: list[str]) -> bool:
    """True iff the tokens send a body or use a write method (curl/wget) — incl.
    combined short flags (``-sd``), ``--json``, uploads, and PUT/PATCH/DELETE (G-02).
    Short-flag rules are curl's: for wget ``-T`` is a timeout and ``-d`` debug."""
    is_curl = bool(tokens) and tokens[0].rsplit("/", 1)[-1] == "curl"
    for i, tok in enumerate(tokens):
        if not is_curl and tok.startswith("-") and not tok.startswith("--"):
            continue  # wget's short flags never carry a body
        nxt = tokens[i + 1].upper() if i + 1 < len(tokens) else ""
        if tok in _POST_DATA_FLAGS or tok in _BODY_FLAGS:
            return True
        if tok.startswith(("--data", "--post-data", "--post-file", "--json=",
                           "--upload-file=", "--body-data", "--body-file")):
            return True
        if tok in ("-X", "--request", "--method") and nxt in _WRITE_METHODS:
            return True
        if tok.startswith(("--request=", "--method=")) and tok.split("=", 1)[1].upper() in _WRITE_METHODS:
            return True
        if tok.startswith("-X") and len(tok) > 2:  # -XPOST / -XPUT (never a combined flag)
            if tok[2:].upper() in _WRITE_METHODS:
                return True
            continue
        if tok.startswith("-d") and not tok.startswith("--") and len(tok) > 2:  # -d<data>
            return True
        if (tok.startswith("-") and not tok.startswith("--") and len(tok) > 2
                and tok[1:].isalpha() and any(ch in tok[1:] for ch in "dFT")):  # -sd, -sSF
            return True
    return False


# curl / wget options that take a value: that value is never the request URL.
_HTTP_ARG_FLAGS = frozenset({
    "-o", "--output", "-H", "--header", "-A", "--user-agent", "-e", "--referer",
    "-u", "--user", "-b", "--cookie", "-c", "--cookie-jar", "-X", "--request",
    "-d", "--data", "--data-raw", "--data-binary", "--data-ascii", "--data-urlencode",
    "--json", "-F", "--form", "-T", "--upload-file", "-w", "--write-out",
    "-m", "--max-time", "--connect-timeout", "-r", "--range", "-K", "--config",
    "--cacert", "--cert", "-E", "--key", "-x", "--proxy", "--resolve",
    "-O", "--output-document", "--output-file", "-t", "--tries", "--timeout",
    "--post-data", "--post-file", "--body-data", "--body-file", "--method",
    "-P", "--directory-prefix", "-U", "-a", "--append-output", "-i", "--input-file",
})
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_HOSTLIKE_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(:\d+)?(/\S*)?$")


def _request_urls(tokens: list[str]) -> list[str]:
    """Every URL a curl / wget call would contact, normalised to carry a scheme.

    Positional operands count even without ``http(s)://`` (curl and wget both
    accept ``host/path``), the scheme is matched case-insensitively, and
    ``--url`` values count; values of options that take an argument (``-o
    file``, ``-H header``, ``-d data``) are skipped. ``wget -O out.html`` and
    ``-o page.html`` therefore stay files, not hosts.
    """
    urls: list[str] = []
    pending: str | None = None  # "url" = next token is a URL, "skip" = an option value
    for tok in tokens[1:]:
        if pending is not None:
            if pending == "url":
                urls.append(tok)
            pending = None
            continue
        if tok == "--url":
            pending = "url"
        elif tok.startswith("--url="):
            urls.append(tok.split("=", 1)[1])
        elif tok.startswith("-"):
            # a separate value follows (`-o file`, `-T 30`); glued forms carry it inline
            if tok in _HTTP_ARG_FLAGS:
                pending = "skip"
        elif _SCHEME_RE.match(tok) or _HOSTLIKE_RE.match(tok):
            urls.append(tok)
    return [u if _SCHEME_RE.match(u) else "http://" + u for u in urls if u]


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


def _git_subcommand(tokens: list[str]) -> tuple[str | None, list[str]]:
    """(subcommand, its arguments) of a git invocation, walking past git's global
    options (those that consume the next token are skipped in pairs)."""
    i = 1  # tokens[0] == "git"
    while i < len(tokens):
        tok = tokens[i]
        if tok in _GIT_GLOBAL_ARG_FLAGS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok, tokens[i + 1:]
    return None, []


def _git_clean_target(tokens: list[str]) -> str | None:
    """``git clean -f…`` deletes untracked files (G-02): its target, else None."""
    sub, rest = _git_subcommand(tokens)
    if sub != "clean":
        return None
    forced = "--force" in rest or any(
        t.startswith("-") and not t.startswith("--") and "f" in t[1:] for t in rest
    )
    return ("git clean " + " ".join(rest)).strip() if forced else None


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

    if first == "mv":  # moving protected data away (or over it) changes the project
        # Every operand counts, not just operands[:-1]: `mv -t DIR SRC…` puts the
        # target first, and moving INTO a protected path is sensitive too.
        protected = [op for op in _operands(tokens, 1) if _is_protected_path(op)]
        return ("fs_delete", " ".join(protected)) if protected else None

    if first == "find":
        target = _find_delete_target(tokens)
        return ("fs_delete", target) if target is not None else None

    if first == "rsync" and any(
        t.startswith("--delete") or t == "--remove-source-files" for t in tokens
    ):
        operands = _operands(tokens, 1)
        return ("fs_delete", operands[-1] if operands else segment.strip())

    if first == "git":  # gated: `git push` / `git clean -f` (even behind global flags)
        tgt = _git_push_target(tokens)
        if tgt is not None:
            return ("git_push", tgt)
        clean = _git_clean_target(tokens)
        return ("fs_delete", clean) if clean is not None else None

    if first in _HTTP_TOKENS:
        # Every URL counts (G-02): a loopback URL placed first must not hide a
        # public one behind it.
        urls = _request_urls(tokens)
        public = [u for u in urls if not _is_loopback_host(_host(u))]
        if urls and not public:
            return None  # loopback only (#12); Indexing/IndexNow hosts are never loopback
        url = public[0] if public else None
        host = _host(url) if url else ""
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


def _find_delete_target(tokens: list[str]) -> str | None:
    """``find … -delete`` / ``-exec rm …``: the search roots + name patterns, else None."""
    deletes = "-delete" in tokens or any(
        tok in ("-exec", "-execdir", "-ok", "-okdir") and i + 1 < len(tokens)
        and tokens[i + 1].rsplit("/", 1)[-1] in _DELETE_TOKENS
        for i, tok in enumerate(tokens)
    )
    if not deletes:
        return None
    roots: list[str] = []
    for tok in tokens[1:]:
        if tok.startswith(("-", "(", "!")):
            break
        roots.append(tok)
    names = [tokens[i + 1] for i, tok in enumerate(tokens[:-1])
             if tok in ("-name", "-iname", "-path", "-ipath", "-wholename")]
    return " ".join(roots + names) or "."


_INTERP_DELETE_RE = re.compile(
    r"(os\.remove|os\.unlink|os\.rmdir|shutil\.rmtree|\.unlink|\.rmdir|"
    r"rmSync|unlinkSync|rmdirSync|FileUtils\.rm_rf|FileUtils\.rm|File\.delete)"
    r"\s*\(\s*(?:(['\"])(.*?)\2)?"
)
_RECURSIVE_DELETE_CALLS = ("rmtree", "rmSync", "rm_rf")


def _classify_interpreter_delete(command: str) -> Hit | None:
    """An interpreter one-liner that deletes files (G-02): tiered on the literal
    paths it names; with no literal path the gate cannot tell, so consent."""
    leads_interpreter = any(
        (toks := _unwrap_wrappers(_tokenize(seg)))
        and _is_interpreter(toks[0].rsplit("/", 1)[-1])
        for seg in _split_segments(command)
    )
    if not leads_interpreter:
        return None
    matches = list(_INTERP_DELETE_RE.finditer(command))
    if not matches:
        return None
    paths = [m.group(3) for m in matches if m.group(3)]
    if not paths:
        return Hit("fs_delete", command.strip(), TIER_CONSENT)
    recursive = any(call in m.group(1) for m in matches for call in _RECURSIVE_DELETE_CALLS)
    tokens = ["rm", *(["-r"] if recursive else []), *paths]
    return Hit("fs_delete", " ".join(paths), _delete_tier(tokens))


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
    urls = _URL_IN_TEXT_RE.findall(command)
    public = [u for u in urls if not _is_loopback_host(_host(u))]
    if urls and not public:
        return None  # loopback only (#12)
    url = public[0] if public else None
    host = _host(url) if url else ""
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


_ENV_PREFIX_RE = re.compile(
    r"""^(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|"(?:[^"\\]|\\.)*"|[^\s'"]*)\s+)+"""
)
_WHICH_RE = re.compile(
    r"\$\(\s*(?:which|command\s+-v|type\s+-p)\s+([\w.-]+)\s*\)"
    r"|`\s*(?:which|command\s+-v|type\s+-p)\s+([\w.-]+)\s*`"
)
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_MAX_NESTING = 3
_BLOCK_KEYWORDS = frozenset({"do", "then", "else", "elif", "if", "while", "until", "time", "!"})


def _substitutions(text: str) -> list[str]:
    """Bodies of ``$( … )`` and backtick command substitutions (not ``$(( ))``
    arithmetic, nothing inside single quotes)."""
    found: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("$(", i) and not text.startswith("$((", i):
            j = _span_end(text, i)
            found.append(text[i + 2:j - 1])
            i = j
        elif text[i] == "`":
            j = _span_end(text, i)
            found.append(text[i + 1:j - 1])
            i = j
        elif text[i] == "'":
            i = _span_end(text, i)
        else:
            i += 1
    return found


def _strip_block_keywords(segment: str) -> str:
    """``do rm -rf x`` / ``then git push`` → the command after the keyword."""
    words = segment.split(None, 1)
    while words and words[0] in _BLOCK_KEYWORDS:
        segment = words[1] if len(words) > 1 else ""
        words = segment.split(None, 1)
    return segment


def _nested_script(segment: str) -> str | None:
    """The command text run by ``bash -c '…'`` / ``sh -c`` / ``eval …``, else None."""
    tokens = _unwrap_wrappers(_tokenize(segment))
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]
    if head == "eval":
        return " ".join(tokens[1:]) or None
    if head in _SHELLS:
        for i, tok in enumerate(tokens[1:], start=1):
            if tok == "-c" or (tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]):
                return tokens[i + 1] if i + 1 < len(tokens) else None
    return None


def _expanded_segments(command: str, depth: int = 0) -> list[str]:
    """Shell segments with the simple disguises removed (G-02): ``NAME=value``
    prefixes, a ``( … )`` subshell, ``$(which git)``, and the script inside
    ``bash -c`` / ``sh -c`` / ``eval`` (recursively, bounded). Expanding only ever
    EXPOSES a gated command; it can never hide one."""
    out: list[str] = []
    if depth < _MAX_NESTING:  # what $( … ) / backticks would run (review #3)
        for inner in _substitutions(_WHICH_RE.sub(lambda m: m.group(1) or m.group(2), command)):
            out.extend(_expanded_segments(inner, depth + 1))
    for segment in _split_segments(command):
        seg = _WHICH_RE.sub(lambda m: m.group(1) or m.group(2), segment).strip()
        if seg.startswith("("):
            seg = seg[1:].strip()
            if seg.endswith(")"):
                seg = seg[:-1].strip()
        seg = _strip_block_keywords(seg.lstrip("{!").strip())
        seg = _ENV_PREFIX_RE.sub("", seg)
        if not seg:
            continue
        inner = _nested_script(seg) if depth < _MAX_NESTING else None
        if inner is not None:
            out.extend(_expanded_segments(inner, depth + 1))
        else:
            out.append(seg)
    return out


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
    deleting = _classify_interpreter_delete(command)
    if deleting is not None:
        return (deleting.action, deleting.target)
    for segment in _expanded_segments(command):
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
    host = _host(target) if "://" in target else ""
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


def _is_unresolvable(path: str) -> bool:
    """A path the gate cannot know before the shell expands it."""
    return path.startswith("~") or any(ch in path for ch in "$`")


def _is_protected_path(path: str) -> bool:
    """master.xlsx / ledgers / _state / backups / a projects/<slug> folder itself —
    judged on the raw operand AND its normalised form (``outputs/../_state``)."""
    return any(_is_protected_form(form) for form in {path, os.path.normpath(path)})


def _is_protected_form(path: str) -> bool:
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
    """Temp/output location, judged AFTER normalisation; a path that climbs out of
    its start (``outputs/../..``) or that the shell would expand is never temp."""
    if _is_unresolvable(path):
        return False
    path = os.path.normpath(path)
    if path == ".." or path.startswith("../"):
        return False
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


def _segment_hit(segment: str, command: str | None = None) -> Hit | None:
    hit = _classify_segment(segment)
    if hit is None:
        return None
    action, target = hit
    if action == "fs_delete":
        tokens = _unwrap_wrappers(_tokenize(_strip_redirections(segment)))
        head = tokens[0].rsplit("/", 1)[-1] if tokens else ""
        if head == "git":  # git clean -f: untracked files, no undo
            return Hit(action, target, TIER_CONSENT)
        if head in ("find", "rsync"):  # bulk by nature
            return Hit(action, target, _delete_tier(["rm", "-r", *target.split()]))
        return Hit(action, target, _delete_tier(tokens))
    if action == "git_push":
        return Hit(action, target, _push_tier(target))
    tokens = _tokenize(_strip_redirections(segment))
    body, body_unknown = _request_bodies(tokens, command or segment)
    unwrapped = _unwrap_wrappers(tokens)
    return _strictest_url_hit(action, target, segment + "\n" + body,
                              _request_urls(unwrapped), body_unknown=body_unknown)


_BODY_FILE_FLAGS = frozenset({"-d", "--data", "--data-binary", "--data-ascii",
                              "--data-urlencode", "--json", "-T", "--upload-file",
                              "--post-file", "--body-file"})
_BODY_MAX_BYTES = 1_000_000


def _request_bodies(tokens: list[str], command: str) -> tuple[str, bool]:
    """(text of the bodies the request sends from files / stdin, unknown?).

    ``-d @file`` / ``--data-binary @file`` / ``-T file`` … are read so a
    ``URL_DELETED`` inside them is seen; ``@-`` (stdin, e.g. a heredoc) yields the
    whole command text. ``unknown`` is True when a body file cannot be read."""
    texts: list[str] = []
    unknown = False
    for i, tok in enumerate(tokens):
        value = None
        if tok in _BODY_FILE_FLAGS and i + 1 < len(tokens):
            value = tokens[i + 1]
        elif "=" in tok and tok.split("=", 1)[0] in _BODY_FILE_FLAGS:
            value = tok.split("=", 1)[1]
        elif tok.startswith("-d@"):
            value = tok[2:]
        if value is None:
            continue
        is_file_flag = tok.split("=", 1)[0] in ("-T", "--upload-file", "--post-file", "--body-file")
        if not (value.startswith("@") or is_file_flag):
            continue  # an inline body: already part of the segment text
        name = value[1:] if value.startswith("@") else value
        if name == "-":
            texts.append(command)
            continue
        try:
            path = Path(os.path.expanduser(name))
            if path.stat().st_size > _BODY_MAX_BYTES:
                unknown = True
                continue
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            unknown = True
    return "\n".join(texts), unknown


def _strictest_url_hit(
    action: str, target: str, text: str, urls: list[str], *, body_unknown: bool = False,
) -> Hit:
    """One request may go to several URLs (curl sends to each): tier EVERY public
    one and keep the strictest, naming that URL as the consent target. A body the
    gate could not read, sent to the Indexing API, may be a URL_DELETED: consent."""
    public = [u for u in urls if not _is_loopback_host(_host(u))]
    if not public:
        return Hit(action, target, _post_tier(action, target, text))

    def tier_of(url: str) -> str:
        if body_unknown and _host(url) == _INDEXING_HOST:
            return TIER_CONSENT
        return _post_tier(action, url, text)

    tiered = [(tier_of(u), u) for u in public]
    tier, url = max(tiered, key=lambda tu: _TIER_RANK[tu[0]])
    if action == "index_update" and _host(url) != _INDEXING_HOST:
        action = "net_post"
    return Hit(action, url, tier)


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
        hits.append(_strictest_url_hit(*interp, command, _URL_IN_TEXT_RE.findall(command)))
    deleting = _classify_interpreter_delete(command)
    if deleting is not None:
        hits.append(deleting)
    for segment in _expanded_segments(command):
        hit = _segment_hit(segment, command)
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


_SCRIPT_RUNNERS = _INTERPRETER_TOKENS | frozenset({"bash", "sh", "zsh"})
_ENV_ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_LEDGER_WRITE_MARKERS = ("'a'", '"a"', "'w'", '"w"', "write(", ">>", "O_APPEND", "O_WRONLY")
_SCRIPT_SCAN_MAX_BYTES = 1_000_000


def _writes_ledger(text: str) -> bool:
    """Source text that appends consent: the writer API, the recorder CLI, or a
    write-mode use of consent.jsonl."""
    if "append_consent" in text:
        return True
    if "consent_ledger" in text and "approve" in text:
        return True
    return _LEDGER_NAME in text and any(m in text for m in _LEDGER_WRITE_MARKERS)


def _script_files(segment: str, cwd: str | None) -> list[Path]:
    """Files an interpreter/shell segment would execute (``python3 x.py``)."""
    tokens = _unwrap_wrappers(_tokenize(segment))
    while tokens and _ENV_ASSIGN_RE.match(tokens[0]):  # PYTHONPATH=. python3 x.py
        tokens = tokens[1:]
    if not tokens or tokens[0].rsplit("/", 1)[-1] not in _SCRIPT_RUNNERS:
        return []
    found: list[Path] = []
    for tok in tokens[1:]:
        if tok.startswith("-"):
            if tok in ("-c", "-m", "-e"):  # inline code / module: no file to read
                return found
            continue
        cand = Path(os.path.expanduser(tok))
        if not cand.is_absolute() and cwd:
            cand = Path(cwd) / cand
        if cand.is_file():
            found.append(cand)
        break  # the first operand is the script; the rest are its arguments
    return found


def _is_installed_plugin_path(path: str) -> bool:
    """A file inside the INSTALLED plugin (the gate, its policy, the hooks)."""
    root = os.path.realpath(_PLUGIN_ROOT)
    if "/plugins/cache/" not in root + "/":
        return False  # running from a dev checkout: editing it is normal work
    target = os.path.realpath(os.path.expanduser(path))
    return target == root or target.startswith(root + os.sep)


def forgery_reason(tool_name: str, tool_input, cwd: str | None = None) -> str | None:
    """Why this call would let the model grant itself consent, or None.

    Covers the recorder CLI / ``append_consent`` from any shell, any non-read-only
    command or redirect touching ``consent.jsonl``, a script FILE that writes the
    ledger, the file-edit tools on the ledger, and edits to the installed plugin
    (the gate and its policy). This is a guardrail against a model approving its
    own action, not a sandbox: a process running as the same user can always
    find another path, which is why consent itself is taken only from the user's
    chat message (consent_from_prompt.py).
    """
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool_name in _FILE_EDIT_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not isinstance(path, str) or not path:
            return None
        if Path(path).name == _LEDGER_NAME:
            return "ledger"
        return "plugin" if _is_installed_plugin_path(path) else None
    command = _bash_command(tool_name, tool_input)
    if command is None:
        return None
    if "consent_ledger" in command and ("approve" in command or "append_consent" in command):
        return "ledger"
    if _LEDGER_NAME in command and _LEDGER_REDIRECT_RE.search(command):
        return "ledger"
    for segment in _split_segments(command):
        if _LEDGER_NAME in segment:
            tokens = _unwrap_wrappers(_tokenize(segment))
            if tokens and tokens[0].rsplit("/", 1)[-1] not in _READ_ONLY_TOKENS:
                return "ledger"
        for script in _script_files(segment, cwd):
            try:
                if script.stat().st_size <= _SCRIPT_SCAN_MAX_BYTES and _writes_ledger(
                    script.read_text(encoding="utf-8", errors="replace")
                ):
                    return "ledger"
            except OSError:
                continue
    return None


def is_consent_forgery(tool_name: str, tool_input, cwd: str | None = None) -> bool:
    """True when the call would let the model write its own consent (see forgery_reason)."""
    return forgery_reason(tool_name, tool_input, cwd) is not None


_CONSENT_HOW = (
    "Onay yalnız Claude sohbetine SENİN yazdığın mesajla kaydedilir:  "
    f"{_APPROVE_COMMAND} <run_id> <action> <target>   ya da   onay: <action> <target>"
)
_FORGERY_MESSAGES = {
    "ledger": ["BLOCKED: onay defterine (consent.jsonl) model yazamaz.", _CONSENT_HOW],
    "plugin": [
        "BLOCKED: kurulu eklentinin dosyaları (onay kapısı, kademe tablosu, hook'lar) "
        "model tarafından değiştirilemez; değişiklik repo'da yapılıp eklenti yeniden kurulur.",
        _CONSENT_HOW,
    ],
}


# ---------------------------------------------------------------------------
# Other shell / file tools (G-06) — mapped onto the Bash / Write / Edit classifiers
# ---------------------------------------------------------------------------

# tool-name suffix -> (canonical tool, field holding the command / path)
_SHELL_TOOL_FIELDS = {
    "__start_process": "command",
    "__run_in_terminal": "command",
    "__execute_command": "command",
}
_FILE_TOOL_FIELDS = {
    "__write_file": ("Write", "path"),
    "__edit_block": ("Edit", "file_path"),
}
_MALFORMED = "__malformed_tool_call__"


def _tool_variants(tool_name: str, tool_input) -> list[tuple[str, dict]]:
    """The (tool, input) pairs to judge for one call.

    Built-in tools pass through. Desktop Commander / terminal shell tools become
    a Bash call; their file tools become Write / Edit on the path they touch. A
    REPL input (``interact_with_process``) is judged both as a shell line and as
    Python code, since the process behind it is usually ``python3 -i``.
    """
    ti = tool_input if isinstance(tool_input, dict) else {}
    if isinstance(tool_name, str) and tool_name.startswith("mcp__"):
        for suffix, field in _SHELL_TOOL_FIELDS.items():
            if tool_name.endswith(suffix) and isinstance(ti.get(field), str):
                return [("Bash", {"command": ti[field]})]
        if tool_name.endswith("__interact_with_process") and isinstance(ti.get("input"), str):
            code = ti["input"]
            return [("Bash", {"command": code}),
                    ("Bash", {"command": "python3 -c " + shlex.quote(code)})]
        if tool_name.endswith("__move_file"):
            src, dst = ti.get("source"), ti.get("destination")
            if isinstance(src, str) and isinstance(dst, str):
                # the destination is written; the source is removed from its place
                return [("Write", {"file_path": dst}),
                        ("Bash", {"command": "mv " + shlex.quote(src) + " " + shlex.quote(dst)})]
            return [(_MALFORMED, {"tool": tool_name})]
        for suffix, (canonical, field) in _FILE_TOOL_FIELDS.items():
            if tool_name.endswith(suffix):
                if isinstance(ti.get(field), str):
                    return [(canonical, {"file_path": ti[field]})]
                return [(_MALFORMED, {"tool": tool_name})]
        if any(tool_name.endswith(suffix) for suffix in (*_SHELL_TOOL_FIELDS, "__interact_with_process")):
            return [(_MALFORMED, {"tool": tool_name})]  # field missing: fail closed
    return [(tool_name, tool_input)]


def _gated(payload: dict) -> tuple[str | None, list[Hit]]:
    """(forgery reason, every gated hit) for the call, across its tool variants."""
    tool_name = payload.get("tool_name") or ""
    variants = _tool_variants(tool_name, payload.get("tool_input"))
    reason = None
    for name, ti in variants:
        reason = forgery_reason(name, ti, payload.get("cwd"))
        if reason is not None:
            break
    hits = [
        Hit("fs_delete", ti["tool"], TIER_CONSENT) if name == _MALFORMED else hit
        for name, ti in variants
        for hit in ([None] if name == _MALFORMED else assess_all(name, ti))
    ]
    return reason, hits


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
    has_consent_fn=None,
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
    reason, hits = _gated(payload)
    if reason is not None:
        return (2, list(_FORGERY_MESSAGES[reason]))
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
    ledger = _ledger()  # may raise (G-03) — main() turns that into a DENY
    has_consent_fn = has_consent_fn or ledger.has_session_consent
    th = ledger.target_hash(hit.target)
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
                workspace, slug, session_id=session_id, action=hit.action,
                target_hash=th, max_age_seconds=_CONSENT_MAX_AGE_SECONDS,
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


_GATED_WORDS = _DELETE_TOKENS | _HTTP_TOKENS | {"git", "find", "rsync", "mv", "eval"}


def _names_gated_tool(payload) -> bool:
    """Whether the raw command text names any tool the gate classifies."""
    if not isinstance(payload, dict):
        return False
    ti = payload.get("tool_input")
    text = (ti.get("command") or ti.get("input")) if isinstance(ti, dict) else None
    if not isinstance(text, str):
        return False
    words = {w.rsplit("/", 1)[-1] for w in re.split(r"[\s;&|()`$\"']+", text) if w}
    return bool(words & _GATED_WORDS)


def main() -> int:
    """Read the PreToolUse stdin payload and emit the gate decision.

    Fail-OPEN on an internal error (unreadable stdin / a classify crash) because
    reaching that branch means NO gated action was confirmed — a gate bug must not
    brick non-gated work (mirrors validate_content_write.py). The gated decision is
    computed first and the deny code is returned even if message emission fails, so
    the gated path stays fail-CLOSED.
    """
    payload = None
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        reason, hits = _gated(payload) if isinstance(payload, dict) else (None, [])
        critical = reason is not None or any(h.tier == TIER_CONSENT for h in hits)
    except Exception as exc:
        # A parser crash on a command that names a gated tool must not become an
        # ALLOW for whatever is chained after it (review #1); anything else stays
        # fail-open so a gate bug never bricks plain work.
        if _names_gated_tool(payload):
            _emit(f"BLOCKED: komut çözümlenemedi ({exc!r}) — güvenli tarafta reddedildi")
            return 2
        _emit(f"WARNING internal error, allowing (fail-open): {exc!r}")
        return 0
    try:
        code, messages = evaluate(payload)
    except Exception as exc:
        # G-03: once a consent-tier action is CONFIRMED, any failure (a missing
        # jsonschema, an unreadable ledger) denies — exit 1 would mean ALLOW.
        if critical:
            _emit(f"BLOCKED: onay doğrulanamadı ({exc!r}) — güvenli tarafta reddedildi")
            return 2
        _emit(f"WARNING internal error, allowing (fail-open): {exc!r}")
        return 0
    for message in messages:
        _emit(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
