---
name: generate-images
description: |
  use_when: |
    Hero image üret, blog görseli oluştur, nano-banana image gen,
    8K ultra realistic image, hero image regenerate. Kullanıcı
    "hero image üret", "blog görseli oluştur", "nano-banana image gen",
    "8K ultra realistic image" der ya da `/pseo-generate-images` çağırır.
    master.xlsx[new_content_plan].image_prompt + alt_text source consume;
    project-config[content_settings.image_model] (R-72 plugin agnostik
    serbest string, default nano-banana, override edilebilir);
    project-config[brand_identity.image_style] profile-aware switch
    (Principle 2 enum 5-value: clean-illustration / product-photo /
    diagram-screenshot / location-photo / esnek);
    project-config[brand_identity.default_hero_url] DURUR #5 fallback
    URL. R-71 (8K ultra realistic prompt enrichment) + R-72 (nano-banana
    default model) + R-73 (1200x675 hero size + manual upload trail) +
    R-74 (multi-skill collaborative upload-instructions Section B) +
    R-75 (`<picture>` LCP optimization + loading="eager" +
    fetchpriority="high") + R-76 (AVIF + WebP + JPG format cascade)
    sentinel enforce.
  also_use: |
    new-blog skill collaborative output (Section B append
    upload-instructions.md, R-74 paterni); existing blog hero image
    regenerate (cheap AI artifact / low-res anime drift detect, R-71
    enforcement); brand_identity güncelleme sonrası hero image refresh
    (image_style profile boyutu değişmişse).
  do_not_use: |
    Yeni blog için (new-blog kullan, image plan tetikler);
    FAQ enhance için (faq-optimization kullan); content prune /
    redirect / delete için (content-remediation kullan);
    image upload için (R-74 manual upload, otomatik publish YASAK,
    auto-upload WordPress credential exposure + plugin agnostik
    Ticimax/Ideasoft farklı API).
version: "1.0"
status: wip
category: production
inputs:
  project_slug:
    type: string
    required: true
    description: "Workspace proje slug (resolves projects/{slug}/master.xlsx + outputs/images/ + outputs/blog/{slug}/)."
  new_content_plan_id:
    type: string
    required: true
    description: "master.xlsx[new_content_plan] row id reference (kolon A); image_prompt + alt_text + content_type source (Phase 10 +3 col)."
  image_kind:
    type: string
    required: false
    default: "hero"
    description: "Image kind — currently hero only (enum: [hero], R-73 1200x675 fixed). Future: inline_section (Wave 3 deferred). Schema-first override: schema-frontmatter inputs[].properties whitelist 4 field additionalProperties=false; enum description'a taşındı (W-F3 D1 paterni reuse)."
outputs:
  - "outputs/images/{slug}-{kind}.webp"
  - "outputs/images/{slug}-{kind}.avif"
  - "outputs/images/{slug}-{kind}.jpg"
  - "outputs/blog/{slug}/upload-instructions.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx#new_content_plan"
  - "init-project:projects/{slug}/project.config.json#content_settings.image_model"
  - "init-project:projects/{slug}/project.config.json#brand_identity.image_style"
  - "init-project:projects/{slug}/project.config.json#brand_identity.default_hero_url"
  - "rules:rules/content-quality.md"
  - "rules:rules/content-html-discipline.md"
  - "rules:rules/content-seo-discipline.md"
  - "rules:rules/content-eeat-discipline.md"
  - "rules:rules/content-llm-discipline.md"
  - "rules:rules/content-update-discipline.md"
  - "templates:templates/content/upload-instructions.template.md"
produces:
  - "new-blog"
triggers:
  manual: ["/pseo-generate-images"]
  natural_language: |
    "hero image üret ve 8K ultra realistic prompt enrichment uygula",
    "blog görseli oluştur ve nano-banana image_model default kullan",
    "nano-banana image gen yap ve 1200x675 hero size R-73 zorla",
    "8K ultra realistic image üret ve cheap AI artifact preempt et",
    "hero image regenerate et ve image_style profile-aware switch uygula"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__higgsfield__generate_image"
  optional:
    - "mcp__higgsfield__job_status"
budget:
  uses_paid_mcp: true
  estimated_credits: 5
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# generate-images — production skill (Phase 11 Wave 2 W-F5)

Hero image üretim skill'i. master.xlsx[new_content_plan].image_prompt
+ alt_text source; project-config[content_settings.image_model] consume
(R-72 plugin agnostik); project-config[brand_identity.image_style]
profile-aware switch (Principle 2 enum 5-value); R-71/R-72/R-73/R-74/
R-75/R-76 sentinel enforce. Higgsfield MCP runtime call (Claude tool
registry); fallback `default_hero_url` (DURUR #5). Pillow Image format
cascade (WebP + AVIF + JPG, R-76); `<picture>` tag LCP optimization
(R-75); upload-instructions.md Section B append (R-74 multi-skill
collaborative output).

The skill is **READ-ONLY** with respect to `master.xlsx`
(`new_content_plan` allowed_writers is `null` — F-1 schema authority).
It never calls `transaction.append`, `transaction.update`, or
`transaction.delete` against the workbook. The only state mutation is
the audit append to `_state/events.jsonl` (event_kind=`work` per
ADR-020 + events.schema event_kind discriminator; event_type=`manual`
per F-14 enum).

## 🔴 KRİTİK — Plugin Agnostik MCP Boundary (F-16, Süleyman Seçenek D)

Worker (this skill) **does NOT write to `.mcp.json`.** Higgsfield MCP
is **not a plugin dependency** — it is configured at VS Code user-level
(Süleyman responsibility). When the plugin is given to another user,
Higgsfield availability is NOT mandatory; the skill gracefully falls
back via DURUR #5.

**Boundary contract:**

| Concern                       | Location                                                    | Discipline                                       |
|-------------------------------|-------------------------------------------------------------|--------------------------------------------------|
| `.mcp.json`                   | Project-local (4 servers: gsc, dataforseo, ScraplingServer, sf) | Plugin agnostik; Higgsfield ABSENT (F-16 intact) |
| Higgsfield MCP                | VS Code user-level (Süleyman setup)                         | Per-user, not per-plugin                         |
| `HIGGSFIELD_API_KEY`          | Süleyman `.env` (12-factor app)                              | Never committed; never in plugin                 |
| `mcp__higgsfield__generate_image` | Claude tool registry runtime call                       | Worker calls if available; DURUR #5 if absent    |

**STOP rule:** if a worker proposal requires writing the Higgsfield
server entry into `.mcp.json`, the proposal violates F-16 plugin
agnostik boundary and MUST stop. R-72 (image_model serbest string +
override edilebilir) is the architectural twin of this boundary at the
schema level.

**External dependency preflight (P1-13 registry contract).** Higgsfield is
declared in `mcp-tool-registry.json` under
`external_user_dependencies.higgsfield` (NOT under `servers`) — the governance
representation of a **user-level external MCP** that must already exist in the
operator's own client environment. Step 4 **preflights**
`mcp__higgsfield__generate_image` in the Claude tool registry; if the external
tool is absent the skill does NOT crash — it routes to **DURUR #5** (graceful
`default_hero_url` fallback + a clear "Higgsfield MCP not configured at
user-level" message). This is what lets the registry advertise a
required-but-not-plugin-installed tool without tripping the
`.mcp.json`↔registry server-key invariant (F-24).

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-principles`)
gate this skill end-to-end. No alt-rule (R-01..R-122) overrides them.

### Principle 1 — Truth-Verifiable Content (R-27, Süleyman 5x vurgu)

**Statement (image context).** alt_text + image caption verifiable;
uydurma claim YASAK. Image içerik claim'leri ile actual generated
image arasında consistency required (alt_text "doktor muayenehanesi"
diyorsa generated image medical clinic resmi olmalı, generic stock
photo değil).

**3-katman defense:**
- Layer 1: skill prompt explicit "uydurma alt_text yasak" — Step 7
  upload-instructions.md Section B render öncesi alt_text source
  verify (manuel kayıt new_content_plan.alt_text, AI invent yasak).
- Layer 2: alt_text source verify — `master.xlsx[new_content_plan]`
  row.alt_text consume (manuel typed by Süleyman / new-blog
  collaborator). AI alt_text invention forbidden.
- Layer 3: image_prompt R-71 8K ultra realistic enrichment — low-res
  anime drift detect; cheap AI artifact preempt.

**Failure mode.** RED (image discard, alt_text inconsistency) — DURUR
#6 trigger.

### Principle 2 — Profile-Aware Enforcement

**Statement.** Skill behavior `project.config.json[profile]` enum'una
göre değişir; image_style boyutu profile-driven (project-config
schema image_style enum, 5-value).

**Enum 5-value switch (Step 2 + Step 3):**

| `profile` value  | `image_style`        | Aesthetic intent                                           |
|------------------|----------------------|------------------------------------------------------------|
| `ymyl`           | `clean-illustration` | Medical/legal authoritative aesthetic; sterile composition |
| `e-commerce`     | `product-photo`      | Transactional intent; product-centric studio lighting      |
| `b2b-saas`       | `diagram-screenshot` | Technical clarity; UI/diagram screenshot composition       |
| `local-service`  | `location-photo`     | Local SEO authority; on-location authentic photography     |
| `portfolio`      | `esnek`              | Flexible — creative discretion                             |

**Failure mode.** RED — `image_style` enum dışı bir değer (DURUR #3);
profile resolve etmezse worker AMBER warning + `esnek` fallback.

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

**Statement (image context).** AI'ın doğal cheap content padding
davranışını image generation'da preempt et.

**3-pattern gate (Step 3 + Step 4 implements):**
- R-71 8K ultra realistic prompt enrichment — low-res / anime drift
  preempt (Süleyman explicit "8K ultra realistic" tone preference).
- R-72 image_model `nano-banana` default (cheap AI artifact preempt;
  plugin agnostik override allowed via `content_settings.image_model`
  serbest string).
- Image content cheap padding yasak — decorative-only image RED;
  fact-conveying / entity-illustrating image expected.

**Failure mode.** AMBER warning (auto-correct prompt enrichment
attempt) → RED fail (manuel revise) on 2x AMBER same pass.

## Routing — 7-Step Workflow

> Step names are stable identifiers across runs.

### Step 1 — `read_master_xlsx_row`

`master.xlsx[new_content_plan]` row read where
`id == {input.new_content_plan_id}`. Workbook opens with
`openpyxl.load_workbook(read_only=True)` (F-1 allowed_writers=null).

`new_content_plan` 14 columns consumed (Phase 10 additive bump):
`id, title, url_slug, primary_keyword, monthly_volume,
assigned_cluster, target_word_count, priority, created_date,
tivl_tag, lifecycle_status, image_prompt, alt_text, content_type`.
Step 1 surface fields: `image_prompt` + `alt_text` + `content_type`
+ `url_slug` (output filename slot).

**DURUR #1.** `image_prompt` empty (R-71 prompt eksik) → REJECT;
init-project / new-blog skill paterni new_content_plan row populate
etmeli.

### Step 2 — `read_project_config` (Profile-Aware Switch + R-72 image_model)

`projects/{slug}/project.config.json` parse:
- `content_settings.image_model` — R-72 plugin agnostik serbest string
  (default `nano-banana`, override edilebilir). Schema:
  `{type: string, default: "nano-banana", description: "R-72.
  Plugin agnostik (Higgsfield veya equivalent), per-project override."}`
- `brand_identity.image_style` — project-config schema 5-enum
  profile-aware (`clean-illustration` / `product-photo` /
  `diagram-screenshot` / `location-photo` / `esnek`).
- `brand_identity.default_hero_url` — DURUR #5 fallback URL
  (R-77 image alt_text fallback).
- `profile` (singular, schema v1.2 W-F1) — Principle 2 switch driver.

Profile-aware `image_style` resolve:

```text
if profile == "ymyl":           image_style := "clean-illustration"
elif profile == "e-commerce":   image_style := "product-photo"
elif profile == "b2b-saas":     image_style := "diagram-screenshot"
elif profile == "local-service":image_style := "location-photo"
elif profile == "portfolio":    image_style := "esnek"
```

When `brand_identity.image_style` is set explicitly, the explicit value
wins (override-friendly); profile-mapped value is the default when the
field is null.

**DURUR #3.** `image_style` enum 5-value dışı (project-config
`brand_identity.image_style` enum violation) → REJECT.

### Step 3 — `r71_prompt_enrichment` (8K Ultra Realistic)

R-71 enrichment pipeline (Süleyman explicit "8K ultra realistic" tone
preference; cheap AI artifact / low-res anime drift preempt):

```text
enriched_prompt :=
    "{image_prompt}, "
    "8K ultra realistic, sharp focus, professional photography, "
    "{image_style}, "
    "1200x675 landscape, hero image composition, "
    "high detail, vibrant colors, "
    "no anime/cartoon style, no low-res artifacts"
```

`image_style` is the profile-aware suffix from Step 2 (5-enum
switch). Tone keywords (`8K ultra realistic`, `sharp focus`,
`photographic`) are R-71 mandatory; AI suistimal preempt directives
(`no anime/cartoon style`, `no low-res artifacts`) are P3 mandatory.

### Step 4 — 🔴 `mcp_higgsfield_runtime_call` (Plugin Agnostik MCP Boundary)

**Worker DOES NOT write to `.mcp.json`.** Worker calls
`mcp__higgsfield__generate_image` from the Claude tool registry at
runtime (F-16 Süleyman Seçenek D + R-72 plugin agnostik twin).

```text
mcp__higgsfield__generate_image(
    model        = content_settings.image_model,   # default "nano-banana"
    prompt       = enriched_prompt,                # Step 3 output
    size         = "1200x675",                     # R-73 hero only
    aspect_ratio = "landscape",
)
```

**DURUR #4.** Higgsfield response size != 1200x675 (R-73 hero size
violation) → REJECT.

**DURUR #5 — Higgsfield MCP unavailable.** Claude tool registry'de
`mcp__higgsfield__generate_image` YOK (VS Code user-level setup
eksik veya `HIGGSFIELD_API_KEY` env yok):
- Fallback: `brand_identity.default_hero_url` consume (project-config'den).
- AMBER warning emit: image generation skip.
- upload-instructions.md Section B "manual upload required, fallback
  hero used" mark.
- events.jsonl `event_type=manual` (F-14 enum), `event_kind=work`
  (ADR-020 event_kind discriminator).

**DURUR #2.** Higgsfield budget aşımı (`estimated_credits` 5 cap) →
`scripts/budget/check_budget.py` blocked.

**Plugin agnostik discipline.** Worker:
- DOES NOT write `mcpServers.higgsfield` into `.mcp.json` (F-16
  violation; STOP rule).
- DOES NOT hardcode `HIGGSFIELD_API_KEY` (Süleyman `.env`, 12-factor).
- DOES use `mcp_tools.required: ["mcp__higgsfield__generate_image"]`
  in frontmatter (advisory — worker reports the dependency; user-level
  MCP availability is not enforced via `.mcp.json`).

### Step 5 — `pillow_format_cascade` (R-76)

Generated raw image (PNG/JPEG byte stream) Pillow library ile convert:

| Format | Output path                                  | Rationale                                    |
|--------|----------------------------------------------|----------------------------------------------|
| WebP   | `outputs/images/{slug}-{kind}.webp`          | Modern, geniş browser support (~30% smaller) |
| AVIF   | `outputs/images/{slug}-{kind}.avif`          | Next-gen (~50% smaller); Safari 16+          |
| JPG    | `outputs/images/{slug}-{kind}.jpg`           | Legacy fallback (universal)                  |

R-76 enforcement: 3 format hepsi yazılmalı; tek format yasak.

```python
from PIL import Image
img = Image.open(raw_bytes_io).convert("RGB")
img.save(f"outputs/images/{slug}-{kind}.webp", format="WEBP", quality=85)
img.save(f"outputs/images/{slug}-{kind}.avif", format="AVIF", quality=70)
img.save(f"outputs/images/{slug}-{kind}.jpg",  format="JPEG", quality=88)
```

### Step 5b — `r78_iptc_disclosure_write` (R-78 AI Image Disclosure)

Format cascade tamamlandıktan sonra (Step 5), WebP + JPG outputs IPTC
`DigitalSourceType=TrainedAlgorithmicMedia` metadata ile patch edilir
(Google Merchant Center AI-image disclosure policy + 2026-05-15 AI
Optimization Guide reaffirmation). AVIF silent skip — piexif format
desteklemez (R-78 failure_mode AMBER, R-76 cascade'in WebP + JPG
çıktıları metadata garantisi sağlar).

```python
from scripts.util.iptc_metadata import write_ai_image_disclosure

# AVIF skip — piexif unsupported (documented R-78 failure_mode)
for output_path in [webp_path, jpg_path]:
    write_ai_image_disclosure(output_path)
```

R-78 enforcement (`rules/content-html-discipline.md`). Utility:
`scripts/util/iptc_metadata.write_ai_image_disclosure` (5/5 unit test
PASS — round-trip + idempotent + missing-file + WebP + constant-format).

### Step 6 — `r75_picture_tag_lcp` (LCP Optimization)

R-75 `<picture>` tag generate (LCP-optimized hero):

```html
<picture>
  <source type="image/avif" srcset="outputs/images/{slug}-hero.avif">
  <source type="image/webp" srcset="outputs/images/{slug}-hero.webp">
  <img src="outputs/images/{slug}-hero.jpg"
       alt="{alt_text}"
       width="1200" height="675"
       loading="eager"
       fetchpriority="high">
</picture>
```

LCP optimization directives:
- `loading="eager"` — above-fold hero (lazy load yasak).
- `fetchpriority="high"` — Chromium 102+ priority hint.
- Explicit `width="1200" height="675"` — CLS preempt (R-62 alignment).
- `alt="{alt_text}"` — `master.xlsx[new_content_plan].alt_text`
  consume (Principle 1 truth-verifiable; uydurma alt_text yasak).

The `<picture>` skeleton is rendered into upload-instructions.md
Section B as the canonical reference; the skill itself does not
inject HTML into `outputs/blog/{slug}/article.html` (new-blog skill
owns that artefact, R-74 multi-skill collaborative paterni).

### Step 7 — `append_section_b_and_emit_provenance` (R-74)

`templates/content/upload-instructions.template.md` Section B render
+ append (multi-skill collaborative output; new-blog Section A intact;
revise-content Section C intact when applicable):

```markdown
## Section B — Hero Image Upload (R-74)

**Generated:** {ISO 8601 UTC timestamp}
**Image Style:** {image_style}        # project-config image_style enum
**Image Model:** {image_model}        # R-72 default nano-banana
**Files:**
- WebP: outputs/images/{slug}-hero.webp ({size_kb} KB)
- AVIF: outputs/images/{slug}-hero.avif ({size_kb} KB)
- JPG:  outputs/images/{slug}-hero.jpg  ({size_kb} KB)

**WordPress Manual Upload Steps (R-74):**
1. WordPress admin → Media Library → Add New
2. Upload all 3 format files (WebP + AVIF + JPG); WordPress
   AVIF support v6.5+ (Squoosh fallback if needed).
3. Alt text: "{alt_text}"  # truth-verifiable, P1 Layer 2
4. Insert into blog post hero placeholder
   ({{HERO_IMAGE_URL_REPLACE}} token)
5. Verify <picture> tag rendering (R-75 LCP optimization)
6. PageSpeed Insights LCP < 2.5s + CLS < 0.1 measure
   (R-65 + R-62 alignment)
```

`_state/events.jsonl` append (audit, F-14 + ADR-020 compliance):

| Field            | Value                                                                          |
|------------------|--------------------------------------------------------------------------------|
| `schema_version` | `"1.0"` (events.schema F-14 const)                                              |
| `event_kind`     | `"work"` (ADR-020 event_kind discriminator)                                     |
| `event_type`     | `"manual"` (success AND DURUR #5 fallback) — F-14 12-enum                       |
| `event_id`       | UUID v4                                                                         |
| `timestamp`      | UTC ISO 8601                                                                    |
| `project_id`     | `{input.project_slug}` (F-14 pattern `^[a-z][a-z0-9-]*$`)                       |
| `note`           | `image_generated: kind={image_kind} model={image_model} plan_id={new_content_plan_id}` (note-encoded provenance) |
| `actor`          | `agent:generate-images` (canonical code block)                                 |
| `image_kind`     | `{input.image_kind}` (default `hero`)                                          |
| `image_model`    | `{content_settings.image_model}` (R-72 plugin agnostik)                         |
| `image_style`    | `{brand_identity.image_style}` (project-config image_style enum, profile-aware) |

Canonical events_writer invocation (schema-first override 16'ıncı uygulama —
`event_type=manual` + `note=image_generated` paterni; `content_new` schema'da
url + url_normalized + after + pillar mandatory koşar, standalone hero
regenerate scope'unda yok → faq-optimization + content-remediation
precedent paterni reuse):

```python
import os
import sys
import hashlib

sys.path.insert(0, os.getcwd())

from scripts.state import events_writer

# Synthetic task_id mint (whats-next paterni reuse, schema regex ^T-[0-9]{4,}$)
hex_token = hashlib.sha1(str(new_content_plan_id).encode()).hexdigest()[:4]
synthetic = 90000 + (int(hex_token, 16) % 9999)
task_id = f"T-{synthetic}"

# WORK event — schema-first override (manual + note=image_generated)
# DURUR #5 (Higgsfield unavailable) durumunda da aynı paterni: event_type=manual.
events_writer.append_work(
    project_id=project_slug,
    event_type="manual",
    task_id=task_id,
    note=(
        f"image_generated: kind={image_kind} model={image_model} "
        f"plan_id={new_content_plan_id}"
    ),
    actor="agent:generate-images",
    primary_source="manual",
)
```

The synthetic `task_id` mint paterni preserves provenance traceability via
the `note` field (`plan_id={new_content_plan_id}`) without coupling the
skill to a `master_task` row that may not exist (new_content_plan can be
1:N to master_task; init-project may delay master_task population).
Schema-first override 16'ıncı uygulama: rules/events-writer.md Section 4
matrix `generate-images → content_new + image_generated` direkt match
gibi görünse de events.schema URL-bearing work event constraints
(`url + url_normalized + after + pillar` REQUIRED) standalone hero
regenerate scope'unda satisfy edilemez; `manual + note=image_generated`
schema authority + intent preservation = doğru fit.

## DURUR Conditions (6)

| #  | Trigger                                                                    | Resolution                                                         |
|----|----------------------------------------------------------------------------|--------------------------------------------------------------------|
| 1  | `master.xlsx[new_content_plan].image_prompt` empty (R-71 prompt eksik)      | REJECT — new-blog / init-project row populate etmeli                |
| 2  | Higgsfield budget aşımı (`estimated_credits` 5 cap)                         | `scripts/budget/check_budget.py` blocked                            |
| 3  | `image_style` project-config 5-enum dışı                                    | REJECT — schema authority cascade fix verify                        |
| 4  | Higgsfield response size != 1200x675 (R-73 hero size violation)             | REJECT — model param mismatch, retry with explicit size param       |
| 5  | Higgsfield MCP unavailable (Claude tool registry'de YOK; F-16 plugin agnostik) | Fallback `brand_identity.default_hero_url` + AMBER + `event_type=manual` |
| 6  | P1 truth-verifiable: alt_text uydurma claim detect                          | RED — image discard, alt_text source verify                         |

## Plugin-Agnostic Discipline

- **🔴 `.mcp.json` Higgsfield server entry YASAK** (F-16 Süleyman
  Seçenek D; R-72 architectural twin). Worker STOP rule on this
  proposal.
- No project slug hardcoded inside this skill (`dentnotion`, `vento`,
  `eykom`, `bigcattr`, `calitte`, `lastiksa`, `noraninsaat`, `adstark`
  are FORBIDDEN tokens — pytest grep verifies).
- `image_model` resolves at runtime from `content_settings.image_model`
  (R-72 serbest string, override edilebilir; default `nano-banana`).
- `image_style` resolves at runtime from `brand_identity.image_style`
  (project-config image_style 5-enum) or profile-mapped default.
- `default_hero_url` resolves at runtime from
  `brand_identity.default_hero_url` (R-77 fallback hero, DURUR #5).
- Per-call / per-url credit shape names (Phase 7 lesson, ADR-028
  anti-pattern) MUST NOT appear — `budget.estimated_credits` (number)
  is the only allowed shape.

## WCAG 2.1 AA Accessibility

- `<img alt="...">` zorunlu (R-77; non-decorative hero image; alt_text
  source `master.xlsx[new_content_plan].alt_text`, uydurma yasak).
- Explicit `width` + `height` attributes (CLS preempt, R-62).
- h3 visible focus state — `<picture>` çevresi `<figure>` wrap
  edilecekse (new-blog skill owns), `figcaption` h3 hierarchy preserve.
- focus-visible CSS hint (R-39 axe-core simulate): `<picture>`
  interactive element değil; ancak çevresel `<a>` link wrap edilirse
  `:focus-visible` outline mandatory.

## Error Handling

| Failure                                              | Mode  | Action                                                  |
|------------------------------------------------------|-------|---------------------------------------------------------|
| `new_content_plan.image_prompt` boş                  | RED   | DURUR #1 — REJECT, prompt source eksik                  |
| Higgsfield budget exhausted                          | RED   | DURUR #2 — `check_budget.py` blocked                    |
| `image_style` enum dışı                              | RED   | DURUR #3 — schema cascade fix verify (v1.2 W-F1)        |
| Higgsfield response 1200x675 size mismatch           | RED   | DURUR #4 — REJECT, retry with explicit size             |
| Higgsfield MCP runtime registry'de YOK               | AMBER | DURUR #5 — `default_hero_url` fallback, `event_type=manual` |
| P1 truth-verifiable alt_text uydurma                 | RED   | DURUR #6 — image discard, alt_text source verify        |
| Pillow AVIF encode fail (libavif missing)            | AMBER | WebP + JPG only fallback; AVIF skip mark in Section B   |
| `<picture>` LCP measurement > 2.5s post-publish      | AMBER | manual measure post-upload, R-75 enforcement check      |

## References

- `rules/content-quality.md` (Foundational Principles 1+2+3,
  R-01..R-122).
- `rules/content-html-discipline.md` (R-71 8K ultra realistic,
  R-72 nano-banana default, R-73 manual upload, R-74 multi-skill
  collaborative output, R-75 LCP optimization, R-76 format fallback,
  R-77 alt text, R-78 IPTC DigitalSourceType disclosure).
- `rules/content-seo-discipline.md` (R-65 LCP < 2.5s ranking signal,
  R-62 CLS preempt).
- `rules/content-eeat-discipline.md` (R-44 source verify; image
  authority signal).
- `schemas/project-config.schema.json` v1.2
  (`content_settings.image_model` serbest string default `nano-banana`;
  `brand_identity.image_style` 5-enum; `brand_identity.default_hero_url`
  format=uri).
- `schemas/master-excel.schema.json` (`new_content_plan` 14 col Phase
  10 +3 col additive: `image_prompt`, `alt_text`, `content_type`).
- `schemas/events.schema.json` (event_kind=`work` ADR-020 discriminator;
  event_type 12-enum F-14: `manual` for success AND DURUR #5 fallback).
- `schemas/skill-frontmatter.schema.json` (8 required fields, category
  enum 8 values, status enum 3 values, `mcp_tools.required` advisory).
- `.mcp.json` (4 servers: `gsc`, `dataforseo`, `ScraplingServer`, `sf`;
  Higgsfield ABSENT — F-16 plugin agnostik boundary intact).
- ADR-020 (event_kind=workflow vs work routing).
- ADR-028 (per-call / per-url credit shape anti-pattern).

## Wave-Out Note

This skill is `status: wip` until Phase 11 Wave 2 acceptance gate;
`active` bump deferred to the post-Wave 2 closeout. Manager owns the
status flip + governance audit. Atomic commit Wave 2 6'ıncı kanıt
hedef (W-F3 + W-F4 + W-F5 paralel atomic dispatch + drift sıfır).
