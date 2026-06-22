#!/usr/bin/env python3
"""
structure_metrics.py — the SINGLE source of truth for CCE "meaningful
structure" thresholds shared by the arming engine (B1) and the gate engine
(B2/B4).

Why this module exists (B4 cross-batch alignment):
    B1 (competitor_recon_transform) counts a COMPETITOR's lists as meaningful
    at ≥3 <li>; B2 (quality_gates) originally counted OUR lists at ≥2 <li>.
    That asymmetry quietly flattered our own content: the structure gate
    requires ``ours ≥ competitor_ceiling + 1``, so a looser threshold on our
    side let a 2-item list clear a bar measured at 3 on the competitor side —
    breaking the "beat the competitor" guarantee (spec §9 yapı matematiği).

    Centralising the thresholds here means B1 and B2 measure structure on the
    SAME ruler. Tables were already symmetric (≥2 rows × ≥2 cols); the list
    threshold is unified to ≥3.

A "meaningful" structure (the rules both engines enforce):
    - table: at least ``MIN_TABLE_ROWS`` rows AND ``MIN_TABLE_COLS`` columns
      (a one-row or one-column table is layout, not data).
    - list:  a <ul>/<ol> with at least ``MIN_LIST_ITEMS`` direct <li>
      (a 1-2 item list is rarely a genuine enumeration; each list is counted
      by its OWN direct <li> so a nested short list never inflates its parent).

Pure constants only — no logic, no imports, no side effects. Both B1 and B2
``from scripts.production.structure_metrics import ...`` these names so any
future tuning happens in exactly one place.

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§6 structure gate, §9 yapı matematiği).
"""

from __future__ import annotations

#: A table is "meaningful" iff it has at least this many rows AND columns.
MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2

#: A list is "meaningful" iff it has at least this many direct <li>.
#: Aligned with B1's competitor count; B2's earlier ≥2 is pulled up to this.
MIN_LIST_ITEMS = 3


__all__ = (
    "MIN_TABLE_ROWS",
    "MIN_TABLE_COLS",
    "MIN_LIST_ITEMS",
)
