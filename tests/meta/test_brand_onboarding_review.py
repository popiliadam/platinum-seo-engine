"""Brand onboarding Stage B — Operator review of draft bank entries.

Covers ``scripts/meta/brand_onboarding_review``:
  - ``generate_review_prompt(discovery_output)`` renders a markdown
    document listing every draft + 3 actions (approve / edit / reject)
    per entry; topic candidates listed at the end.
  - ``apply_review_decisions(discovery_output, decisions)`` filters /
    mutates per operator decision; returns the approved set for Stage C.

Decisions schema is dict-based so prompts can be filled in any UI / CLI
flow without forcing a particular interaction model.
"""

from __future__ import annotations

from scripts.meta.brand_onboarding_review import (
    apply_review_decisions,
    generate_review_prompt,
)


def test_generate_review_prompt_lists_all_drafts() -> None:
    """Prompt mentions every draft claim + lists the 3-action menu."""
    discovery_output = {
        "draft_experience_entries": [
            {
                "hint": "founding_year",
                "claim_core": "8 yıl sektör tecrübesi",
                "evidence_url": "https://x.com",
            },
        ],
        "draft_research_entries": [],
        "topic_candidates": ["e-para", "yan haklar"],
    }
    prompt = generate_review_prompt(discovery_output)
    assert "8 yıl sektör tecrübesi" in prompt
    assert "approve" in prompt.lower()
    assert "edit" in prompt.lower()
    assert "reject" in prompt.lower()
    # Topic candidates surface as a flat comma-joined list
    assert "e-para" in prompt
    assert "yan haklar" in prompt


def test_apply_review_decisions_approves_only_marked() -> None:
    """Only entries marked approved (or edited) survive; rejected dropped."""
    discovery_output = {
        "draft_experience_entries": [
            {
                "hint": "founding_year",
                "claim_core": "8 yıl",
                "evidence_url": "https://x.com",
            },
            {
                "hint": "about_text",
                "claim_core": "BDDK lisanslı",
                "evidence_url": "https://x.com/about",
            },
        ],
        "draft_research_entries": [],
        "topic_candidates": ["e-para"],
    }
    decisions = {
        "experience_0": {"action": "approve"},
        "experience_1": {"action": "reject"},
    }
    result = apply_review_decisions(discovery_output, decisions)
    assert len(result["approved_experience"]) == 1
    assert result["approved_experience"][0]["claim_core"] == "8 yıl"
    assert result["topic_candidates"] == ["e-para"]


def test_apply_review_decisions_supports_edit() -> None:
    """Edit decision lets operator override claim_core / evidence_url."""
    discovery_output = {
        "draft_experience_entries": [
            {
                "hint": "founding_year",
                "claim_core": "8 yıl",
                "evidence_url": "https://x.com",
            },
        ],
        "draft_research_entries": [],
        "topic_candidates": [],
    }
    decisions = {
        "experience_0": {
            "action": "edit",
            "claim_core": "10 yıl BDDK lisanslı e-para tecrübesi",
        },
    }
    result = apply_review_decisions(discovery_output, decisions)
    assert (
        result["approved_experience"][0]["claim_core"]
        == "10 yıl BDDK lisanslı e-para tecrübesi"
    )
    # Untouched fields preserved verbatim
    assert result["approved_experience"][0]["evidence_url"] == "https://x.com"


def test_apply_review_decisions_default_action_is_reject() -> None:
    """Entries with no decision in the map are treated as rejected (safe
    default — operator must opt in to keep an entry)."""
    discovery_output = {
        "draft_experience_entries": [
            {"hint": "founding_year", "claim_core": "8 yıl", "evidence_url": "https://x.com"},
        ],
        "draft_research_entries": [],
        "topic_candidates": [],
    }
    result = apply_review_decisions(discovery_output, {})
    assert result["approved_experience"] == []


def test_apply_review_decisions_handles_research_entries() -> None:
    """Research entries follow the same approve / edit / reject pattern."""
    discovery_output = {
        "draft_experience_entries": [],
        "draft_research_entries": [
            {"title": "2026 industry survey", "url": "https://example.com/survey"},
        ],
        "topic_candidates": [],
    }
    decisions = {
        "research_0": {
            "action": "edit",
            "title": "2026 fintech industry survey",
        },
    }
    result = apply_review_decisions(discovery_output, decisions)
    assert len(result["approved_research"]) == 1
    assert result["approved_research"][0]["title"] == "2026 fintech industry survey"
    # Unchanged url survives
    assert result["approved_research"][0]["url"] == "https://example.com/survey"
