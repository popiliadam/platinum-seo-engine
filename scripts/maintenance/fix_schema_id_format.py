"""Fix schema $id format per ADR-012 + naming.md.

Pattern: http://platinum-seo-engine/schemas/<slug>
- HTTP (not HTTPS) — ADR-012 history-stable URI
- /schemas/ path (file location authoritative)
- slug-only (no .schema.json suffix)

Idempotent: running twice with --apply makes no change after first apply.
Adds $id where missing (e.g., master-excel.schema.json) — inserted after $schema line.

Source authority: rules/naming.md, ADR-012 (DECISIONS_ARCHIVE.md).
Brief: docs/superpowers/plans/v1.4-deep-audit-fix-brief.md Tier 1 Step 2.
Audit: docs/audits/v1.4-rules-schemas-templates-2026-05-07.md K-02 + K-03.

Implementation note: uses line-based regex replacement (NOT json parse+rewrite)
to preserve existing compact-inline formatting (e.g., `"required": ["a", "b"]`
on a single line, `"const": "1.0"` inline). A json.dumps round-trip would
expand these and produce massive diff noise unrelated to the $id change.

Usage:
    python3 scripts/maintenance/fix_schema_id_format.py --dry-run
    python3 scripts/maintenance/fix_schema_id_format.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

SLUG_PATTERN = re.compile(r"^([a-z][a-z0-9-]*)\.(?:schema\.)?json$")
ID_PREFIX = "http://platinum-seo-engine/schemas/"

# Existing $id line: "$id": "<scheme>://platinum-seo-engine/(schemas|templates)/<slug>(.schema.json)?"
ID_LINE_RE = re.compile(
    r'("\$id":\s*")(https?)://platinum-seo-engine/(?:schemas|templates)/([a-z][a-z0-9-]+)(?:\.schema\.json)?(")'
)
# $schema line for inserting $id when missing.
SCHEMA_LINE_RE = re.compile(r'^(\s*)"\$schema":\s*"[^"]+",?\s*$')


def expected_id(filename: str) -> str:
    m = SLUG_PATTERN.match(filename)
    if not m:
        raise ValueError(f"Unexpected schema filename: {filename}")
    return f"{ID_PREFIX}{m.group(1)}"


def transform(content: str, filename: str) -> tuple[str, str | None, str]:
    """Return (new_content, current_id, expected_id_value).

    If $id exists: regex-replace HTTPS→HTTP + path + suffix.
    If $id missing: insert new line after the first $schema line, indented to match.
    """
    expected = expected_id(filename)
    expected_id_value = ID_PREFIX + SLUG_PATTERN.match(filename).group(1)

    m = ID_LINE_RE.search(content)
    if m:
        current = f"{m.group(2)}://platinum-seo-engine/.../{m.group(3)}"  # display only
        new_id_line = f'{m.group(1)}{expected_id_value}{m.group(4)}'
        new_content = ID_LINE_RE.sub(new_id_line, content, count=1)
        return (new_content, current, expected_id_value)

    # No $id present — insert after $schema line (preserve indent + trailing comma).
    lines = content.splitlines(keepends=True)
    out_lines: list[str] = []
    inserted = False
    for line in lines:
        out_lines.append(line)
        if not inserted:
            sm = SCHEMA_LINE_RE.match(line)
            if sm:
                indent = sm.group(1)
                # Match insertion newline style of the matched line.
                eol = "\n" if line.endswith("\n") else ""
                out_lines.append(f'{indent}"$id": "{expected_id_value}",{eol}')
                inserted = True
    if not inserted:
        return (content, None, expected_id_value)  # No $schema line; cannot safely insert.
    return ("".join(out_lines), None, expected_id_value)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes to disk")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args(argv)
    if not (args.apply or args.dry_run):
        parser.error("--apply or --dry-run required")

    changed = 0
    for schema_path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        try:
            content = schema_path.read_text()
        except OSError as e:
            print(f"SKIP {schema_path.name}: {e}", file=sys.stderr)
            continue
        try:
            new_content, current, expected = transform(content, schema_path.name)
        except ValueError as e:
            print(f"SKIP {schema_path.name}: {e}", file=sys.stderr)
            continue
        if new_content == content:
            continue
        changed += 1
        verb = "APPLY" if args.apply else "DRY-RUN"
        print(f"{verb} {schema_path.name}: {current or 'MISSING'} → {expected}")
        if args.apply:
            schema_path.write_text(new_content)

    print(f"\nTotal changes: {changed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
