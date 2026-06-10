---
name: Measurement Discipline
status: enforced
applies_to: [plugin]
spec_section: "measurement"
applied_to_skills: [quick-wins, monthly-report, monitoring-weekly, aio-competitor-map]
since: "2026-06-10"
source: docs/superpowers/plans/amo/2026-06-10-gap-specs-measurement-ai.md (GAP-M1..M4)
---

# Measurement Discipline

Bu doc, SEO ölçüm katmanının (core-update takvimi, müdahale-vs-kontrol kohortları,
sürümlü sabitler, AI Overview varlığı, haftalık anomali istatistiği) dürüstlük
disiplinini tanımlar. **Foundational Principles** (3 üst-prensip) →
[content-quality](content-quality.md#foundational-principles) — burada tekrar
yazılmaz (DRY). Özellikle **Principle 1 (Truth-Verifiable)**: hiçbir ölçüm
çıktısı uydurulmaz; veri yoksa "yetersiz veri" dürüstçe raporlanır, hayali bir
delta/alarm üretilmez.

**Rule-id allocation note (ADR-038 history-stable).** Bu küme `R-137..R-141`
id'lerini sahiplenir. Ölçüm spec'i (GAP-M1..M4) bağımsız taslakta `R-125..R-129`
yazmıştı; çakışma çözümü (`§R-MAP`, 2026-06-10 unified dispatch planı) bunları
yeniden numaralandırdı:
`R-125→R-137`, `R-126→R-138`, `R-127→R-139`, `R-128→R-140`, `R-129→R-141`.
Tüm SKILL.md atıfları ve test grep-sentinel'leri yeni id'leri kullanır.

**Enforcement timeline.** Beş kuralın tamamı *yazılı ve enforced*. Çalışan kod
dağıtımı dalgalara yayılır: **R-137** (takvim örtüşmesi), **R-139** (sürümlü
sabitler — politika beyanı), **R-141** (median+MAD anomali) bu dalgada
(Wave 1a) bağlanır; **R-138** (kohort etiketleme) ve **R-140** (AIO varlığı)
kural metni burada sabitlenir, enforcement kodu quick-wins/aio-competitor-map
tarafında (Wave 1b/2) iner.

---

## Rules

### R-137: Core-Update Overlap Annotation

**Statement.** Her periyodik rapor (aylık, haftalık) penceresinin Google Search
**Ranking** güncellemeleriyle (`service_name == "Ranking"`; core/spam/ranking)
örtüşmesini, **7 günlük settling buffer** dahil, açıkça annotate ETMELİDİR.
Örtüşen bir pencerede trafik/sıralama deltaları, bu annotation olmadan, ne motor
çalışmasına ne de güncellemenin kendisine atfedilemez. Takvim kaynağı tek:
resmi Google Search Status Dashboard JSON akışı
(`https://status.search.google.com/incidents.json`), `service_name=="Ranking"`
filtresiyle; üçüncü-parti update tracker'ları (Semrush sensor vb.) KULLANILMAZ.

**Rationale.** Google'ın kendi rehberi rollout tamamlanana (`end`) kadar etki
değerlendirmesi yapmamaktır; core update'ler ~2 hafta sürer. Mayıs 2026 core
update 2026-06-02'de bitti → Haziran rapor pencerelerinin çoğu settling buffer'a
düşer, dolayısıyla annotation olmadan her rapor **şu an** yanlış-atfetme riski
taşır.

**Enforcement.** `scripts/reporting/update_calendar.py` (`load_calendar` engine
seed ∪ workspace overlay; `overlaps(period_start, period_end, updates,
settle_buffer_days=7)`); seed `google-update-calendar.json` +
`schemas/google-update-calendar.schema.json`; refresh
`scripts/maintenance/refresh_update_calendar.py` (pure parse/merge, ağ yok).
Tüketiciler: `monitoring-weekly` (R-141 anomali cap'i), `monthly-report`
(`measurement_context` bölümü — GAP-M-W2). → [time-discipline](time-discipline.md)
(UTC `Z` storage).

**Failure mode.** Annotation eksikse rapor RED/AMBER değil, **dürüstlük ihlali**
(Principle 1) — overlap penceresinde atıf cümlesi yasak.

### R-138: Intervention Cohort Tagging

**Statement.** Her quick-wins tespit koşusu bir **treated + control** kohort
snapshot'ı (aynı bant, dokunulmamış kontrol sorguları) kalıcı yazMALIDIR;
quick-wins hakkındaki sonuç iddiaları **treated-vs-control farkı** olarak
raporlanır, asla ham treated deltası olarak değil. n<30'da p-value/anlamlılık
tiyatrosu yasak; |fark| < 10pp ⇒ `indistinguishable` ("n<30 — yön gösterici").

**Rationale.** Dokunulmamış bir kontrol setiyle karşılaştırma, motor etkisini
mevsimsellik/genel trend/güncelleme gürültüsünden ayıran en hafif dürüst
standarttır. Ham treated deltası, motorun hak etmediği yükselişleri (veya
suçsuz olduğu düşüşleri) ona yazar.

**Enforcement.** (Wave 1b/2'de kod iner.) `scripts/discovery/quickwins_transform.py`
`control_cohort` çıktısı + `skills/discovery/quick-wins/SKILL.md` Step 7b kohort
snapshot (`_state/metrics/quickwin-cohorts/{date}-cohort.json`) + provenance
event (`event_kind=provenance, source.kind=tool_computed, operation=staging`);
`scripts/reporting/intervention_outcome.py` treated−control farkı +
`monthly-report` entegrasyonu. Bu kuralın metni şimdi (Wave 1a) sabitlendi.

**Failure mode.** Kohort snapshot'ı yoksa quick-wins sonuç iddiası RED (atıf
yapılamaz).

### R-139: Versioned Measurement Constants

**Statement.** Ölçüm eğrileri ve indirim faktörleri — **CTR eğrileri**, **AIO
discount faktörleri**, anomali eşik *verileri* — provenance alanlı **sürümlü
veri dosyalarında** yaşar (örn. `ctr-curve.json` + `schemas/ctr-curve.schema.json`,
`google-update-calendar.json`); bu sabitlerin Python/SKILL gövdelerine literal
kopyalanması yasaktır (grep-sentinel ile test edilebilir).

**Rationale.** Tek-kaynak (→ [single-source-of-truth](single-source-of-truth.md)):
bir CTR eğrisi gömülü literal olduğunda, çalışma yenilendiğinde (yeni çalışma
yayınlandığında) kod ile dosya sürüklenir; provenance kaybolur, "bu sayı nereden
geldi?" cevapsız kalır.

**Enforcement.** Grep-sentinel: `quickwins_transform.py`/SKILL gövdesinde herhangi
bir eğri sabiti (ör. `0.398`/`0.703`) worked-example fence dışında bulunamaz
(GAP-M3, Wave 1b). **Kapsam notu:** bu kural *eğri/indirim verisini* hedefler —
istatistiksel **yöntem sabitleri** (NIST modified-z normalizasyon sabiti
`0.6745 = Φ⁻¹(0.75)`, eşik `k=3.5`) bu kapsamda DEĞİLDİR; bunlar
`scripts/reporting/weekly_anomaly.py`'de belgeli, kwargs/cascade ile
override-edilebilir yöntem parametreleridir (gömülü-ayarlanamaz sihirli sayı
değil).

**Failure mode.** Versiyonsuz gömülü eğri sabiti = RED (grep-sentinel FAIL).

### R-140: AIO Presence Recording Discipline

**Statement.** AI Overview varlık kaydında MCP-sync tespiti yalnızca `present`
veya `not_detected` iddia EDEBİLİR — asla `absent` (wrapper
`load_async_ai_overview` parametresini sunmaz; asenkron AIO'lar `not_detected`
döner, yokluk KANITLANAMAZ). `unchecked ≠ not_detected`. AIO-`present` bir sorgu
üzerindeki herhangi bir CTR/uplift iddiası AIO indirimini (R-139 eğrisi) taşıMALIDIR.
Citation kanıtı yalnızca `references[]` payload'ından gelir, asla organic
sonuçların schema-markup'ından çıkarımla değil.

**Rationale.** AIO varlığı bir kazanımın beklenen CTR'ını kabaca yarıya düşürür
(Ahrefs 2026-02: pos1 −58% … pos10 −19%); yokluğu kanıtlanamayan bir sinyali
"yok" saymak ya da schema-markup'ı "AIO citation" kanıtı sanmak iki ayrı uydurma
biçimidir.

**Enforcement.** (Wave 1b'de kod iner.) `skills/discovery/aio-competitor-map/SKILL.md`
`serp_aio` parse (`references[]`) + `not_detected` enum'u + "absent" yasağı
(grep-sentinel); `skills/discovery/quick-wins/SKILL.md` `aio_presence` sütunları.
Bu kuralın metni şimdi (Wave 1a) sabitlendi.

**Failure mode.** `absent` iddiası veya schema-markup'tan citation çıkarımı = RED.

### R-141: Weekly Anomaly — Median+MAD Modified Z

**Statement.** Haftalık GSC anomali tespiti, **median + MAD modified z-score**
(NIST/Iglewicz–Hoaglin: `M = 0.6745·(x − median)/MAD`, bayrak `|M| ≥ 3.5`)
kullanMALIDIR; yüzde **ve** mutlak taban (floor) eşikleriyle birlikte (düşük
hacimde trivia bastırma) ve **≥6 tam ISO hafta** baz çizgisi üzerinde. n<30
haftalık agregatta **σ-tabanlı** (standart-sapma) eşikler skill/script'lerde
YASAKTIR. Takvim Ranking penceresiyle (R-137, settling buffer dahil) örtüşen
alarmlar **AMBER**'a cap'lenir ve attribution caution taşır; <6 hafta ⇒
`insufficient_history` dürüst render (alarm değil).

**Rationale.** n≈8'de örnek standart sapma kendisi aşırı gürültülüdür ve test
edilen anomalinin kendisi tarafından şişirilir (maskeleme); 5σ ya hiç ateşlemez
(ölü alarm) ya da SD-tahmin gürültüsünden ateşler. MAD'in %50 breakdown noktası
vardır — tek kötü hafta eşiği zehirleyemez. Bu, eski "5-standart-sapma /
trailing-8-hafta-ortalama" placeholder'ını (hem istatistiksel olarak anlamsız
hem de snapshot `gsc_performance` sheet'ine karşı uygulanamaz) değiştirir.

**Enforcement.** `scripts/reporting/weekly_anomaly.py` `detect()` (saf,
deterministik; tarih = `current_iso_week` argümanı, duvar-saati yok); haftalık
geçmiş `scripts/ingestion/gsc_pull.py` `aggregate_iso_weeks` +
`append_weekly_ledger` (`_state/metrics/gsc-weekly.jsonl`, append-only);
`skills/reporting/monitoring-weekly/SKILL.md` Block 3 (DURUR #5: severity=RED ⇒
ikinci audit satırı). → [time-discipline](time-discipline.md) (UTC ISO hafta).

**Failure mode.** σ-tabanlı haftalık eşik veya <6 haftada uydurma alarm = RED.
