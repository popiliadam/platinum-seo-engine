"""REAL transform-CLI boundary for the audit-suite driver (AMO batch 3b, 1d.1 GUARD).

The stub e2e tests (test_audit_suite.py) hand-write canned OUTPUT files; they
cannot catch a filename mismatch between the EXISTING transform CLIs and the path
the driver's loader reads. This module runs the FOUR real CLIs as subprocesses on
minimal canned raw inputs and then drives the REAL loader wired by build_steps,
proving each CLI writes its output exactly where the driver expects to read it.

This locks the step -> output_file map — especially schema_audit, whose CLI writes
``schema_audit.json`` though its sheet is ``schema`` (the 1d.1 trap the audit suite
must carry an explicit output_file for; monthly's "{sheet}.json" assumption breaks
here). These transforms are pure raw-JSON-in -> rows-JSON-out (never network/MCP),
so they MUST run headless; a non-zero exit is a DURUR-class integration gap.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.orchestration.workflows.audit_suite import STEPS, build_steps, output_path

RUN_ID = "vento-2026-06-08-c3d4"
SLUG = "vento"

REPO_ROOT = Path(__file__).resolve().parents[2]
_TRANSFORM_CLI = {
    "tech_audit": REPO_ROOT / "scripts" / "discovery" / "tech_audit_transform.py",
    "schema_audit": REPO_ROOT / "scripts" / "discovery" / "schema_audit_transform.py",
    "on_page_audit": REPO_ROOT / "scripts" / "discovery" / "on_page_audit_transform.py",
    "cannibalization": REPO_ROOT / "scripts" / "discovery" / "cannibalization_transform.py",
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


def _arrange_and_run_transforms(raw_dir: Path, out_dir: str) -> None:
    """Write the smallest valid canned raw input for each step and run its REAL
    transform CLI into out_dir.

    - tech_audit: TWO inputs (--lighthouse + --content-parsing); a flat perf
      score < 50 yields a Performance finding so tech_seo.json has >=1 row.
    - schema_audit: --raw-sf with one JSON-LD blob (Product missing image/offers
      -> one TODO row).
    - on_page_audit: --raw-content-parsing; one item with url/title/meta/h1.
    - cannibalization: --raw with two pages on the same query above K impressions
      -> one conflict row.
    """
    lh = raw_dir / "tech_lighthouse.json"
    cp = raw_dir / "tech_content.json"
    lh.write_text(json.dumps({"items": [
        {"url": "https://vento.example/p1", "performance_score": 0.4, "lcp": 3.2},
    ]}), encoding="utf-8")
    cp.write_text(json.dumps({"items": [
        {"url": "https://vento.example/p1", "title": "T",
         "meta": {"description": "d"}, "h1": ["H"]},
    ]}), encoding="utf-8")
    _run_real_cli([str(_TRANSFORM_CLI["tech_audit"]),
                   "--lighthouse", str(lh), "--content-parsing", str(cp),
                   "--output-dir", out_dir])

    sf = raw_dir / "schema_sf.json"
    sf.write_text(json.dumps({"rows": [
        {"address": "https://vento.example/p1",
         "json_ld": json.dumps({"@type": "Product", "name": "X"})},
    ]}), encoding="utf-8")
    _run_real_cli([str(_TRANSFORM_CLI["schema_audit"]),
                   "--raw-sf", str(sf), "--output-dir", out_dir])

    op = raw_dir / "onpage_content.json"
    op.write_text(json.dumps({"items": [
        {"url": "https://vento.example/p1", "title": "T",
         "meta_description": "d", "h1": ["H"]},
    ]}), encoding="utf-8")
    _run_real_cli([str(_TRANSFORM_CLI["on_page_audit"]),
                   "--raw-content-parsing", str(op), "--output-dir", out_dir])

    gsc = raw_dir / "cann_gsc.json"
    gsc.write_text(json.dumps({"rows": [
        {"keys": ["kw", "https://vento.example/p1"],
         "impressions": 100, "clicks": 5, "position": 3},
        {"keys": ["kw", "https://vento.example/p2"],
         "impressions": 100, "clicks": 5, "position": 8},
    ]}), encoding="utf-8")
    _run_real_cli([str(_TRANSFORM_CLI["cannibalization"]),
                   "--raw", str(gsc), "--output-dir", out_dir])


def test_schema_audit_output_file_differs_from_sheet() -> None:
    """Static lock of the 1d.1 trap: schema_audit's output_file is NOT {sheet}.json."""
    e = next(x for x in STEPS if x["name"] == "schema_audit")
    assert e["sheet"] == "schema"
    assert e["output_file"] == "schema_audit.json"
    assert e["output_file"] != f"{e['sheet']}.json"
    # the other three DO write {sheet}.json — the asymmetry is the whole point.
    for name in ("tech_audit", "on_page_audit", "cannibalization"):
        other = next(x for x in STEPS if x["name"] == name)
        assert other["output_file"] == f"{other['sheet']}.json"


def test_real_audit_cli_outputs_land_where_loader_reads(tmp_path: Path) -> None:
    """For EACH audit step, the REAL transform CLI (run with --output-dir pointed
    at the driver's transform dir) must write the file the driver's loader reads.
    Asserted two ways: (1) the declared output_file exists, and (2) the loader
    wired by build_steps actually loads it — catching the output_file vs sheet
    impedance (RED on schema_audit if it were keyed on {sheet}.json)."""
    transform_dir = output_path(tmp_path, RUN_ID, SLUG, "_probe.json").parent
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _arrange_and_run_transforms(raw_dir, str(transform_dir))

    specs = {s.name: s for s in build_steps(RUN_ID, SLUG, tmp_path)}
    for entry in STEPS:
        # (1) the CLI wrote the declared output_file into the transform dir
        out_file = output_path(tmp_path, RUN_ID, SLUG, entry["output_file"])
        assert out_file.exists(), (
            f"{entry['name']}: CLI did not write {entry['output_file']} "
            f"(looked at {out_file})"
        )
        # (2) the REAL loader build_steps wired reads exactly that file
        # (ignores the raw arg, returns the loaded row list)
        rows = specs[entry["name"]].transform([{"ignored": "raw"}])
        assert isinstance(rows, list) and rows, entry["name"]


def test_schema_audit_cli_does_not_write_sheet_named_file(tmp_path: Path) -> None:
    """Belt-and-braces for the trap: the schema_audit CLI writes schema_audit.json
    and NOT schema.json, so a loader keyed on {sheet}.json would find nothing."""
    transform_dir = output_path(tmp_path, RUN_ID, SLUG, "_probe.json").parent
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _arrange_and_run_transforms(raw_dir, str(transform_dir))
    assert output_path(tmp_path, RUN_ID, SLUG, "schema_audit.json").exists()
    assert not output_path(tmp_path, RUN_ID, SLUG, "schema.json").exists()
