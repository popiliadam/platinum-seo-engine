---
schema_version: "1.0"
name: Merchant Structured Data
status: enforced
applies_to: [skill, workspace]
spec_section: "GAP-A3 (docs/superpowers/plans/amo/2026-06-10-gap-specs-acquisition-local-commerce.md) + unified dispatch §R-MAP (R-147/R-148)"
related: [schema-first, content-html-discipline]
applied_to_skills: [schema-audit]
since: "2026-06-10"
supersedes: none
source: "https://developers.google.com/search/docs/appearance/structured-data/merchant-listing"
---

# Merchant Structured Data — Listing Experience Requirements

E-commerce projects (project.config `profiles` containing `e-commerce`) are
audited against Google's **merchant listing experience** requirements by the
schema-audit skill's merchant module
(`scripts/discovery/merchant_listing_audit.py`, checks M1–M7). These rules fix
what the engine may claim, recommend, and never do. Rule ids R-147/R-148 are
allocated by the unified remediation dispatch §R-MAP (2026-06-10).

Verified sources (official docs only — third-party summaries are not
citation-grade here):

- Merchant listings (required vs recommended properties):
  https://developers.google.com/search/docs/appearance/structured-data/merchant-listing
- Organization-level shipping (Nov 12, 2025 launch):
  https://developers.google.com/search/blog/2025/11/more-ways-to-share-shipping
  · https://developers.google.com/search/docs/appearance/structured-data/shipping-policy
- Organization-level returns:
  https://developers.google.com/search/docs/appearance/structured-data/return-policy

### R-147 — Offer accuracy (fiyat/stok mutlaka canlı sayfayı yansıtır)

Schema offer data must mirror the live page — merchant listings are a
price-accuracy surface, and stale or wrong values are worse than no markup.

- `Offer.price` (or `priceSpecification.price`) must be present, numeric and
  **> 0**; `priceCurrency` must be present and **equal to the project.config
  `currency`** (ISO 4217). A `priceCurrency` that disagrees with the
  project's configured currency is a HIGH finding (real TR-platform failure
  mode: USD markup on a TRY storefront).
- `Offer.availability` must use the canonical `https://schema.org/…`
  ItemAvailability URL form; bare literals (`"InStock"`) are flagged.
- Merchant listing eligibility requires a plain `Offer` whose seller is the
  merchant; `AggregateOffer`-only product markup is flagged.
- An expired `priceValidUntil` must be refreshed or removed (price-accuracy
  signal); unparseable dates are findings, not guesses.
- The engine must **never fabricate** offer data it cannot observe: no
  invented prices, currencies, availability states or dates — absent data
  produces an "add/verify" finding, never a synthesized value. The optional
  price-parity sample (M7) compares markup against pre-fetched rendered HTML
  and is explicitly labeled a heuristic.

**Failure mode:** any M1/M2/M3/M6/M7 finding lands as a TODO row on
`master.xlsx#schema` with the priority encoded in `remaining_work`
(`merchant M1/high: …`); fabricating values to silence a finding is a
hard violation (Foundational Principle: uydurma yasak).

### R-148 — Shipping/returns markup: org-level-first (tek script, tek sayfa)

Shipping and returns annotations are **recommended-not-required** for
merchant listings — findings are framed as an **opportunity**, never as a
compliance failure.

- On limited-template TR platforms (ticimax / ideasoft / imagaza) the
  default recommendation is **org-level** markup deployed once on the
  shipping/returns policy page via the platform's site-wide script slot:
  `Organization.hasShippingService` → `ShippingService` (required property:
  `shippingConditions`, type ShippingConditions) and
  `Organization.hasMerchantReturnPolicy` → MerchantReturnPolicy. No Merchant
  Center account is required for either.
- ⚠️ There is **no `OrganizationShippingDetails` type** — the correct chain
  is `Organization.hasShippingService` → `ShippingService`. Do not invent
  type names.
- Per-offer `OfferShippingDetails` / `hasMerchantReturnPolicy` are the
  **override path only**: use them when a specific product genuinely
  deviates from the site-wide policy (Google's own guidance: per-offer
  markup overrides the org-level policy and should be used only for
  deviations), not as the default deployment strategy.
- Search Console's "Shipping and returns" settings panel is the no-code
  alternative (settings/Merchant Center data override markup) — audit
  findings must mention it in `remaining_work` guidance where relevant.
- Coverage logic (M4/M5): org-level markup observed **or** per-offer markup
  in use satisfies coverage; neither produces exactly ONE site-level
  opportunity row (never per-product row spam). When no Organization
  JSON-LD is observable in the crawl surface, the finding says "not
  observable — verify before deploying" instead of asserting absence on the
  live site.

**Failure mode:** recommending per-product Offer edits on a platform that
only supports site-wide script injection (deployment-impossible advice), or
framing missing shipping/returns markup as a compliance failure, violates
this rule.

## History

- v1.0 (2026-06-10) — created by GAP-A-B1 (acquisition spec GAP-A3); rule
  ids remapped from the spec draft per the unified dispatch §R-MAP.
