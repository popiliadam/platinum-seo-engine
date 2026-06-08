"""The ``content`` workflow: new_blog -> generate_images -> faq_optimization.

The blog-content production pipeline. Unlike the DATA drivers
(``monthly_maintenance``/``audit_suite``/``new_project_setup`` — raw MCP drop ->
transform CLI -> ``verify_raw_drop`` -> ``committer`` -> master.xlsx sheet rows),
the content steps produce a BLOG HTML ARTIFACT: the MODEL generates
``outputs/blog/<post>/article.html`` (+ schema.jsonld, meta-tags.json, hero
images) from a ``new_content_plan`` row. There is NO transform CLI, NO raw drop,
NO sheet to commit — the three production skills are READ-ONLY w.r.t. master.xlsx
(new-blog/faq write only ``outputs/blog/...``; generate-images never calls
``transaction.append``). So this driver CANNOT mirror the data drivers
(run_step/verify_raw_drop/committer) and there is NO 1b2 write-relocation here.

It is an ARTIFACT driver. Each step is ``model_attested`` (content QUALITY is not
code-checkable — spec §11), and the per-step verification the CODE owns is:

  * the expected artifact EXISTS, AND
  * (for an HTML artifact) it carries NO AI-disclosure signal — the deterministic
    ``content_validator.validate_content(html).has_red`` gate (Süleyman's hardest
    constraint: "AI tarafından yazıldı" must never appear in visible HTML). This
    is the EXACT same detector batch 2e's ``ai_disclosure_rescan`` quarantines
    with and the write-time ``validate_content_write`` hook blocks with, so the
    workflow-level check and the write-time hook agree by construction.

The workflow therefore GUARANTEES "every production step ran + produced its
artifact + the artifact carries no AI-disclosure signal"; it does NOT (and cannot)
verify the content is *good* — that is the QA loop, measured separately.

Artifact resolution (build_steps):

  * new_blog / faq_optimization -> ``article.html`` under ``blog_output_dir`` (THIS
    run's blog dir, ``projects/<slug>/outputs/blog/<post>/`` — the recipe supplies
    it via ``--blog-output-dir`` because the ``<post>`` segment encodes which post;
    faq_optimization ENHANCES the same file in place, so both steps verify it).
  * generate_images -> the project hero-image dir
    ``projects/<slug>/outputs/images/`` (a SIBLING of the blog dir — that is where
    the generate-images skill writes ``<slug>-hero.{webp,avif,jpg}``), resolved
    from ``workspace_root`` + ``project_slug``. EXISTS-only (images aren't HTML);
    higgsfield is an external user-MCP often absent headless, so a missing images
    dir is a normal ``missing``, never a crash.

Because every step is model_attested (which ``derive_verdict`` treats as SOFT, and
``required_satisfied`` is vacuously True over zero code_verified steps), a missing
step alone would read 'pass'. The deliverable IS the produced blog, so the
COMPLETION GUARD downgrades pass -> incomplete unless every step is satisfied — it
is load-bearing for this all-attested workflow (the same situation as ``setup``).

Pure + clock-free: ``run_id`` and ``now_epoch`` are passed IN (the CLI requires
``--now-epoch`` for symmetry with the data drivers); the artifact driver has no
freshness gate, so ``now_epoch`` is reserved and not used in verification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from scripts.orchestration import coverage
from scripts.orchestration.remediation import remediation, render
from scripts.validation.content_validator import validate_content

WORKFLOW = "content"

# Module-level ORDERED step table (data-driven). NONE carries a ``sheet`` key:
# the content skills write artifacts, not master.xlsx rows, so there is NO
# committer and NO 1b2 write-relocation. ``base`` selects the artifact anchor:
# ``blog`` = under ``blog_output_dir`` (the per-post article.html); ``images`` =
# the project-level ``outputs/images`` dir (sibling of the blog dir). ``is_html``
# gates the disclosure check: True -> run content_validator; False -> EXISTS-only.
# Every step is ``model_attested`` (content quality is not code-checkable).
STEPS: tuple[dict, ...] = (
    {"name": "new_blog", "base": "blog", "artifact": "article.html",
     "is_html": True, "verification_class": "model_attested"},
    {"name": "generate_images", "base": "images", "artifact": "images",
     "is_html": False, "verification_class": "model_attested"},
    {"name": "faq_optimization", "base": "blog", "artifact": "article.html",
     "is_html": True, "verification_class": "model_attested"},
)


@dataclass(frozen=True)
class ArtifactStep:
    """One resolved artifact-verification step (immutable)."""

    name: str
    path: Path
    is_html: bool
    verification_class: str


def verify_artifact(
    artifact_path: Path | str, *, is_html: bool, profile: str | None = None
) -> str:
    """Coverage STATUS for one produced artifact.

    Pure-ish (one ``exists`` + one ``read_text`` + the frozen detector); NEVER
    raises for a missing/unreadable artifact:

      * artifact missing / unreadable                       -> ``"missing"``
      * ``is_html`` AND the artifact carries an AI-disclosure
        RED signal (``ContentReport.has_red``)              -> ``"failed"``
      * otherwise (present; non-HTML, or HTML disclosure-clean) -> ``"satisfied"``

    The RED branch is the CODE-verified part of an otherwise model_attested
    content step: content QUALITY is not code-checkable, but the deterministic
    AI-disclosure gate IS (Süleyman hard-constraint #2). ``has_red`` is
    profile-independent, so ``profile`` only tunes the (irrelevant here) AMBER
    advisories; it is accepted for signature symmetry and passed through.
    """
    path = Path(artifact_path)
    if not path.exists():
        return "missing"
    if is_html:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "missing"
        if validate_content(text, profile=profile).has_red:
            return "failed"
    return "satisfied"


def build_steps(
    blog_output_dir: Path | str, workspace_root: Path | str, project_slug: str
) -> list[ArtifactStep]:
    """One ArtifactStep per STEPS entry, each artifact path resolved.

    ``blog`` artifacts resolve under ``blog_output_dir`` (THIS run's per-post blog
    dir); the ``images`` artifact resolves to the project-level
    ``projects/<slug>/outputs/images`` dir the generate-images skill writes to.
    """
    blog = Path(blog_output_dir)
    project_outputs = Path(workspace_root) / "projects" / project_slug / "outputs"
    steps: list[ArtifactStep] = []
    for entry in STEPS:
        if entry["base"] == "images":
            path = project_outputs / entry["artifact"]
        else:
            path = blog / entry["artifact"]
        steps.append(
            ArtifactStep(
                name=entry["name"],
                path=path,
                is_html=entry["is_html"],
                verification_class=entry["verification_class"],
            )
        )
    return steps


def run(
    run_id: str, project_slug: str, workspace_root: Path | str,
    blog_output_dir: Path | str, now_epoch: float, *, write: bool = True,
    engine_version: str | None = None,
) -> dict:
    """Verify each produced artifact + record coverage for a content-pipeline run.

    Every step is ``model_attested`` (content quality is not code-checkable), which
    ``derive_verdict`` treats as SOFT, so a missing step alone would read 'pass'.
    The deliverable IS the produced blog, so the COMPLETION GUARD downgrades
    pass -> incomplete unless EVERY step is satisfied (load-bearing here). NO
    committer: the steps produce artifacts, not master.xlsx rows. ``now_epoch`` is
    accepted for CLI symmetry with the data drivers but unused (no freshness gate).
    """
    steps = [
        coverage.build_step(
            spec.name, spec.verification_class,
            verify_artifact(spec.path, is_html=spec.is_html),
            observed_mcp=[],
        )
        for spec in build_steps(blog_output_dir, workspace_root, project_slug)
    ]
    required_satisfied, verdict = coverage.derive_verdict(steps)
    # Every step is model_attested (SOFT) and there are zero code_verified steps,
    # so a missing artifact step alone would read 'pass'. The deliverable is the
    # produced blog, so any non-satisfied step downgrades pass -> incomplete.
    if verdict == "pass" and not all(s["status"] == "satisfied" for s in steps):
        verdict = "incomplete"
    record = coverage.build_record(
        run_id=run_id, steps=steps, required_satisfied=required_satisfied,
        verdict=verdict, project_slug=project_slug, engine_version=engine_version,
    )
    if write:
        coverage.write_coverage(
            record, workspace_root=workspace_root, project_slug=project_slug,
            run_id=run_id,
        )
    return record


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.orchestration.workflows.content_pipeline",
        description="Verify produced blog artifacts + record coverage for a "
        "content-pipeline run.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--blog-output-dir", required=True)
    parser.add_argument("--now-epoch", required=True, type=float)
    parser.add_argument("--engine-version", default=None)
    parser.add_argument("--no-write", dest="write", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI boundary: parse args, run the driver, surface the Turkish remediation."""
    args = _build_arg_parser().parse_args(argv)
    record = run(
        args.run_id, args.slug, Path(args.workspace_root),
        Path(args.blog_output_dir), args.now_epoch, write=args.write,
        engine_version=args.engine_version,
    )
    print(f"verdict: {record['verdict']}")
    fix = remediation(record, slug=args.slug, workflow=WORKFLOW)
    if fix is not None:
        print(render(fix))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
