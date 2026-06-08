"""AMO batch 3a — lint #1: a skill's BODY-invoked MCP tools ⊆ its DECLARED
``mcp_tools``. This is the COMPLEMENT of
``test_skill_mcp_tools_exist_in_registry.py`` (``declared ⊆ registry``). Together
they close the triangle ``used ⊆ declared ⊆ registry`` — an undeclared MCP
dependency can no longer hide in a skill body.

The detector (``scripts/validation/skill_mcp_usage.invoked_tools``) is
invocation-PRECISE: it flags real call sites (qualified
``mcp__server__tool(...)``, native ``call_tool("literal")``,
``SfMcpClient.load_crawl(...)``) and deliberately ignores backtick PROSE MENTIONS
and VARIABLE-dispatched ``call_tool(var, ...)``. One parametrized test per skill so
a regression names the offending skill directly.
"""
from __future__ import annotations

import pathlib

import pytest

from scripts.validation.skill_mcp_usage import body_not_declared

ROOT = pathlib.Path(__file__).resolve().parents[2]
_SKILLS = sorted(ROOT.glob("skills/**/SKILL.md"))


@pytest.mark.parametrize(
    "skill",
    _SKILLS,
    ids=[str(p.relative_to(ROOT)) for p in _SKILLS],
)
def test_skill_body_mcp_tools_subset_declared(skill: pathlib.Path):
    gap = body_not_declared(skill)
    assert gap == set(), (
        f"{skill.relative_to(ROOT)} INVOKES MCP tool(s) not DECLARED in its "
        f"mcp_tools frontmatter: {sorted(gap)}.\n"
        "Remediation: declare these in mcp_tools.required/optional (qualified "
        "form 'mcp__<server>__<tool>'), or add the tool to mcp-tool-registry.json "
        "if absent. (lint #1: body ⊆ declared; complements declared ⊆ registry.)"
    )
