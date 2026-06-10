"""nap_consistency — pure NAP (Name / Address / Phone) normalization + compare.

GAP-A2 (2026-06-10, unified dispatch batch GAP-A-B2): the comparison layer
behind gbp-audit's NAP-mismatch branch
(``scripts/discovery/gbp_audit_transform._analyze_gaps``) — the branch the
transform docstring DECLARED since v1.7 Phase 5 but never implemented.

Canonical NAP single source of truth: ``projects/{slug}/local/nap.json``
(``schemas/local-nap.schema.json``; rules/local-seo-discipline.md R-144).
Callers load that doc and pass dicts in.

Pure-module discipline (D-003 family): no I/O, no clock, no RNG, no events —
same inputs always produce the same findings, byte-for-byte.

Normalization notes
-------------------
* Turkish casefold: Python's ``'İ'.lower()`` yields ``'i' + U+0307``
  (combining dot above), which never equals plain ``'i'``. We therefore map
  ``İ->i`` and ``I->ı`` explicitly BEFORE ``str.lower()``, then fold Turkish
  diacritics to ASCII so ``Atatürk == ataturk`` and
  ``İstiklal == ISTIKLAL == istiklal``.
* Address comparison is ORDER-SENSITIVE token equality after abbreviation
  expansion: a sorted-set comparison would wrongly equate
  ``"5 Sokak No:3"`` with ``"3 Sokak No:5"`` (street-number swap).
* Phone comparison normalizes both sides to E.164 with a trunk-zero rule;
  the dial-prefix country defaults to the canonical address country
  (fallback ``TR``). ``normalize_phone`` is a comparison aid, NOT a
  validator — the stored canonical value is schema-locked to strict E.164.
"""

from __future__ import annotations

import re

__all__ = ["normalize_phone", "normalize_address_tokens", "compare_nap"]


# Pre-lower dotted/dotless-I correction (the Python ``lower()`` trap above).
_TR_I_FOLD = str.maketrans({"İ": "i", "I": "ı"})

# Post-lower Turkish diacritic -> ASCII fold.
_TR_ASCII_FOLD = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u",
})

# ISO 3166-1 alpha-2 -> E.164 dial prefix. Portfolio markets + common cases;
# extend additively. Unknown countries fall back to best-effort "+digits".
_DIAL_PREFIX = {"TR": "90", "CA": "1", "NG": "234", "US": "1", "GB": "44", "DE": "49"}

# Token-level abbreviation expansion, applied AFTER folding (keys AND values
# are in folded-ASCII form). Minimal documented TR street-address set —
# extend additively; never remove an entry (comparison stability).
_ABBREVIATIONS = {
    "cad": "caddesi", "cd": "caddesi",
    "mah": "mahallesi", "mh": "mahallesi",
    "no": "numara",
    "sk": "sokak", "sok": "sokak",
    "blv": "bulvari", "bulv": "bulvari",
    "apt": "apartmani",
}

# Fixed flatten order for schemas/local-nap address objects.
_ADDRESS_COMPONENT_ORDER = ("street", "district", "city", "postal_code", "country")

# Stable comparison/report order of NAP fields.
_NAP_FIELDS = ("business_name", "phone", "address")

_DEFAULT_SOURCE = "gbp_listing"
_NON_DIGITS = re.compile(r"[^0-9]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _fold_tr(text: str) -> str:
    return text.translate(_TR_I_FOLD).lower().translate(_TR_ASCII_FOLD)


def _name_tokens(raw: str) -> list[str]:
    """Folded tokens WITHOUT abbreviation expansion (brand names may
    legitimately contain tokens like 'no' that must not be rewritten)."""
    return _NON_ALNUM.sub(" ", _fold_tr(str(raw))).split()


def normalize_phone(raw: str, default_country: str = "TR") -> str:
    """Best-effort E.164 normalization for NAP comparison.

    Tolerated surface forms: ``0 (212) 123 45 67`` (trunk zero),
    ``+90 212 123 45 67``, ``0090 ...`` (international 00 prefix),
    dashes/spaces, bare 10-digit national numbers. Returns ``""`` when no
    digits survive (callers treat empty as incomparable, never as a match).
    """
    text = str(raw).strip()
    digits = _NON_DIGITS.sub("", text)
    if not digits:
        return ""
    if text.startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    prefix = _DIAL_PREFIX.get((default_country or "").upper())
    if prefix:
        if digits.startswith("0"):
            # National trunk zero (TR convention): 0xxx -> +<cc>xxx
            return "+" + prefix + digits[1:]
        if digits.startswith(prefix) and len(digits) > len(prefix) + 6:
            # Already carries the country code without '+' (e.g. 90212...).
            return "+" + digits
        return "+" + prefix + digits
    return "+" + digits


def normalize_address_tokens(raw: str | dict) -> list[str]:
    """Normalize an address (string surface form OR schemas/local-nap
    address object) to a folded, abbreviation-expanded token list.

    Dict components flatten in fixed order street -> district -> city ->
    postal_code -> country (empty components skipped) so a dict and its
    equivalent printed form tokenize identically.
    """
    if isinstance(raw, dict):
        raw = " ".join(
            str(raw[key]) for key in _ADDRESS_COMPONENT_ORDER if raw.get(key)
        )
    tokens = _NON_ALNUM.sub(" ", _fold_tr(str(raw))).split()
    return [_ABBREVIATIONS.get(token, token) for token in tokens]


def compare_nap(canonical: dict, observed: dict) -> list[dict]:
    """Compare an observed NAP surface (e.g. a fetched GBP listing) against
    the canonical ``local/nap.json`` doc.

    Returns mismatch findings
    ``{field, canonical_value, observed_value, observed_source}`` in stable
    field order (business_name -> phone -> address). Empty list == consistent.

    Contract details:
    * ``observed["location_id"]`` selects the matching ``locations[]`` entry;
      its name/phone/address override the top-level NAP (omitted fields fall
      back). An UNKNOWN location_id is itself a finding
      (``field="location_id"``) and short-circuits the field comparison —
      comparing against the wrong branch would produce garbage findings.
    * Observed fields that are absent/empty are SKIPPED — absence is not
      evidence of mismatch (it may be a different gap category's job).
    * ``observed["source"]`` labels the surface (default ``"gbp_listing"``).
    """
    source = observed.get("source") or _DEFAULT_SOURCE
    expected: dict = {field: canonical.get(field) for field in _NAP_FIELDS}

    location_id = observed.get("location_id")
    if location_id is not None:
        locations = canonical.get("locations") or []
        match = next(
            (loc for loc in locations if loc.get("location_id") == location_id),
            None,
        )
        if match is None:
            known = ", ".join(
                sorted(str(loc.get("location_id")) for loc in locations)
            ) or "<none>"
            return [{
                "field": "location_id",
                "canonical_value": known,
                "observed_value": str(location_id),
                "observed_source": source,
            }]
        expected["business_name"] = match.get("name") or expected["business_name"]
        expected["phone"] = match.get("phone") or expected["phone"]
        expected["address"] = match.get("address") or expected["address"]

    default_country = _country_hint(canonical, expected)
    findings: list[dict] = []
    for field in _NAP_FIELDS:
        canonical_value = expected.get(field)
        observed_value = observed.get(field)
        if not canonical_value or not observed_value:
            continue
        if field == "phone":
            same = normalize_phone(canonical_value, default_country) == \
                normalize_phone(observed_value, default_country)
        elif field == "address":
            same = normalize_address_tokens(canonical_value) == \
                normalize_address_tokens(observed_value)
        else:
            same = _name_tokens(str(canonical_value)) == \
                _name_tokens(str(observed_value))
        if not same:
            findings.append({
                "field": field,
                "canonical_value": _display(canonical_value),
                "observed_value": _display(observed_value),
                "observed_source": source,
            })
    return findings


def _country_hint(canonical: dict, expected: dict) -> str:
    """Dial-prefix country for phone comparison: location-resolved address
    country -> top-level address country -> TR (portfolio default)."""
    for candidate in (expected.get("address"), canonical.get("address")):
        if isinstance(candidate, dict) and candidate.get("country"):
            return candidate["country"]
    return "TR"


def _display(value: str | dict) -> str:
    """Human-readable rendering for gap_description embedding — address
    objects flatten in the fixed component order, everything else is str()."""
    if isinstance(value, dict):
        return " ".join(
            str(value[key]) for key in _ADDRESS_COMPONENT_ORDER if value.get(key)
        )
    return str(value)
