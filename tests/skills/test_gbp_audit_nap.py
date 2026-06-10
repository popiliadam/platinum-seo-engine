"""tests/skills/test_gbp_audit_nap.py — gbp-audit NAP branch (GAP-A2, RED-first).

Closes the declared-but-unimplemented contract re-verified 2026-06-10:
``scripts/discovery/gbp_audit_transform.py`` docstring line ~21 declares
``nap HIGH NAP mismatch`` in the severity matrix, but ``_analyze_gaps``
only ever emitted the "listing not found" nap row. Additionally
``skills/discovery/gbp-audit/SKILL.md`` Step 4 read
``config["brand_identity"]["business_name"]`` / ``["primary_location"]``
— keys that ``schemas/project-config.schema.json#brand_identity``
(``additionalProperties: false``, visual-identity block) does NOT permit.

Canonical NAP source of truth: ``projects/{slug}/local/nap.json``
(``schemas/local-nap.schema.json``; rules/local-seo-discipline.md R-144).

Cases:
  1. canonical nap.json + listing with mismatched phone -> category="nap"
     HIGH row carrying BOTH values in gap_description.
  2. nap.json missing -> single MEDIUM "Canonical NAP file missing" row.
  3. matching NAP (different surface forms) -> ZERO nap rows.
  4. emitted rows conform to the 7-col gbp_audit sheet contract
     (column set + category enum + severityEnum + statusEnum strict).
  5. listing-not-found regression: exactly ONE nap row even with nap.json
     present (comparison is moot without a listing; mirrors the existing
     ``test_listing_not_found_emits_high_severity_nap`` count assertion).
  6. corrupt nap.json -> fail-loud (DURUR — never audit against half a
     canonical).
  7. SKILL.md sentinel: phantom brand_identity Step-4 contract removed;
     frontmatter v1.1 declares the optional ``nap_source`` input.
  8. rules sentinel: rules/local-seo-discipline.md defines R-144/R-145/R-146
     (remapped ids per the unified dispatch §R-MAP) and R-145 carries the two
     official Google policy URLs verbatim.

Existing cases in tests/skills/test_gbp_audit.py stay green (regression —
their assertions are set-membership / nap-row-count on paths this change
keeps stable).

Run from repo root:
    PYTHONPATH=. pytest tests/skills/test_gbp_audit_nap.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.discovery import gbp_audit_transform

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "discovery" / "gbp-audit" / "SKILL.md"
RULES_MD = REPO_ROOT / "rules" / "local-seo-discipline.md"

GBP_AUDIT_COLS = {
    "audit_id",
    "audit_date",
    "category",
    "gap_description",
    "severity",
    "recommended_action",
    "status",
}
CATEGORY_ENUM = {
    "nap", "categories", "photos", "hours",
    "attributes", "posts", "qa", "reviews",
}

CANON_NAP = {
    "schema_version": "1.0",
    "business_name": "Örnek Klima Servisi",
    "phone": "+902121234567",
    "address": {"street": "Atatürk Cad. No:5", "city": "İstanbul"},
}

# A listing complete enough that NO other category fires — isolates the
# nap branch in row-count assertions.
FULL_LISTING_BASE = {
    "business_name": "Örnek Klima Servisi",
    "primary_category": "HVAC service",
    "secondary_categories": ["Air conditioning contractor", "Heating contractor"],
    "photo_count": 12,
    "business_hours": {"mon": "9-18"},
    "holiday_hours": {"2026-01-01": "closed"},
    "attributes": {"parking": True},
    "post_count_30d": 2,
    "qa_count": 3,
    "review_response_rate": 0.9,
    "avg_rating": 4.6,
}


def _write_nap(project_dir: Path, doc: dict = CANON_NAP) -> None:
    local_dir = project_dir / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "nap.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _nap_rows(result: dict) -> list[dict]:
    return [r for r in result["gap_rows"] if r["category"] == "nap"]


# ---------------------------------------------------------------------------
# Transform behavior
# ---------------------------------------------------------------------------

def test_nap_mismatch_emits_high_row_with_both_values(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_workspace_factory(slug="local-nap", profiles=["local-service"])
    _write_nap(project_dir)
    listing = dict(
        FULL_LISTING_BASE,
        phone="+90 212 999 88 77",                # MISMATCH vs canonical
        address="Atatürk Cad. No:5 İstanbul",     # equivalent -> no finding
    )
    monkeypatch.setattr(gbp_audit_transform, "_fetch_listing", lambda config: listing)

    result = gbp_audit_transform.run(project_slug="local-nap")
    assert result["status"] == "success"
    nap_rows = _nap_rows(result)
    assert len(nap_rows) == 1
    row = nap_rows[0]
    assert row["severity"] == "HIGH"
    assert "phone" in row["gap_description"]
    assert "+902121234567" in row["gap_description"]       # canonical value
    assert "+90 212 999 88 77" in row["gap_description"]   # observed value


def test_missing_nap_file_emits_single_medium_row(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_workspace_factory(slug="local-nonap", profiles=["local-service"])
    monkeypatch.setattr(
        gbp_audit_transform, "_fetch_listing",
        lambda config: dict(FULL_LISTING_BASE),
    )

    result = gbp_audit_transform.run(project_slug="local-nonap")
    assert result["status"] == "success"
    nap_rows = _nap_rows(result)
    assert len(nap_rows) == 1
    assert nap_rows[0]["severity"] == "MEDIUM"
    assert "canonical nap file missing" in nap_rows[0]["gap_description"].lower()
    assert "local/nap.json" in nap_rows[0]["gap_description"]


def test_matching_nap_emits_zero_nap_rows(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_workspace_factory(slug="local-match", profiles=["local-service"])
    _write_nap(project_dir)
    # Different surface forms, same NAP after normalization — the
    # load-bearing assertion of the whole comparison layer.
    listing = dict(
        FULL_LISTING_BASE,
        business_name="ÖRNEK KLİMA SERVİSİ",
        phone="0 (212) 123 45 67",
        address="Ataturk Caddesi Numara 5 Istanbul",
    )
    monkeypatch.setattr(gbp_audit_transform, "_fetch_listing", lambda config: listing)

    result = gbp_audit_transform.run(project_slug="local-match")
    assert result["status"] == "success"
    assert _nap_rows(result) == []


def test_emitted_rows_conform_to_seven_col_contract(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_workspace_factory(slug="local-cols", profiles=["local-service"])
    _write_nap(project_dir)
    listing = dict(FULL_LISTING_BASE, phone="+90 212 000 00 00", photo_count=1)
    monkeypatch.setattr(gbp_audit_transform, "_fetch_listing", lambda config: listing)

    result = gbp_audit_transform.run(project_slug="local-cols")
    assert result["status"] == "success"
    assert result["gap_rows"], "expected at least the nap + photos rows"
    for row in result["gap_rows"]:
        assert set(row.keys()) == GBP_AUDIT_COLS
        assert row["category"] in CATEGORY_ENUM
        assert row["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert row["status"] == "TODO"
        assert row["audit_id"].startswith("gbp-")


def test_listing_not_found_still_single_nap_row_with_nap_present(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_workspace_factory(slug="local-nf", profiles=["local-service"])
    _write_nap(project_dir)
    monkeypatch.setattr(gbp_audit_transform, "_fetch_listing", lambda config: None)
    monkeypatch.setattr(
        gbp_audit_transform, "_scrapling_fallback", lambda config: None
    )

    result = gbp_audit_transform.run(project_slug="local-nf")
    assert result["status"] == "success"
    nap_rows = _nap_rows(result)
    assert len(nap_rows) == 1
    assert nap_rows[0]["severity"] == "HIGH"
    assert "listing not found" in nap_rows[0]["gap_description"].lower()


def test_corrupt_nap_json_fails_loud(
    tmp_workspace_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_workspace_factory(slug="local-corrupt", profiles=["local-service"])
    local_dir = project_dir / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "nap.json").write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr(
        gbp_audit_transform, "_fetch_listing",
        lambda config: dict(FULL_LISTING_BASE),
    )

    with pytest.raises(json.JSONDecodeError):
        gbp_audit_transform.run(project_slug="local-corrupt")


# ---------------------------------------------------------------------------
# Doc-artifact sentinels (SKILL.md contract fix + rules file)
# ---------------------------------------------------------------------------

def test_skill_step4_phantom_brand_identity_contract_removed() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    assert 'config["brand_identity"]["business_name"]' not in text, (
        "SKILL.md Step 4 still reads brand_identity.business_name — the key "
        "does not exist in project-config.schema.json#brand_identity "
        "(additionalProperties: false, visual-identity block)"
    )
    assert 'config["brand_identity"]["primary_location"]' not in text
    assert "local/nap.json" in text

    _, fm_raw, _ = text.split("---", 2)
    fm = yaml.safe_load(fm_raw)
    assert fm["version"] == "1.1"
    assert fm["inputs"]["nap_source"]["type"] == "string"
    assert fm["inputs"]["nap_source"]["required"] is False
    assert fm["inputs"]["nap_source"]["default"] == "local/nap.json"


def test_local_seo_rules_define_remapped_ids() -> None:
    text = RULES_MD.read_text(encoding="utf-8")
    for heading in ("### R-144", "### R-145", "### R-146"):
        assert heading in text, f"{heading} missing from rules/local-seo-discipline.md"
    # R-145 (review acquisition white-hat) must cite the two OFFICIAL policy
    # URLs verbatim — third-party summaries are not the authority.
    assert "https://support.google.com/contributionpolicy/answer/7400114" in text
    assert "https://support.google.com/business/answer/14114287" in text
