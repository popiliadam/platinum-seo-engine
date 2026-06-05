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
) -> WriteResult:
    """Idempotently commit ``rows`` to ``sheet`` via ``transaction.replace``.

    ``run_id`` is accepted for the caller's provenance/log intent and to make the
    one orchestrator commit path self-documenting; ``transaction.replace`` has no
    run_id parameter (the whole-block replace is itself the idempotency), so it is
    not threaded further. Returns the transaction ``WriteResult`` unchanged —
    ``WriteResult.rows_affected`` is the step's scored_count.
    """
    return transaction.replace(
        workbook_path,
        sheet,
        rows,
        project_slug,
        schema_path=schema_path,
        state_root=state_root,
        writer=writer,
    )
