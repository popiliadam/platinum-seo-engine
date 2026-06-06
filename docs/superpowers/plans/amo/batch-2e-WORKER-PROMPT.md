# AMO Batch 2e — AI-Disclosure PostToolUse Surface-Rescan (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 2 wave-1 + 2b are shipped (HEAD `3058fb7`, suite **1995/0**).
> This batch closes Süleyman's SECOND hard constraint — "written by AI" must NEVER appear in visible blog HTML.
> The PreToolUse `validate_content_write.py` blocks a bad blog-HTML **Write/Edit**, but a **Bash** heredoc/`cp`/
> `python -c` writes the same file WITHOUT touching the Write tool (the live Vento `vcc-` pattern). 2e is the
> PostToolUse twin: after a write, it RE-SCANS the file's surface, and on a RED content finding QUARANTINES the
> file (renames it off the live `.html` path) + tells the model to rewrite. It REUSES `content_validator` (same
> RED rules as the Write-gate, so the two paths can't drift). Runs SOLO. Then 2f (hardening) closes Faz 2.
> Paste the block below into a fresh Claude Code session (Opus 4.8, 1M context) at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 2e of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 1995 at HEAD 3058fb7) BEFORE any change. END green with
  passed strictly >= N (your new tests add to it) and 0 failed.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build NEW objects, never mutate inputs); no leftover debug prints (the hook writes
  ONLY its block-decision JSON to stdout + optional stderr); small functions (<50 lines); files 200-400 lines.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
Süleyman's HARD constraint: the phrase "written by AI" (and the other AI-disclosure signals) must NEVER appear
in the VISIBLE HTML of a generated blog post (memory feedback_ai_disclosure_ban). The PreToolUse gate
`validate_content_write.py` enforces this on the Write/Edit tools — but a model can BYPASS it by writing the
HTML through Bash (a `cat > … << 'EOF'` heredoc, `cp`, `tee`, `python -c "open(...).write(...)"`), which never
invokes Write/Edit (this is the REAL, USED Vento `vcc-` pattern: the engine's R-61 hook blocks `vcc-` via Write,
so the operator writes the body with a Bash heredoc). THIS batch closes that bypass: a PostToolUse hook that,
AFTER any Edit/Write/Bash, re-scans the blog-HTML file's SURFACE and, on a RED content finding, REVERTS it
(quarantine-rename off the live `.html` path) and tells the model to rewrite without the disclosure. PostToolUse
fires AFTER the write, so it cannot prevent — it must DETECT + REVERT (block-and-revert, spec §3 L4 / §7 2b).

CONFIRMED FACTS (verified against the code 2026-06-06 — do not re-derive):
- The detector to REUSE (do NOT reinvent disclosure detection): `scripts/validation/content_validator.py`
  `validate_content(content: str, *, profile: str | None = None) -> ContentReport`. `ContentReport.findings` is
  a list of `Finding(rule: str, severity: "RED"|"AMBER", message: str)`; `ContentReport.has_red` is True iff any
  finding is RED. The AI-disclosure ban is `rule="AI-disclosure", severity="RED"` and runs on VISIBLE text
  (script/style stripped) — exactly the surface that matters. The PreToolUse `validate_content_write.py` already
  calls it on a full Write; you call it on the FILE CONTENT after the write.
- REUSE from `scripts/hooks/validate_content_write.py` (import — do NOT duplicate): `is_content_html_path(path)`
  (True iff `…/outputs/(blog|content)/…/*.html` and not `*.template.html`) and `_resolve_profile(payload)`
  (best-effort active-project profile; never raises). Your rescan = the POST-write, quarantine-instead-of-prevent
  twin of that module.
- The PostToolUse chain is `hooks/post-tool-use.json`: ONE block, matcher "Edit|Write|Bash", 2 commands
  (audit_post_tool_use.py, env_probe.py). ADD your rescan as a 3rd command (leave the other two untouched).
- PostToolUse hook pattern to MIRROR: `scripts/hooks/audit_post_tool_use.py` — bare-hook sys.path bootstrap,
  stdin parse → `{}` on garbage, `current_session_id(payload)` + `resolve_workspace_root()` +
  `resolve_session_project(ws, session_id=…, strict=False)`, NON-BLOCKING (any error → return 0; never wedge the
  tool chain). The payload: `{"tool_name","tool_input":{...},"session_id"}`; for Write/Edit
  `tool_input.file_path`, for Bash `tool_input.command`.
- A PostToolUse hook signals the model by writing `{"decision":"block","reason":"…"}` to STDOUT (the reason is
  shown to the model; the tool already ran). `denetci.py` uses this exact stdout-JSON form. (If you find the
  PostToolUse decision contract differs on this Claude Code version, STOP + report — but the QUARANTINE below is
  the real enforcement and does not depend on that nuance.)
- A NEW wired hook script MUST be in `RUNTIME_HOOK_SCRIPTS` (tests/hooks/test_hook_scripts_runtime_vs_ci.py) +
  named in scripts/hooks/README.md §1. Bare-hook sys.path: CLAUDE_PLUGIN_ROOT (or parents[2]) before scripts.*.
- Adds NO schema/command/new-hook-FILE → NO D10 count-guard.

THE ENFORCEMENT — quarantine-rename (block-and-revert without a pre-write snapshot):
On a RED finding in a just-written blog HTML file, RENAME it off the live surface:
  `<path>` → `<path>.BLOCKED-ai-disclosure`   (os.replace; overwrite any prior quarantine of the same file)
so the live `.html` no longer exists (the disclosure is OFF the visible surface), the content is PRESERVED for
operator review (not destroyed), and the model is told to rewrite. This is the "revert": for the blog-generation
case the write is a NEW file, so removing it from its path IS the revert. Then emit a PostToolUse block decision
naming the file + rule + quarantine path + the Turkish fix (rewrite without the AI-disclosure phrase).

WHICH FILES TO RESCAN (root-agnostic + no false-positive on reads):
A candidate is a blog-HTML path that this tool plausibly WROTE — identified WITHOUT hard-coding the blog root:
  * Write/Edit: `tool_input.file_path` if `is_content_html_path(file_path)`.
  * Bash: every token in `tool_input.command` that ENDS in `.html` AND `is_content_html_path(token)` (catches
    `cat > outputs/blog/x/article.html << EOF`, `cp tmp outputs/blog/x/article.html`, `tee …`, a literal path in
    `python -c`). Dynamically-constructed paths (a shell variable) are NOT caught — a documented Path-A limit.
  * Filter to candidates that (a) EXIST on disk AND (b) were modified JUST NOW (`now - mtime < window`, e.g.
    window=60s) — so a mere `cat <file>` (a READ; mtime unchanged/old) is NOT quarantined (no false-positive),
    only a fresh WRITE is. (now is the wall clock; this is the only clock read — pass it in to keep the core pure.)

ORIENT FIRST (read, do not change yet):
- `scripts/validation/content_validator.py` — `validate_content`, `ContentReport`, `Finding`, the AI-disclosure
  RED rule (confirm the API + that it runs on visible/script-stripped text).
- `scripts/hooks/validate_content_write.py` — `is_content_html_path` + `_resolve_profile` (you import both) +
  its RED-finding logic (you mirror: a RED finding → enforce).
- `scripts/hooks/audit_post_tool_use.py` — the PostToolUse stdin/resolve/non-blocking pattern + sys.path boot.
- `scripts/hooks/denetci.py` — the stdout `{"decision":"block","reason":…}` form + non-crashing main.
- `hooks/post-tool-use.json` — the block you add a 3rd command to.
- grep tests/ for any test pinning post-tool-use.json structure/command-count → scope its migration in if found.

SCOPE — create/modify ONLY these files:
  NEW  scripts/hooks/ai_disclosure_rescan.py            (the PostToolUse surface-rescan; see SPEC)
  NEW  tests/hooks/test_ai_disclosure_rescan.py         (candidate-extraction + detect + quarantine + block + non-crash)
  EDIT hooks/post-tool-use.json                         (ADD ai_disclosure_rescan as a 3rd command; other 2 untouched)
  EDIT tests/hooks/test_hook_scripts_runtime_vs_ci.py   (ADD "ai_disclosure_rescan.py" to RUNTIME_HOOK_SCRIPTS)
  EDIT scripts/hooks/README.md                          (document ai_disclosure_rescan.py under §1 runtime hooks)

SPEC — scripts/hooks/ai_disclosure_rescan.py (PostToolUse; non-blocking on error; quarantine = the enforcement):
  Bare-hook sys.path bootstrap; import `validate_content` (content_validator), `is_content_html_path` +
  `_resolve_profile` (validate_content_write), `current_session_id`/`resolve_workspace_root`/
  `resolve_session_project` (session_binding).

  PURE-ish helpers (build NEW objects; the only IO is the explicit file reads/rename):
    - candidate_paths(payload, *, now, window=60.0) -> list[Path]:
        derive blog-HTML paths this tool plausibly WROTE (Write/Edit file_path; Bash `.html` tokens matching
        is_content_html_path), keep those that EXIST and have `now - mtime < window`. Returns [] for anything
        else. (Reads mtime; `now` passed in so the decision logic is testable without the wall clock.)
    - scan_red(path, *, profile) -> list[Finding]:
        read the file text (utf-8, errors='replace'); `report = validate_content(text, profile=profile)`; return
        the RED findings (`[f for f in report.findings if f.severity == "RED"]`). On an unreadable file → [].
    - quarantine(path) -> Path:
        os.replace(path, path + ".BLOCKED-ai-disclosure"); return the quarantine path. (Removes the live `.html`.)
    - block_reason(blocked: list[tuple[Path, list[Finding], Path]]) -> str:
        a Turkish, model+operator-visible message naming each quarantined file + its RED rule(s) + the quarantine
        path + the fix, e.g.:
          "🔴 BLOKLANDI: {file} görünür HTML'de AI-disclosure sinyali taşıyor (kural: {rules})."
          "Dosya canlı yüzeyden kaldırıldı (karantina: {qpath})."
          "Açıklamayı kaldırıp yeniden yaz — görünür 'AI tarafından yazıldı' ifadesi YASAK "
          "(R-28/R-45/R-89/R-105/R-119 'self-evident' sinyalleri yeterli)."
  main() -> int (NON-CRASHING, mirrors audit_post_tool_use):
    try:
      payload = parse stdin (→ {} on garbage); if not payload.get("tool_name"): return 0.
      profile = _resolve_profile(payload)   # best-effort; never raises
      now = <wall clock>
      blocked = []
      for path in candidate_paths(payload, now=now):
          reds = scan_red(path, profile=profile)
          if reds: blocked.append((path, reds, quarantine(path)))
      if blocked:
          print(json.dumps({"decision": "block", "reason": block_reason(blocked)}))  # STDOUT → model
          # optional: also a stderr line so the operator sees it in the transcript.
      return 0
    except Exception:
      # A buggy rescan must not brick the tool chain (mirrors validate_content_write fail-open-on-error). The
      # PreToolUse Write-gate remains the primary guard for Write/Edit; this closes the Bash bypass best-effort.
      return 0
  Module docstring: cite the AI-disclosure hard constraint + that this is the POST-write quarantine twin of
  validate_content_write (REUSES content_validator + is_content_html_path), closes the Bash/heredoc bypass,
  quarantine-renames off the live surface (block-and-revert), non-blocking-on-error, classified RUNTIME.

  Wiring — hooks/post-tool-use.json: add a 3rd command to the existing block (matcher stays "Edit|Write|Bash"):
    { "type": "command",
      "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/ai_disclosure_rescan.py\"",
      "timeout": 15,
      "statusMessage": "AMO AI-disclosure surface rescan..." }

TDD — write these FIRST (RED), then implement (GREEN). tmp_path; build a project tree with an
`…/outputs/blog/<slug>/article.html`; use a KNOWN AI-disclosure phrase for the RED case (read content_validator
to pick a phrase its AI-disclosure rule fires on — e.g. an explicit "written by AI" / Turkish equivalent) and a
clean post for the GREEN case. Cover:
  1. candidate_paths: a Write payload with a blog-HTML file_path (fresh mtime) → [that path]; a non-blog path
     (e.g. /tmp/x.html or outputs/audits/x.html) → []; a Bash heredoc command naming the blog .html (fresh) →
     [that path]; a Bash `cat <blog.html>` where the file is OLD (now-mtime > window) → [] (read, not write).
  2. scan_red: a file with an AI-disclosure phrase → a RED Finding (rule "AI-disclosure"); a clean post → [].
  3. quarantine: renames `article.html` → `article.html.BLOCKED-ai-disclosure` (live path gone; quarantine has
     the content).
  4. main() (subprocess, mirror test_audit_post_tool_use / test_denetci): a Bash-heredoc payload that wrote a
     disclosed blog HTML → stdout is JSON decision=="block" mentioning the file + AI-disclosure; the live `.html`
     is GONE and the `.BLOCKED-ai-disclosure` exists; exit 0.
  5. main(): a clean blog HTML write → stdout empty, file untouched, exit 0.
  6. main(): a non-blog write (outputs/audits/x.html or /tmp) → no scan, no quarantine, exit 0.
  7. main(): bogus/empty stdin → exit 0, no crash.
  8. (belt-and-suspenders) a Write of a disclosed blog HTML (the PreToolUse gate would normally block it, but
     prove the PostToolUse net also catches it) → quarantined + block.

METHOD:
  1. Baseline pytest (record N == 1995).
  2. Write test_ai_disclosure_rescan.py (RED).
  3. Implement ai_disclosure_rescan.py; wire the 3rd post-tool-use command; register RUNTIME + README.
  4. Confirm the existing post-tool-use tests + audit_post_tool_use/env_probe are untouched/green.
  5. Full suite; passed >= N, 0 failed.
  6. Self-review @code-reviewer + @verifier (inline): REUSES content_validator + is_content_html_path (no
     duplicated detection); only a JUST-WRITTEN blog HTML is quarantined (recency guard → a read never triggers);
     non-blocking on error (a rescan bug never wedges the tool chain); quarantine uses os.replace; the other two
     post-tool-use hooks are intact.

DURUR (stop + report):
  - An ai_disclosure_rescan / post-write content gate already exists (grep) — report rather than duplicate.
  - The PostToolUse `{"decision":"block"}` contract differs on this Claude Code version (the block doesn't
    surface) — STOP + report (the quarantine still enforces, but flag the signal-channel difference).
  - validate_content / is_content_html_path / _resolve_profile aren't importable as described — STOP + report
    (do NOT reimplement disclosure detection).
  - A test pins post-tool-use.json to exactly 2 commands and adding a 3rd breaks it un-migratably — STOP + report.
  - Any existing test regresses for a reason outside this batch's files.

REPORT (print verbatim when DONE):
  - Baseline N and final pytest line (passed/skipped/failed).
  - Files created/edited + new-test count.
  - Confirm it REUSES content_validator.validate_content + validate_content_write.is_content_html_path (quote the
    imports) — no duplicated disclosure detection.
  - The candidate-selection rule (Write/Edit file_path + Bash `.html` tokens, EXISTS + fresh-mtime) + confirm a
    READ (`cat old.html`) is NOT quarantined (recency guard) and a non-blog path is ignored.
  - The quarantine mechanism (os.replace → `.BLOCKED-ai-disclosure`; live `.html` removed; content preserved) +
    the block-decision stdout JSON.
  - Confirm NON-BLOCKING-ON-ERROR (a rescan bug → exit 0, never wedges the tool chain) and that the other two
    post-tool-use hooks (audit, env_probe) are intact + green.
  - Confirm classified RUNTIME + README; no schema/command → no D10.
  - Any DURUR hit, out-of-scope need, or assumption (e.g. the exact AI-disclosure phrase you used in tests).
```
