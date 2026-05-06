---
# llm_native: true — no transform script (LLM-native, intentionally script-less per Q-PHASE15-AIO-COMPETITOR-01)
name: aio-competitor-map
description: |
  Use when: kullanıcı "AIO analiz", "competitor SERP analizi", "top10
  AIO map", "AI overview rakip", "rakip içerik AIO citation", "SERP
  pattern map" der ya da /pseo-aio-competitor-map çağırır; SERP top-N
  fetch (DataForSEO heavy) + Scrapling tier-1 fetch (per URL) +
  R-109/R-110/R-111 AIO signal detect (schema markup + entity reference
  + author authority) + competitor_pages.jsonl staging.
  Also use when: yeni keyword için pre-content-plan AIO landscape
  haritalanacak; mevcut pillar için competitor refresh yapılacak;
  brand'ın AIO-friendly olup olmadığını competitor citation pattern'ı
  ile test edilecek; cluster-map sonrası seçilen ana keyword için
  competitor R-109..R-111 sinyalleri ölçülecek.
  Do not use when: SERP rank tracking için (gsc skill); manuel tek URL
  analiz için (on-page-audit kullan); content gap için (content-gaps
  kullan); kendi sitemizin AIO-friendliness denetimi için (schema-audit
  + on-page-audit kombinasyonu); target_keyword empty ya da whitespace
  (DURUR #5); budget_credits_per_day aşılmış (DURUR #1 — skip skill,
  AMBER); SERP empty top_n=0 (DURUR #2 REJECT).
version: "1.0"
status: wip
category: discovery
inputs:
  target_keyword:
    type: string
    required: true
    description: "Hedef keyword. SERP top-N fetch için anahtar; whitespace-only ise DURUR #5 ABORT."
  location:
    type: string
    required: false
    default: "tr-TR"
    description: "DataForSEO location_code resolver girdisi (BCP-47 form). Default tr-TR (Türkiye)."
  top_n:
    type: integer
    required: false
    default: 10
    description: "SERP top-N organic result fetch limiti (default 10). top_n=0 ise DURUR #2 REJECT."
outputs:
  - "_state/events.jsonl"
  - "inbox/competitor_pages/{date}-{slug}.jsonl"
consumes:
  - "init-project:project-config[domain]"
  - "init-project:project-config[budget_credits_per_day]"
triggers:
  manual: ["/pseo-aio-competitor-map"]
  natural_language: |
    "AIO analiz yap", "competitor SERP haritası", "top10 AIO map",
    "AI overview rakip analizi", "rakip içerik AIO citation",
    "SERP pattern map", "rakip AIO citation density",
    "competitor schema markup tarama"
  hooks: []
mcp_tools:
  required:
    - "mcp__dataforseo__serp_organic_live_advanced"
    - "mcp__ScraplingServer__fetch"
  optional: []
budget:
  uses_paid_mcp: true
  estimated_credits: 30
autonomy:
  confidence: MEDIUM
  requires_approval: false
  safe_auto_execute: true
---

# aio-competitor-map — discovery skill (Phase 12 Wave 1 / W-G3)

7-step protocol. SERP top-N fetch (DataForSEO heavy endpoint) → her URL
Scrapling tier-1 `fetch` (Apify v1.2+ fallback dökümante) → R-109/R-110/
R-111 AIO sinyal detect (schema.org markup + entity reference +
author authority) → `inbox/competitor_pages/{date}-{slug}.jsonl`
staging-only writer. master.xlsx WRITE YASAK (staging-only; gelecek
phase'de master.xlsx[opportunity] sync skill yapacak — Phase 13+).

Bu skill, Phase 11+ content kuralları R-109..R-111 ile tek pre-content
"AIO landscape" sondaj sinyalini sağlar; bir keyword için competitor'ların
schema.org/entity/authority sinyallerini niceliksel ölçer.

Convention authority: `skills/discovery/competitive-analysis/SKILL.md`
(DFS+Scrapling pattern, raw inbox drift recovery, §14.5 tier ladder
disiplin). Bu skill staging-only path izler ve master.xlsx hiçbir
sheet'ine yazmaz — Phase 7+ ADR-025 staging-first paradigm consumer'ı.

## Inputs (frontmatter contract)

| Name             | Type    | Default  | Notes                                                            |
|------------------|---------|----------|------------------------------------------------------------------|
| `target_keyword` | string  | —        | Required. SERP query string; whitespace-only → DURUR #5 ABORT.    |
| `location`       | string  | "tr-TR"  | BCP-47 locale → DataForSEO location_code+language_code resolver.  |
| `top_n`          | integer | 10       | SERP organic result cap; 0 → DURUR #2 REJECT.                     |

`workspace_root` resolved via `PSEO_WORKSPACE_ROOT` env veya explicit
test override.

## Outputs (artifacts produced)

- `projects/{slug}/inbox/competitor_pages/{date}-{slug}.jsonl` —
  competitor_pages.jsonl staging dosyası. Her satır 1 competitor URL +
  AIO signal payload (R-109 schema markup count, R-110 entity refs,
  R-111 author authority signals). Format: JSON-Lines. **NO Excel
  write** — Phase 7+ staging-only per ADR-025 consumer.
- `projects/{slug}/_state/events.jsonl` — `event_kind=provenance`
  girdileri. `source.kind` ∈ `{dataforseo_mcp, scrapling_mcp}`,
  `target_excel_sheet=null` (staging-only), `target_table=
  scrapling_aio_competitor_map`. `notes` alanı "aio_mapped" semantik
  marker'ını taşır (events.schema event_type=WORK-only; provenance'ta
  notes free-text).

## Schema-First Override Notu (Lesson 7+23)

Brief'in önerdiği `event_type=aio_mapped` field'ı `events.schema.json`
F-8 enum WORK-only kapsamında — provenance event'lerinde
`additionalProperties=false` nedeniyle tip ihlali olur. Worker
schema-first override uygulamıştır:

- `event_kind=provenance` (brief'te zaten doğru).
- Aio_mapped semantic marker → `notes="aio_mapped"` + `target_table=
  scrapling_aio_competitor_map`.
- `operation=ingest` (raw fetch + per-URL signal compute).
- `target_excel_sheet=null` (staging-only invariant).

Bu override schema disipline saygı gösterir; brief drift bulgusu
Output Package'da raporlanır.

## 7-Step Body Protocol

### Step 1 — SERP fetch (DataForSEO heavy, budget guard)

```python
# §16.8 budget pre-flight — DURUR #1 (AMBER + skip skill)
import json
from pathlib import Path

config_path = workspace_root / "projects" / project_slug / "project.config.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
budget_max = config.get("budget_credits_per_day", 500)
consumed_today = consumed_credits_today(events_path)  # events.jsonl rollup
if consumed_today + 30 > budget_max:  # estimated_credits=30
    emit_skipped_event(reason="budget_exceeded")
    raise BudgetExceededError("DURUR #1 — budget_credits_per_day aşıldı")

raw_serp = mcp__dataforseo__serp_organic_live_advanced(
    keyword=target_keyword,
    location_code=resolve_location(location),  # "tr-TR" → 2792
    language_code=resolve_language(location),  # "tr-TR" → "tr"
    depth=top_n,
)
```

### Step 2 — Top-N URL list extract

```python
serp_items = raw_serp.get("tasks", [{}])[0].get("result", [{}])[0].get("items", [])
organic_urls = [item["url"] for item in serp_items if item.get("type") == "organic"][:top_n]
if not organic_urls:
    emit_rejected_event(reason="serp_empty")
    raise SerpEmptyError("DURUR #2 — SERP top_n result 0")
```

Paralel processing OK — her URL bağımsız Scrapling fetch + transform.

### Step 3 — Each URL Scrapling fetch (tier-1 fallback Apify v1.2+)

```text
# Pseudocode (LLM-native skill per Q-PHASE15-AIO-COMPETITOR-01;
# fence intentionally `text` not `python` per Q-V1.2-AIO-COMPETITOR-FENCE-01
# resolution — bare identifier `5xx_marker` is documentation placeholder).
fetched = []
for url in organic_urls:
    try:
        resp = mcp__ScraplingServer__fetch(url=url)  # tier-1
        fetched.append({"url": url, "html": resp.get("html"), "status": resp.get("status_code")})
    except Exception:
        # tier-1 fail → Apify v1.2+ fallback dokümante (§14.5 escalate)
        # Phase 12 minimum: tier-1 only; Apify entry point Phase 13+ yapılacak.
        fetched.append({"url": url, "html": None, "status": 5xx_marker})

all_failed = all(f["html"] is None for f in fetched)
if all_failed:
    emit_amber_event(reason="all_scrapling_5xx", partial=True)
    # DURUR #3 AMBER — boş aio_signals partial result
    return  # graceful exit
```

Tier-1 fallback Apify v1.2+ (§14.5 ladder canonical 'fetch' →
'stealthy_fetch' eşdeğeri) dokümante — Phase 13+ aktivasyonu.

### Step 4 — AIO citation pattern detect (R-109 + R-110 + R-111)

Her fetched URL için 3 sinyal grubu hesaplanır. Saf-compute,
deterministik:

```python
from bs4 import BeautifulSoup  # html parser
import json as _json

def detect_aio_signals(html: str) -> dict:
    if not html:
        return {"r_109_schema": [], "r_110_entities": 0, "r_111_authority": {}}
    soup = BeautifulSoup(html, "html.parser")

    # R-109: Schema.org markup presence (Article, NewsArticle, FAQPage, HowTo)
    schema_types_found = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "{}")
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                t = entry.get("@type")
                if isinstance(t, list):
                    schema_types_found.extend(t)
                elif isinstance(t, str):
                    schema_types_found.append(t)
        except Exception:
            continue  # JSON-LD parse fail → ignore (R-109 enforcement görmez)

    aio_relevant = [t for t in schema_types_found
                    if t in ("Article", "NewsArticle", "FAQPage", "HowTo")]

    # R-110: Entity references count (Person/Organization/Place schema entities)
    entity_count = sum(
        1 for t in schema_types_found
        if t in ("Person", "Organization", "Place", "LocalBusiness")
    )

    # R-111: Author authority signals (sameAs, credentials, byline structure)
    authority = {
        "sameAs_links": 0,
        "credentials_present": False,
        "byline_present": False,
    }
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "{}")
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if entry.get("@type") == "Person" or "author" in entry:
                    author_obj = entry.get("author") or entry
                    if isinstance(author_obj, dict):
                        if author_obj.get("sameAs"):
                            authority["sameAs_links"] += len(
                                author_obj["sameAs"]
                                if isinstance(author_obj["sameAs"], list)
                                else [author_obj["sameAs"]]
                            )
                        if author_obj.get("hasCredential") or author_obj.get("jobTitle"):
                            authority["credentials_present"] = True
        except Exception:
            continue
    if soup.find(class_=lambda c: c and "byline" in c.lower()) or soup.find(rel="author"):
        authority["byline_present"] = True

    return {
        "r_109_schema": aio_relevant,
        "r_110_entities": entity_count,
        "r_111_authority": authority,
    }
```

**R-109 Enforcement:** schema.org markup presence (Article / NewsArticle
/ FAQPage / HowTo). AIO citation pattern empirik olarak bu @type'lar
top citation candidate.

**R-110 Enforcement:** entity reference count (Person / Organization /
Place / LocalBusiness). AIO anti-pattern dökümante; empty count = AIO
citation reddi sinyali.

**R-111 Enforcement:** author authority (sameAs, credentials, byline
structure). Quality-driven hijack için competitor'ın authority skoru
kıyas tabanı.

DURUR #4: tüm URL'lerde aio_signal toplam 0 (R-109..R-111 hiçbiri
detect edilemedi) → AMBER + report empty payload.

### Step 5 — competitor_pages.jsonl staging write

```python
staging_path = (
    workspace_root / "projects" / project_slug / "inbox" / "competitor_pages"
    / f"{date}-{slugify(target_keyword)}.jsonl"
)
staging_path.parent.mkdir(parents=True, exist_ok=True)
total_signals = 0
with staging_path.open("w", encoding="utf-8") as f:
    for fetched_url, signals in zip(organic_urls, all_signals):
        record = {
            "snapshot_date": snapshot_iso_utc,
            "target_keyword": target_keyword,
            "url": fetched_url,
            "rank_position": organic_urls.index(fetched_url) + 1,
            "aio_signals": signals,
        }
        f.write(_json.dumps(record, ensure_ascii=False) + "\n")
        total_signals += (
            len(signals["r_109_schema"]) + signals["r_110_entities"]
            + (1 if signals["r_111_authority"]["byline_present"] else 0)
        )

if total_signals == 0:
    emit_amber_event(reason="aio_signal_empty")  # DURUR #4
```

Her satır 1 competitor URL — JSON-Lines (jsonl) format.

### Step 6 — master.xlsx WRITE YASAK (invariant)

Bu skill master.xlsx'in HİÇBİR sheet'ine yazmaz. `transaction.append`
/ `transaction.update` import edilmez. Bu invariant test
`test_no_master_xlsx_write_invariant` sentinel monkey-patch ile
doğrulanır. Phase 13+ master.xlsx[opportunity] sync ayrı bir skill
tarafından staging dosyasından okunarak yapılacak (parallel pattern:
dfs-pull → cluster-map; ADR-025).

### Step 7 — events.jsonl append (provenance + aio_mapped marker)

```python
from scripts.state import events_writer

# DataForSEO — paid, cost.credits populated
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "dataforseo_mcp",
        "mcp_server": "dataforseo",
        "mcp_tool": "dataforseo__serp_organic_live_advanced",
        "response_bytes": len(_json.dumps(raw_serp)),
    },
    operation="ingest",
    target_excel_sheet=None,
    target_table="scrapling_aio_competitor_map",
    rows_written=len(organic_urls),
    notes="aio_mapped",  # semantic marker (event_type WORK-only)
    cost={
        "provider": "dataforseo",
        "credits": 30,
        "budget_key": "project.config.budget_credits_per_day",
    },
)

# Scrapling — free per URL
events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        "kind": "scrapling_mcp",
        "mcp_server": "ScraplingServer",
        "mcp_tool": "ScraplingServer__fetch",
        "response_bytes": sum(len(f.get("html") or "") for f in fetched),
    },
    operation="ingest",
    target_excel_sheet=None,
    target_table="scrapling_aio_competitor_map",
    rows_written=sum(1 for f in fetched if f.get("html")),
    notes="aio_mapped",
)
```

`target_excel_sheet=null` intentional — staging-only path. Append-only
invariant: events.jsonl asla in-place rewrite görmez (line-append).

## DURUR conditions (5)

Stop and flag the manager — fallback YASAK.

1. **DURUR #1 — `budget_credits_per_day` aşıldı.** project-config
   `budget_credits_per_day` < (consumed_today + estimated_credits=30).
   AMBER → skip skill, `events.jsonl` `notes="skipped"` event,
   raises `BudgetExceededError`.
2. **DURUR #2 — SERP empty.** `top_n=0` ya da DataForSEO 0 organic
   result döndürdü. REJECT, raises `SerpEmptyError`. Hiçbir Scrapling
   call dispatch edilmez.
3. **DURUR #3 — Tüm Scrapling 5xx.** Tüm `top_n` URL'lerin tier-1
   fetch'i fail (HTML None / status 5xx). AMBER + partial result
   (boş `aio_signals`); event'te durum işaretlenir. Apify v1.2+
   fallback Phase 13+ aktivasyon dökümante.
4. **DURUR #4 — AIO signal 0 (toplam).** R-109/R-110/R-111
   sinyallerinden hiçbiri tüm URL'lerde detect edilemedi (cumulative
   total == 0). AMBER + empty payload report. Staging dosyası yine
   yazılır (auditable boş kayıt) — ama `notes="aio_signal_empty"`
   event'i append edilir.
5. **DURUR #5 — `target_keyword` empty / whitespace-only.** Whitespace
   strip sonrası boş string → ABORT, raises `EmptyKeywordError`. Hiçbir
   MCP call yapılmaz, hiçbir staging yazılmaz.

## Foundational Principles 3-Layer Coverage

Bu skill, Phase 11 W-F1 cascade fix sonrası `rules/content-quality.md`
Foundational Principles üç katmanını discovery context'inde uygular:

### Principle 1 — Truth-Verifiable (R-27)

SERP raw response provenance event payload'ında saklanır
(`source.response_bytes` + raw inbox dosyası `inbox/dfs/{date}-
serp_organic_live_advanced-{slug}.json`). Drift recovery: transform
bug'ı upstream payload'ı kaybetmez. Her competitor URL'inden çıkarılan
sinyal R-109/R-110/R-111 deterministik regex/JSON-LD parse — uydurma
yok. Provenance `event_kind=provenance` schema authority bu disipline
zaten enforce eder.

### Principle 2 — Profile-Aware Enforcement

5-value profile enum (`e-commerce`, `ymyl`, `local-service`,
`b2b-saas`, `portfolio`) — AIO sinyallerinin yorumlanmasında profile-
aware ağırlık farkı dökümantedir:

- **YMYL** profilinde E-E-A-T sinyalleri (R-111 author authority,
  sameAs links, credentials) en yüksek ağırlık. Empty authority →
  AIO citation reddi yüksek olasılık.
- **e-commerce** profilinde Product/Offer schema (R-109 alternatif
  varyant) ek sinyal — base detection bu skill kapsamı dışı (Phase
  13+ on-page-audit consumer'ı).
- **local-service** profilinde LocalBusiness/Place entity (R-110)
  ağırlığı yüksek.
- **b2b-saas** profilinde Organization + sameAs (R-111) baskın.
- **portfolio** profilinde minimal authority — düşük ağırlık.

Profile bilgisi `project-config.profile` field'ından okunur (schema
v1.2 sonrası singular field; lesson 8 v2 cascade fix kapsamı).

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

Bu skill **competitor URL üretmez** — bütün competitor URL'leri
DataForSEO `serp_organic_live_advanced` çıktısı kaynaklıdır. Hayali /
fabricate URL üretimi yasak (R-27 truth-verifiable consumer'ı). Skill
sadece SERP'den dönen URL'leri Scrapling ile fetch eder ve sinyalleri
deterministik parse eder. AI tarafından hayali competitor URL üretimi
sentinel-test'le doğrulanır (`test_no_url_fabrication_invariant`).

R-111 quality-driven hijack: competitor'a daha iyi yanıt yarışı için
sinyal kıyas tabanı sağlar — spammy hijack (keyword stuffing) yasaktır
(Principle 1 ihlali).

## Plugin Agnostic Discipline (F-16 Invariant)

Bu skill `.mcp.json` dosyasına byte yazmaz, schema'lara ASLA dokunmaz,
hiçbir slug literali içermez. `project_slug` her path'te parametre
olarak akar; transform 0 hardcoded slug word içerir. F-16 plugin-
agnostic boundary intact — MCP boundary `mcp__dataforseo__*` ve
`mcp__ScraplingServer__*` registry üzerinden referenslı.

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (this frontmatter
  v1.0), `schemas/events.schema.json` (`event_kind=provenance`,
  `target_excel_sheet=null`, F-8 event_type WORK-only — provenance'ta
  kullanılmaz; aio_mapped semantic `notes` field'ında),
  `schemas/project-config.schema.json` v1.2 (`profile` enum 5 value,
  `budget_credits_per_day`).
- Content rules: `rules/content-seo-discipline.md` R-109 (AIO Pattern
  Cevap-Önce + Citation Density), R-110 (AIO Anti-Pattern), R-111
  (AIO Hijack Quality-Driven).
- Sister skills: `skills/discovery/competitive-analysis/SKILL.md`
  (DFS+Scrapling pattern convention authority — staging-only +
  raw-inbox drift recovery), `skills/discovery/quick-wins/SKILL.md`
  (Phase 5 discovery 10-step pattern — bu skill 7-step varyantı,
  DURUR list ve report format paralel).
- Tests: `tests/skills/test_aio_competitor_map.py` (≥12 cases incl.
  frontmatter validity + DURUR #1..#5 sentinel + R-109/R-110/R-111
  detect + master.xlsx WRITE YOK invariant + .mcp.json byte unchanged
  + Foundational Principles 3-layer).

## Discipline checklist

- [x] TODO/fallback YASAK — her DURUR raises.
- [x] Schema-first override (Lesson 7+23) — `event_type=aio_mapped`
      brief drift'i `notes="aio_mapped"`+`target_table=
      scrapling_aio_competitor_map` ile kapatıldı.
- [x] Plugin-agnostic — `project_slug` her path'te parametre, hiç
      hardcoded slug word; `.mcp.json` byte unchanged.
- [x] ADR-013: `Use when` / `Also use when` / `Do not use when` STRING
      content inside `description`.
- [x] Cross-module IMPORT discipline — `events_writer` import edilebilir,
      `scripts.excel.transaction` ASLA import edilmez (staging-only).
- [x] Append-only state — `events.jsonl` line-append; in-place rewrite yok.
- [x] STAGING-ONLY: master.xlsx WRITE YASAK; output path
      `inbox/competitor_pages/{date}-{slug}.jsonl`.
- [x] Foundational Principles 3-katman — Principle 1 truth-verifiable
      provenance event payload, Principle 2 profile-aware 5-enum
      ağırlık dokümante, Principle 3 AI suistimal önlemi (URL
      fabrication yasak — DataForSEO output kaynaklı).
