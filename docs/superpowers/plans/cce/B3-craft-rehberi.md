# WORKER PROMPT — B3: Craft Rehberi (Competitive Content Engine)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Sıfır context varsay. SADECE bu dosyadaki görevleri yap. B1/B2/B4 dosyalarına DOKUNMA. Bitince handoff raporu döndür — **PUSH ETME.**
>
> Tam tasarım: `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` §5+§11.

## Görevin

Mevcut content rule'ları (R-01..R-148) tamamen "şunu YAPMA" yasakları. Eksik olan **pozitif yazım rehberi** ("nasıl HARİKA/ruhlu/özgün yazılır"). Bunu yeni bir kural dosyası olarak yaz — operatörün şikâyetinin ("ruhsuz/sığ/generic") doğrudan ilacı. Bu, B2'nin `voice` + `originality` + `depth` kapılarının pozitif karşılığıdır.

## ÖNCE: R-token numarasını doğrula (kritik)

```bash
grep -rhoE 'R-[0-9]+' rules/ | sort -t- -k2 -n | uniq | tail -3
```

En yüksek mevcut token'ı bul (beklenen: **R-148**). Yeni kurallar ondan **SONRA** başlar (R-149, R-150, …). Mevcut hiçbir R-token'a DOKUNMA. `tests/rules/test_rule_id_uniqueness.py`'yi çalıştır — yeni kuralların onu kırmadığını doğrula (tüm R-token tekil kalmalı).

## Dosyalar

- Create: `rules/content-craft-discipline.md`
- Modify: `rules/content-quality.md` — Cross-References bölümüne `→ content-craft-discipline` satırı ekle (yalnız 1 satır; başka değişiklik yok)
- Test: `tests/rules/test_content_craft_discipline.py`

## İçerik sözleşmesi — `rules/content-craft-discipline.md`

Frontmatter, mevcut `rules/content-eeat-discipline.md` ile AYNI yapıda olmalı:
```yaml
---
name: Content Craft Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization]
source: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md §5
spec_section: "CCE — Pozitif Yazım Katmanı"
---
```

Foundational Principles'a referans ver (tekrar yazma — DRY): `→ rules/content-quality.md#foundational-principles`. Sonra `## Rules` altında, **R-149'dan başlayarak** (mevcut max'a göre ayarla) şu temaları KESİN kurallara dök (her kural: **Statement / Rationale / Enforcement / Failure mode** — emsal: content-eeat-discipline.md):

1. **Empati/pain-mirror intro (profil-aware).** Intro, okurun gerçek derdini yansıtsın (örn. eksik diş → "gülerken el kapatmak"). YMYL'de empati+netlik (satışçı DEĞİL — güven bölgesi); pazarlama yüzeyinde cesur ton. `brand_identity.profile` + `feedback_marketing_surface_boldness` hizası. Enforcement: B2 `voice`/`aeo` kapısı.
2. **Somut örnek/senaryo zorunluluğu.** Her ana iddia ≥1 somut örnek/senaryo/sayı ile desteklenir (soyut genelleme tek başına yasak).
3. **Marka sesi.** `brand_identity.tone` + `hitap` + `tone_phrases_blocklist` aktif; generic ansiklopedi tonu yasak (B2 `voice` kapısı pozitif karşılığı).
4. **Özgün değer (rakip-üstü).** Her içerik, rakiplerin hiçbirinde olmayan ≥1 gerçek özgün öğe taşır (özgün veri/hesap aracı/vaka/daha iyi karşılaştırma); HTML'de `data-original="true"` ile işaretlenir (B2 `originality` kapısı bunu okur). Uydurma YASAK (Principle 1 üstte) — özgünlük gerçek olmalı.
5. **Derinlik/akış.** Her H2 gerçek işleme (yüzeysel başlık-bas-geç yasak); bölümler arası mantıksal akış (B2 `depth` kapısı pozitif karşılığı).

Numaralandırmayı mevcut max'a göre ardışık ver (R-149, R-150, …). Her kuralın Enforcement satırı ilgili B2 kapısına çapraz referans versin (motor ↔ kural hizası).

## TDD adımları

- [ ] **Step 1 — Failing test yaz.** Örnek:

```python
# tests/rules/test_content_craft_discipline.py
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "rules" / "content-craft-discipline.md"

def test_file_exists_with_frontmatter():
    txt = DOC.read_text(encoding="utf-8")
    assert txt.startswith("---")
    assert "applied_to_skills: [new-blog, revise-content, faq-optimization]" in txt

def test_rules_start_after_existing_max():
    existing = [int(m) for m in re.findall(r'R-(\d+)', (ROOT/"rules"/"content-quality.md").read_text())]
    craft = [int(m) for m in re.findall(r'R-(\d+)', DOC.read_text())]
    assert craft, "craft kuralı yok"
    # yeni craft kuralları mevcut content-quality max'ından büyük (çakışma yok)
    assert min(c for c in craft if c >= 149) > 148

def test_each_rule_has_four_sections():
    txt = DOC.read_text()
    for rid in re.findall(r'### (R-\d+)', txt):
        block = txt.split(rid,1)[1].split("### R-")[0]
        for sec in ("Statement","Rationale","Enforcement","Failure mode"):
            assert sec in block, f"{rid} eksik: {sec}"
```

- [ ] **Step 2 — Run, FAIL gör.** `pytest tests/rules/test_content_craft_discipline.py -v`
- [ ] **Step 3 — content-craft-discipline.md yaz** (yukarıdaki sözleşme; R-149+).
- [ ] **Step 4 — content-quality.md Cross-References'a 1 satır ekle.**
- [ ] **Step 5 — Run, PASS gör + uniqueness korunur:** `pytest tests/rules/test_content_craft_discipline.py tests/rules/test_rule_id_uniqueness.py -v`
- [ ] **Step 6 — Commit.** `git add rules/content-craft-discipline.md rules/content-quality.md tests/rules/test_content_craft_discipline.py && git commit -m "feat(cce): B3 content-craft-discipline — pozitif yazım/ruh kuralları R-149+ (TDD)"`

## Kabul kriterleri

- [ ] R-149+ (mevcut max doğrulandı); mevcut R-token'a dokunulmadı; uniqueness testi GREEN.
- [ ] 5 tema KESİN kurallara döküldü; her kural 4 bölüm (Statement/Rationale/Enforcement/Failure mode).
- [ ] Her Enforcement satırı ilgili B2 kapısına çapraz referans veriyor.
- [ ] content-quality.md'ye yalnız 1 satır cross-ref eklendi (başka değişiklik yok).
- [ ] `pytest tests/rules/ -v` temiz (mevcut testler kırılmadı).
- [ ] Handoff raporu manager'a. PUSH YOK.
