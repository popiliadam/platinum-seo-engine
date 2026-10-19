"""Thin, idempotent commit wrapper over ``scripts.excel.transaction.replace``.

The orchestrator owns exactly ONE commit path so batch 1b2 can point the 3
reference skills at it. We use ``replace()``, NOT ``append()``: replace clears
the sheet's data block (from the schema's ``data_start_row`` down) then writes
``rows``, preserving the header block — so re-running the same step never
duplicates rows. That whole-block replace IS the "idempotent resume keyed on
run_id/window" the spec wants for a snapshot workflow, and it also fixes the known
GSC snapshot-duplicate bug (the reference skills are rewired here in batch 1b2).
"""
from __future__ import annotations

from pathlib import Path

from scripts.excel import transaction
from scripts.excel.transaction import WriteResult


class EmptyCommitError(ValueError):
    """A 0-row commit was refused: ``replace`` would silently empty the sheet."""


def commit(
    workbook_path: Path | str,
    sheet: str,
    rows: list[dict],
    *,
    run_id: str,
    project_slug: str,
    schema_path: Path | str | None = None,
    state_root: Path | str | None = None,
    writer: str = "orchestrator",
    allow_empty: bool = False,
) -> WriteResult:
    """Idempotently commit ``rows`` to ``sheet`` via ``transaction.replace``.

    ``run_id`` is accepted for the caller's provenance/log intent and to make the
    one orchestrator commit path self-documenting; ``transaction.replace`` has no
    run_id parameter (the whole-block replace is itself the idempotency), so it is
    not threaded further. Returns the transaction ``WriteResult`` unchanged —
    ``WriteResult.rows_affected`` is the step's scored_count.

    An empty ``rows`` raises ``EmptyCommitError`` BEFORE the workbook is touched
    unless the caller passes ``allow_empty=True`` (V-01): ``replace`` clears the
    data block first, so an empty upstream result would otherwise erase the sheet.
    """
    if not rows and not allow_empty:
        raise EmptyCommitError(
            f"refusing to replace sheet {sheet!r} with 0 rows (run {run_id}); "
            f"pass allow_empty=True if an empty sheet is the intended result"
        )
    return transaction.replace(
        workbook_path,
        sheet,
        rows,
        project_slug,
        schema_path=schema_path,
        state_root=state_root,
        writer=writer,
    )
