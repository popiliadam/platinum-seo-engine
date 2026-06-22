"""B3 (CCE) — rules/content-craft-discipline.md: pozitif yazım/ruh katmanı.

Mevcut R-01..R-148 hep "şunu YAPMA" yasakları. Bu dosya eksik POZİTİF yazım
rehberini (pain-mirror empati girişi, somut örnek, marka sesi, rakip-üstü
özgünlük, derinlik/akış) R-149+ kesin kurallarına döker — B2 kapı motorunun
(scripts/production/quality_gates.py §6) voice / originality / depth / aeo
kapılarının POZİTİF karşılığı.

Spec: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md §5 + §11.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "rules" / "content-craft-discipline.md"
QUALITY = ROOT / "rules" / "content-quality.md"

# grep -rhoE 'R-[0-9]+' rules/ | sort -t- -k2 -n | uniq | tail -1  ->  R-148
EXISTING_MAX = 148
FOUR_SECTIONS = ("Statement", "Rationale", "Enforcement", "Failure mode")
# §6 kapı motoru anahtarları — craft kuralları bunların POZİTİF karşılığıdır.
B2_GATES = ("voice", "originality", "depth", "aeo")
HEADING = re.compile(r"### (R-\d+)")


def _ids(text):
    return [int(n) for n in re.findall(r"### R-(\d+)", text)]


def _rule_block(text, rid):
    """rid'in (``### R-NN``) kendi başlığından SONRAKİ bloğu döndür. Başlığa
    kilitlenir (forward-ref güvenli: bare ``R-NN`` metinde önce geçse bile)."""
    after = text.split(f"### {rid}", 1)[1]
    return after.split("### R-", 1)[0]


def test_file_exists_with_frontmatter():
    assert DOC.exists(), "rules/content-craft-discipline.md yok — B3 oluşturmalı"
    txt = DOC.read_text(encoding="utf-8")
    assert txt.startswith("---"), "YAML frontmatter '---' ile başlamalı"
    assert "applied_to_skills: [new-blog, revise-content, faq-optimization]" in txt
    assert "status: enforced" in txt
    assert "applies_to: [plugin]" in txt


def test_rules_start_after_existing_max():
    craft = _ids(DOC.read_text(encoding="utf-8"))
    assert craft, "craft kuralı yok"
    assert craft[0] == EXISTING_MAX + 1, (
        f"ilk kural R-{EXISTING_MAX + 1} olmalı, görülen R-{craft[0]}"
    )
    # mevcut hiçbir R-token'ı YENİ ``### R-NN`` başlığı olarak tekrar etmez.
    assert min(craft) > EXISTING_MAX, f"craft başlıkları > R-{EXISTING_MAX} olmalı: {sorted(craft)}"
    # ardışık numaralandırma (boşluk/atlama yok)
    assert craft == list(range(craft[0], craft[0] + len(craft))), f"R-NN ardışık değil: {craft}"


def test_five_craft_themes_present():
    craft = _ids(DOC.read_text(encoding="utf-8"))
    assert len(craft) == 5, f"5 craft teması (R-149..R-153) bekleniyor: {sorted(craft)}"


def test_each_rule_has_four_sections():
    txt = DOC.read_text(encoding="utf-8")
    rids = HEADING.findall(txt)
    assert rids, "kural başlığı yok"
    for rid in rids:
        block = _rule_block(txt, rid)
        for sec in FOUR_SECTIONS:
            assert sec in block, f"{rid} eksik bölüm: {sec}"


def test_each_enforcement_cross_refs_a_b2_gate():
    """Her kuralın Enforcement bölümü ≥1 B2 kapısına (voice/originality/depth/aeo)
    çapraz referans verir — motor ↔ kural hizası (kabul kriteri)."""
    txt = DOC.read_text(encoding="utf-8")
    for rid in HEADING.findall(txt):
        block = _rule_block(txt, rid)
        enf = block.split("Enforcement", 1)[1].split("Failure mode", 1)[0].lower()
        assert any(g in enf for g in B2_GATES), (
            f"{rid} Enforcement bölümü bir B2 kapısına {B2_GATES} çapraz referans vermiyor"
        )


def test_foundational_principles_referenced_not_duplicated():
    """DRY: 3 üst-prensip tekrar yazılmaz, content-quality'ye link verilir."""
    txt = DOC.read_text(encoding="utf-8")
    assert "content-quality.md#foundational-principles" in txt


def test_content_quality_cross_ref_added():
    """content-quality.md Cross-References'a tek satır craft cross-ref'i eklenmeli."""
    assert "content-craft-discipline" in QUALITY.read_text(encoding="utf-8")
