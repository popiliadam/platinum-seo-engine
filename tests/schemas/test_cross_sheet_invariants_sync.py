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

import json
from pathlib import Path

import openpyxl

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

    P0-01 fix (codex audit): the previous implementation read the severity
    literal via ``re.search(r'severity="(\\w+)"', source)`` on each function's
    body. That regex MISSED F-02/F-03/F-04 — their severity lives in the helper
    ``_check_no_excel_formula``, not the function body — which is exactly how
    the F-04 CRITICAL-vs-HIGH drift went undetected. Severity is now read from
    each rule's RESULT dict (``_code_rule_meta``), so helper-delegated
    severities are no longer a blind spot.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_severity = {r["id"]: r["severity"] for r in schema["rules"]}
    code = _code_rule_meta()

    mismatches = [
        f"{rid}: code={meta['severity']!r} vs schema={schema_severity[rid]!r}"
        for rid, meta in code.items()
        if rid in schema_severity and schema_severity[rid] != meta["severity"]
    ]
    assert not mismatches, (
        "Severity drift between validate_invariants.py and "
        f"cross-sheet-invariants.json: {mismatches}"
    )


# ---------------------------------------------------------------------------
# P0-01 semantic-binding: registry `rule` TEXT + `severity` must equal what
# the implementation actually returns (not just the ID-set / a regex literal).
# ---------------------------------------------------------------------------

def _code_rule_meta() -> dict[str, dict]:
    """Invoke each implemented check on an empty workbook + tmp workspace and
    capture its canonical id/rule/severity from the returned result dict."""
    import tempfile, pathlib
    wb = openpyxl.Workbook()
    if wb.active is not None:
        wb.remove(wb.active)            # truly empty -> checks SKIP but still return rule/severity
    out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as td:
        ws_root = pathlib.Path(td)
        (ws_root / "projects" / "demo" / "_state").mkdir(parents=True, exist_ok=True)
        for fn in validate_invariants._RULE_FUNCTIONS:
            res = fn(wb, "demo", workspace_root=ws_root)
            out[res["id"]] = {"rule": res["rule"], "severity": res["severity"]}
    return out


def test_registry_rule_text_binds_to_implementation():
    """Every IMPLEMENTED F-ID's registry `rule` text MUST equal the string the
    implementation returns. Prevents the silent semantic drift where F-01 means
    'status enum' in code but 'url subset' in the registry."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    reg = {r["id"]: r for r in schema["rules"]}
    code = _code_rule_meta()
    mism = []
    for rid, meta in code.items():
        if rid not in reg:
            continue  # Direction-A test already guards missing-from-schema
        if reg[rid]["rule"].strip() != meta["rule"].strip():
            mism.append(f"{rid}: registry={reg[rid]['rule']!r} vs code={meta['rule']!r}")
    assert not mism, "cross-sheet-invariants.json rule text drifted from implementation:\n" + "\n".join(mism)


def test_registry_severity_binds_to_implementation():
    """Severity must match too — read from the RESULT dict (not a source regex),
    so helper-delegated severities (F-02/03/04) are no longer a blind spot."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    reg = {r["id"]: r["severity"] for r in schema["rules"]}
    code = _code_rule_meta()
    mism = [f"{rid}: registry={reg[rid]!r} vs code={m['severity']!r}"
            for rid, m in code.items() if rid in reg and reg[rid] != m["severity"]]
    assert not mism, "severity drift:\n" + "\n".join(mism)
