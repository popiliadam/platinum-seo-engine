# Worker Prompt — Batch pb0: Intent-Router Precision (mention ≠ request)

> **Initiative:** Path B follow-on (O4 governance ladder, **rung 0**). Authority:
> `docs/superpowers/specs/2026-06-09-path-b-general-orchestration-research.md` §1, §6, §8.
> **You are a fresh Opus 4.8 (1M-context) worker.** Build ONLY this batch. Report back to the manager.

## Hard rules (non-negotiable — every AMO worker obeys these)
- **NO `Task`/`Agent` tools — work INLINE.** Subagents fail in this repo ("Prompt too long").
- **Baseline-first:** run the FULL suite, record exact `pytest` pass/fail/skip N at start; end strictly ≥ that pass count, 0 new fails.
- **TDD:** RED → GREEN → REFACTOR. Write the failing test FIRST, watch it fail for the right reason, then implement.
- **Scope-locked:** touch ONLY the files named in §Scope. Any out-of-scope need → STOP and report; do not wander.
- **No commit** — the manager commits after independently re-deriving your claim. Make WIP checkpoints if you like, but do not `git commit` the batch as final.
- **Never weaken a guarantee to make a test pass.** If a test is wrong, say so in the report; don't silently delete it.

## Why this batch exists (the live bug — read this)
The intent router (`scripts/hooks/intent_router.py`) is a `UserPromptSubmit` hook. Today, when a prompt merely *contains* a canonical phrase (e.g. `"aylık bakım"`), it writes a **`declared`** intent marker — which ARMS the denetçi Stop-hook (`scripts/hooks/denetci.py`) to BLOCK turn-end and nag `/pseo-run monthly <slug>` if the workflow didn't run. This fires on **mentions and questions**, not just requests. It has misfired THREE times in a single recent session — including on a research prompt whose only crime was *discussing* "aylık bakım". The cascade: router writes `declared` → denetçi nags a workflow the operator never asked for. It is *safe* (nothing executes) but it is exactly the **mention ≠ request** false-positive Path B must solve, and adding more router patterns makes it WORSE.

**Your job:** the router must only ARM the denetçi (write a `declared` marker) when the prompt is an **actionable request**, not a mention/question — while still *surfacing* the option helpfully when the workflow is merely mentioned. Deterministic, additive, never-crash, byte-preserving for genuine commands.

## The current contract (grounded — DO NOT re-derive, but DO re-read the file)
Read `scripts/hooks/intent_router.py` in full. The relevant shape:
- `classify(prompt) -> (workflow_key|None, matched[])` — substring match over `CANONICAL_WORKFLOWS` (only `"monthly"` today). 1 match → that key; 0 or ≥2 → None.
- `route(prompt, *, session_id, workspace_root, turn_id, intent_id, declared_at) -> {"marker","voice","tier","matched","slug"}` — PURE; the caller writes the marker + prints the voice. Today:
  - **Tier-1** (`workflow is not None`): `_tier1_result(...)` → marker `status="declared"` + actionable voice `➤ Niyet: {label} algılandı → çalıştır: {command}`.
  - **Tier-2** (None/collision): marker `status="superseded"` + the `_ADVISORY`.
- The denetçi (`denetci.py:145`) only owes a workflow when `marker.status == "declared"`. A `superseded` marker owes nothing.
- The marker schema is `schemas/intent-marker.schema.json` (`status` enum is `("declared","superseded","consumed")` per `intent_router._STATUSES`). **Do NOT change the schema or the enum.**

## What to build — a THIRD tier ("mentioned, not requested")
Add a pure predicate and a third branch in `route`. Three outcomes now:

| Case | Condition | marker `status` | voice | Denetçi armed? |
|---|---|---|---|---|
| **Tier-1 (request)** | `classify` matched **AND** `is_actionable_request(prompt)` | `declared` (unchanged) | actionable `➤ Niyet: … → çalıştır: …` (unchanged) | YES (unchanged) |
| **Tier-1-soft (mention)** | `classify` matched **AND NOT** `is_actionable_request(prompt)` | **`superseded`** | a SOFT hint: `ℹ️ '{label}' geçti — çalıştırmak istersen: {command}` | **NO** ← the fix |
| **Tier-2 (no match)** | `classify` returned None | `superseded` (unchanged) | `_ADVISORY` (unchanged) | NO (unchanged) |

The key property: **a mere mention NEVER writes `declared`, so the denetçi is never owed a phantom workflow** — but the operator still *sees* how to run it (helpful surfacing, the valuable half of the vision). A genuine command is byte-for-byte unchanged.

### `is_actionable_request(prompt: str) -> bool` (PURE, no IO)
Deterministic, data-driven, conservative, and **biased to False on ambiguity** (a false-negative just means the operator types the command — cheap; a false-positive nags — expensive). Specify it as:

1. Normalise: `lower()`, strip. Empty/non-str → `False`.
2. **Strong actionable signal (any ⇒ candidate True):** the explicit command token `/pseo-run`, OR an imperative/request verb token from a data-driven set — at minimum (extend thoughtfully, Turkish + English):
   `yap, yapar mısın, çalıştır, calistir, başlat, baslat, koş, kos, çek, cek, üret, uret, oluştur, olustur, güncelle, guncelle, hazırla, hazirla, devam et, resume, run, başlatalım, çalıştıralım`.
   Match as whole-word-ish tokens (a simple word-boundary/substring rule is fine given these are distinctive; document the choice).
3. **Question / discussion signal (any ⇒ force False, overrides step 2):** the prompt ends with `?`, OR contains a question/meta marker — at minimum:
   `nedir, ne demek, ne işe, nasıl, nasil, neden, niçin, nicin, hakkında, hakkinda, açıkla, acikla, anlat, araştır, arastir, incele, mı?, mi?, mu?, mü?, mı ?, fark ne, ne zaman, mıdır, midir`.
   (Rationale: a prompt that is dominantly a question is a *mention*, never a *request*, even if it also contains an imperative verb like "açıkla".)
4. Default (no strong actionable signal) → `False`.

Order matters: a question marker (step 3) WINS over an actionable verb (step 2) — "aylık bakımı açıkla" is a question, not a run request. Document this precedence in the docstring.

> **Design note for the report:** these lists are heuristic and Turkish-morphology-imperfect by nature. That is ACCEPTABLE because the cost is asymmetric (biased to not-arm). Keep the lists as module-level frozensets so they are trivially extendable; do NOT try to build a full NL grammar (out of scope, spec §6).

## TDD — write these RED first (in `tests/hooks/test_intent_router.py`, extend, don't rewrite)
Add a focused test class. Cover at minimum:
- **The live false-positives (MUST be Tier-1-soft, status `superseded`, denetçi NOT armed):**
  - A research/question prompt that mentions monthly: e.g. `"path b araştırması: aylık bakım router'ı nasıl çalışıyor inceleyelim"` → `route(...)["marker"]["status"] == "superseded"` AND the voice is the soft hint (NOT the `➤ … çalıştır` declared voice).
  - `"aylık bakım nedir?"` → superseded + soft.
  - `"monthly maintenance workflow'unu açıkla"` → superseded + soft.
- **Genuine requests (MUST stay Tier-1, status `declared`, byte-identical voice to today):**
  - `"demo-furniture'da aylık bakım yap"` → `declared` + the exact `➤ Niyet: aylık bakım algılandı → çalıştır: /pseo-run monthly demo-furniture` voice (assert the voice string is UNCHANGED from current behaviour).
  - `"/pseo-run monthly demo-furniture"` → `declared`.
  - `"aylık bakımı çalıştır"` → `declared`.
- **`is_actionable_request` unit table:** a parametrized list of (prompt, expected_bool) covering each verb, each question marker, the precedence rule (question beats verb), empty/non-str.
- **No-match unchanged:** a prompt with no canonical phrase → Tier-2 advisory, `superseded` (existing behaviour preserved).
- **Never-crash:** `main()` still degrades to the advisory on any internal error (existing guarantee; add a regression if not already covered).
- **End-to-end via subprocess** (mirror the existing subprocess tests): pipe a mention payload → assert NO `declared` marker on disk; pipe a request payload → assert a `declared` marker.

Also: re-run the EXISTING `test_intent_router.py` + `test_denetci.py` — they must stay green (the denetçi tests assume `declared` semantics; your change only narrows WHEN `declared` is written, so a denetçi test that constructs a `declared` marker directly is unaffected — confirm).

## Scope (touch ONLY these)
- `scripts/hooks/intent_router.py` — add `is_actionable_request` + the third `route` branch + the soft voice. Keep `main()`, the schema, the `_STATUSES` enum, the context line, and the degraded path UNCHANGED.
- `tests/hooks/test_intent_router.py` — add the new test class (extend; do not delete existing tests).
- **No** schema/command/MCP/manifest change → **no D10 count cascade**, no new RUNTIME_HOOK_SCRIPTS entry (the hook is already wired).

## DONE when
- Full suite ≥ baseline pass count, 0 new fails; the new tests are green; the existing router + denetçi tests are green.
- A mention/question that names a canonical workflow writes `superseded` (NOT `declared`) and emits the soft hint; a genuine request writes `declared` with the byte-identical actionable voice.
- `route` stays PURE; `main` stays never-crash; schema/enum untouched.

## DURUR (stop + report) if
- Making a mention go `superseded` would require changing the marker schema or the `_STATUSES` enum (it must NOT — `superseded` already exists).
- Any existing denetçi/router test can only be made green by weakening the `declared`-arming guarantee for genuine requests.
- You discover the denetçi keys on something other than `marker.status == "declared"` (re-read `denetci.py:145` — if reality differs from this prompt, STOP and report the discrepancy; do not code around an assumption).

## Report back (to the manager)
- Exact baseline N and final N (pass/fail/skip).
- The full diff of `intent_router.py` (the new predicate + branch + voice).
- The new test names + which live-false-positive prompts you locked as regressions.
- Any judgment calls on the verb/question word lists (what you included/excluded and why).
- Confirm: schema/enum/command-count untouched; `route` pure; `main` never-crash.
