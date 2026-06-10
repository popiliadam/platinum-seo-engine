---
name: indexing-ping
description: |
  Use when: kullanıcı "ping et", "indeksle", "indexnow gönder", "google
  submit", "url submit", "kanonik bildir" der ya da /pseo-indexing-ping
  çağırır; yeni yayınlanan/güncellenen URL listesi için IndexNow + Google
  Indexing API submit yapılacak; R-58 lifecycle robots map (READ-ONLY)
  consume + R-91 redirect/410 cascade enforce edilecek.
  Also use when: new-blog skill cascade producer'ı olarak tetiklenir
  (yeni içerik publish sonrası); content-remediation skill 301/410 redirect
  deploy sonrası kanonikleri yenilemek istediğinde; manuel toplu URL
  submit listesi verildiğinde (CSV/JSON liste yerine inline array
  parametre).
  Do not use when: master.xlsx eksikse (init-project önce çalışmalı,
  DURUR #5 cascade); URL listesi boşsa (DURUR #1 SKIP); submission_type
  enum dışı bir değer (DURUR #2 ABORT); IndexNow API key yok ve
  google_indexing_api da kapalı (DURUR #3 hibrit branch); GSC API 5xx +
  retry once fail ise AMBER report (DURUR #4); R-91 cascade reddi
  yapılacak target URL'ler ile birlikte (DURUR #5 REJECT, redirect_404
  sheet'te action=410 satırları skip).
version: "1.0"
status: wip
category: publishing
inputs:
  target_urls:
    type: array
    required: true
    description: "Submit edilecek URL listesi (string array, fully-qualified absolute URL'ler). Boş array DURUR #1 SKIP. R-91 cascade kontrolü: master.xlsx[redirect_404] sheet'te action=410 olan URL'ler REJECT, action=301 olanlar target_url'e rewrite."
  submission_type:
    type: string
    required: true
    description: "Enum: indexnow, google_indexing_api, both. Invalid değer DURUR #2 ABORT. 'indexnow' sadece IndexNow REST POST; 'google_indexing_api' şu an sitemap-submit path (mcp__gsc__submit_sitemap = sitemap.xml submit, per-URL DEĞİL); per-URL Google Indexing API URL_UPDATED GENEL bir kanal DEĞİL — yalnızca JobPosting/BroadcastEvent sayfaları için uygundur (eligibility hard-gate + consent gate, Wave 2 sonrası wire); 'both' iki path paralel çalışır."
outputs:
  - "_state/events.jsonl"
  - "outputs/indexing/{date}-submission-report.json"
consumes:
  - "init-project:master.xlsx[redirect_404]"
  - "init-project:master.xlsx[robots_txt]"
  - "init-project:project-config[domain]"
  - ".env:INDEXNOW_KEY"
produces: []
triggers:
  manual: ["/pseo-indexing-ping"]
  natural_language: |
    "url ping et", "url indeksle", "indexnow gönder",
    "google submit", "url submit et", "kanonik bildir",
    "indexnow ping", "indexing api submit", "url tara dizine ekle"
  hooks: []
  scheduled: []
mcp_tools:
  required:
    - "mcp__gsc__submit_sitemap"
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: true
  safe_auto_execute: false
---

# indexing-ping — publishing skill (Phase 12 Wave 1, W-G1)

URL submit pipeline. Reads a `target_urls` array, applies R-91 redirect/
410 cascade against `master.xlsx[redirect_404]`, then submits the
surviving URL set via two parallel paths:

1. **IndexNow REST** — `POST https://api.indexnow.org/IndexNow` with
   stdlib `urllib.request` (no MCP, no third-party HTTP lib). JSON body:
   `{ "host": "<domain>", "key": "<INDEXNOW_KEY>",
       "keyLocation": "https://<domain>/<key>.txt",
       "urlList": [...] }`. Reads `INDEXNOW_KEY` from `.env`; absent →
   AMBER skip indexnow path (DURUR #3).
2. **Sitemap submission (current Google-side path, GENERIC channel)** —
   `mcp__gsc__submit_sitemap` submits the project `sitemap.xml` document
   (NOT per-URL); Google then crawls the URLs it lists. This is the only
   Google-side path wired in Wave 1. Together with IndexNow it is one of the
   two **generic** indexing channels (works for any valid URL on the domain).

   The **per-URL Google Indexing API** (`indexing.googleapis.com/v3/
   urlNotifications:publish`, notification types `URL_UPDATED` /
   `URL_DELETED`) is **NOT a generic channel**: per Google's documented
   restriction it is eligible ONLY for **JobPosting** or **BroadcastEvent**
   pages — submitting any other page type violates Google's spam policies.
   It is **not yet wired** (reserved for post-Wave-2) and, when wired, is
   governed by the two-gate contract in Step 5 (an eligibility hard-gate AND
   the operator-consent gate). **Never autonomous** — autonomous submission
   is forbidden (`requires_approval: true`, `safe_auto_execute: false`).

The skill is **READ-ONLY** with respect to `master.xlsx`. F-1 schema
authority: `redirect_404` and `robots_txt` sheets allowed_writers=null
for this skill (verified pre-flight; W-G1 grep sentinel asserts the
worker never invokes `transaction.append`, `transaction.update`, or
`transaction.delete`). The only state mutation is the audit append to
`_state/events.jsonl` and the per-run JSON report under
`outputs/indexing/{date}-submission-report.json`.

## Inputs (frontmatter contract)

| Name              | Type   | Default | Notes                                                                       |
|-------------------|--------|---------|-----------------------------------------------------------------------------|
| `target_urls`     | array  | —       | Required. Empty array → DURUR #1 SKIP.                                      |
| `submission_type` | string | —       | Required. Enum: `indexnow` / `google_indexing_api` / `both`. Else DURUR #2. |

## Outputs (artifacts produced)

- `_state/events.jsonl` — audit append. **Schema-first override** (lesson
  7+23 worker authority): the brief sketched `event_type=indexing_submitted`
  but `events.schema.json` declares `event_type` as a **closed 12-value
  enum** (10 legacy: `content_new, content_revise, content_remove,
  tech_fix, quickwin_applied, pillar_launch, schema_fix,
  redirect_deployed, backlink_outreach, manual` + 2 skill_<name>:
  `skill_content_remediation, skill_whats_next`). `indexing_submitted`
  is NOT in the enum;
  emitting it would fail `Draft7Validator` and break the events.schema
  event_type enum.
  The skill therefore writes `event_kind=work` + `event_type=manual`
  (free-form work record, `note` required and populated with the
  `host + url_count + submitted_count + failed_count` summary), and
  populates the schema's purpose-built `indexing_ping` sub-object
  (events.schema.json `properties.indexing_ping`: `attempted, call_type,
  response_code, called_at, verified_at, verified_coverage`). `task_id`
  is required on
  work events; the skill mints `T-NNNN` from a per-run counter.
- `outputs/indexing/{date}-submission-report.json` — human-readable
  per-run report with `submitted_count, failed_urls[], rejected_urls[]
  (R-91 cascade), durations, indexnow_response_code, gsc_response_codes`.

## Foundational Principles Enforcement (3-Layer)

The 3 üst-prensip (Phase 10 `rules/content-quality.md#foundational-
principles`) gate this skill end-to-end. No alt-rule (R-01..R-148)
overrides them.

### Principle 1 — Truth-Verifiable URL Submission (R-58, R-91)

**Statement.** Submit edilen her URL kanıtlanabilir kaynaklı: ya
`master.xlsx[redirect_404]` cascade survivor ya da çağıran skill'in
`outputs/blog/{slug}/article.html` artefact'ı (new-blog producer).
Hayali URL submit YASAK; AI suistimal kapısı: `target_urls` parametre
manifesti dışında URL üretilemez.

**3-katman defense:**
- Layer 1: input validation — `target_urls` her elemanı RFC 3986
  absolute URL (https:// prefix zorunlu) + `urlparse` host eşleşmesi
  `project-config[domain]` ile match olmalı; mismatch DURUR #5 REJECT.
- Layer 2: R-91 cascade — `redirect_404` sheet lookup; `action=410` ise
  REJECT (kalıcı kaldırılmış URL submit edilmez); `action=301` ise
  `target_url` kolonu ile rewrite (chain max 1 hop, döngü guard).
- Layer 3: events.jsonl append — her submitted_url ayrı satır olarak
  yazılır (`note` field'da host + url_count summary), sonradan manuel
  doğrulanabilir audit trail.

**Failure mode:** RED — submission abort, çıktı discard. Layer 1/2/3
herhangi biri fail → DURUR #5 trigger.

### Principle 2 — Profile-Aware Behaviour (Placeholder Pattern)

**Statement.** `indexing-ping` skill'i `project-config[profile]` enum'una
karşı **profile-agnostic** davranır: ymyl/e-commerce/local-service/b2b-
saas/portfolio profillerinin hepsi aynı submit yolunu kullanır (IndexNow
+ Google Indexing API REST kontratlarında profile-conditional davranış
yoktur). Ancak placeholder pattern kayıt edilir, böylece Phase 13+ skill
genişlemesinde profile-aware switch eklenebilir (örn ymyl YMYL profil
ek manuel review gate).

**Enum 5-value placeholder:** `e-commerce` / `ymyl` / `local-service` /
`b2b-saas` / `portfolio`. Skill bu profillerin hiçbirinde davranış
değiştirmez; profile_resolved değeri sadece events.jsonl audit
metadata'sına eklenir (gelecek raporlar için drill-down).

### Principle 3 — AI Suistimal Önlemi (Anti-Cheap-Submission Gate)

**Statement.** AI'ın "submit liste şişirme" suistimali preempt edilir:
target_urls listesi sadece çağıran skill'in artefact'ından (new-blog
output URL'leri) ya da kullanıcının açık manifest'inden gelir.
Hayali / paddingli / wildcard URL submit yasak.

**Gate kuralları:**
- target_urls dedup (canonical normalize: trailing slash, protocol,
  case-fold host).
- Per-run cap: max 1000 URL (IndexNow 10000 cap, GSC 200/day quota
  buffer). Cap aşımı AMBER warning + truncate, audit'a yazılır.
- Same URL within 24h re-submit detect → AMBER skip (events.jsonl
  history scan); zorla yeniden ping için `force=true` flag (gelecek
  cycle).
- Wildcard pattern (`*`, `?`) input olarak REJECT — DURUR #5.

**Failure mode:** AMBER warning + auto-correct attempt; 2x AMBER aynı
pass → RED upgrade.

## Routing — 8-Step Workflow

> Step names are stable identifiers used as
> `steps[*].name` when the skill calls `workflow_runner.create_run`.

### Step 1 — `read_project_config`

`projects/{slug}/project.config.json` parse. `domain` + `profile`
field oku; `profile` placeholder pattern gereği audit metadata'sına
eklenir. `INDEXNOW_KEY` `.env` lookup (stdlib `os.environ.get`); yoksa
DURUR #3 hibrit branch (indexnow skip, google_indexing_api devam ettir
eğer submission_type bunu içeriyorsa).

### Step 2 — `read_master_xlsx_redirect_map`

`master.xlsx[redirect_404]` ve `master.xlsx[robots_txt]` sheet READ.
`openpyxl.load_workbook(read_only=True)`. F-1 allowed_writers=null
discipline: skill MUST NOT call `transaction.append`,
`transaction.update`, or `transaction.delete`.

`redirect_404` 5 columns consumed: `url, inlinks, action, target_url,
status`. Dictionary build: `{url: {action, target_url, status}}` for
O(1) cascade lookup.

`robots_txt` 5 columns consumed: `id, level, issue, detail, resolution`.
R-58 lifecycle map READ-ONLY consume; skill bu sheet'i write etmez,
sadece sitemap path / disallow rule sanity check için referans alır.

**DURUR #5 trigger.** master.xlsx eksik → init-project skill önce
çalışmalı (Phase 5 W-Q paterni).

### Step 3 — `validate_target_urls` (R-91 Cascade)

`target_urls` her eleman:
- RFC 3986 absolute URL (https:// zorunlu) + `urlparse` host =
  project-config[domain] match.
- Wildcard pattern (`*`, `?`) → REJECT (Principle 3 anti-cheap-content).
- `redirect_404` lookup:
  - action=410 → REJECT (kalıcı kaldırılmış URL submit yok).
  - action=301 → `target_url` ile rewrite (max 1 hop, döngü guard).
  - action=other / row missing → kabul.

Rejected URL'ler `rejected_urls[]` listesinde event'e eklenir.

**DURUR #5 trigger.** R-91 cascade fail (target=None on 301 row, döngü
detect) → reject + audit.

### Step 4 — `submit_indexnow` (Conditional)

Sadece `submission_type in [indexnow, both]` ise çalışır.
`INDEXNOW_KEY` yoksa skip (DURUR #3 AMBER).

stdlib HTTP request (no third-party lib):

```python
# Pseudocode — actual impl uses urllib.request.Request + urlopen
body = json.dumps({
    "host": domain,
    "key": indexnow_key,
    "keyLocation": f"https://{domain}/{indexnow_key}.txt",
    "urlList": validated_urls,
}).encode("utf-8")
req = urllib.request.Request(
    "https://api.indexnow.org/IndexNow",
    data=body,
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
```

Expected response: 200/202 success, 400 invalid, 403 forbidden, 422
unprocessable. Non-2xx → AMBER + retry-once exponential backoff (Step 4
inline retry, NOT global retry).

### Step 5 — `submit_google_indexing_api` (Conditional)

Sadece `submission_type in [google_indexing_api, both]` ise çalışır.

`mcp__gsc__submit_sitemap` submits the project `sitemap.xml` document
(sitemap-level submission, NOT per-URL). Per GSC sitemap API: 200/204
success, 429 quota, 5xx server.

**Per-URL Google Indexing API — eligibility hard-gate (NOT a generic channel).**
The per-URL Indexing API (`indexing.googleapis.com/v3/
urlNotifications:publish`) is **not a generic URL-indexing channel**: per
Google's documented restriction it accepts ONLY pages whose primary content
is a **JobPosting** posting or a **BroadcastEvent** (live-stream) — any other
page type is a spam-policy violation. Generic indexing therefore stays on the
two generic channels (sitemap submission + IndexNow). This per-URL path is
**not yet wired** (reserved for post-Wave-2). When it IS wired, BOTH of the
following gates must pass before any per-URL notification fires:

1. **Eligibility pre-check (deterministic hard-gate, policy).** Parse the
   target page's JSON-LD and confirm the `@type` is `JobPosting` or
   `BroadcastEvent` structured data. **Ineligible page → REFUSE** with an
   explanation (`"Indexing API yalnızca JobPosting / BroadcastEvent sayfaları
   için uygundur; bu sayfa uygun değil — sitemap submission + IndexNow
   kullan"`). This gate is Google's documented eligibility restriction and is
   **independent of consent** — an ineligible page is refused even WITH
   operator approval.
2. **Operator-consent gate.** Explicit per-run Süleyman approval
   (`requires_approval: true`, `safe_auto_execute: false`); autonomous
   submission is forbidden. Consent is **necessary but NOT sufficient**: it
   gates an *eligible* page's notification but cannot make an ineligible page
   eligible.

The `URL_UPDATED` / `URL_DELETED` notification types stay RESERVED for this
unbuilt per-URL path and are never emitted on the wired sitemap path (which
records `sitemap_submission` semantics — see Step 7).

**DURUR #4 trigger.** GSC API 5xx / timeout → AMBER + retry-once
exponential backoff (1s base, 2x). Retry fail → mark URL failed,
continue with remaining URLs (no global abort).

### Step 6 — `aggregate_results`

Per-URL outcome dictionary build:
- `submitted_count` — IndexNow OR GSC 2xx.
- `failed_urls[]` — IndexNow AND/OR GSC fail (`{url, reason, response_code}`).
- `rejected_urls[]` — Step 3 R-91 cascade reject (`{url, reason}`).
- `indexnow_response_code` — last IndexNow API response (single batch).
- `gsc_response_codes` — list of per-URL GSC response codes.
- `durations_ms` — per-step elapsed time.

### Step 7 — `emit_events_provenance`

`_state/events.jsonl` append. **Schema-first override** rationale (see
Outputs section above): `event_type=indexing_submitted` would violate
the events.schema event_type enum, so skill writes:

| Field            | Value                                          |
|------------------|------------------------------------------------|
| `schema_version` | `1.0`                                          |
| `event_kind`     | `work` (events.schema enum, ADR-020)           |
| `event_type`     | `manual` (closed-12 enum compliant)            |
| `event_id`       | `manual_T-NNNN_<timestamp_compact>`            |
| `task_id`        | `T-NNNN` (per-run minted, work events require) |
| `timestamp`      | UTC ISO 8601                                   |
| `project_id`     | `project-config[project_id]`                   |
| `note`           | `host + url_count + submitted + failed summary`|
| `indexing_ping`  | `{ attempted, response_code, called_at }` — **sitemap_submission** semantics; `call_type` is OMITTED on the wired `mcp__gsc__submit_sitemap` path (a sitemap-level submission has no per-URL notification type). The `call_type` enum (`URL_UPDATED` / `URL_DELETED`) stays RESERVED for the unbuilt, consent-gated per-URL Google Indexing API. |
| `primary_source` | `manual`                                       |

Per-URL detail goes into `indexing_ping` sub-object plus the
companion JSON report (Step 8); events.jsonl stays under the
events.schema.json closed enum.

### Step 8 — `write_report_artifact`

`outputs/indexing/{date}-submission-report.json` write:

```json
{
  "schema_version": "1.0",
  "run_at_utc": "2026-05-04T10:30:00Z",
  "submission_type": "both",
  "host": "example.com",
  "submitted_count": 7,
  "failed_urls": [{"url": "...", "reason": "...", "response_code": 503}],
  "rejected_urls": [{"url": "...", "reason": "R-91 410 cascade"}],
  "indexnow_response_code": 200,
  "gsc_response_codes": [200, 200, 200, 200, 200, 200, 200],
  "durations_ms": {"step3": 5, "step4": 120, "step5": 850, "step7": 3}
}
```

Artefact is the truth-verifiable audit complement (Principle 1 Layer 3).

## DURUR Conditions (5)

| #  | Trigger                                                      | Resolution                                                                |
|----|--------------------------------------------------------------|---------------------------------------------------------------------------|
| 1  | target_urls boş                                              | SKIP — event severity=info, audit append, output report yine yazılır     |
| 2  | submission_type enum dışı (`indexnow`/`google_indexing_api`/`both` değil) | ABORT — RED, çıktı yok                                                    |
| 3  | INDEXNOW_KEY .env'de yok (`os.environ.get` None)             | AMBER skip indexnow path; google_indexing_api submission_type'a dahilse devam |
| 4  | GSC API 5xx / timeout                                        | AMBER + retry-once exponential backoff; retry fail → URL failed, continue |
| 5  | target_url R-91 cascade (action=410 ya da target=None on 301) | REJECT — rejected_urls[]'a yaz; rest of run continues                     |

## master.xlsx WRITE YASAK (R-58 + F-1)

W-G1 sadece `redirect_404` + `robots_txt` sheet'lerini READ eder. WRITE
YOK. F-1 schema authority (master-excel.schema.json):

- `redirect_404.allowed_writers` = null (read-only consume).
- `robots_txt.allowed_writers` = null (R-58 lifecycle map READ-ONLY).

Test sentinel: monkey-patch `openpyxl.Workbook.save` → çağrılırsa fail
fast (W-G1 hiçbir koşulda workbook save çağırmaz).

## Plugin-Agnostic Discipline

- No project slug hardcoded inside this skill (`dentnotion`, `vento`,
  `eykom`, `bigcattr`, `calitte`, `lastiksa`, `noraninsaat`, `adstark`
  are FORBIDDEN tokens — pytest grep verifies).
- Domain comes from `project-config[domain]` at runtime.
- `.mcp.json` is **NEVER** modified by this skill (F-16 invariant).
  Test sentinel: pre/post byte-hash diff on `.mcp.json` must be
  identical.
- Per-call / per-url credit shape names (Phase 7 lesson, ADR-028 anti-
  pattern) MUST NOT appear in this skill — `budget.estimated_credits`
  (number, here 0) is the only allowed shape per skill-frontmatter
  schema. Phase 7 reject paterni `metric_*name` ve credit `*_per_call`
  / `*_per_url` shape isimlerinin hiçbiri bu skill body'sinde yer almaz
  (test sentinel grep kanıtlar).

## Error Handling

| Failure                           | Mode  | Action                                                          |
|-----------------------------------|-------|-----------------------------------------------------------------|
| target_urls empty                 | INFO  | DURUR #1 SKIP, audit append                                     |
| submission_type invalid           | RED   | DURUR #2 ABORT, no output                                       |
| INDEXNOW_KEY missing              | AMBER | DURUR #3 hibrit; gsc path devam edebilirse                      |
| GSC 5xx / timeout                 | AMBER | DURUR #4 retry-once exponential backoff; fail → URL skip        |
| R-91 cascade reject (410 / None)  | INFO  | DURUR #5 REJECT, audit + report                                 |
| host mismatch (URL ≠ domain)      | RED   | Principle 1 Layer 1 reject + audit                              |
| wildcard pattern in target_urls   | RED   | Principle 3 reject + audit                                      |
| master.xlsx save attempt          | RED   | F-1 violation — fail-fast (test sentinel)                       |
| .mcp.json byte hash drift         | RED   | F-16 violation — fail-fast (test sentinel)                      |

## Schema-First Override Decisions Made (Lesson 7+23)

The brief sketched the events.jsonl payload using `event_type=
indexing_submitted` and listed `event_kind=work` / `event_type=
indexing_submitted` under "Outputs". Worker authority applied:

1. **Override 1 — `event_type` enum compliance.** `events.schema.json`
   declares `event_type` as a closed 12-value enum; the brief's
   `indexing_submitted` is NOT in it. Skill writes `event_type=manual`
   instead and shifts the indexing-specific fields into the schema's
   purpose-built `indexing_ping` sub-object (events.schema
   `properties.indexing_ping`). Compliance restored without schema bump
   (Phase 12 hedef 0 schema bump).
2. **Override 2 — Frontmatter `outputs[]` is artifact refs, not event
   payload fields.** The brief's "Outputs" mixed conceptual layers.
   Frontmatter outputs[] now lists `_state/events.jsonl` and
   `outputs/indexing/{date}-submission-report.json` (artifact ref
   strings per skill-frontmatter.schema.json L64-72). The
   `event_kind/event_type/note/indexing_ping` fields are documented
   under "Step 7 — emit_events_provenance" as events.jsonl payload,
   not as frontmatter outputs[].
3. **Override 3 — `task_id` required on work events.** The brief did
   not mention `task_id`; events.schema.json allOf rule (L277-281)
   requires it on `event_kind=work`. Skill mints a per-run `T-NNNN`
   counter (compatible with master_task.task_id pattern).

Manager spot-check expected to confirm these are valid schema-first
overrides (no manager mop-up needed for ≤10-line atomic per-property
fixes per Phase 11 lesson 28 matrix).

## References

- `rules/content-quality.md` (Foundational Principles, R-01..R-148).
- `schemas/skill-frontmatter.schema.json` (8 required fields, category
  enum 8 values, status enum 3 values).
- `schemas/events.schema.json` (event_kind enum 4 values, event_type
  closed 12-value enum, indexing_ping sub-object
  `properties.indexing_ping`, ADR-020 workflow kind).
- `schemas/master-excel.schema.json` (18 sheets — `redirect_404` and
  `robots_txt` columns; F-1 allowed_writers=null discipline).
- `schemas/project-config.schema.json` v1.2 (singular profile field,
  Phase 11 W-F1 cascade fix).
- ADR-020 (event_kind=workflow vs work routing).
- ADR-028 (Phase 7 lesson — generic shape-name anti-pattern; ADR text
  carries the specific token forms, intentionally omitted here so this
  skill body stays grep-clean).

## Wave-Out Note

This skill is `status: wip` until Phase 12 Wave 2 acceptance gate;
`active` bump deferred to the post-Wave 1 closeout. Manager owns the
status flip + governance audit.
