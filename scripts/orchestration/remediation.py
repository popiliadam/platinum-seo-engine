"""Operator-remediation surface for the AMO workflow driver (Phase-1 first-class).

A run that does not reach ``verdict == "pass"`` must always leave a non-coder
operator (Mac app) with exactly ONE next action: a copy-pasteable Turkish
one-line fix command. ``remediation`` turns a coverage record into a structured
remediation dict (or None when the run passed); ``render`` formats that dict into
a compact, model-visible block whose LAST line is the fix command.

Pure: reads only the passed record, builds new objects, never mutates inputs,
performs no IO and reads no clock.
"""
from __future__ import annotations

from typing import Any

# Turkish 'why' templates, keyed by verdict. 'paused' frames an EXTERNAL
# dependency (GSC/DFS) that --resume retries; the others name the offending steps.
_WHY_PAUSED = (
    "Çalışma harici bir bağımlılıkta (GSC/DFS) duraklatıldı; "
    "`--resume` ile kaldığı yerden devam eder."
)


def _unsatisfied_step_names(record: dict) -> list[str]:
    """Names of steps that did not reach status 'satisfied', in record order."""
    return [
        step["name"]
        for step in record.get("steps", [])
        if step.get("status") != "satisfied"
    ]


def _why_turkish(verdict: str, missing: list[str]) -> str:
    """One Turkish sentence: external-dependency framing for paused, else the
    offending step names."""
    if verdict == "paused":
        return _WHY_PAUSED
    names = ", ".join(missing) if missing else "—"
    if verdict == "failed":
        return f"Şu adımlar başarısız oldu: {names}; `--resume` ile yeniden dener."
    return f"Şu adımlar eksik kaldı: {names}; `--resume` eksik adımları tamamlar."


def remediation(
    coverage_record: dict, *, slug: str, workflow: str = "monthly"
) -> dict[str, Any] | None:
    """Structured remediation for a non-pass run, or None when it passed.

    Returns a NEW dict; ``coverage_record`` is never mutated.
    """
    verdict = coverage_record.get("verdict")
    if verdict == "pass":
        return None
    missing = _unsatisfied_step_names(coverage_record)
    return {
        "missing": missing,
        "verdict": verdict,
        "one_line_fix_command": f"/pseo-run {workflow} {slug} --resume",
        "why_turkish": _why_turkish(verdict, missing),
    }


def render(remediation_dict: dict) -> str:
    """Compact operator block; the fix command is always the LAST line."""
    verdict = remediation_dict["verdict"]
    fix = remediation_dict["one_line_fix_command"]
    return (
        f"⚠️  Çalışma tamamlanmadı (verdict: {verdict}).\n"
        f"{remediation_dict['why_turkish']}\n"
        f"Düzeltmek için şunu çalıştır:\n"
        f"{fix}"
    )
