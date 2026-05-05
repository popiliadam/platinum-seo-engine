---
name: content-remediation
description: |
  Use when: kullanıcı "content prune yap", "decay action uygula",
  "URL retire et", "301/410 patch", "robots disallow ekle" der ya da
  `/pseo-content-remediation` çağırır. master.xlsx[content_decay]
  satırından action="prune" / "redirect" / "delete" alındığında, R-85
  multi-signal threshold verify edilir, R-90 manuel approve gate
  zorunlu, R-91 301/410 decision tree branch'lenir, 3 sheet writer
  (redirect_404 + robots_txt + completed_work) atomic transaction.
  Also use when: consistency report FAIL trigger var ve content
  audit (R-44..R-54 source verification fail) sonucu URL retire
  gerekiyor; content_improve sheet'inde priority=HIGH FAIL durumlar
  legacy cleanup için; project-config[profile] enum 5-değer
  (e-commerce | ymyl | local-service | b2b-saas | portfolio) içinden
  biri sabit ve profile-aware approve gate uygulanacak (Principle 2).
  Do not use when: mevcut blog drift fix için (revise-content skill
  domain — content-remediation = RETIRE scope only); FAQ block
  re-render için (faq-optimization Wave 2 kullan); yeni blog üretimi
  için (new-blog kullan); image generation için (generate-images
  kullan); content_decay.action == "revise" (DURUR #4, wrong skill);
  R-85 multi-signal threshold satisfied değil (DURUR #1, single-
  signal remediation YASAK); R-90 manuel approve YOK (DURUR #2);
  action="redirect" + target_url=null (DURUR #3, R-91 decision tree
  reject).
version: "1.0"
status: wip
category: production
inputs:
  project_slug:
    type: string
    required: true
    description: "Workspace proje slug (resolves projects/{slug}/master.xlsx + project-config.json)."
  url:
    type: string
    required: true
    description: "master.xlsx[content_decay].url referansı (retire edilecek kanonik URL)."
  action:
    type: string
    required: true
    description: "Remediation action — R-91 decision tree branch (enum: [prune, redirect, delete]). Schema-first override: schema-frontmatter inputs[].properties whitelist 4 field [type, required, default, description] additionalProperties=false; enum description'a taşındı (W-F3 D1 paterni reuse)."
  target_url:
    type: string
    required: false
    description: "action='redirect' için 301 hedef URL (DURUR #3 — null ise reject); action='prune' organic traffic varsa topical_map'ten relevant page derive."
outputs:
  - "master.xlsx#redirect_404"
  - "master.xlsx#robots_txt"
  - "master.xlsx#completed_work"
  - "_state/events.jsonl"
consumes:
  - "init-project:projects/{slug}/master.xlsx#content_decay"
  - "init-project:projects/{slug}/master.xlsx#content_improve"
  - "init-project:projects/{slug}/master.xlsx#redirect_404"
  - "init-project:projects/{slug}/master.xlsx#robots_txt"
  - "init-project:projects/{slug}/master.xlsx#completed_work"
  - "init-project:projects/{slug}/project-config.json"
  - "rules:rules/content-quality.md"
  - "rules:rules/content-html-discipline.md"
  - "rules:rules/content-seo-discipline.md"
  - "rules:rules/content-eeat-discipline.md"
  - "rules:rules/content-llm-discipline.md"
  - "rules:rules/content-update-discipline.md"
produces:
  - "indexing-ping"
triggers:
  manual: ["/pseo-content-remediation"]
  natural_language: |
    "content prune yap ve URL retire et 301/410 patch uygula",
    "decay action uygula ve master.xlsx redirect_404 sheet güncelle",
    "URL retire et ve robots disallow ekle 410 Gone permanent",
    "301 redirect deploy et ve organic traffic preserve hedef sayfaya",
    "robots disallow ekle ve content cleanup R-91 decision tree apply"
  hooks: []
  scheduled: []
mcp_tools:
  required: []
  optional:
    - "mcp__gsc__index_inspect"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# content-remediation — production skill (Phase 11 Wave 2 W-F4)

Content RETIRE skill. master.xlsx[content_decay] satırından action=
"prune"/"redirect"/"delete" alır, R-85 multi-signal threshold verify
eder, R-90 manuel approve gate uygular, R-91 301/410 decision tree
branch'ler, 3 master.xlsx sheet'e WRITE eder (redirect_404 +
robots_txt + completed_work, transaction.update). Skill-level
enforcement: sheet schema'larında `allowed_writers: null` (governance
Phase 14+ defer); skill kendi disiplini ile WRITE kontrolü yapar.

Scope ayrımı: content-remediation = RETIRE scope only. Mevcut blog
drift fix YASAK (revise-content skill domain); R-118 humanize sadece
410 reason text + redirect target seçimi'nde uygulanır, content
revision değil.

## Foundational Principles (Üst-Prensip — Alt-Rule Override Edemez)

### Principle 1 — Truth-Verifiable Content (R-27, 3-katman defense)

Prune/delete kararının "decay reason" verifiable + uydurma yasak.
Multi-signal cross-check zorunlu (R-85), single-signal yetmez.

- **Layer 1 (pre-remediation):** skill prompt explicit "uydurma decay
  reason yasak" sentinel; remediation kararı GSC actual data ile
  bağlanır.
- **Layer 2 (multi-signal verify):** R-85 multi-signal threshold —
  clicks_delta + position_delta + impressions_delta + delta_pct +
  trend (3/5 minimum satisfied gerekli, single-signal YASAK).
- **Layer 3 (audit trail):** completed_work entry verifiable kaynak
  (GSC actual data); `note` field decay reason + signal list
  belirtir, fabricate yasak.
- **Failure mode:** P1 multi-signal verify fail → DURUR #1 RED
  (remediation iptal, manual approve gerekli).

### Principle 2 — Profile-Aware Enforcement (project-config[profile])

Skill behavior project-config.json[profile] enum'una göre değişir.
Enum 5-value: `e-commerce` | `ymyl` | `local-service` | `b2b-saas` |
`portfolio`. Remediation context'inde R-90 manual approve gate
profile'a göre sıkılaşır:

- `profile == "ymyl"` → R-90 manual approve gate **DAHA SIKI**:
  legal/medical/financial content prune ek belge gerekli; hatalı
  410 = lost authority signal (irreversible).
- `profile == "e-commerce"` → product page prune dikkat (out-of-stock
  vs permanent removal ayrımı; out-of-stock = 301 to category,
  permanent removal = 410).
- `profile == "local-service"` → location-specific care (geographic
  SEO authority, NAP consistency), location page prune redirect to
  parent service area.
- `profile == "b2b-saas"` → tolerant (feature deprecation routine);
  301 to changelog/docs.
- `profile == "portfolio"` → minimal prune (rare); showcase entity
  preserve, project removal manuel manager onay.

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Content)

R-118 humanize + R-117 uniqueness + AI signature blocklist
(tone_phrases_blocklist consume) → uygulanır 410 reason text +
redirect target page seçimi'nde (cheap content sayfaya 301 yasak).

- **R-118 humanize scope-out:** mevcut blog drift fix (revise-content
  domain) bu skill scope'una girmez. content-remediation = RETIRE
  scope only.
- **R-117 uniqueness check:** redirect target page R-117 uniqueness
  fail eden bir cheap-content değilse, redirect kabul; redirect
  hedefi de cheap-content ise → AMBER warning, manuel revize öner.
- **Failure mode:** AMBER warning (auto-correct attempt) → RED fail
  (manuel revise revise-content skill'e routing).

## Schema Authority Compliance

- **F-2:** `master.xlsx[content_decay].action` schema'da type/enum/
  description null. Bu skill action enum'unu R-86/R-87/R-90/R-91
  rules'tan **rule-derived** consume eder (string compare):
  `prune` / `redirect` / `delete` (action="revise" → DURUR #4 wrong
  skill; revise-content domain).
- **F-9:** `_state/events.jsonl` `event_kind` enum 4-value (ADR-020):
  `provenance` | `work` | `audit` | `workflow`. content-remediation
  output = production work → `event_kind=work`.
- **F-10:** `master.xlsx[redirect_404]` 5 col [url, inlinks, action,
  target_url, status]; allowed_writers null + protected_columns null
  → schema-level governance gate YOK; skill-level enforcement intact
  (transaction.update OK, governance Phase 14+ defer).
- **F-11:** `master.xlsx[robots_txt]` 5 col [id, level, issue,
  detail, resolution]; allowed_writers null → skill-level
  enforcement intact.
- **F-12:** `master.xlsx[completed_work]` 6 col [id, task_or_content,
  url, date, category, note]; allowed_writers null + protected_
  columns null → skill-level enforcement intact.
- **F-14:** events.jsonl required 5 field [schema_version, event_
  kind, event_id, timestamp, project_id]; project_id pattern
  `^[a-z][a-z0-9-]*$`; event_type 10-enum içinde:
  - action=prune veya delete → `event_type=content_remove`
  - action=redirect → `event_type=redirect_deployed`
- **F-15:** `master.xlsx[content_improve]` 8 col; allowed_writers
  null → READ-ONLY consume (consistency report FAIL trigger için
  optimization sheet read).

## Routing (8-Step Workflow)

### Step 1: master.xlsx[content_decay] Action String Read (F-2 Derive)

Row read where `url == {input.url}`. Action string compare
(schema'da enum null, R-86/R-87/R-90/R-91 rules'tan derive):

- `action == "prune"` → Step 2 trigger.
- `action == "redirect"` → Step 2 trigger.
- `action == "delete"` → Step 2 trigger.
- `action == "revise"` → DURUR #4 (revise-content skill domain,
  wrong skill).
- `action != prune/redirect/delete/revise` → DURUR #4 trigger.

Input action override: `input.action` parametresi
content_decay.action ile cross-check; mismatch durumunda RED
(input drift, content_decay authority).

### Step 2: R-85 Multi-Signal Threshold Verify (P1 Layer 2)

GSC data cross-check (`master.xlsx[content_decay]` sütunları +
`content_improve` sheet F-15 READ-ONLY):

- `clicks_delta < -20%` (significant drop)
- `delta_pct < -15%`
- `position_delta > +5` (position drop)
- `impressions_delta < -10%`
- `trend == "down"` (3-month rolling)

Multi-signal threshold: minimum 3/5 signal satisfied gerekli (single-
signal remediation YASAK — Principle 1 Layer 2).

DURUR #1 trigger: R-85 threshold satisfied değil → manual approve
gerekli (Süleyman onayı), single-signal remediation YASAK.

### Step 3: R-90 Manual Approve Gate (autonomy MEDIUM, Principle 2)

Süleyman onayı zorunlu (autonomy.confidence: MEDIUM, requires_
approval: true). project-config.json read → `profile` field
profile-aware gate sıkılaştırması:

- `profile == "ymyl"` → DAHA SIKI: legal/medical/financial content
  prune için ek belge gerekli (irreversible 410 = lost authority
  signal).
- `profile == "e-commerce"` → product page prune dikkat (out-of-stock
  vs permanent removal ayrımı; default = 301 to category).
- `profile == "local-service"` → location page redirect to parent
  service area (geographic authority preserve).
- `profile == "b2b-saas"` → tolerant (feature deprecation routine);
  301 to changelog/docs preferred.
- `profile == "portfolio"` → minimal prune (rare); manager manuel
  onay.

DURUR #2 trigger: R-90 manuel approve YOK → STOP.

### Step 4: R-91 301/410 Decision Tree (4 Senaryo)

R-91 decision tree branch:

**Senaryo 1 — action="prune" + organic traffic VAR (R-85 GSC clicks > 0):**
- 301 redirect (target_url topical_map'ten relevant page derive,
  veya input.target_url override).
- R-117 uniqueness check redirect target (cheap content değilse
  kabul).
- master.xlsx[redirect_404] write: `[url, inlinks, "301",
  target_url, "active"]`.

**Senaryo 2 — action="prune" + organic traffic YOK (R-85 GSC clicks == 0):**
- 410 Gone (permanent removal).
- R-118 humanize 410 reason text (tone_phrases_blocklist consume).
- master.xlsx[robots_txt] write: `[id, "warning", "disallow_404",
  url, "robots Disallow:"]`.
- master.xlsx[redirect_404] entry: `[url, inlinks, "410", null,
  "permanent"]`.

**Senaryo 3 — action="redirect":**
- 301 redirect (target_url INPUT override veya topical_map relevant).
- target_url validate: HEAD request 200 OK, sayfa exist; cheap
  content değil (R-117).
- master.xlsx[redirect_404] write: `[url, inlinks, "301",
  target_url, "active"]`.
- DURUR #3 trigger: target_url == null → REJECT (R-91 decision
  tree).

**Senaryo 4 — action="delete":**
- 410 Gone (permanent, irreversible).
- master.xlsx[robots_txt] write: `[id, "critical", "disallow_410",
  url, "robots Disallow: + 410"]`.
- master.xlsx[redirect_404] entry: `[url, inlinks, "410", null,
  "permanent"]`.

### Step 5: R-118 Humanize Pass (Scope-Out Check, Principle 3)

R-118 humanize skill-content ölçeği — content-remediation context'inde:

- 410 reason text humanize (tone_phrases_blocklist consume; AI
  signature avoid).
- Redirect target page seçimi'nde AI signature blocklist (cheap
  content target sayfaya 301 yasak; AMBER warning).
- **Scope-out (CRITICAL):** mevcut blog drift fix YASAK — bu skill
  RETIRE scope only. Revise-content skill domain leakage detect
  edilirse RED (file path veya skill ref kontrolü).
- **Test:** revise-content domain leakage detect (article.html
  modify yasak, change_summary.md emit yasak — bu skill çıktıları
  master.xlsx[redirect_404 + robots_txt + completed_work] +
  events.jsonl ile sınırlı).

### Step 6: master.xlsx Writer (3 Sheet, F-10/F-11 Skill-Level Enforcement)

Step 4 decision'a göre 3 sheet'e WRITE (transaction.update,
skill-level enforcement intact, schema-level allowed_writers null =
governance Phase 14+ defer):

- `master.xlsx[redirect_404]` (transaction.update F-10) — 5 col:
  url, inlinks, action ("301"|"410"), target_url, status.
- `master.xlsx[robots_txt]` (transaction.update F-11) — 5 col: id,
  level (severity), issue, detail (URL), resolution.

Atomic transaction discipline: write batch (3 sheet) tek commit
window içinde rollback-able; partial failure → tüm sheet revert.

### Step 7: master.xlsx[completed_work] Entry (F-12 Audit Trail, P1 Layer 3)

Entry append (transaction.update F-12, 6 col):

- `id`: UUID v4
- `task_or_content`: `"remediation: {action}"`
- `url`: `{input.url}`
- `date`: UTC ISO 8601 today (YYYY-MM-DD)
- `category`: action enum value (`"prune"` | `"redirect"` | `"delete"`)
- `note`: `"R-91 decision: {decision_path}; R-85 signals:
  {satisfied_signals}; profile: {profile}"`

Principle 1 Layer 3 audit trail: `note` field decay reason + signal
list verifiable (GSC actual data kaynak), fabricate yasak.

### Step 8: events.jsonl Append (F-9 + F-14)

Event entry (5 required field F-14 strict):

- `schema_version` = `"1.0"` (F-14 const).
- `event_kind` = `"work"` (F-9 ADR-020 4-enum içinden, production
  output).
- `event_id` = UUID v4.
- `timestamp` = UTC ISO 8601.
- `project_id` = `{input.project_slug}` (F-14 pattern: `^[a-z]
  [a-z0-9-]*$`).
- `event_type`:
  - `action == "prune"` veya `"delete"` → `content_remove` (F-14
    enum 10-value).
  - `action == "redirect"` → `redirect_deployed` (F-14 enum).
- `actor` = `"skill:content-remediation"`.
- `target` = `{input.url}`.
- `action` = `{input.action}`.
- `decision_path` = R-91 senaryo (1|2|3|4).
- `signals_satisfied` = list (R-85 multi-signal).

## DURUR Conditions (5 koşul)

1. **DURUR #1 — R-85 Multi-Signal Threshold Satisfied Değil.**
   `clicks_delta + delta_pct + position_delta + impressions_delta +
   trend` 3/5 minimum sağlanmıyor → single-signal remediation YASAK
   (P1 Layer 2). Manual approve gerekli (Süleyman onayı). Default
   path: STOP, master_task close suggestion.
2. **DURUR #2 — R-90 Manuel Approve YOK.** Süleyman onay gate
   geçmedi (autonomy.confidence: MEDIUM, requires_approval: true) →
   STOP. Profile-aware gate sıkılaştırma (P2): ymyl > b2b-saas
   tolerance.
3. **DURUR #3 — action="redirect" + target_url=null.** R-91 decision
   tree Senaryo 3 reject; redirect path için target_url zorunlu.
   Manager input.target_url override gerekli veya topical_map'ten
   derive.
4. **DURUR #4 — Wrong Action.** `content_decay.action != "prune" /
   "redirect" / "delete"` → wrong skill domain. action="revise" →
   revise-content skill (Wave 1 W-F2); action enum dışı değer →
   schema drift report.
5. **DURUR #5 — completed_work Skill-Level Write Governance.**
   `completed_work` sheet schema-level `allowed_writers: null` →
   schema-level gate YOK; skill-level enforcement intact (write OK,
   governance Phase 14+ defer). Bu DURUR aktif değil — informational
   gate, write proceed.

## WRITE Contract (F-10/F-11/F-12 Skill-Level Enforcement)

Bu skill 3 master.xlsx sheet'e WRITE eder (skill-level enforcement
intact, schema-level allowed_writers null = governance Phase 14+
defer):

- `master.xlsx[redirect_404]` (F-10, 5 col, transaction.update).
- `master.xlsx[robots_txt]` (F-11, 5 col, transaction.update).
- `master.xlsx[completed_work]` (F-12, 6 col, transaction.update —
  audit trail).

READ-ONLY consume (write yapılmaz):

- `master.xlsx[content_decay]` (F-2 — action read).
- `master.xlsx[content_improve]` (F-15 — consistency report read).
- `project-config.json` (P2 profile read).

Output artifacts:

- `_state/events.jsonl` (append, F-9 + F-14 enum).

## Canonical Drift Resolution (Q-W3W2Cb-002 Doc)

URL canonical mismatch detection + branch matrix paterni (cross-skill convention: revise-content + verify-indexing + content-remediation cooperative resolution, intra-wave investigation paterni Phase 14 W3-W2-C-b doğum belgesi Q-W3W2Cb-001 in-wave RESOLVED `/main-page` duplicate-canonical example).

### Detection

GSC `index_inspect` coverage state ile canonical drift surface edilir:

- `coverageState == "DUPLICATE_REDIRECT"` veya `googleCanonical != userCanonical` → drift confirmed.
- `coverageState == "MOVED_PERMANENTLY"` veya `googleCanonical points to different URL` → canonical drift implicit.
- revise-content skill Step 3 reportu URL legitimacy soru olarak surface edebilir (Q-W3W2Cb-001 paterni: Step 3 surfaced legitimacy question, Step 6 verify-indexing GSC inspect resolved).

### Resolution Branch Matrix

**(a) Duplicate via canonical** — googleCanonical başka URL'ye işaret ediyor, kaynak URL duplicate:

- `action == redirect_deployed` (R-91 Senaryo 3 paterni reuse).
- `target = googleCanonical` (GSC authoritative source).
- `event_type = redirect_deployed` (F-14 direct match), `note = "duplicate_via_canonical_GSC_inspect"`.
- Q-W3W2Cb-001 W3-W2-C-b in-wave RESOLVED paterni: `/main-page` → `/` 301 deploy.

**(b) Canonical drift** — userCanonical doğru ama site internal link/sitemap drift'i nedeniyle Google başka URL'yi tercih etmiş:

- `action == redirect_deployed` + `target = primary_url` (R-91 Senaryo 1 + Senaryo 3 birleşim).
- Internal link audit + sitemap regenerate (cross-skill: tech-audit + on-page-audit refer).
- `event_type = redirect_deployed`, `note = "canonical_drift_primary_url_restored"`.

**(c) Manual review** — drift surface ama düz redirect yetersiz (örn. content materially differs, cluster-level rerouting gerekli):

- `action == manual_review` (skill spec event_type=manual + note explanation).
- improve_routing event_type=manual + `note = "[skill=content-remediation event_type_intent=canonical_review explanation=...]"` (worker schema-first override paterni reuse, rules/events-writer.md Section 4 cross-ref).
- Manager scope: revise-content tetikle veya cluster-map yeniden değerlendir.

### Cross-Skill Convention

İntra-wave cooperative resolution paterni:

- **revise-content** (Step 3) drift soru olarak surface edebilir (URL legitimacy challenge).
- **verify-indexing** (Step 6) GSC `index_inspect` ile drift confirm/refute (authoritative source).
- **content-remediation** (Step 4 R-91) branch matrix uygula + redirect_404 sheet write.
- 3 skill cooperative aynı wave içinde (Phase 14 W3-W2-C-b kanıt: Q-W3W2Cb-001 same-wave self-resolve positive drift).

## Plugin-Agnostik Disiplin

Skill content'inde proje slug hardcode YASAK. Tüm proje referansları
runtime input ({input.project_slug}, {input.url}, {input.target_url})
üzerinden çözümlenir. URL örnekleri SKILL.md'de generic placeholder
(`https://example.com/blog/post-slug`) kullanır.

## Versioning + Status

- `version: "1.0"` (Phase 11 Wave 2 ilk shipping).
- `status: wip` (Phase 12 stabilizasyon sonrası `active` promote).
- Output schema_version: `1.0` (events.jsonl payload + master.xlsx
  3-sheet write contract kontratı).
- `autonomy.confidence: MEDIUM` (R-90 manual approve gate enforced;
  HIGH promotion 3 başarılı remediation cycle sonrası, profile-aware
  ymyl gate intact).
