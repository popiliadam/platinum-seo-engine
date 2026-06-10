---
name: Tech SEO Governance
status: enforced
applies_to: [plugin, skill]
applied_to_skills: [hreflang-audit, facet-nav-audit, robots-policy-audit, migration-map, content-remediation, sf-import]
source: 2026-06-10 technical-SEO infrastructure cluster build (GAP-T1..T4) + Google Search Central 2024-2026 guidance
spec_section: "Tech SEO Governance — hreflang / faceted nav / robots-noindex lifecycle / migration"
---

# Tech SEO Governance

Technical-SEO infrastructure policy for the four crawl/index governance gaps
(hreflang/i18n, faceted-navigation & crawl-budget, robots/noindex lifecycle,
site-migration redirect maps). Every rule below is **recommendation-only**: the
engine has no write access to client infrastructure (CMS, server config,
robots.txt, sitemaps) — it computes findings + proposed artifacts + deployment
instructions, and the **operator deploys**. Failure mode for the discovery
rules is therefore AMBER (findings written, nothing blocked) unless explicitly
noted RED.

These rules are derived from Google Search Central documentation (2024–2026):
hreflang ([Localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions)),
faceted navigation ([Managing crawling of faceted navigation URLs](https://developers.google.com/crawling/docs/faceted-navigation),
[Crawling December 2024](https://developers.google.com/search/blog/2024/12/crawling-december-faceted-nav)),
crawl budget ([Crawl budget management](https://developers.google.com/crawling/docs/crawl-budget)),
robots/noindex ([robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro),
[Block indexing with noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing),
[Robots meta / X-Robots-Tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)),
and site moves ([Site moves with URL changes](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes),
[Redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects)).

Output convention: all findings are written into `master.xlsx#robots_txt`
(id/level/issue/detail/resolution) with a per-skill id prefix (`HF-`/`FN-`/`RP-`)
via `scripts/util/sheet_merge.py`, surviving sf-import's `transaction.replace`
snapshot; migration rows land in `master.xlsx#redirect_404`. No new master.xlsx
sheet, no events-schema change, no project-config schema change (history-stable
per ADR-038, additive-only per ADR).

---

## Rules

### R-125: Hreflang Cluster Reciprocity

**Statement.** Every hreflang annotation set must form a **closed, reciprocal
cluster**: each member must list **itself plus every other member** (the
bidirectional return-link requirement), and all hreflang targets must be HTTP
200, indexable, self-canonical, and **fully-qualified absolute** URLs. A
one-directional pair (A links B, B does not link A) is a **HIGH** finding.
A return target that is `noindex`, non-canonical, or non-200 is a **HIGH**
finding (it breaks the cluster).

**Rationale.** Google **ignores** a hreflang annotation that is not reciprocated
([Localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions)),
so a one-directional pair silently delivers zero benefit; and a return target
that cannot be indexed/canonicalized removes that variant from the cluster. This
is the single highest-leverage hreflang check.

**Enforcement.** `hreflang-audit` skill computes the reciprocity graph from
`projects/{slug}/sf-exports/{date}/raw/hreflang_all.csv`, joining
`canonicals_all.csv` + `internal_all.csv` (Indexability) to validate return
targets. Findings → `robots_txt` rows, id prefix `HF-`.

**Failure mode.** AMBER (findings written; deployment is operator-executed —
the engine has no `<head>`/sitemap write access).

### R-126: Hreflang Code & x-default Validity

**Statement.** hreflang codes must be **ISO 639-1 language** (+ optional **ISO
3166-1 Alpha-2 region**, e.g. `tr-TR`, `en-CA`) or `x-default`. Unknown/invalid
codes (e.g. `en-UK` — the ISO region code is `gb`) = **MEDIUM**. Missing
`x-default` on a multi-language cluster = **LOW** (recommended, not required). A
single-language project with **zero** hreflang = **COMPLIANT** (explicit
NOT_APPLICABLE verdict — absence of hreflang is correct, not a defect).

**Rationale.** Invalid codes are silent failures (Google neither warns nor maps
the variant). The validator is **permissive** — it must never RED an exotic-but-
valid code (e.g. `zh-Hant-TW`); only clearly malformed codes are flagged.
Single-language sites (the entire current portfolio: tr-TR, en-CA, en-NG) need
the cheap hygiene assurance that no stray/contradictory hreflang exists.

**Enforcement.** `hreflang-audit` validates each code against a permissive
BCP-47-ish regex; single-language + zero hreflang short-circuits to
NOT_APPLICABLE with an empty finding set and a rendered report.

**Failure mode.** AMBER.

### R-127: Locale Consistency (config ↔ site)

**Statement.** When hreflang exists, at least one cluster member's hreflang code
must be **compatible with** `project.config.json[language.content_locale]`
(language-subtag match). A declared content locale that appears in **no**
hreflang cluster on the site = **MEDIUM** (the site claims variants the engine's
portfolio config does not know about → flag for the operator to either extend
portfolio config or fix the site).

**Rationale.** A mismatch between the engine's declared locale and the site's
hreflang map signals either stale portfolio config or a real site
mis-annotation; either way it is an operator decision, never an autonomous fix
(no multi-language client has signed; `project.config` has no `alternates`
array yet — deferred until one does).

**Enforcement.** `hreflang-audit` compares cluster codes (language subtag) to
`content_locale`; mismatch → `HF-` row.

**Failure mode.** AMBER.

### R-128: Parameter Taxonomy

**Statement.** Every query parameter and facet path-segment observed in a crawl
is classified into the **closed set**
`{facet_filter, sort, pagination, internal_search, session_or_tracking, functional, unknown}`.
Classification source order: (1) per-project override file
(`projects/{slug}/config/facet-policy.json`), (2) platform seed dictionary, (3)
behavioral heuristics (cardinality, canonical-target collapse, indexability
mix). When `unknown`-class URLs ≥ a configured threshold → an operator-triage
finding.

**Rationale.** Crawl-budget governance for large auto-generated sites
([Crawl budget management](https://developers.google.com/crawling/docs/crawl-budget))
requires knowing *what* the parameter space is before deciding how to manage it.
Platform seed dictionaries are marked HEURISTIC; the engine must **not invent
platform-specific parameter names it cannot verify** — unverifiable parameters
flow to the `unknown`-triage path by design, never to a fabricated class.

**Enforcement.** `facet-nav-audit` parses every Address with `urllib.parse`,
buckets by param name + path-segment facet (via `url_patterns` + platform
seeds), and emits the taxonomy into the report; over-threshold `unknown` → a
`FN-` row.

**Failure mode.** AMBER.

### R-129: Index-Bloat Budget

**Statement.** `internal_search` URLs must **NEVER** be indexable (Google: block
crawling of internal search results; de-index via the noindex path per R-133).
`sort` / `session_or_tracking` URLs must be crawl-blocked or canonicalized and
**never** appear in a sitemap. `facet_filter` URLs may be indexable **ONLY with
demand evidence** — a matching query in `master.xlsx#cluster_keywords` /
`#gsc_performance` with volume/impressions > 0; otherwise the recommendation is
block/canonical. Zero-result filter combinations must return **HTTP 404**
([faceted navigation](https://developers.google.com/crawling/docs/faceted-navigation)).

**Rationale.** Internal-search and infinite-facet spaces are classic
crawl-budget sinks and index-bloat sources; indexing a facet only pays off when
real search demand exists for it. Demand is read from existing master.xlsx data
(volumes/impressions) → **zero paid MCP calls**.

**Enforcement.** `facet-nav-audit` cross-references each indexable
facet/search/sort URL against the demand sheets; offenders → `FN-` rows
(internal_search indexable = HIGH; sort/tracking indexable = MEDIUM;
facet_filter indexable without demand = MEDIUM).

**Failure mode.** AMBER (recommendations only).

### R-130: Blocking-Mechanism Decision Tree

**Statement.** Choose the blocking mechanism by intent:
- **never indexed + crawl waste** → robots.txt `disallow` pattern;
- **currently indexed + must be removed** → crawlable `noindex` **FIRST**;
  robots.txt `disallow` only **after** de-indexing is confirmed (cross-link
  R-133);
- **duplicate-ish / consolidating signals** → `rel=canonical`;
- **new build** → fragment-based (`#`) filters (Google generally does not crawl
  fragments).

The engine emits **recommended** robots.txt blocks + per-class actions; the
**operator deploys** — the engine never writes to client infrastructure.

**Rationale.** robots.txt is a crawl-management tool, **not** a de-indexing tool
([robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro));
disallowing a URL that must leave the index traps it (Google can still index it
from external links and never sees the noindex) — hence the noindex-first
ordering and the R-133 cross-link.

**Enforcement.** `facet-nav-audit` produces a deterministic
`proposed_robots_block` (`disallow: /*?*<param>=` + explicit `allow:`
exceptions for the `functional` class) inside the report; never deployed by the
engine.

**Failure mode.** AMBER.

### R-131: Governed robots.txt Policy (Recommendation-Only)

**Statement.** The engine maintains a per-project **EXPECTED** robots.txt policy
(derived from the R-128..R-130 parameter classes + the project profile). The
**live** robots.txt is fetched and parsed on each audit; diffs against the
expected policy become findings; the engine emits a full **proposed robots.txt
artifact**. Deployment is **ALWAYS operator-executed** (no client-site writes
exist). The `Sitemap:` directive must be present and point at the live sitemap.

**Rationale.** Centralizing the expected policy lets every audit detect drift
(an operator hand-edit, a CMS regression) and produce a single deployable
artifact instead of scattered advice.

**Enforcement.** `robots-policy-audit` fetches `https://{domain}/robots.txt`
(Scrapling GET — a read of a public file, no consent gate), lints it, and writes
`RP-` rows + `outputs/robots/{date}-robots.proposed.txt`.

**Failure mode.** AMBER.

### R-132: Noindex Deployment Path (R-58 Deployability)

**Statement.** Lifecycle noindex (the R-58 map: `ON_HOLD → noindex,follow`)
deploys via the platform-appropriate channel, in **priority order**: (1)
CMS/SEO-plugin per-page robots control (e.g. WordPress + Rank Math per-post
robots meta), (2) `X-Robots-Tag` HTTP header via server/CDN config, (3)
theme-level `<head>` template edit. The engine renders the **instruction + the
exact value**, never the page itself.

**Rationale.** R-58 ([content-html-discipline.md](content-html-discipline.md))
maps content lifecycle → meta robots but is **undeployable as written**: the
content pipeline emits body fragments (R-22 header/footer untouchable), so it has
no `<head>` access and ON_HOLD content is silently indexable today. This rule is
the deployment path R-58 lacks. Every meta-robots rule has an exact
`X-Robots-Tag` equivalent
([Robots meta / X-Robots-Tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)),
which is the documented alternative for untouchable-`<head>` platforms.

**Enforcement.** `robots-policy-audit` renders `deployment_instructions` from a
platform matrix keyed by the 6-value `project.config[platform]` enum; entries
the worker cannot verify from official docs carry `verified: false` (fabricating
panel paths is forbidden).

**Cross-link:** R-58 (content-html-discipline — lifecycle robots-meta map).

**Failure mode.** AMBER.

### R-133: Noindex/Disallow Mutual Exclusion

**Statement.** A URL that must **leave** the index must **NOT** be robots.txt-
disallowed until its removal is confirmed (noindex requires crawlability).
Ordering: deploy `noindex` → verify de-indexed (directives/index data) → only
**then** optionally `disallow` for crawl savings. Any URL that is simultaneously
(a) disallowed by the live robots.txt **and** (b) carrying `noindex` / lifecycle
`ON_HOLD` is a **HIGH** finding.

**Rationale.** A robots.txt-disallowed page can never be crawled, so Google never
sees its `noindex` and may keep indexing it from external links
([Block indexing with noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing)) —
the classic de-indexing trap.

**Enforcement.** `robots-policy-audit` scans live disallow rules × `directives_all`
noindex URLs × lifecycle ON_HOLD slugs; conflicts → `RP-` rows.

**Failure mode.** AMBER.

### R-134: Migration Redirect-Map Contract

**Statement.** Every old URL in the crawl inventory must resolve to exactly one
disposition: `301 → mapped target` (one-to-one wherever possible) or `410`.
**Homepage-collapse guard:** > 5% of 301 targets being the homepage is a **HIGH**
finding (topical signals collapse). Chains in the deployed map must be ≤ 3 hops;
loops are forbidden. Redirects must be retained **≥ 1 year** (180-day hard
floor); retirement only with traffic evidence.

**Rationale.** Google's site-move guidance
([Site moves with URL changes](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)):
prepare a one-to-one mapping, do **not** mass-redirect to the homepage, use
server-side 301, keep redirects ~1 year. A silently dropped (unmapped) URL or a
loop is a hard correctness failure.

**Enforcement.** `migration-map` skill builds the map from explicit pairs +
ordered regex rules over the full inventory; rows → `master.xlsx#redirect_404`.

**Failure mode.** RED for loops / unmapped-silent-drop; AMBER otherwise.

### R-135: Migration Phase Gate

**Statement.** Migration phases are `plan → freeze → deploy (operator) →
verify`. The engine produces the map and the verification; the **operator
deploys** (htaccess/nginx/platform snippets are recommendations). Domain-level
moves additionally get a **Change-of-Address** checklist item (GSC UI,
operator-executed). The old sitemap is kept temporarily live alongside the new
one to accelerate redirect discovery.

**Rationale.** Phase separation keeps the irreversible, outward-facing step
(deployment) firmly operator-owned; the Change-of-Address tool has no API and
applies only to domain moves, not path/CMS restructures
([Change of Address](https://support.google.com/webmasters/answer/9370220)).

**Enforcement.** `migration-map` emits the phase-gate checklist (incl.
Change-of-Address when the domain changes) in the rendered report.

**Failure mode.** AMBER.

### R-136: Post-Migration Verification & Rollback Watch

**Statement.** Verify mode must confirm, per map row: old URL → **single-hop
301** → **200** target. Findings: chain > 3, `302`-instead-of-`301`, `404`
regressions, redirect-to-homepage drift. Verification cadence: **T+1d / T+7d /
T+30d**. Unresolved CRITICALs → a **rollback recommendation** in the report.

**Rationale.** Migrations regress silently; a fixed verification cadence with an
explicit rollback trigger catches 302-leaks, broken chains, and homepage
collapse before ranking loss compounds
([Redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects)).

**Enforcement.** `migration-map` verify mode reads `redirect_chains.csv` +
`response_codes_all.csv` from the post-launch export and updates matching
`redirect_404` rows' `status`.

**Failure mode.** AMBER.
