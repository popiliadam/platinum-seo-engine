"""D-17 — one documented number parser (Turkish thousands, one rounding rule)."""
from __future__ import annotations

import pytest

from scripts.planning import master_task_sync as mts
from scripts.util.coerce import to_float, to_int


@pytest.mark.parametrize("raw, expected", [
    ("5.400", 5400), ("5,400", 5400), ("1.234.567", 1234567), ("5.400,5", 5400.5),
    ("5,400.5", 5400.5), ("12.7", 12.7), ("5,4", 5.4), ("%12", None), ("12%", 12.0),
    ("", None), (None, None), (True, None), ("abc", None), (3, 3.0),
])
def test_to_float(raw, expected) -> None:
    assert to_float(raw) == expected


def test_to_int_truncates_and_defaults() -> None:
    assert to_int("12.7") == 12 and to_int(12.7) == 12
    assert to_int("5.400") == 5400
    assert to_int("x", default=0) == 0


def test_master_task_sync_reads_turkish_thousands() -> None:
    assert mts._to_int("5.400") == 5400
