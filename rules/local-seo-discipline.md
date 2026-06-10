---
name: Local SEO Discipline
status: enforced
applies_to: [workspace, skill]
spec_section: "GAP-A2 (2026-06-10 acquisition build spec) + §16.5"
related: [content-seo-discipline, content-html-discipline, schema-first]
applied_to_skills: [gbp-audit, new-blog, revise-content]
since: "2026-06-10"
supersedes: none
schema_version: "1.0"
---

# Local SEO Discipline — NAP, Reviews, Location Pages

Governance for local-search work across the portfolio: one canonical NAP
source of truth, white-hat-only review acquisition, and anti-doorway
location-page methodology. Born in GAP-A2 (2026-06-10 acquisition build
spec; unified dispatch batch GAP-A-B2, rule ids R-144–R-146 per the
unified §R-MAP allocation) alongside `schemas/local-nap.schema.json`,
`scripts/discovery/nap_consistency.py` and the gbp-audit NAP branch.

## Rules

### R-144: NAP Single Source of Truth

`projects/{slug}/local/nap.json` (validates against
`schemas/local-nap.schema.json`) is the ONLY canonical NAP
(Name / Address / Phone) for a project.

- Every skill/report/template that prints NAP (location pages, footers,
  LocalBusiness JSON-LD, GBP recommendations) reads it — never a
  hand-typed copy and never a second "source of truth".
- Mismatches observed anywhere (GBP listing, site footer, contact page,
  LocalBusiness schema) are **HIGH findings** against the canonical:
  `gbp-audit` emits them to `master.xlsx#gbp_audit` with
  `category="nap"` via `scripts/discovery/nap_consistency.compare_nap`.
  They are NEVER silently "fixed" in copy — the operator decides which
  side is right, updates `nap.json` if the canonical itself is stale,
  then syncs every surface to it.
- Multi-location businesses list every branch in `locations[]` with a
  stable `location_id`; comparison resolves per location (a branch's
  phone/address overrides the top-level NAP, omissions fall back).
- Failure modes: `nap.json` missing → gbp-audit emits one MEDIUM
  "Canonical NAP file missing" row (the audit still runs);
  present-but-unparseable → **fail-loud STOP** (gbp-audit DURUR #9) —
  auditing against half a canonical is worse than stopping.
- Citation/directory consistency beyond Google (TR directories) has no
  reliable API and stays operator work — the canonical doc is what the
  operator syncs those listings against.

### R-145: Review Acquisition — White-Hat Only

Engine output and operator-facing assets MUST NOT:

1. offer or imply **incentives** for reviews (payment, discount, free
   goods/services, draws/raffles) — whether for posting, revising or
   removing a review;
2. **gate or filter by sentiment** — asking only satisfied customers
   (or steering unhappy ones away from Google) is selective
   solicitation and violates policy just like incentives do;
3. draft incentive or gating copy into any client deliverable.

The ONLY sanctioned pattern: ask **every** customer post-service, with
the direct GBP review link (or its QR form), no filter, no reward.
Policy authority — cite these official URLs, not third-party summaries:

- https://support.google.com/contributionpolicy/answer/7400114
  (Maps user-generated-content policy: prohibited review practices)
- https://support.google.com/business/answer/14114287
  (Business Profile review policy + enforcement)

Enforcement is now profile-level (review intake frozen / existing
reviews unpublished), so a violation is a client-asset risk, not a
style preference.

Forbidden phrase patterns (TR) — production skills must never emit
them; listed here so `scripts/validation/content_validator.py` can
adopt them later (validator adoption itself is out of GAP-A2 scope):

- "yorum karşılığı indirim"
- "puan karşılığı hediye"
- "5 yıldız bırakana"
- "yorum yapana çekiliş"
- "olumsuz yorumu kaldırın, ... verelim"

The operator handout template for this rule is
`templates/content/review-acquisition-policy.template.md`.

### R-146: Location Pages — Anti-Doorway

Google's spam policy prohibits doorway pages — "multiple pages targeted
at specific regions or cities that funnel users to one page"
(https://developers.google.com/search/docs/essentials/spam-policies#doorway-pages).
A location page may ship ONLY when ALL of the following hold:

1. **≥3 location-unique elements** drawn from: location-specific
   service detail (what is actually offered/served THERE), local proof
   (case study / completed job / photos taken at that location),
   location-specific FAQ, embedded map + per-location NAP rendered
   from `local/nap.json`. The skeleton slots live in
   `templates/content/location-page.template.html`.
2. **No city-swap boilerplate:** pairwise similarity against sibling
   location pages stays under the Screaming Frog near-duplicate
   threshold — the signal is already available via the existing
   `near_duplicates_report` canonical export; two location pages ~90%
   identical with only the city name swapped is the red flag.
3. **No orphans:** every location page is reachable from site
   navigation and present in the sitemap.
4. **One page per REAL serviced location** — no pages for cities
   without genuine service presence there (representation authority:
   https://support.google.com/business/answer/3038177).

The engine provides the template + this rule; location-page content is
produced through the normal production-skill discipline (new-blog /
revise-content three-layer enforcement). A programmatic city-page
generator is explicitly out of scope — bulk generation IS the doorway
machine this rule exists to prevent.

## Cross-references

- Schema: `schemas/local-nap.schema.json` (canonical NAP contract)
- Pure module: `scripts/discovery/nap_consistency.py`
  (`normalize_phone`, `normalize_address_tokens`, `compare_nap`)
- Consumer: `scripts/discovery/gbp_audit_transform.py` +
  `skills/discovery/gbp-audit/SKILL.md` (v1.1 — NAP branch + Step-4
  identity source fix)
- Templates: `templates/content/location-page.template.html`,
  `templates/content/review-acquisition-policy.template.md`
- Tests: `tests/discovery/test_nap_consistency.py`,
  `tests/skills/test_gbp_audit_nap.py`,
  `tests/schemas/test_local_nap_schema.py`
