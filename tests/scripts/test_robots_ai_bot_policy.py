"""S-08 / S-09 — the robots proposal keeps deliberate AI-bot blocks; the audit
knows the three AI-bot classes and reads project.config[ai_bots].

S-08: _build_proposed dropped EVERY ``Disallow: /``, so a client's deliberate
      ``User-agent: GPTBot / Disallow: /`` vanished from the proposed file.
S-09: R-99 was prose only; ai_bots was written but never read; the default list
      carried the retired Claude-Web and none of the 2026 search / user agents.
"""
from __future__ import annotations

from scripts.discovery import robots_policy_transform as rpt
from scripts.state import bootstrap_project

DOMAIN = "x.test"


def _t(robots: str, **kw) -> dict:
    return rpt.transform(robots, [], [], [], "custom", DOMAIN, **kw)


def _issues(out: dict) -> dict[str, str]:
    return {r["issue"]: r["level"] for r in out["robots_txt_rows"]}


# --- S-08 -----------------------------------------------------------------------

def test_proposal_keeps_a_deliberate_ai_bot_block() -> None:
    robots = ("User-agent: *\nDisallow: /cart\n\n"
              "User-agent: GPTBot\nDisallow: /\n\n"
              "Sitemap: https://x.test/sitemap.xml\n")
    proposed = _t(robots)["proposed_robots_txt"]
    groups = rpt._parse_robots(proposed)["groups"]
    gpt = [g for g in groups if "gptbot" in g["agents"]]
    assert gpt and gpt[0]["disallow"] == ["/"]


def test_proposal_still_drops_a_site_wide_star_block() -> None:
    proposed = _t("User-agent: *\nDisallow: /\n")["proposed_robots_txt"]
    assert "/" not in rpt._parse_robots(proposed)["star_disallow"]


def test_proposal_comes_with_a_diff() -> None:
    out = _t("User-agent: *\nDisallow: /cart\nnoindex: /old\n")
    diff = out["proposed_diff"]
    assert "-noindex: /old" in diff
    assert "+Sitemap: https://x.test/sitemap.xml" in diff


# --- S-09 -----------------------------------------------------------------------

def test_three_bot_classes_are_declared() -> None:
    classes = rpt.AI_BOT_CLASSES
    assert {"GPTBot", "Google-Extended", "CCBot", "Applebot-Extended", "Bytespider"} <= set(classes["training"])
    assert {"OAI-SearchBot", "PerplexityBot", "Claude-SearchBot"} <= set(classes["search"])
    assert {"ChatGPT-User", "Claude-User"} <= set(classes["user"])


def test_blocking_an_ai_search_bot_is_high() -> None:
    out = _t("User-agent: OAI-SearchBot\nDisallow: /\n\nSitemap: https://x.test/s.xml\n")
    levels = [lvl for issue, lvl in _issues(out).items() if "AI search" in issue]
    assert levels == ["HIGH"]


def test_blocking_a_training_bot_alone_is_not_a_finding() -> None:
    out = _t("User-agent: GPTBot\nDisallow: /\n\nSitemap: https://x.test/s.xml\n")
    assert not [i for i in _issues(out) if "AI" in i]


def test_bot_the_config_allows_but_robots_blocks_is_medium() -> None:
    out = _t("User-agent: GPTBot\nDisallow: /\n\nSitemap: https://x.test/s.xml\n",
             ai_bots=["GPTBot"])
    hits = {i: lvl for i, lvl in _issues(out).items() if "ai_bots" in i}
    assert list(hits.values()) == ["MEDIUM"]


def test_retired_user_agent_is_flagged() -> None:
    out = _t("User-agent: Claude-Web\nDisallow: /\n\nSitemap: https://x.test/s.xml\n")
    assert any("retired" in i.lower() for i in _issues(out))


def test_default_ai_bots_list_is_current() -> None:
    bots = set(bootstrap_project.DEFAULT_AI_BOTS)
    assert "Claude-Web" not in bots
    assert {"OAI-SearchBot", "Claude-SearchBot", "PerplexityBot", "ChatGPT-User", "Claude-User"} <= bots
    assert not bots & set(rpt.AI_BOT_CLASSES["training"])  # training = client's call
