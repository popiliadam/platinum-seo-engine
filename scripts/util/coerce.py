#!/usr/bin/env python3
"""coerce.py — one documented number parser for sheet and API cells (D-17).

There were 18 private ``_safe_int`` copies with 7 behaviours: "12.7" became 0
in one place, 12 in another and 13 in a third, and "5.400" (Turkish thousands)
became 5. The rules here, in order:

* None, "", bool, NaN → ``default``.
* int / float pass through; ``to_int`` TRUNCATES toward zero (12.7 → 12).
* Strings: spaces and the "%" sign are dropped, then the separator is decided
    - both "." and "," present → the LAST one is the decimal mark
      ("5.400,5" → 5400.5, "5,400.5" → 5400.5);
    - only one kind, appearing once, followed by exactly 3 digits → thousands
      ("5.400" → 5400, "5,400" → 5400);
    - only one kind, repeated → thousands ("1.234.567" → 1234567);
    - otherwise it is the decimal mark ("12.7" → 12.7, "5,4" → 5.4).
"""
from __future__ import annotations

import math
import re
from typing import Any

_THOUSANDS_TAIL = re.compile(r"^-?\d{1,3}[.,]\d{3}$")


def _normalize_number_text(text: str) -> str:
    s = text.strip().replace(" ", "").replace(" ", "").rstrip("%")
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        return s.replace(thou, "").replace(dec, ".")
    sep = "." if has_dot else "," if has_comma else ""
    if not sep:
        return s
    if s.count(sep) > 1 or _THOUSANDS_TAIL.match(s):
        return s.replace(sep, "")
    return s.replace(sep, ".")


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return default if isinstance(value, float) and math.isnan(value) else float(value)
    text = str(value)
    if not text.strip():
        return default
    try:
        out = float(_normalize_number_text(text))
    except ValueError:
        return default
    return default if math.isnan(out) else out


def to_int(value: Any, default: int | None = None) -> int | None:
    f = to_float(value, None)
    return default if f is None or math.isinf(f) else int(f)


__all__ = ("to_float", "to_int")
