---
name: verify-indexing
description: |
  Use when: kullanıcı "indeksleme doğrula", "coverage check", "url
  inspection", "indexing verify", "submit sonrası kontrol", "kanonik
  doğrula" der ya da /pseo-verify-indexing çağırır; W-G1 indexing-ping
  submit sonrası 24-72 saat GSC index_inspect ile actual vs expected
  status mismatch raporu üretilecek; outputs/indexing/{date}-coverage-
  report.json + _state/events.jsonl audit append.
  Also use when: completed_work sheet'inde recent indexing submission
  varsa otomatik olarak aynı URL listesi target alınır; expected_status
  enum (indexed / not_indexed / crawled_not_indexed) verilmişse status
  compare yapılır; coverage audit Foundational Principle 1 truth-
  verifiable enforcement zorunluluğunda.
  Do not use when: ilk submit (W-G1 indexing-ping kullan); GSC API
  credential yok / 401 (DURUR #1 ABORT); target_urls boş (DURUR #2
  SKIP); GSC quota tükenmiş gün (DURUR #4 AMBER kısmi sonuç);
  manuel WordPress upload doğrulama (skill scope dışı, manuel
  inceleme).
version: "1.0"
status: wip
category: publishing
inputs:
  target_urls:
    type: array
    required: true
    description: "Doğrulanacak URL listesi (string array, fully-qualified absolute URL'ler). Boş array DURUR #2 SKIP. completed_work sheet'inde W-G1 submission paterni varsa otomatik populate edilir."
  expected_status:
    type: string
    required: true
    description: "Beklenen indeks durumu. Enum (description-only, schema-first override per W-G1 paterni: enum YASAK frontmatter inputs[*] schema'da, description'a taşı): indexed | not_indexed | crawled_not_indexed. Invalid değer Step 3 reject + audit. DURUR #2 target_urls empty SKIP."
outputs:
  - "_state/events.jsonl"
  - "outputs/indexing/{date}-coverage-report.json"
consumes:
  - "init-project:master.xlsx[completed_work]"
  - "indexing-ping:_state/events.jsonl"
produces: []
triggers:
  manual: ["/pseo-verify-indexing"]
  natural_language: |
    "indeksleme doğrula", "coverage check", "url inspection",
    "indexing verify", "submit sonrası kontrol", "kanonik doğrula",
    "url status check", "indeks raporu", "coverage report üret"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__gsc__index_inspect"
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: false
  safe_auto_execute: true
---

# verify-indexing — publishing skill (Phase 12 Wave 2, W-G4)

URL coverage verification pipeline. Reads a `target_urls` array (or
auto-populates from `master.xlsx[completed_work]` recent submissions),
queries `mcp__gsc__index_inspect` per URL, compares actual vs expected
status, and writes a coverage mismatch report. **Sequential dependency
on W-G1**: this skill verifies what `indexing-ping` (Wave 1, W-G1) has
submitted 24-72 hours earlier — it is the truth-verifiable closing leg
of the submit/verify pair.

The skill is **READ-ONLY** with respect to `master.xlsx`. F-1 schema
authority: `completed_work` sheet allowed_writers=null (effectively;
schema declares no writer for it) for this skill (verified pre-flight;
W-G4 grep sentinel asserts the worker never invokes
`transaction.append`, `transaction.update`, or `transaction.delete`).
The only state mutation is the audit append to `_state/events.jsonl`
and the per-run JSON report under `outputs/indexing/{date}-coverage-
report.json`.

## Sequential Dependency on W-G1

W-G4 (`verify-indexing`) is the verification counterpart of W-G1
(`indexing-ping`). The Indexing API submit/verify protocol per
docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md §24
(Autonomous System Considerations; §24.5 Outcome Verification Loop)
expects the verify call **24-72 hours after submit**: GSC needs that
window to crawl/process the URL, and shorter windows produce false
`not_indexed` readings.

**Order discipline (Wave 2 dispatch):**
1. W-G1 `indexing-ping` runs first; emits work events with
   `indexing_ping={attempted, call_type=URL_UPDATED, response_code,
   called_at}` sub-object.
2. ≥24h later, W-G4 `verify-indexing` reads those events
   (`consumes: indexing-ping:_state/events.jsonl`), pulls the URL set
   plus the `called_at` timestamp, queries `mcp__gsc__index_inspect`,
   and emits **AUDIT** events recording the verification result.
3. Coverage report JSON is the human-readable counterpart per Phase 11
   lesson 29 self-extending positive drift.

If W-G1 events are absent and `target_urls` is also empty, DURUR #2
SKIP fires (no work to do). If W-G1 events exist but `called_at` is
< 24h old, the skill emits an INFO audit event with `audit_action=
accessed` + a `note`-equivalent field stating "verify window not yet
elapsed; rerun ≥24h after called_at".

## Inputs (frontmatter contract)

| Name              | Type   | Default | Notes                                                                                                  |
|-------------------|--------|---------|--------------------------------------------------------------------------------------------------------|
| `target_urls`     | array  | —       | Required. Empty array → DURUR #2 SKIP. Auto-populate from `completed_work` if W-G1 submission present. |
| `expected_status` | string | —       | Required. Enum (description-only, schema-first override): `indexed` / `not_indexed` / `crawled_not_indexed`. |

## Outputs (artifacts produced)

- `_state/events.jsonl` — audit append. **Schema-first override**
  (lesson 7+23+31 worker authority, 4th convergent application after
  Wave 1 W-G1/W-G2/W-G3): the brief sketched
  `event_type=indexing_verified` but `events.schema.json` declares
  `event_type` as a closed 12-value WORK-only enum (10 legacy:
  `content_new, content_revise, content_remove, tech_fix,
  quickwin_applied, pillar_launch, schema_fix, redirect_deployed,
  backlink_outreach, manual` + 2 skill_<name>:
  `skill_content_remediation, skill_whats_next`). `indexing_verified`
  is NOT in the enum — it is also
  irrelevant here because **`event_type` is WORK-only** and this skill
  emits `event_kind=audit`. The schema's allOf rule for `audit` kind
  requires `audit_action`, `audit_target`, `actor` (no `event_type` or
  `task_id` mandatory). The skill therefore writes:
  - `event_kind=audit` (events.schema enum, ADR-020)
  - `audit_action=accessed` (audit-action enum: created / modified /
    deleted / **accessed** / permission_changed / config_changed —
    `accessed` is the semantically correct match for a READ-only
    coverage check that does not mutate the audited resource)
  - `audit_target=gsc:index_inspect:{url_normalized}` (resource-path
    convention, mirrors AUDIT field documentation)
  - `actor=skill:verify-indexing` (system process identity)
  - `event_id=verify_indexing_{url_hash8}_{timestamp_compact}`
  - `indexing_ping` sub-object reused as informational payload: the
    schema's `verified_at` + `verified_coverage` fields are precisely
    designed for this verification leg (events.schema.json
    `properties.indexing_ping.verified_at` documents it as "GSC
    urlInspection result timestamp (§24.4, 24h later)"). Although
    `indexing_ping` is annotated WORK-only, an
    `additionalProperties=false` violation would only fire on
    out-of-schema keys; reusing this sub-object on an audit event
    requires confirmation. **Defensive choice**: this skill carries
    the verification fields **inside `audit_target` URN** (e.g.
    `gsc:index_inspect:{url_normalized}#verified_coverage=indexed`)
    so no schema bump is needed and Phase 12 hedef 0 schema bump
    holds. `note` is NOT required on audit events (it is WORK-only),
    so coverage detail goes into the JSON report (next bullet) not
    the events.jsonl row body.
- `outputs/indexing/{date}-coverage-report.json` — human-readable
  per-run report with `target_urls[]`, `coverage[]
  ({url, actual_status, expected_status, mismatch_bool, gsc_response_raw})`,
  `mismatch_count`, `match_count`, `quota_partial_flag`, `durations_ms`.

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-
principles`) gate this skill end-to-end. No alt-rule (R-01..R-122)
overrides them. Audit event_kind already ENFORCES Principle 1
provenance because every recorded line has actor + audit_target +
audit_action triple — schema-level proof that the verification
happened, performed by which actor, against which resource.

### Principle 1 — Truth-Verifiable Coverage (Audit Provenance)

**Statement.** Coverage report'taki her satır kanıtlanabilir
kaynaklı: `mcp__gsc__index_inspect` raw response → events.jsonl audit
satırı → coverage-report.json paralel kayıt. Hayali coverage status
fabrikasyonu YASAK; AI suistimal kapısı: GSC API çağrısı yapılmadan
satır üretilemez. AI suistimal preempt: model "muhtemelen indexed"
gibi tahmin üretemez, sadece GSC API output yansıtılır.

**3-katman defense:**
- Layer 1: input validation — `target_urls` her elemanı RFC 3986
  absolute URL (https:// prefix zorunlu) + `urlparse` host eşleşmesi
  `project-config[domain]` ile match olmalı; mismatch reject + audit.
- Layer 2: GSC raw response capture — her URL için `index_inspect`
  raw JSON response coverage-report.json'a yazılır (`gsc_response_raw`
  field), audit_target URN'ine de coverage özeti embed edilir.
- Layer 3: events.jsonl audit append — her doğrulama ayrı satır,
  sonradan manuel doğrulanabilir audit trail. `audit_action=accessed`
  (READ-only, mutation yok) Foundational Principle 1 truth-verifiable
  zorunluluğunu schema-level garantiler.

**Failure mode:** RED — verification abort, çıktı discard. Layer 1/2/3
herhangi biri fail → DURUR #1 (auth) ya da Step 3 reject.

### Principle 2 — Profile-Aware Behaviour (Documented Pattern)

**Statement.** `verify-indexing` skill'i `project-config[profile]`
enum'una karşı **profile-conscious** davranır: ymyl ve e-commerce
profiler için coverage mismatch ciddiyeti farklıdır ve raporda
açıklanır (skill mantığı aynı kalır, dökümantasyon ayrışır).

**Enum 5-value documented:** `e-commerce` / `ymyl` / `local-service` /
`b2b-saas` / `portfolio`. Davranış ayrışmaları:

- **ymyl** (sağlık, finans, hukuk): `not_indexed` mismatch riski
  delisting'e işaret edebilir; coverage-report'a `ymyl_critical_flag`
  ekleyebilir gelecek release. Şu an profile_resolved audit
  metadata'sına eklenir, raporda görünür.
- **e-commerce**: SKU page disappear riski stok-tükenmesi false
  positive olabilir; raporda `commerce_sku_check_recommended` notu.
- **local-service / b2b-saas / portfolio**: standart davranış,
  raporda profile_resolved metadata olarak görünür.

Skill bu profillerin mantığını bu sürümde **documented placeholder**
olarak tutar; Phase 13+ release'lerde profile-conditional severity
genişlemesi yapılabilir. profile_resolved değeri events.jsonl audit
metadata'sına ve coverage-report.json'a eklenir.

### Principle 3 — AI Suistimal Önlemi (Anti-Hallucinated-Coverage Gate)

**Statement.** AI'ın "coverage status hayali fabrikasyonu" suistimali
preempt edilir: coverage status sadece `mcp__gsc__index_inspect` raw
response'tan üretilir. Hayali / pattern-matched / heuristic status
YASAK.

**Gate kuralları:**
- target_urls dedup (canonical normalize: trailing slash, protocol,
  case-fold host) — aynı URL'i iki kez sorgulayıp credit harcamamak.
- Per-run cap: max 200 URL (GSC URL Inspection 200/day default
  quota). Cap aşımı AMBER warning + truncate, audit'a yazılır
  (DURUR #4 partial result paterni).
- Wildcard pattern (`*`, `?`) input olarak REJECT.
- GSC raw response yoksa coverage row üretilmez — empty rather than
  hallucinated; bu kural "AI hayali coverage YASAK" garantisidir.

**Failure mode:** AMBER warning + auto-correct attempt; 2x AMBER aynı
pass → RED upgrade.

## Routing — 6-Step Workflow

> Step names are stable identifiers used as
> `steps[*].name` when the skill calls `workflow_runner.create_run`.

### Step 1 — `read_project_config`

`projects/{slug}/project.config.json` parse. `domain` + `profile`
field oku; `profile` Principle 2 documented pattern gereği audit
metadata'sına ve coverage-report'a eklenir. GSC credential check
(`.env` ve project.config.gsc_property_id) — yoksa DURUR #1 ABORT.

### Step 2 — `read_master_xlsx_completed_work`

`master.xlsx[completed_work]` sheet READ.
`openpyxl.load_workbook(read_only=True)`. Schema authority:
`completed_work` 6 columns (`id, task_or_content, url, date, category,
note`). F-1 allowed_writers null discipline: skill MUST NOT call
`transaction.append`, `transaction.update`, or `transaction.delete`.

W-G1 indexing-ping submission paterni recent satırlarda
`category=indexing_submitted` ya da `note=indexing_ping_submitted`
gibi marker barındırır (W-G1 indexing_ping sub-object'leri events.jsonl
içinde, completed_work sheet'inde category sinyali). target_urls
input boş ise bu sheet'ten son 7 gün içinde submit edilen URL'ler
auto-populate edilir.

**DURUR #5 trigger.** master.xlsx eksik → init-project skill önce
çalışmalı (Phase 5 W-Q paterni; bu skill için DURUR #5 değil sentinel
abort, manager ya da kullanıcı init-project'e yönlendirir).

### Step 3 — `validate_target_urls`

`target_urls` her eleman:
- RFC 3986 absolute URL (https:// zorunlu) + `urlparse` host =
  project-config[domain] match.
- Wildcard pattern (`*`, `?`) → REJECT (Principle 3 anti-cheap-content).
- expected_status enum match: indexed / not_indexed /
  crawled_not_indexed; mismatch reject + audit (drift 4. değere
  schema-first override engellemiştir).

Rejected URL'ler `rejected_urls[]` listesinde event'e eklenir.

### Step 4 — `inspect_gsc_per_url`

`mcp__gsc__index_inspect` per URL. Raw response capture (per Google
Search Console URL Inspection API docs):

```python
# Pseudocode — actual impl uses mcp__gsc__index_inspect tool call
for url in validated_urls:
    raw = mcp_gsc_index_inspect(url=url, site_url=domain_property_url)
    actual_status = raw.get("inspectionResult", {}) \
                       .get("indexStatusResult", {}) \
                       .get("coverageState", "unknown")
    coverage.append({
        "url": url,
        "actual_status": actual_status,
        "expected_status": expected_status,
        "mismatch_bool": (actual_status != expected_status),
        "gsc_response_raw": raw,
    })
```

Expected response: 200 success per URL. 429 quota → DURUR #4 AMBER
partial result; remaining URLs skipped, partial flag in event.
401 / auth fail → DURUR #1 ABORT.

**DURUR #4 trigger.** GSC quota exceeded mid-run → AMBER + partial
result + event payload `quota_partial_flag=true`.

### Step 5 — `aggregate_results`

Per-URL coverage list build:
- `match_count` — `actual_status == expected_status`.
- `mismatch_count` — diff.
- `unknown_count` — actual_status="unknown" (GSC raw response missing
  coverageState — counts as mismatch, separate flag).
- `rejected_urls[]` — Step 3 reject.
- `quota_partial_flag` — true if DURUR #4 fired mid-run.
- `durations_ms` — per-step elapsed time.

**DURUR #3 trigger.** All URLs `not_indexed` while expected_status =
`indexed` (i.e. all mismatch, fan-out failure) → AMBER + escalate
flag (raporda `escalation_recommended=true`, manuel ineceleme önerisi).

### Step 6 — `emit_audit_events`

`_state/events.jsonl` append. **Schema-first override** rationale (see
Outputs section above): event_kind=audit, audit_action=accessed,
audit_target encodes verification result via URN fragment, no
event_type / task_id required by audit allOf rule.

| Field            | Value                                                          |
|------------------|----------------------------------------------------------------|
| `schema_version` | `1.0`                                                          |
| `event_kind`     | `audit` (events.schema enum, ADR-020)                          |
| `event_id`       | `verify_indexing_{url_hash8}_{timestamp_compact}`              |
| `timestamp`      | UTC ISO 8601                                                   |
| `project_id`     | `project-config[project_id]`                                   |
| `audit_action`   | `accessed` (audit-action enum 6-value)                         |
| `audit_target`   | `gsc:index_inspect:{url_normalized}#actual={status}&expected={s}&mismatch={bool}` |
| `actor`          | `skill:verify-indexing`                                        |
| `primary_source` | (omitted; primary_source is WORK-only)                         |

Per-URL detail goes into the companion JSON report (Step 5
`coverage[]`); events.jsonl audit lines stay under the events.schema
audit allOf rule contract.

### Step 7 — `write_report_artifact`

`outputs/indexing/{date}-coverage-report.json` write:

```json
{
  "schema_version": "1.0",
  "run_at_utc": "2026-05-04T10:30:00Z",
  "host": "example.com",
  "expected_status": "indexed",
  "match_count": 5,
  "mismatch_count": 2,
  "unknown_count": 0,
  "rejected_urls": [],
  "quota_partial_flag": false,
  "escalation_recommended": false,
  "profile_resolved": "ymyl",
  "coverage": [
    {
      "url": "https://example.com/blog/foo",
      "actual_status": "indexed",
      "expected_status": "indexed",
      "mismatch_bool": false,
      "gsc_response_raw": {"...": "..."}
    }
  ],
  "durations_ms": {"step2": 18, "step4": 940, "step6": 4}
}
```

Artefact is the truth-verifiable audit complement (Principle 1 Layer 3
+ Principle 3 anti-hallucination). Self-extending positive drift per
Phase 11 lesson 29: report shape locked here so downstream consumers
(monthly-report, governance audits) have a stable contract.

## DURUR Conditions (4 minimum, lesson 32 self-extending teşvik)

| #  | Trigger                                                       | Resolution                                                                                                                  |
|----|---------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| 1  | GSC API auth fail (.env credentials missing veya 401)         | ABORT — RED, çıktı yok, audit-only event with audit_action=accessed + audit_target=gsc:index_inspect:auth_failure.          |
| 2  | target_urls boş + completed_work auto-populate de boş         | SKIP — info severity, audit append, output report yine yazılır (empty coverage[], match_count=0, mismatch_count=0).         |
| 3  | All URLs not_indexed (expected indexed → all mismatch)        | AMBER + escalate (`escalation_recommended=true` raporda, manuel inceleme).                                                  |
| 4  | GSC URL Inspection quota exceeded (200/day default) mid-run   | AMBER + partial result; kalan URL'ler skipped; event payload `quota_partial_flag=true`.                                     |

## master.xlsx WRITE YASAK (F-1 + W-G1 paterni reuse)

W-G4 sadece `completed_work` sheet'ini READ eder. WRITE YOK. F-1
schema authority (master-excel.schema.json):

- `completed_work.allowed_writers` = null (effectively; schema declares
  no writer field — read-only consume contract).

Test sentinel: monkey-patch `openpyxl.Workbook.save` → çağrılırsa fail
fast (W-G4 hiçbir koşulda workbook save çağırmaz). Aynı paterni W-G1
indexing-ping uyguladı — Wave 2 worker re-uses Wave 1 sentinel.

## Plugin-Agnostic Discipline

- No project slug hardcoded inside this skill (`dentnotion`, `vento`,
  `eykom`, `bigcattr`, `calitte`, `lastiksa`, `noraninsaat`, `adstark`
  are FORBIDDEN tokens — pytest grep verifies).
- Domain comes from `project-config[domain]` at runtime.
- `.mcp.json` is **NEVER** modified by this skill (F-16 invariant).
  Test sentinel: pre/post byte-hash diff on `.mcp.json` must be
  identical. Wave 1 W-G1 set this paterni; W-G4 inherits unchanged.
- Per-call / per-url credit shape names (Phase 7 lesson, ADR-028 anti-
  pattern) MUST NOT appear in this skill — `budget.estimated_credits`
  (number, here 0) is the only allowed shape per skill-frontmatter
  schema. Phase 7 reject paterni `metric_*name` ve credit `*_per_call`
  / `*_per_url` shape isimlerinin hiçbiri bu skill body'sinde yer almaz
  (test sentinel grep kanıtlar).

## Error Handling

| Failure                              | Mode  | Action                                                                          |
|--------------------------------------|-------|---------------------------------------------------------------------------------|
| GSC credential missing / 401         | RED   | DURUR #1 ABORT, audit-only event                                                |
| target_urls empty + auto-populate empty | INFO | DURUR #2 SKIP, audit append, empty coverage report                            |
| All URLs not_indexed (fan-out fail)  | AMBER | DURUR #3 AMBER + escalate flag in report                                        |
| GSC quota exceeded mid-run           | AMBER | DURUR #4 partial result; kalan URL'ler skipped; quota_partial_flag=true         |
| host mismatch (URL ≠ domain)         | RED   | Principle 1 Layer 1 reject + audit                                              |
| wildcard pattern in target_urls      | RED   | Principle 3 reject + audit                                                      |
| expected_status enum invalid         | RED   | Step 3 reject + audit                                                           |
| master.xlsx save attempt             | RED   | F-1 violation — fail-fast (test sentinel)                                       |
| .mcp.json byte hash drift            | RED   | F-16 violation — fail-fast (test sentinel)                                      |

## Schema-First Override Decisions Made (Lesson 7+23+31, 4th Convergent Application)

The brief sketched `event_type=indexing_verified` for the audit
event_kind. Worker authority applied — this is the 4th convergent
schema-first override after Wave 1 W-G1 / W-G2 / W-G3 (lesson 31):

1. **Override 1 — `event_type` is WORK-only.** events.schema.json
   declares `event_type` as a closed 12-value enum that applies only
   to `event_kind=work`. The audit allOf rule (events.schema.json
   allOf[2]) requires `audit_action`, `audit_target`, `actor` and does
   NOT require `event_type`. Skill therefore omits `event_type`
   entirely on audit lines and uses `audit_action=accessed` to encode
   "what was done" — this is the schema-correct way to record a
   READ-only verification. Compliance restored without schema bump
   (Phase 12 hedef 0 schema bump).

2. **Override 2 — Coverage detail goes into JSON report, not events
   row body.** The brief listed coverage status fields directly in
   the events.jsonl payload. `note` is WORK-only (events.schema
   description: "Free text; required on event_type=manual and
   event_type=content_remove"). On audit events `note` is not
   required and not the natural carrier. Skill encodes minimal
   coverage summary in `audit_target` URN (e.g.
   `gsc:index_inspect:{url_normalized}#actual={status}&expected={s}&mismatch={bool}`)
   and writes the full per-URL coverage list to
   `outputs/indexing/{date}-coverage-report.json`.

3. **Override 3 — Avoid `indexing_ping` sub-object reuse on audit.**
   The schema's `indexing_ping` sub-object is annotated WORK-only
   (events.schema L188 description: "WORK-only. Optional ..."). While
   `additionalProperties=false` would only fire on out-of-schema keys,
   leaning on a WORK-only sub-object inside an audit event creates
   ambiguity. Defensive choice: encode verification fields inside
   `audit_target` URN, leaving `indexing_ping` for genuine W-G1
   submission events. Phase 12 hedef 0 schema bump preserved.

4. **Override 4 — Frontmatter `outputs[]` is artifact refs, not event
   payload fields.** Same paterni as W-G1: outputs[] lists artifact
   path strings only (`_state/events.jsonl`,
   `outputs/indexing/{date}-coverage-report.json`); payload fields
   (`event_kind`, `audit_action`, `audit_target`, `actor`) live under
   "Step 6 — emit_audit_events" prose, not in frontmatter.

Manager spot-check expected to confirm these are valid schema-first
overrides (no manager mop-up needed for ≤10-line atomic per-property
fixes per Phase 11 lesson 28 matrix). Convergent 4th worker
application strengthens lesson 31 paterni production-ready signal.

## References

- `rules/content-quality.md` (Foundational Principles, R-01..R-122).
- `schemas/skill-frontmatter.schema.json` (8 required fields, category
  enum 8 values, status enum 3 values).
- `schemas/events.schema.json` (event_kind enum 4 values, audit
  required fields `audit_action / audit_target / actor`, audit_action
  enum 6 values, indexing_ping sub-object `properties.indexing_ping`
  WORK-only, ADR-020 workflow kind).
- `schemas/master-excel.schema.json` (18 sheets — `completed_work` 6
  columns; F-1 allowed_writers null discipline).
- `schemas/project-config.schema.json` v1.5 (singular profile field,
  Phase 11 W-F1 cascade fix; 5-value enum).
- ADR-020 (event_kind=workflow vs work routing, audit semantic).
- ADR-028 (Phase 7 lesson — generic shape-name anti-pattern; ADR text
  carries the specific token forms, intentionally omitted here so this
  skill body stays grep-clean).
- W-G1 `skills/publishing/indexing-ping/SKILL.md` (Wave 1 schema-first
  override paterni, sequential dependency upstream skill).

## Wave-Out Note

This skill is `status: wip` until Phase 12 Wave 2 acceptance gate;
`active` bump deferred to the post-Wave 2 closeout. Manager owns the
status flip + governance audit.
