"""K-02 (v1.5-Phase-2 Tier 1) registry consistency:
``schemas/cross-sheet-invariants.json`` ↔ ``scripts/validation/validate_invariants.py``.

Bidirectional check + ``KNOWN_SCHEMA_ONLY`` known-deferred set
(``test_hook_scripts_exist.EXPECTED_DEFERRED`` paterni reuse). F-06/F-07
are declared in the schema but intentionally NOT implemented in
``validate_invariants.py`` — they are join-level rules handled by the
``consistency_check`` tool at the cross-sheet boundary, not at the
Excel-row boundary. Listing them in ``KNOWN_SCHEMA_ONLY`` keeps the
authority cite alive while preventing silent drift in either direction.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

from scripts.validation import validate_invariants

ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "cross-sheet-invariants.json"

# F-NN ids declared in cross-sheet-invariants.json but intentionally NOT
# implemented in validate_invariants.py (consistency_check tool handles
# them at the cross-sheet join level, not Excel-row level).
KNOWN_SCHEMA_ONLY: frozenset[str] = frozenset({"F-06", "F-07"})


def _load_schema_f_ids() -> set[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {r["id"] for r in schema["rules"] if r["id"].startswith("F-")}


def _code_f_ids() -> set[str]:
    return {
        fn.__name__.replace("check_", "").replace("_", "-")
        for fn in validate_invariants._RULE_FUNCTIONS
    }


def test_every_implemented_rule_is_declared_in_schema():
    """Yön A: validate_invariants.py F-NN ⊆ cross-sheet-invariants.json F-NN.

    Bir kuralın production kodunda implement edilip schema'da declare
    edilmemesi 'silent rule' demektir; consistency_check tool schema'yı
    SoT olarak alır, declare edilmemiş F-NN'ler reporting'de görünmez.
    """
    missing = sorted(_code_f_ids() - _load_schema_f_ids())
    assert not missing, (
        f"validate_invariants.py'da implement edilen ama schema'da olmayan "
        f"F-NN rules: {missing}. K-02 paterni: schema'ya additive ekle."
    )


def test_every_declared_schema_rule_is_implemented_or_known_deferred():
    """Yön B: schema F-NN ⊆ kod F-NN ∪ KNOWN_SCHEMA_ONLY.

    Schema'da declared olup kod'da implement edilmemiş F-NN'ler ya
    explicit known-deferred set'te listelenmeli ya da
    validate_invariants.py'a check fonksiyonu eklenmeli.
    """
    unimplemented = sorted(
        _load_schema_f_ids() - _code_f_ids() - KNOWN_SCHEMA_ONLY
    )
    assert not unimplemented, (
        f"Schema'da declared ama kod'da implement edilmemiş ve "
        f"KNOWN_SCHEMA_ONLY'de listelenmemiş F-NN rules: {unimplemented}."
    )


def test_known_schema_only_set_is_authoritative():
    """KNOWN_SCHEMA_ONLY drift guard: F-06/F-07 schema'da kalmaya devam etmeli.

    Eğer schema'dan silinirlerse KNOWN_SCHEMA_ONLY claim asılsız kalır;
    test silinen tarafı zorlar (geri ekle ya da set'ten çıkar).
    """
    missing_known = sorted(KNOWN_SCHEMA_ONLY - _load_schema_f_ids())
    assert not missing_known, (
        f"KNOWN_SCHEMA_ONLY claim ediyor ama schema'da yok: {missing_known}. "
        f"Schema'ya geri eklenmeli ya da KNOWN_SCHEMA_ONLY'den çıkarılmalı."
    )


def test_severity_consistency_for_implemented_rules():
    """Severity drift guard: validate_invariants.py F-NN severity ↔
    schema severity match.

    Drift catch: severity'i sadece bir tarafta değiştirip diğer tarafı
    unutmak (örn. F-13 severity HIGH→MEDIUM kod'da değişti ama schema'da
    HIGH kaldı). Severity literal kod içinde ``severity="..."`` argument
    ile döndürülür; ilk match SoT olarak alınır.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_severity = {r["id"]: r["severity"] for r in schema["rules"]}

    mismatches: list[str] = []
    for fn in validate_invariants._RULE_FUNCTIONS:
        rule_id = fn.__name__.replace("check_", "").replace("_", "-")
        if rule_id not in schema_severity:
            continue  # Yön A test handles missing-from-schema
        src = inspect.getsource(fn)
        m = re.search(r'severity="(\w+)"', src)
        if not m:
            continue
        code_sev = m.group(1)
        sch_sev = schema_severity[rule_id]
        if code_sev != sch_sev:
            mismatches.append(
                f"{rule_id}: code={code_sev!r} vs schema={sch_sev!r}"
            )

    assert not mismatches, (
        "Severity drift between validate_invariants.py and "
        f"cross-sheet-invariants.json: {mismatches}"
    )
