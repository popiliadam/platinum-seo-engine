"""
sheet_merge.py — idempotent, namespace-scoped row merge into a master.xlsx sheet.

Several writers share ``robots_txt`` / ``redirect_404``: sf-import projects its
SF rows there, and the tech-SEO governance skills (hreflang-audit /
facet-nav-audit / robots-policy-audit / migration-map) add COMPUTED findings to
the same sheets. Each must refresh ONLY its own rows — no duplication on re-run,
no clobbering of sf_projection's ``R-NNN`` rows or each other's ``HF-`` / ``FN-``
/ ``RP-`` rows.

Every call goes through ``transaction.merge``: the current sheet is read, the
caller's own namespace dropped, the caller's new rows added, and the union
written back — all under ONE excel.lock hold (V-03), so two skills merging at
the same time can never base their write on the same stale snapshot. The lock is
taken with ``acquire_blocking=True``: a concurrent writer waits its turn instead
of failing.

Three functions:
  - ``merge_prefixed_rows`` — id-namespaced sheets (``robots_txt``): generates
    sequential ids ``f"{id_prefix}{seq:03d}"`` for the new rows.
  - ``merge_keyed_rows``   — keyed sheets without an id column (``redirect_404``):
    replaces rows whose ``key_column`` value matches a new row's key.
  - ``replace_owned_rows`` — a writer whose rows carry no id (sf-import's
    ``redirect_404``): drops the rows ``owns`` claims, keeps everyone else's, adds
    the new rows except where another writer already holds that key.

Discipline (mirrors sf_projection / tech_audit_transform):
  - No slug literals; never mutates the caller's row dicts (new dicts only).
  - Schema validation + lock + backup are transaction.merge's job — RowSchemaError
    / SchemaSheetMismatchError / LockTimeout / EmptyMergeError propagate unchanged.
  - Append-only state preserved: transaction.merge emits the provenance event.

Refs: scripts/excel/transaction.py (merge + exceptions + data_start_row),
schemas/master-excel.schema.json (sheet shapes), scripts/ingestion/sf_projection.py
(the R-NNN rows this merge preserves), rules/tech-seo-governance.md (R-125..R-136).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# scripts is a namespace package; ensure repo root on sys.path for absolute imports.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.excel import transaction  # noqa: E402
from scripts.excel.transaction import WriteResult  # noqa: E402


def _merge(
    xlsx_path: Path | str,
    sheet: str,
    fn: Callable[[list[dict]], list[dict]],
    *,
    project_slug: str,
    writer: str,
    schema_path: Path | str | None,
    state_root: Path | str | None,
) -> WriteResult:
    return transaction.merge(
        xlsx_path, sheet, fn, project_slug,
        schema_path=schema_path, state_root=state_root, writer=writer,
        acquire_blocking=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_prefixed_rows(
    xlsx_path: Path | str,
    sheet: str,
    new_rows: list[dict],
    *,
    id_prefix: str,
    id_column: str = "id",
    run_id: str,
    project_slug: str,
    writer: str,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
) -> WriteResult:
    """Idempotently merge ``new_rows`` into an id-namespaced ``sheet``.

    Drops every current row whose ``id_column`` value starts with ``id_prefix``
    (the caller's own namespace), assigns the new rows sequential ids
    ``f"{id_prefix}{seq:03d}"`` (seq from 1), and re-lands the union (foreign
    rows + freshly-id'd new rows). Re-running with the same ``new_rows``
    reproduces the same ids → no duplication, no foreign-row loss. ``run_id`` is
    accepted for the caller's provenance intent. Caller dicts are never mutated.
    """
    renumbered = [
        {**row, id_column: f"{id_prefix}{seq:03d}"}
        for seq, row in enumerate(new_rows, start=1)
    ]

    def union(existing: list[dict]) -> list[dict]:
        kept = [
            row for row in existing
            if not str(row.get(id_column) or "").startswith(id_prefix)
        ]
        return kept + renumbered

    return _merge(
        xlsx_path, sheet, union, project_slug=project_slug, writer=writer,
        schema_path=schema_path, state_root=state_root,
    )


def merge_keyed_rows(
    xlsx_path: Path | str,
    sheet: str,
    new_rows: list[dict],
    *,
    key_column: str = "url",
    run_id: str,
    project_slug: str,
    writer: str,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
) -> WriteResult:
    """Idempotently merge ``new_rows`` into a keyed ``sheet`` with no id column.

    For sheets like ``redirect_404`` (key = ``url``): drops every current row
    whose ``key_column`` value matches a key present in ``new_rows``, keeps the
    rest, appends ``new_rows`` verbatim. Re-running replaces the same keys in
    place (idempotent). Caller dicts are never mutated.
    """
    new_keys = {row.get(key_column) for row in new_rows}
    fresh = [dict(row) for row in new_rows]

    def union(existing: list[dict]) -> list[dict]:
        return [row for row in existing if row.get(key_column) not in new_keys] + fresh

    return _merge(
        xlsx_path, sheet, union, project_slug=project_slug, writer=writer,
        schema_path=schema_path, state_root=state_root,
    )


def replace_owned_rows(
    xlsx_path: Path | str,
    sheet: str,
    new_rows: list[dict],
    *,
    owns: Callable[[dict], bool],
    key_column: str = "url",
    run_id: str,
    project_slug: str,
    writer: str,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
) -> WriteResult:
    """Refresh the caller's rows in ``sheet`` when they carry no id namespace.

    Drops every current row ``owns`` claims (the caller's previous snapshot),
    keeps all other writers' rows, and adds ``new_rows`` — except a new row whose
    ``key_column`` value another writer's kept row already holds (that writer's
    plan for the key wins; no duplicate key is created). Caller dicts are never
    mutated.
    """
    fresh = [dict(row) for row in new_rows]

    def union(existing: list[dict]) -> list[dict]:
        kept = [row for row in existing if not owns(row)]
        held = {row.get(key_column) for row in kept}
        return kept + [row for row in fresh if row.get(key_column) not in held]

    return _merge(
        xlsx_path, sheet, union, project_slug=project_slug, writer=writer,
        schema_path=schema_path, state_root=state_root,
    )


__all__ = ("merge_prefixed_rows", "merge_keyed_rows", "replace_owned_rows")
