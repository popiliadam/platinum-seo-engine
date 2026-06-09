"""Batch-E finding 13 — slash-command arg parsing must survive quoted paths.

Background: in a command `!`…`` block Claude Code exposes the args only as the
`$ARGUMENTS` string (it does NOT set `$1/$2/$3`). The provisional fix (commit
ef7f658) reparsed with `set -- $ARGUMENTS`, but that is broken two ways:
  * bash/sh: word-splits on IFS and does NO quote removal, so
    `approve r1 act "/tmp/My Dir/x"` → $3=`"/tmp/My`, $4=`Dir/x"`.
  * zsh: does not word-split unquoted at all → the whole string lands in $1.
Either way a quoted path argument (consent target, `--workspace <path>`) is
mangled — and pseo-bind even forwarded `$2 $3` UNQUOTED.

The robust, shell-agnostic, injection-safe fix is to reparse via Python's
shlex (quote-aware) and re-emit shlex-quoted tokens into `eval "set -- …"`:
shlex.quote guarantees every token is an inert shell literal, so `eval` can
neither word-split nor execute injected metacharacters. This test pins that
exact idiom into the path-taking commands and proves it parses quoted paths.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

# The canonical safe reparse idiom. Pasted verbatim into the command bodies.
SAFE_REPARSE = (
    'eval "set -- $(python3 -c '
    "'import shlex,sys;print(\" \".join(shlex.quote(a) for a in shlex.split(sys.argv[1])))'"
    ' "$ARGUMENTS")"'
)

# Commands whose arguments can contain a path/target with spaces.
PATH_ARG_COMMANDS = ("pseo-approve.md", "pseo-bind.md")


def _text(name: str) -> str:
    return (_ROOT / "commands" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PATH_ARG_COMMANDS)
def test_command_uses_safe_reparse_idiom(name: str) -> None:
    text = _text(name)
    assert SAFE_REPARSE in text, (
        f"{name} must reparse $ARGUMENTS via the quote-aware shlex idiom"
    )


@pytest.mark.parametrize("name", PATH_ARG_COMMANDS)
def test_command_dropped_unsafe_bare_reparse(name: str) -> None:
    text = _text(name)
    assert "set -- $ARGUMENTS" not in text, (
        f"{name} still uses the unsafe bare `set -- $ARGUMENTS` reparse, which "
        f"splits quoted paths"
    )


def test_pseo_bind_quotes_forwarded_positionals() -> None:
    text = _text("pseo-bind.md")
    assert 'bind "$1" $2 $3' not in text, "pseo-bind forwards $2 $3 UNQUOTED"
    assert 'bind "$1" "${2:-}" "${3:-}"' in text, (
        "pseo-bind must forward every positional quoted"
    )


# --- behavioural proof: the idiom parses quoted paths in real shells ---------

def _parse(argstr: str, shell: str = "bash") -> list[str]:
    """Run the safe reparse under `shell` and return the parsed positionals."""
    script = f'{SAFE_REPARSE}; for a in "$@"; do printf "%s\\n" "$a"; done'
    out = subprocess.run(
        [shell, "-c", script],
        env={"ARGUMENTS": argstr, "PATH": __import__("os").environ["PATH"]},
        capture_output=True, text=True, check=True,
    )
    return out.stdout.splitlines()


@pytest.mark.skipif(not shutil.which("python3"), reason="python3 required")
@pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
def test_idiom_parses_quoted_path(shell: str) -> None:
    if not shutil.which(shell):
        pytest.skip(f"{shell} not available")
    # consent target with spaces
    assert _parse('r1 index_update "/tmp/My Dir/x.xml"', shell) == [
        "r1", "index_update", "/tmp/My Dir/x.xml",
    ]
    # --workspace path with spaces
    assert _parse('demo-furniture --workspace "/tmp/My Dir"', shell) == [
        "demo-furniture", "--workspace", "/tmp/My Dir",
    ]
    # simple single slug
    assert _parse("demo-furniture", shell) == ["demo-furniture"]
    # empty → no positionals (the MISSING_* branch still fires)
    assert _parse("", shell) == []
