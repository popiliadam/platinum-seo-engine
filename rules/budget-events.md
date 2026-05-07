---
name: Budget Events
status: enforced
applies_to: [workspace, skill]
spec_section: "§16.8 + ADR-016 + ADR-029"
related: [append-only-state, events-writer, schema-first]
since: "2026-05-06"
supersedes: none
---

# Budget Events — cost.credits Canonical Field

The DataForSEO daily budget guard (`scripts/budget/check_budget.py`,
spec §16.8) sums credits from PROVENANCE events whose
`source.kind == "dataforseo_mcp"`. The summed field is **`cost.credits`**
(per `schemas/events.schema.json`, ADR-017 schema-first naming +
ADR-029 per-run estimated_credits convention).

## Rules

### R-budget-1 — Skill orchestrator writes the budget event
Only the skill orchestrator (the inline Python block in `SKILL.md`,
e.g. `skills/ingestion/dfs-pull/SKILL.md` Step 9) calls
`events_writer.append_provenance(..., cost={...})`. The pure
transform module (`scripts/ingestion/dfs_pull.py`) MUST NOT write
events — it returns staging payloads only (Phase 6 D-003).

### R-budget-2 — `cost` payload shape
```python
cost={
    "provider": "dataforseo",        # ADR-017 source-of-truth
    "credits": float(estimate),      # the field check_budget reads
    "budget_key": "project.config.dataforseo.budget_credits_per_day",
}
```
Do NOT write `source.credits_used` or any alternative field name.
`check_budget._extract_credits()` only inspects `cost.credits`.

### R-budget-3 — Estimated, not actual
Per ADR-029, `credits` is the per-run estimate (e.g. `len(keywords) *
1.5` for keyword_overview + search_volume), not the post-call API
charge. Drift between estimate and actual is acceptable for guard
purposes; the guard prevents over-spend, not exact accounting.

### R-budget-4 — Round-trip locked by tests
`tests/budget/test_budget_accounting.py` runs the full chain
(append_provenance → events.jsonl → check_budget) and asserts a
non-zero `used_24h`. Any future change that breaks the writer→reader
contract fails this test.

## History

- v1.1 Wave 2 (2026-05-06) — codify; Q-PHASE15-BUDGET-COST-01
  SELF-RESOLVED. Original audit assumed `dfs_pull.py` orchestrates
  the event write; Phase 6 D-003 split made it a pure transform.
