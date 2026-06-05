# AMO Batch 0e2 — portfolio.json safety, Option 1 build (WORKER PROMPT)

> **Manager note:** Batch 0e investigated and DURUR'd (case c): `shared/portfolio.json` is written by
> model-executed inline python in `skills/meta/init-project/SKILL.md` Step 6 (no callable code to lock), and
> the test has a hand-copied *mirror* of that logic. Manager approved **Option 1**: extract a flock-guarded
> helper, rewire Step 6 to call it, and convert the test mirror to import it. This is a behavior-preserving
> change (identical JSON shape) that makes the registry concurrency-safe + kills the two drifting copies.
> Paste into a fresh Opus-4.8 1M session. (File-disjoint from 0f; parallel-safe.)

---

```text
You are a WORKER. Repo: /Users/apple/Documents/platinum-seo-engine (Python, pytest). AMO batch 0e2, managed
elsewhere. Scope-locked, inline only, NO git, NO Task/Agent tools (they FAIL here), STOP + print REPORT when done.

HARD RULES: Baseline-first (`PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`,
record N ~1775; end green, passed >= N). TDD (RED first). Immutability (build new dicts, don't mutate), no debug
prints, functions <50 lines. Edit ONLY the SCOPE files — anything else → STOP + report.

CONFIRMED (batch 0e investigation — don't re-investigate): the ONLY writer of `shared/portfolio.json` is the
inline python in `skills/meta/init-project/SKILL.md` Step 6 (`register_portfolio`, ~lines 225-245), a lock-free
read-modify-write (read whole JSON → append slug if absent → write whole JSON back) → lost-update race under
two parallel init-project runs. `tests/skills/test_init_project.py` has a test-local MIRROR `_register_portfolio`
(~line 128, docstring "Mirror skill step 6"), NOT an import. No portfolio writer module exists.

GOAL (manager-approved Option 1): extract one flock-guarded helper, rewire the SKILL.md to call it, convert the
test mirror to import it. Identical JSON shape; all readers untouched.

SCOPE — create/modify ONLY:
  NEW  scripts/state/portfolio_writer.py          (the flock-guarded register_project helper + tiny CLI)
  NEW  tests/state/test_portfolio_writer.py       (concurrency TDD)
  EDIT skills/meta/init-project/SKILL.md          (Step 6: replace the inline read-modify-write with a call
                                                   to the helper — keep the step's documented behavior/output
                                                   + the skill frontmatter IDENTICAL; only the write mechanism changes)
  EDIT tests/skills/test_init_project.py          (import register_project; drop the local _register_portfolio mirror)

SPEC — scripts/state/portfolio_writer.py:
- `register_project(workspace_root, slug, domain, market, *, created_at) -> Path` (pass created_at in so the
  function is pure/testable; SKILL.md supplies datetime). Under ONE blocking exclusive lock on the file
  (mirror `scripts/state/events_writer.py`'s `fcntl.flock(LOCK_EX)` discipline), do the read-modify-write:
    * open `workspace_root/shared/portfolio.json` O_RDWR|O_CREAT; flock LOCK_EX;
    * data = parsed JSON or `{"schema_version": "1.0", "projects": []}` if empty/missing;
    * if slug not already in `{p["slug"] for p in data["projects"]}` → build a NEW data dict (immutability)
      appending `{"slug","domain","market","created_at"}`; else leave unchanged (idempotent dedup);
    * truncate + write `json.dumps(data, ensure_ascii=False, indent=2) + "\n"`; flock LOCK_UN; close.
  PRESERVE the EXACT shape readers expect: top-level `{"schema_version":"1.0","projects":[{slug,domain,market,
  created_at}, …]}`, indent=2, trailing newline, ensure_ascii=False.
- A thin CLI (`python3 -m scripts.state.portfolio_writer register <slug> --domain --market --workspace`) is
  optional but lets the SKILL.md call it as a subprocess if cleaner than an inline import — your choice; keep
  whichever the SKILL.md uses consistent.

SPEC — skills/meta/init-project/SKILL.md Step 6: replace the inline read-modify-write block with a call to
`register_project(...)` (import or CLI). The step's described OUTPUT and the skill's frontmatter/contract must
read IDENTICALLY — only the underlying write becomes lock-safe. Do not touch other steps.

SPEC — tests/skills/test_init_project.py: replace the local `_register_portfolio` mirror with
`from scripts.state.portfolio_writer import register_project` and call it; keep `test_portfolio_json_valid`
(~line 428: valid JSON + append-only + dedup) and the idempotency tests (~281/294) green.

TDD — tests/state/test_portfolio_writer.py: (1) two concurrent threads each register a distinct slug → BOTH
land, no lost update, file valid JSON, exactly 2 projects; (2) re-registering the same slug is idempotent (no
dup); (3) shape exactly matches the contract (schema_version, projects[] of the 4 keys, trailing newline).
Use tmp_path; never touch the real workspace.

METHOD: baseline → tests RED → implement helper → rewire SKILL.md + migrate test → full suite (passed >= N,
0 failed; init-project + monitoring-weekly tests stay green) → @code-reviewer + @verifier inline. NOTE: editing
an existing SKILL.md adds no command/schema → no count-guard bump.

DURUR: if rewiring Step 6 to call the helper would change the skill's documented contract/output beyond the
write mechanism, or a skill-contract test pins the inline python literally → report rather than weaken it.

REPORT: baseline N + final pytest line; the helper's lock discipline + proof of no-lost-update (2-thread test);
confirmation the JSON shape + all readers (monitoring-weekly) + init-project tests are intact; that the test
mirror is gone (now imports the helper); only the 4 scoped files changed; any DURUR.
```
