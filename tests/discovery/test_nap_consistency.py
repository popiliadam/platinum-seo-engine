"""tests/discovery/test_nap_consistency.py — pure NAP normalize/compare tests.

GAP-A2 (2026-06-10 acquisition spec; unified dispatch batch GAP-A-B2),
RED-first: ``scripts/discovery/nap_consistency.py`` is the pure
(no-I/O, no-clock, no-RNG) helper module behind the gbp-audit transform's
NAP-mismatch branch — the branch the transform docstring DECLARED since
v1.7 Phase 5 but never implemented (re-verified 2026-06-10 against
``scripts/discovery/gbp_audit_transform.py``).

Canonical NAP source of truth: ``projects/{slug}/local/nap.json``
(``schemas/local-nap.schema.json``; rules/local-seo-discipline.md R-144).

Covered (12+ cases):
  - phone normalization TR surface variants -> E.164
    (trunk-0 + parens/spaces, ``+90`` form, bare 10-digit national,
    ``00`` international prefix, dashes),
  - Turkish İ/I casefold (the Python ``'İ'.lower() == 'i̇'`` combining-dot
    trap is explicitly avoided),
  - address abbreviation equivalence (``Cad.``/``caddesi``,
    ``No:``/``numara``) + dict->token flatten,
  - true mismatch detection (different street number / phone),
  - multi-location matching by ``location_id`` (incl. unknown id finding),
  - missing observed fields are SKIPPED (absence is not a mismatch),
  - determinism (same inputs -> identical serialized findings).

Run from repo root:
    PYTHONPATH=. pytest tests/discovery/test_nap_consistency.py -v
"""

from __future__ import annotations

import json

from scripts.discovery import nap_consistency


# ---------------------------------------------------------------------------
# normalize_phone — TR surface forms -> E.164
# ---------------------------------------------------------------------------

def test_normalize_phone_tr_trunk_zero_with_parens_and_spaces() -> None:
    assert nap_consistency.normalize_phone("0 (212) 123 45 67") == "+902121234567"


def test_normalize_phone_plus_form() -> None:
    assert nap_consistency.normalize_phone("+90 212 123 45 67") == "+902121234567"


def test_normalize_phone_bare_ten_digit_national() -> None:
    assert nap_consistency.normalize_phone("2121234567") == "+902121234567"


def test_normalize_phone_double_zero_international_prefix() -> None:
    assert nap_consistency.normalize_phone("0090 212 123 45 67") == "+902121234567"


def test_normalize_phone_dashes() -> None:
    assert nap_consistency.normalize_phone("0212-123-45-67") == "+902121234567"


# ---------------------------------------------------------------------------
# normalize_address_tokens — Turkish fold + abbreviation map + flatten
# ---------------------------------------------------------------------------

def test_address_tokens_abbreviation_equivalence() -> None:
    a = nap_consistency.normalize_address_tokens("Atatürk Cad. No:5")
    b = nap_consistency.normalize_address_tokens("ataturk caddesi numara 5")
    assert a == b == ["ataturk", "caddesi", "numara", "5"]


def test_address_tokens_turkish_i_fold_both_directions() -> None:
    # 'İ' must fold to plain ascii 'i' (NOT Python's default 'i' + combining
    # dot), and dotless-I uppercase ('ISTIKLAL') must land on the same token.
    assert (
        nap_consistency.normalize_address_tokens("İstiklal Caddesi")
        == nap_consistency.normalize_address_tokens("ISTIKLAL CADDESI")
        == ["istiklal", "caddesi"]
    )


def test_address_tokens_dict_flatten_fixed_component_order() -> None:
    tokens = nap_consistency.normalize_address_tokens(
        {"street": "Atatürk Cad. No:5", "city": "İstanbul"}
    )
    assert tokens == ["ataturk", "caddesi", "numara", "5", "istanbul"]


# ---------------------------------------------------------------------------
# compare_nap — canonical vs observed
# ---------------------------------------------------------------------------

def _canon() -> dict:
    return {
        "schema_version": "1.0",
        "business_name": "Örnek Klima Servisi",
        "phone": "+902121234567",
        "address": {"street": "Atatürk Cad. No:5", "city": "İstanbul"},
        "locations": [
            {
                "location_id": "kadikoy",
                "name": "Örnek Klima Kadıköy",
                "phone": "+902165554433",
                "address": {"street": "Bağdat Caddesi No:12", "city": "İstanbul"},
            },
        ],
    }


def test_compare_nap_equivalent_surface_forms_zero_findings() -> None:
    observed = {
        "business_name": "ÖRNEK KLİMA SERVİSİ",
        "phone": "0 212 123 45 67",
        "address": "Ataturk Caddesi Numara 5 Istanbul",
    }
    assert nap_consistency.compare_nap(_canon(), observed) == []


def test_compare_nap_phone_mismatch_detected_with_default_source() -> None:
    findings = nap_consistency.compare_nap(
        _canon(), {"phone": "+90 212 999 88 77"}
    )
    assert len(findings) == 1
    f = findings[0]
    assert f["field"] == "phone"
    assert f["canonical_value"] == "+902121234567"
    assert f["observed_value"] == "+90 212 999 88 77"
    assert f["observed_source"] == "gbp_listing"  # default source label


def test_compare_nap_street_number_mismatch_detected() -> None:
    findings = nap_consistency.compare_nap(
        _canon(), {"address": "Atatürk Caddesi Numara 7 İstanbul"}
    )
    assert [f["field"] for f in findings] == ["address"]


def test_compare_nap_multi_location_matched_by_id_zero_findings() -> None:
    observed = {
        "location_id": "kadikoy",
        "business_name": "Örnek Klima Kadıköy",
        "phone": "0216 555 44 33",
    }
    assert nap_consistency.compare_nap(_canon(), observed) == []


def test_compare_nap_multi_location_resolves_location_level_values() -> None:
    findings = nap_consistency.compare_nap(
        _canon(), {"location_id": "kadikoy", "phone": "0216 000 00 00"}
    )
    assert len(findings) == 1
    assert findings[0]["field"] == "phone"
    # canonical side must be the LOCATION phone, not the top-level phone
    assert findings[0]["canonical_value"] == "+902165554433"


def test_compare_nap_unknown_location_id_is_a_finding() -> None:
    findings = nap_consistency.compare_nap(
        _canon(), {"location_id": "ankara", "phone": "+903121112233"}
    )
    assert [f["field"] for f in findings] == ["location_id"]


def test_compare_nap_missing_observed_fields_skipped() -> None:
    # Absent observed data is NOT a mismatch — we cannot claim a difference
    # we did not observe.
    assert nap_consistency.compare_nap(_canon(), {}) == []


def test_compare_nap_deterministic_and_field_ordered() -> None:
    observed = {
        "business_name": "Başka İsim",
        "phone": "+905551112233",
        "address": "Yanlış Mahallesi 9",
    }
    r1 = nap_consistency.compare_nap(_canon(), dict(observed))
    r2 = nap_consistency.compare_nap(_canon(), dict(observed))
    assert (
        json.dumps(r1, sort_keys=True, ensure_ascii=False)
        == json.dumps(r2, sort_keys=True, ensure_ascii=False)
    )
    # stable field order: business_name -> phone -> address
    assert [f["field"] for f in r1] == ["business_name", "phone", "address"]
