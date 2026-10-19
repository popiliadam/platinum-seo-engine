"""S-01 — one official, recorded indexing path instead of hand-written _index_*.py.

The owner decided (2026-10-13) to use the Indexing API for every page. The
shared path checks that the new content is live before sending, keeps a daily
quota per project and queues the overflow, needs consent only for URL_DELETED,
pings IndexNow too, and writes one report per run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.production import indexing_submit as ix

NOW = datetime(2026, 10, 19, 9, 30, tzinfo=timezone.utc)


def _page(url: str, body: str = "yeni paragraf", *, canonical: str | None = None, robots: str = "") -> str:
    can = f'<link rel="canonical" href="{canonical or url}">'
    meta = f'<meta name="robots" content="{robots}">' if robots else ""
    return f"<html><head>{can}{meta}</head><body>{body}</body></html>"


class Fake:
    def __init__(self, pages: dict[str, tuple[int, str]]):
        self.pages, self.posted, self.pinged = pages, [], []

    def fetch(self, url):
        status, html = self.pages[url]
        return status, html, {}

    def publish(self, url, kind):
        self.posted.append((url, kind))
        return 200, {"urlNotificationMetadata": {"url": url}}

    def indexnow(self, host, urls):
        self.pinged.append((host, list(urls)))
        return 200


def _project(tmp_path: Path) -> Path:
    d = tmp_path / "projects" / "demo"
    d.mkdir(parents=True)
    return d


def test_live_check_rules() -> None:
    u = "https://x.test/a/"
    assert ix.live_check(u, 200, _page(u)).ok
    assert ix.live_check(u, 404, "").reason == "HTTP 404"
    assert ix.live_check(u, 200, _page(u, robots="noindex,follow")).reason == "noindex"
    assert "canonical" in ix.live_check(u, 200, _page(u, canonical="https://x.test/b/")).reason
    assert not ix.live_check(u, 200, _page(u, "eski"), expect="yeni paragraf").ok
    assert ix.live_check(u, 410, "", notification="URL_DELETED").ok
    assert not ix.live_check(u, 200, _page(u), notification="URL_DELETED").ok


def test_fifty_urls_one_command_dead_one_skipped_with_reason(tmp_path: Path) -> None:
    urls = [f"https://x.test/p{i}/" for i in range(50)]
    pages = {u: (200, _page(u)) for u in urls}
    pages[urls[7]] = (200, _page(urls[7], robots="noindex"))
    fake = Fake(pages)
    res = ix.submit(urls, project_dir=_project(tmp_path), now=NOW, fetch=fake.fetch,
                    publish=fake.publish, indexnow=fake.indexnow)
    assert len(fake.posted) == 49 and urls[7] not in [u for u, _ in fake.posted]
    skipped = [r for r in res.report["results"] if r.get("skipped")]
    assert skipped == [{"url": urls[7], "google_http": None, "live_check": "noindex", "skipped": "noindex"}]
    assert fake.pinged and len(fake.pinged[0][1]) == 49
    saved = json.loads(res.report_path.read_text(encoding="utf-8"))
    assert saved["type"] == "URL_UPDATED" and len(saved["results"]) == 50


def test_quota_counts_todays_reports_and_queues_overflow(tmp_path: Path) -> None:
    project = _project(tmp_path)
    first = [f"https://x.test/a{i}/" for i in range(3)]
    second = [f"https://x.test/b{i}/" for i in range(4)]
    fake = Fake({u: (200, _page(u)) for u in first + second})
    ix.submit(first, project_dir=project, now=NOW, fetch=fake.fetch, publish=fake.publish, cap=5)
    assert ix.used_today(project, "2026-10-19") == 3
    later = NOW.replace(hour=11)
    res = ix.submit(second, project_dir=project, now=later, fetch=fake.fetch, publish=fake.publish, cap=5)
    assert res.queued == second[2:] and ix.read_queue(project) == second[2:]
    tomorrow = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
    ix.submit([], project_dir=project, now=tomorrow, fetch=fake.fetch, publish=fake.publish, cap=5)
    assert [u for u, _ in fake.posted][-2:] == second[2:] and ix.read_queue(project) == []


def test_url_deleted_needs_consent(tmp_path: Path) -> None:
    u = "https://x.test/gone/"
    fake = Fake({u: (410, "")})
    res = ix.submit([u], project_dir=_project(tmp_path), now=NOW, fetch=fake.fetch,
                    publish=fake.publish, notification="URL_DELETED")
    assert fake.posted == [] and "consent" in res.report["results"][0]["skipped"]
    ix.submit([u], project_dir=_project(tmp_path / "b"), now=NOW, fetch=fake.fetch,
              publish=fake.publish, notification="URL_DELETED", deletion_allowed=lambda _u: True)
    assert fake.posted == [(u, "URL_DELETED")]


def test_dry_run_sends_and_writes_nothing(tmp_path: Path) -> None:
    u = "https://x.test/a/"
    project = _project(tmp_path)
    fake = Fake({u: (200, _page(u))})
    res = ix.submit([u], project_dir=project, now=NOW, fetch=fake.fetch, publish=fake.publish, dry_run=True)
    assert fake.posted == [] and res.report_path is None
    assert not (project / "outputs").exists()


def test_command_and_skill_point_at_the_official_path() -> None:
    root = Path(__file__).resolve().parents[2]
    cmd = (root / "commands" / "pseo-index.md").read_text(encoding="utf-8")
    assert "scripts/production/indexing_submit.py" in cmd
    skill = (root / "skills" / "publishing" / "indexing-ping" / "SKILL.md").read_text(encoding="utf-8")
    assert "indexing_submit.py" in skill
    assert "yalnızca JobPosting/BroadcastEvent sayfaları için uygundur" not in skill
