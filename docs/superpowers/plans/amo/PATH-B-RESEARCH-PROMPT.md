# Path B Research Charter — General Auto-Orchestration Engine (revisiting the O4 decision gate with shipped-v2.0 evidence)

> **Paste the fenced block below into a FRESH Claude Code session at `/Users/apple/Documents/platinum-seo-engine`.**
> It makes you a research/design session with zero prior context. Your job is to **investigate + design + recommend**,
> NOT to build. Deliverable = a feasibility/design document with a GO / NO-GO / CONDITIONAL-GO recommendation.

```text
You are a fresh RESEARCH + DESIGN session for the Platinum SEO Engine (a Claude Code plugin), v2.0.0 shipped.
Your single task: investigate whether — and if so HOW — to build "Path B", a GENERAL auto-orchestration engine
that, from an arbitrary operator intent, AUTO-DERIVES and sequences the relevant skills / scripts / MCP tools,
instead of today's hard-coded workflows. Produce a design/feasibility DOC with a clear recommendation. Do NOT
write production code, do NOT build it — this is research. Be adversarial and honest; do not hype.

═══════════════════════════════════════════════════════════════════════════════════════════════
0. WHAT THIS IS (the operator's vision, in his words)
═══════════════════════════════════════════════════════════════════════════════════════════════
The operator (Süleyman — non-coder SEO expert, simple Turkish, evidence-driven) wants: "every prompt, when
relevant, should auto-engage the right skill/script/MCP/file; all files interconnected; a conductor (orchestra
şefi) at the head." Today's engine (Path A) realizes a PART of this: a conductor (`/pseo-run`) that drives 4
HARD-CODED workflows. Path B = the rest of the vision: derive the right ordered tool-set for ANY intent.
This was DELIBERATELY DEFERRED. Your job is to determine if it should now be built, and the safest way if so.

═══════════════════════════════════════════════════════════════════════════════════════════════
1. READ FIRST — orient before forming any opinion (the AMO recurring lesson: a wrong ASSUMPTION only
   surfaces when checked against the real code — verify, never assume). Read in this order:
═══════════════════════════════════════════════════════════════════════════════════════════════
- `docs/superpowers/specs/2026-06-05-agentic-orchestration-multiproject-design.md` — the v3 design. Focus:
  §3-§5 (Path A rationale), §7 (phase sketches), §10 **O4** (the promote-to-declarative DECISION GATE — this
  charter is literally "re-open O4 with v2.0 evidence"), §11 (HONEST scope — the ≤5% boundary).
- `docs/superpowers/plans/amo/MANAGER.md` — the BUILD record: the batch table (Faz 0-4 all ✅), decisions
  D1-D17, the **3-O4 row** (the LIGHT-promote that was done instead of the full engine), the "two driver
  shapes" banner, the v2.0.0 release banner.
- Memory `project_amo_initiative.md` (the full narrative) + the `feedback_*` files (the operator's hard
  constraints + communication style).
- The CODE (read, do not edit): `scripts/hooks/intent_router.py` (the CURRENT auto-router — only 1 canonical
  pattern, substring match, NUDGE-not-execute), `scripts/orchestration/workflow_driver.py` (the shared
  data-driver), `scripts/orchestration/workflows/{monthly_maintenance,audit_suite,new_project_setup,
  content_pipeline}.py` (the 4 workflows — the two shapes), `scripts/orchestration/{run_step,verify,committer,
  coverage}.py` (the FROZEN spine — Path B composes it, never edits it), `scripts/hooks/{outward_action_gate,
  denetci,ai_disclosure_rescan}.py` (the safety layer), `scripts/reporting/orchestration_metrics.py` (the
  ≤5% correctness oracle).

═══════════════════════════════════════════════════════════════════════════════════════════════
2. WHAT EXISTS TODAY (Path A — shipped v2.0.0, live-proven via D11)
═══════════════════════════════════════════════════════════════════════════════════════════════
- A conductor `/pseo-run` driving 4 HARD-CODED ordered workflows (monthly/audit/setup/content). Each step:
  the MODEL makes the MCP call → drops provenance-stamped raw JSON → an existing transform CLI runs → CODE
  verifies (identity+content+freshness gate, `verify_raw_drop`) → commits → a coverage record. TWO driver
  SHAPES emerged: a DATA-driver (3 workflows, shares `workflow_driver`) + an ARTIFACT-driver (content).
- A 1-pattern intent ROUTER (`intent_router.py`): recognizes ONLY "aylık bakım"/monthly via substring match;
  NUDGES (injects a `/pseo-run monthly <slug>` suggestion) — it does NOT execute. The other 3 workflows + all
  individual skills are invoked EXPLICITLY.
- The SAFETY layer: per-session consent gate (blocks push/delete/POST/sitemap/Indexing unless approved),
  AI-disclosure quarantine, the denetçi Stop-hook (forces a declared-but-unrun workflow), the correctness
  oracle (the trustworthy ≤5% structured-error number, independent of the self-reported verdict).
- **Path A was a DELIBERATE choice** (operator + a 9-agent adversarial review of the original design, 51
  findings): hard-coded sequences first; NO general DAG engine, NO auto-derived capability graph. Faz-3
  VINDICATED it — two distinct driver shapes proved a single universal engine would over-abstract. The O4
  gate says: promote to the general engine ONLY if a 4th distinct workflow proves the abstraction earns its keep.

═══════════════════════════════════════════════════════════════════════════════════════════════
3. THE CONCRETE PROBLEM (fresh LIVE evidence — use this, it is the motivating data)
═══════════════════════════════════════════════════════════════════════════════════════════════
In a recent session the router + denetçi demonstrated the precision gap LIVE: the operator MENTIONED "aylık
bakım" while ASKING A QUESTION (not requesting a run); the router's naive substring match fired → wrote a
"declared" monthly intent marker → at turn-end the denetçi (correctly, by its rules) NAGGED "you declared
monthly but didn't run it." A double false-positive. It was SAFE (router only suggests, denetçi only nags,
nothing executed, no budget spent) but it exposes the core unsolved problem Path B must crack:
**relevance detection** — distinguishing "mention/discuss" from "intend/request", and mapping a free-form
intent to the CORRECT tool-set, precisely enough to act on. Naive matching engages on mere mention.

═══════════════════════════════════════════════════════════════════════════════════════════════
4. RESEARCH QUESTIONS (answer each with evidence + a recommendation)
═══════════════════════════════════════════════════════════════════════════════════════════════
Q1 — DERIVATION. How would a general engine map an arbitrary intent → the correct ORDERED tool-set? Evaluate +
   SCORE these options (and any you find better):
   (A) Declarative capability/dependency graph: each skill DECLARES its inputs/outputs/preconditions
       (machine-readable metadata); the engine resolves + topo-sorts a plan. (How much metadata exists today?
       What would each of the ~45 skills need to declare? Is the graph acyclic + complete?)
   (B) LLM-planner + deterministic validator: the model proposes a sequence, a code validator checks it
       against the capability registry + the gates before executing. (Where does the ≤5% guarantee go when
       the PLAN itself is model-generated?)
   (C) Hybrid: a curated capability graph for the known core + LLM gap-filling at the edges.
   (D) THE HONEST BASELINE TO BEAT — DON'T build the engine: just expand Path A (add more canonical router
       patterns [it is data-driven — 1 dict entry per workflow] + author more hard-coded workflows as needed).
       Quantify: how many more workflows/patterns would cover, say, 80% of real operator intents? Is the
       general engine worth it vs this?
Q2 — RELEVANCE. How to PRECISELY detect when a tool/skill is relevant to an intent (the mention≠request
   problem)? Options: an intent grammar / imperative-mood detection / confidence thresholds / an explicit
   operator-confirm step before assembling. What false-positive rate is acceptable, and who bears the cost?
Q3 — SAFETY (the hardest — this likely decides GO/NO-GO). The v2.0 guarantees hold because each step has a
   DETERMINISTIC gate (`verify_raw_drop` identity+content+freshness + silent-skip) and the oracle reconciles
   KNOWN sheets per known workflow. For a DYNAMICALLY-assembled sequence: (a) can each auto-selected step
   still be code-verified, or do arbitrary steps collapse to model_attested? (b) can the oracle reconcile
   arbitrary outputs it has no STEPS table for? (c) how do the consent gate + denetçi + AI-disclosure
   quarantine extend to steps the engine chose at runtime? An engine that erodes the ≤5% backstop or the
   consent walls is a NON-STARTER (operator hard constraint).
Q4 — HONEST SCOPE (spec §11). Of "any operator intent", what fraction is genuinely code-verifiable (structured
   ingestion/audit) vs model_attested (analysis/content/judgment)? Be brutally honest — the general engine
   does NOT make a model_attested step verifiable; it just sequences it.
Q5 — WORTH IT? Adversarial synthesis: is Path B worth its risk + cost vs Path-A expansion (option D)? Define
   the CONCRETE promote-trigger that flips O4 (e.g. "≥N operator intents/month fall outside the hard-coded
   set" or "≥2 workflows share ≥K edges a graph would dedupe"). If the trigger isn't met, the honest answer
   is NO-GO (keep expanding Path A) — say so.

═══════════════════════════════════════════════════════════════════════════════════════════════
5. PRINCIPLES / HARD CONSTRAINTS (absolute — a design that breaks these is rejected)
═══════════════════════════════════════════════════════════════════════════════════════════════
- The spine (`run_step`/`verify`/`committer`/`coverage`) is FROZEN — Path B COMPOSES it, never edits it.
- The safety layer is PRESERVED + extended, never weakened: per-session consent for outward actions;
  "AI-written" NEVER in visible HTML; append-only state (events/consent/cost ledgers — never os.replace a
  log); the ≤5% oracle backstop must still apply to every code_verified step.
- Plugin-agnostic: NO CMS/site/project specifics in engine logic.
- Path B is ADDITIVE / a PROMOTION — Path A's 4 proven workflows remain the verified baseline; the engine
  does not delete them. Don't re-open settled decisions D1-D17 without NEW evidence.
- Honest ≤5%: never claim a model_attested step is structurally verified.
- If it proceeds to BUILD later: manager/worker model (fresh Opus-4.8 1M-context worker batches; NO Task/Agent
  tools — they fail here; TDD RED-first; scope-locked; manager independently re-derives each batch's claim).

═══════════════════════════════════════════════════════════════════════════════════════════════
6. METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Read everything in §1. Ground EVERY claim in the real code/spec (quote file:line). The AMO build's biggest
   bugs (D11) came from assumptions that were never checked against reality — do not repeat that.
2. For each design option (A-D), build the strongest case FOR and AGAINST. Score on: feasibility, safety-layer
   compatibility, ≤5%-scope honesty, operator-value, build-risk, and reversibility.
3. Argue the NULL hypothesis hard (option D — "don't build it"). Path B must EARN its existence against it.
4. Synthesize into the deliverable with an explicit, defensible recommendation.

═══════════════════════════════════════════════════════════════════════════════════════════════
7. DELIVERABLE
═══════════════════════════════════════════════════════════════════════════════════════════════
Write `docs/superpowers/specs/2026-06-XX-path-b-general-orchestration-research.md` containing:
  - Executive summary + the GO / NO-GO / CONDITIONAL-GO recommendation (1 paragraph, up front).
  - The 4-5 design options scored (table) — INCLUDING option D (Path-A expansion) as the baseline.
  - The SAFETY MODEL for dynamic sequences (the Q3 analysis — the load-bearing section).
  - The HONEST-SCOPE analysis (Q4 — what % is verifiable vs attested).
  - The concrete O4 promote-trigger (Q5) — the measurable signal that flips the decision.
  - IF GO/CONDITIONAL: a phased roadmap of SMALL first batches (e.g. "capability-metadata schema for skills"
    → "a read-only planner that PROPOSES a plan + a validator, behind a hard operator-confirm, executing
    NOTHING" → ... ) that de-risks incrementally — never a big-bang engine.
  - A short "recommended next step" for the operator (in simple Turkish, since he reads it).

Present the recommendation to the operator in simple Turkish (2-3 options + your recommendation) before/with
committing the doc. Remember: he decides; surface only genuinely critical forks. Do NOT build production code
in this session — research + the doc only.
```
