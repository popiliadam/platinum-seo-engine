"""S-24 — a revision may not silently drop what the live page carries.

revise-content, content-remediation and the WordPress REST deploy scripts
published new versions without comparing them to the live page, so a table,
calculator form, iframe, real photo, internal link, H2 or JSON-LD type could
disappear unnoticed. The gate inventories both versions and stops the deploy
when anything is missing — a quality gate (fix and retry), not a consent.
"""
from __future__ import annotations

from scripts.production.deploy_diff_gate import compare, inventory

HOST = "x.test"

LIVE = """
<article>
  <h2>Fiyatlar</h2><table><tr><td>A</td></tr></table>
  <h2>Hesaplayıcı</h2><form action="/calc"><input name="m2"></form>
  <h2>Video</h2><iframe src="https://www.youtube.com/embed/x"></iframe>
  <img src="/foto/ekip.jpg" alt="Ekip">
  <a href="https://x.test/kombi">Kombi</a> <a href="/klima">Klima</a> <a href="https://other.test/">dış</a>
  <script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Article"},{"@type":"HowTo"}]}</script>
</article>
"""


def test_inventory_counts_the_value_carrying_elements() -> None:
    inv = inventory(LIVE, site_host=HOST)
    assert (inv.tables, inv.forms, inv.iframes, inv.images, inv.internal_links) == (1, 1, 1, 1, 2)
    assert inv.h2 == ("fiyatlar", "hesaplayıcı", "video")
    assert inv.jsonld_types == frozenset({"Article", "HowTo"})


def test_identical_revision_passes() -> None:
    result = compare(LIVE, LIVE, site_host=HOST)
    assert result.ok and result.missing == ()


def test_dropped_table_stops_the_deploy_and_is_named_first() -> None:
    new = LIVE.replace("<table><tr><td>A</td></tr></table>", "<p>Fiyatlar değişti.</p>")
    result = compare(LIVE, new, site_host=HOST)
    assert not result.ok
    assert result.missing[0].startswith("table")
    assert result.report().split("\n")[0].startswith("BLOCKED")


def test_every_kind_of_loss_is_reported() -> None:
    new = (LIVE.replace('<form action="/calc"><input name="m2"></form>', "")
               .replace('<a href="/klima">Klima</a>', "")
               .replace("<h2>Video</h2>", "<h2>Videolar</h2>")
               .replace(',{"@type":"HowTo"}', ""))
    missing = " ".join(compare(LIVE, new, site_host=HOST).missing)
    for word in ("form", "internal link", "video", "HowTo"):
        assert word in missing, (word, missing)


def test_additions_are_fine() -> None:
    new = LIVE.replace("</article>", "<table><tr><td>B</td></tr></table></article>")
    assert compare(LIVE, new, site_host=HOST).ok


def test_revise_and_merge_flows_run_the_gate() -> None:
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "skills" / "production"
    revise = (root / "revise-content" / "SKILL.md").read_text(encoding="utf-8")
    assert "deploy_diff_gate.py" in revise and "DURUR #9" in revise
    remediation = (root / "content-remediation" / "SKILL.md").read_text(encoding="utf-8")
    assert "deploy_diff_gate.py" in remediation
