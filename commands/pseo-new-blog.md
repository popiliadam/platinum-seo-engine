---
description: |
  Use when: kullanıcı "yeni blog yaz", "blog üret", "new content", "pillar/cluster yaz", "blog draft", "makale üret" der ya da `/pseo-new-blog` çağırırsa.
  Also use when: aktif projede `master.xlsx[new_content_plan]` sheet'inde bekleyen NCP satırı var; pillar content production tetiklenmek isteniyor; Foundational Principles 3-katman enforce + R-71..R-76 image discipline gerekli.
  Do not use when: mevcut blog revize gerekiyorsa (`revise-content` skill, ayrı), FAQ block ekleme (`faq-optimization` skill, ayrı), content remediation/decay sunset (`content-remediation` skill, ayrı), image-only generation (`generate-images` skill direkt çağrılır).
argument-hint: "<project-slug> <new-content-plan-id> [--mode draft|publish]"
allowed-tools: Bash(jq:*), Bash(python3:*), Read
model: sonnet
---

# /pseo-new-blog — Production Content Generation

> **Skill:** `skills/production/new-blog/SKILL.md` (Phase 11 W1, aktif). NCP satırı → SERP analiz → 5 template render → JSON-LD @graph 5 entity → Foundational Principles 3-layer enforce → outputs/blog/{slug}/{article.md,html,jsonld} + meta-tags + upload-instructions + onay gate.

## 1. Aktif projeyi çöz

`$1` zorunlu slug; eksikse durur. NCP id `$2` zorunlu.

!`if [ -z "$PSEO_WORKSPACE_ROOT" ]; then echo "ERROR: PSEO_WORKSPACE_ROOT env var set edilmemiş"; elif [ -z "$1" ]; then echo "MISSING_SLUG: usage /pseo-new-blog <project-slug> <new-content-plan-id> [--mode draft|publish]"; elif [ -z "$2" ]; then echo "MISSING_NCP_ID: <new-content-plan-id> argümanı zorunlu"; else echo "active=$1 ncp_id=$2 mode=${3:---mode=draft}"; fi`

## 2. Skill chain

`skills/production/new-blog/SKILL.md` 8-step protokol koşar:

1. master.xlsx[new_content_plan] satır oku (id=$2)
2. project-config consume (brand_identity + content_settings + profile)
3. R-71..R-76 image discipline enforce (8K ultra realistic, nano-banana model R-72 default, hero image R-73, picture LCP, format cascade webp+jpg+avif R-76, alt text R-74)
4. Content generation: markdown + HTML + JSON-LD @graph (5 entity: Article + Person/Organization + WebPage + BreadcrumbList + FAQPage)
5. Foundational Principles 3-layer enforce (Truth-Verifiable + Profile-Aware + AI-Suistimal)
6. Output write — `outputs/blog/{slug}/article.{md,html,jsonld}` + `meta-tags.json` + `upload-instructions.md`
7. events.jsonl append — `event_kind=work + event_type=content_new + task_id=T-XXXXX` (URL-bearing pillar pattern: url+url_normalized+after+pillar mandatory per events.schema)
8. Onay gate: `awaiting_approval` (workflow-run.schema)

DURUR (6 sentinel inline): NCP id bulunamadı / mode enum dışı / project-config eksik / image generation FAIL / R-71..R-76 ihlali / Foundational Principle violation.

## 3. Çalıştırma notları

- `--mode publish` Süleyman onayı sonrası master.xlsx[new_content_plan].lifecycle_status `PLANNED → DONE` update (`scripts/excel/transaction.py` update).
- `--mode draft` (default) sadece outputs yaz, master.xlsx update yok; review sonrası ayrı `--mode publish` çağrılır.
- Hero image generation paid MCP (higgsfield ~1 credit/image); budget pre-flight `scripts/budget/check_budget.py`.
- Workflow-run state machine: `_state/workflows/{run_id}.json`.

## 4. Bağımlılıklar

- Skill: `skills/production/new-blog/SKILL.md` (Phase 11 W1, active)
- Scripts: `scripts/state/events_writer.py` (`append_work`) + `scripts/state/workflow_runner.py` + `scripts/excel/transaction.py` + `scripts/reporting/render_template.py` + `scripts/budget/check_budget.py`
- Templates: `templates/content/{new-blog.template.md, new-blog.template.html, faq-block.template.html, upload-instructions.template.md}`
- Rules: `rules/content-quality.md` + `rules/content-html-discipline.md` + `rules/content-seo-discipline.md` + `rules/content-eeat-discipline.md` + `rules/content-llm-discipline.md` + `rules/content-update-discipline.md`
- Schemas: `schemas/master-excel.schema.json#new_content_plan` + `schemas/events.schema.json` (URL-bearing work event content_new branch)
- MCP: `mcp__higgsfield__generate_image` (required) + `mcp__higgsfield__job_status` (optional polling) + `mcp__gsc__search_analytics` (SERP delta) + `mcp__dataforseo__serp_organic_live_advanced` (SERP analiz)
- project.config: `brand_identity` + `content_settings` + `profile` (local-service vs ymyl)
