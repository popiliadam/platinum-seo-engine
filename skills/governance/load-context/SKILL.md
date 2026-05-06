---
name: load-context
description: |
  Use when: kullanıcı "fresh session başlat", "load context", "wakeup",
  "manager session aç", "/pseo-active" der ya da yeni session ilk
  promptu geliyor. Fresh manager session wakeup'ını codify eder; spec
  §13.2 + SESSION_PROTOCOL.md §2 7-step sequence'i executable yapar
  ve <15KB context budget verify eder.
  Also use when: phase gateway öncesi context refresh, fresh worker
  dispatch hazırlığı, manager handoff (önceki session bitti, yenisi
  başladı).
  Do not use when: dar scope worker dispatch (manager prompt yazma —
  WORKER_PROMPTS.md template), phase planning (yeni phase plan
  yazma — manager kararı), bug fix (debug). load-context read-only
  bootstrap aggregator; master.xlsx asla mutate edilmez.
version: "1.0"
status: active
category: governance
inputs:
  phase_id:
    type: string
    required: false
    default: "auto-detect"
    description: "Phase id (örn 'phase-13'). Default 'auto-detect': PHASE_STATUS.md 'Active Phase' satırından regex extract."
  max_kb:
    type: integer
    required: false
    default: 15
    description: "Toplam okunan dosya byte budget'ı KB cinsinden. Default 15 (spec §13.2 budget). Aşıldıysa AMBER + suggested trim."
outputs:
  - "outputs/reports/{date}-load-context.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md"
  - "init-project:docs/PHASE_STATUS.md"
  - "init-project:docs/OPEN_QUESTIONS.md"
  - "init-project:docs/DECISIONS.md"
  - "init-project:docs/REFERENCE_INDEX.md"
  - "init-project:docs/SESSION_PROTOCOL.md"
  - "init-project:docs/CONTEXT_LEDGER.md"
produces: []
triggers:
  manual: ["/pseo-active"]
  natural_language: |
    "fresh session başlat", "load context", "wakeup",
    "manager session aç", "session protocol başlat",
    "context yükle", "yeni session", "manager handoff"
  hooks: []
  scheduled: []
mcp_tools:
  required: []
  optional: []
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: HIGH
  requires_approval: false
  safe_auto_execute: true
---

# load-context — governance skill (Phase 13)

Read-only manager session wakeup aggregator. Codifies the 7-step
sequence from `docs/SESSION_PROTOCOL.md` §2 (mirroring spec §13.2)
into an executable governance flow:

1. Bootstrap prompt (user pastes; out of skill scope).
2. Spec §1 + §13 + §17 read (ONLY these three sections).
3. `docs/PHASE_STATUS.md` read.
4. `docs/OPEN_QUESTIONS.md` read.
5. `docs/DECISIONS.md` last 5 ADR read.
6. `docs/REFERENCE_INDEX.md` full read.
7. STOP — anything else only on demand.

The skill produces a single markdown report summarizing what was
loaded, the active phase auto-detected from PHASE_STATUS, the byte
budget (target <15KB per spec §13.2), and the per-file size breakdown
so the manager can confirm the wakeup was within budget.

**Read-only contract:** `master.xlsx` MUST NOT be opened. Skill
writes only to `outputs/reports/{date}-load-context.md` and
`_state/events.jsonl`.

## Foundational Principles (3-layer enforce)

1. **Truth-verifiable** — every "active phase" / "last 5 ADR" /
   "byte count" claim derives from a parsed file (regex anchor
   match), not from a memory cache. If PHASE_STATUS does not say
   "Active Phase: Phase 13", the report does not say it.
2. **Profile-aware (5-enum)** — the budget default (15KB) mirrors
   the spec §13.2 manager-session profile; the `max_kb` input
   permits per-profile override (e.g. `enterprise` profile may run
   at 20KB if compliance docs grew).
3. **AI suistimal yasağı** — the skill MUST NOT call any LLM tool
   to "summarize" the loaded files. Section extraction is regex
   anchor match; ADR extraction is `## ADR-NNN` heading match.
   Summarization is the manager's judgment call. `mcp_tools=[]`
   enforces.

## DURUR (no fall-back) conditions

1. **DURUR #1 — spec design.md missing OR §1/§13/§17 anchors not
   found** → AMBER exit. The 3-section bounded read is the cheapest
   accurate authority for wakeup; without it the manager cannot
   ground decisions. Falling back to "read everything" would blow
   the byte budget.
2. **DURUR #2 — total byte budget exceeded** (sum of all 7 reads
   > `max_kb * 1024`) → AMBER + suggested per-file trim
   (sorted descending by size). Never silently truncate; surface
   the budget violation so the manager either accepts the bigger
   payload or tightens the docs.

## Inputs (frontmatter contract)

| Name        | Type    | Default       | Notes                                                                                  |
|-------------|---------|---------------|----------------------------------------------------------------------------------------|
| `phase_id`  | string  | `auto-detect` | Auto-extracts from PHASE_STATUS.md "Active Phase" line; explicit override allowed.     |
| `max_kb`    | integer | `15`          | Byte budget cap (KB). Default mirrors spec §13.2 manager wakeup target.                |

## Outputs (artifacts produced)

- `outputs/reports/{date}-load-context.md` — auto-detected active
  phase + byte budget summary + 7-step status checklist.
- `_state/events.jsonl` — single `event_kind=audit` row
  (`audit_action="accessed"`, `audit_target="session:wakeup-codify"`,
  `actor="agent:load-context"`).

## 9-Step Body Protocol

### Step 1 — `extract_spec_sections_1_13_17` (DURUR #1)

```python
# Standalone-executable entrypoint (Phase 14 W3-W1 helper exec compliance):
# imports + entrypoint variables init for downstream concat blocks.
import os
import sys
import re
import json
from pathlib import Path

# sys.path insert so `scripts.*` packages resolve under subprocess exec.
sys.path.insert(0, os.getcwd())

# Entrypoint variables (placeholder defaults — orchestrator overrides at runtime)
phase_id = "auto-detect"
max_kb = 15
project_id = "drifttest"

spec_path = Path("docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md")
phase_status_path = Path("docs/PHASE_STATUS.md")
open_questions_path = Path("docs/OPEN_QUESTIONS.md")
decisions_path = Path("docs/DECISIONS.md")
reference_index_path = Path("docs/REFERENCE_INDEX.md")
session_protocol_path = Path("docs/SESSION_PROTOCOL.md")

spec = spec_path.read_text(encoding="utf-8")
def _section(idx: int) -> str:
    pat = re.compile(rf"^## {idx}\.[^\n]*\n(.*?)(?=^## \d+\.)", re.MULTILINE | re.DOTALL)
    m = pat.search(spec)
    if not m:
        raise SystemExit(f"DURUR #1: spec §{idx} anchor not found")
    return m.group(0)
section_1 = _section(1)
section_13 = _section(13)
section_17 = _section(17)
spec_bytes = sum(len(s.encode("utf-8")) for s in (section_1, section_13, section_17))
assert spec_bytes < 10_000, f"spec sections grew unexpectedly: {spec_bytes}B"
```

Each section is bounded by the next `## N.` heading. Anchor
regex `^## \d+\.` is the canonical extractor used by spec-aware
tooling.

### Step 2 — `parse_phase_status`

```python
phase_status = phase_status_path.read_text(encoding="utf-8")
active_match = re.search(r"^\*\*Active Phase:\*\*\s*([^\n]+)", phase_status, re.MULTILINE)
active_phase = active_match.group(1).strip() if active_match else "<unknown>"
blockers_match = re.search(r"^### Blockers\n(.*?)(?=^##|\Z)", phase_status, re.MULTILINE | re.DOTALL)
blockers = blockers_match.group(1).strip() if blockers_match else ""
```

Active phase comes from the canonical `**Active Phase:**` markdown
bold line; blockers come from the `### Blockers` section.

### Step 3 — `read_open_questions`

```python
open_q = open_questions_path.read_text(encoding="utf-8")
# Extract Q-XX-NN entries, count Phase 13+ candidates
q_entries = re.findall(r"^### (Q-[A-Z]+-\d+)", open_q, re.MULTILINE)
```

Q-NN-MM format (e.g. `Q-CR-02`, `Q-CD-01`). Count per category for
the report.

### Step 4 — `read_last_5_adr`

```python
decisions = decisions_path.read_text(encoding="utf-8")
# Anchor: "## ADR-NNN"
adr_anchors = list(re.finditer(r"^## ADR-(\d+)", decisions, re.MULTILINE))
last_5_starts = [m.start() for m in adr_anchors[-5:]]
# Slice from first of last-5 to end
adr_block = decisions[last_5_starts[0]:] if last_5_starts else ""
```

The 5 most recent ADRs are the "what was decided?" surface a fresh
session needs. Older ADRs live in `DECISIONS_ARCHIVE.md` (per
ADR-011 rotation rule).

### Step 5 — `read_reference_index`

```python
ref_index = reference_index_path.read_text(encoding="utf-8")
# Full read: ~3KB, well under budget
```

The Q&A "where to look?" index is small enough to read in full.

### Step 6 — `verify_session_protocol_match`

```python
session_protocol = session_protocol_path.read_text(encoding="utf-8")
# Count the numbered 7-step sequence in §2
step_lines = re.findall(r"^\d\.\s", session_protocol, re.MULTILINE)
assert len(step_lines) >= 7, (
    f"SESSION_PROTOCOL §2 wakeup sequence drifted: expected ≥7 numbered "
    f"steps, found {len(step_lines)}"
)
```

The 7-step sequence is the contract; if SESSION_PROTOCOL drifts to
6 or 8 steps the wakeup contract is broken and the report flags it.

### Step 7 — `verify_byte_budget` (DURUR #2)

```python
total = (spec_bytes + len(phase_status.encode("utf-8"))
         + len(open_q.encode("utf-8")) + len(adr_block.encode("utf-8"))
         + len(ref_index.encode("utf-8")))
budget_bytes = max_kb * 1024
verdict = "GREEN" if total <= budget_bytes else "AMBER"
if total > budget_bytes:
    # Surface per-file sorted desc — manager picks the trim target
    sizes = sorted([
        ("spec §1+§13+§17", spec_bytes),
        ("PHASE_STATUS.md", len(phase_status.encode("utf-8"))),
        ("OPEN_QUESTIONS.md", len(open_q.encode("utf-8"))),
        ("DECISIONS.md last 5 ADR", len(adr_block.encode("utf-8"))),
        ("REFERENCE_INDEX.md", len(ref_index.encode("utf-8"))),
    ], key=lambda kv: -kv[1])
```

Budget verdict is reported, never silently truncated.

### Step 8 — `render_report`

Write `outputs/reports/{date}-load-context.md`:

- **Active phase** — auto-detected (PHASE_STATUS).
- **Blockers** — PHASE_STATUS `### Blockers` section.
- **Open questions** — count by Q-XX prefix.
- **Last 5 ADR** — IDs + titles.
- **Byte budget** — total / cap / verdict + per-file sizes.
- **7-step status** — checklist of which steps loaded successfully.

### Step 9 — `emit_audit_event`

```python
from scripts.state import events_writer
# Documented invocation (orchestrator runs at workflow time):
# events_writer.append_audit(
#     project_id=project_id,
#     audit_action="accessed",
#     audit_target="session:wakeup-codify",
#     actor="agent:load-context",
#     notes=f"phase={active_phase} bytes={total} verdict={verdict}",
# )
audit_payload = {
    "event_kind": "audit",
    "audit_action": "accessed",
    "audit_target": "session:wakeup-codify",
    "actor": "agent:load-context",
    "notes": f"phase={active_phase} bytes={total} verdict={verdict}",
}
```

`event_kind=audit` requires `audit_action + audit_target + actor`
triple per `events.schema.json` allOf. `event_type` (WORK-only enum)
is NOT used — schema-first override (lesson 31+34) routes governance
signals to audit kind.

## Master.xlsx WRITE forbidden

load-context MUST NOT call `transaction.append`, `transaction.update`,
`transaction.delete`, or `wb.save`. It does not open `master.xlsx` —
the wakeup operates on `docs/` exclusively. The test suite enforces
this by regex grep over the production prose.

## Why §1 + §13 + §17 only (not the full spec)

The spec is 68KB. Reading it whole would blow the 15KB budget on
the first file. §1 (Vision) anchors the WHY, §13 (Manager Session
Protocol) anchors the HOW, §17 (Phase Roadmap) anchors the WHERE
WE ARE. These three sections sum to <10KB typical and answer 95%
of fresh-session questions. The other sections are demand-loaded
when the manager identifies a specific need.

## Why "auto-detect" phase

Hardcoding `phase-13` here would create the same drift class
schema-validate exists to surface (manager finding F-13.1). Auto-
detection from PHASE_STATUS lets this skill survive Phase 14, 15,
... without edits.

## Cross-references

- Schemas: `schemas/events.schema.json` (audit branch).
- Cross-modules: `scripts/state/events_writer.py` (audit append),
  `scripts/reporting/render_template.py` (report render).
- Tests: `tests/skills/governance/test_load_context.py`.
- Sibling governance skills: `schema-validate` (schema drift),
  `glossary-audit` (term drift), `drift-check` (master.xlsx
  invariants).
