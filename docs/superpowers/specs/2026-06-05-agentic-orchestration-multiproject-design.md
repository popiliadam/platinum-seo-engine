# Agentic Orchestration & Multi-Project Autonomy — Design Spec **v3** (review-hardened)

> **Status:** DRAFT — awaiting Süleyman approval
> **Date:** 2026-06-05
> **Codename:** AMO (Autonomy & Multi-project Orchestration) — candidate **v2.0** milestone
> **History:** v1 (intent-driven manual diagnosis) → v2 (plan-and-verify reframe) → **v3 (adversarial review: 9 agents, 51 findings, 7 blind-spots; build-philosophy = "Path A / start simple")**
> **Build philosophy (operator-chosen):** start with hard-coded ordered sequences for 3-4 known workflows; NO declarative DAG engine and NO auto-derived capability graph yet — promote to a general engine only if a 4th workflow proves the abstraction earns its keep. Deliver "the system knows all its parts" cheaply via two targeted lints, not a graph.

---

## 0. Özet (Süleyman için — Türkçe)

**Ne yapıyoruz?** İki şikâyetini çözüyoruz: (1) iş yaparken doğru skill/MCP çoğu zaman devreye girmiyor, (2) aynı anda tek projede çalışabiliyorsun. Çözüm: **otonom bir orkestrasyon + denetçi + paralel-proje katmanı.**

**Bu plan nasıl sağlamlaştı?** İlk taslağımı (v1→v2) **9 ajanlı düşmanca incelemeden** geçirdik. 51 bulgu çıktı; bazıları kritikti (örn. bağlama mekanizmam Mac app'te hiç çalışmıyordu, güvenlik geçitleri yoktu). Hepsini bu sürüme işledim. İnceleme ayrıca "fazla mühendislik yapma, basit başla" dedi — **sen de basit yolu seçtin (Path A).**

**Path A ne demek?** Koca bir genel "iş akışı motoru" kurmuyoruz. Bilinen 3-4 işi (aylık bakım, yeni proje kurulumu, içerik hattı, audit) **düz sıralı Python betikleri** olarak kuruyoruz. "Sistem tüm parçalarına hakim olsun" isteğini ise iki ucuz denetimle veriyoruz: (1) her skill gerçekten beyan ettiği MCP'leri çağırıyor mu, (2) `events.jsonl`'daki gerçek çağrılar beyanla uyuşuyor mu. Genel motora ancak 4. iş bu soyutlamayı hak ederse terfi ederiz.

**Ne kazanacaksın (6 faz):**

| Faz | Kazanım | Risk |
|---|---|---|
| **0** | Her oturum (VSCode penceresi VEYA Mac app sohbeti) bir projeye kilitli — **session_id dosyasıyla**, env değişkeniyle değil; karışma yok + gizli veri-hataları kapanır + güvenli paralel yazma | Düşük |
| **1** | "Aylık bakım" tek mesajla uçtan uca, doğru skill/MCP'ler **garantili+doğrulanmış** çalışır (kimlik+içerik kontrolü) | Orta |
| **2** | **Güvenlik geçitleri** (Indexing/publish/push/exfil reddi + consent defteri) + **doğruluk kanıtı** (sahte-yeşil'i engeller) — orkestratörle BİRLİKTE | Orta |
| **3** | Aynı otomasyonu diğer hatlara yay + "hakimiyet" denetimleri | Düşük-Orta |
| **4** | 10 projede paralel + **maliyet tavanı + kill-switch** + (opsiyonel, varsayılan KAPALI) zamanlanmış otonom | Yüksek |

**Bozulunca ne göreceksin?** Sen kod bilmiyorsun; o yüzden her blok/hata, basit Türkçe **tek-satır çözüm komutu** taşıyacak ("Tamamlamak için yaz: `/pseo-run monthly alpha --resume`"). Mac app'te terminal olmadan da çalışır.

**Dürüst sınır:** ≤%5 hata hedefi **yapısal işlerde** (veri çekme/işleme/rapor) tutturulur — ve bunu *kanıtlayan* bağımsız bir doğruluk-oracle'ı var. **İçerik kalitesi** (blog yazımı) orkestrasyonla garanti edilmez; o ayrı bir kapı (model + içerik-validatörü) ile ölçülür. Bu ayrımı baştan koyuyoruz.

Aşağısı teknik gövde (İngilizce, repo standardı).

---

## 1. Goals, non-goals

- **G1 Guaranteed engagement** — a stated intent runs every step the job requires, deterministically; a coverage record proves what ran.
- **G2 Auditor (denetçi)** — a skipped/failed required step is detected and forced to completion (or RED-escalated) before turn-end.
- **G3 Multi-project parallelism** — N sessions, each bound to a distinct project, never cross-contaminating state/audit/output — across **VSCode multi-window, the Claude Desktop Mac app, AND CLI**.
- **G4 Smart autonomy WITH enforced gates** — read/compute/draft auto-flows; irreversible/outward actions (Indexing-API submit, publish, `git push`, exfil, oversized DFS) are **machine-denied** unless consent + prereqs. *Gates are built ALONGSIDE the orchestrator, never deferred — autonomy without them is unsafe.*
- **G5 Measurable ≤5% on structured workflows** — error rate measured by an **independent correctness oracle** (reconcile master.xlsx vs raw provenance), not by the orchestrator's own self-reported "done".
- **G6 No regression** — the full existing pytest suite stays green (record exact baseline N at each phase start; end ≥ baseline).

**Non-goals:** a generic user-authored workflow engine; replacing the skill system (orchestrator invokes/verifies, doesn't reimplement); removing manual control; CMS/plugin specifics in the engine (plugin-agnostic preserved).

---

## 2. Verified constraints & corrected facts (BINDING — from code, 2026-06-05)

- **C1 — within a project: parallel-read / single-writer.** `events.jsonl` append is safe (blocking `LOCK_EX`, `events_writer.py:319`). `master.xlsx` commit is fail-fast `LOCK_EX|LOCK_NB` with **no retry** → concurrent second writer silently loses its write (`transaction.py:374-377`, unused `import time:42`). Rule: fan out reads/compute in parallel; funnel ALL master.xlsx writes through one serialized committer.
- **C2 — binding MUST be a session-id marker FILE, not an env var.** Proven: `PSEO_WORKSPACE_ROOT` is **absent** from the live hook/session env (`env|grep PSEO` empty); `.env` is sourced ONLY into MCP subprocesses (`.mcp.json` `set -a; source .env`), never into hooks. In the **Claude Desktop Mac app** there is no per-window shell, so `export PSEO_SESSION_PROJECT` is impossible → env-var binding is structurally unusable in 1 of 3 target environments. Corrected mechanism: a marker file keyed by the **Claude session_id** the harness passes to every hook on stdin; workspace root persisted editor-independently; engine root from **`CLAUDE_PLUGIN_ROOT`** (set in all environments), never from cwd/open-folder. (The engine repo and the workspace `projects/{slug}/` are SIBLING dirs — the editor's open folder maps to no project.)
- **C3 — hooks gate/nudge, never invoke.** Stop hook can `decision:block` + force-continue (8-block cap, `stop_hook_active`); PreToolUse can `deny`; both inject model-visible `reason`/`additionalContext`. No hook can invoke a skill/tool/subagent.
- **C4 — subagents FAIL in this project.** The session MCP registry is too large ("Prompt is too long") so `Task`/`Agent` tools error (recorded in 8 existing worker prompts). Therefore: (a) the orchestrator has **no `kind:agent` step type** — judgment steps are model-inline checkpoints recorded as `model_attested`, never `code_verified`; (b) every AMO worker prompt carries a hard "NO Task/Agent — work inline" rule; (c) the full plan-and-verify loop **cannot run in CI** (no model, no MCP, no subagent) → a stub harness + live acceptance script are required (§9).
- **C5 — master.xlsx writes live in SKILL.md prose, not callable modules.** Transforms are pure (`quickwins_transform.py:21` "the skill orchestrator owns transaction.append"); the actual `transaction.append/replace` runs inside model-executed SKILL.md Python blocks (`gsc-pull/SKILL.md:204-210`). So "orchestrator invokes `python3 -m step`" only computes rows — the **commit must be relocated** into a callable committer the orchestrator owns.

**Corrected facts the review caught (do not repeat v2's errors):**
- A resumable **`paused`** state ALREADY EXISTS (`workflow-run.schema.json` status enum; `_ALLOWED_TRANSITIONS` has `running→paused`, `paused→running`). Map external-failure onto `paused` — do NOT invent a `blocked` state (saves a schema bump).
- `failure_reason.code` real enum = `[validation_error, mcp_error, budget_exhausted, user_rejected, timeout, internal_error]`. The v2 codes (`mcp_unreachable/gsc_outage/dfs_budget_exhausted`) **do not exist** — add an additive boolean `failure_reason.external` discriminator instead.
- `event_type` is a **closed exactly-12 enum** with 3 tests asserting the count + description cites + `additionalProperties:false`. `workflow_coverage` **cannot** be event_type #13 → write coverage to a dedicated `_state/coverage/<run_id>.json`, OUT of events.jsonl.
- CI frontmatter/schema validation is the **schema-validate step** (`ci.yml:39-40`), not "Step 7".
- **10 projects already exist** on disk (adstark, aluminumstation, bigcat, dentnotion, eykom, iwallet, lastiksa, noran, vento, miningaa); `ACTIVE_PROJECTS_MAX=12` is copy-pasted across 6 reporting files + maxItems=12 in 3 schemas. "3-5 projects" is the demo; the real portfolio is 10 and climbing toward the cap.

---

## 3. Target architecture (v3 — Path A, simplified)

```
SEN (a session bound to project "alpha" via session-id marker file)
  │  "alpha'da aylık bakım yap"
  ▼
[L1] INTENT ROUTER (UserPromptSubmit hook, ONE voice per prompt)
     Tier-1 canonical match -> inject "invoke /pseo-run monthly alpha" + write intent_declared
       marker (session_id, turn_id, intent_id) AND SUPPRESS the whats-next advisory line
     Tier-2 fuzzy / >=2-workflow collision -> whats-next advisory ONLY, NO marker
  ▼
[L2] ORCHESTRATOR = a hard-coded ORDERED SEQUENCE (plain Python per workflow; no DAG engine)
     For each step the recipe interleaves:
       (model) make THIS MCP call -> drop raw artifact at the ORCHESTRATOR-DICTATED path,
               stamped {run_id, slug, site_url, window, tool, fetched_at}   [model-owned]
       (code)  run_step.py: VERIFY artifact identity+content+freshness (hard-fail on mismatch)
               -> run the pure transform -> COMMIT via single committer (transaction.replace,
               keyed on run_id/window = idempotent) -> record coverage to _state/coverage/<run_id>.json
     Writes serialize through ONE committer holding a BLOCKING lock (bounded wait -> paused on timeout)
     Cross-project = fully parallel (disjoint locks); intra-job parallel = only batch-N generation
  ▼
[L3] DENETÇİ (Stop hook, extends existing stop.json chain; no-op unless a turn has an intent_declared)
     checks: (a) every current-turn intent_declared reached a running/done job  [non-start gate]
             (b) coverage (_state/coverage) satisfied for the executed steps
             (c) failure_reason.external == true -> map run to PAUSED + RED report + ALLOW turn-end
                 else missing-work -> decision:block + a Turkish one-line fix command
  ▼
[L4] GATES (PreToolUse, 2nd block — built WITH the orchestrator, not after)
     deny (git push | rm/unlink | curl/POST | mcp__*submit*/index URL_UPDATED | oversized DFS)
       unless an append-only hash-chained consent ledger entry (run_id, action, target_hash) exists
     AI-disclosure: post-write content-SURFACE rescan of outputs/blog/**/*.html (block-and-revert),
       so Bash cp/heredoc/python -c cannot bypass the Write/Edit-only validator
  ▼
[ORACLE + OBSERVABILITY] reconcile master.xlsx rows vs raw-provenance per run_id (independent of
     self-reported status) -> THE ≤5% number; + first-pass / retry / coverage-miss metrics
  ▼
Sana: özet + kanıt + (blok varsa) tek-satır Türkçe çözüm komutu

Pencere/sohbet 2..N -> other projects, fully parallel. SF crawl = single-window (shared singleton).
```

**Per-step `verification_class`:** `code_verified` (structured Python steps — gate is identity+content) vs `model_attested` (judgment steps like blog generation — orchestrator records they ran but does NOT verify quality; the content-validator gate + QA loop bound quality separately). The coverage record carries this class so the metric NEVER counts an attested step as verified.

---

## 4. "Knows all its parts" — delivered WITHOUT the graph (Path A)

The capability-graph value (catching parts the system uses but doesn't track) is delivered by two **targeted, cheap** checks instead of a full auto-derived graph:

1. **`body ⊆ declared` MCP lint** (governance/CI): parse each SKILL.md body for `mcp__server__tool` AND native `sf_*` (SfMcpClient) calls; fail if any tool is invoked in prose but missing from that skill's `mcp_tools.required/optional`. (Catches the 6 active skills with undeclared MCP deps + the `sf_load_crawl` that isn't even in the registry — fix the registry too.)
2. **`observed ⊆ declared` reconciliation** (runtime/oracle): `events.schema.json` already records `source.mcp_tool` on every provenance row. For each run, collect the observed MCP-tool set and assert it ⊇ the workflow's declared-required set; declared-but-not-observed = coverage miss (block), observed-but-not-declared = AMBER feeding back into lint #1. This turns the existing append-only log into the deterministic MCP-skip detector.

These two give the "mastery" Süleyman asked for at ~a fraction of the graph's cost and risk. The full auto-derived graph + declarative workflow schema is **deferred to Phase 3+** and built ONLY if a 4th workflow proves it earns its keep.

---

## 5. Revised phase roadmap (build plan)

| Phase | Worker batches | Deliverable | Hard prerequisites |
|---|---|---|---|
| **0** | 0a, 0b | Binding substrate (session-id marker, `/pseo-bind`, resolver split, audit+content-gate fix, cross-env hook probe) **+** shared-resource safety (portfolio.json lock, backup-rotation fix) **+** **blocking master.xlsx lock** (its own atomic batch — must precede ANY parallel writer) | — |
| **1** | 1a, 1b, 1c, 1d | 1a schema migrations (coverage file shape, `failure_reason.external`, reuse `paused`); 1b ordered-sequence runner + **committer relocation** + identity-content verify (idempotent `replace`); 1c intent router (one-voice + marker lifecycle); 1d reference workflow `monthly-maintenance` + `/pseo-run` + operator-remediation surface | 0 |
| **2** | 2a, 2b, 2c | 2a consent ledger (schema + append-only writer); 2b PreToolUse outward-action + AI-disclosure-surface gates; 2c denetçi Stop-hook (reuse paused) **+ correctness oracle** | 1 |
| **3** | per-workflow | Replicate to new-project-setup / content-pipeline / audit-suite; ship the two "mastery" lints (§4); **promote to declarative engine + graph ONLY if earned** | 1, 2 |
| **4** | 4a, 4b | Portfolio cross-project fan-out + portfolio cost/quota ledger + kill-switch; scheduler **default OFF**, explicit per-cadence consent | 0-3 |

Dependency note: the **failure-taxonomy + coverage shape (1a)** and the **consent-ledger schema (2a)** are hard prerequisites the denetçi/gates key on — they are scheduled BEFORE their consumers, not as later details.

---

## 6. Phase 0 — detailed design

**Goal:** every session (VSCode window, Mac-app conversation, or CLI) binds to one project via a session-id marker file; per-session correct audit/content/consent attribution; safe parallel writes. Backward-compatible: marker unset → today's `active.json` behavior.

### 6.1 Binding substrate (batch 0a)

- **`/pseo-bind <slug>`** (reuse `/pseo-active`'s atomic tempfile+fsync+os.replace + slug validation): writes `$PSEO_WORKSPACE_ROOT/_state/sessions/<session_id>.json = {active_project, bound_at}`. session_id comes from the hook/command payload the harness provides in all environments. Prints a confirmation banner. NO `export`.
- **Workspace root persistence:** `/pseo-bind` and `/pseo-init` persist `{workspace_root}` to an editor-independent `~/.config/pseo/config.json` (and/or `shared/config.json`); hooks resolve workspace root from there + `CLAUDE_PLUGIN_ROOT`, never `os.environ`. Replace the hardcoded `~/.claude/plugins/cache/...` engine-root fallback (`pseo-status.md:21,29`) with `${CLAUDE_PLUGIN_ROOT}`.
- **Resolution chain (single helper, two contracts):** `resolve_session_project(workspace, arg, *, strict) -> str|None` = `explicit arg → session marker(by session_id) → active.json`. `strict=True` raises on unbound (for explicit commands, preserves `dump_workspace._resolve_slug` contract); `strict=False` returns None (for advisory consumers). Profile derivation is a thin wrapper calling it with `strict=False`. (Fixes the v2 "one helper, incompatible contracts" error.)
- **Audit + content-gate fix:** `post-tool-use.json` audit emission and `validate_content_write.py:_resolve_profile` resolve project from the **session marker FIRST**, never global `active.json`. Add a regression test: two sessions with the SAME process env but DIFFERENT session markers → events land under the correct per-project `events.jsonl`.
- **Cross-environment hook probe (DURUR gate):** a trivial hook writing `{event, session_id, cwd, has(CLAUDE_PLUGIN_ROOT), stdin_keys}` to a probe log; run once each in VSCode / Mac-app / CLI and diff. **DURUR** if any gate-bearing hook does not fire identically with the same stdin shape + CLAUDE_PLUGIN_ROOT. Do not assume desktop == CLI.

### 6.2 Shared-resource safety (batch 0a)

- **`portfolio.json` lock:** wrap its read-modify-write in blocking `flock(LOCK_EX)` (or convert to append-only JSONL). It is workspace-global and written by `init-project` with no lock today.
- **Backup rotation fix:** `_rotate_backups` (`transaction.py:448-461`) must scope to `master-*.xlsx` (the same glob the F-22 invariant + `_backups_recent` use), so `.empty` markers/tempfiles never displace real snapshots. Test: seed `.empty` + 7 xlsx → all 7 xlsx survive.
- **Two-sessions-same-project guard:** a per-project `_state/session.lock` (owner session_id + ts) acquired at a write-workflow start; a second session resolving the same slug for a WRITE warns/denies rather than silently coexisting.

### 6.3 Blocking master.xlsx lock (batch 0b — its own atomic batch, MUST precede any parallel writer)

- Add an `acquire_blocking=True` path to `transaction._acquire_lock`: `flock(LOCK_EX)` with a **bounded fixed timeout** (e.g. 30s) + a clean typed `LockTimeout` (NOT jittered exponential backoff — the review flagged that as over-engineering for a 1-operator tool). On timeout → transition the run to **`paused`** (operator decides), never a swallowed `LockHeldError`.
- Test: two concurrent writers both succeed serially under the blocking path (no lost write); a held lock past timeout yields `LockTimeout` → `paused`.

### 6.4 Phase 0 DURUR

Any existing test regresses; audit/content/consent still reads global `active.json`; the cross-env probe shows a gate-bearing hook firing differently in any environment; the blocking lock can still silently drop a write.

---

## 7. Phases 1-4 — design sketches (full specs authored when reached)

### Phase 1 — orchestrator + reference workflow (batches 1a-1d)
- **1a (schema-first, frozen first):** `_state/coverage/<run_id>.json` shape (run_id, steps[{name, verification_class, status, observed_mcp[], input_count, scored_count}], required_satisfied, verdict); additive `failure_reason.external: bool`; confirm `paused` reuse + the `(running→paused)`/`(paused→running)` edges suffice for external-failure-allow-end. NO `event_type` change. Paired drift/cite tests.
- **1b (runner + committer):** `scripts/orchestration/run_step.py` (verify artifact identity+content+freshness → pure transform → `committer.commit(sheet, rows, run_id)` via `transaction.replace` keyed on run_id/window → write coverage). Relocate the reference workflow's 3 skills' writes out of SKILL.md prose into the committer. **Identity gate:** raw drops carry `{run_id, slug, site_url, window, tool, fetched_at}`; the transform HARD-FAILS (not silent-skips) on slug/site/window mismatch + stale mtime + a high silent-skip ratio (`input_count` vs `scored_count`). Orchestrator dictates the raw path (embeds run_id) so a model-misnamed/wrong-project drop simply isn't where the gate looks.
- **1c (intent router):** one-voice UserPromptSubmit (Tier-1 suppresses whats-next + writes marker; Tier-2 advisory only). Marker lifecycle: keyed `(session_id, turn_id, intent_id)`; Stop gate evaluates only current-turn markers; `intent_superseded` retraction on correction; never block on a cross-turn (older) marker.
- **1d:** `workflows/monthly-maintenance` as an ordered Python sequence (gsc-pull → quick-wins + content-decay → single committer → monthly-report) + `/pseo-run <workflow> [slug]` wrapper + the operator-remediation surface (every block/RED renders a Turkish one-line fix command via `additionalContext`).

### Phase 2 — gates + oracle (alongside, batches 2a-2c)
- **2a:** `_state/consent.jsonl` schema — append-only, **hash-chained** (prev-hash per line); a recorder; paired tests. Wire `check_append_only` logic into a PreToolUse gate (deny non-append edits to `_state/**/*.jsonl` + forward-only status flips to `_state/workflows/*.json`).
- **2b:** 2nd PreToolUse block — Bash-parse `git push`/`rm`/`curl|wget POST`; concrete MCP submit tools (`mcp__gsc__submit_sitemap`, future indexing `URL_UPDATED`); oversized DFS — default-deny unless a consent entry for `(run_id, action, target_hash)` exists. AI-disclosure → PostToolUse content-surface rescan of `outputs/blog/**/*.html` (block-and-revert). Secret gate: scan the literal pending bytes (incl. gitignored targets), not just git-enumerated files. A drift F-rule fails if a skill declares an outward MCP tool not covered by a gate matcher.
- **2c:** denetçi Stop-hook (extends existing `stop.json` chain; `stop_validation.py` untouched; no-op unless current-turn intent_declared exists; respects 8-block cap). **Correctness oracle:** `scripts/reporting/orchestration_metrics.py` re-derives expected row identities/counts from raw-provenance headers and diffs against master.xlsx per run_id; error rate = (reconcile-mismatch runs)/(total) — grounded in output truth, not self-report.

### Phase 3 — replicate + mastery lints
- `workflows/{new-project-setup, content-pipeline, audit-suite}` as ordered sequences. Ship the two §4 lints (`body⊆declared`, `observed⊆declared`) + fix the registry (`sf_load_crawl`). **Decision gate:** if a 4th distinct workflow shows real shared-edge needs, promote to the declarative engine + auto-graph; else keep hard-coded sequences.

### Phase 4 — portfolio + cost ceiling + scheduler (off by default)
- `/pseo-run-portfolio` cross-project fan-out (disjoint locks). **Portfolio cost/quota ledger** under `shared/` (atomic reserve-then-confirm; GSC call-count vs quota, DFS credits vs daily pool, image spend) with a **hard global ceiling + kill-switch** (ceiling hit → runs → `paused`, not silent degrade). `/pseo-status --portfolio` triage table (run_id, status, missing_steps, external vs internal) + a written recovery runbook. Scheduler **default OFF**, explicit per-cadence consent, projected daily cost shown before arming. Per-step mid-job budget preflight (not just job-start).

---

## 8. Cross-cutting first-class deliverables (not afterthoughts)

- **Operator remediation surface** — every block/RED carries a structured `{missing[], one_line_fix_command, why_turkish}`; rendered as model-visible `additionalContext`, never UI-only `systemMessage`. A non-coder in the Mac app (no terminal) must always have one copy-pasteable next action. Phase-1 DURUR.
- **E2E stub harness** — a fixture that drops canned raw inbox JSONs (correct / stale / wrong-project / truncated / MISSING) and asserts the gate verdict + coverage + denetçi decision for each, exercising the full `run_step` path WITHOUT a live model. Plus a **live acceptance checklist** run once per environment per phase (trigger intent → observe gate stop on a deliberately-skipped MCP → observe block → observe consent deny). Autonomy (Phase 4) MUST NOT arm until the loop is demonstrated live in all 3 environments.
- **Correctness oracle** — see §7 Phase 2; the only trustworthy source of the ≤5% number.
- **Self-upgrade versioning** — stamp every `workflows/*.json` + any generated artifact with the engine version; orchestrator asserts `artifact_version == plugin.json version` at run start (fail-loud "regenerate" on mismatch). Add these to the `version_bump` 5-file set so an engine bump can't leave them behind (closes the known plugin-cache-stale class).
- **ACTIVE_PROJECTS_MAX consolidation** — lift the constant into ONE module sourced from schema `maxItems`; kill the 6-file copy; document the 12→N headroom policy (raise via schema-first migration with paired reporting-skill tests, OR an "active subset" of K-of-N in autonomous rotation). The scheduler iterates the ACTUAL on-disk count (10), not "3-5".

---

## 9. Build model (manager / worker)

- **This = manager session.** Build via fresh **Opus 4.8 1M-context worker sessions**, one self-contained prompt per batch (0a, 0b, 1a … 4b). Süleyman relays each worker's REPORT back to the manager; manager verifies (code-review + verifier + suite-green) before dispatching the next fresh worker.
- **Every worker prompt MUST:** be self-contained (1M context → inline the full files it touches + exact acceptance criteria + DONE/DURUR); **NO Task/Agent tools — work inline** (C4); baseline-first (record exact pytest N, end strictly ≥); TDD (RED→GREEN→REFACTOR); scope-locked (file-disjoint batch; out-of-scope → STOP + report); schema-first for any schema change (4-way sync: code fn + rule text + severity + 8-value category enum, run `test_cross_sheet_invariants_sync.py` before report); **no commit** (manager commits after review).
- **Worker checkpoint contract (build resumability):** each worker writes an append-only `PROGRESS.json` (phase, tasks-done, tests RED/GREEN, files-touched, baseline N) at every task boundary and makes **WIP commits on an isolated worktree/branch** (using-git-worktrees) — so a worker dying mid-batch is resumable from checkpoint, not full-redo.

---

## 10. Risks & open questions (v3)

- **O1 — `/pseo-bind` session_id source.** Confirm the exact field name + presence of session_id in UserPromptSubmit/PreToolUse/PostToolUse/Stop payloads across all 3 environments (the cross-env probe, §6.1, resolves this empirically before any binding code).
- **O2 — committer relocation blast radius.** Moving writes out of SKILL.md prose changes ~3 skills in Phase 1 and more in Phase 3; each must keep its existing tests green. Scope per-workflow.
- **O3 — consent-ledger UX for a non-coder.** How does Süleyman "sign" consent in the Mac app (no terminal)? Likely a `/pseo-approve <run_id>` command writing the ledger entry. Designed in Phase 2a.
- **O4 — promote-to-declarative trigger.** Define the concrete signal (e.g. ≥2 workflows sharing ≥N edges, or operator-authored workflows requested) that flips Phase 3 from "more hard-coded sequences" to "build the engine + graph".
- **O5 — GSC/DFS quota modeling.** Real daily quotas must be entered into the cost ledger (Phase 4) before the scheduler is armed.

---

## 11. Honest scope & success criteria

- **≤5% holds for structured workflows** (gsc/dfs/scrapling ingestion, discovery, audit, reporting) — correctness verified by the oracle (identity+content gate + reconcile-vs-provenance), NOT by self-reported status.
- **Content-quality steps are `model_attested`, not `code_verified`** — orchestration guarantees they RAN and produced an artifact; quality is bounded by the model + the content-validator gate + the QA loop, and measured separately. A measured 0% structured-error is meaningful ONLY because the oracle is independent of run status.
- **Success = ** N sessions bound to N projects across VSCode + Mac app + CLI with zero cross-attribution (proven by the multi-session test); `/pseo-run monthly <slug>` runs end-to-end with every required step gated by identity+content; the denetçi blocks an incomplete job with a Turkish fix-command and allows-but-flags an external-failure (`paused`); every irreversible action is denied without consent; the oracle reports structured-error ≤5%; the existing suite stays green at every phase boundary.

---

## 12. Approval checklist (for Süleyman)

- [ ] Path A (hard-coded sequences now, graph deferred, "mastery" via 2 lints) — confirmed ✅ (2026-06-05).
- [ ] Architecture v3 (session-id binding; gates+oracle alongside; verify=identity+content; reuse `paused`; coverage out of events.jsonl) — onaylıyor musun?
- [ ] Revised phasing 0 / 1a-d / 2a-c / 3 / 4 + worker build model (no-subagent, checkpointed) — onaylıyor musun?
- [ ] Open questions O1-O5 — kabul mü, tartışalım mı?

On approval: commit this spec, then author the **Phase 0 (batch 0a) worker prompt** (self-contained, TDD, no-subagent) for a fresh Opus-1M worker; you relay its report back; I verify; we proceed batch by batch.

---

## Appendix A — adversarial review provenance

9-agent workflow (8 dimension critics + blind-spot), 51 findings, verdict **CONDITIONAL GO**. The 5 must-fixes (all folded into this spec): (1) session-id binding substrate; (2) outward-action + consent gates built alongside; (3) coverage→`_state/coverage` + `failure_reason.external` + reuse `paused`; (4) identity+content verification + append→replace fix; (5) honest Phase-0/1 scope split + defer graph. Blind-spots folded in: operator-remediation surface, 10-project/cap-12 headroom + portfolio cost ceiling, e2e stub harness, self-upgrade versioning, one-voice intent router. One critic finding corrected as factually wrong (a usable `paused` state already exists — no new `blocked` state). Full findings: workflow run `wf_527271b3-931`.
