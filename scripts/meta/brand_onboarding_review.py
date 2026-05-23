"""Brand onboarding Stage B — Operator review of discovery output.

Stage A (``brand_onboarding_discovery.discover``) proposes draft bank
entries from public sources. Stage B asks the operator to decide
approve / edit / reject per entry; only approved (or edited+approved)
entries flow into Stage C (``brand_onboarding_write.write_bank_entries``)
and get persisted into ``project.config.json``.

The decision schema is dict-based so the calling layer (CLI, web UI,
slash command, …) can collect responses in whichever format suits
that surface, then hand a flat ``{"experience_0": {...}, "research_1":
{...}}`` mapping to ``apply_review_decisions``.

Per R-44 source verification, Stage B does NOT enforce evidence_url
presence — that gate sits in Stage C so a draft entry can survive
through the review without an evidence URL (an operator may add one
during the edit). Stage C atomically rejects the whole batch if any
approved entry lacks evidence_url.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

#: Default decision when an entry has no entry in the decisions map.
#: Safe default — operator must opt in to keep an entry.
_DEFAULT_DECISION: dict[str, str] = {"action": "reject"}


def generate_review_prompt(discovery_output: dict) -> str:
    """Render the operator-facing review prompt as markdown.

    The prompt is purely textual — UI / CLI layers display it verbatim,
    operator fills in decisions, calling layer hands the decisions dict
    to ``apply_review_decisions``.
    """
    lines: list[str] = ["# Brand Onboarding — Operator Review", ""]

    exp_count = len(discovery_output["draft_experience_entries"])
    lines.append(f"## Discovered {exp_count} experience entries")
    for i, entry in enumerate(discovery_output["draft_experience_entries"]):
        lines.append(f"\n### experience_{i}")
        lines.append(f"- **Claim:** {entry['claim_core']}")
        lines.append(f"- **Evidence:** {entry.get('evidence_url', '(none)')}")
        lines.append(
            f"- **Source:** {entry.get('source', entry.get('hint', 'unknown'))}"
        )
        lines.append("- **Action:** [A] approve / [E] edit / [R] reject")

    res_count = len(discovery_output["draft_research_entries"])
    lines.append(f"\n## Discovered {res_count} research entries")
    for i, entry in enumerate(discovery_output["draft_research_entries"]):
        lines.append(f"\n### research_{i}")
        lines.append(f"- **Title:** {entry.get('title', '(untitled)')}")
        lines.append(f"- **URL:** {entry.get('url', '(none)')}")
        lines.append(
            f"- **Methodology:** {entry.get('methodology', '(unknown)')}"
        )
        lines.append("- **Action:** [A] approve / [E] edit / [R] reject")

    lines.append("\n## Topic candidates (seeds for applicable_topics)")
    lines.append(", ".join(discovery_output["topic_candidates"]) or "(none)")

    return "\n".join(lines)


def apply_review_decisions(
    discovery_output: dict, decisions: dict[str, dict]
) -> dict[str, Any]:
    """Filter / mutate draft entries per operator decisions.

    Args:
        discovery_output: shape returned by ``discover()``.
        decisions: ``{"experience_<idx>": {"action": "approve|edit|reject",
                       "claim_core"?: str, "evidence_url"?: str,
                       "title"?: str, "url"?: str, "methodology"?: str},
                       "research_<idx>": {...}}``.
            Entries omitted from the map are treated as ``reject``.

    Returns:
        ``{"approved_experience": [...], "approved_research": [...],
           "topic_candidates": [...]}`` — the input for Stage C.
    """
    approved_experience = _apply_to_bucket(
        discovery_output["draft_experience_entries"],
        decisions,
        key_prefix="experience_",
        editable_fields=("claim_core", "evidence_url"),
    )
    approved_research = _apply_to_bucket(
        discovery_output["draft_research_entries"],
        decisions,
        key_prefix="research_",
        editable_fields=("title", "methodology", "url"),
    )
    return {
        "approved_experience": approved_experience,
        "approved_research": approved_research,
        "topic_candidates": list(discovery_output["topic_candidates"]),
    }


def _apply_to_bucket(
    entries: list[dict],
    decisions: dict[str, dict],
    key_prefix: str,
    editable_fields: tuple[str, ...],
) -> list[dict]:
    """Filter + mutate one of the two buckets (experience / research)."""
    out: list[dict] = []
    for i, entry in enumerate(entries):
        decision = decisions.get(f"{key_prefix}{i}", _DEFAULT_DECISION)
        if decision["action"] == "reject":
            continue
        approved = deepcopy(entry)
        if decision["action"] == "edit":
            for field in editable_fields:
                if field in decision:
                    approved[field] = decision[field]
        out.append(approved)
    return out
