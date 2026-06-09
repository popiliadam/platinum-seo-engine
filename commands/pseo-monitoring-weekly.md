---
description: |
  Use when: kullanıcı "haftalık check", "weekly health", "haftalık monitoring", "weekly health report", "haftalık sağlık raporu" der ya da `/pseo-monitoring-weekly` çağırırsa.
  Also use when: Pazartesi 09:00 UTC cron-like trigger (skill scheduled "0 9 * * 1"); manager portfolio-overview öncesi tek-proje sağlık özeti istiyor; events.jsonl son 7 gün filter + drift-check output reuse + GSC week-over-week delta + budget burn rate aggregation gerekli.
  Do not use when: ay sonu rapor (`/pseo-monthly`), portföy genel rapor (`portfolio-overview` skill, ayrı), drift kontrol (`/pseo-driftcheck`), günlük check (skill scope dışı — bu skill rolling 7-day window).
argument-hint: "[project-slug] [--week-start YYYY-MM-DD] [--week-end YYYY-MM-DD]"
allowed-tools: Bash(jq:*), Bash(python3:*), Bash(date:*), Read
model: sonnet
---

# /pseo-monitoring-weekly — Weekly Health Check

> **Skill:** `skills/reporting/monitoring-weekly/SKILL.md` (Phase 12 W2 + Phase B Wave 3 inline orchestration, aktif). events.jsonl + drift-check output + GSC delta + budget burn 7-day rolling window aggregator → outputs/reports/{date}-monitoring-weekly.md (read-only, no master.xlsx WRITE, no MCP).

## 1. Aktif projeyi çöz

!`set -- $ARGUMENTS; if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; else PROJECT="${1:-$(jq -r '.active_project // empty' "$PSEO_WORKSPACE_ROOT/shared/active.json" 2>/dev/null)}"; if [ -z "$PROJECT" ]; then echo "NO_ACTIVE_PROJECT — once /pseo-active <slug>"; else WS_END="${3:-$(date -u +%Y-%m-%d)}"; WS_START="${2:-$(date -u -v-7d +%Y-%m-%d 2>/dev/null || date -u --date='7 days ago' +%Y-%m-%d)}"; echo "active=$PROJECT week=$WS_START..$WS_END"; fi; fi`

## 2. Skill chain

`skills/reporting/monitoring-weekly/SKILL.md` 8-step + 3 inline Python block (Phase B Wave 3 inline orchestration paterni, no subprocess):

- **Block 1:** Setup + drift-check `_state/reports/{latest}-consistency-report.json` read (DURUR #3 inline default fallback if missing)
- **Block 2:** events.jsonl 7-day filter + `shared/portfolio.json` read + per-project metrics aggregate (drift verdict + GSC anomaly + budget burn rate cost.credits/day vs project-config.budget_credits_per_day) + severity compute
- **Block 3:** Markdown render via `templates/reports/monitoring-weekly.template.md` (DURUR #4 inline fallback if missing) + `events_writer.append_audit` emit (event_kind=audit, audit_action=accessed, audit_target=reports:monitoring-weekly:{week_start})

Çıktı: `outputs/reports/{date}-monitoring-weekly.md` (~1700+ byte) + events.jsonl audit-row (no event_type per Section 6 ADR-020 disambiguation, append_audit convenience wrapper).

## 3. Çalıştırma notları

- **No MCP, no DFS, no master.xlsx WRITE** — strict read-only (Phase 9 reporting paterni 8 skill no-write invariant reuse).
- 5σ anomaly threshold hit ise CRITICAL severity report'a girer (DURUR #5 manager onayı Phase 14+ governance).
- Cron mode (`scheduled: 0 9 * * 1`): report-only, `requires_approval: false`, `safe_auto_execute: true` (HIGH confidence).
- Plugin agnostik: PSEO_PROJECT_ID env veya `$1` arg, slug literal yok.

## 4. Bağımlılıklar

- Skill: `skills/reporting/monitoring-weekly/SKILL.md` (Phase 12 W2, active)
- Scripts: `scripts/state/events_writer.py` (`append_audit` convenience wrapper) + `scripts/reporting/render_template.py` (string.Template $var substitution)
- Templates: `templates/reports/monitoring-weekly.template.md`
- Rules: `rules/events-writer.md` Section 4c (audit-only events, event_type YASAK per Section 6 ADR-020)
- Schemas: `schemas/events.schema.json` (audit if/then required: audit_action + audit_target + actor)
- project.config: `budget.credits_per_day` (burn rate baseline)
- Upstream: `governance/drift-check` (consistency-report.json) + `init-project` (`master.xlsx[gsc_performance]`)
