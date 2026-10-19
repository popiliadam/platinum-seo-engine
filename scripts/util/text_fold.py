#!/usr/bin/env python3
"""text_fold.py — one Turkish-aware case/diacritic fold for the whole engine (D-06).

Python's ``"İ".lower()`` is ``"i" + U+0307`` (a combining dot), so lower-casing
BEFORE the Turkish map gave ``make_url_slug("İzmir Diş Kliniği") ==
"i-zmir-dis-klinigi"`` and ``"İzmir" != "izmir"`` in brand checks. Three
modules had their own fold, two of them wrong. The rule here: map İ→i and
I→ı FIRST, then lower-case.

* ``lower_tr``  — display-safe lower case (keeps ç ğ ı ö ş ü).
* ``fold_key``  — comparison key: lower_tr + ASCII fold (ı→i, ş→s …), so
  "IŞIK", "ışık" and "isik" match, and "IKEA" stays "ikea".
* ``slugify``   — URL slug from fold_key.
"""
from __future__ import annotations

import re

_TR_I_FOLD = str.maketrans({"İ": "i", "I": "ı"})
_TR_ASCII_FOLD = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u",
})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def lower_tr(text: str) -> str:
    return (text or "").translate(_TR_I_FOLD).lower()


def fold_key(text: str) -> str:
    return lower_tr(text).translate(_TR_ASCII_FOLD)


def fold_tokens(text: str) -> set[str]:
    return set(_WORD.findall(fold_key(text)))


def slugify(text: str) -> str:
    return _NON_ALNUM.sub("-", fold_key(text).strip()).strip("-")


__all__ = ("lower_tr", "fold_key", "fold_tokens", "slugify")
