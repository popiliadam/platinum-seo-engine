---
name: sf-crawl-orchestrator
description: |
  Use when: kullanıcı "screaming frog crawl tetikle", "SF MCP crawl başlat",
  "24 raporu çek", "site full crawl", "sf orchestrator", "MCP üzerinden
  sf-export al" der ya da `/pseo-sf-crawl <slug>` çağırırsa. SF 24 native
  MCP'yi sürer: sf_crawl → sf_crawl_progress polling → 24 raporu (Tier 1
  14 + Tier 2 10) sırasıyla sf_generate_report(save_report=True) ile
  export eder → SF allowed_directory'den projeye atomic move → mevcut
  sf-import skill'ini subprocess olarak çalıştırarak master.xlsx'in
  6 SF-türevi sheet'ine projeksiyon yapar.
  Also use when: project.config.sf.mcp.enabled=true ve SF GUI canlı
  (mcp__sf__sf_list_allowed_base_directory probe PASS); operator yeni
  bir batch için "MCP-primary" akışı tercih ediyor (file-drop fallback
  bypass); requires_approval=true gate operator onayını bekler;
  workflow_runner.pause/resume ile 24-rapor döngüsü ortasında recovery
  mümkün; D-SF-16 atomic rollback semantiği — 14 Tier 1 raporun TÜMÜ
  başarılı OR `_state/staging/sf-crawl-{run_id}/` temizlenir (DURUR-orch-8).
  Do not use when: SF MCP kapalı ya da `project.config.sf.mcp.enabled=false`
  (file-drop fallback → mevcut `sf-import` skill direkt çağrılır); GSC
  ingestion (`gsc-pull`), DataForSEO (`dfs-pull`), Scrapling (`scrapling-ops`)
  ayrı skill'ler; master.xlsx yokken çağırma (`init-project` önce
  çalışmalı). Concurrent SF crawl varsa (sf_list_crawls IN_PROGRESS) →
  DURUR-orch-7 (R13 mitigation), operator GUI'yi kontrol etsin.
version: "1.0"
status: active
category: ingestion
inputs:
  project_slug:
    type: string
    required: true
    description: "Slug; resolves projects/{slug}/sf-exports/{date}/raw/ + project.config.json."
  url:
    type: string
    required: false
    description: "Crawl başlangıç URL'si. Belirtilmezse project.config.domain kullanılır."
  resume_run_id:
    type: string
    required: false
    description: "Mevcut paused workflow run'ı resume etmek için (workflow_runner.resume; --resume flag). Yeni bir run yerine var olanı sürdürür."
  include_tier3:
    type: boolean
    required: false
    default: false
    description: "Tier 3 (16 opsiyonel) rapor export'unu da çalıştır. Default false (Q-SF-MCP-10 lock: 24 rapor only). True olduğunda enumerate_reports(40) döner."
outputs:
  - "projects/{slug}/sf-exports/{date}/raw/"
  - "projects/{slug}/_state/workflows/{run_id}.json"
  - "projects/{slug}/_state/events.jsonl"
  - "projects/{slug}/inbox/sf-mcp/{date}-sf-crawl-{slug}.json"
  - "projects/{slug}/outputs/reports/{date}-sf-crawl.md"
  - "master.xlsx#crawl_sitemap"
  - "master.xlsx#redirect_404"
  - "master.xlsx#schema"
  - "master.xlsx#on_page_audit"
  - "master.xlsx#tech_seo"
  - "master.xlsx#robots_txt"
consumes:
  - "init-project:projects/{slug}/master.xlsx"
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "sf-import"
  - "drift-check"
triggers:
  manual: ["/pseo-sf-crawl"]
  natural_language: |
    "screaming frog crawl tetikle", "SF MCP crawl başlat", "24 raporu çek",
    "site full crawl", "sf-crawl orchestrator", "MCP üzerinden sf-export al"
  hooks: []
mcp_tools:
  required:
    - "mcp__sf__sf_crawl"
    - "mcp__sf__sf_crawl_progress"
    - "mcp__sf__sf_generate_report"
    - "mcp__sf__sf_list_allowed_base_directory"
  optional:
    - "mcp__sf__sf_list_crawls"
budget:
  uses_paid_mcp: false
  estimated_credits: 0
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---

# sf-crawl-orchestrator — ingestion skill (v1.8 Phase 3, MCP-primary)

9-step protocol. Bridges SF 24 native MCP (HTTP `http://127.0.0.1:11435/mcp`)
to the file-based sf-import skill. **MCP-PRIMARY ingestion path** (v2.2): the
orchestrator handles the full 24-report export per crawl (Tier 1 14 + Tier 2
10) via `mcp__sf__sf_generate_report(save_report=True)`, moves files from SF
allowed_directory into `projects/{slug}/sf-exports/{date}/raw/`, then invokes
sf-import as a subprocess for projection into master.xlsx's 6 SF-derived
sheets. File-drop fallback is preserved as disaster recovery only.

This skill is the **first HTTP MCP consumer** in PSEO (D-SF-01 + D-SF-14).
Future HTTP MCPs (local LM Studio, custom servers) reuse the
`scripts.util.sf_mcp_client.SfMcpClient` pattern established in Phase 2.
SKILL.md body invocations use Claude's `mcp__sf__sf_*` wrapper form; the
companion script `scripts/ingestion/sf_crawl_orchestrator.py` is **pure
transform** (enumerate_reports + move_with_rollback + parse_progress_response)
and does NOT call MCP directly (mirrors gsc_pull.py / dfs_pull.py pattern).

## Inputs (frontmatter contract)

| Name              | Type    | Default                    | Notes                                                                    |
|-------------------|---------|----------------------------|--------------------------------------------------------------------------|
| `project_slug`    | string  | —                          | Required. Resolves `projects/{slug}/sf-exports/` + project.config.json. |
| `url`             | string  | project.config.domain      | Crawl başlangıç URL'si. Omit → fallback to domain.                       |
| `resume_run_id`   | string  | None                       | --resume flag; paused workflow_runner run'ı sürdür.                      |
| `include_tier3`   | boolean | false                      | Q-SF-MCP-10 lock: 24 raporu only by default. True → 40 raporu.           |

`workspace_root` is resolved via `PSEO_WORKSPACE_ROOT` env or explicit
test override (mirrors workflow_runner / events_writer / sf-import).

## Outputs (artifacts produced)

- `projects/{slug}/sf-exports/{date}/raw/{report_name}.csv` × 24 — exported
  CSVs after atomic move from SF allowed_directory (D-SF-16 + D-SF-03).
- `projects/{slug}/_state/workflows/{run_id}.json` — workflow state file
  (ADR-021); pausable + resumable for mid-loop recovery.
- `projects/{slug}/_state/events.jsonl` — provenance entries
  (`source.kind=sf_mcp`, per-report row).
- `projects/{slug}/inbox/sf-mcp/{date}-sf-crawl-{slug}.json` — envelope JSON
  recording crawl_id, report manifest, durations, AMBER warnings (drift
  recovery witness; mirrors sf-import envelope discipline).
- `projects/{slug}/outputs/reports/{date}-sf-crawl.md` — human-readable run
  summary rendered from `templates/reports/sf-crawl.template.md`.
- Indirect (via sf-import subprocess Step 7): master.xlsx 6 sheet rows.

## 9-Step Body Protocol

> Step name conventions follow sf-import + dfs-pull discipline:
> `workflow_runner.create_run(steps=[...])` carries the 7 workflow-managed
> step names; `create_run` itself (Step 1) and `complete` (Step 9) are body
> protocol Steps but not entries in the steps[] list.

### Step 1 — `create_run`

Open a workflow run shell. The state file lives at
`projects/{slug}/_state/workflows/{run_id}.json` (ADR-021). If
`resume_run_id` is provided, skip create_run and call `workflow_runner.resume`
instead (paused → running, paused_at preserved per rules/append-only-state.md).

```python
from scripts.state import workflow_runner

if resume_run_id:
    handle = workflow_runner.resume(
        resume_run_id, project_slug=project_slug,
    )
else:
    handle = workflow_runner.create_run(
        skill="sf-crawl-orchestrator",
        project_slug=project_slug,
        steps=[
            {"name": "preflight"},
            {"name": "crawl_trigger"},
            {"name": "poll"},
            {"name": "export_24_reports"},
            {"name": "atomic_move"},
            {"name": "invoke_sf_import"},
            {"name": "emit_provenance_and_report"},
        ],
        initial_status="awaiting_approval",  # Q-SF-MCP-02 lock: requires_approval=true
        approval_meta={
            "approver": "user",
            "subject": f"SF MCP crawl triggered for {project_slug}; 24 raporu export edilecek. Onaylıyor musunuz?",
        },
    )
    # Operator approves via workflow_runner.approve(run_id, approver="user")
    # → awaiting_approval → running; this step resumes from Step 2.
```

### Step 2 — `preflight` (DURUR-orch-1/2/4/7 enforcement)

Three independent probes:

1. `mcp__sf__sf_list_allowed_base_directory` returns the SF allowed
   directory (D-SF-10). If the call raises (GUI not responsive, MCP not
   connected) → DURUR-orch-1.
2. Compare the returned path to `project.config.sf.mcp.allowed_directory`;
   mismatch → DURUR-orch-4.
3. `mcp__sf__sf_list_crawls` returns the live crawl list. Any entry with
   status="IN_PROGRESS" → DURUR-orch-7 (R13 concurrent-crawl guard:
   refuse to trigger a second crawl that would corrupt the GUI state).
   Note: spec mentions `sf_crawl_progress` for this check but that tool
   requires a crawl_id; `sf_list_crawls` is the natural enumerator.
4. If the SF GUI surfaces an open modal dialog (any prior probe raises
   `IllegalStateException`) → DURUR-orch-2.

```python
workflow_runner.start_step(handle.run_id, 0, project_slug=project_slug)
try:
    allowed_dir_resp = mcp__sf__sf_list_allowed_base_directory()
except Exception as exc:
    # orch-1 vs orch-2 distinction: SF GUI modal dialog surfaces as
    # IllegalStateException; everything else (connection refused, timeout)
    # is orch-1. Failure code is the canonical workflow-run.schema enum;
    # DURUR identity travels in the message for operator-facing detail.
    tag = "DURUR-orch-2" if "IllegalStateException" in str(exc) else "DURUR-orch-1"
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="mcp_error",
        message=f"{tag} SF MCP allowed_base_directory probe failed: {exc}",
        step_index=0,
    )
    raise SystemExit(2)

mcp_allowed = allowed_dir_resp.get("allowed_directory") if isinstance(allowed_dir_resp, dict) else str(allowed_dir_resp)
expected_allowed = project_config["sf"]["mcp"]["allowed_directory"]
if expected_allowed and mcp_allowed != expected_allowed:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="validation_error",
        message=f"DURUR-orch-4 SF allowed_directory mismatch: MCP={mcp_allowed} expected={expected_allowed}",
        step_index=0,
    )
    raise SystemExit(2)

list_resp = mcp__sf__sf_list_crawls()
in_progress = [c for c in list_resp.get("crawls", []) if c.get("status") == "IN_PROGRESS"]
if in_progress:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="mcp_error",
        message=f"DURUR-orch-7 concurrent SF crawl(s) IN_PROGRESS: {[c.get('crawl_id') for c in in_progress]}",
        step_index=0,
    )
    raise SystemExit(2)  # R13 mitigation

workflow_runner.finish_step(handle.run_id, 0, project_slug=project_slug,
                            output_ref=f"allowed_directory={mcp_allowed}")
```

### Step 3 — `crawl_trigger`

```python
workflow_runner.start_step(handle.run_id, 1, project_slug=project_slug)
crawl_url = url or project_config["domain"]
crawl_config_path = project_config["sf"]["mcp"].get("crawl_config_path")
trigger_resp = mcp__sf__sf_crawl(
    url=crawl_url,
    **({"crawl_config_file_path": crawl_config_path} if crawl_config_path else {}),
)
crawl_id = trigger_resp["crawl_id"]
workflow_runner.finish_step(handle.run_id, 1, project_slug=project_slug,
                            output_ref=f"crawl_id={crawl_id}")
# Provenance: emit sf_mcp_crawl_started event (informational; full
# provenance batch fires in Step 8 after the run completes).
```

### Step 4 — `poll`

Loop `mcp__sf__sf_crawl_progress(crawl_id)` every 60s; bail when status
is `DONE` or `FAILED`. Max wait `project.config.sf.mcp.max_wait_minutes`
(default 180; Q-SF-MCP-03 lock). Exceeding the cap → DURUR-orch-3
(operator review required).

```python
import time
from scripts.ingestion import sf_crawl_orchestrator

workflow_runner.start_step(handle.run_id, 2, project_slug=project_slug)
max_wait_sec = int(project_config["sf"]["mcp"]["max_wait_minutes"]) * 60
poll_interval = 60
elapsed = 0
final_state = None
while elapsed <= max_wait_sec:
    raw = mcp__sf__sf_crawl_progress(crawl_id=crawl_id)
    state = sf_crawl_orchestrator.parse_progress_response(raw)
    if state.status in ("DONE", "FAILED"):
        final_state = state
        break
    time.sleep(poll_interval)
    elapsed += poll_interval

if final_state is None:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="timeout",
        message=f"DURUR-orch-3 sf_crawl_progress exceeded max_wait_minutes={max_wait_sec // 60}",
        step_index=2,
    )
    raise SystemExit(2)

if final_state.status == "FAILED":
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="mcp_error",
        message=f"DURUR-orch-3 sf_crawl_progress reported FAILED for crawl_id={crawl_id}",
        step_index=2,
    )
    raise SystemExit(2)  # terminal-failed variant of orch-3

workflow_runner.finish_step(handle.run_id, 2, project_slug=project_slug,
                            output_ref=f"urls_crawled={final_state.urls_crawled}")
```

### Step 5 — `export_24_reports` (24 raporu × sf_generate_report loop)

Iterate the 24-report list returned by
`sf_crawl_orchestrator.enumerate_reports(include_tier3=False)` — 14 Tier 1
+ 10 Tier 2, sourced from `scripts.ingestion.sf_import.TIER1_REQUIRED` +
`TIER2_RECOMMENDED` frozensets (SSoT discipline per
rules/single-source-of-truth.md; canonical names live in
`schemas/sf-required-reports.schema.json`). Per-report export goes to a
temp staging directory `_state/staging/sf-crawl-{run_id}/`.

Tier policy (matches sf-import):
- **Tier 1 fail** → DURUR-orch-8: rollback (delete temp staging dir + all
  partial CSVs), surface RED to operator. D-SF-16 atomic semantics.
- **Tier 2 fail** → AMBER warning, continue (matches sf-import
  search_console_all canonical exemption).

```python
import shutil
from pathlib import Path
from scripts.ingestion import sf_crawl_orchestrator
from scripts.ingestion import sf_import as _sf_import_const  # SSoT import only

workflow_runner.start_step(handle.run_id, 3, project_slug=project_slug)
report_names = sf_crawl_orchestrator.enumerate_reports(include_tier3=include_tier3)
assert len(report_names) == (40 if include_tier3 else 24), \
    f"enumerate_reports drift: expected {40 if include_tier3 else 24}, got {len(report_names)}"

temp_staging = workspace_root / "projects" / project_slug / "_state" / "staging" / f"sf-crawl-{handle.run_id}"
temp_staging.mkdir(parents=True, exist_ok=True)

per_report_timeout = int(project_config["sf"]["mcp"]["per_report_timeout_seconds"])
amber_warnings: list[str] = []
tier1_required = _sf_import_const.TIER1_REQUIRED
exported: list[str] = []

for report_name in report_names:
    try:
        resp = mcp__sf__sf_generate_report(
            crawl_id=crawl_id,
            report_name=report_name,
            save_report=True,
            output_directory=mcp_allowed,
            timeout=per_report_timeout,
        )
        # Move the saved CSV from SF allowed_directory → temp_staging.
        src = Path(mcp_allowed) / f"{report_name}.csv"
        dst = temp_staging / f"{report_name}.csv"
        sf_crawl_orchestrator.move_with_rollback(src, dst)
        exported.append(report_name)
    except Exception as exc:
        if report_name in tier1_required:
            # D-SF-16 rollback: delete temp staging, surface DURUR-orch-8.
            shutil.rmtree(temp_staging, ignore_errors=True)
            workflow_runner.fail(
                handle.run_id, project_slug=project_slug,
                code="mcp_error",
                message=f"DURUR-orch-8 Tier 1 export failed for {report_name!r}: {exc}; "
                        f"rollback complete (temp_staging deleted)",
                step_index=3,
            )
            raise SystemExit(2)  # D-SF-16 atomic rollback
        # Tier 2 → AMBER, continue.
        amber_warnings.append(f"Tier 2 export failed for {report_name!r}: {exc}")

workflow_runner.finish_step(handle.run_id, 3, project_slug=project_slug,
                            output_ref=f"exported={len(exported)} amber={len(amber_warnings)}")
```

### Step 6 — `atomic_move` (temp staging → projects/{slug}/sf-exports/{date}/raw/)

```python
import datetime
workflow_runner.start_step(handle.run_id, 4, project_slug=project_slug)

today = datetime.date.today().isoformat()
target_raw = workspace_root / "projects" / project_slug / "sf-exports" / today / "raw"
if target_raw.exists():
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="validation_error",
        message=f"DURUR-orch-5 sf-exports target already exists: {target_raw}",
        step_index=4,
    )
    raise SystemExit(2)

target_raw.parent.mkdir(parents=True, exist_ok=True)
try:
    shutil.move(str(temp_staging), str(target_raw))  # atomic when same FS
except Exception as exc:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="internal_error",
        message=f"DURUR-orch-6 shutil.move failed: {exc}",
        step_index=4,
    )
    raise SystemExit(2)

workflow_runner.finish_step(handle.run_id, 4, project_slug=project_slug,
                            output_ref=str(target_raw))
```

### Step 7 — `invoke_sf_import` (Q-SF-MCP-05 default YES — auto-invoke)

Subprocess the existing sf-import skill to project the 24 raw CSVs into
master.xlsx's 6 SF-derived sheets. `--source-run-id` chains provenance:
sf-import's events.jsonl entry carries this orchestrator's run_id so
drift-check can correlate the two events later.

```python
import subprocess
workflow_runner.start_step(handle.run_id, 5, project_slug=project_slug)

result = subprocess.run(
    [
        "python3", "-m", "scripts.ingestion.sf_import",
        "--project", project_slug,
        "--sf-export-path", str(target_raw.parent),  # the {date} dir; sf-import discovers raw/
        "--source-run-id", handle.run_id,
    ],
    capture_output=True, text=True, timeout=600,
)
if result.returncode != 0:
    workflow_runner.fail(
        handle.run_id, project_slug=project_slug,
        code="internal_error",
        message=f"sf-import subprocess returned {result.returncode}: {result.stderr[:500]}",
        step_index=5,
    )
    raise SystemExit(2)

workflow_runner.finish_step(handle.run_id, 5, project_slug=project_slug,
                            output_ref=f"sf_import_exit=0 stdout_tail={result.stdout[-200:]}")
```

### Step 8 — `emit_provenance_and_report` (sf_mcp source + render template)

One `events_writer.append_provenance` entry summarizes the entire crawl
(per-report row counts captured in `outputs` of the workflow run; finer-
grained per-report rows are NOT emitted to keep events.jsonl compact —
the envelope JSON in inbox/sf-mcp/ carries the per-report manifest).

```python
import json
from scripts.state import events_writer
workflow_runner.start_step(handle.run_id, 6, project_slug=project_slug)

envelope = {
    "_meta": {
        "captured_at": _utc_iso_z(),
        "tool": "sf_mcp",
        "project_slug": project_slug,
        "crawl_id": crawl_id,
        "crawl_url": crawl_url,
        "exported_count": len(exported),
        "amber_warnings": amber_warnings,
    },
    "reports": [{"canonical_name": r, "tier": "required" if r in tier1_required else "recommended"}
                for r in exported],
}
envelope_path = (
    workspace_root / "projects" / project_slug
    / "inbox" / "sf-mcp"
    / f"{today}-sf-crawl-{project_slug}.json"
)
envelope_path.parent.mkdir(parents=True, exist_ok=True)
envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2),
                        encoding="utf-8")

events_writer.append_provenance(
    project_id=project_slug,
    run_id=events_writer.next_run_id(project_slug),
    source={
        # events.schema source.additionalProperties=false; only these keys are valid:
        "kind": "sf_mcp",
        "mcp_server": "sf",
        "mcp_tool": "sf__sf_generate_report",
        "response_bytes": len(json.dumps(envelope)),
        "row_count": len(exported),
    },
    operation="ingest",
    rows_written=len(exported),
)

# Render report via templates/reports/sf-crawl.template.md.
from scripts.reporting import render_template
report_path = render_template.render(
    template_path=workspace_root / "templates" / "reports" / "sf-crawl.template.md",
    output_path=workspace_root / "projects" / project_slug
                / "outputs" / "reports" / f"{today}-sf-crawl.md",
    variables={
        "project_slug": project_slug,
        "date": today,
        "crawl_id": crawl_id,
        "exported_count": str(len(exported)),
        "amber_count": str(len(amber_warnings)),
        "amber_warnings": "\n".join(f"- {w}" for w in amber_warnings) or "_(none)_",
        "run_id": handle.run_id,
    },
)

workflow_runner.finish_step(handle.run_id, 6, project_slug=project_slug,
                            output_ref=str(envelope_path))
```

### Step 9 — `complete`

```python
workflow_runner.complete(handle.run_id, project_slug=project_slug, outputs={
    # F5: outputs.* must be STRING-TYPED.
    "crawl_id": crawl_id,
    "reports_exported": str(len(exported)),
    "amber_warnings": str(len(amber_warnings)),
    "sf_export_path": str(target_raw),
    "envelope_path": str(envelope_path),
    "report_path": str(report_path),
    "sf_import_run_id": handle.run_id,  # same run_id chains both
})
```

## 24-Report enumeration (SSoT)

The 24-report list comes from the existing
`scripts/ingestion/sf_import.py` `TIER1_REQUIRED` (14) +
`TIER2_RECOMMENDED` (10) frozensets, which themselves mirror
`schemas/sf-required-reports.schema.json` `definitions.canonicalName.enum`.
`enumerate_reports(include_tier3=False)` IMPORTS from these — never
re-lists names inline (per rules/single-source-of-truth.md).

When `include_tier3=True`, the function returns all 40 names from the
canonicalName enum minus T1+T2 = 16 Tier 3 entries (future-proofing per
Q-SF-MCP-10 lock; default 24).

## Tier policy

| Tier        | Missing/Export fail → | Notes                                            |
|-------------|-----------------------|--------------------------------------------------|
| Required    | DURUR-orch-8 + rollback | All 14 must succeed; partial run rolled back.   |
| Recommended | AMBER warning         | Matches sf-import policy; `search_console_all`   |
|             |                       | typical exemption.                               |
| Optional    | SILENT                | Only included when `include_tier3=True`.         |

## D-SF-16 — Atomic crawl semantics

The orchestrator's "all-or-nothing" guarantee on Tier 1 export is
implemented by writing every CSV first to a temp directory
`_state/staging/sf-crawl-{run_id}/`. ONLY when all 14 Tier 1 reports
export successfully do we `shutil.move(temp_staging → sf-exports/{date}/raw/)`.
A single Tier 1 failure triggers `shutil.rmtree(temp_staging,
ignore_errors=True)` BEFORE the orchestrator raises DURUR-orch-8 — sf-import
never sees a half-populated raw/ directory.

## DURUR conditions (8)

Stop and flag the operator — do not patch, do not fall back.

1. **orch-1** — `mcp__sf__sf_list_allowed_base_directory` raises (SF GUI
   not responsive, MCP not connected, network error).
2. **orch-2** — SF GUI surfaces an `IllegalStateException` (modal dialog
   open — e.g. an unsaved settings change). Operator must close the
   dialog manually before re-running.
3. **orch-3** — `sf_crawl_progress` polling exceeds
   `project.config.sf.mcp.max_wait_minutes` (default 180), OR returns
   status="FAILED" terminally.
4. **orch-4** — `mcp__sf__sf_list_allowed_base_directory` returns a path
   that mismatches `project.config.sf.mcp.allowed_directory` (operator
   must reconcile F-15 isolation governance before proceeding).
5. **orch-5** — target `projects/{slug}/sf-exports/{date}/raw/` already
   exists at atomic move time (operator must archive or remove the
   prior batch; we refuse to overwrite).
6. **orch-6** — `shutil.move(temp_staging → sf-exports/{date}/raw/)`
   raises (disk full, permission denied, cross-filesystem error). Temp
   staging is preserved for forensics; operator decides whether to
   retry or rollback manually.
7. **orch-7** — `mcp__sf__sf_list_crawls` reports an
   `IN_PROGRESS` crawl (R13 mitigation; never trigger a parallel crawl
   that would corrupt the GUI state).
8. **orch-8** — Tier 1 export fails for any single report. D-SF-16
   atomic rollback: temp_staging deleted, no partial state survives.

## Resume capability (D-SF-16 + workflow_runner.pause/resume)

The orchestrator is **resumable mid-loop**. If `mcp__sf__sf_crawl_progress`
times out OR `mcp__sf__sf_generate_report` raises a recoverable error
(transient network), the operator can:

1. Set workflow state to `paused`: `workflow_runner.pause(run_id, ...)`
   (paused_at preserved).
2. After fixing the underlying issue (re-open SF GUI, increase
   max_wait_minutes), resume via `/pseo-sf-crawl <slug> --resume <run_id>`.
3. The skill body checks `resume_run_id` at Step 1 and calls
   `workflow_runner.resume()` instead of `create_run` — preserves
   step history + previously exported reports in temp staging.

## Cross-references

- Schemas: `schemas/sf-mcp-tool-mapping.schema.json` (Phase 1 NEW; 6
  use-case keys + sfMcpTool enum), `schemas/sf-required-reports.schema.json`
  (canonical 40-report enum; Tier 1/2/3 frozensets in sf_import.py SSoT),
  `schemas/project-config.schema.json` v1.5 (`sf.mcp.*` block; Migration
  0005 populates defaults), `schemas/events.schema.json`
  (`source.kind=sf_mcp` enum addition Phase 1),
  `schemas/skill-frontmatter.schema.json` (this frontmatter).
- Cross-modules (IMPORT-only): `scripts/state/workflow_runner.py`
  (create_run, start_step, finish_step, complete, fail, pause, resume),
  `scripts/state/events_writer.py` (append_provenance, next_run_id),
  `scripts/ingestion/sf_import.py` (TIER1_REQUIRED + TIER2_RECOMMENDED
  frozensets — SSoT for tier membership),
  `scripts/util/sf_mcp_client.py` (Phase 2; NOT used here — orchestrator
  body calls MCP via `mcp__sf__sf_*` wrapper form; sf_mcp_client is for
  Phase 5 consumer skills with `use_sf_mcp_live=True`).
- Tests: `tests/skills/test_sf_crawl_orchestrator.py` (10 cases:
  happy_path_24_reports + 8 DURUR cases + sf-import handoff),
  `tests/scripts/test_sf_crawl_orchestrator.py` (6 cases: pure-transform
  helper coverage), `tests/smoke/test_sf_mcp_smoke.py` (1 case live MCP
  skipif).
- Companion skill: `skills/ingestion/sf-import/SKILL.md` (frontmatter
  adds `source_run_id` optional input in Phase 3; body 8-step protocol
  UNCHANGED per D-SF-07).
- Command: `commands/pseo-sf-crawl.md` (Phase 6 NEW;
  `/pseo-sf-crawl <slug> [url] [--resume <run_id>]`).

## Discipline checklist

- [x] TODO/fallback YASAK — every DURUR raises, none silently downgrade.
- [x] Schema-first — frontmatter validates against
      `schemas/skill-frontmatter.schema.json` Draft 7;
      `mcp_tools.required` entries match `mcp-tool-registry.json` sf
      server inventory (sf_crawl, sf_crawl_progress, sf_generate_report,
      sf_list_allowed_base_directory).
- [x] Plugin-agnostik — no slug literals; `project_slug` flows through.
- [x] ADR-013 — `Use when`/`Also use when`/`Do not use when` are STRING
      content inside `description`, not separate fields.
- [x] D-SF-16 — atomic rollback on Tier 1 export failure (temp_staging
      pattern); sf-import never sees a half-populated raw/ directory.
- [x] D-SF-17 — multi-session execution (this skill = Phase 3 Worker
      deliverable; Phase 5 consumer flag wiring is a separate Worker).
- [x] F-15 isolation — SF allowed_directory governance preserved
      (configurable via project.config.sf.mcp.allowed_directory but
      always cross-checked at preflight).
- [x] F5 — `outputs.*` values are STRING-TYPED (artifact paths or
      stringified counts), never raw ints.
- [x] requires_approval=true (Q-SF-MCP-02 lock) — initial_status=
      "awaiting_approval" in create_run; operator must approve before
      crawl_trigger fires.
- [x] SSoT — 24-report enumeration imports from
      `scripts.ingestion.sf_import.TIER1_REQUIRED` + `TIER2_RECOMMENDED`
      frozensets; never re-lists names inline.
