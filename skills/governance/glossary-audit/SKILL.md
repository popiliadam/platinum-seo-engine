---
name: glossary-audit
description: |
  Use when: kullanıcı "glossary audit", "term drift", "sözlük kontrol",
  "glossary missing", "/pseo-driftcheck" der ya da Disiplin #8 (Glossary
  Discipline) enforcement gerekir. GLOSSARY.md drift detect; cross-ref
  docs/REFERENCE_INDEX.md ve spec §20; reverse-lookup orphan/missing
  term'leri skills/**/SKILL.md'de denetler.
  Also use when: yeni skill eklendi (terim katalog tutarlılığı), spec
  §20 güncellendi (terim eklendi/çıkarıldı), CI quality gate, fresh
  session öncesi glossary sanity check.
  Do not use when: schema drift (schema-validate'in işi),
  master.xlsx invariants (drift-check'in işi). glossary-audit
  AMBER-only warn skill — RED kararı vermez, missing term ya da
  orphan term'i sadece liste eder; insan triage'a gerek var.
version: "1.0"
status: wip
category: governance
inputs:
  glossary_path:
    type: string
    required: false
    default: "docs/GLOSSARY.md"
    description: "Glossary kaynağı. Default docs/GLOSSARY.md (alfabetik liste)."
  spec_path:
    type: string
    required: false
    default: "docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md"
    description: "Spec design.md path. §20 (Glossary) section'ı extract için."
outputs:
  - "outputs/reports/{date}-glossary-audit.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:docs/GLOSSARY.md"
  - "init-project:docs/REFERENCE_INDEX.md"
  - "init-project:docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md"
  - "init-project:skills/**/SKILL.md"
produces: []
triggers:
  manual: ["/pseo-driftcheck"]
  natural_language: |
    "glossary audit", "sözlük kontrol", "term drift",
    "glossary missing", "orphan term", "glossary discipline",
    "terim eksik", "terim drift kontrol"
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

# glossary-audit — governance skill (Phase 13)

Read-only term catalog audit. Loads `docs/GLOSSARY.md` (alphabetical
term registry per Disiplin #8), extracts spec §20 bold-marked terms,
verifies `docs/REFERENCE_INDEX.md` glossary anchor integrity, and
performs reverse-lookup over `skills/**/SKILL.md` to surface two drift
classes:

- **Orphan terms** — listed in GLOSSARY.md but never referenced in any
  skill body.
- **Missing terms** — used in a skill body (Title Case, capitalized
  noun) but absent from GLOSSARY.md.

Both classes surface as **AMBER warn** entries (NOT RED). RED-style
hard-failure is reserved for schema-validate and drift-check.

**Read-only contract:** `master.xlsx` MUST NOT be opened. Skill writes
only to `outputs/reports/{date}-glossary-audit.md` and
`_state/events.jsonl`.

## Foundational Principles (3-layer enforce)

1. **Truth-verifiable** — every "missing term" claim cites the file +
   line number where the term was used; every "orphan term" claim
   cites GLOSSARY.md line. No prose-fabricated drift claims.
2. **Profile-aware (5-enum)** — defensive whitelist (acronyms common
   to all profiles) prevents `solo` profile false positives without
   exempting `enterprise` profile from terminology rigor.
3. **AI suistimal yasağı** — the skill MUST NOT call any LLM tool to
   "judge" whether a term is glossary-worthy. Terminology curation is
   human authority (Süleyman + Disiplin #8). `mcp_tools=[]` enforces.

## DURUR (no fall-back) conditions

1. **DURUR #1 — `docs/GLOSSARY.md` missing or unparseable** → AMBER
   exit. Glossary is the source of truth; without it no audit is
   possible. The skill DOES NOT fall back to spec §20 (that would
   mask Disiplin #8 violation).
2. **DURUR #2 — orphan term detected** → AMBER warn list (NOT RED).
   A term in GLOSSARY but unused in any skill could be (a) genuinely
   stale, (b) used in docs/spec but not skills (legitimate),
   (c) about-to-be-used in a Phase 13+ skill (legitimate). Human
   triage determines.
3. **DURUR #3 — missing term detected** → AMBER warn list (NOT RED).
   A capitalized term used in a skill body but absent from GLOSSARY
   could be (a) Disiplin #8 violation requiring catalog add, (b) a
   common acronym (whitelisted), (c) a proper noun (URL, brand name).
   Human triage determines.

## Inputs (frontmatter contract)

| Name             | Type   | Default                                                                  | Notes                                          |
|------------------|--------|--------------------------------------------------------------------------|------------------------------------------------|
| `glossary_path`  | string | `docs/GLOSSARY.md`                                                       | Alphabetical term registry root.               |
| `spec_path`      | string | `docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md`       | spec §20 cross-ref source for term extract.    |

## Outputs (artifacts produced)

- `outputs/reports/{date}-glossary-audit.md` — orphan list +
  missing list + verdict.
- `_state/events.jsonl` — single `event_kind=audit` row
  (`audit_action="accessed"`, `audit_target="docs:glossary-audit"`,
  `actor="agent:glossary-audit"`).

## 8-Step Body Protocol

### Step 1 — `parse_glossary` (DURUR #1)

```python
glossary_text = Path(glossary_path).read_text(encoding="utf-8")
# Pattern: "- **TermName** — definition"
import re
term_pattern = re.compile(r"^- \*\*([^\*]+)\*\*", re.MULTILINE)
glossary_terms = set(term_pattern.findall(glossary_text))
if not glossary_terms:
    raise SystemExit("DURUR #1: GLOSSARY.md unparseable or empty")
```

Glossary follows the alphabetical bullet pattern documented in
Disiplin #8. The skill counts ~20 terms typical (manager kanıt #12 =
23 lines including header/separator).

### Step 2 — `extract_spec_section_20`

```python
spec_text = Path(spec_path).read_text(encoding="utf-8")
# Find "## 20." section bounded by next "## " header
section_re = re.compile(r"^## 20\.[^\n]*\n(.*?)(?=^## \d+\.)", re.MULTILINE | re.DOTALL)
m = section_re.search(spec_text)
section_20 = m.group(1) if m else ""
spec_term_pattern = re.compile(r"^- \*\*([A-Z][^\*]+)\*\*", re.MULTILINE)
spec_terms = set(spec_term_pattern.findall(section_20))
```

Spec §20 declares the canonical term set. GLOSSARY.md should be a
superset (Phase 0 bootstrap added some + Phase 5+ adds more).

### Step 3 — `verify_reference_index_anchor`

```python
ref_index_text = (Path("docs") / "REFERENCE_INDEX.md").read_text(encoding="utf-8")
# Heading-link integrity: REFERENCE_INDEX should mention "GLOSSARY.md"
assert "GLOSSARY.md" in ref_index_text, (
    "REFERENCE_INDEX missing glossary anchor"
)
```

REFERENCE_INDEX is the Q&A "where to look for X?" router; the
glossary anchor MUST be present (link integrity).

### Step 4 — `scan_skill_bodies_for_terms`

```python
skill_terms_used: dict[str, list[Path]] = {}
for skill_md in (REPO_ROOT / "skills").rglob("SKILL.md"):
    text = skill_md.read_text(encoding="utf-8")
    # Strip frontmatter to focus on body prose
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    body = text[m.end():] if m else text
    # Extract Title Case 2+ capitalized tokens (heuristic)
    candidates = re.findall(r"\b([A-Z][A-Za-z]{1,}(?:\s+[A-Z][A-Za-z]{1,})*)\b", body)
    for c in candidates:
        skill_terms_used.setdefault(c, []).append(skill_md)
```

Heuristic: capitalized 2+ token spans are candidates for glossary
terms. False positives are filtered by the whitelist below.

### Step 5 — `detect_orphan_terms` (DURUR #2)

```python
used_set = set(skill_terms_used.keys())
orphan_terms = sorted(glossary_terms - used_set)
# Each orphan_term: in GLOSSARY but no skill mentions it.
```

Orphan terms surface as AMBER warn list (NOT RED). Manager triages:
keep (used in docs/spec only) vs. remove (genuinely stale).

### Step 6 — `detect_missing_terms_with_whitelist` (DURUR #3)

```python
ACRONYM_WHITELIST = frozenset({
    "JSON", "URL", "API", "HTML", "CSS", "SEO", "MCP", "GSC",
    "DFS", "AIO", "FAQ", "JSON-LD", "XML", "HTTP", "CSV", "CLI",
    "CI", "ADR", "UTC", "SHA", "SHA-256", "UUID", "REST", "TLS",
    # F/D/M rule prefixes - they are rule IDs, not glossary terms
    "F-01", "F-02", "F-03",  # ... the suite
    # R-XX rule prefixes
})
def _is_rule_id(t: str) -> bool:
    return bool(re.match(r"^[FDMR]-\d+$", t))
missing_terms = sorted(
    t for t in skill_terms_used
    if t not in glossary_terms
    and t not in ACRONYM_WHITELIST
    and not _is_rule_id(t)
)
```

Defensive whitelist guards against false positives from common
acronyms and rule IDs (R-XX, F-XX, D-XX, M-XX). Without the whitelist
every skill body would report dozens of false positives. The
whitelist is conservative; new acronyms must be added explicitly.

### Step 7 — `render_report`

Write `outputs/reports/{date}-glossary-audit.md`:

- **Glossary terms** — count + list.
- **Spec §20 terms** — count + diff vs glossary (extras / missing).
- **Skills using terms** — count of distinct candidates.
- **Orphan terms** — DURUR #2 list (AMBER).
- **Missing terms** — DURUR #3 list with first-occurrence
  file path (AMBER).
- **Verdict** — GREEN if both lists empty; AMBER otherwise.

### Step 8 — `emit_audit_event`

```python
from scripts.state import events_writer
events_writer.append_audit(
    project_id=project_id,
    audit_action="accessed",
    audit_target="docs:glossary-audit",
    actor="agent:glossary-audit",
    notes=f"orphans={len(orphan_terms)} missing={len(missing_terms)}",
)
```

`event_kind=audit` requires the `audit_action + audit_target + actor`
triple per `events.schema.json` allOf. `event_type` (WORK-only enum)
is NOT used — schema-first override (lesson 31+34) routes governance
signals to audit, never to work.

## Master.xlsx WRITE forbidden

glossary-audit MUST NOT call `transaction.append`, `transaction.update`,
`transaction.delete`, or `wb.save`. It does not open `master.xlsx` —
the audit operates on `docs/` and `skills/` exclusively. The test
suite enforces this by regex grep over the production prose.

## Why orphan + missing surface as AMBER (not RED)

Disiplin #8 (Glossary Discipline) is a curation discipline, not a
hard schema rule. Both drift classes are signals for human triage:

- An orphan term may be used in `docs/` but not in any skill yet
  (Phase 13 future skill will reference it).
- A missing term may be a proper noun the skill body legitimately
  introduces.

RED would force an unnecessary halt; AMBER surfaces the signal,
manager triages. This split is symmetric with `drift-check`'s
F-15 manual-triage routing.

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json` (link to body
  parser), `schemas/events.schema.json` (audit branch).
- Cross-modules: `scripts/state/events_writer.py` (audit append),
  `scripts/reporting/render_template.py` (report render).
- Tests: `tests/skills/governance/test_glossary_audit.py`.
- Sibling governance skills: `schema-validate` (schema drift),
  `drift-check` (master.xlsx invariants), `load-context`
  (session wakeup).
