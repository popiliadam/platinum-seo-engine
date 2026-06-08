"""REAL transform-CLI boundary for the new-project-setup driver (AMO batch 3c).

The stub e2e tests (test_new_project_setup.py) hand-write canned OUTPUT files;
they cannot catch a filename mismatch between the EXISTING planning transform CLIs
and the path the driver's loader reads, NOR the SEQUENTIAL DEPENDENCY between the
three steps. This module runs the THREE real CLIs as subprocesses IN ORDER on
minimal canned inputs, THREADING each committed sheet into the next dependent
step, and then drives the REAL loader wired by build_steps — proving (a) each CLI
writes its output exactly where the driver expects, and (b) the chain works.

The dependency mechanism (the new wrinkle vs 3b) — the dependent transforms do
NOT read master.xlsx directly; the MODEL extracts the prior committed sheet and
passes it as an explicit CLI arg:

  topical_map  --(its `cluster` column)-->  cluster_map  --cluster-defs-json
  cluster_keywords  --({keyword: cluster} map)-->  new_content_plan  --cluster-map

So the workflow's IN-ORDER execution (topical_map committed before cluster_map
runs; cluster_keywords committed before new_content_plan runs) is what satisfies
the `consumes:` frontmatter — no driver change is needed. This test reproduces
that threading on the REAL CLIs.

These transforms are pure raw-JSON-in -> rows-JSON-out (never network/MCP), so
they MUST run headless; a non-zero exit is a DURUR-class integration gap.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.orchestration.workflows.new_project_setup import (
    STEPS,
    build_steps,
    output_path,
)

RUN_ID = "dental-2026-06-08-c3d4"
SLUG = "dental"
SEED = "dental implants"

REPO_ROOT = Path(__file__).resolve().parents[2]
_TRANSFORM_CLI = {
    "topical_map": REPO_ROOT / "scripts" / "planning" / "topical_map_transform.py",
    "cluster_map": REPO_ROOT / "scripts" / "planning" / "cluster_map_transform.py",
    "new_content_plan": REPO_ROOT / "scripts" / "planning" / "new_content_plan_transform.py",
}


def _run_real_cli(args: list[str]) -> None:
    """Run a transform CLI offline; STOP loudly if it cannot (DURUR: these
    transforms are pure raw-JSON-in -> rows-JSON-out, never network/MCP)."""
    proc = subprocess.run(
        [sys.executable, *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"transform CLI did not run offline (rc={proc.returncode}): {args}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


def _flat(items: list[dict]) -> dict:
    """The flat DFS wrapper shape (`{"items": [...]}`) `_normalize_dfs_response`
    tolerates — the simplest deterministic synthetic payload."""
    return {"items": items}


def _kw(keyword: str, volume: int, *, intent: str | None = None) -> dict:
    item = {"keyword": keyword, "keyword_info": {"search_volume": volume}}
    if intent is not None:
        item["search_intent_info"] = {"main_intent": intent}
    return item


def _arrange_and_run_chain(raw_dir: Path, out_dir: str) -> dict:
    """Write the smallest valid canned input per step and run the THREE real
    CLIs IN ORDER, threading each committed sheet into the next step.

    Returns the three parsed output row-lists keyed by sheet name.
    """
    # --- Step 1: topical_map ------------------------------------------------
    # keyword_ideas + related_keywords -> pillar "dental implants" + three
    # cluster rows (cost / procedure / pain). The cluster column of these rows
    # becomes cluster_map's cluster_defs (the dependency hand-off).
    ideas = raw_dir / "topical_ideas.json"
    related = raw_dir / "topical_related.json"
    ideas.write_text(json.dumps(_flat([
        _kw("dental implants", 5000),
        _kw("dental implants cost", 800),
        _kw("dental implants procedure", 400),
    ])), encoding="utf-8")
    related.write_text(json.dumps(_flat([
        _kw("dental implants cost", 800),
        _kw("dental implants pain", 300),
    ])), encoding="utf-8")
    _run_real_cli([
        str(_TRANSFORM_CLI["topical_map"]),
        "--raw-keyword-ideas", str(ideas),
        "--raw-related-keywords", str(related),
        "--seed-keyword", SEED,
        "--output-dir", out_dir,
    ])
    topical_rows = json.loads(
        (Path(out_dir) / "topical_map.json").read_text(encoding="utf-8")
    )

    # DEPENDENCY HAND-OFF 1: extract the committed topical_map `cluster` column
    # (the model reads master.xlsx#topical_map column B) -> cluster_defs JSON.
    cluster_defs = sorted({r["cluster"] for r in topical_rows if r.get("cluster")})
    defs_path = raw_dir / "cluster_defs.json"
    defs_path.write_text(json.dumps(cluster_defs), encoding="utf-8")

    # --- Step 2: cluster_map (consumes topical_map via --cluster-defs-json) --
    sugg = raw_dir / "cluster_sugg.json"
    rel2 = raw_dir / "cluster_related.json"
    gsc = raw_dir / "cluster_gsc.json"
    sugg.write_text(json.dumps(_flat([
        _kw("dental implants cost calculator", 200),
        _kw("best dental implants procedure", 150),
    ])), encoding="utf-8")
    rel2.write_text(json.dumps(_flat([
        _kw("dental implants pain relief", 100),
    ])), encoding="utf-8")
    gsc.write_text(json.dumps({"rows": [
        {"keys": ["dental implants cost calculator", "https://dental.example/cost"],
         "clicks": 10, "impressions": 200, "position": 5.0},
    ]}), encoding="utf-8")
    _run_real_cli([
        str(_TRANSFORM_CLI["cluster_map"]),
        "--raw-keyword-suggestions", str(sugg),
        "--raw-related-keywords", str(rel2),
        "--raw-gsc", str(gsc),
        "--cluster-defs-json", str(defs_path),
        "--seed-keyword", SEED,
        "--project-slug", SLUG,
        "--output-dir", out_dir,
    ])
    cluster_rows = json.loads((Path(out_dir) / "cluster_keywords.json").read_text("utf-8"))

    # DEPENDENCY HAND-OFF 2: build {keyword: cluster} from the committed
    # cluster_keywords sheet (the model reads master.xlsx#cluster_keywords via
    # read_cluster_keywords_snapshot) -> --cluster-map JSON for new_content_plan.
    cluster_map = {r["keyword"]: r["cluster"] for r in cluster_rows}
    cluster_map_path = raw_dir / "cluster_map.json"
    cluster_map_path.write_text(json.dumps(cluster_map), encoding="utf-8")

    # --- Step 3: new_content_plan (consumes cluster_keywords via --cluster-map)
    # The content-gaps staging is the plan's keyword universe; assigned_cluster
    # is cross-referenced from the cluster_map (= the prior committed sheet).
    staging = raw_dir / "content_gaps_staging.json"
    staging.write_text(json.dumps({"schema_version": "1.0", "tool": "keyword_ideas",
        "rows": [
            {"id": 1, "keyword": "dental implants cost calculator",
             "search_volume": 200, "gap_score": 600},
            {"id": 2, "keyword": "best dental implants procedure",
             "search_volume": 150, "gap_score": 400},
        ]}), encoding="utf-8")
    _run_real_cli([
        str(_TRANSFORM_CLI["new_content_plan"]),
        "--staging", str(staging),
        "--cluster-map", str(cluster_map_path),
        "--date", "2026-06-08",
        "--output-dir", out_dir,
    ])
    plan_rows = json.loads((Path(out_dir) / "new_content_plan.json").read_text("utf-8"))

    return {
        "topical_map": topical_rows,
        "cluster_keywords": cluster_rows,
        "new_content_plan": plan_rows,
    }


def test_every_setup_output_file_is_sheet_named() -> None:
    """Unlike 3b's schema_audit (the 1d.1 trap), ALL THREE setup CLIs write
    `{sheet}.json` — the explicit output_file equals {sheet}.json for each."""
    for entry in STEPS:
        assert entry["output_file"] == f"{entry['sheet']}.json", entry["name"]


def test_real_setup_clis_run_in_order_and_outputs_land_where_loader_reads(
    tmp_path: Path,
) -> None:
    """Run the THREE real CLIs IN ORDER (threading each committed sheet into the
    next), then assert (1) each declared output_file exists in the driver's
    transform dir and (2) the REAL loader build_steps wired reads exactly it."""
    transform_dir = output_path(tmp_path, RUN_ID, SLUG, "_probe.json").parent
    transform_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _arrange_and_run_chain(raw_dir, str(transform_dir))

    specs = {s.name: s for s in build_steps(RUN_ID, SLUG, tmp_path)}
    for entry in STEPS:
        out_file = output_path(tmp_path, RUN_ID, SLUG, entry["output_file"])
        assert out_file.exists(), (
            f"{entry['name']}: CLI did not write {entry['output_file']} "
            f"(looked at {out_file})"
        )
        rows = specs[entry["name"]].transform([{"ignored": "raw"}])
        assert isinstance(rows, list) and rows, entry["name"]


def test_dependency_chain_cluster_map_consumes_topical_map(tmp_path: Path) -> None:
    """The PROOF that cluster_map consumed topical_map: every committed
    cluster_keywords.cluster value MUST be one of topical_map's `cluster`
    column values (D-02; the cluster_defs hand-off). Empty would mean the chain
    is broken."""
    transform_dir = output_path(tmp_path, RUN_ID, SLUG, "_probe.json").parent
    transform_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = _arrange_and_run_chain(raw_dir, str(transform_dir))

    topical_clusters = {r["cluster"] for r in out["topical_map"] if r.get("cluster")}
    cluster_keyword_clusters = {r["cluster"] for r in out["cluster_keywords"]}
    assert cluster_keyword_clusters, "cluster_map produced zero rows — chain broken"
    assert cluster_keyword_clusters <= topical_clusters, (
        f"cluster_keywords.cluster {cluster_keyword_clusters} not a subset of "
        f"topical_map.cluster {topical_clusters} — dependency hand-off failed"
    )


def test_dependency_chain_new_content_plan_consumes_cluster_keywords(
    tmp_path: Path,
) -> None:
    """The PROOF that new_content_plan consumed cluster_keywords: at least one
    plan row's assigned_cluster MUST be filled from the cluster_map built off
    the committed cluster_keywords sheet."""
    transform_dir = output_path(tmp_path, RUN_ID, SLUG, "_probe.json").parent
    transform_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = _arrange_and_run_chain(raw_dir, str(transform_dir))

    cluster_keyword_clusters = {r["cluster"] for r in out["cluster_keywords"]}
    assigned = {r["assigned_cluster"] for r in out["new_content_plan"]
                if r.get("assigned_cluster")}
    assert assigned, (
        "no new_content_plan row received an assigned_cluster — the cluster_map "
        "hand-off from cluster_keywords did not reach the plan"
    )
    assert assigned <= cluster_keyword_clusters, (
        f"new_content_plan.assigned_cluster {assigned} not drawn from "
        f"cluster_keywords.cluster {cluster_keyword_clusters}"
    )
