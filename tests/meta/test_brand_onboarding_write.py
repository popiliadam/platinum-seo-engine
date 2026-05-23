"""Brand onboarding Stage C — Atomic bank write.

Covers ``scripts/meta/brand_onboarding_write.write_bank_entries``:
  1. Appends approved entries to ``project.config.json``'s
     ``experience_database`` and ``original_research_database`` with the
     four R-121 fields populated (applicable_topics inherited from
     topic_candidates, max_usage_per_month=3 default,
     last_used_in_content_id=None initial).
  2. R-44 enforcement: every experience entry must carry
     ``evidence_url``; every research entry must carry ``url``.
  3. Atomicity: if any entry in the batch fails validation, the file
     is left unchanged (no partial writes).
  4. Auto-generated ``id`` prefixed ``exp-`` / ``res-``.
"""

from __future__ import annotations

import json

from scripts.meta.brand_onboarding_write import write_bank_entries


def test_write_appends_to_existing_bank(tmp_workspace_factory) -> None:
    project = tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [
            {
                "claim_core": "10 yıl BDDK lisanslı e-para tecrübesi",
                "evidence_url": "https://example.com/hakkimizda",
            },
        ],
        "approved_research": [],
        "topic_candidates": ["e-para", "BDDK"],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "success"
    assert result["experience_added"] == 1
    assert result["research_added"] == 0

    config = json.loads((project / "project.config.json").read_text(encoding="utf-8"))
    bank = config["content_settings"]["experience_database"]
    assert len(bank) == 1
    entry = bank[0]
    assert entry["claim_core"] == "10 yıl BDDK lisanslı e-para tecrübesi"
    assert entry["id"].startswith("exp-")
    # Topic candidates seeded into the new entry's applicable_topics
    assert entry["applicable_topics"] == ["e-para", "BDDK"]
    # R-121 defaults
    assert entry["max_usage_per_month"] == 3
    assert entry["last_used_in_content_id"] is None
    assert entry["phrasings"] == []
    # context mirrors claim_core (schema required: ["id", "context"])
    assert entry["context"] == "10 yıl BDDK lisanslı e-para tecrübesi"


def test_write_rejects_entry_without_evidence_url(tmp_workspace_factory) -> None:
    """R-44 source verification: every experience bank entry MUST have
    a non-empty ``evidence_url``."""
    tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [{"claim_core": "10 yıl", "evidence_url": ""}],
        "approved_research": [],
        "topic_candidates": [],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "error"
    assert "evidence_url" in result["error"].lower()


def test_write_atomic_no_partial_writes(tmp_workspace_factory) -> None:
    """If any approved entry is invalid, none of the batch is written."""
    project = tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [
            {"claim_core": "10 yıl", "evidence_url": "https://example.com/x"},
            {"claim_core": "missing evidence", "evidence_url": ""},  # invalid
        ],
        "approved_research": [],
        "topic_candidates": [],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "error"

    config = json.loads((project / "project.config.json").read_text(encoding="utf-8"))
    # File untouched — bank still empty
    assert config["content_settings"]["experience_database"] == []


def test_write_handles_research_entries_with_url(tmp_workspace_factory) -> None:
    """Research entries follow the parallel R-44 enforcement on ``url``."""
    project = tmp_workspace_factory(slug="test", profiles=["b2b-saas"])
    review_output = {
        "approved_experience": [],
        "approved_research": [
            {
                "title": "2026 fintech survey",
                "url": "https://example.com/survey",
                "methodology": "N=500, online questionnaire",
            },
        ],
        "topic_candidates": ["fintech"],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "success"
    assert result["research_added"] == 1

    config = json.loads((project / "project.config.json").read_text(encoding="utf-8"))
    research_bank = config["content_settings"]["original_research_database"]
    assert len(research_bank) == 1
    entry = research_bank[0]
    assert entry["title"] == "2026 fintech survey"
    assert entry["id"].startswith("res-")
    assert entry["applicable_topics"] == ["fintech"]
    assert entry["url"] == "https://example.com/survey"


def test_write_rejects_research_entry_without_url(tmp_workspace_factory) -> None:
    """Research entries without a URL are rejected (parallel to R-44 evidence_url)."""
    tmp_workspace_factory(slug="test", profiles=["b2b-saas"])
    review_output = {
        "approved_experience": [],
        "approved_research": [{"title": "untitled survey", "url": ""}],
        "topic_candidates": [],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "error"
    assert "url" in result["error"].lower()
