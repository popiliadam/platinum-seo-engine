---
name: refresh-audit
description: |
  Use when: kullanıcı "verileri freshle", "veri tazele", "GSC + SF + DFS
  yenile", "master excel yenile", "tüm veriyi güncelle", "pillar cluster
  yapısını kontrol et", "konu otoritesi denetimi", "yamyamlık kontrolü",
  "aktif taskları revize et", "taskları günlere dağıt", "adstark taskları
  güncelle", "tam SEO audit", "refresh audit" der ya da /pseo-refresh çağırır.
  Also use when: aktif projenin master.xlsx'i mevcut; GSC / SF (tam 24
  rapor) / DFS (eksiksiz) / Scrapling MCP kaynaklarının tamamı bir arada
  tazelenip (append-only, transaction.py backup) ardından TAM discovery
  denetim suite'i (teknik + on-page + schema + robots + hreflang + facet +
  topical otorite + cannibalization) çalıştırılıp adstark CRM ↔ master.xlsx
  aktif taskları MUTABAKATA getirilecek + günlere dengeli DAĞITILACAK
  (dual-write disiplini); aynı bakım dizisi birden çok projede kullanılacak.
  Do not use when: tek bir ingestion kaynağı yeter (gsc-pull, sf-import,
  dfs-pull, scrapling-ops — ayrı skill'ler); yalnız rapor (monthly-report);
  yalnız drift (drift-check); yalnız master_task (master-task-sync); İÇERİK
  ÜRETİMİ / publish / indexing / remediation gerekiyor (SEO tarafı
  ANALİZ-ONLY; task-write fazı consent ile yazar). Master.xlsx yokken
  çağırma; init-project önce çalışmalı (DURUR #1).
version: "2.1"
status: active
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/master.xlsx + project.config.json. Boşsa shared/active.json'dan (session binding öncelikli)."
  days_back:
    type: integer
    required: false
    default: 90
    description: "GSC recent pencere (gün). Previous pencere eşit uzunlukta; content-decay bunu kullanır."
  refresh_sources:
    type: array
    required: false
    default: ["gsc", "sf", "dfs", "scrapling"]
    description: "Tazelenecek kaynaklar. MCP kapalı/erişilemezse SKIP + flag (audit INCOMPLETE işaretlenir)."
  audit_depth:
    type: string
    required: false
    default: "full"
    description: "'full' = TAM discovery suite (teknik+on-page+schema+robots+hreflang+facet+topical+cannibalization+decay+gaps+internal-links). 'lite' = cannibalization + content-decay + drift-check (cannibalization her iki modda da ZORUNLU)."
  reconcile_tasks:
    type: boolean
    required: false
    default: true
    description: "adstark ↔ master task mutabakatı + günlere dağıtım (Faz 7)."
  apply_task_changes:
    type: boolean
    required: false
    default: false
    description: "false = task mutabakatı YALNIZ diff önerir + DURUR. true = consent sonrası dual-write uygular. Consent olmadan true varsayma."
  tasks_per_day:
    type: integer
    required: false
    default: 4
    description: "Faz 7 gün-dağıtımı kapasitesi. Mevcut adstark yükü (today_and_overdue + upcoming_deadlines) üstüne, günde bu sayıyı aşmayacak şekilde boş iş günlerine yayar."
  dry_run:
    type: boolean
    required: false
    default: false
    description: "true = TÜM fazlar salt-okunur; yazım adımları 'PLANNED' raporlanır — tam prova."
  staleness_hours:
    type: integer
    required: false
    default: 20
    description: "Bir kaynak son N saatte tazelendiyse SKIP + flag. 0 = kapalı (zorla tazele). NOT: audit_depth=full iken DFS/SF için önerilen 0 (tam güncel resim)."
outputs:
  - "master.xlsx#gsc_performance / crawl_* / directives / structured_data / tech_seo / on_page_audit / schema / cluster_keywords / topical_map / cannibalization / content_decay / dfs_ranked_keywords / backlinks / master_task (delege append-only writer'lar)"
  - "adstark task updates + gün-dağıtımı (apply_task_changes=true + consent + !dry_run; dual-write)"
  - "outputs/reports/{date}-refresh-audit.md (birleşik audit + task mutabakat + gün-planı)"
  - "_state/events.jsonl · _state/metrics/refresh-audit.jsonl · _state/coverage/{run_id}.json · _state/locks/refresh-audit-{slug}.lock"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "gsc-pull / sf-crawl-orchestrator / dfs-pull / scrapling-ops (ingestion)"
  - "tech-audit / on-page-audit / schema-audit / robots-policy-audit / hreflang-audit / facet-nav-audit / cluster-map / topical-map / cannibalization / content-decay / content-gaps / internal-links / competitive-analysis / gbp-audit / geo-analysis / aio-competitor-map (discovery+planning; local & AI-search koşullu)"
  - "master-task-sync:master.xlsx#master_task"
produces:
  - "monthly-report"
  - "mark-done"
  - "whats-next"
triggers:
  manual: ["/pseo-refresh"]
  natural_language: |
    "verileri freshle", "veri tazele", "GSC SF DFS yenile", "master excel yenile",
    "tam SEO audit", "konu otoritesi denetimi", "yamyamlık kontrolü",
    "aktif taskları revize et", "taskları günlere dağıt", "refresh audit"
  hooks: []
  scheduled:
    - cron: "0 7 1 * *"
      mode: "report-only"
mcp_tools:
  required:
    - "mcp__gsc__enhanced_search_analytics"
    - "mcp__gsc__search_analytics"
  optional:
    - "mcp__gsc__index_inspect"
    - "mcp__gsc__detect_quick_wins"
    - "mcp__sf__sf_crawl"
    - "mcp__sf__sf_crawl_progress"
    - "mcp__sf__sf_export_crawl"
    - "mcp__sf__sf_generate_bulk_export"
    - "mcp__dataforseo__dataforseo_labs_google_keyword_overview"
    - "mcp__dataforseo__dataforseo_labs_bulk_keyword_difficulty"
    - "mcp__dataforseo__dataforseo_labs_google_ranked_keywords"
    - "mcp__dataforseo__dataforseo_labs_google_relevant_pages"
    - "mcp__dataforseo__serp_organic_live_advanced"
    - "mcp__dataforseo__backlinks_bulk_referring_domains"
    - "mcp__dataforseo__backlinks_bulk_spam_score"
    - "mcp__ScraplingServer__stealthy_fetch"
    - "mcp__ScraplingServer__bulk_stealthy_fetch"
    - "mcp__adstark__list_customers"
    - "mcp__adstark__get_customer"
    - "mcp__adstark__list_tasks"
    - "mcp__adstark__today_and_overdue"
    - "mcp__adstark__upcoming_deadlines"
    - "mcp__adstark__update_task"
    - "mcp__adstark__move_task"
    - "mcp__adstark__complete_task"
    - "mcp__adstark__reopen_task"
    - "mcp__adstark__add_task"
    - "mcp__adstark__board_summary"
budget:
  uses_paid_mcp: true
  estimated_credits: 0
  notes: "DFS: AUDIT COMPLETENESS ÖNCELİKLİ — bütçe aşımında SKIP/truncate YAPMA; uyar + devam, oversized ise consent iste (asla eksik keyword evreni döndürme). Scrapling bütçe-farkında (top-20 cluster + top-5 rakip sınırlı). adstark ücretsiz."
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
  notes: "SEO veri/denetim ANALİZ-ONLY. Master yazımları append-only + transaction.py. Faz 7 YAZIM içerir ama default propose-only + consent. dry_run=true iken hiç yazmaz."
---

# refresh-audit — çok-kaynaklı tazeleme + TAM SEO audit + adstark↔master task mutabakat/dağıtım orkestratörü

Orkestratördür: yeni transform yazmaz, mevcut skill'leri sabit dizide koşturur ve
tek birleşik rapor üretir. **Amaç: eksiksiz audit** — hiçbir faz/adım sessizce atlanmaz.

## Yürütme stratejisi (v1.6 — context ekonomisi + hız)
- **Uzun kutbu önce başlat:** SF crawl en uzun adım → Faz 2 crawl'ı ERKEN tetikle; arka planda tararken Faz 1 GSC'yi yürüt.
- **Disjoint-sheet paralel delege:** Ağır ingestion (SF/DFS/Scrapling) ve Faz 5 audit dalgalarını AYRI sheet'lere yazacak şekilde bölüp paralel subagent'lara ver — transaction.py workbook kilidi commit'leri güvenle SERİ yapar (kanıtlı: 6 paralel writer, 0 bozulma). **Aynı sheet'e iki writer YASAK** (disjoint sahiplik). Devasa MCP JSON'ları subagent context'inde kalır, orkestratör hafif.
- **Büyük MCP çıktısı context'e ALINMAZ:** raw-inbox-first DOSYAYA → jq/python ile işle (GSC/DFS/adstark 100K-350K char döndürür). Subagent'a açıkça söyle.
- **Eşzamanlı okuma güvenilmez:** yazım sürerken sheet "boş" görünebilir → tek okumaya güvenip alarm verme; Faz 9 self-check fiili teyit eder.
- **Paralel audit → cross-populate:** quick_wins ve opportunity paralel yazılırsa F-16 (quick_wins.url ⊆ opportunity) kırılır → Faz 5 sonrası bir cross-populate geçişi (quick_wins URL'lerini opportunity'ye yansıt).

## Değişmezler (8 kural)
- **A — ham yazım YOK.** Tüm sheet yazımları alt skill'ler üzerinden `scripts/excel/transaction.py` (backup + lock + schema-validate + provenance = "backup + append-only").
- **B — SEO tarafı ANALİZ-ONLY.** publish/index/retire/robots-deploy/git-push YOK; yalnız öneri.
- **C — task mutabakatı önce-öner-sonra-uygula.** Default `apply_task_changes=false` → diff + DURUR; consent sonrası **dual-write** (adstark + master), **reschedule** (dedup by task-key, kopya YASAK). **v1.8: adstark panosu marker'sız 200+ task içerebilir → yeni bulguyu eklemeden ÖNCE composite-key (customer+url+issue/P) dedup ZORUNLU; ekleneni [mt:<id>] marker'la damgala + dönen adstark-id'yi master.work_log_ref'e GERİ yaz (çift-yönlü). Kanıt lastiksa-tr: 16 bulgu → 5 yeni, 11 mevcut task'la örtüştü.** **v2.0 (A24 — bayder): adstark `update_task` alanı TAM-REPLACE eder + `list_tasks` uzun description'ları TRUNCATE ederek döndürür + `get_task` tool YOK → mevcut bir task'a kanıt-append ederken truncated desc'i EZME (gizli kuyruk data-loss riski). Güvenli davranış: description tam & temiz bitiyorsa append+yaz (kanıt bayder task-v2-26 temizdi → güncellendi); truncated/şüpheliyse (açık paren, yarım kelime) EZME → kanıtı master_task'ta sakla + raporda DÜRÜST flag'le (alternatif: yeni standalone note/task). Kanıt bayder: task-v2-22 [BLOCKED] desc "...+GBP" kesik döndü → atlandı, ezilmedi. Çift-yönlü linkage NOTU: `transaction.py` approved-writer `run_id`'yi flock altında race-free AUTO-ALLOCATE eder (caller-injectable DEĞİL) → back-linkage subagent'ına int run_id geçirmeye ÇALIŞMA; standart yazım yolu zaten INTEGER run_id basar (A20b bu path'te otomatik karşılanır, F-13 PASS). Ayrıca master_task'ta ayrı adstark-link kolonu YOK (19-kolon kilitli şema) → adstark-id `work_log_ref`'e `adstark:<id>` olarak eklenir.**
- **D — dry_run mutlak.** true iken hiçbir faz yazmaz; her yazım "PLANNED".
- **E — COMPLETENESS.** Eksik veri = yanlış audit. Bir kaynak/rapor eksikse sessizce geçme; **INCOMPLETE flag** + Faz 9 completeness gate'inde escalate. DFS bütçe için truncate YASAK.
- **F — CANLI-MUTABAKAT ÖNCE — ÇİFT-YÖNLÜ (v1.6, v1.8 genişletme).** Tek-kaynak bir "0/eksik" sinyalini (schema=0, orphan=N, duplicate=0, H1=yok) rapora **HIGH** yazmadan önce diğer kaynakla ÇAPRAZ-DOĞRULA. Yanlış-negatif İKİ YÖNDE de olur: (a) SF undercount → schema=0 (kanıt: SF schema=0 iken canlı 28-29/29 @graph vardı); (b) **Scrapling/canlı tier0 (JS'siz get) JS-render'lı elemanı atlar → sahte "H1/schema yok"** (v1.8 kanıt lastiksa-tr/Ticimax: Scrapling "26/27 H1 yok" dedi, SF h1_all 704/778 DOLU → JS-render FN; gerçek 74 eksik). **On-page element-mevcudiyeti için SF crawl (h1_all/structured_data) OTORİTEDİR; canlı fetch yalnız içerik/geçerlilik mutabakatı içindir.** İki kaynak uyuşmadan "kriz" deme.
- **G — DOMAIN FİLTRESİ (v1.6).** SF raporları (özellikle orphan/all-inlinks) başka projelerin URL'lerini içerebilir → her SF analizinden ÖNCE satırları proje domain'ine filtrele (kanıt: "1711 orphan" tümü harici sızıntıydı, gerçek=0).
- **H — ONAY DÜRÜSTLÜĞÜ (v1.7, v1.9 netleştirme).** Subagent'lar/orkestratör insan-onay etiketi UYDURMAZ. Analiz-only append yazımlar için run-seviyesi yetki yeterlidir ama audit izinde onu "auto-approved under refresh-audit run {run_id} (non-interactive, analysis-only)" olarak DÜRÜST kaydet — asla gerçekleşmemiş bir insan onayını ("operator-pre-authorized" gibi) taklit etme. Dışa-dönük/CRM yazımı (Faz 7) yalnız GERÇEK operatör consent'i ile (kanıt: bir koşuda GSC subagent'ı sahte "operator-pre-authorized" bastı → güvenlik flag'i). **EXPLICIT-CONSENT NETLEŞTİRME (v1.9 — A16):** operatörün SANA sunduğun SPESİFİK bir CRM aksiyonuna verdiği doğrudan onay ("evet hepsini yaz", "o decompose'u yap", "senin önerine göre gidelim" — somut diff/plan MASADA iken) EXPLICIT sayılır → dual-write serbest. Ancak spesifik aksiyon MASADA YOKKEN genel "sen karar ver / en iyi senaryo ne ise" delegasyonu CRM yazımı için TEK BAŞINA YETMEZ → önce somut diff/gün-planı SUN, sonra onay al. Kanıt rkturizm-tr: 9-task diff+gün-planı sunuldu → operatör "hepsini yaz" → explicit sayıldı, dual-write yapıldı. **PROVENANCE run_id INTEGER (v1.9 — A20b):** her provenance event'i INTEGER `run_id` ile yaz (None/string → F-13 HIGH drift). Orkestratör bir int run_id belirleyip subagent'lara geçir. Kanıt rkturizm-tr: 1/61 event `run_id=None` → F-13 FAIL (minor, upstream emitter fix önerildi).

## DURUR Gate'leri
| # | Koşul | Aksiyon |
|---|-------|---------|
| 1 | `master.xlsx` yok | DUR — init-project önce |
| 2 | **DFS bütçe aşımı** | **SKIP ETME** — uyar + devam; oversized ise consent iste, ASLA truncate etme (completeness) |
| 3 | Aktif proje çözülemedi | DUR — `/pseo-active <slug>` |
| 4 | Alt skill schema-validate FAIL | O sheet rollback, raporla, devam |
| 5 | SEO dışa-dönük aksiyon bekleniyor | DUR — kapsam-dışı |
| 6 | Faz 7 adstark customer_id çözülemedi | Task fazı DUR + flag |
| 7 | Faz 7 adstark↔master ÇELİŞKİ | Otomatik çözme; operatöre bırak (CONFLICT) |
| 8 | `apply_task_changes=true` ama consent yok | Uygulama DUR — `/pseo-approve` |
| 9 | Aynı proje başka CANLI run kilidi | DUR — resume/bekle (stale TTL sonrası devral) |
| 10 | **Mandatory kaynak/rapor eksik** (SF <24 rapor [near/exact-dup istisnası: AMBER, flag+devam], DFS truncate, cannibalization koşmadı) | Audit INCOMPLETE — escalate, "tamamlandı" DEME |

## Faz 0 — Preflight + kilit + staleness
1. **Aktif proje:** session binding → active.json → argüman. Boşsa DURUR #3. Slug'ı yazdır+teyit.
2. **Eşzamanlılık kilidi** al (`_state/locks/refresh-audit-{slug}.lock`; canlı run varsa DURUR #9; TTL'li).
3. `project.config.json` + `master.xlsx` var mı? Yoksa DURUR #1.
4. **Bütçe pre-flight:** tahmini DFS/Scrapling maliyet raporla (bilgi amaçlı — DFS'i durdurmaz).
5. **Staleness:** `< staleness_hours` kaynak SKIP+flag (`audit_depth=full` iken DFS/SF için 0 önerilir).
6. **Erişilebilirlik:** SF MCP açık mı (24-rapor için gerekli), GSC doğrulanmış mı, adstark açık mı.
6b. **CONFIG-DRIFT (v1.7):** `config.sf.mcp.enabled` ↔ canlı SF probe (`sf_list_crawls`) uyuşmazlığını tespit et — server yanıt veriyorsa ama config `false` ise config gerçeği yansıtmıyor → `enabled=true`'ya çek (yoksa orkestratör MCP-crawl yolunu yanlışlıkla atlar). Kanıt: bu koşuda vento `enabled=false` iken SF server açıktı ve 6277-URL crawl'ı yüklüydü.
6c. **GSC PROPERTY-PERMISSION DRIFT (v1.9 — A17):** MCP-erişilebilir ≠ property-yetkili. `gsc_list_sites` ile `config.gsc.site_url`'ün `permissionLevel`'ını KONTROL ET — `siteUnverifiedUser` ise GSC pull **sessizce boş/hatasız** döner (sahte "0 tık"). Owner-doğrulanmış varyantı seç: aynı domain için hem `sc-domain:X` hem `https://X/` listelenebilir; owner olanı (genelde URL-prefix) `config.gsc.site_url`'e yaz. Kanıt rkturizm-tr: `sc-domain:rkturizm.com` siteUnverifiedUser, `https://rkturizm.com/` siteOwner → config düzeltildi, GSC 291 satır geldi. TR projelerinde ayrıca `config.dataforseo.location_name` "Turkey" ise "Turkiye"ye çek (40501, Faz 3). **www/PROTOKOL VARYANTI (v2.1 — bigcat-tr):** config'in URL-prefix'i property listesinde HİÇ bulunmayabilir — owner property www/protokol bakımından FARKLI olabilir. `gsc_list_sites` çıktısında config `site_url`'ün TAM string'i yoksa, aynı domain'in owner-doğrulanmış varyantına (www↔non-www, http↔https farkı dahil) hizala. Kanıt bigcat-tr: config `https://bigcattr.com/` (non-www, listede YOK) → owner `https://www.bigcattr.com/` (www) → düzeltildi, GSC 224 satır.
6d. **active.json UÇUCU — SESSION-BINDING OTORİTE (v1.9 — A18):** `shared/active.json` paralel bir session tarafından koşu ORTASINDA geri çevrilebilir (senin yazdığını ezer). Bu yüzden: (i) çözülen slug'ı `shared/sessions/<session-id>.json` binding'ine yaz (asıl otorite), (ii) HER subagent dispatch'inden ÖNCE active.json'ı hedefe RE-ASSERT et (tek sefer yetmez), (iii) subagent'lara explicit `{slug}`+path ver, active.json'a GÜVENMESİNLER. Kanıt rkturizm-tr: active.json 2× `lastiksa-tr`'ye döndü; explicit-kimlik guard'ı doğru projeye yazdırdı.
7. **Resume:** bekleyen run varsa devam et.
8. **Yasak:** boş MCP → sayı UYDURMA ("N/A + sebep"). dry_run → yazımları "PLANNED".

## Faz bağımlılık hard-gate'leri
Upstream SKIP/FAIL → downstream **atlanır + "gated" satırı** (sessiz geçme YOK):
`quick-wins`/F-08 ← gsc_performance; `content-gaps` ← DFS staging; `cluster-map` D-02 ← topical_map;
`competitive-analysis`/topical otorite ← SERP+backlink verisi; Faz 7 ← Faz 6 master_task tazelenmiş.

**Faz 1–4 arasında kenar YOKTUR — numaralandırma sıra değil, okuma sırasıdır.**
Yukarıdaki liste bağımlılıkların TAMAMIDIR ve hiçbiri Faz 3'ü Faz 2'ye bağlamaz.
Dört ingestion fazı ayrık sheet'lere yazar, dolayısıyla §143'teki disjoint-sheet
paralel delege kuralı doğrudan geçerlidir:

| faz | yazdığı sheet |
|---|---|
| Faz 1 GSC | `gsc_performance` |
| Faz 2 SF | `crawl_sitemap`, `redirect_404` |
| Faz 3 DFS | `dfs_ranked_keywords`, `dfs_relevant_pages`, `backlinks` |
| Faz 4 Scrapling | *(master'a yazmaz — tutarsızlık listesi üretir)* |

İkili kesişim: yok. Bu yüzden **Faz 1/2/3 eşzamanlı başlatılır**; DFS'i SF crawl'ın
arkasında sıraya koymak duvar saatini boşuna uzatır (SF crawl fazın en yavaş
adımıdır ve DFS ondan tek bir girdi almaz). Sıralı koşmak isteniyorsa bu bir
BÜTÇE kararıdır (eşzamanlı kredi tavanı), bağımlılık değil — ve öyle yazılır.

## Faz 1 — GSC tazeleme (→ `gsc-pull`)
`days_back` recent + eşit previous; enhanced + search_analytics, raw-inbox-first → transform →
approval → write. Sonra index_inspect + detect_quick_wins. **ÇIKTI:** satır, yeni query, quick-win, indexlenmeyen.

## Faz 2 — SF crawl (→ `sf-crawl-orchestrator`) — **TAM 24 RAPOR ZORUNLU**
**CRAWL CONFIG ÖN-KOŞULU (v1.6, v1.9 genişletme):** crawl BAŞLAMADAN SF'te şunlar AÇIK/doğru olmalı, yoksa raporlar yanıltıcı gelir: (a) **Structured Data (JSON-LD) extraction** — kapalıysa `structured_data`/`schema` FALSE-NEGATIVE 0 üretir; (b) **Near/Exact Duplicate detection** — kapalıysa `exact_duplicates`+`near_duplicates` (2 rapor) üretilemez → 22/24; (c) **User-Agent = `Googlebot (Smartphone)` (v1.9 — A19):** mobil-öncelikli indeksleme → Google'ın fiilen indekslediğini görürsün + cloaking/differential-serving yakalar; default "Screaming Frog SEO Spider" UA'sı sana ziyaretçi içeriği sunar → audit yanıltıcı olur; (d) **Rendering = Text-Only** server-side stack'te (WP/RankMath schema+H1'i server basıyor) hız+yeterli; şüpheli "H1/schema yok" canlıyla çelişirse JS Rendering'e escalate. Operatör "hangi UA" sorarsa doğrudan Googlebot-Smartphone öner. Kapalı/yanlışsa doğru config'le YENİDEN crawl et. Yalnız near/exact-dup eksikse: Tier-2 **AMBER** — completeness'i HARD-FAIL ETME, flag'le + devam. Diğer eksik rapor → DURUR #10 INCOMPLETE.
**POST-CRAWL CRAWL ANALYSIS ZORUNLU (v1.7, v1.9 netleştirme):** near/exact-dup + hash verisi yalnız SF'te crawl bitince çalıştırılan **"Crawl Analysis"** ile dolar. Duplicate toggle AÇIK olsa bile Crawl Analysis koşmadıysa `near_duplicates`/`exact_duplicates` raporları MEVCUT ama **0 satır** gelir (24/24 "rapor var" ≠ dup verisi dolu). **AUTO-ANALYSIS TESPİTİ (v1.9 — A20):** `sf_crawl_progress` çıktısındaki `postCrawlAnalysisProgress.percentComplete`'i KONTROL ET — `100` ise Crawl Analysis crawl-sonu OTOMATİK koştu (GUI ayarı) → boş dup/orphan = **GERÇEK 0**, sahte-boş DEĞİL → AMBER'a düşürME, "genuine zero" olarak raporla. `<100` veya alan yoksa Crawl Analysis koşmadı → MCP-crawl sonrası tetikle (varsa; yoksa operatöre "SF GUI'de Crawl Analysis → 2 raporu re-export" talimatı + AMBER). Kanıt rkturizm-tr: `postCrawlAnalysisProgress=100` → near/exact-dup+orphan iki yoldan da 0 → gerçek sıfır (re-export gerekmedi). Kanıt lastiksa-tr: toggle açıktı, analysis koşmamıştı, boştu; operatör koşunca 2 gerçek near-dup cluster çıktı. Toggle-kapalı (rapor yok) ≠ analysis-koşmadı (rapor var/boş) ≠ genuine-0 (analysis koştu, boş) — ÜÇÜNÜ AYIR.
**RE-EXPORT MEKANİZMASI (v1.8):** operatör Crawl Analysis koştuktan sonra near/exact-dup `sf_generate_report` LİSTESİNDE YOKTUR → `sf_export_seo_element_urls(seo_element_name="Content", filter_name="Near Duplicates" | "Exact Duplicates")` ile çek; orphan `sf_generate_report(category="Orphan Pages")`. file_path allowed base köküne DÜZ dosya adı (alt-dizin yoksa NoSuchFileException). Kanıt lastiksa-tr: operatör Crawl Analysis sonrası re-export → 75 indexable near-dup (13×%100 kategori/şablon), 0 exact, 0 orphan.
**CDN-HOST BUG (v1.8 — engine zaafı flag):** `sf_projection._derive_site_host` EN SIK host'u seçer → imaj-yoğun e-ticarette CDN host'unu (ör. `static.ticimax.cloud`, 2281 imaj) gerçek domain (827 sayfa) yerine seçer → `redirect_404` projeksiyonu **0 satır** yazar, gerçek iç-domain 3xx/4xx düşer. FIX: `map_redirect_404`'ü explicit `site_host=<config domain>` ile çağır. Kalıcı engine fix önerilir. Kanıt lastiksa-tr: 20 gerçek 3xx/4xx (4 hard-404 dahil) kaybolmuştu, düzeltildi.
SF MCP açıksa Tier 1 + Tier 2 **24 raporun HEPSİ** çekilir (subset YASAK): internal_links,
inlinks/outlinks, directives (noindex/canonical/robots), structured_data, response codes
(kırık/redirect/blocked), page titles/meta descriptions/H1-H2, canonical zinciri, hreflang,
pagination, orphan URLs, crawl depth, duplicate, images/alt, sitemap coverage, redirect zinciri,
AMP, JS-rendered, word count/thin, security (HTTPS/mixed), vb. MCP kapalıysa `sf-import` ile
**tam export seti**; eksik rapor → DURUR #10 INCOMPLETE (near/exact-dup istisnası: AMBER). **DOMAIN FİLTRESİ (Değişmez G):** orphan/all-inlinks raporlarını analizden önce proje domain'ine filtrele (harici sızıntı → false orphan). **ÇIKTI:** 22-24/24 rapor onayı + kırık/redirect/noindex/orphan(domain-filtreli) sayıları.

## Faz 3 — DFS tazeleme (→ `dfs-pull`) — **EKSİKSİZ (completeness > bütçe)**
`location_code`/`language_code` config'ten. **⚠️ TR LOCALE (v1.6): `location_name="Turkey"` DataForSEO tarafından REDDEDİLİR (Code 40501); `location_name="Turkiye"` (BM 2022 adı) veya doğrudan `location_code=2792` kullan.** keyword_overview + bulk_keyword_difficulty + **ranked_keywords TAM sayfalama** (örnekleme/truncate YOK) + relevant_pages + serp (gerekirse) + opsiyonel backlinks (referring_domains + spam_score → otorite/toksik sinyal). **Bütçe: full-audit'te ~1000+ kredi normaldir** (budget_credits_per_day tipik 500 → aşılır); completeness>bütçe: uyar+devam, oversized ise consent iste — **asla yarım keyword evreni**. **ÇIKTI:** keyword sayısı (tam), difficulty/volume delta, otorite sinyalleri, tahmini kredi.
**PROJEKSİYON ZORUNLU (v1.7):** `dfs-pull` D-003 gereği staging-only'dir (keyword_overview + search_volume → cluster-map tüketir). Ama `ranked_keywords` + `relevant_pages` + `backlinks` ham inbox'ta writer'sız kalırsa **completeness açığı** olur (kanıt: bu koşuda 337 ranked + 72 backlink toplandı ama master'a yazılamadı). ÇÖZÜM: `scripts/ingestion/dfs_project_transform.py` ile `ranked_keywords` → **`dfs_ranked_keywords`** sheet'ine, `backlinks` (referring_domains+spam) → **`backlinks`** sheet'ine projekte et (transaction.replace, idempotent). Projeksiyon yoksa DURUR #10 (ham inbox'ta bırakıp "DFS tam master'da" DEME).
**ENVELOPE TUZAĞI (v1.9 — A22, engine zaafı flag):** `dfs_project_transform._find_items` tam DFS REST `tasks[]` envelope'unu traverse EDEMEZ (liste elemanlarına recurse etmez) → ham MCP/REST payload'unu doğrudan beslersen **hatasız 0 satır** (dry-run count=0) → sessiz completeness tuzağı ("DFS tam master'da" derken projeksiyon boş). FIX: transform input olarak dict-addressable `{"items":[...]}.norm.json` sibling dosyaları yaz (ham envelope'u drift-recovery için sakla), sonra transform'a onu ver. Kalıcı engine fix önerilir. Kanıt rkturizm-tr: ranked_keywords 483/483 tam projekte oldu (workaround). Difficulty sink (A8): `cluster_keywords`'te `keyword_difficulty` kolonu yoksa difficulty ADVISORY (yalnız inbox/staging), "DFS tam master'da" derken dahil etme.

## Faz 4 — Scrapling canlı doğrulama (→ `scrapling-ops`)
Pillar + top-20 cluster + top-5 rakip SERP canlı fetch. Tutarsızlık: eksik H1, schema drift,
301/404 hedef, thin content, rakip içerik boşluğu + başlık deseni. **ÇIKTI:** tutarsızlık listesi (URL→sorun→kanıt).

## Faz 5 — TAM SEO audit suite (ANALİZ-ONLY) — hiçbir modül atlanmaz
`audit_depth=full` → tüm modüller; `lite` → yalnız (*) işaretliler. Her modül kendi master sheet'ini yazar (transaction).

| Grup | Modül (skill) | Ne bulur |
|---|---|---|
| Teknik | `tech-audit` | crawl/index/status/canonical/directive sorunları (P1/P2) |
| Teknik | `robots-policy-audit` | robots.txt + noindex çakışma/drift |
| Teknik | `hreflang-audit` | çok-dilli hreflang hataları |
| Teknik | `facet-nav-audit` | faceted/parametre index şişmesi |
| On-page | `on-page-audit` | title/meta/heading/içerik on-page kalite |
| On-page | `schema-audit` | JSON-LD/structured data + rich result uygunluğu |
| Otorite | `topical-map` | pillar/cluster taksonomi kapsama + derinlik |
| Otorite | `cluster-map` (D-02) | cluster→pillar bağı, keyword projeksiyonu |
| Otorite | `internal-links` | pillar'a iç link akışı (otorite dağılımı) + boşluk |
| Otorite | `competitive-analysis` | rakip topical benchmark (konu otoritesi açığı) |
| Çakışma | `cannibalization` (*) | aynı query'e ≥2 URL — **her modda ZORUNLU** |
| İçerik | `content-decay` (*) | recent vs previous düşen sayfalar |
| İçerik | `content-gaps` | hacimli ama içeriksiz keyword → yeni cluster |
| Local | `gbp-audit` | Google Business Profile: harita/yorum/NAP/kategori. **Gate = `config.profiles` içinde `local-service` (v1.6 düzeltme — `business.local` DEĞİL).** Local ise ZORUNLU; `gbp_audit` sheet workbook'a bootstrap edilmeli (şemada var) + `local/nap.json` gerekli. Değilse SKIP+not. |
| AI-search | `geo-analysis` + `aio-competitor-map` | AI Overview / LLM alıntı görünürlüğü + rakip AI haritası (config `ai_search.enabled` ile koşullu) |

**Konu otoritesi skoru:** topical-map kapsama + cluster derinliği + internal-link akışı +
competitive benchmark birleştirilir → pillar bazlı otorite haritası (zayıf pillar'lar flag). **ÇIKTI:** pillar otorite haritası + cannibalization çakışmaları + orphan/gap/decay.
**PILLAR-KEYWORD GAP → FABRİKASYON DEĞİL INCOMPLETE (v1.8, Değişmez E):** DFS staging tek-pillar ağırlıklıysa (ör. %95 P1) zayıf pillar'lar için cluster/topical satırı UYDURMA → `topical_map`/`cluster_keywords` MERGE'ünü INCOMPLETE flag'le + "pillar-bazlı `keyword_ideas` pull (+onay) gerek" öner. MERGE yapılacaksa `scripts/util/sheet_merge.py merge_keyed_rows` (additive — 90 curated EXISTS TR-not satırı KORU); committer whole-block replace curated satırları ezme riski taşır. Kanıt lastiksa-tr: 6 zayıf pillar (P2/P4/P5 içerik çölü) — MERGE ertelendi, tek-pillar yoğunlaşması gerçek stratejik bulgu olarak raporlandı + master_task'a pillar-build task'ı oldu.
**KEYWORD DISCOVERY — SEED-ANCHORED (v1.9 — A15):** zayıf/niş pillar'da taze keyword için `keyword_ideas` KATEGORİ-DRIFT ile alakasız çöp döndürür (altın fiyatı, "ne demek") → bunun yerine seed-anchored `keyword_suggestions` (AND full-text, topik-garantili) kullan. Gerçek talep düşükse DÜRÜSTÇE ince raporla; navigational/kurum-sahipli sorguları (kura/başvuru/gov) private operatör için hedeflenemez diye AÇIKÇA hariç tut. Kanıt rkturizm-tr: Hac pillar için `hac fiyatları 2026` (14.8k) seed-anchored bulundu; Diyanet-sahipli process sorguları hariç tutuldu.
**REPLACE-VERDICT YERLEŞİM DİSİPLİNİ (v1.9 — A21):** Faz 5 audit modülleri ham SF sheet'lerini (on_page_audit/tech_seo/schema/robots_txt) VERDICT'lerle REPLACE eder → satır DÜŞER (by-design). Bir audit subagent'ı row-drop/immutability endişesiyle verdict'i sheet'e YAZMAYIP yalnız staging artifact'ına bırakırsa → bu bir SAPMADIR: (i) INCOMPLETE-flag ile AÇIKÇA raporla (sessiz bırakma), (ii) orkestratör bu staging sentez artifact'ını Faz 6 master-task-sync'e EXPLICIT besle (aksi halde verdict'ler master_task/drift-check'e görünmez). İdeal: verdict'ler REPLACE sheet'lerine yazılır. Kanıt rkturizm-tr: Faz 5b staging'e yazdı, sheet-replace atladı → Faz 6'ya sentez artifact'ı explicit beslendi, veri kaybı olmadı ama REPLACE-drop gerçekleşmedi (dürüst flag).

**CANNIBALIZATION — TEK-URL QUERY-VARYANT TUZAĞI (v2.1 — bigcat-tr):** DFS `ranked_keywords`'te bir terimin çok sorgu-varyantı için çok POZİSYON görünmesi ("maine coon" p45 + "cat maine coon" p28 + "maine coon cat" p30, hepsi aynı vol) kanibalizasyon DEĞİLDİR — bu TEK URL'in query-varyant yayılımı + zayıf ranking'idir. Kanibalizasyon = FARKLI URL'ler aynı sorguya. Flag'lemeden ÖNCE distinct URL doğrula (GSC page+query veya ranked_kw url kolonu); "N pozisyon" DFS sinyalini otomatik kanibal sayma → içerik/iç-link fırsatına route et. Kanıt bigcat-tr: maine-coon "3-URL kanibal" varsayımı çürütüldü (tek URL), kanibalizasyon sheet'ine yazılmadı, task açılmadı.
**CONTENT-DECAY — AĞIRLIKLI-ORTALAMA POZİSYON ARTEFAKTI (v2.1 — bigcat-tr):** Sayfa-seviyesi ortalama pozisyon kötüleşmesi GERÇEK ranking kaybı OLMAYABİLİR — yüksek-hacim bir head sorgusu gösterim kaybederse sayfanın ağırlıklı-ortalama pozisyonu diğer sorgulara kayar (artefakt, gerçek sıra sabit). Gerçek-decay için SORGU-seviyesinde doğrula: ana sorguların pos'u stabil mi? Stabilse → mevsimsel/talep (revize task'ı AÇMA); yalnız gerçekten düşen sorgusu olan sayfaya revize task'ı aç. Kanıt bigcat-tr: british-shorthair sayfa-pos 1.79→2.18 "kötüleşti" göründü ama ana sorguları ("kedi" 1.33→1.14, "british shorthair" 1.73→1.44) STABİL/İYİ → kayma "kedi" impr kaybının ağırlık-kaymasıydı, mevsimsel, revize task'ı açılmadı (Değişmez F + index_inspect mevsimsel-ayrımı ile birlikte kullan).

## Faz 6 — master_task SSoT (→ `master-task-sync`)
Faz 1-5 sheet'lerinden master_task SSoT topla (auto satır, D-only merge; manuel/protected'a dokunmaz). **ÇIKTI:** eklenen/güncellenen auto satır.
- **task_id `T-NNNNN` (v1.6):** authority `rules/master-task-id.md` → `^T-[0-9]{4,}$`. Transform hex/sha256 ID üretirse write-layer schema-validate REDDEDER (BLOCKED). İdempotency kalıcı `_state/master_task_id_map.json` (content-signature → T-NNNNN) ile korunur; hex GÖRÜNÜR ID olarak KULLANILMAZ.
- **Hacim eşiği (v1.6):** cluster_keywords/pillar kaynağından keyword-başına-1-task ÜRETME (bloat: 972 kw → 1520 append). SEO-değer eşiği uygula (assigned_url'siz + monthly_volume≥500 veya top-N); düşürülen satırı sessizce atma — LOG'la (no silent truncate).
- **Kapsam notu:** skill'in `SOURCE_DEFS`'i quick_wins/opportunity/robots_txt'i OKUMAYABİLİR (farklı writer'lar sahip). Faz 6 "tüm bulgular" beklentisini skill'in fiili kapsamıyla hizala; eksik kaynağı flag'le.

## Faz 7 — adstark ↔ master task mutabakatı + **GÜNLERE DAĞITIM** (YAZIM — önce-öner-sonra-uygula)
> Amaç: CRM board = master SSoT + dengeli iş takvimi. Disiplin: dual-write · reschedule · SEO-değer filtresi.
1. **Müşteri çöz** (customer_id; yoksa DURUR #6).
2. **İki taraf + mevcut yük oku:** adstark `list_tasks` + `today_and_overdue` + `upcoming_deadlines` (gün-doluluk) + master `master_task`/`tech_seo`.
3. **Stabil task-key diff + DEDUP-FIRST:** birincil key = `master_task.id`, adstark `description`'a görünür marker `[mt:<id>]` olarak basılır (O(1) rematch); marker yoksa (İLK sync: pano marker'sız olabilir) fallback composite key = `(customer_id + hedef_url + issue_kategori/P-seviye)`. Eşleşme: master-only → `add_task` (marker ile); adstark-only → master satır/orphan flag; farklı → `update_task`/`move_task` (**reschedule**, marker korunur); bir tarafta done → diğerini kapat. **KAPATMA SEBEP-KAYDI (v2.1 — bigcat-tr):** `complete_task` NOT/sebep alanı YOK → bir task'ı sebeple (ör. çakışma-supersession) kapatırken önce `update_task` ile açıklamaya kapatma-notunu ekle (A24 tam-desc oku+append), SONRA `complete_task`; yoksa "neden kapandı" kaydı kaybolur. Kanıt bigcat-tr: v2-249 (restore) + v2-270 (improve) 301-consolidate kararıyla kapatıldı — önce supersession notu + `[mt:T-0067]` eklendi, sonra tamamlandı.
   - **DUP vs ÇAKIŞMA AYRIMI (v1.9 — A23):** yeni bulgu mevcut task'la (i) aynı URL+aynı issue → **DUP**, ekleme (kopya YASAK); (ii) aynı URL farklı issue → yeni task ama örtüşme-notlu; (iii) mevcut task'ın VARSAYIMINI taze veri ÇÜRÜTÜYORSA → **ÇAKIŞMA** (DURUR #7 değil, aksiyon): mevcut task'ı düzeltme-notuyla `update_task`'la güncelle. Kanıt rkturizm-tr: mevcut v2-184 `/ramazan-umresi→/ramazan-umresi-2026` 301 yönünü varsayıyordu AMA taze SF canonical TERS (year'sız kanonik) → v2-184'e "T-0048 ile senkronize et, ters 301 kurma" flag'i eklendi. Örtüşme/çakışma kanıtını raporla ("T-XXXX ≈/⚠ task-v2-YYY").
   - **`update_task` ALAN-REPLACE (v1.9 — A23):** `update_task` verdiğin alanı REPLACE eder (append DEĞİL) → merge/çakışma güncellemesinde önce mevcut tam `description`'ı OKU, üstüne kanıt satırı ekle, TÜMÜNÜ yaz; yoksa mevcut açıklamayı truncate edersin. Kanıt rkturizm-tr: v2-184/v2-234 tam açıklama korunarak `--- [REFRESH ...]` kanıtı eklendi.
4. **SEO-değer filtresi:** gerçek etki (GSC pos/imp, CTR, dup/missing meta, P1 teknik) → taşı; lab-only PageSpeed / kozmetik heading / meta-pixel advisory → done öner.
5. **Açıklama detay şablonu** (adstark `description`): `Ne · Neden(SEO) · Kanıt(GSC query+pos / SF issue ref) · Hedef URL · Öncelik(P1/P2) · Due`. Boş açıklamalar bununla dolar.
6. **GÜN DAĞITIMI:** aktif taskları öncelik (P1 önce) + `tasks_per_day` kapasitesiyle **boş iş günlerine yay** — mevcut dolu günleri (adım 2 yükü) aşma, hafta sonu/atlanan günleri config'e göre atla; her task'a dengeli `due` ata. Yığılma YASAK.
7. **Önce-öner-dur:** DIFF + gün-planı tablosu sun. `apply_task_changes=false` veya `dry_run` → DUR, `/pseo-approve` bekle.
8. **Uygula (consent + !dry_run):** **sıralı dual-write** — önce master (SSoT, transaction, rollback-able), sonra adstark. adstark yazımı master commit sonrası patlarsa: `events.jsonl`'e `PENDING_CRM_SYNC` kaydı + o task'ı flag + retry (blind değil); ASLA sessiz uyumsuzluk bırakma (partial-failure telafisi). Her yazım → provenance. **ÇIKTI:** diff (add/update/close/conflict) + gün-dağıtım takvimi + açıklama-doldurulan + (varsa) PENDING_CRM_SYNC.

## Faz 8 — Drift/tutarlılık (→ `drift-check`)
`validate_invariants.py` (F-08 dahil) + `validate_schema.py`. **ÇIKTI:** geçen/başarısız invariant + kritik ihlaller.
**PRE-EXISTING vs KOŞU-VERİSİ DRIFT AYRIMI (v2.1):** overall RED olsa bile FAIL'ler yalnız bilinen istisnalarsa "koşu-verisi ihlali YOK" diye AYIR: F-15 (cannibalization triage) AMBER-by-design; F-16 (quick_wins⊆opportunity) genelde pre-existing marka-orphan quick_win (tek-sorgu→çok-URL, query-key'e sığmaz → `quickwins_transform` regen ister); **F-17 (manuel satır off-enum priority — ör. `priority='P2'` yerine high/medium/low)** koşu-ÖNCESİ oluşturulmuş manuel/competitor_gap satırlarından gelir → pre-existing, koordineli protected-row edit ister, bu-koşunun ihlali DEĞİL; F-24 engine-registry (koşu-verisiyle karıştırma). Bu-koşunun YAZDIĞI sheet'lerde F-05 (kolon-count) veya F-13 (run_id int değil) çıkarsa GERÇEK — ayır. Kanıt bigcat-tr: F-15+F-16+F-17 üçü de pre-existing/by-design, F-05/F-08/F-13/F-24 PASS → koşu-verisi ihlali yok.

## Faz 9 — QA + COMPLETENESS gate + self-check + coverage
- **Output validation** (her faz): format·completeness·consistency·scope. FAIL → geri besle, tekrar; 3.'de escalate (qa-loop, blind retry YOK).
- **COMPLETENESS gate (DURUR #10):** zorunlu adım checklist'i — GSC çekildi · SF 24/24 rapor (near/exact-dup AMBER hariç) + **post-crawl Crawl Analysis koştu (dup verisi dolu)** · DFS tam (truncate yok) + **ranked_keywords/backlinks master'a projekte edildi** (`dfs_ranked_keywords`/`backlinks` sheet dolu — ham inbox yeterli DEĞİL) · Faz 5 tüm modüller koştu (özellikle cannibalization + topical otorite) · master_task toplandı (task_id `T-NNNNN` write PASS) · (task fazı açıksa) diff + gün-planı üretildi. Eksik varsa audit INCOMPLETE → escalate, "tamamlandı" DEME.
- **Bitiş self-check:** master'ı yeniden aç; raporlanan öncesi/sonrası satır sayılarını fiili sheet'lerle karşılaştır. Uyuşmazsa düzelt. **v1.8 uyarı: REPLACE sheet'lerinde satır DÜŞÜŞÜ (verdict konsolidasyonu) ve `topical_map`/`cluster_keywords`/`dfs_ranked_keywords`'te çok-satırlı header zonu (+2/+4 offset; row1-2 boş/header tekrarı) BEKLENENDİR — bozulma DEĞİL. `transaction`/`data_start_row` katmanının saydığı esastır; naif openpyxl satır sayımı offset kadar sapar. Subagent'a "gömülü başlık = bozulma" DEME talimatı ver.** **LEGACY STALE-DATA SATIR AYRIMI (v2.1 — bigcat-tr):** Beklenen offset (boş/header-tekrar satırları) ile şema-header ZONUNUN ÜSTÜNDEKİ eski-şema STALE-DATA satırlarını AYIR. İkincisi: eski `header@1/data@2` layout'undan kalma, GERÇEK-DEĞER taşıyan yetim veri satırları; `replace()` header-bloğunu (row1-5) koruduğu için DOKUNAMAZ ve canonical okuyucu (`data_start_row`) görmez → bir sayfa sheet'te İKİ KEZ görünür (stale+fresh). Bu bu-koşunun bozması DEĞİL ama kozmetik offset de DEĞİL — pre-existing schema-repair borcu (raw hand-edit ister → YAPMA, flag'le + öner). Kanıt bigcat-tr: content_decay fiziksel satır 1-4 + gsc_performance satır 1-3 legacy stale (gerçek header row5/row4).
- **Metrik + coverage:** `_state/metrics/refresh-audit.jsonl` + `_state/coverage/{run_id}.json` (→ `/pseo-status` + `/pseo-whats-next`).

## Faz 10 — Birleşik rapor + kilidi bırak (`outputs/reports/{date}-refresh-audit.md`)
`dry_run` ise başa **"DRY-RUN — hiçbir yazım yapılmadı"** banner.
1. Yönetici özeti (≤5). 2. Kaynak-bazlı delta + **completeness durumu (24/24, DFS tam mı)** + **VERİ-YERLEŞİM HARİTASI (v1.7): hangi sheet MERGE (curated korunur: cluster_keywords/topical_map), hangi APPEND (master_task/opportunity/new_content_plan), hangi REPLACE (türetilmiş: on_page_audit/schema/cannibalization/content_decay), ve hangi ham veri yalnız inbox/staging'de orphan kaldı (writer yoksa flag)**.
3. **Anomali/delta alarmı** (clicks düşüş>%X / ani deindex / pozisyon çöküşü → HIGH).
4. **Pillar konu-otorite haritası** + zayıf pillar'lar (+ **AI-search görünürlük** & rakip AI haritası config açıksa). 5. **Cannibalization çakışmaları**.
6. Orphan/gap/decay + teknik/on-page/schema (+ **local/GBP** bulguları local ise) bulguları. 7. **Task mutabakat + gün-dağıtım takvimi** (add/update/close/CONFLICT).
8. Drift ihlalleri (severity + doğa: data mı engine-seviye mi — F-24 gibi registry drift'i koşu verisiyle karıştırma). 9. Öncelikli aksiyon (etki×efor, en acil 10). 10. Bekleyen onaylar → `/pseo-approve`. 11. Sonraki adım → `whats-next`. 12. **Kilidi serbest bırak — `rm` DEĞİL (outward-action-gate `fs_delete`'i engeller); lock dosyasına `{"status":"released",...}` YAZ.** **Yanlış-alarm çürütmelerini (schema/orphan/duplicate) raporda açıkça belirt.**

TÜM çıktılar Türkçe. Önce oku/doğrula, sonra (alt skill'ler + consent'li task yazımı, dry_run değilse) yaz.
Kanıtsız "tamamlandı" deme. Boş MCP'de sayı UYDURMA. Eksik audit'i "tam" gibi raporlama.
