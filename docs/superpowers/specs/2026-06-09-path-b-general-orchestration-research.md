# Path B — General Auto-Orchestration Engine: Feasibility & Design Research

> **Status:** RESEARCH (no code built; recommendation for Süleyman's decision)
> **Date:** 2026-06-09
> **Author:** fresh research session (manager-style), Opus 4.8 1M-context
> **Re-opens:** spec §10 **O4** ("promote-to-declarative trigger") with v2.0.0 live evidence
> **Companion docs:** `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md` (the v3 / Path A design); `docs/superpowers/plans/amo/MANAGER.md` (the build record); `docs/superpowers/plans/amo/PATH-B-RESEARCH-PROMPT.md` (this charter)

---

## 0. Executive summary & recommendation (read this first)

**Recommendation: NO-GO on building the general orchestration engine now. CONDITIONAL-GO on a 3-rung de-risking ladder whose first two rungs are pure Path-A governance value and whose third rung (executing a dynamically-assembled plan) stays gated behind a concrete promote-trigger that is *not currently met*.**

The investigation produced one assumption-overturning fact and one load-bearing safety fact:

1. **The capability graph is not missing — it is latent and unreconciled.** All 45 skills already declare `inputs`/`outputs`/`consumes`/`produces`/`mcp_tools`/`triggers.natural_language` in frontmatter. The `produces` edges are clean (66 of 68 point at real skills; only 2 dangle), but `produces`/`consumes` are **not reconcilable as inverse edges of one graph — 77% asymmetric** (53 of 68 cases where A `produces` B, B does not `consume` A), and **no test validates either field**. A planner built on the frontmatter as-is would topo-sort on an unreconciled structure — the exact D11 failure mode ("the map looks right; the live data disagrees").
2. **The ≤5% correctness oracle cannot backstop a dynamically-assembled sequence without eroding its own independence.** Its independence comes from holding the `(step → sheet, output_file)` map *out of band* (a hardcoded registry). A dynamic plan has no pre-registered map, so either every Path B run scores `unresolved_workflow` (no backstop) or the run authors its own audit checklist (independence lost).

Against this, the **null hypothesis (Path-A expansion) is strong and cheap**: a new workflow is a ~15-line `STEPS` table + a thin wrapper, and a new router trigger is one dict entry. The general engine would have to beat ~3–4 more such tables on cost *and* risk — a bar it does not clear today. **What the engine would genuinely add — auto-engaging the right tool and handling novel intents — is dominated by one separable, cheap win (relevance precision) and one rare need (novel multi-step intents) that this operator does not currently have.**

So: **do the two cheap things that realize the *valuable* part of Süleyman's vision and de-risk a future engine; defer the engine itself until the trigger fires.**

---

## 1. Live evidence — the precision gap demonstrated *again*, this turn

This research session opened with a `UserPromptSubmit` hook firing on the research prompt itself:

```
➤ Niyet: aylık bakım algılandı → çalıştır: /pseo-run monthly demo-furniture
```

The prompt only *discussed* "aylık bakım" (monthly maintenance) as the subject of study; it did not request a run. The router's substring match (`intent_router.py:130-134`) fired a Tier-1 declaration anyway. Then, at the end of that same research turn, the **denetçi `Stop` hook completed the cascade** — seeing a `declared` intent with no fresh passing run, it blocked turn-end with `⚠️ Niyet algılandı (monthly) ama bu turda workflow çalışmadı → /pseo-run monthly demo-furniture` (`denetci.py:145-148`). So the *full* false-positive chain the charter §3 describes reproduced end-to-end, **in one session, on a prompt whose entire purpose is to study it**: router declares a phantom intent → denetçi nags to "complete" it. Correct by each hook's rules; wrong in fact. It was *safe* (the router only nudges, the denetçi only blocks turn-end, nothing executed, no budget spent), but it is the clearest possible statement of the core unsolved problem: **naive matching engages on mere mention.** Crucially, the cost landed in the worst place — the denetçi *owes* a workflow it should never have been told about. Any expansion that adds *more* substring patterns makes this *worse*, not better; **rung-0 (move the trigger behind imperative-shape / explicit confirm, so the denetçi only ever owes a *confirmed* intent) is the fix, §6/§8.**

---

## 2. What exists today (grounded in code — every claim is file:line)

### 2.1 The frozen spine (Path B may compose it, never edit it)

| Module | Role | Key fact |
|---|---|---|
| `scripts/orchestration/run_step.py` | one code-verified step | `run_step` = verify → transform(loader) → commit → silent-skip gate → coverage step (`run_step.py:43-98`) |
| `scripts/orchestration/verify.py` | the identity+content+freshness gate | `verify_raw_drop` checks existence→parse→structure→identity→freshness→truncation, returns a stable reason code, **never inspects SEO correctness** (`verify.py:96-147`) |
| `scripts/orchestration/committer.py` | the one commit path | wraps `transaction.replace` (idempotent whole-block) (`committer.py:38-46`) |
| `scripts/orchestration/coverage.py` | the per-run proof | `derive_verdict`: `required_satisfied` = every **code_verified** step satisfied; verdict ∈ {pass, incomplete, failed} (`coverage.py:158-175`) |
| `scripts/orchestration/workflow_driver.py` | the shared **data-driver** (O4 light-promote) | `_run_one` routes `code_verified`→`run_step` (count enforced) vs `model_attested`→`_run_attested_step` (count advisory) (`workflow_driver.py:196-213`) |

**The load-bearing trick:** the orchestrator dictates the raw-drop path (`inbox_path` embeds `run_id`, `workflow_driver.py:70-76`), so a model that makes a wrong/misnamed MCP call produces a drop that "simply isn't where the gate looks." That is how a model-made call earns `code_verified` status *without trusting the model's judgment* — only its mechanics, which the gate re-checks.

### 2.2 The four shipped workflows = two driver shapes

A workflow today is **a `STEPS` tuple + a thin CLI wrapper**. Example (`monthly_maintenance.py:42-55`): three dict entries, each `{name, sheet, output_file, writer, site_url, window, tool, verification_class}`. The wrapper delegates everything to `workflow_driver.run_workflow`.

- **Data-driver** (monthly/audit/setup): raw MCP drop → transform CLI → `verify_raw_drop` → `committer` → master.xlsx rows. Shares `workflow_driver`.
- **Artifact-driver** (content): model emits `outputs/blog/<post>/article.html`; per-step verify = artifact-exists + `content_validator.validate_content(html).has_red is False` (`content_pipeline.py:92-121`). Shares **only** `coverage`.

Faz-3 proving *two distinct shapes* is itself the strongest in-repo argument against a single universal engine (`MANAGER.md:94-104`): a graph that unified them would either over-abstract or carry both — no simpler than the two drivers that exist.

### 2.3 The safety layer — and which parts are sequencing-coupled

| Guard | Mechanism | Coupled to *which workflow ran*? |
|---|---|---|
| **Outward-action consent gate** (2b/2f) | `PreToolUse` classifies the model's **concrete tool call** — `git push` / `rm` / `curl POST` / `mcp__gsc__submit_sitemap` — and denies unless a per-session consent ledger entry exists (`outward_action_gate.py:239-320`) | **NO.** Intercepts the actual tool call; plan-agnostic. |
| **AI-disclosure quarantine** (2e) | `PostToolUse` rescans any blog-HTML write; renames it off the live surface on a RED signal | **NO.** Fires on the artifact, not the plan. |
| **Denetçi** (2c) | `Stop` hook: a *declared* intent must reach a fresh coverage record with verdict=pass, else block with a Turkish fix (`denetci.py:132-159`) | **Partially.** Keys on the intent marker's `workflow` + freshness; assumes a single declared workflow. |
| **Correctness oracle** (2d/3-oracle) | reconciles committed master.xlsx rows vs transform OUTPUT, **independent of the self-reported verdict** (`orchestration_metrics.py`) | **YES.** Resolves a run's workflow by subset-matching a **hardcoded `_WORKFLOWS` registry** (`:57-60`, `:139-158`). |

This split is the crux of the whole safety analysis (§5): **two of four guards are already plan-agnostic and Path B inherits them for free; the other two are coupled to the "known workflow" assumption.**

### 2.4 The latent capability graph (the surprise)

Every skill's frontmatter already declares (verified across all 45 `SKILL.md`):

```yaml
inputs:   { project_slug: {type, required, default, ...}, ... }   # typed
outputs:  [ "master.xlsx#gsc_performance", "events.jsonl", ... ]   # artifact refs
consumes: [ "init-project:projects/{slug}/master.xlsx", ... ]      # upstream
produces: [ "quick-wins", "content-decay", "drift-check", ... ]    # downstream
mcp_tools:{ required: [...], optional: [...] }
triggers: { manual: [...], natural_language: "...", scheduled: [...] }
budget:   { uses_paid_mcp, estimated_credits }
autonomy: { confidence, requires_approval, safe_auto_execute }
```

This is *already a capability-graph node definition.* A consistency probe across the 45 skills (clean YAML parse) found:

- **`produces` is a clean skill→skill edge list** — of 68 distinct produce-targets, 66 resolve to real skills; only **2 dangle** (`content-improve`, `dashboard-refresh`, likely renamed/removed). So the field itself is not garbage.
- **But `produces` and `consumes` are NOT reconcilable as inverse edges of one graph:** in **53 of 68 cases (77%)** where A declares `produces: B`, B does **not** declare a matching `consumes: A`. The two fields encode different, never-reconciled views (`produces` ≈ "downstream skills I feed"; `consumes` ≈ "artifacts/skills I read" — `consumes` legitimately mixes skill-refs and artifact-refs like `init-project:projects/{slug}/master.xlsx`).
- **No test validates either field** (no acyclicity / symmetry / dangling-ref check anywhere in `tests/`). The 3a lint only enforces `mcp_tools ⊆ registry` — nothing about the dependency edges.

**Conclusion:** the orchestrator ignores a real but **unreconciled and unvalidated** dependency structure. This is *both* good news for option A (rich metadata exists) *and* a hard blocker (it must be normalized + validated into a single consistent edge set before anything can safely topo-sort on it).

---

## 3. The five design options (Q1)

### Option A — Declarative capability/dependency graph + topo-sort engine
Each skill declares inputs/outputs/preconditions; the engine resolves + topologically sorts a plan for an arbitrary intent.

- **FOR:** the metadata mostly exists (§2.4); aligns with Süleyman's literal "all files interconnected, conductor at the head" vision; a clean graph would auto-cover future skills.
- **AGAINST:** the graph is 77% asymmetric / unreconciled and unvalidated — planning on it propagates stale edges (D11 class). The two driver shapes (§2.2) resist a single topo-sort abstraction. **It does not solve relevance** (it tells you *how* to sequence, not *whether* an intent is even a request — §7). It does not make a `model_attested` step verifiable (§6). Highest build-risk; the engine is the part the adversarial review explicitly deferred.

### Option B — LLM-planner + deterministic validator
The model proposes an ordered sequence; a code validator checks it against the registry + gates before anything executes.

- **FOR:** the model is already strong at "given this intent, which skills in what order"; leans on existing strengths; the validator is a small, testable surface.
- **AGAINST — and this is the central question the charter poses:** *where does the ≤5% guarantee go when the plan itself is model-generated?* Answer (§5): it survives **only** for steps the validator can map onto a *registered* `(sheet, output_file, tool)` shape that the spine can gate and the oracle can reconcile. Every other proposed step collapses to `model_attested` — the validator must *refuse to claim* it is code-verified. So Option B is honest *only if* the validator is a strict allow-lister that downgrades-or-rejects, never a rubber stamp.

### Option C — Hybrid (curated core + LLM gap-filling at the edges)
The 4 proven workflows stay hard-coded + oracle-backed; for a novel intent the model proposes a sequence, the validator maps each step to a registered shape where possible, executes through the existing gated spine, and **marks any un-registered step `model_attested` and surfaces it for operator confirm.**

- **FOR:** preserves the core's ≤5% and all four guards; honest about the edges; additive and reversible; this is the *realistic* shape Path B would take if ever built.
- **AGAINST:** still needs the graph-consistency substrate (option A's prerequisite) and an oracle-extension design (§5) before the "execute" step is safe. Until those exist it is identical in *value* to option D plus a read-only proposer.

### Option D — Path-A expansion (THE BASELINE TO BEAT — "don't build the engine")
Add more canonical router patterns (data-driven, 1 dict entry per workflow, `intent_router.py:80-92`) + author more hard-coded `STEPS`-table workflows as needed.

- **FOR:** a workflow = ~15-line `STEPS` table + a thin wrapper that delegates to `workflow_driver`; a router trigger = 1 dict entry. **Every step is pre-registered, so the oracle backstops it and all four guards apply with zero new design.** Perfect ≤5% honesty; minimal build-risk; totally reversible.
- **AGAINST:** does not improve *relevance* (more substring patterns = more false-positives, §7); cannot serve a *genuinely novel* intent without a human authoring a new table; does not realize the "any intent" half of the vision.

**How many more workflows cover ~80% of real operator intents?** From the live portfolio + skills inventory, the recurring *multi-step sequences* beyond the 4 built are roughly: **weekly-monitoring**, a **keyword-research→cluster→content-plan** discovery sequence (≈ `setup`), a **content-remediation/decay-sunset** sequence, and a **GBP/local** sequence. That is **~3–4 more `STEPS` tables**. Most other operator asks are *single skills* already invocable directly (quick-win, cannibalization, schema-audit, dfs-pull, …) — they need no workflow at all. **The general engine must beat ~3–4 cheap tables. It cannot, today.**

### Scoring (1 = poor, 5 = excellent for the engine's goals)

| Criterion | A: graph engine | B: LLM-planner+validator | C: hybrid | **D: Path-A expansion** |
|---|---|---|---|---|
| Feasibility (build) | 2 | 3 | 3 | **5** |
| Safety-layer compatibility | 2 | 3 | 4 | **5** |
| ≤5%-scope honesty | 3 | 4 (if strict) | 4 | **5** |
| Operator value *delivered now* | 2 | 3 | 3 | **3** |
| Operator value *if vision matures* | 4 | 4 | **5** | 2 |
| Build-risk (5 = low risk) | 1 | 3 | 3 | **5** |
| Reversibility | 3 | 4 | 4 | **5** |
| Solves **relevance** (the live bug) | 1 | 2 | 2 | **1** |
| **Weighted verdict** | **Defer** | Conditional | **Target *if* trigger fires** | **Win today** |

**Read of the table:** D wins *today* on every cost/safety axis; C is the right *target* the day the trigger fires; A is dominated by C (C reuses A's metadata without committing to the full engine); B is the *mechanism inside* C. None of A/B/C solves relevance — that is a separate, cheaper track (§7).

---

## 4. Q4 — Honest scope: what fraction is genuinely code-verifiable?

The spec's binary (`code_verified` vs `model_attested`, §3) understates the truth. The shipped workflows reveal **three tiers**, and the distinction matters enormously for "what does a general engine actually buy":

| Tier | What the CODE proves | Steps (of the 13 structural steps shipped) |
|---|---|---|
| **T1 — fully code-verified** | identity+content+freshness **+ silent-skip count** + oracle committed-vs-output reconcile | `content_decay`, `on_page_audit` — the per-row ingestion steps (**2 of 13**) |
| **T2 — provenance-gated + oracle-reconciled, count advisory** | identity+content+freshness gate **still hard-fails**; oracle still reconciles committed-vs-output; only the *count* check is advisory (the transform legitimately aggregates) | `gsc_pull`, `quick_wins`, `tech_audit`, `schema_audit`, `cannibalization`, + setup's 3 (**~8 of 13**) |
| **T3 — artifact-attested only** | artifact exists + (HTML) AI-disclosure clean. **No provenance, no reconcile.** | content's 3 steps + report steps (**~3 of 13**) |

Two honest readings of "code-verifiable":

- **Strict (the count gate is meaningful):** only **T1 ≈ 15%** of structural steps. The D11 reclassification of `gsc_pull`+`quick_wins` to `model_attested` (`MANAGER.md:111`) proves the engine has been *honest* about pushing aggregating steps out of the strict class.
- **Practical (the oracle can independently reconcile committed-vs-output):** **T1 + T2 ≈ 77%** — but **only because the oracle holds the step-map out of band.** This is exactly the property a dynamic sequence destroys (§5).
- **Genuinely model_attested (no code grounding beyond existence):** **T3** — content & reports. **A general engine does not change this at all. It just sequences it.** The charter's brutal-honesty demand is satisfied: for content/analysis/judgment work, the engine adds ordering, not verification.

**The decisive corollary:** the ≤5% guarantee lives in T1+T2, and T1+T2's *independence* lives in the out-of-band step-map. Therefore **the value a general engine can safely deliver is bounded not by the planner's cleverness but by whether the oracle's independent map can survive dynamic step-sets.** It cannot, by construction, without the extension in §5.

---

## 5. Q3 — The safety model for dynamic sequences (the load-bearing section)

This is the section that decides GO/NO-GO. I analyze each guarantee against a *runtime-assembled* sequence.

### 5.1 Per-step verification — Q3(a): can each auto-selected step still be code-verified?

`verify_raw_drop` is **step-shape-generic, not workflow-specific.** It needs only `(expected_run_id, expected_slug, [site_url], [window], [tool])` and a raw drop at the dictated path (`verify.py:96-147`). So:

- A dynamically-selected step **that fits the data-driver shape** (make MCP call → provenance-stamped drop → transform CLI → commit) **is still fully gated** — identity+content+freshness hard-fail exactly as today. ✅
- A dynamically-selected step **outside that shape** (a novel MCP call with no transform/commit, a judgment step, an artifact step) **collapses to `model_attested`** — precisely the spec §11 boundary. ✅ honest, but no new verification.

**Verdict 5.1:** code-verification *per step* survives dynamic selection **for steps the planner maps onto the registered data-driver shape.** This is fine *iff* the planner/validator is forbidden from labeling anything else `code_verified` (Option B's strict-validator requirement).

### 5.2 The oracle — Q3(b): can it reconcile arbitrary outputs it has no STEPS table for?

**No — not without eroding its independence.** The oracle resolves a run's workflow by subset-matching the **hardcoded `_WORKFLOWS` registry** (`orchestration_metrics.py:57-60, 139-158`); an unresolved run returns `unresolved_workflow` and is **excluded from the error-rate denominator** (`:437-447`). Today only `monthly`+`audit` are even registered — `setup`/`content` already fall through (acceptable: setup is all-attested, content writes no sheets).

For a dynamic sequence there are exactly three options, and each has a cost:

1. **Don't register dynamic runs** → every Path B run is `unresolved_workflow` → **no ≤5% backstop at all.** Unacceptable for any sheet-writing step.
2. **The run authors its own `(step→sheet, output_file)` map into the coverage record** → the oracle reads the map from the run → **the run now influences its own audit checklist.** The oracle still independently re-derives *counts* from the workbook (its core independence — `committed_row_count` via openpyxl, `:165-196`), so a run cannot fake the *numbers*; but it *can* mis-declare *which sheets/files to check*, hiding a wrong write by omitting it from the map. Independence is *partially* eroded: counts stay independent, the *checklist* becomes run-attested.
3. **A gate-signed plan ledger** (the only safe path): when the planner commits a plan, it writes the assembled step-map to an **append-only, hash-chained, consent-gated plan ledger** (mirroring `consent_ledger.py` — O_APPEND+flock, never `os.replace`). The oracle reads the *signed, immutable* map, not the mutable coverage record the run rewrites. This **restores out-of-band independence** because the map is frozen at plan-commit time and tamper-evident.

**Verdict 5.2:** the oracle backstop is recoverable for dynamic sequences **only** via option 3 — a new append-only plan-ledger substrate the oracle reads. This is a *real, designable* artifact (the consent/cost ledgers are the proven pattern), but **it does not exist today and is a hard prerequisite** for safely executing dynamic plans. Until it exists, dynamic execution forfeits the ≤5% number.

### 5.3 Consent gate + AI-disclosure — Q3(c): do they extend to runtime-chosen steps?

**Yes, for free.** Both are `PreToolUse`/`PostToolUse` interceptors on the model's **concrete tool calls** (`outward_action_gate.py:239-257`; `ai_disclosure_rescan` on blog-HTML writes). They never inspect the plan. Whether a hardcoded recipe or a Path B planner selected the step, the moment the model emits `git push` / `rm` / `curl POST indexing.googleapis.com` / `mcp__gsc__submit_sitemap`, the gate fires and demands per-session consent; the moment a blog HTML carries an AI-disclosure signal, it is quarantined. **These walls are orthogonal to sequencing and Path B inherits them unchanged.** ✅ This is the single strongest safety argument *for* the feasibility of a future Path B.

### 5.4 The denetçi — the subtle coupling

The denetçi blocks turn-end when a *declared* intent did not reach a fresh passing run (`denetci.py:132-159`). For a dynamic plan, two things blur: (a) *what was declared* (the router writes one `workflow` marker; a multi-intent prompt has no single workflow), and (b) *what counts as satisfied* (a dynamic plan's "done" is its own assembled step-set). The denetçi would need the same signed plan ledger (§5.2 opt 3) to know "this turn owed plan P; did P's coverage reach pass?" **This is additive, not a rewrite** — but it is a second consumer of the plan-ledger prerequisite.

### 5.5 Safety verdict

| Guarantee | Survives dynamic sequencing? | Cost |
|---|---|---|
| Per-step identity+content+freshness | ✅ for data-driver-shaped steps; others honestly downgrade | none (spine is generic) |
| Outward-action consent wall | ✅ unchanged | none (tool-call interceptor) |
| AI-disclosure quarantine | ✅ unchanged | none (artifact interceptor) |
| **≤5% oracle independence** | ⚠️ **only via a new append-only plan ledger** | **a new substrate — hard prerequisite** |
| Denetçi intent-completion | ⚠️ additive, needs the plan ledger | shares the prerequisite |

**An engine that ships *before* the signed-plan-ledger exists erodes the ≤5% backstop — a Süleyman hard-constraint violation and an automatic NO-STARTER.** With the ledger, Path B is *safe-able*. The ledger is therefore the gating de-risk artifact, and — crucially — it is **only worth building once demand (§8 T1) is real.**

---

## 6. Q2 — Relevance detection (the separable, cheaper track)

The mention≠request problem (§1) is **independent of the orchestration-engine question** and is the part of Süleyman's vision ("right tool auto-engages") with the highest value-to-cost ratio. Options:

| Approach | What it does | Verdict |
|---|---|---|
| **More substring patterns** (status quo + D) | adds Tier-1 patterns per workflow | ❌ *worsens* false-positives linearly — the live bug ×N |
| **Imperative-mood / request-shape detection** | only declare intent when the prompt is a *command* ("yap", "çalıştır", "güncelle") not a *question/mention* ("nedir", "nasıl", "...hakkında") | ✅ cheap, deterministic, directly kills the §1 bug; pure addition to `classify` |
| **Confidence threshold + explicit confirm** | router *proposes* ("monthly çalıştırayım mı?") and only the operator's "evet" arms it; denetçi keys on the *confirmed* intent, not the *mentioned* one | ✅ strongest; the false-positive cost moves from "denetçi nags" to "one ignorable question"; aligns with the operator-confirm principle |
| **Full intent grammar / LLM intent classifier** | a learned/structured NL→intent map (the `triggers.natural_language` blocks made machine-usable) | ⚠️ overkill now; only justified if §8 demand is real |

**Acceptable false-positive rate & who bears the cost:** today the cost is borne by the *denetçi* (it nags about an un-run "intent") and the *operator* (confusion) — the worst place for it. The fix is to move the cost to a **pre-execution confirm** the operator can ignore in one keystroke, so a false-positive costs a glance, never a nag or a spent budget. **Target: a router that never *declares* (and thus never makes the denetçi owe) without either imperative-shape evidence or an explicit operator confirm.** This is a small, high-value change worth doing **regardless of the engine decision.**

---

## 7. Q5 — The concrete O4 promote-trigger

Path B's engine (option C) flips from NO-GO to GO when **all** of these hold; until then, keep expanding Path A. Each is *measurable from artifacts the engine already writes.*

- **T1 — DEMAND (currently UNKNOWN → instrument it).** ≥ **8 distinct operator intents/month** fall *outside* the hard-coded workflow set **and** are not single-skill invocations (i.e., genuinely novel multi-step sequences). *Measure:* the router already writes intent markers; log Tier-2 (unmatched) prompts and classify monthly. Today: unmeasured, anecdotally ≈0 — the 4 workflows + direct single-skill calls cover the live portfolio.
- **T2 — DEDUP (already moot).** ≥2 workflows share ≥3 edges a graph would dedupe. *Status:* monthly/audit/setup **already** share `workflow_driver` via the O4 light-promote; content is deliberately separate. The shared structure was captured **without** a graph, so a graph adds nothing here. T2 is satisfied-and-already-addressed — it is **not** an argument for the engine.
- **T3 — GRAPH HEALTH (currently FAILED).** The latent `consumes`/`produces` structure is normalized into one validated edge set: a graph-consistency lint is green (target: <5% asymmetric edges, 0 dangling skill-refs, acyclic). Today: **77% asymmetric, unreconciled, unvalidated** (§2.4). **A planner cannot be built safely until this is green.**
- **T4 — ORACLE EXTENSIBILITY (currently ABSENT).** A design + substrate exists for the oracle (and denetçi) to reconcile a dynamically-assembled step-set **without the run authoring its own audit map** — i.e., the append-only, hash-chained, consent-gated **plan ledger** of §5.2 option 3.

**Decision rule:** GO on option C **iff T1 ∧ T3 ∧ T4** (T2 moot). **Today: T1 unknown(≈unmet), T3 failed, T4 absent → NO-GO is the honest answer.** Keep expanding Path A.

---

## 8. IF/WHEN conditional — the de-risking ladder (small batches, never a big-bang engine)

Every rung delivers standalone value and is independently shippable. The ladder *is* the recommendation: do rungs 0–1 now (they are Path-A governance, not "the engine"); rungs 2–4 only as the trigger climbs.

> **Rung 0 — Relevance precision (do now; not the engine at all).**
> Add imperative-shape detection + an optional confirm step to `intent_router.py`'s `classify`/`route`. Kills the §1 false-positive. The denetçi only ever owes a *confirmed* intent. ~1 batch, pure addition, TDD, no new substrate. **Realizes the "right tool auto-engages, no nagging" half of the vision cheaply.**

> **Rung 1 — Graph-consistency lint (do now; pure Path-A "mastery lint" #3).**
> A read-only governance lint that validates the latent `consumes`/`produces` graph: symmetry, no dangling skill-refs, acyclic, `outputs`/`consumes` artifact-ref agreement. Sibling of the existing 3a (`body⊆declared`) and 3-gov (`F-27`) lints. **Delivers value even if Path B is never built** (it catches the skill-contract drift the 2026-06-04 audit already flagged) **and is the hard prerequisite (T3) for any future planner.** ~1 batch, read-only, no engine.

> **Rung 2 — Read-only planner that PROPOSES, executes NOTHING (only if T1 starts trending up).**
> Behind a hard operator-confirm, an LLM-planner proposes an ordered sequence for a novel intent and a deterministic validator checks each step against the registry + the (now-validated) graph + the gates, labeling each step T1/T2/T3 (§4) and **refusing to call anything `code_verified` that isn't data-driver-shaped.** Output is a *plan preview* + projected budget. **Executes nothing** — it is a design-validation harness. This is where Option B's validator gets built and proven without risk.

> **Rung 3 — The signed plan ledger (T4) + oracle/denetçi extension.**
> Append-only, hash-chained, consent-gated plan ledger (the `consent_ledger.py` pattern). The oracle reads the frozen map (restoring out-of-band independence, §5.2 opt 3); the denetçi keys on the confirmed plan. **Only now is dynamic *execution* safe-able.**

> **Rung 4 — Gated dynamic execution (Option C) — only if T1∧T3∧T4 all hold.**
> Execute a confirmed, validated plan through the *existing* gated spine, T3 steps surfaced for explicit operator confirm, every step oracle-reconciled via the rung-3 ledger. The 4 proven workflows remain the verified baseline and are never deleted (additive promotion, per the charter's hard constraint).

**Build model if it proceeds (unchanged from AMO):** manager/worker, fresh Opus-4.8 1M-context workers, **NO Task/Agent tools**, TDD RED-first, scope-locked, manager re-derives each batch's claim independently (the D11 lesson: a contract-key error is invisible to an independent derivation that inherits it — cross-check against real workspace files).

---

## 9. Adversarial self-check (did Path B get a fair hearing?)

- **Steelman for GO:** Süleyman's literal vision *is* the engine; the portfolio is growing (10→12+); the metadata already exists; the consent walls already extend for free. — *Rebuttal:* vision-alignment is a reason to *keep the door open* (CONDITIONAL), not to build now; growth is the *trigger* (T1), not a present fact; the metadata exists but is 77%-asymmetric / unreconciled (T3); "walls extend for free" is true but the *oracle* does not (T4).
- **Steelman for "just build the lint and call it done":** rung 1 alone closes the governance gap. — *Rebuttal:* true, and that is exactly why rung 1 is "do now" and unconditional; it simply isn't the *engine*.
- **Did I dismiss a cheap win?** The two cheap wins (rungs 0–1) are *foregrounded as the recommendation*, not dismissed. The expensive part (rungs 3–4) is deferred, not refused.
- **Is the NO-GO just status-quo bias?** No — the recommendation *adds* two batches (relevance + graph lint) and defines a concrete, measurable path to YES. It refuses only the *premature, ≤5%-eroding* version.

---

## 10. Süleyman'a — basit Türkçe özet ve öneri

**Soru:** "Her komutu otomatik doğru araca bağlayan genel bir orkestra şefi" (Path B) şimdi kurulsun mu?

**Bulduğum 3 önemli gerçek:**
1. **İyi haber:** 45 skill'in hepsi zaten "neyi girer / neyi üretir / neye bağlı" bilgisini içinde taşıyor. Yani "harita" var.
2. **Kötü haber:** O haritanın iki yarısı (kim-üretir / kim-tüketir) birbirini tutmuyor — **%77 oranında uyumsuz** (A "B'yi üretirim" diyor ama B "A'dan beslenirim" demiyor) ve **hiçbir test bunu kontrol etmiyor.** Bugün bu haritaya güvenip plan yapmak = D11'deki "harita doğru görünüyor ama canlı veri farklı" hatası.
3. **Güvenlik:** Tehlikeli işleri durduran duvarlar (push/silme/Indexing onayı + "AI yazdı" karantinası) plandan bağımsız çalışıyor → Path B bunları bedavaya devralır. **AMA** ≤%5 doğruluk-kanıtı (oracle) sadece *bilinen* workflow'ları denetleyebiliyor; serbest bir plan için bu kanıt **bozulur** — bu senin "asla taviz verme" dediğin kural.

**Önerim — motoru ŞİMDİ kurmayalım (HAYIR), ama 2 ucuz adımı hemen yapalım:**

| Seçenek | Ne yapar | Maliyet/Risk | Öneri |
|---|---|---|---|
| **A) İki ucuz adım (ÖNERİM)** | (1) Router'ı düzelt: "aylık bakım nedir?" diye SORUNCA tetiklemesin, sadece "yap/çalıştır" deyince — bugünkü yanlış-alarmı bitirir. (2) Skill haritasını doğrulayan bir denetim ekle (tutarsızlıkları yakalar). | Düşük / Düşük | ✅ **Bunu yapalım** |
| **B) Tam motoru kur** | Her niyeti otomatik plana çeviren genel sistem | Yüksek / Yüksek — ≤%5 kanıtını bozar, %77 uyumsuz haritaya dayanır | ❌ Şimdilik hayır |
| **C) Sadece bekle, hiçbir şey yapma** | — | — | ❌ Yanlış-alarm sürer, harita bozuk kalır |

**Neden A:** Vizyonunun **en değerli yarısı** ("doğru araç kendiliğinden devreye girsin, beni boşuna dürtmesin") aslında ucuz adımla geliyor; pahalı yarısı (serbest plan) ise senin nadiren ihtiyaç duyduğun bir şey — bugün 4 workflow + tekil skill'ler portföyü zaten kapsıyor. Motoru ileride kurmaya değer hale getiren **net bir tetik** tanımladım (§7): ay içinde ≥8 "yeni tip çok-adımlı iş" çıkarsa + harita temizlenirse + oracle uzatılırsa → o zaman C seçeneğine (güvenli melez) geçeriz. Bugün o tetik **kapalı.**

**Senin kararın gereken tek kritik çatal:** Rung 0 + Rung 1'i (router düzeltme + harita denetimi) ayrı bir AMO-tarzı batch olarak **şimdi mi başlatalım**, yoksa **v2.0 sonrası diğer işlerle sıraya mı koyalım**? İkisi de küçük; ben "şimdi, çünkü router yanlış-alarmı her oturumda çıkıyor" derim.

---

## 11. Decision record (for the manager log)

- **O4 re-evaluated with v2.0.0 evidence → NO-GO on the general engine; CONDITIONAL-GO on the rung-0/1 governance batch + a defined trigger (T1∧T3∧T4).** T2 found moot (light-promote already captured shared structure). T3 failed (graph 77% asymmetric / unreconciled). T4 absent (oracle hardcoded to 2 workflows). T1 unknown → instrument.
- **Hard constraints honored:** spine frozen (Path B composes, never edits); ≤5% never claimed for attested steps; safety layer preserved + extended via the plan ledger, never weakened; plugin-agnostic; additive (4 workflows remain the verified baseline).
- **No production code written this session** (research + this doc only).
