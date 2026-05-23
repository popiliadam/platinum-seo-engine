"""Brand onboarding Stage C — Atomic write of approved entries to project.config.json.

Stage A discovered draft bank entries. Stage B let the operator approve /
edit / reject each one. Stage C is the persistence layer — it validates
the approved batch in full, builds the canonical entry shape, and writes
both bank arrays back into ``projects/{slug}/project.config.json`` atomically.

R-44 source verification is enforced HERE (not in Stage B) so the gate
lives at a single, well-defined boundary:
  - every experience entry MUST carry a non-empty ``evidence_url``.
  - every research entry MUST carry a non-empty ``url``.

Atomicity: if ANY entry in the batch fails validation, the file stays
exactly as it was — no partial writes, no half-applied changes. The
caller gets ``{"status": "error", "error": "<reason>"}`` and can decide
whether to surface the message for operator correction.

Entry shape (canonical going forward):
  experience_database items:
    id, context (mirrors claim_core for schema-required compat),
    claim_core, evidence_url, evidence_type, verified_date,
    + R-121 fields (applicable_topics, phrasings,
      last_used_in_content_id, max_usage_per_month).
  original_research_database items:
    id, title, methodology, sample_size, url, publication_date,
    + R-121 fields + key_findings.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

#: R-121 default density cap. Operator can edit per entry post-write.
_DEFAULT_MAX_USAGE_PER_MONTH = 3


def write_bank_entries(
    project_slug: str,
    review_output: dict,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """Append validated approved entries to project.config.json.

    Returns:
        ``{"status": "success", "experience_added": int,
            "research_added": int}`` on success.
        ``{"status": "error", "error": "<reason>"}`` if any entry
        fails validation (no file write happens in this case).
    """
    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    config_path = workspace_root / "projects" / project_slug / "project.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    topic_candidates: list[str] = list(review_output.get("topic_candidates", []))

    # Validate + build every new entry BEFORE touching the file.
    new_exp: list[dict] = []
    for raw in review_output.get("approved_experience", []):
        if not raw.get("evidence_url"):
            return {
                "status": "error",
                "error": (
                    "R-44 enforcement: every experience entry MUST carry a "
                    f"non-empty evidence_url (entry claim_core={raw.get('claim_core')!r})"
                ),
            }
        new_exp.append(_build_experience_entry(raw, topic_candidates))

    new_res: list[dict] = []
    for raw in review_output.get("approved_research", []):
        if not raw.get("url"):
            return {
                "status": "error",
                "error": (
                    "R-44 enforcement: every research entry MUST carry a "
                    f"non-empty url (entry title={raw.get('title')!r})"
                ),
            }
        new_res.append(_build_research_entry(raw, topic_candidates))

    # All validation passed — atomic apply.
    cs = config.setdefault("content_settings", {})
    cs.setdefault("experience_database", []).extend(new_exp)
    cs.setdefault("original_research_database", []).extend(new_res)

    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "success",
        "experience_added": len(new_exp),
        "research_added": len(new_res),
    }


# ---------------------------------------------------------------------------
# Entry-shape builders — canonical going-forward schema for bank entries.
# ---------------------------------------------------------------------------

def _build_experience_entry(raw: dict, topic_candidates: list[str]) -> dict:
    """Canonical experience entry shape.

    ``context`` is set to ``claim_core`` so the schema's ``required:
    ["id", "context"]`` invariant survives during the transition window
    (the field appeared in the pre-Phase-3 schema; new code uses
    ``claim_core``).
    """
    claim = raw["claim_core"]
    return {
        "id": f"exp-{uuid.uuid4().hex[:8]}",
        "context": claim,  # schema-required mirror of claim_core
        "claim_core": claim,
        "evidence_url": raw["evidence_url"],
        "evidence_type": raw.get("evidence_type", "site_reference"),
        "verified_date": raw.get("verified_date"),
        # R-121 enrichment (Task 3.1 schema v1.4)
        "applicable_topics": list(topic_candidates),
        "phrasings": list(raw.get("phrasings", [])),
        "last_used_in_content_id": None,
        "max_usage_per_month": int(
            raw.get("max_usage_per_month", _DEFAULT_MAX_USAGE_PER_MONTH)
        ),
    }


def _build_research_entry(raw: dict, topic_candidates: list[str]) -> dict:
    """Canonical research entry shape (R-114 bank-driven research)."""
    return {
        "id": f"res-{uuid.uuid4().hex[:8]}",
        "title": raw["title"],
        "methodology": raw.get("methodology", ""),
        "sample_size": raw.get("sample_size"),
        "url": raw["url"],
        "publication_date": raw.get("publication_date"),
        "key_findings": list(raw.get("key_findings", [])),
        # R-121 enrichment (Task 3.1 schema v1.4)
        "applicable_topics": list(topic_candidates),
        "phrasings": list(raw.get("phrasings", [])),
        "last_used_in_content_id": None,
        "max_usage_per_month": int(
            raw.get("max_usage_per_month", _DEFAULT_MAX_USAGE_PER_MONTH)
        ),
    }
