#!/usr/bin/env python3
"""
render_template.py — minimal $variable substitution for Markdown templates.

Usage:
    render_template.py <template.md> <data.json>

Uses string.Template ($key / ${key}) — stdlib only. Phase 9 reporting will
upgrade to jinja2 if conditionals/loops become necessary.

DIALECT BOUNDARY (P2-03): this renderer owns the ``string.Template`` family
declared in ``templates/manifest.json`` (the ``templates/reports/`` *.template.md
files). It does NOT understand ``{{PLACEHOLDER}}`` double-brace tokens — those
belong to the content-generation skills and would be left verbatim here. The
dialect-per-family contract is enforced by tests/reporting/test_template_dialect.py.

Exit 0 success; exit 1 on missing file, malformed JSON, or unknown $key.
Output goes to stdout; errors to stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from string import Template


def _die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        _die("usage: render_template.py <template.md> <data.json>")

    tpl_path, data_path = Path(argv[1]), Path(argv[2])
    if not tpl_path.exists():
        _die(f"template not found: {tpl_path}")
    if not data_path.exists():
        _die(f"data file not found: {data_path}")

    template_text = tpl_path.read_text(encoding="utf-8")
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _die(f"invalid JSON in {data_path}: {exc.msg} (line {exc.lineno})")
    if not isinstance(data, dict):
        _die("data JSON must be an object at the top level")

    try:
        rendered = Template(template_text).substitute({k: str(v) for k, v in data.items()})
    except KeyError as exc:
        _die(f"missing key in data: {exc.args[0]}")
    except ValueError as exc:
        _die(f"template syntax error: {exc}")

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
