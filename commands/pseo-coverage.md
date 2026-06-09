---
description: |
  Use when: kullanıcı "kapsam denetimi", "coverage", "hangi skill/araç kullanılıyor",
  "ne orkestre edilmiyor", "kullanılmayan MCP", "öksüz script", "neyi otomatikleştireyim",
  "ad-hoc skill'ler", "capability coverage" der ya da `/pseo-coverage [slug]` çağırır.
  Also use when: tüm motorun (45 skill / 48 MCP aracı / script'ler) ETKİN kullanımını tek
  bakışta görmek gerekir — hangi skill'ler orkestre (workflow STEPS), hangileri yalnız
  komutla, hangileri YALNIZ ad-hoc (sıralanmadan/denetçisiz) çalışıyor; hangi MCP araçları
  hiç kullanılmıyor; ve hangi ad-hoc skill'i ÖNCE bir workflow'a/route'a taşımak en değerli
  (graf merkeziyetine göre). Opsiyonel slug verilirse o projenin events.jsonl'ından SINIRLI
  bir runtime katmanı (sheet→writer proxy) eklenir.
  Do not use when: portföy durum triyajı (`/pseo-status-portfolio`); tek-proje workflow
  state (`/pseo-status`); drift/invariant kontrolü (`/pseo-driftcheck`); rapor üretimi
  (`/pseo-monthly`). Bu komut HİÇBİR ŞEY YAZMAZ — yalnız okur ve yapısal kapsamı raporlar.
argument-hint: "[project-slug]"
allowed-tools: Bash(python3:*), Bash(find:*), Bash(sort:*), Bash(tail:*), Bash(xargs:*), Bash(jq:*), Read
model: sonnet
---

# /pseo-coverage — Kapasite Kapsam Denetimi (READ-ONLY)

Motorun TÜM parçalarının etkin kullanımını tek Türkçe blokla denetle:

- **Skill'ler (45):** `orchestrated` (bir workflow STEPS yazarı) · `commanded` (bir komut
  `skills/.../SKILL.md`'yi çağırıyor) · `ad-hoc-only` (ikisi de değil — yalnız kendi
  description tetikleyicileriyle erişilebilir; sıralanmıyor/denetçiden geçmiyor — ölü değil).
- **MCP araçları (48 kayıtlı, 4 sunucu):** `orchestrated` (workflow STEP `tool`'u) ·
  `declared-only` (bir skill `mcp_tools`'unda var ama hiçbir workflow adımında yok) ·
  `unused` (registry'de var, hiçbir skill kullanmıyor). higgsfield ayrıca dış/opsiyonel.
- **Script'ler:** `referenced` (modül adı repoda başka yerde geçiyor) vs `orphaned` (öksüz).
- **Öneri:** ad-hoc skill'ler graf merkeziyetine (produces+consumes kenarları) göre
  sıralanır — operatör hangisini ÖNCE orkestrasyona/route'a taşıyacağını görür.

> **Saf + READ-ONLY çekirdek:** `scripts/reporting/capability_coverage.py`
> (`coverage_report` / `render_report`). Modül `parents[2]` ile köke bağlanır (kurulu kopya
> gölgeleyemez — 0c dersi), pb1 `parse_graph` + 3a `declared_tools`'u YENİDEN KULLANIR ve
> HİÇBİR durum yazmaz. Slug verilmezse STATİK rapor üretir (workspace gerekmez); slug
> verilirse o projenin `_state/events.jsonl`'ından SINIRLI runtime katmanı eklenir
> (events.jsonl'da `skill` alanı yok → yalnız provenance sheet→writer proxy; MCP-araç
> runtime sinyali canlı veride neredeyse boş, dürüstçe öyle etiketlenir).

## 1. Raporu üret + Türkçe bloğu bas

Engine root'u çöz (`CLAUDE_PLUGIN_ROOT` yoksa fallback). Opsiyonel slug `$ARGUMENTS`'tan
gelir (`$1` `!`…`` bloklarında BOŞ gelir — `docs/bugs/2026-06-09-slash-command-positional-args-empty.md`
— bu yüzden blok başında `set -- $ARGUMENTS`). Bu adım yalnız OKUR — hiçbir yazma, hiçbir MCP çağrısı:

!`set -- $ARGUMENTS; ENGINE_ROOT="${CLAUDE_PLUGIN_ROOT:-${PSEO_ENGINE_ROOT:-$(find /Users/apple/.claude/plugins/cache 2>/dev/null -type d -name 'platinum-seo-engine' | sort | tail -1 | xargs -I{} find {} -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort -V | tail -1)}}"; if [ -z "$ENGINE_ROOT" ]; then echo "ERROR: CLAUDE_PLUGIN_ROOT yok ve fallback bulunamadı — PSEO_ENGINE_ROOT env var set edin"; exit 3; fi; SLUG="${1:-}"; ARGS=""; if [ -n "$PSEO_WORKSPACE_ROOT" ]; then if [ -z "$SLUG" ]; then SLUG=$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null); fi; if [ -n "$SLUG" ]; then ARGS="--workspace-root $PSEO_WORKSPACE_ROOT --slug $SLUG"; fi; fi; PYTHONPATH="$ENGINE_ROOT" python3 -m scripts.reporting.capability_coverage $ARGS 2>&1`

## 2. Çıktıyı yorumla

- Türkçe blok geldiyse: olduğu gibi operatöre sun (skill/MCP/script tabloları + öneri tablosu
  + varsa runtime). Önemli okumalar:
  - **ad-hoc-only skill'ler** → motorun yarısı burada; bunlar sıralanmadan/denetçisiz çalışır.
    Öneri tablosunun en üstündekiler en bağlantılı (en değerli) taşıma adaylarıdır.
  - **KULLANILMAYAN MCP araçları** → registry'de var ama hiçbir skill kullanmıyor; ya bir
    skill'e bağla ya da registry'den düşmeyi düşün (ayrı karar, bu komut YAZMAZ).
  - **ÖKSÜZ (orphaned) script'ler** → hiçbir yerde referans verilmeyen modüller; `low_confidence`
    işaretliyse (CLI girişi/kısa ad) elle doğrula — yanlış "ölü" demek, yanlış "kullanılıyor"dan kötüdür.
  - **runtime** (slug verildiyse) → `observed writer-skill (sheet proxy)` hangi orkestre
    yazarların gerçekten çalıştığını gösterir; `atfedilemeyen sheet'ler` hiçbir orkestre yazarın
    sahip olmadığı yazılmış sheet'lerdir (SINIRLI sinyal — dürüstçe etiketli).
- Çıktı `ERROR: ...` ise: mesajı operatöre ilet (engine path sorunu). Slug verilmediyse de
  STATİK rapor yine gelir — runtime katmanı sadece atlanır.

## 3. Ad-hoc-only allow-list (kabul kararı)

Coverage tool'unun verisi DOĞRU; "ad-hoc-only" listesi ölü skill DEĞİL — ama
hepsi de kalıcı olarak kabul edilebilir değil. Karar yüzeyi: **read-only /
advisory / operatör-tetikli** skill'ler ad-hoc kalır (KABUL); **state-değiştiren
veya çekirdek-SEO** skill'ler bir workflow'a/route'a taşınmalıdır (PROMOTION
ADAYI — gelecek iş; bu komut HİÇBİR ŞEY taşımaz, yalnız kararı belgeler).

**KABUL (intentional ad-hoc — sıralama/denetçi gerektirmez):**
- Portföy raporlama (READ-ONLY, operatör tetikler): `portfolio-overview`,
  `portfolio-heatmap`, `portfolio-kpi-trend`, `portfolio-monthly-roundup`,
  `portfolio-task-heatmap`, `portfolio-weekly-brief`, `weekly-summary`
- Read-only keşif/analiz/doğrulama (advisory): `aio-competitor-map`,
  `competitive-analysis`, `geo-analysis`, `glossary-audit`, `schema-validate`
- Oturum/kurulum yardımcıları (interaktif, operatör-sürücülü): `brand-onboarding`,
  `load-context`

**PROMOTION ADAYI (kritik state-değiştiren / SEO-etkili — route edilmeli, future work):**
`content-remediation`, `indexing-ping`, `verify-indexing`, `mark-done`,
`sf-import`, `revise-content`, `internal-links`, `content-gaps`,
`master-task-sync` — yukarıdaki "Öneri" tablosu bunları graf-merkeziyetine göre
sıralar; consent-gate'li dış aksiyonlar (örn. `indexing-ping`) ayrıca önce
`/pseo-approve` defterinden geçer. **Promotion-into-workflows bu komutun kapsamı
DIŞI** (ayrı karar; bu allow-list yalnız "hangi ad-hoc KABUL" yüzeyidir).

## 4. Bağımlılıklar

- Saf + READ-ONLY çekirdek: `scripts/reporting/capability_coverage.py`
  (`classify_skills` / `classify_mcp` / `classify_scripts` / `recommendations` /
  `runtime_coverage` / `coverage_report` / `render_report`).
- Yeniden kullanılan lint'ler: pb1 `scripts/validation/skill_graph_consistency.parse_graph`
  (skill rosteri + graf) + 3a `scripts/validation/skill_mcp_usage.declared_tools` (declared set).
- Orkestrasyon kaynağı: 4 workflow STEPS tablosu (`scripts/orchestration/workflows/*.py`).
- MCP kaynağı: `mcp-tool-registry.json` (4 sunucu + higgsfield external).
- Runtime kaynağı (opsiyonel): `projects/{slug}/_state/events.jsonl` (+ coverage kayıtları).
- Kardeş READ-ONLY komutlar: `commands/pseo-status-portfolio.md`, oracle
  `scripts/reporting/orchestration_metrics.py`. Bu komut HİÇBİR ŞEY YAZMAZ.
