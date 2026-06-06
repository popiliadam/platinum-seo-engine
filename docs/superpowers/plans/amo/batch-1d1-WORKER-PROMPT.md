# AMO Batch 1d.1 — Reconcile Driver + /pseo-run with the REAL transform CLIs (WORKER PROMPT)

> **Manager note:** Batch 1d's e2e stub used canned `{step}.json` drops, so it proved the driver's LOGIC but
> never the INTEGRATION with the real transform CLIs. The manager then read the CLIs and found two concrete
> gaps that would make a live `/pseo-run monthly` fail: (1) the driver loader reads
> `_state/transform/{run_id}/{step}.json` but `scripts/ingestion/gsc_pull.py` writes `gsc_performance.json`
> (the SHEET name, not the step name — `gsc_pull.py:392`); (2) the `/pseo-run` recipe's generic single `--raw`
> doesn't fit `scripts/discovery/content_decay_transform.py`, which REQUIRES `--recent` AND `--previous`
> (`content_decay_transform.py:397,401`). This batch reconciles the driver + the recipe with the REAL CLI
> signatures + output filenames, and adds an INTEGRATION test (runs the real CLIs) so the gap is test-caught,
> not just live-caught. Spine (run_step/coverage/verify/committer) stays UNCHANGED. Paste into a fresh Opus-4.8
> 1M session. After this, Süleyman live-tests before Faz 2.

---

```text
You are a WORKER fixing ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 1d.1 of the AMO initiative, managed
elsewhere. Work ONLY within scope. Do NOT git commit/push — STOP and print the REPORT when done.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long"). Inline only.
- Do NOT git commit/push/branch.
- Baseline-first: `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  record exact "N passed" (N ~1890). END green, passed >= N. (If a SINGLE pre-existing `tests/ci/test_check_secrets_sh.py`
  failure appears, it is NOT yours — out of scope; note it and proceed; your real bar is "no NEW failures".)
- TDD: write the failing INTEGRATION test FIRST, watch it fail, then fix the driver to make it green.
- House style: immutability; no debug prints in shipped code (the CLI boundary print stays); functions <50 lines;
  clock-free logic (now_epoch passed in).
- Scope-lock: modify ONLY the files in SCOPE. Anything else -> STOP + report.

WHY THIS BATCH (read carefully):
The monthly workflow driver (batch 1d) loads each step's model-produced transform output via
`scripts/orchestration/workflows/monthly_maintenance.py::output_path(...) -> _state/transform/{run_id}/{step}.json`
and run_step's loader-transform reads it. But the EXISTING transform CLIs write their output keyed by the
SHEET name, and one CLI takes a different arg shape. So a live `/pseo-run monthly` would fail at the first
step. You reconcile the driver + the `/pseo-run` recipe with what the CLIs ACTUALLY do, and lock it with an
integration test that runs the real CLIs.

CONFIRMED FACTS (manager-verified 2026-06-06 — but you MUST re-read each CLI to get the EXACT args/outputs):
- `scripts/ingestion/gsc_pull.py` CLI: `--raw <recent> [--enriched <file>] [--output-dir <dir>]`; with
  `--output-dir` it writes **`gsc_performance.json`** into that dir (line ~392). Step name is `gsc_pull`,
  sheet is `gsc_performance` -> the driver currently looks for `gsc_pull.json` (WRONG).
- `scripts/discovery/quickwins_transform.py` CLI: `--raw <detect_quick_wins> [--enriched] [--top-n] [...]
  [--output-dir]`; writes **`quick_wins.json` + `opportunity.json`**. Step `quick_wins`, primary sheet
  `quick_wins` -> driver looks for `quick_wins.json` (CORRECT by coincidence).
- `scripts/discovery/content_decay_transform.py` CLI: **`--recent <file> --previous <file>` (BOTH required)**
  `[--output-dir]`; writes **`content_decay.json`**. Step `content_decay`, sheet `content_decay` -> driver
  looks for `content_decay.json` (CORRECT filename) BUT the recipe must pass `--recent`+`--previous`, NOT a
  single `--raw`.
- RESOLUTION: the driver's transform-output path must key by the step's SHEET name (the CLIs write
  `{sheet}.json`), not the step name. After that, all 3 match: gsc_performance.json / quick_wins.json /
  content_decay.json. (Re-read each CLI's argparse + the exact filename it writes — do not trust this summary
  blindly; if any differs, follow the CODE and report it.)
- The driver loader reads a bare JSON list OR {"rows":[...]}. The CLIs write a bare JSON list
  (`json.dumps(result["<sheet>"], ...)`) — compatible.
- run_step / coverage / verify / committer (the spine) are CORRECT and must NOT change — only the workflow
  driver's path mapping + the recipe + tests.

ORIENT FIRST (read, do not change yet):
- `scripts/ingestion/gsc_pull.py` (argparse ~354-360 + the `--output-dir` write ~389-395),
  `scripts/discovery/quickwins_transform.py` (~424-490), `scripts/discovery/content_decay_transform.py`
  (~396-442) — the EXACT CLI args + output filenames.
- `scripts/orchestration/workflows/monthly_maintenance.py` — `STEPS` (each has `name`+`sheet`), `output_path`,
  `_output_loader`, `build_steps` (it wires `transform=_output_loader(output_path(..., step_name))`).
- `tests/orchestration/test_monthly_maintenance.py` — the e2e stub; you adjust its canned outputs to the
  SHEET-named files + add the integration test.
- `commands/pseo-run.md` — Section 3 (the per-step MCP call + raw drop + transform CLI). You rewrite it to the
  real per-step CLI invocations.

SCOPE — modify ONLY:
  EDIT scripts/orchestration/workflows/monthly_maintenance.py   (output_path keys by SHEET, not step name)
  EDIT tests/orchestration/test_monthly_maintenance.py          (canned outputs -> sheet-named; + INTEGRATION test)
  EDIT commands/pseo-run.md                                     (Section 3: real per-step CLI invocations)

SPEC — monthly_maintenance.py:
- Change the transform-output path to key by the step's SHEET: e.g.
  `output_path(workspace_root, run_id, slug, sheet) -> .../_state/transform/{run_id}/{sheet}.json`, and in
  `build_steps` pass `entry["sheet"]` (not `entry["name"]`) to it. The RAW inbox drop path stays keyed by
  STEP name (`inbox_path(... step_name ...)`) — only the OUTPUT path changes to the sheet. Keep `run()` and
  everything else identical. (gsc_pull -> gsc_performance.json; quick_wins -> quick_wins.json; content_decay
  -> content_decay.json.)

SPEC — tests/orchestration/test_monthly_maintenance.py:
- Update the e2e stub's canned transform outputs to be written at the SHEET-named paths the driver now reads
  (so the happy path stays green with the corrected mapping).
- ADD an INTEGRATION test `test_real_transform_cli_outputs_land_where_loader_reads` (the gap-catcher): for
  EACH of the 3 steps, run the REAL transform CLI as a subprocess with a MINIMAL canned raw inbox input
  (the smallest valid input each CLI accepts — read each CLI to see its expected raw shape; for content_decay
  pass BOTH `--recent` and `--previous`) and `--output-dir` pointing at a tmp dir, then assert the file the
  driver's `output_path(...sheet...)` points to EXISTS in that dir (i.e. the CLI's output filename ==
  `{sheet}.json`). Use tmp_path; this proves the driver loader and the CLI agree on the filename. If a CLI
  needs network/MCP it should NOT — these transforms are pure (raw JSON in -> rows JSON out); if one cannot
  run offline, STOP + report (do not stub it away — the point is to test the REAL boundary).

SPEC — commands/pseo-run.md Section 3 (the per-step recipe): replace the single generic `--raw` example with
the REAL per-step invocations (and the raw drops each needs):
  * gsc_pull: MCP `mcp__gsc__search_analytics` (recent) [+ enriched via `mcp__gsc__enhanced_search_analytics`];
    provenance-stamped raw drop(s) under `_state/inbox/{run_id}/`; then
    `gsc_pull.py --raw <recent_drop> [--enriched <enriched_drop>] --output-dir _state/transform/{run_id}/`
    (writes gsc_performance.json).
  * quick_wins: `mcp__gsc__detect_quick_wins` [+ enriched]; then
    `quickwins_transform.py --raw <detect_drop> [--enriched <enriched_drop>] --output-dir …` (writes
    quick_wins.json + opportunity.json).
  * content_decay: `mcp__gsc__enhanced_search_analytics` for the RECENT window AND the PREVIOUS window (two
    drops); then `content_decay_transform.py --recent <recent_drop> --previous <previous_drop> --output-dir …`
    (writes content_decay.json).
  Keep the provenance-stamped raw-drop requirement (the driver gates the PRIMARY/recent drop at
  `_state/inbox/{run_id}/{step}.json` -> input_count). Make the recipe EXPLICIT that content_decay needs two
  windows. Keep Sections 1,2,4,5,6,7 of the command otherwise intact; only Section 3's per-step mechanics +
  any output-filename mention change. Re-confirm the command still passes the generic command guards
  (allowed-tools already lists Bash(python3:*) + the 3 MCP tools; if you reference a NEW shell program declare
  it; no `python3 -c`; no `stub`; only real `schemas/*.json` refs).

METHOD:
  1. Baseline pytest (N ~1890).
  2. Write the INTEGRATION test (RED — it should fail on gsc_pull because the driver currently reads
     gsc_pull.json while the CLI writes gsc_performance.json).
  3. Fix output_path -> by sheet; adjust the stub's canned outputs to sheet-named. GREEN.
  4. Rewrite commands/pseo-run.md Section 3.
  5. FULL suite; passed >= N, 0 NEW failed. `git status --short` = ONLY the 3 scoped files.
  6. @code-reviewer + @verifier inline.

DURUR (stop + report):
  - A transform CLI cannot run offline on a minimal canned input (needs network/MCP) -> report (do not stub).
  - A CLI's real output filename is NOT `{sheet}.json` for some step -> report the real name; the driver must
    match the REAL filename (sheet is the manager's hypothesis; the CODE wins).
  - Fixing this needs a run_step/coverage/verify/committer change -> STOP + report (it should not; only the
    workflow driver's path mapping).

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line (note the pre-existing check_secrets failure if present; confirm 0 NEW).
  - The output_path change (step->sheet) + proof the integration test runs the 3 REAL CLIs and each writes
    where the driver loader reads (the asserted filenames).
  - The per-step recipe corrections (esp. content_decay --recent/--previous + gsc_pull output gsc_performance.json).
  - Confirmation the spine (run_step/coverage/verify/committer) is UNCHANGED; only the 3 scoped files changed.
  - Any DURUR / surprise (e.g. a CLI whose real output filename differs from {sheet}.json).
```
