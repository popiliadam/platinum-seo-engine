# Deterministic Content Validator — Design Spec

**Date:** 2026-06-04
**Author:** Süleyman Çapar (via Claude)
**Status:** Approved (design) — implementation pending
**Source finding:** `docs/audits/2026-06-04_deep_quality_security_audit.md` → Gap 1
**Related memory:** `feedback_ai_disclosure_ban`, `project-deep-audit-2026-06-04`

---

## 1. Problem

The five content-production skills (`new-blog`, `revise-content`, `faq-optimization`,
`content-remediation`, `generate-images`) emit HTML/MD that goes live on client
sites. Their quality gates exist **only as prose inside SKILL.md** — there is no
deterministic Python check over the generated content. Consequently the project's
hardest constraint (the **AI-disclosure ban**: no "written by AI" / "yapay zeka
tarafından yazıldı" phrasing in visible HTML) rests entirely on the LLM obeying a
prompt. This is the same *declared-but-unenforced invariant* failure mode as the
confirmed F-12 no-op, but on the production content path.

`scripts/production/*.py` runtime does not exist yet (deferred to Phase 11 W2), so
the skills cannot call a validator at their own gate step today. The reliable
enforcement boundary that *is* live is the **Write tool** itself.

## 2. Goal & non-goals

**Goal.** A deterministic, zero-dependency validator that inspects generated HTML
and (a) **blocks** the write when a hard rule is violated, (b) **warns** on softer
rules — wired at the Write boundary so it cannot be bypassed by an LLM ignoring
prose.

**Non-goals (v1).**
- No WCAG/contrast (R-39), meta-pixel (R-35), or W3C validation (R-59) — these need
  heavier infra (color math, font metrics, html5lib). Deferred.
- No cross-revision checks (R-89 canonical preserve, R-88 freshness theater) — need
  before/after state. Deferred.
- No AMBER→2×AMBER→RED escalation state machine — single-pass verdict only.
- No config schema change. The blocklist is built-in for v1 (config-extensible later
  → would be a schema-first bump). Reading the *existing* `profile` field is fine.
- MD content pipeline: library is format-agnostic and the CLI accepts any file, but
  the **hook scope** is the live HTML surface only (see §7).

## 3. Architecture

Two units, one shared library:

```
LLM executes new-blog → Write tool → projects/<slug>/outputs/blog/<slug>/article.html
        │
        ▼
  PreToolUse hook (3rd entry in hooks/pre-tool-use.json, matcher Edit|Write|Bash)
        │  scripts/hooks/validate_content_write.py
        │   - reads stdin JSON (tool_name, tool_input.file_path, .content/.new_string)
        │   - is it a content HTML write? no → exit 0
        │   - resolve profile (best-effort) → call library
        ▼
  scripts/validation/content_validator.py   ← PURE, no I/O, stdlib only
        │   validate_content(html, profile) → ContentReport(findings[], verdict)
        ▼
  verdict RED  → hook sys.exit(2)  → write BLOCKED, findings on stderr
  verdict AMBER/GREEN → exit 0 (+ AMBER warnings on stderr) → write proceeds
```

**Why pure library + thin hook.** The library has no I/O and takes content as a
string → fully unit-testable with fixtures. The hook does stdin parsing, path
filtering, profile resolution, and translates the verdict into an exit code. The
same library is callable from the skill gate (Phase 11) and a CLI, so the rule logic
lives in exactly one place.

**Why stdlib `html.parser`, not BeautifulSoup.** Zero new dependency (the Pillow
undeclared-dep lesson: a new dep can mask test-collection errors and trip the 3.10
lock). Our checks — extract visible text, scan tag/attribute — are well within
stdlib reach. Must run on Python 3.10+ (CI matrix 3.10 + 3.14).

## 4. Rule set (v1 "balanced", 8 rules)

| Rule | Check | Severity | Fragment-safe? |
|------|-------|----------|----------------|
| **AI-disclosure** | visible text matches a disclosure phrase (see §5) | 🔴 RED | yes |
| **R-22** fragment boundary | `<!doctype`, `<html`, `<head`, `<body` present | 🔴 RED | yes |
| **R-43** FAQ accordion | `<details>` or `<summary>` tag present | 🔴 RED | yes |
| **R-77** image alt | any `<img>` with missing/empty `alt` | 🔴 RED | yes |
| **R-61** pse- prefix | any `class="…"` token not starting `pse-` | 🔴 RED | no (full doc) |
| **R-106** citation density | citations per 500 words outside [1,2] | 🟡 AMBER | no |
| **R-101** self-contained intro | intro has a back-reference phrase (see §5) | 🟡 AMBER | no |
| **R-104** stats density | numeric stats vs word count outside profile band | 🟡 AMBER | no |

"Fragment-safe" = correct to evaluate on an Edit `new_string` fragment (presence
checks). Non-fragment-safe rules need the whole document and run on **Write** only.

**Verdict:** RED if any RED finding; else AMBER if any AMBER finding; else GREEN.

## 5. AI-disclosure blocklist & intro back-references

Phrase-level, case-insensitive, Unicode-aware. The bare term "AI" / "yapay zeka" is
**never** flagged — only multi-word disclosure phrases. Checked against **visible
text only** (script/style/comments stripped — §6), so JSON-LD and image IPTC
disclosure (R-78, *required*) are untouched.

Disclosure patterns (regex, `\s+` between words to tolerate spacing):
- TR: `yapay\s+zeka\s+(taraf[ıi]ndan|ile)\s+(yaz[ıi]l|üretil|oluşturul)`,
  `bu\s+(içerik|yaz[ıi]|makale)\s+yapay\s+zeka`,
  `(yapay\s+zeka|dil\s+modeli|ChatGPT)\s+taraf[ıi]ndan\s+(yaz|üret|oluştur)`
- EN: `written\s+by\s+(an\s+)?AI`, `generated\s+by\s+(an\s+)?AI`,
  `AI[- ]generated\s+(content|article|text)`,
  `as\s+an?\s+(AI|large\s+)?(language\s+model|AI\s+language\s+model)`,
  `created\s+by\s+artificial\s+intelligence`, `\bI\s+am\s+an\s+AI\b`

Intro back-reference patterns (R-101, AMBER): `yukar[ıi]da\s+gördüğünüz`,
`bu\s+yaz[ıi]da`, `bu\s+makalede`, `as\s+(mentioned|shown)\s+above`,
`as\s+we\s+(saw|discussed)\s+above`. Applied to the first `<p>`/intro block only.

> The patterns live as a module-level constant in `content_validator.py`, easy to
> extend. No project-config field in v1.

## 6. Visible-text extraction

A small `html.parser.HTMLParser` subclass collects text data, **skipping** the
content of `<script>`, `<style>`, `<template>`, `<noscript>`, and HTML comments. The
AI-disclosure, intro back-reference, citation-density, and stats-density checks run
on this visible text. Structural checks (R-22, R-43, R-77, R-61) run on the parsed
tag/attribute stream (or raw-string presence for doctype).

## 7. Hook integration

Add a **third entry** to the existing `hooks/pre-tool-use.json` `PreToolUse[0].hooks`
array (matcher stays `Edit|Write|Bash`):

```json
{ "type": "command",
  "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/validate_content_write.py\"",
  "timeout": 15,
  "statusMessage": "Content rule validation..." }
```

`validate_content_write.py`:
- Reads stdin JSON. Gets `tool_name`, `tool_input.file_path`, and content
  (`tool_input.content` for Write, `tool_input.new_string` for Edit).
- **Path scope:** proceed only if `file_path` matches `**/outputs/blog/**/*.html`
  (the live published fragment). Anything else (Bash, non-content paths, internal
  `.md` like upload-instructions/change_summary) → `exit 0` immediately.
- **Write:** run the full validator on `content`.
- **Edit:** run only the fragment-safe RED subset on `new_string` (so an Edit cannot
  inject a disclosure phrase / accordion / doctype). Density & pse-prefix need the
  full doc → skipped on Edit (covered at next Write + CLI/CI).
- Resolve `profile` best-effort: `PSEO_WORKSPACE_ROOT/shared/active.json` →
  `projects/<active>/project.config.json` → `profile` (else first of `profiles`,
  else `None` = neutral defaults). Profile only affects the R-104 AMBER band; RED
  rules are profile-independent.
- **Verdict → exit:** RED → write findings to stderr, `sys.exit(2)` (BLOCK).
  AMBER → write warnings to stderr, `sys.exit(0)`. GREEN → `sys.exit(0)`.

**Error handling — conservative about blocking, loud about failure.** Wrap `main()`
in try/except: on *any* unexpected error (stdin parse, import, parser crash) write a
loud `WARNING` to stderr and `sys.exit(0)` (**fail-open** — a buggy gate must not
brick all content production; CLI/CI + skill gate are backups). A *true RED finding*
is fail-closed (`exit 2`). The AI-disclosure check is a plain regex over text →
crash probability ~0, and is covered by tests.

**CLI:** `python -m scripts.validation.content_validator <file.html> [--profile P]`
prints findings; exit 1 on RED, 0 otherwise. For CI/manual use.

## 8. Files

**Create**
- `scripts/validation/content_validator.py` — pure library + CLI `main()`.
- `scripts/hooks/validate_content_write.py` — PreToolUse hook wrapper.
- `tests/validation/test_content_validator.py` — library unit tests (fixtures are
  inline HTML constants — no `__init__.py`, matching the PEP 420 + conftest
  `sys.path` convention already used under `tests/`).
- `tests/hooks/test_validate_content_write.py` — hook-level tests.

**Modify (known cascades — cross-checked)**
- `hooks/pre-tool-use.json` — add the 3rd hook entry.
- `scripts/hooks/README.md` — add `validate_content_write.py` to the §1 runtime table.
- `tests/hooks/test_hook_scripts_runtime_vs_ci.py` — add it to the runtime set.

> `plugin.json` "6 hook" file count is **unchanged** (we add an entry, not a JSON
> file). No README/ARCHITECTURE count churn.

## 9. Test matrix (TDD — RED first)

Library (`test_content_validator.py`), one violating fixture per rule asserting the
exact finding + severity, plus:
- **Clean fixture** → GREEN (a well-formed `pse-`-classed article fragment).
- **False-positive guards (critical):**
  1. A blog *about* AI ("Yapay zeka nedir?") using "AI"/"yapay zeka" heavily but
     with no disclosure phrase → **GREEN**.
  2. JSON-LD `<script>` containing "AI generated" but not in visible text → **GREEN**
     (script stripped).
  3. An `<img>` whose AI-source disclosure is in IPTC/schema, not visible HTML →
     **GREEN** (R-78 required, untouched).
- **Profile band:** same stats count is AMBER for YMYL (tight) but GREEN for
  local-service (loose) — proves profile-aware R-104.
- **Multi-finding:** a fixture violating 2 RED rules → verdict RED, both reported.

Hook (`test_validate_content_write.py`):
- Write to `…/outputs/blog/x/article.html` with a disclosure phrase → exit 2.
- Write clean content → exit 0.
- Write to a non-content path (e.g. a script) → exit 0 (skipped).
- Edit injecting a disclosure phrase into a content path → exit 2.
- Malformed stdin / missing fields → exit 0 + WARNING (fail-open).
- Bash tool event → exit 0 (skipped).

## 10. Commit plan (atomic, `[deep-audit]` tag, English)

1. `feat(validation): deterministic content validator library [deep-audit Gap1]`
   — `content_validator.py` + library tests + fixtures (RED→GREEN).
2. `feat(hooks): wire content validator at the Write boundary [deep-audit Gap1]`
   — hook script + `pre-tool-use.json` entry + hook tests + README §1 + runtime-vs-ci
   test update.

Each commit: full `pytest` green + zero regression, proven (code-reviewer +
verifier) before it lands. This spec committed alongside / ahead of commit 1.

## 11. Future (explicitly deferred)

- Config-extensible blocklist (`content_settings.ai_disclosure_blocklist`) — needs a
  schema-first additive bump + migration.
- AMBER escalation state (2×AMBER→RED) across runs.
- WCAG (R-39), meta-pixel (R-35), W3C (R-59), canonical/freshness (R-88/89).
- Skill-gate integration when `scripts/production/*` runtime lands (Phase 11 W2).
- MD-surface validation if a future pipeline publishes Markdown.
