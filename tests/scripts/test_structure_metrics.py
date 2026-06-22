"""Tests for scripts/production/structure_metrics.py — the SINGLE source of
truth for CCE "meaningful structure" thresholds (B4 cross-batch alignment).

Background: B1 (competitor_recon_transform) counted COMPETITOR lists at ≥3 <li>
while B2 (quality_gates) counted OUR lists at ≥2 <li> — an asymmetric threshold
that let our content clear the structure gate against a competitor ceiling
measured more strictly (it flattered us, breaking the "beat the competitor"
guarantee, spec §9). structure_metrics centralises the thresholds so B1 and B2
measure identically. Table thresholds were already aligned (≥2 rows × ≥2 cols);
the list threshold is unified to ≥3.
"""

from __future__ import annotations

from scripts.production import competitor_recon_transform as cr
from scripts.production import quality_gates as qg
from scripts.production import structure_metrics as sm


def test_canonical_threshold_values():
    assert sm.MIN_TABLE_ROWS == 2
    assert sm.MIN_TABLE_COLS == 2
    # Aligned to B1's competitor count; B2's old ≥2 is pulled up to this.
    assert sm.MIN_LIST_ITEMS == 3


def test_competitor_recon_uses_canonical_thresholds():
    # B1 imports the canonical constants — no private redefinition (single source).
    assert cr.MIN_TABLE_ROWS == sm.MIN_TABLE_ROWS
    assert cr.MIN_TABLE_COLS == sm.MIN_TABLE_COLS
    assert cr.MIN_LIST_ITEMS == sm.MIN_LIST_ITEMS


def test_quality_gates_uses_canonical_thresholds():
    # B2 imports the same canonical constants.
    assert qg.MIN_TABLE_ROWS == sm.MIN_TABLE_ROWS
    assert qg.MIN_TABLE_COLS == sm.MIN_TABLE_COLS
    assert qg.MIN_LIST_ITEMS == sm.MIN_LIST_ITEMS
