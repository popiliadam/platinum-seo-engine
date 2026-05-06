---
name: brand-onboarding
description: |
  Use when: kullanıcı "yeni proje", "brand onboarding", "proje bootstrap",
  "wizard çalıştır", "yeni site ekle", "project-config oluştur" der ya da
  /pseo-brand-onboarding çağırır; brand_identity 18 + content_settings 14
  + profile enum 5-value Süleyman input'u alarak project-config.schema 1.2
  conformant staging output üretir.
  Also use when: workspace henüz yok (Phase 14 öncesi staging-only mode);
  domain DNS doğrulanması gerekiyor; profile heuristic suggest fallback
  istendi; init-project çalıştırılmadan önce config wizardı isteniyor.
  Do not use when: mevcut proje config update için (separate edit-config
  skill — gelecek phase); workspace var ve direkt project.config.json
  yazılacak (Phase 14+ behavior; init-project devreye giriyor); başka
  projenin config'i kopyalanacak (template-clone — gelecek phase).
version: "1.0"
status: active
category: meta
inputs:
  project_slug: { type: string, required: true,  description: "kebab-case slug (^[a-z][a-z0-9-]*$). Reserved word check (admin/system/root/api/www) + projects/{slug} collision check (DURUR #2)." }
  domain:       { type: string, required: true,  description: "URI format + DNS resolve sanity. DURUR #6 fallback AMBER (Süleyman manual confirm)." }
  profile_hint: { type: string, required: false, description: "Optional 5-value enum (e-commerce, ymyl, local-service, b2b-saas, portfolio). Otomatik suggest fallback when omitted (domain heuristic)." }
outputs:
  - "_state/events.jsonl"
  - "outputs/onboarding/{slug}-staging-config.json"
consumes:
  - "schemas/project-config.schema.json"
triggers:
  manual: ["/pseo-brand-onboarding"]
  natural_language: "\"yeni proje aç\", \"brand onboarding başlat\", \"project-config oluştur\", \"proje bootstrap çalıştır\", \"wizard çalıştır\", \"yeni site ekle\", \"brand kimliğini gir\""
  hooks: []
  scheduled: []
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# brand-onboarding — meta skill (Phase 12 Wave 1, W-G2)

10-step interactive wizard that captures brand identity + content
settings + profile hint from Süleyman, validates against
`schemas/project-config.schema.json` v1.2, and emits a
**staging-only** config artifact under `outputs/onboarding/`. The
canonical `projects/{slug}/project.config.json` write is
deferred to Phase 14 (workspace bring-up); pre-Phase-14 invocations
remain non-destructive — STAGING-ONLY mode (DURUR #5 surfaces an
AMBER warning but does NOT block the wizard). Süleyman'ın manuel
onayı (`approval_received=true`) zorunlu (DURUR #1) — onay yoksa
events.jsonl'a yazma yapılmaz, hiçbir staging dosyası kalıcı
kabul edilmez.

## Foundational Principles enforcement (3-layer)

1. **Truth-verifiable (Principle 1, R-27)** — Süleyman'ın cevapları
   `events.jsonl` payload'una (`notes` field, `event_kind=workflow`
   discipline) **birebir aktarılır**. Skill kendi kafasından alan
   tahmin etmez; eksik alanı AMBER ile geri sorar (DURUR #3).
2. **Profile-aware (Principle 2; profile-aware enforcement)** — `profile_hint` 5-value
   enum'una (`e-commerce | ymyl | local-service | b2b-saas |
   portfolio`) **type-safe** kilitlenir. 6. değer reddedilir
   (DURUR #4). `profile_hint` boşsa domain heuristic suggest
   (TLD pattern, kelime regex) Süleyman'a sunulur — son kararı
   Süleyman verir (autonomy boundary).
3. **AI suistimal yasağı** — Skill brand_identity 18 + content_settings
   14 alanını ASLA otomatik doldurmaz. Her alan Süleyman input
   prompt'undan gelir; Süleyman boş bıraktıysa default eklenmez,
   prompt yeniden iterate edilir (DURUR #3) ve seçim AMBER ile
   netleştirilir.

## Inputs (frontmatter contract)

| Name           | Type    | Required | Notes                                                                     |
|----------------|---------|----------|---------------------------------------------------------------------------|
| `project_slug` | string  | yes      | kebab-case (`^[a-z][a-z0-9-]*$`) + reserved word + collision check.       |
| `domain`       | string  | yes      | URI format + `socket.gethostbyname` DNS sanity. AMBER fallback (#6).      |
| `profile_hint` | string  | no       | 5-value enum. Boşsa heuristic suggest. 6. değer REJECT (#4).              |

## Outputs (artifacts produced)

- `_state/events.jsonl` — workflow lifecycle event (event_kind=workflow,
  workflow_action=done, workflow_run_id={generated}). **Yazılır
  YALNIZCA** Süleyman onayı geldikten sonra (DURUR #1).
- `outputs/onboarding/{slug}-staging-config.json` —
  project-config.schema.json v1.2 conformant staging artifact;
  validation amaçlı, `projects/{slug}/project.config.json`
  DEĞİLDİR (DURUR #5 STAGING-ONLY mode).

## 10-Step Body Protocol

### Step 1 — Validate `project_slug`

Regex `^[a-z][a-z0-9-]*$` (project-config.schema.project_id pattern).
Reserved word check: `admin`, `system`, `root`, `api`, `www`,
`config`, `static`, `assets`, `public`, `private`, `internal`. Bu
slug'lar workspace bootstrap pipe'ında çakışma yaratır → REJECT.
Mevcut `projects/{slug}/` dizini varsa DURUR #2.

### Step 2 — Validate `domain`

URI format kontrolü (`urllib.parse.urlparse` scheme + netloc) +
`socket.gethostbyname(host)` DNS sanity (Python stdlib, harici
bağımlılık yok). DNS resolve fail olursa DURUR #6 — AMBER prompt
("Bu domain DNS'te bulunamadı. Manuel onay verir misin? [y/N]").
Süleyman onaylarsa devam, aksi halde ABORT.

### Step 3 — Suggest `profile`

`profile_hint` set ise direkt geç. Değilse heuristic:

| Heuristic                                      | Suggest        |
|------------------------------------------------|----------------|
| Domain TLD `.shop`, `.store`, alt-domain `mağaza`, `shop` regex | e-commerce     |
| Pattern `klinik\|hastane\|saglik\|hukuk\|finans`                | ymyl           |
| Pattern `tamir\|servis\|nakliyat\|temizlik` + `.com.tr`         | local-service  |
| Pattern `app\|saas\|platform\|api` + `.io\|.dev`                | b2b-saas       |
| Pattern `portfolyo\|portfolio\|kisisel`                         | portfolio      |

Heuristic önerisini Süleyman'a göster, "Bu mu? [y/N + alternatif
seç]" prompt. Son kararı **Süleyman** verir.

### Step 4 — Brand identity 20-field interactive prompt

Her alan ayrı prompt; default YOK (AI suistimal yasağı). Skip
edilen alan AMBER + iterate (DURUR #3). 20 alan sırası (v1.3
ADR-030 ile 18 → 20: `pronoun_preference` + `formality` canonical
eklendi; eski `hitap` + `tone` 1-yıl deprecated alias):

1. `logo_url` — URI
2. `primary_color` — `^#[0-9a-fA-F]{6}$`
3. `secondary_color` — `^#[0-9a-fA-F]{6}$`
4. `accent_color` — `^#[0-9a-fA-F]{6}$`
5. `font_family_heading` — string
6. `font_family_body` — string
7. `header_template_id` — enum [`minimal`, `classic`, `ecom`]
8. `footer_template_id` — enum [`minimal`, `full`]
9. `source_url_for_sampling` — URI
10. `tone` — enum [`semi-pro`, `conversational`, `formal`, `casual`] — DEPRECATED v1.3 (use `formality`)
11. `formality` — enum [`semi-pro`, `conversational`, `formal`, `casual`] — v1.3 canonical
12. `hitap` — enum [`sen`, `siz`] — DEPRECATED v1.3 (use `pronoun_preference`)
13. `pronoun_preference` — enum [`sen`, `siz`] — v1.3 canonical
14. `anglicism_tolerance` — enum [`low`, `medium`, `high`]
15. `tone_phrases_blocklist` — array<string>
16. `font_heading` — string (alias of #5)
17. `font_body` — string (alias of #6)
18. `default_hero_url` — URI
19. `same_as_urls` — array<URI>
20. `image_style` — enum [`clean-illustration`, `product-photo`,
    `diagram-screenshot`, `location-photo`, `esnek`]

### Step 5 — Content settings 14-field interactive prompt

Aynı disiplin (default yok, skip = AMBER iterate). 14 alan:

1. `toc_strategy` — enum [`none`, `static`, `sticky`, `auto-generate`]
2. `related_posts_strategy` — enum [`none`, `cluster`, `tag-based`, `manual`]
3. `author_strategy` — enum [`none`, `byline-required`, `byline-optional`, `person-schema-only`]
4. `css_strategy` — enum [`inline`, `external-tier`, `hybrid`]
5. `indexnow_enabled` — boolean
6. `ai_training_optin` — boolean
7. `video_integration` — enum [`none`, `youtube`, `vimeo`, `self-hosted`]
8. `internal_data_sharing` — boolean
9. `external_uniqueness_check` — boolean
10. `original_research_database` — array<object>
11. `experience_database` — array<object>
12. `video_database` — array<object>
13. `disclaimer_templates` — object<string,string>
14. `image_model` — string (default-aware: `nano-banana`)

### Step 6 — `projects/{slug}/project.config.json` YAZILMAZ

Phase 14 öncesi workspace yok ya da skill scope dışında. Bu adım
explicit no-op: skill **asla** `projects/{slug}/config/` dizinine
yazmaz. STAGING-ONLY (DURUR #5).

### Step 7 — Emit staging output package

`outputs/onboarding/{slug}-staging-config.json` yazılır. İçerik
`schemas/project-config.schema.json` v1.2 ile (Draft7) **validate
edilir**; başarısızsa DURUR #3 (eksik alan iterate). Schema PASS
olunca artifact diske inilir. Bu **staging** output; `init-project`
Phase 14'te bunu input olarak okuyabilir, ama buradaki dosya
otoritatif değildir.

### Step 8 — Süleyman onayı (DURUR #1)

Skill `awaiting_approval` durumuna geçer. Onaylanmadan:
- `events.jsonl` yazılmaz
- staging artifact "draft" işaretlidir (file_name suffix `.draft`
  yerine değil — onay öncesi zaten yazılmış olabilir; gerçek gating
  events.jsonl appendinde)
- ABORT path'i temizdir (no event, no portfolio touch)

Onay komutu: Süleyman explicit "evet/onaylıyorum/y" yazar →
`approval_received=true`. Hayır/atlama → ABORT.

### Step 9 — Append `_state/events.jsonl` (ONLY ON APPROVAL)

```jsonc
{
  "schema_version": "<events.schema $.const>",
  "event_kind": "workflow",
  "workflow_action": "done",
  "workflow_run_id": "<uuid>",
  "step_index": 8,
  "event_id": "brand_onboarded_<slug>_<timestamp>",
  "timestamp": "<ISO8601 UTC>",
  "project_id": "<project_slug>",
  "notes": "brand-onboarding wizard complete; semantic_marker=brand_onboarded; profile=<chosen>"
}
```

> **Schema-first override (Lesson 7+23):** Brief `event_type=brand_onboarded`
> öneriyor; ancak `events.schema.json` `event_type` enum'u 10-value
> WORK-only kapalı liste (`content_new`, `content_revise`, ...).
> `event_kind=workflow` için doğru alanlar `workflow_action` (8-value
> lifecycle) + `workflow_run_id`. Semantic marker olarak `brand_onboarded`
> string'i `notes` field'una taşınır — schema invariant korunur,
> intent kaybolmaz.

### Step 10 — Output report

Süleyman'a `outputs/onboarding/{slug}-staging-config.json` path,
chosen profile, 18 brand_identity + 14 content_settings field
özet tablosu, ve "Phase 14 init-project bu staging dosyasını
input olarak okuyacak" notu raporlanır.

## DURUR conditions (6)

Stop and flag the manager — do not patch, do not fall back silently.

1. **DURUR #1 — Süleyman onayı yok.** `approval_received != true` →
   ABORT. `events.jsonl` yazılmaz, staging artifact orphan kalır
   (cleanup audit ledger sorumluluğu).
2. **DURUR #2 — `project_slug` çakışması.** `projects/{slug}/`
   dizini var ya da reserved word listesi (admin/system/root/api/www
   vs.) ile çakışıyor → REJECT.
3. **DURUR #3 — Brand identity / content settings zorunlu alan
   eksik.** Süleyman alan atladı → AMBER + prompt yeniden iterate.
   Skill default doldurmaz (AI suistimal yasağı).
4. **DURUR #4 — `profile_hint` enum dışı.** 5-value (`e-commerce`,
   `ymyl`, `local-service`, `b2b-saas`, `portfolio`) dışı seçim →
   REJECT. Type-safe assert; 6. değer kabul edilmez.
5. **DURUR #5 — Workspace yok (Phase 14 öncesi).** `projects/`
   dizini engine repo'sunda yok → STAGING-ONLY mode (warning, devam).
   `projects/{slug}/project.config.json` ASLA yazılmaz.
6. **DURUR #6 — Domain DNS resolve fail.** `socket.gethostbyname`
   exception fırlatır → AMBER prompt; Süleyman manual confirm
   verirse devam, "no" derse ABORT.

## Plugin agnostik invariant (F-16)

Bu skill `.mcp.json` dosyasına **ASLA** yazmaz, MCP tool sözleşmesi
yoktur (`mcp_tools.required = []`, `mcp_tools.optional = []`).
Phase 11+ plugin agnostik MCP boundary korunur; byte-hash sentinel
test'le doğrulanır (`tests/skills/test_brand_onboarding.py`).

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (frontmatter
  contract), `schemas/project-config.schema.json` v1.2 (staging
  artifact validation), `schemas/events.schema.json` v1.0
  (workflow event_kind discipline ADR-020).
- Skills: `init-project` (Phase 14 staging consumer),
  `load-context`, `whats-next` (meta peer skills).
- Lessons: 7+23 (worker schema-first override yetkisi), 28
  (manager mop-up matrisi), 30 (plugin agnostik MCP boundary F-16),
  32 (atomic phase paterni).
- Tests: `tests/skills/test_brand_onboarding.py` (15 case;
  frontmatter + 6 DURUR + plugin agnostik + 3-layer principles +
  schema staging conformance).
