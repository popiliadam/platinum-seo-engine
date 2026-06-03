---
description: |
  Use when: kullanıcı "GBP audit", "Google Business Profile kontrol", "place_id eksik mi", "business listing kontrol", "harita listing audit", "google haritalar profili", "GMB audit", "local listing gap" der ya da `/pseo-gbp-audit` çağırırsa.
  Also use when: aktif projenin `project.config.profiles` array'inde `"local-service"` var; init-project çalışmış (master.xlsx hazır); GBP gap analysis 8 kategori (NAP / categories / photos / hours / attributes / posts / Q&A / reviews) triage gerekiyor; DFS budget mevcut (~3 credit/audit).
  Do not use when: profile != local-service (skill kendisi DURUR #6 ile skip eder ama gereksiz çağrı); master.xlsx yokken (`/pseo-init` önce); tech-audit (`/pseo-tech-audit`), GSC pull (`/pseo-gsc-pull`), DFS pull (`/pseo-dfs-pull`), schema audit (`/pseo-schema-audit`) gerekiyor — her birinin ayrı komutu var.
argument-hint: "[<project-slug>]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(ls:*), Bash(grep:*), Read
model: sonnet
---

# /pseo-gbp-audit — Google Business Profile Audit

> **Skill:** `skills/discovery/gbp-audit/SKILL.md` (Phase 5, aktif — G-AI-02 closure). DFS `business_data_business_listings_search` + Scrapling fallback → `scripts/discovery/gbp_audit_transform.py` pure compute → master.xlsx#gbp_audit sheet write + `outputs/reports/{date}-gbp-audit.md` + events.jsonl provenance row + onay gate. Otonom GBP API submit YASAK (`feedback_indexing_api_consent`).

## 1. Aktif projeyi çöz

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else CFG="$PSEO_WORKSPACE_ROOT/projects/$PROJECT/project.config.json"; if [ -f "$CFG" ]; then PROFILES=$(jq -r '.profiles | join(",")' "$CFG" 2>/dev/null); echo "active=$PROJECT profiles=$PROFILES"; if echo ",$PROFILES," | grep -q ",local-service,"; then echo "profile_gate=OK"; else echo "profile_gate=SKIP (local-service yok — skill DURUR #6 ile graceful exit verir)"; fi; else echo "config_missing — /pseo-init önce"; fi; fi; fi`

## 2. Skill chain

`skills/discovery/gbp-audit/SKILL.md` 8-step protokol koşar (spec §16.5 MCP discipline):

1. **profile_gate** — `project.config.profiles` içinde `"local-service"` yoksa DURUR #6 skip (paid call ÖNCESİ early exit)
2. **preflight_budget** — `scripts/budget/check_budget.py` (~3 credit estimate, ADR-016 SSoT)
3. **create_run** — workflow_runner.create_run (ADR-021)
4. **fetch_listing** — `mcp__dataforseo__business_data_business_listings_search` + raw JSON to `inbox/dfs/{date}-gbp-listing-{slug}.json` + provenance event with `cost.credits=3.0`
5. **scrapling_fallback** (conditional) — DFS empty result ise `mcp__ScraplingServer__fetch` Google Maps place page (anti-bot block tolere)
6. **transform** — `scripts/discovery/gbp_audit_transform.py` 8-category gap analysis + severity matrix (HIGH: listing yok / NAP mismatch / primary category yok / <3 photo / regular hours yok; MEDIUM: <2 secondary cat / <10 photo / holiday hours yok / attr eksik / review response <50% / avg rating <4.0; LOW: posts none last 30d / qa empty)
7. **request_approval** — onay gate (workflow-run.schema awaiting_approval); kullanıcı raporu inceler + onaylar
8. **write_excel + render_report + complete** — `transaction.append` master.xlsx#gbp_audit (7 col schema-locked) + `templates/reports/gbp-audit.template.md` render + final provenance event

DURUR (8 sentinel): budget fail / master.xlsx eksik / MCP auth-network / DFS response schema drift / RowSchemaError / profile_gate skip (graceful) / workflow_runner schema fail / PSEO_WORKSPACE_ROOT unset.

## 3. Çalıştırma notları

- **Otonom GBP submit YASAK:** Bu skill sadece audit + rapor üretir; GBP dashboard'una otomatik bir şey yazmaz (`feedback_indexing_api_consent` hard constraint). `recommended_action` kolonu operator için talimat; operator manuel uygular.
- **Profile gate erken çıkar:** e-commerce / b2b-saas / portfolio pure projelerde skill DURUR #6 ile graceful skip eder; credit harcanmaz.
- **3 credit/audit:** tech-audit'in ~13 credit'inden çok daha hafif (tek MCP call, URL listesi yok — single business query).
- **Scrapling fallback:** DFS empty dönerse Google Maps place page'i Scrapling'le çeker; anti-bot block (403) → transform `listing=None` ile devam eder ve "GBP listing not found" HIGH severity gap row emit eder.

## 4. Bağımlılıklar

- Skill: `skills/discovery/gbp-audit/SKILL.md` (Phase 5, active — G-AI-02 closure)
- Scripts: `scripts/discovery/gbp_audit_transform.py` + `scripts/budget/check_budget.py` + `scripts/state/events_writer.py` (`append_provenance`) + `scripts/excel/transaction.py` + `scripts/state/workflow_runner.py` + `scripts/reporting/render_template.py`
- Templates: `templates/reports/gbp-audit.template.md` (Phase 11 W deliverable; skill ship öncesi minimal inline render OK)
- Rules: `rules/schema-first.md` + `rules/budget-events.md` + `rules/append-only-state.md`
- Schemas: `schemas/master-excel.schema.json#gbp_audit` (7 cols, severityEnum + statusEnum reuse) + `schemas/events.schema.json`
- MCP: `mcp__dataforseo__business_data_business_listings_search` (required, paid ~3 credit) + `mcp__ScraplingServer__fetch` (optional fallback)
- Upstream: `init-project` (master.xlsx + project.config.json with `profiles: ["local-service", ...]`)
- Memory: `feedback_indexing_api_consent` (no autonomous GBP submit) + `feedback_hard_constraints` (.mcp.json byte-byte invariant)
