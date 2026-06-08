"""End-to-end test for the ARTIFACT-based content-pipeline driver (AMO batch 3d).

Unlike the DATA drivers (monthly/audit/setup — raw MCP drop -> transform CLI ->
verify_raw_drop -> committer -> sheet rows), the ``content`` workflow produces a
BLOG HTML ARTIFACT. The model generates ``outputs/blog/<post>/article.html``
(+ schema/meta/images) from a ``new_content_plan`` row; there is NO transform CLI,
NO raw drop, NO master.xlsx sheet to commit. So this driver CANNOT mirror
``audit_suite``/``new_project_setup`` (run_step + verify_raw_drop + committer). It
is an ARTIFACT driver: each step is ``model_attested`` (content QUALITY is not
code-checkable), and the per-step verification the CODE owns is — the expected
artifact EXISTS, and (for an HTML artifact) it passes the deterministic
AI-disclosure gate (``content_validator.validate_content(html).has_red`` is False —
the SAME detector batch 2e's ``ai_disclosure_rescan`` quarantines with + Süleyman's
hard-constraint #2).

The CLEAN/RED fixtures mirror ``tests/validation/test_content_validator.py`` (a
clean ``pse-`` article -> GREEN; a "written by AI" article -> RED). The driver's
verdict + completion-guard + the Turkish ``/pseo-run content <slug> --resume``
remediation are asserted per scenario, and every record is proven to validate
against the frozen ``schemas/coverage.schema.json``.

Because all three steps are ``model_attested`` (SOFT in ``derive_verdict``, and
``required_satisfied`` is vacuously True over zero code_verified steps), a missing
step alone would read 'pass'. The deliverable IS the produced blog, so the
COMPLETION GUARD (pass -> incomplete unless every step is satisfied) is load-bearing
here — exactly the all-attested situation as ``setup``.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from scripts.hooks.validate_content_write import is_content_html_path
from scripts.orchestration import coverage
from scripts.orchestration.remediation import remediation
from scripts.orchestration.workflows import content_pipeline
from scripts.orchestration.workflows.content_pipeline import (
    STEPS,
    build_steps,
    run,
    verify_artifact,
)

RUN_ID = "demo-furniture-2026-06-08-c3d4"
SLUG = "demo-furniture"
# The <post> path segment is supplied by the recipe via --blog-output-dir (it
# encodes which post). Deliberately DISTINCT from SLUG to prove the driver does
# NOT assume post == slug — it verifies article.html under WHATEVER blog dir it is
# given. (The current new-blog SKILL.md happens to use post == slug.)
POST = "first-blog-post"
NOW = 1_750_000_000

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)

ALL_STEPS = ["new_blog", "generate_images", "faq_optimization"]

# Reuse the content_validator fixtures: a clean pse- article (GREEN, no RED) and
# an AI-disclosure article ("written by AI" -> RED). has_red is the only signal
# the artifact gate consumes, and it is profile-independent.
CLEAN_HTML = (
    '<article class="pse-blog-post"><p class="pse-lead">Temiz ve özgün '
    "içerik.</p></article>"
)
RED_HTML = (
    '<article class="pse-blog-post"><p>This article was written by AI to '
    "save time.</p></article>"
)


def _schema_errors(record: dict) -> list:
    return list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(record))


def _blog_dir(workspace: Path) -> Path:
    """THIS run's blog output dir: projects/<slug>/outputs/blog/<post>/."""
    return workspace / "projects" / SLUG / "outputs" / "blog" / POST


def _images_dir(workspace: Path) -> Path:
    """The project-level hero-image dir the generate-images skill writes to:
    projects/<slug>/outputs/images/ (a SIBLING of the blog dir, not under it)."""
    return workspace / "projects" / SLUG / "outputs" / "images"


def _write_article(workspace: Path, html: str = CLEAN_HTML) -> Path:
    blog_dir = _blog_dir(workspace)
    blog_dir.mkdir(parents=True, exist_ok=True)
    path = blog_dir / "article.html"
    path.write_text(html, encoding="utf-8")
    return path


def _make_images_dir(workspace: Path) -> Path:
    images = _images_dir(workspace)
    images.mkdir(parents=True, exist_ok=True)
    return images


# --- step table -----------------------------------------------------------

def test_step_table_is_the_three_content_steps() -> None:
    assert [e["name"] for e in STEPS] == ALL_STEPS


def test_step_table_all_steps_are_model_attested() -> None:
    """Content QUALITY is not code-checkable (spec §11): every step is
    model_attested. There is NO code_verified step (no per-row ingestion), so the
    completion guard is the only completeness enforcer."""
    assert all(e["verification_class"] == "model_attested" for e in STEPS)


def test_step_table_is_html_flags() -> None:
    """article.html steps (new_blog, faq_optimization) run the disclosure gate;
    the images step is EXISTS-only (images aren't HTML)."""
    by = {e["name"]: e for e in STEPS}
    assert by["new_blog"]["is_html"] is True
    assert by["faq_optimization"]["is_html"] is True
    assert by["generate_images"]["is_html"] is False


def test_no_step_writes_a_master_sheet_marker() -> None:
    """The 3 production skills are READ-ONLY w.r.t. master.xlsx (no
    transaction.append) -> the STEPS table carries NO 'sheet' key: there is NO
    1b2 write-relocation and NO committer."""
    assert all("sheet" not in e for e in STEPS)


# --- verify_artifact (the CODE-owned per-step check) ----------------------

def test_verify_artifact_clean_html_is_satisfied(tmp_path: Path) -> None:
    path = tmp_path / "article.html"
    path.write_text(CLEAN_HTML, encoding="utf-8")
    assert verify_artifact(path, is_html=True) == "satisfied"


def test_verify_artifact_missing_html_is_missing(tmp_path: Path) -> None:
    assert verify_artifact(tmp_path / "nope.html", is_html=True) == "missing"


def test_verify_artifact_ai_disclosure_red_html_is_failed(tmp_path: Path) -> None:
    """The deterministic AI-disclosure gate fires at the workflow level: a RED
    article.html -> 'failed'. This is the CODE-verified part of an otherwise
    model_attested content step (Süleyman hard-constraint #2)."""
    path = tmp_path / "article.html"
    path.write_text(RED_HTML, encoding="utf-8")
    assert verify_artifact(path, is_html=True) == "failed"


def test_verify_artifact_images_dir_present_is_satisfied(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    assert verify_artifact(images, is_html=False) == "satisfied"


def test_verify_artifact_images_dir_absent_is_missing(tmp_path: Path) -> None:
    """A missing images dir on a headless run (no higgsfield) is a normal
    'missing', never a crash."""
    assert verify_artifact(tmp_path / "images", is_html=False) == "missing"


def test_verify_artifact_is_html_false_skips_content_scan(tmp_path: Path) -> None:
    """is_html=False (images) is EXISTS-only: a file whose bytes would be RED is
    NOT scanned (images aren't HTML, and the content gate must not run on them)."""
    blob = tmp_path / "not-html"
    blob.write_text(RED_HTML, encoding="utf-8")
    assert verify_artifact(blob, is_html=False) == "satisfied"


def test_verify_artifact_never_raises_on_unreadable_html(tmp_path: Path) -> None:
    """is_html=True on a path that exists but cannot be read as text (a dir) ->
    'missing', never an exception."""
    d = tmp_path / "article.html"
    d.mkdir()
    assert verify_artifact(d, is_html=True) == "missing"


# --- scope agreement with the write-time hook (reuse the SAME predicate) ---

def test_is_html_flags_agree_with_hook_scope_predicate(tmp_path: Path) -> None:
    """By construction the driver's HTML gate scope matches the write-time hook:
    article.html under outputs/blog/ IS a content-html path (gate runs); the
    project images dir is NOT (.html-less). Same is_content_html_path batch 2e's
    rescan reuses -> the workflow-level check and the hook agree."""
    blog_dir = _blog_dir(tmp_path)
    assert is_content_html_path(str(blog_dir / "article.html")) is True
    assert is_content_html_path(str(_images_dir(tmp_path))) is False


# --- build_steps wiring ----------------------------------------------------

def test_build_steps_resolves_one_step_per_entry(tmp_path: Path) -> None:
    blog_dir = _blog_dir(tmp_path)
    steps = build_steps(blog_dir, tmp_path, SLUG)
    assert [s.name for s in steps] == ALL_STEPS
    by = {s.name: s for s in steps}
    # article.html resolves under the GIVEN blog dir (post-agnostic).
    assert by["new_blog"].path == blog_dir / "article.html"
    assert by["faq_optimization"].path == blog_dir / "article.html"
    # the images step resolves to the project-level outputs/images dir.
    assert by["generate_images"].path == _images_dir(tmp_path)
    assert by["new_blog"].is_html is True
    assert by["generate_images"].is_html is False
    assert all(s.verification_class == "model_attested" for s in steps)


# --- run() scenarios -------------------------------------------------------

def test_run_all_artifacts_clean_verdict_pass(tmp_path: Path) -> None:
    _write_article(tmp_path, CLEAN_HTML)
    _make_images_dir(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, _blog_dir(tmp_path), NOW)
    assert record["verdict"] == "pass"
    assert len(record["steps"]) == 3
    assert all(s["status"] == "satisfied" for s in record["steps"])
    assert all(s["verification_class"] == "model_attested" for s in record["steps"])
    # NO committer / sheet: steps carry no observed_mcp + no sheet provenance.
    assert _schema_errors(record) == []
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []
    assert remediation(record, slug=SLUG, workflow="content") is None


def test_run_missing_step_is_incomplete_via_completion_guard(tmp_path: Path) -> None:
    """All steps are model_attested (SOFT). A missing images dir (headless, no
    higgsfield) alone would read 'pass' (required_satisfied vacuously True). The
    deliverable is the produced blog, so the completion guard downgrades pass ->
    incomplete — the load-bearing guard for this all-attested workflow."""
    _write_article(tmp_path, CLEAN_HTML)
    # NO images dir -> generate_images missing.
    record = run(RUN_ID, SLUG, tmp_path, _blog_dir(tmp_path), NOW, write=False)
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses["generate_images"] == "missing"
    assert statuses["new_blog"] == "satisfied"
    assert record["verdict"] != "pass"
    assert record["verdict"] == "incomplete"
    rem = remediation(record, slug=SLUG, workflow="content")
    assert rem is not None
    assert "generate_images" in rem["missing"]
    assert rem["one_line_fix_command"] == "/pseo-run content demo-furniture --resume"


def test_run_ai_disclosure_red_article_fails_the_step(tmp_path: Path) -> None:
    """An AI-disclosure RED article.html -> the new_blog AND faq_optimization
    steps (both verify article.html) read 'failed' -> verdict 'failed'. The
    workflow-level disclosure gate fires independent of the write-time hook."""
    _write_article(tmp_path, RED_HTML)
    _make_images_dir(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, _blog_dir(tmp_path), NOW, write=False)
    statuses = {s["name"]: s["status"] for s in record["steps"]}
    assert statuses["new_blog"] == "failed"
    assert statuses["faq_optimization"] == "failed"
    assert record["verdict"] == "failed"


def test_run_headless_no_images_does_not_crash(tmp_path: Path) -> None:
    """generate-images uses higgsfield (an external user-MCP, often absent
    headless); a missing images dir is a normal 'missing', never a crash — and the
    HTML steps still verify."""
    _write_article(tmp_path, CLEAN_HTML)
    record = run(RUN_ID, SLUG, tmp_path, _blog_dir(tmp_path), NOW, write=False)
    by = {s["name"]: s["status"] for s in record["steps"]}
    assert by["generate_images"] == "missing"
    assert by["new_blog"] == "satisfied"
    assert by["faq_optimization"] == "satisfied"


def test_run_steps_are_in_declared_order(tmp_path: Path) -> None:
    _write_article(tmp_path, CLEAN_HTML)
    _make_images_dir(tmp_path)
    record = run(RUN_ID, SLUG, tmp_path, _blog_dir(tmp_path), NOW, write=False)
    assert [s["name"] for s in record["steps"]] == ALL_STEPS


# --- CLI boundary (clock-free: --now-epoch is required) --------------------

def test_cli_no_artifacts_prints_content_remediation_and_writes_coverage(
    tmp_path: Path, capsys
) -> None:
    rc = content_pipeline.main([
        "--workspace-root", str(tmp_path), "--slug", SLUG, "--run-id", RUN_ID,
        "--blog-output-dir", str(_blog_dir(tmp_path)), "--now-epoch", str(NOW),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/pseo-run content demo-furniture --resume" in out
    assert "incomplete" in out  # no artifacts -> all missing -> incomplete
    written = json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )
    assert _schema_errors(written) == []


def test_cli_happy_path_exits_zero_and_prints_pass(tmp_path: Path, capsys) -> None:
    _write_article(tmp_path, CLEAN_HTML)
    _make_images_dir(tmp_path)
    rc = content_pipeline.main([
        "--workspace-root", str(tmp_path), "--slug", SLUG, "--run-id", RUN_ID,
        "--blog-output-dir", str(_blog_dir(tmp_path)), "--now-epoch", str(NOW),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "verdict: pass" in out
