# Competitive Content Engine (CCE) — Tasarım Dokümanı

> **Status: APPROVED DESIGN — ready for implementation planning.**
> Brainstorm edildi + onaylandı 2026-06-22 (Süleyman). Hedef: `new-blog` (ve
> sonra `revise-content` + `faq-optimization`) skill'lerinin ürettiği içeriğin
> **her zaman ilk-10 organik rakipten ölçülebilir biçimde daha kaliteli**
> çıkmasını garanti eden hibrit (kod-ölçer + Claude-yazar) motor.
> Manager/worker akışı: bu doküman worker session'ların **tek doğruluk
> kaynağıdır**.

## 1. Problem (neden var)

`skills/production/` altındaki 5 skill (`new-blog`, `revise-content`,
`faq-optimization`, `content-remediation`, `generate-images`) `status: wip` ve
**hiçbirinin runtime'ı yok** (`scripts/production/` = 0 Python). İçerik
üretimi tamamen agent'ın o anki yorumuna kalıyor. Operatör (Süleyman)
gözlemiyle üç somut şikâyet:

1. **Ruhsuz / AI gibi** — teknik olarak doğru ama broşür tonu; empati, marka
   sesi, hikâye yok.
2. **Sığ / generic** — bilgi doğru ama özgün hiçbir şey yok; "herhangi bir
   rakip de yazabilir" (kanıt: `dentnotion/.../izmir-gaziemir-implant-tedavisi`
   — teknik kusursuz, özgün sıfır).
3. **Tutarsız** — bazı içerik iyi, bazısı zayıf; tekrarlanabilir bir taban yok.

Kök neden iki katmanlı: (a) **mekanik** — kuralları uygulayan motor yok →
tutarsızlık; (b) **tasarım** — mevcut content rule'ları (R-01..R-148) tamamen
"şunu YAPMA" yasakları; "nasıl HARİKA yazılır" pozitif rehberi yok → kurala
uysa bile ruhsuz/sığ çıkar.

## 2. Hedef + başarı kriteri

**Hedef.** Üretilen her içerik, o sorgunun ilk-10 organik rakibini
**kapsam + yapı + özgünlük + AEO** boyutlarında ölçülebilir biçimde geçmeden
"hazır" sayılamaz.

**Başarı kriteri (ölçülebilir, §8'de tam tanım).**
- **Kapsam:** rakiplerin değindiği her alt-başlık/soru/varlık bizim içerikte
  **kanıtlanabilir** biçimde var (gap = 0) — uydurma OLMADAN.
- **Yapı:** anlamlı tablo + liste sayısı ≥ en iyi rakip **+1**; H2/H3 dengesi
  sağlıklı.
- **Özgünlük:** rakiplerin hiçbirinde olmayan **≥1 gerçek özgün değer**.
- **AEO:** intro = sorunun direkt cevabı; Google AI Overview'ın değindiği her
  nokta içerikte işlenmiş.
- **Doğruluk (mutlak, hepsinin üstünde):** uydurma kaynak/stat/quote = 0.

## 3. Mimari — hibrit 3-aşamalı döngü

Çekirdek ilke: **Claude yazar, kod "rakipten iyi mi?" diye ölçer, geçmezse
geri yollar.** Kod ölçülebilir kaliteyi (kapsam, yapı, AEO) garanti eder;
Claude ölçülemeyen kaliteyi (ruh, derinlik, akıcı Türkçe) üretir.

```
┌─────────────────────────────────────────────────────────────┐
│ 1) SİLAHLANMA (kod)   Scrapling×10 + DFS + GSC → Brief Paketi  │
│        ↓                                                       │
│ 2) YAZIM (Claude)     Brief'i al → ruhlu + derin + AEO içerik  │
│        ↓                                                       │
│ 3) KAPI (kod)         7 kapı ölç → hepsi yeşil mi?             │
│        ├── HAYIR → eksik raporu → (2)'ye geri dön (re-write)   │
│        └── EVET  → içerik "hazır" + provenance yaz             │
└─────────────────────────────────────────────────────────────┘
```

Döngü, tüm kapılar yeşil olana kadar (hard cap: N tur, §8) tekrarlar.

## 4. Bileşen A — Silahlanma Motoru (kod, yazımdan ÖNCE)

Konum: `scripts/production/` (yeni klasör). Çıktısı tek bir **Brief Paketi**
JSON (§7 şema). Alt-bileşenler:

### 4a. `competitor_recon.py` — rakip kapsama haritası
- Girdi: `primary_keyword`, market/locale (proje config'ten), serve-location
  doğrulaması (DFS Method-C disiplini, `feedback_dfs_wrapper_tr_bug` dersi).
- DFS `serp_organic_live_advanced` (depth=10) → ilk-10 organik URL.
- Her URL için `mcp__ScraplingServer__stealthy_fetch` (Tier-1, **zorunlu** —
  eski "optional, top-3" davranışı kaldırılıyor) → DOM parse:
  - H2/H3 başlık ağacı
  - cevaplanan sorular (FAQ + soru-başlıklar + PAA eşleşmeleri)
  - kapsanan varlıklar/konular (entity/terim çıkarımı)
  - **anlamlı** tablo sayısı + liste sayısı (boş/2-satır yapı sayılmaz)
  - kelime sayısı
- Çıktı: `competitors[]` envanteri + birleşik **kapsama kümesi**.

### 4b. `keyword_aio_intel.py` — keyword + AI Overview
- DFS keyword sinyalleri: `dataforseo_labs_google_keyword_suggestions`
  (substring — güvenilir), `keyword_overview`, `search_intent`.
  `keyword_ideas` **semantik furniture/relevance filtresinden geçmeden**
  kullanılmaz (`feedback_dfs_keyword_ideas_ng_noise` dersi).
- **AI Overview analizi:** sorgunun AIO'su DFS SERP advanced'in `ai_overview`
  öğesinden (varsa) + gerekirse `ai_optimization` toollarından çekilir →
  AIO'nun değindiği **answer_points[]** + gösterdiği **cited_sources[]**.
  AIO yoksa: `aio.present=false`, answer_points boş (kapı koşulu gevşer).
- Çıktı: `keyword_set[]` + `aio{}`.

### 4c. GSC sinyali
- Mevcut `gsc-pull` çıktısı (`master.xlsx`) + gerekirse
  `mcp__gsc__search_analytics` → o URL/konudaki gerçek sorgular + mevcut
  pozisyon. Read-only.

### 4d. `build_brief.py` — gap hesabı + birleştirme
- `gap` = (rakip kapsama kümesi) − (bizim mevcut/planlı içerik) → kapsanması
  gereken başlık/soru/varlık listesi.
- `structure_ceiling` = rakip yapı maksimumları (tablo/liste/H2).
- Hepsini §7 şemasına serialize eder.

## 5. Bileşen B — Yazım Katmanı (Claude, "ruh" burada)

`new-blog` skill'i Brief Paketini alır ve yazar. İki yeni girdi:

1. **Brief Paketi** (§7) — ne kapsanacağı, AIO hedefleri, yapı tavanı.
2. **Craft rehberi** (yeni `rules/content-craft-discipline.md`, §11) — mevcut
   "yasak" kurallarının eksik tamamlayıcısı: **pozitif yazım rehberi**
   (pain-mirror/empati girişi, somut örnek, profil-uygun ton, hikâye, marka
   sesi). YMYL'de "güven bölgesi" tonu (empati+netlik, satışçılık değil);
   pazarlama yüzeyinde cesur ton (`feedback_marketing_surface_boldness`).

Yazım kuralları (mevcut + güçlendirilen):
- Intro = sorunun **direkt cevabı**, self-contained, AEO uyumlu (R-01/R-29/R-101).
- Gövde **gap listesindeki her maddeyi** işler — ama **kanıtlanabilir
  şekilde**; kaynağı yoksa o noktayı dürüstçe atlar, ASLA uydurmaz (§6 P0).
- Yapı matematiği (§9) uygulanır.
- Bank-driven özgünlük (R-105/R-114/R-119) → Özgünlük kapısını besler.

## 6. Bileşen C — Kapı Motoru (kod ölçer, geçmezse RED)

Konum: `scripts/production/quality_gates.py`. Üretilen içeriği Brief'e karşı
ölçer. **8 kapı; Doğruluk (P0) hepsinin üstünde.**

| # | Kapı | Ölçüm | Geçme şartı | RED davranışı |
|---|------|-------|-------------|----------------|
| P0 | **Doğruluk** | Her stat/quote/kaynak → fact-check (R-44/R-52/R-105) | Uydurma = 0 | İçerik discard, claim revize. **Mutlak — gap'in üstünde.** |
| 1 | **Gap** | `brief.gap.must_cover` ⊆ içerik (başlık+soru+varlık) | Eksik = 0 **veya** eksik madde "kaynak yok → dürüst atlandı" diye loglu | Eksik+kaynaklı madde → re-write |
| 2 | **Yapı** | anlamlı tablo+liste sayısı; H2/H3 oranı | ≥ `structure_ceiling`+1; uzun H2'de ≥2 H3 (R-30) | Eksik yapı → re-write |
| 3 | **Derinlik** | Her H2 gerçekten işlenmiş mi (thin tarama) | Yüzeysel/tek-paragraf H2 = 0 | Sığ bölüm → derinleştir |
| 4 | **AEO** | intro cevap-önce mi; `aio.answer_points` kapsandı mı | intro direkt cevap + tüm answer_points işlenmiş | re-write |
| 5 | **Ruh** | AI-imza blocklist (R-118) + jenerik açılış | blocklist density ≤ eşik; klişe açılış yok | humanize pass |
| 6 | **Özgünlük** | Rakip kümesinde olmayan ≥1 gerçek değer | ≥1 özgün değer (veri/araç/vaka/karşılaştırma) | özgün değer ekle |
| 7 | **Görsel/Şema** | JSON-LD @graph valid + hero görsel ref + tablo zenginliği | @graph geçerli + hero var | düzelt |

**P0 ile Gap çatışması (kritik karar).** Gap kapısı "rakibin her konusunu
kapsa" der; bu Claude'u uydurmaya itebilir. Çözüm: **Gap zorunluluğu mutlak
DEĞİL.** Bir gap maddesi ancak kanıtlanabilir kaynak/veriyle kapatılır;
kaynak yoksa madde "dürüstçe atlandı" olarak `change_log`'a yazılır ve Gap
kapısını YİNE geçer. Doğruluk (P0) her zaman kazanır.

## 7. Brief Paketi — veri şeması

```json
{
  "topic": { "primary_keyword": "...", "content_type": "guide|comparison|listicle|research|tutorial|review", "locale": "tr-TR", "market": "TR" },
  "keyword_set": [ { "kw": "...", "volume": 0, "intent": "Informational", "source": "dfs_suggestions|gsc" } ],
  "aio": { "present": true, "answer_points": ["..."], "cited_sources": ["url"] },
  "competitors": [ { "url": "...", "h2_h3": ["..."], "questions": ["..."], "entities": ["..."], "tables": 0, "lists": 0, "word_count": 0 } ],
  "gap": { "must_cover_headings": ["..."], "must_answer_questions": ["..."], "must_mention_entities": ["..."] },
  "structure_ceiling": { "tables": 0, "lists": 0, "h2": 0, "best_competitor_word_count": 0 },
  "gsc": { "real_queries": ["..."], "current_position": null },
  "generated_at": "ISO-8601", "cost_note": "no-cap; fresh top-10 her çağrı"
}
```

## 8. "Rakipten kaliteli" — somut ölçüm + döngü kontrolü

- **Kapsam skoru** = |içerikte kapsanan gap maddesi| / |toplam gap maddesi| =
  %100 (kaynaksızlar "dürüst atla" olarak sayılır, uydurma yok).
- **Yapı skoru** = (içerik anlamlı tablo+liste) − (en iyi rakip) ≥ +1.
- **Özgünlük** = ≥1 (boolean+kanıt).
- **AEO** = answer_points kapsama %100 + intro cevap-önce = true.
- **Döngü cap:** en fazla **3 re-write turu**; 3'te de bir kapı kırmızıysa →
  AMBER, operatöre net eksik raporu (sonsuz döngü yok).

## 9. Yapı matematiği (tablo/liste kararı)

Üç katman, sırayla:
1. **İçerik tipi tabanı.** `content_type=comparison` → ≥1 karşılaştırma
   tablosu zorunlu; `tutorial/guide` → ≥1 adım tablosu/numaralı liste;
   `listicle` → sayılı liste.
2. **Semantik tetikleyici.** Bir bölümde 3+ karşılaştırılabilir veri noktası
   (fiyat/süre/ölçü/özellik) → tablo; sıralı süreç → numaralı liste; eşdeğer
   seçenekler/kriterler → madde işareti. (Kelime sayısı DEĞİL — bilginin
   şekli belirler.)
3. **Rakip tavanı.** Anlamlı tablo+liste sayısı ≥ en iyi rakip +1.
   "Anlamlı" = gerçek bilgi taşıyan; doldurma/2-satır yapı sayılmaz.

## 10. Maliyet + tazelik politikası

**Maliyet sınırı YOK** (operatör kararı: "her içerik çok kıymetli"). Her
içerik üretimi **taze** top-10 tarama yapar; önbellek kullanılmaz (bayat
rakip verisi riski). DFS/Scrapling/GSC çağrıları kalite için serbest.

## 11. Mevcut sistemle hizalama

- **Korunan:** new-blog'un 12-step iskeleti, R-22 fragment, R-78..R-83
  JSON-LD @graph, R-35 meta pixel, WCAG, plugin-agnostik `pse-` prefix,
  events.jsonl provenance, F-1 read-only master.xlsx.
- **Güçlendirilen:** Step 3 SERP (→ depth=10 zorunlu), Step 4 Scrapling
  (optional/top-3 → **zorunlu/top-10**), Step 5 AIO (zayıf → gerçek
  answer_points analizi), R-30 H3 gate (→ §9 yapı matematiği), Principle 3
  (→ ölçülen kapı motoru).
- **Yeni:** `scripts/production/` runtime (4 modül + quality_gates +
  orkestratör), `rules/content-craft-discipline.md` (pozitif yazım rehberi),
  Özgünlük + Görsel/Şema kapıları.
- **R-token disiplini:** yeni craft kuralları **mevcut max R-token'dan sonra**
  başlar (şu an R-148 → **R-149+**; worker `grep` ile doğrular). Mevcut
  R-01..R-148'e dokunulmaz (`project_template_r_token_resolution` dersi).

## 12. Kapsam + aşamalar (batch temeli)

**Önce yalnız `new-blog`.** Kanıtlandıktan sonra aynı motor `revise-content`
+ `faq-optimization`'a taşınır (kapı motoru + brief paketi yeniden kullanılır).

| Faz | İçerik | Çıktı |
|-----|--------|-------|
| F1 | Silahlanma motoru (`competitor_recon`, `keyword_aio_intel`, `build_brief`) + testler | Brief Paketi üretimi |
| F2 | Kapı motoru (`quality_gates.py`, 8 kapı) + testler | PASS/RED ölçüm |
| F3 | Craft rehberi (`content-craft-discipline.md` R-125+) + testler | Pozitif yazım katmanı |
| F4 | Orkestratör (`new_blog.py` silahlan→yaz→kapı döngüsü) + new-blog SKILL.md güncelle + testler | Çalışan new-blog |
| F5 | Gerçek konu kanıt testi (rakibi geçtik mi ölç) | Kabul kanıtı |

## 13. Test + kabul

- Her modül TDD (RED → GREEN); hermetik (canlı MCP olmadan fixture'la test).
- Kapı motoru: bilinen "kötü" (thin/generic) içerik → RED; bilinen "iyi"
  içerik → PASS (golden test).
- F5 kabul: gerçek bir Türkçe konuda üret → 8 kapı yeşil + manuel operatör
  onayı.
- Plugin-agnostik grep guard (proje slug hardcode yasağı) korunur.

## 14. Açık kararlar / riskler

- **R1:** Entity/soru çıkarımı (4a) ne kadar kod, ne kadar Claude? → Karar:
  Scrapling DOM'dan deterministik çıkarım (başlık/tablo/liste = kod);
  semantik gap eşleştirme (anlamca aynı mı?) Claude-destekli helper.
- **R2:** AIO her sorguda yok. → `aio.present=false` ise AEO kapısı yalnız
  "intro cevap-önce"ye düşer (answer_points koşulu atlanır).
- **R3:** Re-write döngüsü maliyeti. → Operatör onayı: sınır yok; yalnız
  sonsuz-döngü guard (3 tur cap).
- **R4:** Craft rehberi "ruh"u nasıl ölçülür? → Kısmen ölçülebilir (R-118
  blocklist, klişe açılış regex); tam "ruh" Claude + operatör review.
