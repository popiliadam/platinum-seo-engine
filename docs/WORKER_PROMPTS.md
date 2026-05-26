# Worker Session Prompts

Manager'ın worker session açarken kullandığı 4 template. Her worker dar scope'lu, single-purpose. Spec §14.6.

Her worker dispatch'i:
- Scope'u sıkı tanımlar
- Hangi spec section'ları okuyacağını (ve okumayacağını) söyler
- Tam dosya listesini verir
- Worker Output Package format'ında dönüş ister
- Scope creep yasak

---

## Type 1: Schema Migration Worker

**Scope:** Eski repo'dan tek bir schema dosyası taşı, fixture yaz, validate et.

**Read ONLY:**
- Spec §5 (Master Excel) veya §6 (SF reports) veya §7 (Cross-sheet) — sadece ilgili section
- `rules/schema-discipline.md`
- Eski schema dosyası (kaynak path manager tarafından verilir)

**Do NOT read:**
- Full spec
- Diğer schema dosyaları (sadece ilgili olan)
- Skill / hook / command dosyaları

**Files to create/modify:**
- `schemas/{schema-name}.schema.json` (kopya + ARCHITECTURE-v4 ref'lerini new docs'a remap)
- `tests/schemas/{schema-name}.fixture.json` (geçerli örnek)
- `tests/schemas/{schema-name}.invalid.fixture.json` (en az 1 hatalı örnek)

**Verification (must run before returning):**
- `python scripts/validate_schema.py schemas/{schema-name}.schema.json tests/schemas/{schema-name}.fixture.json` → PASS
- Invalid fixture → FAIL beklenir

**Forbidden:**
- Eski dosyayı mutate etme (sadece `cp` ile kopyala — ADR-004)
- Spec'in diğer section'larına dokunma
- Skill/hook yazma

**Return:** Worker Output Package (spec §13.4 format).

---

## Type 2: Skill Implementation Worker

**Scope:** 1 skill markdown yaz + smoke test.

**Read ONLY:**
- Spec §9 (Skill Description Discipline)
- Spec §11'in **sadece bu skill'le ilgili** alt-bölümü (manager link verir)
- `rules/skill-description-discipline.md`
- `schemas/skill-frontmatter.schema.json`

**Do NOT read:**
- Full §11 catalog (45 skill)
- Diğer skill dosyaları
- Migration scripts

**Files to create/modify:**
- `skills/{category}/{name}/SKILL.md` (frontmatter + body, `rules/skill-description-discipline.md` kurallarına uygun)
- `tests/skills/{name}.smoke.test.{ext}` (description-driven dispatch smoke test)

**Verification:**
- Frontmatter `schemas/skill-frontmatter.schema.json`'a uygun
- Smoke test PASS
- Description NL-trigger phrasing'e uygun (§9)

**Forbidden:**
- Yeni schema yaratma
- Birden fazla skill yazma (1 worker = 1 skill)
- Hook / command yazma

**Return:** Worker Output Package.

---

## Type 3: Test Writing Worker

**Scope:** Verilen skill / script / schema için test yaz, koştur, raporla.

**Read ONLY:**
- Hedef dosya (tek)
- Mevcut test dosyaları (referans için, **modify etmeden**)
- `rules/testing-discipline.md`

**Do NOT read:**
- Full spec
- Migration list
- Diğer skill'lerin testleri (sadece pattern referans için)

**Files to create/modify:**
- `tests/{path}/{name}.test.{ext}` (unit / integration / e2e — manager belirler)
- Coverage gerektiriyorsa fixture dosyası

**Verification:**
- Test runner ile koştur, PASS/FAIL raporla
- Coverage ≥ %80 (testing-discipline kuralı)
- Flaky test → 3 kez koştur, hepsi PASS olmalı

**Forbidden:**
- Implementation kodunu mutate etme (sadece test ekle)
- Yeni feature ekleme
- Mevcut test'i silme (manager onayı olmadan)

**Return:** Worker Output Package + PASS/FAIL özeti.

---

## Type 4: Documentation Worker

**Scope:** Belirli doc dosyalarını yaz veya güncelle (örn. yeni skill landing'inde WORKFLOWS catalog güncelleme).

**Read ONLY:**
- Hedef doc dosyası (varsa)
- İlgili spec section (manager link verir)
- Güncelleme sebebi olan kaynak dosya (örn. yeni skill)

**Do NOT read:**
- Full spec
- Schemas / skills / scripts (sadece ilgili olanı)

**Files to create/modify:**
- `docs/{filename}.md` (manager belirler — örn. `WORKFLOWS.md`, `ARCHITECTURE.md`)

**Constraints:**
- Her dosya **<5KB** (spec §14 hard rule)
- Türkçe human-readable, JSON/code/identifier İngilizce
- Mevcut dosya üzerine yazılıyorsa Read önce zorunlu

**Verification:**
- `wc -c {file}` ile boyut kontrolü
- Markdown lint geçer
- İçerik factual (spec ile çelişmemeli)

**Forbidden:**
- Doc dışı dosyalara dokunma
- Yeni decision verme (DECISIONS manager'da kalır)
- Yeni open question açma (manager'a paket içinde rapor et, kendi yazma)

**Return:** Worker Output Package.
