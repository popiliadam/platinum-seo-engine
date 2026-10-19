#!/usr/bin/env python3
"""crux_field.py — real-user Core Web Vitals from the CrUX API (S-19).

The tech audit read only DataForSEO Lighthouse LAB data (desktop by default):
TBT stood in for INP and no real-user number ever reached the report. Google
ranks on FIELD data — the Chrome UX Report p75 over 28 days, mobile first. This
module turns a CrUX ``records:queryRecord`` response into per-URL field
signals and findings; Lighthouse stays the diagnostic layer.

Google thresholds (unchanged): LCP 2.5 s / 4 s, INP 200 / 500 ms,
CLS 0.1 / 0.25; TTFB 0.8 / 1.8 s (diagnostic, not a Core Web Vital).
p75 above the first bound = needs improvement (MEDIUM), above the second =
poor (HIGH).

Pure functions; ``fetch_record`` is the only network call (API key in
``CRUX_API_KEY``). A URL with too little traffic has no URL-level record —
the caller may fall back to the origin record, and the finding says which.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
FORM_FACTOR_DEFAULT = "PHONE"

# metric key in the CrUX response → (label, unit, good bound, poor bound)
THRESHOLDS = {
    "largest_contentful_paint": ("LCP", "ms", 2500.0, 4000.0),
    "interaction_to_next_paint": ("INP", "ms", 200.0, 500.0),
    "cumulative_layout_shift": ("CLS", "", 0.1, 0.25),
    "experimental_time_to_first_byte": ("TTFB", "ms", 800.0, 1800.0),
}


@dataclass(frozen=True)
class FieldMetric:
    name: str
    p75: float
    rating: str  # good | needs_improvement | poor


@dataclass(frozen=True)
class FieldSignal:
    url: str
    scope: str  # "url" | "origin"
    form_factor: str
    metrics: tuple[FieldMetric, ...]


def rate(metric_key: str, p75: float) -> str:
    _label, _unit, good, poor = THRESHOLDS[metric_key]
    if p75 <= good:
        return "good"
    return "needs_improvement" if p75 <= poor else "poor"


def parse_record(response: dict, *, url: str | None = None) -> FieldSignal | None:
    """One CrUX response → FieldSignal (None when it carries no record)."""
    record = (response or {}).get("record")
    if not isinstance(record, dict):
        return None
    key = record.get("key") or {}
    scope = "url" if key.get("url") else "origin"
    metrics: list[FieldMetric] = []
    for metric_key, block in (record.get("metrics") or {}).items():
        if metric_key not in THRESHOLDS or not isinstance(block, dict):
            continue
        raw = (block.get("percentiles") or {}).get("p75")
        try:
            p75 = float(raw)  # CLS p75 arrives as a string ("0.05")
        except (TypeError, ValueError):
            continue
        metrics.append(FieldMetric(THRESHOLDS[metric_key][0], p75, rate(metric_key, p75)))
    return FieldSignal(
        url=url or key.get("url") or key.get("origin") or "",
        scope=scope,
        form_factor=key.get("formFactor") or "ALL_FORM_FACTORS",
        metrics=tuple(metrics),
    )


def _fmt(metric: FieldMetric) -> str:
    if metric.name == "CLS":
        return f"{metric.p75:.2f}"
    if metric.name in ("LCP", "TTFB"):
        return f"{metric.p75 / 1000:.1f}s"
    return f"{metric.p75:.0f}ms"


_RESOLUTION = {
    "LCP": "Speed up the largest element: optimise/preload the hero image, cut server and render-blocking time",
    "INP": "Reduce main-thread work on interaction: split long JS tasks, trim third-party scripts",
    "CLS": "Reserve space for images, ads and embeds; avoid late-inserted content",
    "TTFB": "Cache HTML at the edge, cut server/database time, check redirects",
}


def field_findings(signal: FieldSignal) -> list[dict]:
    """Findings for metrics that are not 'good' (dicts: category/label/severity/resolution/url)."""
    out: list[dict] = []
    source = f"CrUX {signal.scope}-level p75, {signal.form_factor.lower()}"
    for m in signal.metrics:
        if m.rating == "good":
            continue
        out.append({
            "category": "Layout Stability" if m.name == "CLS" else "Performance",
            "label": f"Field {m.name} {_fmt(m)} ({m.rating.replace('_', ' ')}; {source})",
            "severity": "HIGH" if m.rating == "poor" else "MEDIUM",
            "resolution": _RESOLUTION[m.name],
            "url": signal.url,
        })
    return out


def fetch_record(api_key: str, url: str, *, form_factor: str = FORM_FACTOR_DEFAULT,
                 origin_fallback: bool = True) -> dict:
    """CrUX record for ``url`` (falls back to its origin when the URL has none)."""
    def query(body: dict) -> dict:
        req = urllib.request.Request(
            f"{CRUX_ENDPOINT}?key={api_key}", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            raise

    data = query({"url": url, "formFactor": form_factor})
    if not data.get("record") and origin_fallback:
        from urllib.parse import urlparse
        p = urlparse(url)
        data = query({"origin": f"{p.scheme}://{p.netloc}", "formFactor": form_factor})
        if data.get("record"):
            data["requested_url"] = url
    return data


__all__ = ("THRESHOLDS", "FieldMetric", "FieldSignal", "rate", "parse_record",
           "field_findings", "fetch_record")
