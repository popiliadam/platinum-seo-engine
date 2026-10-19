#!/usr/bin/env python3
"""indexing_submit.py — the one official indexing path (S-01, /pseo-index).

Owner decision 2026-10-13: the Google Indexing API is used for every page
(Google's documentation limits it to JobPosting / BroadcastEvent; the decision
was taken knowing that). Until now each project carried hand-written
``outputs/_index_*.py`` scripts (110+ across 9 projects) with no shared quota,
error handling, record or "is the new content live" check. This module is that
shared path:

* live check BEFORE sending (lesson 2026-05-13): URL_UPDATED needs HTTP 200, a
  self canonical (or none), no ``noindex`` and — when given — the expected new
  text on the page; URL_DELETED needs 404/410. A URL that fails is skipped and
  its reason recorded; nothing is spent on it.
* daily quota per project (default 200): used = URLs already sent today
  according to today's reports; the overflow waits in
  ``_state/indexing_queue.json`` and goes first on the next run.
* URL_UPDATED is free (G-01 tier "serbest"); URL_DELETED needs this session's
  consent for that URL (``/pseo-approve <run> index_update <url>``).
* IndexNow (Bing, Yandex) is pinged for the same URLs when ``INDEXNOW_KEY`` is
  set.
* every run writes ``outputs/indexing/{date}-{HHMMSS}-submission.json``.

The network sits behind three injectable callables (``fetch``, ``publish``,
``indexnow``) so the decisions are tested without IO.

CLI:
    python3 scripts/production/indexing_submit.py submit <slug> URL [URL ...]
        [--type URL_UPDATED|URL_DELETED] [--expect TEXT] [--cap N] [--dry-run]
    python3 scripts/production/indexing_submit.py status <slug> URL
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

DAILY_CAP_DEFAULT = 200
NOTIFICATION_TYPES = ("URL_UPDATED", "URL_DELETED")
PUBLISH_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
METADATA_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications/metadata"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
SA_PATH_DEFAULT = "~/.config/seo-core/secrets/google-indexing.json"
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


Fetch = Callable[[str], tuple[int, str, dict]]
Publish = Callable[[str, str], tuple[int, dict]]
IndexNow = Callable[[str, list[str]], int]


@dataclass(frozen=True)
class LiveCheck:
    url: str
    ok: bool
    reason: str


class _HeadSignals(HTMLParser):
    """robots meta + canonical link, in any attribute order (review fix)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.robots: list[str] = []
        self.canonical: str | None = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot"):
            self.robots.append(a.get("content", "").lower())
        elif (tag == "link" and "canonical" in a.get("rel", "").lower().split()
              and self.canonical is None):
            self.canonical = a.get("href", "").strip()

    handle_startendtag = handle_starttag


def _norm(url: str, base: str | None = None) -> str:
    """Absolute URL, lower-case host, no trailing slash (canonical comparison)."""
    p = urlparse(urljoin(base or url, url.strip()))
    query = f"?{p.query}" if p.query else ""
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}{query}"


def live_check(url: str, status: int, html: str, headers: dict | None = None, *,
               notification: str = "URL_UPDATED", expect: str | None = None) -> LiveCheck:
    """Whether ``url`` is in the state its notification claims (pure)."""
    if notification == "URL_DELETED":
        ok = status in (404, 410)
        return LiveCheck(url, ok, "gone" if ok else f"still answers HTTP {status} — not deleted")
    if status != 200:
        return LiveCheck(url, False, f"HTTP {status}")
    head = _HeadSignals()
    head.feed(html or "")
    robots = " ".join(head.robots)
    x_robots = str((headers or {}).get("x-robots-tag", "")).lower()
    if "noindex" in robots or "noindex" in x_robots:
        return LiveCheck(url, False, "noindex")
    if head.canonical and _norm(head.canonical, base=url) != _norm(url):
        return LiveCheck(url, False, f"canonical points elsewhere: {head.canonical}")
    if expect and expect not in (html or ""):
        return LiveCheck(url, False, "new content not live yet (expected text missing)")
    return LiveCheck(url, True, "live")


def plan_batch(urls: list[str], *, used_today: int, cap: int) -> tuple[list[str], list[str]]:
    """(send now, queue for tomorrow) within the daily cap; order and dedup kept."""
    seen: list[str] = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    room = max(cap - used_today, 0)
    return seen[:room], seen[room:]


def reports_dir(project_dir: Path) -> Path:
    return project_dir / "outputs" / "indexing"


def queue_path(project_dir: Path) -> Path:
    return project_dir / "_state" / "indexing_queue.json"


def used_today(project_dir: Path, day: str) -> int:
    """URLs posted to Google today, from today's submission reports."""
    total = 0
    for path in sorted(reports_dir(project_dir).glob(f"{day}-*-submission.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        total += sum(1 for r in report.get("results", []) if r.get("google_http") is not None)
    return total


def read_queue(project_dir: Path) -> list[str]:
    try:
        data = json.loads(queue_path(project_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [u for u in data.get("urls", []) if isinstance(u, str)] if isinstance(data, dict) else []


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


@dataclass
class RunResult:
    report: dict
    report_path: Path | None
    queued: list[str] = field(default_factory=list)


def submit(
    urls: list[str],
    *,
    project_dir: Path,
    now: datetime,
    fetch: Fetch,
    publish: Publish | None,
    indexnow: IndexNow | None = None,
    notification: str = "URL_UPDATED",
    expect: str | None = None,
    cap: int = DAILY_CAP_DEFAULT,
    deletion_allowed: Callable[[str], bool] = lambda _u: False,
    dry_run: bool = False,
) -> RunResult:
    """Check, send within quota, queue the rest, and record the run."""
    if notification not in NOTIFICATION_TYPES:
        raise ValueError(f"notification must be one of {NOTIFICATION_TYPES}")
    day = now.strftime("%Y-%m-%d")
    queued_before = read_queue(project_dir) if notification == "URL_UPDATED" else []
    send, overflow = plan_batch(queued_before + list(urls),
                                used_today=used_today(project_dir, day), cap=cap)
    results: list[dict] = []
    sent: list[str] = []
    retry: list[str] = []
    for url in send:
        row: dict = {"url": url, "google_http": None}
        if notification == "URL_DELETED" and not deletion_allowed(url):
            row["skipped"] = ("URL_DELETED needs this session's consent: "
                              f"/pseo-approve <run_id> index_update {url}")
            results.append(row)
            continue
        try:
            status, html, headers = fetch(url)
        except OSError as exc:  # URLError, timeout, reset: keep going, keep the record
            row["skipped"] = f"fetch error: {exc}"
            results.append(row)
            continue
        check = live_check(url, status, html, headers, notification=notification, expect=expect)
        row["live_check"] = check.reason
        if not check.ok:
            row["skipped"] = check.reason
        elif not dry_run and publish is not None:
            try:
                code, payload = publish(url, notification)
            except OSError as exc:
                code, payload = 0, {"error": f"send error: {exc}"}
            row["google_http"], row["google_response"] = code, payload
            if code == 200:
                sent.append(url)
            else:
                retry.append(url)  # 429 / 5xx / network: try again next run
        results.append(row)
    indexnow_http = None
    if sent and indexnow is not None and not dry_run:
        indexnow_http = indexnow(urlparse_host(sent[0]), sent)
    report = {
        "sent_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": notification,
        "daily_cap": cap,
        "dry_run": dry_run,
        "results": results,
        "indexnow_http": indexnow_http,
        **({"queued_for_next_day": retry + overflow} if notification == "URL_UPDATED"
           else {"not_sent_rerun_tomorrow": retry + overflow}),
        "note": "HTTP 200 means Google received the notification, not that the page is indexed.",
    }
    report_path = None
    if not dry_run:
        report_path = reports_dir(project_dir) / f"{day}-{now.strftime('%H%M%S%f')}-submission.json"
        _atomic_write_json(report_path, report)
        if notification == "URL_UPDATED":
            _atomic_write_json(queue_path(project_dir),
                               {"urls": retry + overflow, "updated_at": report["sent_at"]})
    # URL_DELETED is never queued (it needs a fresh consent): the report lists
    # what to rerun instead of claiming it was queued.
    queued = retry + overflow if notification == "URL_UPDATED" and not dry_run else []
    return RunResult(report, report_path, queued)


def urlparse_host(url: str) -> str:
    return urlparse(url).hostname or ""


# --- real network adapters (not exercised by unit tests) ----------------------

def http_fetch(url: str) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": GOOGLEBOT_UA, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            headers = {k.lower(): v for k, v in r.headers.items()}
            # a repeated X-Robots-Tag must not lose its first value
            headers["x-robots-tag"] = ", ".join(r.headers.get_all("X-Robots-Tag") or [])
            return r.status, r.read().decode("utf-8", "ignore"), headers
    except urllib.error.HTTPError as e:
        return e.code, "", {k.lower(): v for k, v in (e.headers or {}).items()}


def _google_token(sa_path: str) -> str:
    try:
        from google.auth.transport.requests import Request as GRequest
        from google.oauth2 import service_account
    except ImportError as exc:  # optional operator dependency
        raise RuntimeError("google-auth is not installed: pip install google-auth") from exc
    creds = service_account.Credentials.from_service_account_file(
        os.path.expanduser(sa_path), scopes=["https://www.googleapis.com/auth/indexing"])
    creds.refresh(GRequest())
    return creds.token


def google_publisher(sa_path: str) -> Publish:
    token = _google_token(sa_path)

    def publish(url: str, notification: str) -> tuple[int, dict]:
        req = urllib.request.Request(
            PUBLISH_ENDPOINT, data=json.dumps({"url": url, "type": notification}).encode(),
            method="POST", headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return e.code, {"error": e.read().decode("utf-8", "ignore")[:300]}

    return publish


def google_metadata(sa_path: str, url: str) -> tuple[int, dict]:
    """Last notification Google holds for ``url`` (getMetadata)."""
    from urllib.parse import quote
    token = _google_token(sa_path)
    req = urllib.request.Request(f"{METADATA_ENDPOINT}?url={quote(url, safe='')}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "ignore")[:300]}


def indexnow_pinger(key: str) -> IndexNow:
    def ping(host: str, urls: list[str]) -> int:
        body = json.dumps({"host": host, "key": key, "urlList": urls}).encode()
        req = urllib.request.Request(INDEXNOW_ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    return ping


# --- CLI -------------------------------------------------------------------------

def _project_dir(slug: str) -> Path:
    from scripts.state.session_binding import resolve_workspace_root
    ws = resolve_workspace_root()
    if ws is None:
        raise SystemExit("no workspace root — set PSEO_WORKSPACE_ROOT")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise SystemExit(f"invalid project slug: {slug!r}")
    path = ws / "projects" / slug
    if not (path / "project.config.json").is_file():
        raise SystemExit(f"project not found: {path}")
    return path


def _deletion_consent(slug: str) -> Callable[[str], bool]:
    from scripts.state import consent_ledger as cl
    from scripts.state.session_binding import current_session_id, resolve_workspace_root
    ws, session = resolve_workspace_root(), current_session_id()

    def allowed(url: str) -> bool:
        return bool(ws and session) and cl.has_session_consent(
            ws, slug, session_id=session, action="index_update",
            target_hash=cl.target_hash(url), max_age_seconds=3600)

    return allowed


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="indexing_submit.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("slug")
    s.add_argument("urls", nargs="+")
    s.add_argument("--type", default="URL_UPDATED", choices=NOTIFICATION_TYPES)
    s.add_argument("--expect")
    s.add_argument("--cap", type=int, default=DAILY_CAP_DEFAULT)
    s.add_argument("--dry-run", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("slug")
    st.add_argument("url")
    args = p.parse_args(argv)
    sa_path = os.environ.get("GOOGLE_INDEXING_SA", SA_PATH_DEFAULT)
    if args.cmd == "status":
        _project_dir(args.slug)
        code, payload = google_metadata(sa_path, args.url)
        print(json.dumps({"http": code, "metadata": payload}, ensure_ascii=False, indent=2))
        return 0 if code == 200 else 1
    project = _project_dir(args.slug)
    key = os.environ.get("INDEXNOW_KEY")
    result = submit(
        args.urls, project_dir=project, now=datetime.now(timezone.utc), fetch=http_fetch,
        publish=None if args.dry_run else google_publisher(sa_path),
        indexnow=indexnow_pinger(key) if key else None, notification=args.type,
        expect=args.expect, cap=args.cap, deletion_allowed=_deletion_consent(args.slug),
        dry_run=args.dry_run)
    for row in result.report["results"]:
        state = row.get("skipped") or f"HTTP {row['google_http']}"
        print(f"  {row['url']}  →  {state}")
    if result.queued:
        print(f"queued for the next run (daily cap {args.cap}): {len(result.queued)}")
    rerun = result.report.get("not_sent_rerun_tomorrow")
    if rerun:
        print(f"NOT sent and NOT queued (URL_DELETED needs a fresh consent), rerun: {len(rerun)}")
    if result.report_path:
        print(f"report: {result.report_path}")
    ok = all(r.get("google_http") == 200 or args.dry_run and not r.get("skipped")
             for r in result.report["results"])
    return 0 if ok else 1


__all__ = ("DAILY_CAP_DEFAULT", "LiveCheck", "live_check", "plan_batch", "used_today",
           "read_queue", "submit", "RunResult")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
