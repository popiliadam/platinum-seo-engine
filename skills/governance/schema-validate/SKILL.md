---
name: schema-validate
description: |
  Use when: kullanıcı "schema validate", "schema doğrula", "frontmatter
  kontrol", "draft7 audit", "/pseo-driftcheck" der ya da phase gateway
  öncesi quality gate fired. JSON Schema Draft7 validation across all
  schemas under schemas/, cross-sheet-invariants 20 rules
  (F-01..F-15 + D-01..D-03 + M-01..M-02), and SKILL.md frontmatter
  compliance under skills/**/.
  Also use when: yeni schema eklendi (additive bump), frontmatter
  drift şüphesi, CI quality gate, drift-check öncesi pre-flight.
  Do not use when: master.xlsx invariants (drift-check'in işi),
  glossary terim drift'i (glossary-audit'in işi), build error
  (build-error-resolver). schema-validate read-only audit, master.xlsx
  asla mutate edilmez.
version: "1.0"
status: wip
category: governance
inputs:
  schema_path:
    type: string
    required: false
    default: "schemas/"
    description: "Schema dosyalarının kök dizini. Default schemas/. Runtime glob ile *.schema.json enumerate edilir; hardcoded count YOK."
  strict:
    type: boolean
    required: false
    default: true
    description: "True ise herhangi FAIL exit 1; False ise AMBER + report-only. Default true (CI gate semantiği)."
outputs:
  - "outputs/reports/{date}-schema-validate.md"
  - "_state/events.jsonl"
consumes:
  - "init-project:schemas/*.schema.json"
  - "init-project:schemas/cross-sheet-invariants.json"
  - "init-project:skills/**/SKILL.md"
produces: []
triggers:
  manual: ["/pseo-driftcheck"]
  natural_language: |
    "schema validate", "schema doğrula", "frontmatter kontrol",
    "draft7 audit", "schema drift", "schema audit",
    "frontmatter compile", "skill frontmatter check"
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

# schema-validate — governance skill (Phase 13)

Read-only schema audit. Enumerate all `schemas/*.schema.json` via runtime
`glob()` (NOT hardcoded count — count drift is the failure mode this skill
is designed to surface), validate each as a well-formed JSON Schema
Draft7 meta-schema, validate the cross-sheet-invariants instance
document's `rules[]` array (20 rule registry, key=`rules` per
S3.5 instance pivot), and validate every `skills/**/SKILL.md`
frontmatter block against `schemas/skill-frontmatter.schema.json`.

**Read-only contract:** `master.xlsx` MUST NOT be opened, mutated, or
referenced from `outputs[]`. The skill writes only to
`outputs/reports/{date}-schema-validate.md` (markdown report) and
`_state/events.jsonl` (single `event_kind=audit` row).

## Foundational Principles (3-layer enforce)

This skill operates under the three Foundational Principles
(rules/foundational-principles.md):

1. **Truth-verifiable** — every assertion in the report MUST trace back
   to a schema authority (the schema file itself or its
   `Draft7Validator.iter_errors` output). No prose fabrication.
2. **Profile-aware (5-enum)** — the skill respects the project profile
   enum (`solo` / `agency` / `inhouse` / `enterprise` / `pilot`). Strict
   mode default mirrors the agency/enterprise CI gate semantics.
3. **AI suistimal yasağı** — the skill MUST NOT call any LLM tool to
   "explain" a schema error away. Failures surface as-is in the report;
   human judgment owns repair. `mcp_tools=[]` enforces this at the
   contract level.

## DURUR (no fall-back) conditions

1. **DURUR #1 — `import jsonschema` smoke fails** → AMBER + exit 1.
   The skill cannot proceed without the validator library; this is
   an environment defect, not a data defect.
2. **DURUR #2 — `schemas/` directory missing** → exit 1. The skill
   uses a runtime `glob('schemas/*.schema.json')` enumerate (NOT a
   hardcoded count) precisely so that schema additions/removals do
   NOT silently change behaviour. Missing root directory is fatal.
3. **DURUR #3 — strict=true AND any FAIL** → exit 1; non-strict mode
   downgrades to AMBER + report-only (CI gate skipped, manager review
   required). Never silently PASS on FAIL.

## Inputs (frontmatter contract)

| Name           | Type    | Default     | Notes                                                                            |
|----------------|---------|-------------|----------------------------------------------------------------------------------|
| `schema_path`  | string  | `schemas/`  | Root dir for runtime glob enumerate. NOT a count parameter.                      |
| `strict`       | boolean | `true`      | True → any FAIL exits 1. False → AMBER + report.                                 |

## Outputs (artifacts produced)

- `outputs/reports/{date}-schema-validate.md` — human-readable report
  enumerating every schema validated, every cross-sheet-invariants
  rule structurally checked, every SKILL.md frontmatter result.
- `_state/events.jsonl` — single `event_kind=audit` entry
  (`audit_action="accessed"`, `audit_target="schemas:bulk-validate"`,
  `actor="agent:schema-validate"`).

## 8-Step Body Protocol

### Step 1 — `validator_smoke` (DURUR #1)

```python
try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError as exc:
    raise SystemExit(f"DURUR #1: jsonschema unavailable: {exc}")
```

`Draft7Validator.check_schema(schema)` is the meta-schema gate; without
it the skill cannot validate anything.

### Step 2 — `enumerate_schemas` (runtime glob, NOT hardcoded count)

```python
from pathlib import Path
schema_root = Path(schema_path)
if not schema_root.exists():
    raise SystemExit(f"DURUR #2: {schema_root} missing")
schema_files = sorted(schema_root.glob("*.schema.json"))
# IMPORTANT: count is computed at runtime; F-13.1 manager finding —
# brief authority claim "19 schema" diverged from filesystem 18.
# Schema authority kazanır (lesson 31+34 schema-first override).
```

Hardcoded counts in this skill body or description WOULD reintroduce
the very drift this skill exists to detect. Count is reported to the
report markdown but never asserted as a constant.

### Step 3 — `meta_validate_each_schema`

```python
for sp in schema_files:
    schema = json.loads(sp.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)  # raises SchemaError on bad meta
```

Each `.schema.json` file must itself be a valid Draft7 meta-schema.
This catches `$ref` typos, malformed `enum`, unrecognized keywords.

### Step 4 — `validate_cross_sheet_invariants_rules`

```python
csi = json.loads((schema_root / "cross-sheet-invariants.json").read_text("utf-8"))
rules = csi["rules"]   # KEY = "rules" — NOT "invariants"
assert isinstance(rules, list)
assert len(rules) >= 1
required_per_rule = {"id", "severity", "category", "rule"}
for entry in rules:
    missing = required_per_rule - set(entry.keys())
    assert not missing, f"rule {entry.get('id', '?')} missing keys: {missing}"
```

The cross-sheet-invariants instance document carries 20 rules
(F-01..F-15 + D-01..D-03 + M-01..M-02 = 20) per spec §7. The top-level
key is `rules` per S3.5 pivot — NOT `invariants`. This skill explicitly
exercises that key so a memory-drift typo (the natural mistake) is
caught at the audit step, not silently masked.

### Step 5 — `validate_skill_frontmatter_compliance`

```python
fm_schema = json.loads((schema_root / "skill-frontmatter.schema.json").read_text("utf-8"))
fm_validator = Draft7Validator(fm_schema)
skill_root = REPO_ROOT / "skills"
for skill_md in skill_root.rglob("SKILL.md"):
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        # FAIL: frontmatter block missing
        ...
    fm = yaml.safe_load(m.group(1))
    errors = sorted(fm_validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    # accumulate per-file
```

Every `skills/**/SKILL.md` frontmatter is Draft7-validated against
the canonical `skill-frontmatter.schema.json`. The 13 root properties
declared there (name, description, version, status, category, inputs,
outputs, triggers, consumes, produces, mcp_tools, budget, autonomy)
are the contract surface.

### Step 6 — `aggregate_verdict` (DURUR #3)

```python
overall = "GREEN" if not failures else ("RED" if strict else "AMBER")
if strict and failures:
    raise SystemExit(1)   # DURUR #3
```

Strict + FAIL → exit 1. Non-strict + FAIL → AMBER report, no exit.
Never silently PASS on FAIL.

### Step 7 — `render_report`

Write `outputs/reports/{date}-schema-validate.md` with sections:

- **Schemas** — count (runtime), per-file PASS/FAIL with first 3 errors.
- **Cross-Sheet Invariants** — `rules` array length, per-rule structural
  PASS/FAIL.
- **SKILL.md Frontmatter** — count (runtime), per-file PASS/FAIL with
  Draft7 errors.
- **Summary** — overall verdict (GREEN/AMBER/RED).

### Step 8 — `emit_audit_event`

```python
from scripts.state import events_writer
events_writer.append_audit(
    project_id=project_id,
    audit_action="accessed",
    audit_target="schemas:bulk-validate",
    actor="agent:schema-validate",
    notes=f"verdict={overall} schemas={len(schema_files)} skills={len(skill_files)}",
)
```

The audit event_kind requires the `audit_action + audit_target + actor`
triple per `events.schema.json` allOf rule. `event_type` (the WORK-only
closed 10-value enum) is NOT used here; that field is reserved for
work-tracking events (DONE protocol §21.4) and the schema-first
override (lesson 31+34) directs governance signals to the audit kind.

## Master.xlsx WRITE forbidden

This skill MUST NOT call `transaction.append`, `transaction.update`,
`transaction.delete`, or `wb.save` against `master.xlsx`. It does not
even open the workbook — schemas live under `schemas/` and SKILL.md
files live under `skills/`, both outside the project state tree.
The test suite enforces this by regex grep over the production prose:
the call-site syntax (transaction-dot-append-with-paren etc.) is
forbidden in this body, and the body intentionally references those
tokens WITHOUT the trailing paren to discuss them in negative form.

## Why the `rules` key matters (W-H1 finding F-13.1 reuse)

The cross-sheet-invariants instance document uses the top-level key
`rules` (per spec §3.5 instance pivot). Memory drift naturally
produces the misspelling `invariants` (the document title has
"Invariants" in it). schema-validate explicitly tests the `rules`
key so this drift is caught the moment it appears — schema authority
wins over memory authority (lesson 31+34 schema-first override).

## Why hardcoded schema count is forbidden

The brief's authority claim ("19 schema") diverged from the actual
filesystem count (18). The natural temptation is to lock the count
in a constant; schema-validate explicitly avoids this. `glob()` enumerate
makes the skill self-aware: it reports whatever exists at runtime, and
the report records the count for the manager to cross-check. This is
the lesson 31+34 schema-first override paterni applied to a count
authority.

## Cross-references

- Schemas: `schemas/skill-frontmatter.schema.json`,
  `schemas/cross-sheet-invariants.json`,
  `schemas/events.schema.json` (event_kind=audit branch).
- Cross-modules: `scripts/state/events_writer.py` (audit append),
  `scripts/reporting/render_template.py` (report render).
- Tests: `tests/skills/governance/test_schema_validate.py`.
- Sibling governance skills: `drift-check` (master.xlsx invariants),
  `glossary-audit` (term drift), `load-context` (session wakeup).
