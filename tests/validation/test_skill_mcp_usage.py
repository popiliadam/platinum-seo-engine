"""Unit tests for scripts/validation/skill_mcp_usage.py — AMO batch 3a, lint #1
parser (a skill's BODY-invoked MCP tools ⊆ its DECLARED mcp_tools).

Inline string fixtures only (no real SKILL.md files) so the detector's
invocation-precision is pinned independently of the live skill tree. The TWO
precision traps — a backtick PROSE MENTION (monthly-report) and a VARIABLE-
dispatched ``call_tool(var, ...)`` (SF_EXPORT_DISPATCH) — are explicit, named
tests: they are the whole point of "invocation-precise" and must never regress.
"""
from __future__ import annotations

import textwrap

from scripts.validation.skill_mcp_usage import (
    body_not_declared,
    declared_tools,
    invoked_tools,
    iter_skill_gaps,
    split_frontmatter_body,
)


# --- declared_tools (mirrors the registry test's block parser) -------------

def test_declared_tools_parses_required_and_optional_with_alias():
    fm = textwrap.dedent(
        """\
        name: demo
        mcp_tools:
          required:
            - "mcp__gsc__search_analytics"
            - "mcp__dataforseo__on_page_lighthouse"
          optional:
            - "mcp__ScraplingServer__fetch"
        budget:
          uses_paid_mcp: false
        """
    )
    assert declared_tools(fm) == {
        "gsc__search_analytics",
        "dataforseo__on_page_lighthouse",
        "scrapling__fetch",  # ScraplingServer -> scrapling alias applied
    }


def test_declared_tools_inline_empty_lists_is_empty_set():
    fm = (
        "name: demo\nmcp_tools:\n  required: []\n  optional: []\n"
        "budget:\n  uses_paid_mcp: false\n"
    )
    assert declared_tools(fm) == set()


# --- invoked_tools — class A (qualified call) ------------------------------

def test_invoked_class_a_qualified_call():
    body = "raw_gsc = mcp__gsc__search_analytics(site_url=site, days=28)\n"
    assert invoked_tools(body) == {"gsc__search_analytics"}


def test_precision_trap_1_backtick_mention_not_flagged():
    # monthly-report SKILL.md ~line 95: a backtick PROSE MENTION, no call parens.
    body = "The `mcp__gsc__search_analytics` tool MAY be invoked opportunistically.\n"
    assert invoked_tools(body) == set()


def test_invoked_higgsfield_external_server_excluded():
    body = "img = mcp__higgsfield__generate_image(prompt=p)\n"
    assert invoked_tools(body) == set()


# --- invoked_tools — class B (native call_tool string literal) -------------

def test_invoked_class_b_call_tool_positional_literal():
    body = 'list_resp = client.call_tool("sf_list_crawls")\n'
    assert invoked_tools(body) == {"sf__sf_list_crawls"}


def test_invoked_class_b_call_tool_tool_name_kwarg_literal():
    body = 'r = client.call_tool(tool_name="sf_crawl_progress")\n'
    assert invoked_tools(body) == {"sf__sf_crawl_progress"}


def test_precision_trap_2_call_tool_variable_first_arg_not_flagged():
    # SF_EXPORT_DISPATCH passes a VARIABLE first arg -> unresolvable statically.
    body = "client.call_tool(tool, file_path=rel_path, **call_kwargs)\n"
    assert invoked_tools(body) == set()


def test_invoked_class_b_call_tool_fstring_first_arg_not_flagged():
    body = 'client.call_tool(f"sf_{element}")\n'
    assert invoked_tools(body) == set()


# --- invoked_tools — class C (SfMcpClient wrapper method) ------------------

def test_invoked_class_c_load_crawl_wrapper_method():
    body = "client.load_crawl(crawl_id)\n"
    assert invoked_tools(body) == {"sf__sf_load_crawl"}


def test_health_wrapper_is_not_a_registry_tool():
    # SfMcpClient.health() is an MCP initialize handshake, NOT a tool call.
    body = "preflight_ok = client.health()\n"
    assert invoked_tools(body) == set()


# --- split_frontmatter_body ------------------------------------------------

def test_split_body_markdown_rule_does_not_truncate_and_fm_decl_not_invoked():
    text = textwrap.dedent(
        """\
        ---
        name: demo
        mcp_tools:
          required:
            - "mcp__sf__sf_crawl"
        ---
        Intro paragraph.

        ---

        After a horizontal rule we call mcp__gsc__search_analytics(x) for real.
        """
    )
    fm, body = split_frontmatter_body(text)
    assert "mcp_tools:" in fm
    assert "After a horizontal rule" in body  # body NOT truncated by markdown ---
    invoked = invoked_tools(body)
    assert invoked == {"gsc__search_analytics"}
    # the mcp_tools frontmatter declaration is NOT counted as a body invocation:
    assert "sf__sf_crawl" not in invoked


def test_split_fewer_than_two_fences_returns_whole_text_as_body():
    text = "no frontmatter here\njust body text\n"
    fm, body = split_frontmatter_body(text)
    assert fm == ""
    assert body == text


# --- body_not_declared + iter_skill_gaps -----------------------------------

def _skill_text(mcp_tools_block: str, body: str) -> str:
    return (
        "---\nname: demo\n"
        f"{mcp_tools_block}"
        "budget:\n  uses_paid_mcp: false\n---\n"
        f"{body}"
    )


def test_body_not_declared_declared_invocation_has_no_gap(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        _skill_text(
            'mcp_tools:\n  required: []\n  optional:\n    - "mcp__sf__sf_list_crawls"\n',
            'x = client.call_tool("sf_list_crawls")\n',
        ),
        encoding="utf-8",
    )
    assert body_not_declared(skill) == set()


def test_body_not_declared_undeclared_invocation_is_the_gap(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        _skill_text(
            "mcp_tools:\n  required: []\n  optional: []\n",
            "client.load_crawl(crawl_id)\n",
        ),
        encoding="utf-8",
    )
    assert body_not_declared(skill) == {"sf__sf_load_crawl"}


def test_iter_skill_gaps_collects_only_nonempty_gaps(tmp_path):
    gapped = tmp_path / "skills" / "discovery" / "gapped"
    gapped.mkdir(parents=True)
    (gapped / "SKILL.md").write_text(
        _skill_text(
            "mcp_tools:\n  required: []\n  optional: []\n",
            'client.call_tool("sf_list_crawls")\n',
        ),
        encoding="utf-8",
    )
    clean = tmp_path / "skills" / "discovery" / "clean"
    clean.mkdir(parents=True)
    (clean / "SKILL.md").write_text(
        _skill_text(
            'mcp_tools:\n  required: []\n  optional:\n    - "mcp__sf__sf_list_crawls"\n',
            'client.call_tool("sf_list_crawls")\n',
        ),
        encoding="utf-8",
    )
    assert iter_skill_gaps(tmp_path) == {
        "skills/discovery/gapped/SKILL.md": {"sf__sf_list_crawls"}
    }
