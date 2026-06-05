#!/usr/bin/env python3
"""sf_import.py — Implementation of the sf-import skill CLI protocol.

A deterministic CLI (NOT a workflow_runner run shell). Stages of main(argv),
as described in skills/ingestion/sf-import/SKILL.md:
A. workspace/path resolution — DURUR #5 (exit 5)
B. validate_export_path — raw/ subfolder discovery — DURUR #1 (exit 1)
C. validate_tier1 — 14/14 required reports + filename normalization
   (match_tiers, defined here) — DURUR #2 (exit 2)
D. envelope_inbox — sha256 + tier mapping → inbox/sf/{date}-{slug}.json
   (master.xlsx existence check → DURUR #6, exit 6)
E. sitemap_xcheck — Phase-X DEFERRED (not wired; no mcp__gsc__list_sitemaps
   call, no sf_sitemap_xcheck module)
F. write_excel + provenance — 6-sheet projection via transaction.replace
   (idempotent refresh) + events_writer.append_provenance(source.kind=sf_csv)
G. complete — stdout summary + return 0 (no workflow_runner, no outputs dict)

Plugin-agnostic: project_slug + sf_export_path required, no slug literals.

CLI:
    python3 -m scripts.ingestion.sf_import \
        --project bigcat-tr \
        --sf-export-path projects/bigcat-tr/sf-exports/2026-05-07/

Authority: skills/ingestion/sf-import/SKILL.md (DURUR conditions enforced).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module or imported in tests.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.excel import transaction  # noqa: E402
from scripts.ingestion import sf_projection  # noqa: E402
from scripts.state import events_writer  # noqa: E402


# Tier registry (mirrors schemas/sf-required-reports.schema.json)
TIER1_REQUIRED = frozenset({
    "internal_all", "all_inlinks", "all_outlinks", "response_codes_all",
    "issues_overview_report", "page_titles_all", "meta_description_all",
    "h1_all", "canonicals_all", "directives_all", "indexability",
    "structured_data_all", "sitemaps_all", "redirect_chains",
})
TIER2_RECOMMENDED = frozenset({
    "h2_all", "images_all", "hreflang_all", "orphan_pages",
    "all_anchor_text", "near_duplicates_report", "exact_duplicates_report",
    "search_console_all", "crawl_depth", "pagination_all",
})


class FileMatch(NamedTuple):
    canonical_name: str
    tier: str
    filename_original: str
    filename_normalized: str
    sha256: str
    row_count: int


class SFImportError(Exception):
    """Top-level error for sf_import failures (DURUR triggers)."""


def normalize_filename(name: str) -> str:
    """Skill protocol filename normalization rules (in order):
    1. Lowercase basename. 2. Drop .csv extension.
    3. Strip locale shadow `de_`. 4. Strip mode prefix `v_` / `p_` / `bi_`.
    5. Fold Turkish dotless `ı` → ASCII `i`. 6. Drop `(N)` and `-copy/_old` suffix.
    """
    n = name.lower()
    if n.endswith(".csv"):
        n = n[:-4]
    for prefix in ("de_", "v_", "p_", "bi_"):
        if n.startswith(prefix):
            n = n[len(prefix):]
    n = n.replace("ı", "i")
    # Drop (N) suffix
    import re as _re
    n = _re.sub(r"\(\d+\)$", "", n)
    for suf in ("-copy", "_old"):
        if n.endswith(suf):
            n = n[:-len(suf)]
    return n


def match_tiers(raw_dir: Path) -> tuple[list[FileMatch], set[str], set[str]]:
    """Walk raw/, normalize names, match canonical names.

    Returns (matched, missing_t1, missing_t2). Ambiguous matches abort.
    """
    if not raw_dir.is_dir():
        raise SFImportError(f"raw_dir not a directory: {raw_dir}")

    matched: list[FileMatch] = []
    seen_canonicals: dict[str, str] = {}  # canonical → original filename

    for path in sorted(raw_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".csv"):
            continue
        canonical = normalize_filename(path.name)
        if canonical in seen_canonicals:
            raise SFImportError(
                f"Ambiguous match: {seen_canonicals[canonical]} and {path.name} "
                f"both normalize to '{canonical}'"
            )
        seen_canonicals[canonical] = path.name

        if canonical in TIER1_REQUIRED:
            tier = "required"
        elif canonical in TIER2_RECOMMENDED:
            tier = "recommended"
        else:
            tier = "optional"

        with open(path, "rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()
        with open(path, "r", encoding="utf-8") as f:
            row_count = max(0, sum(1 for _ in f) - 1)

        matched.append(FileMatch(
            canonical_name=canonical,
            tier=tier,
            filename_original=path.name,
            filename_normalized=f"{canonical}.csv",
            sha256=sha,
            row_count=row_count,
        ))

    found_canonicals = {m.canonical_name for m in matched}
    missing_t1 = TIER1_REQUIRED - found_canonicals
    missing_t2 = TIER2_RECOMMENDED - found_canonicals
    return matched, missing_t1, missing_t2


def build_envelope(
    project_slug: str,
    sf_root: Path,
    raw_dir: Path,
    matched: list[FileMatch],
    amber_warnings: list[str],
    workspace_root: Path,
) -> Path:
    """Step 4: write inbox/sf/{date}-{slug}.json before any projection."""
    today = datetime.date.today().isoformat()
    inbox_path = (
        workspace_root / "projects" / project_slug
        / "inbox" / "sf" / f"{today}-{project_slug}.json"
    )
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "_meta": {
            "captured_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": "screaming_frog",
            "project_slug": project_slug,
            "sf_export_path": str(sf_root.relative_to(workspace_root) if sf_root.is_absolute() else sf_root),
            "raw_dir": str(raw_dir.relative_to(workspace_root) if raw_dir.is_absolute() else raw_dir),
            "amber_warnings": amber_warnings,
        },
        "files": [
            {
                "canonical_name": m.canonical_name,
                "tier": m.tier,
                "filename_original": m.filename_original,
                "filename_normalized": m.filename_normalized,
                "file_hash": f"sha256:{m.sha256}",
                "row_count": m.row_count,
            } for m in matched
        ],
    }
    inbox_path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return inbox_path


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    """Path relative to workspace_root as a POSIX string; absolute string when
    the path is not under workspace_root (defensive — mirrors build_envelope).

    The Step 7 ``source.source_folder`` is documented as the ingest folder
    relative to the workspace root; in production raw_dir lives under it. We
    never crash on an out-of-tree path (e.g. a test pointing at a real export
    dir) — we fall back to the absolute string instead.
    """
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return str(path)


def project_and_write(
    raw_dir: Path,
    master_xlsx: Path,
    project_slug: str,
    *,
    workspace_root: Path,
) -> dict[str, int]:
    """Step 6+7: project the six SF sheets and replace them in master.xlsx
    (idempotent), then emit one ``sf_csv`` source-provenance event.

    Step 6 — ``sf_projection.project_all`` yields the six schema-valid sheet
    row lists; each is written via ``transaction.replace`` (clears the sheet's
    data block, then re-lands the rows), so re-running this refreshes rather
    than duplicates. ``replace`` itself emits a ``tool_computed`` provenance
    event per sheet.

    Step 7 — a single ``sf_csv`` source-provenance event records the data
    lineage (``sf_csv → tool_computed``): ``source.source_folder`` is the raw
    dir relative to the workspace root, ``source.row_count`` and
    ``rows_written`` are the total rows projected.

    Errors propagate (DURUR): a ``RowSchemaError`` from an invalid projected
    row, or any ``transaction``/``events_writer`` failure, is NOT swallowed.

    Args:
        raw_dir: the SF crawl's ``.../raw/`` export directory.
        master_xlsx: the project's master.xlsx (written via the approved path).
        project_slug: project_id (plugin-agnostic; no slug literals here).
        workspace_root: the workspace root (for the events.jsonl path + the
            relative ``source_folder``).

    Returns:
        ``{sheet: rows_written}`` for the six projected sheets, in projection
        key order.
    """
    projections = sf_projection.project_all(Path(raw_dir))

    counts: dict[str, int] = {}
    for sheet, rows in projections.items():
        result = transaction.replace(
            master_xlsx,
            sheet,
            rows,
            project_slug,
            writer="sf-import",
        )
        counts[sheet] = result.rows_affected

    total_rows = sum(counts.values())
    # run_id auto-allocated race-free under the append flock (P1-11) — the prior
    # next_run_id() then append_provenance() two-step could collide concurrently.
    events_writer.append_provenance(
        project_id=project_slug,
        source={
            "kind": "sf_csv",
            "source_folder": _rel_to_workspace(Path(raw_dir), workspace_root),
            "row_count": total_rows,
        },
        operation="ingest",
        rows_written=total_rows,
        workspace_root=workspace_root,
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Implement sf-import skill protocol.")
    p.add_argument("--project", required=True, help="project_slug (lowercase kebab)")
    p.add_argument("--sf-export-path", required=True,
                   help="path to sf-exports/{date}/ directory (raw/ subfolder enforced)")
    p.add_argument("--workspace-root", default=os.environ.get("PSEO_WORKSPACE_ROOT"),
                   help="defaults to $PSEO_WORKSPACE_ROOT")
    p.add_argument("--dry-run", action="store_true", help="validate + envelope only; skip Excel write")
    args = p.parse_args(argv)

    if not args.workspace_root:
        print("ERROR: --workspace-root or PSEO_WORKSPACE_ROOT required (DURUR #5)", file=sys.stderr)
        return 5
    workspace_root = Path(args.workspace_root)
    sf_root = Path(args.sf_export_path)
    if not sf_root.is_absolute():
        sf_root = workspace_root / sf_root

    # Step 2 — validate_export_path
    raw_dir = sf_root / "raw" if (sf_root / "raw").is_dir() else sf_root
    if not raw_dir.is_dir():
        print(f"ERROR: raw_dir not found at {sf_root} or {sf_root}/raw (DURUR #1)", file=sys.stderr)
        return 1

    # Step 3 — validate_tier1
    matched, missing_t1, missing_t2 = match_tiers(raw_dir)
    if missing_t1:
        print(f"ERROR: Tier 1 missing: {sorted(missing_t1)} (DURUR #2)", file=sys.stderr)
        return 2

    amber: list[str] = []
    if missing_t2:
        amber.append(f"Tier 2 missing (AMBER): {sorted(missing_t2)}")

    # Step 4 — envelope_inbox
    master_xlsx = workspace_root / "projects" / args.project / "master.xlsx"
    if not master_xlsx.exists():
        print(f"ERROR: master.xlsx missing at {master_xlsx} (DURUR #6)", file=sys.stderr)
        return 6

    inbox_path = build_envelope(args.project, sf_root, raw_dir, matched, amber, workspace_root)

    print(f"OK: matched {len(matched)} files (Tier1 {len(TIER1_REQUIRED & {m.canonical_name for m in matched})}/14, "
          f"Tier2 {len(TIER2_RECOMMENDED & {m.canonical_name for m in matched})}/10)")
    print(f"Envelope: {inbox_path}")
    if amber:
        for w in amber:
            print(f"WARN: {w}")

    if args.dry_run:
        print("DRY-RUN: skipping Excel projection.")
        return 0

    # Step 6/7 — per-sheet projection (idempotent replace) + sf_csv provenance.
    # project_and_write raises on any projection / write / event failure (DURUR);
    # we do not catch — a RowSchemaError must surface as a non-zero exit.
    counts = project_and_write(
        raw_dir, master_xlsx, args.project, workspace_root=workspace_root
    )
    for sheet, n in counts.items():
        print(f"OK: {sheet} ← {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
