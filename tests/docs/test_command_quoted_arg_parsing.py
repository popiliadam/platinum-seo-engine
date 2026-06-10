"""Batch-E finding 13 (FINALIZED) — slash-command arg parsing must survive
quoted paths UNDER TEXT SUBSTITUTION (the real Claude Code mechanism).

Claude Code TEXT-SUBSTITUTES the literal ``$ARGUMENTS`` token into a command's
``!`…`` preload block source *before* the shell runs it. It does NOT export an
``ARGUMENTS`` environment variable, and it does NOT set ``$1/$2/$3`` inside the
block. Consequences (all empirically reproduced, 2026-06-10):

  * ``python3 -m … approve "$ARGUMENTS"`` (double-quoted) — the user's own
    quote characters are substituted *inside* the outer quote, so the shell
    mis-tokenizes them. This is the live production failure:
    ``/pseo-approve … "origin main"`` → "unknown action 'origin main'" and a
    quoted ``"/tmp/My Dir/x.xml"`` recorded as ``/tmp/My``.
  * the ``eval "set -- $(python3 -c 'shlex …' "$ARGUMENTS")"`` idiom (commit
    ef7f658's "provisional/UNVERIFIED" successor) parses correctly ONLY if
    ``$ARGUMENTS`` is an env VAR; under text substitution its nested quotes
    corrupt the tokens the same way.

The robust fix forwards ``$ARGUMENTS`` **UNQUOTED** straight to the module's
argparse. bash/sh/zsh tokenize the substituted source honouring the user's own
quotes, so a quoted target / ``--workspace`` path arrives as ONE argv item and
argparse (run_id/action/target ; slug + ``--workspace``) is the parser. An
UNQUOTED multiword target surfaces loudly as argparse "unrecognized arguments"
instead of silently truncating.

These tests MODEL TEXT SUBSTITUTION (substitute the literal token, no env var).
The previous version of this file modelled env-var passing, so it passed while
production failed — the D11 inherited-contract-error lesson made executable.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

# The two commands whose arguments can carry a path/target containing spaces.
# (command file, python module, argparse subcommand)
_FORWARDERS = [
    ("pseo-approve.md", "scripts.state.consent_ledger", "approve"),
    ("pseo-bind.md", "scripts.state.session_binding", "bind"),
]
_NAMES = [n for n, _, _ in _FORWARDERS]


def _text(name: str) -> str:
    return (_ROOT / "commands" / name).read_text(encoding="utf-8")


def _bang_blocks(text: str) -> list[str]:
    """Bodies of every ``!`…`` preload block (block bodies carry no backtick)."""
    return re.findall(r"!`([^`]+)`", text)


def _exec_block(name: str, module: str, sub: str) -> str:
    """The block that invokes ``python3 -m <module> <sub> …``."""
    for body in _bang_blocks(_text(name)):
        if f"-m {module} {sub}" in body:
            return body
    raise AssertionError(f"{name}: no !`…` block invoking -m {module} {sub}")


# --- static: the command bodies use the robust idiom, not the broken ones ----

@pytest.mark.parametrize("name,module,sub", _FORWARDERS)
def test_forwards_arguments_unquoted_to_argparse(name: str, module: str, sub: str) -> None:
    block = _exec_block(name, module, sub)
    assert f"-m {module} {sub} $ARGUMENTS" in block, (
        f"{name} must forward $ARGUMENTS UNQUOTED to argparse — text "
        f"substitution makes bash honour the user's quotes; argparse is the "
        f"parser. Found: {block!r}"
    )


@pytest.mark.parametrize("name", _NAMES)
def test_no_eval_set_reparse(name: str) -> None:
    text = _text(name)
    assert 'eval "set --' not in text, (
        f"{name} still uses the eval+shlex reparse — correct only for env-var "
        f"passing, corrupts quoted args under text substitution (finding #13)"
    )


@pytest.mark.parametrize("name,module,sub", _FORWARDERS)
def test_no_double_quoted_or_resplit_forward(name: str, module: str, sub: str) -> None:
    block = _exec_block(name, module, sub)
    assert f'{sub} "$ARGUMENTS"' not in block, (
        f"{name} double-quotes $ARGUMENTS — under text substitution the user's "
        f"quotes land inside the outer quote and mis-tokenize"
    )
    for bad in ('"$1"', '"$2"', '"$3"', '"${2:-}"', '"${3:-}"'):
        assert bad not in block, (
            f"{name} re-forwards positional {bad} — Claude Code does not set "
            f"$1/$2/$3 in !`…` blocks; forward $ARGUMENTS to argparse instead"
        )


# --- behavioural: the idiom parses quoted paths under TEXT SUBSTITUTION -------

def _parse_textsub(argstr: str, shell: str = "bash") -> list[str]:
    """Simulate Claude Code text-substituting the literal ``$ARGUMENTS`` token
    into the forward idiom, then running it. Returns the argv the CLI receives.

    NOTE: ``$ARGUMENTS`` is substituted into the SOURCE (no env var), exactly as
    the harness does — the user's quotes become real shell quotes.
    """
    idiom = 'python3 -c "import sys,json;print(json.dumps(sys.argv[1:]))" $ARGUMENTS'
    src = idiom.replace("$ARGUMENTS", argstr)
    out = subprocess.run(
        [shell, "-c", src],
        env={"PATH": os.environ["PATH"]},
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


@pytest.mark.skipif(not shutil.which("python3"), reason="python3 required")
@pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
def test_unquoted_textsub_parses_quoted_path(shell: str) -> None:
    if not shutil.which(shell):
        pytest.skip(f"{shell} not available")
    # consent target with spaces
    assert _parse_textsub('r1 index_update "/tmp/My Dir/x.xml"', shell) == [
        "r1", "index_update", "/tmp/My Dir/x.xml",
    ]
    # --workspace path with spaces
    assert _parse_textsub('demo-furniture --workspace "/tmp/My Dir"', shell) == [
        "demo-furniture", "--workspace", "/tmp/My Dir",
    ]
    # simple single slug
    assert _parse_textsub("demo-furniture", shell) == ["demo-furniture"]
    # empty → no positionals (the MISSING_* preflight still fires)
    assert _parse_textsub("", shell) == []


# --- end-to-end: the REAL approve block keeps a quoted target intact ----------

@pytest.mark.skipif(not shutil.which("python3"), reason="python3 required")
def test_real_approve_block_preserves_quoted_target_under_textsub(tmp_path: Path) -> None:
    """Run the actual pseo-approve !`…` execute block under text substitution
    against a throwaway workspace; the quoted multiword target must reach the
    consent ledger intact (the production symptom was a truncated target /
    "unknown action <leaked-target>"). Hermetic: HOME has no pseo config so the
    env workspace wins, and everything is written under tmp_path.
    """
    block = _exec_block("pseo-approve.md", "scripts.state.consent_ledger", "approve")
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    (home / ".config" / "pseo").mkdir(parents=True)  # exists but NO config.json
    (ws / "shared").mkdir(parents=True)
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "testproj"}), encoding="utf-8"
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "PSEO_WORKSPACE_ROOT": str(ws),
        "CLAUDE_PLUGIN_ROOT": str(_ROOT),
    }
    target = "/tmp/My Dir/sitemap.xml"  # < 48 chars → shown verbatim in banner
    src = block.replace("$ARGUMENTS", f'r1 git_push "{target}"')
    out = subprocess.run(["bash", "-c", src], env=env, capture_output=True, text=True)
    combined = out.stdout + out.stderr
    assert "unknown action" not in combined, (
        f"valid action leaked the target into the action slot: {combined!r}"
    )
    assert target in combined, f"quoted target was mangled under text-sub: {combined!r}"
    # Defence in depth: the persisted entry hashes the INTACT target.
    from scripts.state.consent_ledger import target_hash
    ledger = ws / "projects" / "testproj" / "_state" / "consent.jsonl"
    assert ledger.exists(), f"no consent ledger written: {combined!r}"
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["target_hash"] == target_hash(target)
