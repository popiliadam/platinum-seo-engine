---
name: Content Craft Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, faq-optimization]
source: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md §5
spec_section: "CCE — Pozitif Yazım Katmanı"
---

# Content Craft Discipline

Bu doc CCE (Competitive Content Engine) **pozitif yazım katmanını** tanımlar. Mevcut R-01..R-148 içerik kuralları büyük ölçüde "şunu YAPMA" yasaklarıdır; bu dosya eksik tamamlayıcıyı verir: **nasıl HARİKA / ruhlu / özgün yazılır** — pain-mirror empati girişi, somut örnek, marka sesi, rakip-üstü özgünlük, derinlik/akış. Operatör şikâyetinin ("ruhsuz / sığ / generic", W7) doğrudan ilacıdır.

Her craft kuralı, B2 kapı motorunun (`scripts/production/quality_gates.py` §6) bir kapısının **pozitif karşılığıdır** — kapı kod ile ölçer ("geçmezse RED"), bu kurallar nasıl yazılacağını söyler (motor ↔ kural hizası): `voice` (§6 "Ruh"), `originality` (§6 "Özgünlük"), `depth` (§6 "Derinlik"), `aeo` (§6 "AEO").

**Foundational Principles** (3 üst-prensip) `→ rules/content-quality.md#foundational-principles` — burada tekrar yazılmaz (DRY, → [single-source-of-truth](single-source-of-truth.md)). Bu craft katmanı 3 prensibe tabidir ve hiçbiri onları override edemez:
1. **Truth-Verifiable (Principle 1)** — özgünlük / örnek / deneyim / empati GERÇEK olmalı; uydurma craft yasak (R-105/R-114/R-119 bank-driven). P0 Doğruluk her craft kuralının üstündedir.
2. **Profile-Aware (Principle 2)** — empati tonu profile göre değişir: YMYL "güven bölgesi" (empati + netlik, satışçılık yok), pazarlama yüzeyi cesur ton.
3. **Anti-Cheap-Content (Principle 3)** — derinlik / ruh / özgünlük bu prensibin **pozitif inşasıdır** (R-118/R-117/R-30 yasaklarının olumlu yüzü).

---

## Rules

### R-149: Empati / Pain-Mirror Giriş (Profile-Aware)

**Statement.** Her içeriğin girişi (intro) okurun **gerçek derdini** somut biçimde yansıtır (pain-mirror): soyut tanım değil, okurun yaşadığı an. Örn. eksik diş → "gülerken elini ağzına götürmek"; kombi arızası → "sabah duşta suyun aniden soğuması". Bu empati kancası, sorunun **direkt cevabıyla** (R-01 / R-29 / R-101 AEO cevap-önce intro) AYNI açılış bloğunda birleşir: empati + self-contained cevap. Ton profile-aware (Principle 2): `profiles ⊇ {ymyl}` → **güven bölgesi** tonu (empati + netlik, satışçı dil YASAK); pazarlama yüzeyi (e-commerce / landing) → cesur, sinematik ton (operatör kararı — pazarlama yüzeyi cesaret hizası). Profil ne olursa olsun uydurma deneyim yasak (Principle 1 / R-119).

**Rationale.** Jenerik LLM açılışı ("X, günümüzde önemli bir konudur") okurla bağ kurmaz, dwell-time düşürür, AIO citation almaz ve Helpful-Content cheap-content sinyali taşır (Principle 3). Pain-mirror giriş "beni anlıyor" hissini ilk 2 saniyede kurar (engagement) ve cevabı öne çekerek AEO uyumu sağlar. YMYL'de satışçı ton Trustworthiness'i kırar (güven bölgesi); pazarlama yüzeyinde sönük ton dönüşüm kaybettirir — bu yüzden ton sabit değil, profile-aware.

**Enforcement.** new-blog render-time intro üretimi: (1) pain-mirror cümlesi + direkt cevap birleşik; (2) ton `brand_identity.formality` (canonical; legacy alias `tone`) + `brand_identity.pronoun_preference` (canonical; legacy alias `hitap`) + Principle 2 profile tablosundan seçilir. Ölçüm: B2 kapı motoru §6 **voice** kapısı (jenerik / klişe açılış = RED) + **aeo** kapısı (intro cevap-önce mi; `aio.answer_points` kapsandı mı) bu kuralın doğrudan pozitif karşılığıdır (`scripts/production/quality_gates.py`).

**Failure mode.** Jenerik / empatisiz açılış veya YMYL'de satışçı ton → voice kapısı RED (humanize / re-write pass). Intro cevabı geciktiriyorsa → aeo kapısı RED. Uydurma deneyim → P0 Doğruluk RED.

**Cross-link.** → R-01 / R-29 / R-101 (AEO cevap-önce intro), R-119 (uydurma deneyim yasak), [content-quality](content-quality.md#foundational-principles) (Principle 2 profile tablosu), spec §6 voice+aeo kapıları.

### R-150: Somut Örnek / Senaryo Zorunluluğu

**Statement.** Her ana iddia (her H2'nin taşıdığı temel sav) **en az 1 somut örnek, senaryo, sayı veya mini-vaka** ile desteklenir. Tek başına soyut genelleme ("kaliteli ürün önemlidir") yasak — ya somutlaştırılır ("3 mm tek cam yerine 4+16+4 mm yalıtımlı ünite ısı kaybını ~%30 azaltır") ya da çıkarılır. Örnekteki tüm sayısal / vaka iddiaları kanıtlanabilir olmalı (Principle 1 / R-44 source-verification; deneyim-vaka bank-driven R-105 / R-114 / R-119) — uydurma örnek yasak.

**Rationale.** Soyut genelleme yığını klasik jenerik-AI imzasıdır (Principle 3): okura yeni bilgi vermez, rakipten ayrışmaz, AIO citation almaz. Somut örnek aynı anda iki şey üretir: **derinlik** (gerçek işleme) + **güven** (sınanabilir kanıt). "Göster, anlatma" — örnek bir iddiayı doğrulanabilir kılar; sayı/vaka olmayan bölüm okurun zihninde boş kalır.

**Enforcement.** new-blog render-time: her H2 bloğu için ≥1 somutluk sinyali (sayı, "örneğin / diyelim" senaryosu, mini-vaka, somut karşılaştırma). Ölçüm: B2 kapı motoru §6 **depth** kapısı (yüzeysel / tek-paragraf H2 = 0) bu kuralın pozitif karşılığıdır — somut örnek yokluğu sığlık sinyali sayılır (`scripts/production/quality_gates.py`). Hipotetik örnek R-54 ile açıkça flag'lenir.

**Failure mode.** Örneksiz soyut H2 → depth kapısı RED (bölüm derinleştir / örnek ekle). Uydurma örnek → P0 Doğruluk RED (örnek çıkar veya kaynakla).

**Cross-link.** → R-44 / R-52 (fact-check), R-54 (hipotetik flag), R-104 (stats density profile-aware), [content-quality](content-quality.md#foundational-principles) (Principle 1 + Principle 3).

### R-151: Marka Sesi Aktif (Brand Voice)

**Statement.** İçerik proje marka sesini **aktif** taşır; jenerik "ansiklopedi / Wikipedia" tonu yasak. Kaynak alanlar (`project.config.json[brand_identity]`): ton `formality` (canonical; legacy alias `tone`), Türkçe hitap `pronoun_preference` (canonical; legacy alias `hitap`), anglisizm toleransı `anglicism_tolerance`, marka düzeyi yasak kalıplar `tone_phrases_blocklist`. Bu alanlar set ise içerik onlara UYAR; set DEĞİLse Principle 2 profile-aware defaults geçerli (YMYL = semi-pro + siz, e-commerce = conversational + sen, b2b-saas = formal + siz). Her marka kendi sesinde konuşur — aynı motorla yazılan iki marka ayırt edilebilir olmalı.

**Rationale.** Tek-tip nötr ton, operatörün "ruhsuz / generic" şikâyetinin (W7) ana kaynağıdır: iki marka ayırt edilemiyorsa marka değeri sıfırdır. Marka sesi tutarlılığı hem okur bağı hem AIO entity tutarlılığı sağlar (tanınabilir ses = recognizable brand-entity sinyali). `tone_phrases_blocklist` AI imza kelimelerini (R-118) marka düzeyinde keser; bu kural R-118 yasağının pozitif yüzüdür.

**Enforcement.** new-blog render-time: `brand_identity` alanları okunur; ton / hitap / anglisizm uygulanır; `tone_phrases_blocklist` kelimeleri elenir. Ölçüm: B2 kapı motoru §6 **voice** kapısı (AI-imza blocklist R-118 + jenerik açılış) bu kuralın pozitif karşılığıdır — jenerik ansiklopedi tonu voice kapısını geçemez (`scripts/production/quality_gates.py`).

**Failure mode.** Jenerik / marka-dışı ton veya blocklist kelime sızması → voice kapısı RED → humanize pass → 2x AMBER → terminal RED.

**Cross-link.** → R-118 (AI signature humanize — stilistik yasak karşılığı), R-23 / R-60 (profile-aware CSS), [content-quality](content-quality.md#foundational-principles) (Principle 2 ton tablosu), schema `brand_identity` (`formality` / `pronoun_preference` / `anglicism_tolerance` / `tone_phrases_blocklist`).

### R-152: Rakip-Üstü Özgün Değer (Originality)

**Statement.** Her içerik, Brief Paketindeki (spec §7) **rakip kümesinin hiçbirinde olmayan ≥1 gerçek özgün öğe** taşır: özgün veri / ölçüm (R-114), hesap aracı / checklist, gerçek vaka / birinci-el deneyim (R-119), uzman görüşü (R-105) veya rakipten ölçülebilir biçimde daha iyi / derin bir karşılaştırma. Bu öğe HTML'de `data-original="true"` attribute'üyle işaretlenir (B2 originality kapısı bu işareti okur). Özgünlük **gerçek** olmalı — uydurma "özgün veri" yasak (Principle 1; R-105 / R-114 / R-119 bank-driven, bank'ta yoksa öğe kullanılmaz).

**Rationale.** Rakibi "geçmek" ranking + AIO citation için zorunludur: SERP top-10 ile %50+ örtüşen içerik (R-117 uniqueness) seçilmez. Özgün değer = rakip kapsama haritasında (Brief §7 `competitors`) bulunmayan, okurun başka yerde bulamayacağı şey. Ancak Principle 1 mutlaktır: özgünlük uydurmayla DEĞİL, gerçek bank-driven varlıkla sağlanır — sahte özgünlük domain reputation'ı kalıcı yakar.

**Enforcement.** new-blog render-time: Brief competitor entity / heading / question kümesi ile diff → ≥1 öğe rakiplerde yok + bank-verified → `data-original="true"`. Ölçüm: B2 kapı motoru §6 **originality** kapısı (rakip kümesinde olmayan ≥1 gerçek değer; boolean + kanıt) bu kuralın doğrudan pozitif karşılığıdır (`scripts/production/quality_gates.py`); P0 Doğruluk her zaman üstte (spec §6 P0↔Gap çatışma kararı).

**Failure mode.** Özgün öğe yok → originality kapısı RED (özgün değer ekle). Uydurma özgün öğe → P0 Doğruluk RED (öğe çıkar).

**Cross-link.** → R-105 (expert quote bank), R-114 (original research bank), R-119 (first-hand experience bank), R-117 (uniqueness ≥ %70), spec §6 originality kapısı + §8 özgünlük skoru, [content-quality](content-quality.md#foundational-principles) (Principle 1).

### R-153: H2 Derinliği + Mantıksal Akış (Depth & Flow)

**Statement.** Her H2 **gerçek işleme** taşır — başlık-bas-tek-paragraf-geç yasak: H2 kendi alt-savını açar, somutlaştırır (R-150) ve gerekirse H3'lere bölünür (R-30: word count > 200 olan H2 → ≥2 H3). Bölümler arası **mantıksal akış** zorunlu: her H2 bir öncekinin üstüne biner (giriş → bağlam → derinleşme → sonuç), kopuk / sıra-bağımsız bilgi parçaları değil. İçerik bir "argüman yayı" izler, rastgele başlık torbası değil.

**Rationale.** "Başlık basıp geçme" Principle 3'ün birinci cheap-content sinyalidir (AI H2'leri başlık yapıp tek paragraf yazar). Akışsız bölümler okuru kaybeder (dwell-time düşer) ve AIO için tutarlı bir cevap iskeleti sunmaz. Derinlik + akış, "rakipten daha kaliteli" ölçütünün (spec §8) okur-tarafı kanıtıdır — yapı skoru rakibi geçse bile sığ işleme içeriği zayıf bırakır.

**Enforcement.** new-blog render-time: her H2 min işleme (≥ paragraf + somutluk; uzun H2'de R-30 H3 gate) + bölüm geçiş tutarlılığı. Ölçüm: B2 kapı motoru §6 **depth** kapısı (yüzeysel / tek-paragraf H2 = 0) + §9 yapı matematiği bu kuralın pozitif karşılığıdır (`scripts/production/quality_gates.py`). Yüzeysel bölüm → depth RED → derinleştir.

**Failure mode.** Yüzeysel / tek-paragraf H2 veya kopuk akış → depth kapısı RED (bölüm derinleştir / yeniden sırala) → 3 re-write turu cap → AMBER (spec §8).

**Cross-link.** → R-30 (H3 gate + heading keyword density), R-150 (somut örnek — derinliğin yapı taşı), spec §9 yapı matematiği + §8 kalite ölçümü, [content-quality](content-quality.md#foundational-principles) (Principle 3).

---

## Cross-References

- → [content-quality](content-quality.md#foundational-principles) — 3 üst-prensip (Principle 1 truth-verifiable, 2 profile-aware, 3 anti-cheap-content); craft katmanı bunlara tabidir
- → [content-eeat-discipline](content-eeat-discipline.md) — EEAT görünür kanıt (R-28 byline, R-124 expert-review); craft sesi bunun üstüne biner
- → [content-seo-discipline](content-seo-discipline.md) — AEO cevap-önce intro (R-01 / R-29 / R-101), H3 gate (R-30)
- → [content-llm-discipline](content-llm-discipline.md) — AIO `answer_points` + summary footer (R-101)
- → [single-source-of-truth](single-source-of-truth.md) — `brand_identity` + experience/research bank tek yerde
- → spec `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` §5 (yazım katmanı) + §6 (kapı motoru) + §8 (kalite ölçümü) + §9 (yapı matematiği)

## Enforcement (Plugin-Level)

- F4 orkestratör (`scripts/production/new_blog.py` silahlan → yaz → kapı döngüsü) ve production skill'leri (new-blog, sonra revise-content, faq-optimization) bu rules dosyasını consume eder.
- Her craft kuralı (R-149..R-153) B2 kapı motorunun (`scripts/production/quality_gates.py` §6) bir kapısına eşlenir: **R-149 → voice + aeo**, **R-150 → depth**, **R-151 → voice**, **R-152 → originality**, **R-153 → depth**. Kapı RED ise re-write turu çalışır (spec §8; max 3 tur → AMBER, sonsuz döngü yok).
- **P0 Doğruluk her craft kuralının ÜSTÜNDEDİR**: özgünlük / örnek / empati / deneyim GERÇEK olmalı; uydurma craft = P0 RED (Principle 1, spec §6 P0↔Gap kararı).
