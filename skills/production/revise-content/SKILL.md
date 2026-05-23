---
name: revise-content
description: |
  Use when: kullanıcı "blog revize et", "içerik güncelle",
  "decay düzelt", "section revise et", "blog tazele", "post güncelle",
  "article refresh" der ya da `/pseo-revise` çağırır. master.xlsx
  [content_decay] satırından action="revise" alındığında, R-87
  section-targeted diff workflow uygulanır, R-88 freshness theater
  preempt edilir, R-89 canonical preserve edilir.
  Also use when: GSC clicks delta drop > threshold detect edildiğinde
  (R-85 multi-signal: clicks_delta < -20%, delta_pct < -15%, trend
  "down" 3-month rolling); manuel revise request var ve mevcut blog
  outputs/blog/{slug}/article.html olarak diskten okunabiliyor;
  project-config[profile] enum 5-değer (e-commerce | ymyl |
  local-service | b2b-saas | portfolio) içinden biri sabit ve revize
  sırasında profile-aware tone preserve edilecek (Principle 2).
  Do not use when: yeni blog için (new-blog skill kullan); FAQ block
  re-render için (faq-optimization Wave 2 kullan); decay action
  "prune"/"redirect"/"delete" için (content-remediation Wave 2
  domain); image generation için (generate-images kullan); existing
  HTML diskte yok (DURUR #1, R-89 canonical preserve enforce
  edilemez); R-85 multi-signal threshold satisfied değil (DURUR #3,
  revize gereksiz); R-87 section-targeted yasak ve scope=full
  manuel approve olmadan (DURUR #5).
version: "1.0"
status: active
category: production
inputs:
  project_slug:
    type: string
    required: true
    description: "Workspace proje slug (resolves projects/{slug}/master.xlsx + outputs/blog/{slug}/)."
  url:
    type: string
    required: true
    description: "master.xlsx[content_decay].url referansı (mevcut blog kanonik URL)."
  scope:
    type: string
    required: false
    default: "section"
    description: "Revize scope — 'section' (R-87 default zorunlu) veya 'full' (DURUR #5 manuel approve gate)."
outputs:
  - "outputs/blog/{slug}/article.html"
  - "outputs/blog/{slug}/change_summary.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx#content_decay"
  - "master-task-sync:master.xlsx#master_task"
  - "init-project:projects/{slug}/project.config.json"
  - "rules:rules/content-quality.md"
  - "rules:rules/content-html-discipline.md"
  - "rules:rules/content-seo-discipline.md"
  - "rules:rules/content-eeat-discipline.md"
  - "rules:rules/content-llm-discipline.md"
  - "rules:rules/content-update-discipline.md"
  - "templates:templates/content/revision.template.md"
produces:
  - "indexing-ping"
triggers:
  manual: ["/pseo-revise"]
  natural_language: |
    "blog revize et ve decay düzelt section-targeted",
    "içerik güncelle ve dateModified bump et freshness koruyarak",
    "section revize et ve canonical URL preserve et değiştirme",
    "blog tazele R-87 section-targeted scope ile değiştir",
    "post güncelle ve R-88 freshness theater preempt et"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__gsc__search_analytics"
  optional:
    - "mcp__dataforseo__dataforseo_labs_google_keyword_overview"
budget:
  uses_paid_mcp: true
  estimated_credits: 2
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# revise-content — production skill (Phase 11 Wave 1 W-F2)

Section-targeted revise skill. master.xlsx[content_decay] satırından
action="revise" alır, R-87 section-targeted diff uygular, R-88
freshness theater preempt eder, R-89 canonical preserve eder, R-103
content version increment eder. READ-ONLY contract: master.xlsx
[content_decay] + master_task sheet'lerine YAZMAZ (allowed_writers
null + master_task protected_columns 7 alan); sadece outputs/ + _state
yazar.

## Foundational Principles (Üst-Prensip — Alt-Rule Override Edemez)

### Principle 1 — Truth-Verifiable Content (R-27, 3-katman defense)

Tüm content/source/link/data %100 doğru ve kanıtlanabilir; uydurma
yasak. Revise context'inde:

- **Layer 1 (pre-revise):** revise prompt başlangıcında "uydurma
  yasak" sentinel; revision.template.md `truth_verifiable: true`
  field zorunlu.
- **Layer 2 (post-revise):** fact-check pass — yeni claim'lerin
  kaynak verify (R-44 source verification + R-105 expert quote).
- **Layer 3 (citation):** citation enforce — eklenen her stat/quote
  source URL ile bağlanır.
- **Failure mode:** P1 fact-check fail → DURUR #7 RED (revize iptal,
  çıktı discard, dateModified bump YOK).

### Principle 2 — Profile-Aware Enforcement (project-config[profile])

Skill behavior project.config.json[profile] enum'una göre değişir.
Enum 5-value: `e-commerce` | `ymyl` | `local-service` | `b2b-saas` |
`portfolio`.

- `profile == "ymyl"` → counter-argument (R-50) korunur, revize
  sırasında counter-argument silinemez; byline (R-28) preserve
  edilmeli, author değişmez (R-89 canonical adjacent).
- `profile == "e-commerce"` → conversational tone preserve, CTA
  freshness güncelle.
- `profile == "local-service"` → location signal preserve (NAP
  consistency).
- `profile == "b2b-saas"` → formal tone + diagram/screenshot
  preserve.
- `profile == "portfolio"` → showcase entity preserve (project
  list).

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

AI'ın doğal cheap content padding davranışını preempt et. Revise
context'inde:

- **R-88 freshness theater check:** dateModified bump + content
  delta orantılı olmalı; `delta == 0 AND claim_delta == 0 AND
  structure_hash unchanged` → RED (sahte tarih güncelleme).
- **Section-targeted scope (R-87):** full overhaul yasak default;
  scope=section default; scope=full manuel approve gate (DURUR #5).
- **Per-section change quantification:** word delta + structure
  delta + claim delta hesaplama, change_summary.md'ye log.

## R-121 Bank Selection Logic (Pre-Revise + Pre-Publish)

Bank entry (R-105 expert quote / R-114 original research / R-119
first-hand experience) selection passes a **3-step filter**, with one
revise-specific addition: the existing article's already-cited bank
entries count toward the density cap. R-121 is **per content**, not
per skill invocation — replacing a stale fact with a new bank entry
adds, removing one subtracts, holding one steady leaves the cap
unchanged.

**Step 4 (Existing Blog Parse) addition:** during the BeautifulSoup
parse, also extract pre-revise bank citations. Two detection paths:
- `<blockquote data-bank-entry-id="exp-..." />` or
  `<aside data-bank-entry-id="res-..." />` — explicit attribution
  attribute (preferred; new-blog runtime will emit this once Phase 11
  Wave 2 lands).
- Text-matching fallback for older articles without
  `data-bank-entry-id`: regex against `entry.claim_core` + phrasings
  of every bank entry in `project.config[content_settings.
  experience_database] ∪ original_research_database`.

The detected entries form `bank_entries_pre[]`; the revise pass then
runs the 3-step filter against `bank_entries_pre[] ∪ candidates_new[]`:

1. **Topic match.** `entry.applicable_topics ∩ (decay_row.url_slug ∪
   decay_row.matched_keywords ∪ topical_map[matching_row].cluster) ≠ ∅`
   → entry remains a candidate; empty intersection → entry skipped
   (and if it was a pre-revise entry, the removal is logged in
   change_summary.md as "bank entry pruned: topic no longer matches
   revised content").
2. **Profile density cap.** Apply the per-profile maximum to the
   union set:
   - YMYL: 2 experience + 1 research entry per content
   - b2b-saas: 1 experience + 1 research entry per content
   - e-commerce / local-service / portfolio: 1 experience + 0 research
     entry per content
   If `|bank_entries_pre|` already meets or exceeds the cap, **no new
   entries are introduced during revise** — the skill rotates phrasings
   on existing entries instead.
3. **Rotation (30-day).** For each NEW candidate (not pre-revise),
   count usage in `master.xlsx[completed_work]` rows where
   `bank_entry_id == entry.id` AND `timestamp >= now - 30d`. Skip if
   `count >= entry.max_usage_per_month`. Pre-revise entries are
   exempted from rotation (they are already on the page; removing them
   only to satisfy the rotation cap would be churn).

If a pre-revise entry fails topic match (filter 1), the revise drops
it from the article; this counts as a `claim_delta -= 1` for the R-88
freshness-theater check (Step 6) — a genuine content delta, not a
fake bump.

**R-89 canonical interplay.** Bank entry attribution (the
`data-bank-entry-id` attribute on `<blockquote>` / `<aside>`) is part
of the article's content signal, not its canonical URL. Changing
which entries are cited does **not** trigger R-89 canonical change —
only URL slug changes do (R-91 redirect path).

**Post-publish state mutation** (Step 8 events.jsonl append):
- For each entry **newly introduced** in this revise, its
  `last_used_in_content_id` is set; the `master.xlsx[completed_work]`
  row records the `bank_entry_id`(s) added.
- For each pre-revise entry **retained**, no change (already counted
  in a prior `completed_work` row when the article originally
  shipped).
- For each pre-revise entry **dropped**, the change_summary.md logs
  the removal but does NOT touch the original `completed_work` row —
  historical attribution preserved (append-only state, R-rule
  events-writer discipline).

**Schema enablement (v1.4, commit `8e07e1c`):** R-121 reads
`applicable_topics`, `phrasings`, `last_used_in_content_id`,
`max_usage_per_month` on each bank entry. Stage C of brand-onboarding
(commit `cb8df43`) populates these via R-44 evidence-gated atomic
write.

**Runtime integration deferred to Phase 11 Wave 2.** This SKILL.md
section is the spec lock; `scripts/production/revise_content.py` does
not yet exist. When Wave 2 lands the runtime, the pre-revise
extraction lives in Step 4; the 3-step filter runs between Step 5
(section-targeted detect) and Step 6 (revise generate).

## Schema Authority Compliance

- **F-2:** `master.xlsx[content_decay].action` schema'da type/enum/
  description null. Bu skill action enum'unu R-86/R-87/R-90/R-91
  rules'tan **rule-derived** consume eder (string compare):
  `revise` / `prune` / `redirect` / `delete`.
- **F-6:** `master.xlsx[content_decay].allowed_writers` null →
  READ-ONLY consume; `transaction.append/update/delete` YASAK.
- **F-3 (W-F1 paralel):** project-config schema 1.2 + profile enum
  5-value W-F1 worker tarafından uygulanıyor; bu skill profile
  field'ı **var olduğu varsayımıyla** consume eder (Principle 2
  switch).
- **F-8:** events.jsonl `event_type=content_revise` (10-enum içinden
  4'üncü değer).

## Routing (8-Step Workflow)

### Step 1: master.xlsx Read + Action Verify (F-2 rule-derived)

`master.xlsx[content_decay]` satırı `url == {input.url}` filtresiyle
okunur. Action string compare (schema'da enum null, R-86/R-87/R-90/
R-91 rules'tan derive):

- `action == "revise"` → bu skill trigger devam.
- `action == "prune"` → DURUR #2 (content-remediation Wave 2 domain).
- `action == "redirect"` → DURUR #2 (content-remediation Wave 2).
- `action == "delete"` → DURUR #2 (content-remediation Wave 2).

DURUR #1 trigger: existing blog yok (`outputs/blog/{slug}/article.
html` filesystem'de bulunamıyor).

### Step 2: Decay Metric Verify (R-85 Multi-Signal Threshold)

`mcp__gsc__search_analytics` çağrı: `siteUrl={project_slug
domain}`, `dimensions=[query, page]`, page filtresi {input.url}.

GSC clicks delta hesaplama: `clicks_recent - clicks_previous`
(content_decay.clicks_delta cross-check).

R-85 multi-signal threshold:

- `clicks_delta < -20%` (significant drop)
- `delta_pct < -15%`
- `trend == "down"` (3-month rolling)

DURUR #3 trigger: multi-signal threshold satisfied değil → revize
gereksiz, master_task sync close request emit (READ-ONLY contract
— bu skill kendisi master_task'a yazmaz).

### Step 3: project-config Read (Profile-Aware Switch — Principle 2)

`projects/{slug}/project.config.json` parse → `profile` field read
(W-F1 schema 1.2 enum 5-value varsayımı). `content_settings` 14
field consume (toc_strategy, ai_training_optin, byline_policy, vs.).

Profile-aware revise switch:

- `profile == "ymyl"` → R-28 byline preserve + R-50 counter-argument
  intact.
- `profile == "e-commerce"` → conversational tone preserve.
- `profile == "local-service"` → NAP signal preserve.
- `profile == "b2b-saas"` → formal tone + diagram preserve.
- `profile == "portfolio"` → showcase entity preserve.

### Step 4: Existing Blog Parse (R-89 Canonical Preserve)

`outputs/blog/{slug}/article.html` BeautifulSoup parse:

- `<link rel="canonical">` extract → **canonical_original**.
- JSON-LD @graph Article.dateModified extract → **dateModified_pre**.
- H1/H2/H3 outline + section boundaries.
- JSON-LD @graph 5 entity (Article + Person + Organization +
  WebPage + BreadcrumbList) preserve list.
- content-version meta (R-103) extract → **version_pre**.

DURUR #6 trigger: revise içinde canonical URL change attempt → RED
(R-89 immutable; URL slug change R-91 redirect path).

### Step 5: R-87 Section-Targeted Detect

`input.scope` switch:

- `scope == "section"` (default) → section-targeted diff zorunlu,
  Step 6 devam.
- `scope == "full"` → DURUR #5 trigger (manuel approve gate; R-87
  full-rewrite yasak default).

Section identify (target_sections[] internal state):

- Outdated section (timestamp/stat reference older than 12 ay).
- Decay-correlated section (GSC query drop matched H2 keyword).
- Broken-link section (link freshness fail).

### Step 6: R-88 Freshness Theater Preempt + Revise Generate

**Pre-revise snapshot:**

- `word_count_pre` = total visible text word count.
- `claim_count_pre` = stat/quote/fact reference count.
- `structure_hash_pre` = hash(H1+H2+H3 outline tuple).

**Revise generate** (revision.template.md render, profile-aware
tone):

- `target_sections[]` içinde content delta compose.
- claim/stat/source update (Principle 1 Layer 2 fact-check enforce).
- link freshness check → broken link replace (P1 Layer 3 citation).

**Post-revise snapshot:**

- `word_count_post`, `claim_count_post`, `structure_hash_post`.

**R-88 freshness theater check (CRITICAL):**

- `word_delta = word_count_post - word_count_pre`
- `claim_delta = claim_count_post - claim_count_pre`
- `structure_changed = structure_hash_pre != structure_hash_post`

DURUR #4 trigger: `word_delta == 0 AND claim_delta == 0 AND NOT
structure_changed` → RED (sahte tarih güncelleme; dateModified bump
YOK, çıktı discard).

AMBER warning: `word_delta > 0 AND claim_delta == 0 AND NOT
structure_changed` → manuel review öner (style-only change).

### Step 7: R-103 Content Version Increment + dateModified Update

Major revise detect:

- `claim_delta > 5` OR
- `structure_changed` OR
- `profile_switch` detected (project-config profile değişmiş eski
  vs yeni snapshot).

Major revise → version increment: `v1` → `v2` (R-103 content-
version meta increment, semver minor bump on output schema).

Minor revise (`claim_delta <= 5 AND NOT structure_changed AND NOT
profile_switch`) → version unchanged.

dateModified update: UTC ISO 8601 `now()` (Article schema +
visible HTML).

`canonical` UNCHANGED (R-89 immutable enforce).

Output write: `outputs/blog/{slug}/article.html` (atomic temp+
rename).

### Step 8: change_summary.md + events.jsonl Append

**change_summary.md format:**

```markdown
# Change Summary — {url}

**Revised:** 2026-XX-XXTHH:MM:SSZ
**Scope:** section
**Sections Modified:** N
**Word Delta:** +147 (1832 → 1979)
**Claim Delta:** +2 (12 → 14)
**Structure Delta:** unchanged (R-87 section-targeted)
**Version:** v1 → v2 (major revise; claim_delta=7 > 5)
**dateModified:** 2026-XX-XXTHH:MM:SSZ
**Canonical:** UNCHANGED (https://example.com/blog/post-slug)
**Profile (P2):** ymyl

## Sections Modified
1. H2 "Subheading 1" — outdated stat replaced (2024 → 2026)
2. H2 "Subheading 3" — broken link replaced
3. H2 "Subheading 5" — counter-argument added (profile=ymyl R-50)

## R-88 Freshness Theater Check
- Pre snapshot: 1832 word, 12 claim, structure_hash=abc123
- Post snapshot: 1979 word, 14 claim, structure_hash=abc123
- Result: PASS (claim_delta=2 > 0; word_delta=+147 orantılı)

## Principle 1 Truth-Verifiable Audit
- New claims: 2
- Source verified: 2/2 (R-44)
- Citations attached: 2/2 (R-105)
```

**events.jsonl append (F-8 enum):**

- `event_type` = `content_revise`
- `event_kind` = `production`
- `schema_version` = `1.0`
- `actor` = `skill:revise-content`
- `target` = `{url}`
- `timestamp` = UTC ISO 8601
- `scope` = `{input.scope}`
- `version_increment` = `true|false`
- `word_delta`, `claim_delta`, `structure_changed` (R-88 audit
  trail)
- `canonical_preserved` = `true` (R-89 invariant)

## DURUR Conditions (7 koşul)

1. **DURUR #1 — Existing Blog Yok.** `outputs/blog/{slug}/article.
   html` filesystem'de bulunamıyor → R-89 canonical preserve enforce
   edilemez (revize için kaynak yok); kullanıcıyı new-blog skill'e
   yönlendir.
2. **DURUR #2 — Wrong Action.** `content_decay.action != "revise"`
   (prune/redirect/delete) → wrong skill; content-remediation Wave 2
   domain.
3. **DURUR #3 — Decay Threshold Satisfied Değil.** R-85 multi-signal
   threshold (clicks_delta + delta_pct + trend) tüm 3 koşul
   sağlanmıyor → revize gereksiz, master_task close suggestion.
4. **DURUR #4 — R-88 Freshness Theater Detect.** `word_delta == 0
   AND claim_delta == 0 AND NOT structure_changed` → RED, sahte
   tarih güncelleme; çıktı discard, dateModified bump YAPMA.
5. **DURUR #5 — scope=full Overhaul.** `input.scope == "full"` →
   R-87 section-targeted yasak default; manuel approve gate (skill
   tek başına full-rewrite yapamaz).
6. **DURUR #6 — R-89 Canonical Değişim.** Revise sırasında canonical
   URL değişim attempt → RED, immutable; URL slug change R-91
   redirect path domain.
7. **DURUR #7 — P1 Fact-Check Fail.** Principle 1 Layer 2 post-
   revise fact-check fail (yeni claim'lerin kaynak verify fail) →
   RED, revize iptal, çıktı discard.

## READ-ONLY Contract (F-6 Enforcement)

Bu skill master.xlsx hiçbir sheet'e YAZMAZ:

- `master.xlsx[content_decay]` allowed_writers null (F-6) → READ-
  ONLY.
- `master.xlsx[master_task]` protected_columns 7 alan (task,
  category, priority, impact, duration_est_min, assignee, note) →
  READ-ONLY consume; revize tracking için master_task row reference
  okur, yazmaz. master_task sync skill (allowed_writers içinde)
  yazma sorumluluğunu taşır.

Sadece şu artifact'lere yazılır (outputs § + produces §):

- `outputs/blog/{slug}/article.html` (updated)
- `outputs/blog/{slug}/change_summary.md` (new)
- `_state/events.jsonl` (append, F-8 enum)

## Plugin-Agnostik Disiplin

Skill content'inde proje slug hardcode YASAK. Tüm proje referansları
runtime input ({input.project_slug}, {input.url}) üzerinden
çözümlenir. URL örnekleri SKILL.md'de generic placeholder
(`https://example.com/blog/post-slug`) kullanır.

## Versioning + Status

- `version: "1.0"` (Phase 11 Wave 1 ilk shipping).
- `status: wip` (Phase 11 Wave 2 stabilizasyon sonrası `active`
  promote).
- Output schema_version: `1.0` (events.jsonl payload + change_summary
  format kontratı).
