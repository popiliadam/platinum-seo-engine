#!/usr/bin/env python3
"""content_validator.py — deterministic post-generation content gate.

Pure, zero-dependency (stdlib ``html.parser`` only) inspection of generated
blog HTML against the testable subset of the R-XX content rules. Returns a
:class:`ContentReport`; it performs NO I/O and never writes files, so the rule
logic is fully unit-testable from a string. The runtime gate
(``scripts/hooks/validate_content_write.py``) and a future skill-side call both
consume this one library.

Audit ref: docs/audits/2026-06-04_deep_quality_security_audit.md (Gap 1).
Design:    docs/superpowers/specs/2026-06-04-content-validator-design.md.

Severity:
    RED   — hard rule violation; the gate blocks the write.
    AMBER — advisory; the gate warns but allows the write.

Visible-text rules (AI-disclosure, …) run on text with <script>/<style>/
<template>/<noscript> and comments stripped, so JSON-LD and image IPTC
disclosure (R-123, *required*) are never flagged.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

def _skip_block_re(tags: tuple[str, ...]) -> "re.Pattern[str]":
    """Compile a regex that removes HTML comments and the given tags *with
    their content* (closed blocks), plus any lone/unclosed open tag of the same
    names. Robust to malformed HTML: an unclosed <style>/<script> strips only
    the open tag rather than swallowing the rest of the document."""
    group = "|".join(tags)
    return re.compile(
        r"<!--.*?-->"
        r"|<(" + group + r")\b[^>]*>.*?</\1\s*>"
        r"|<(?:" + group + r")\b[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )


# Visible text keeps <svg> (its <text> can be real prose); the structural pass
# (class/img) drops <svg> too, since icon SVGs carry third-party classes.
_VISIBLE_STRIP_RE = _skip_block_re(("script", "style", "template", "noscript"))
_STRUCT_STRIP_RE = _skip_block_re(("script", "style", "template", "noscript", "svg"))


# --------------------------------------------------------------------------
# Findings model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """A single rule violation."""

    rule: str
    severity: str  # "RED" | "AMBER"
    message: str


@dataclass
class ContentReport:
    """Aggregate verdict over a piece of content."""

    findings: list[Finding]

    @property
    def has_red(self) -> bool:
        return any(f.severity == "RED" for f in self.findings)

    @property
    def verdict(self) -> str:
        if any(f.severity == "RED" for f in self.findings):
            return "RED"
        if any(f.severity == "AMBER" for f in self.findings):
            return "AMBER"
        return "GREEN"


# --------------------------------------------------------------------------
# Visible-text extraction
# --------------------------------------------------------------------------

class _TextCollector(HTMLParser):
    """Collects all character data. Skip blocks are removed by regex *before*
    parsing (so no fragile open/close-tag depth tracking that a malformed
    document could leave stuck). ``convert_charrefs`` decodes entities so e.g.
    a non-breaking space still reads as whitespace for the phrase checks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def extract_visible_text(html: str) -> str:
    """Return human-visible text: script/style/template/noscript blocks and
    HTML comments removed (robust to unclosed skip tags), remaining tags
    stripped, entities decoded."""
    collector = _TextCollector()
    collector.feed(_VISIBLE_STRIP_RE.sub(" ", html))
    collector.close()
    return collector.text()


# --------------------------------------------------------------------------
# Rule: AI-disclosure ban (🔴 RED) — the project's hardest constraint.
# Phrase-level, case-insensitive. The bare term "AI"/"yapay zeka" is never
# flagged; only multi-word disclosure phrasings are.
# --------------------------------------------------------------------------

_AI_CONNECTOR = r"(?:taraf[ıi]ndan|ile|kullan[ıi]larak|yard[ıi]m[ıi]yla)"
_AI_DISCLOSURE_PATTERNS = (
    # Turkish
    r"yapay\s+zeka\s+" + _AI_CONNECTOR + r"\s+(?:yaz[ıi]l|üretil|oluştur|hazırlan)",
    r"bu\s+(?:içerik|yaz[ıi]|makale)\s+yapay\s+zeka\s+" + _AI_CONNECTOR,
    r"(?:dil\s+modeli|chatgpt|gpt|claude|gemini|llm)\s+taraf[ıi]ndan\s+"
    r"(?:yaz|üret|oluştur|hazırlan)",
    # English
    r"written\s+by\s+(?:an?\s+)?ai\b",
    r"generated\s+by\s+(?:an?\s+)?ai\b",
    r"ai[-\s]generated\s+(?:content|article|text|copy)",
    r"as\s+an?\s+(?:ai\s+language\s+model|large\s+language\s+model|ai)\b",
    r"created\s+by\s+artificial\s+intelligence",
    r"\bi\s+am\s+an\s+ai\b",
)
_AI_DISCLOSURE_RE = re.compile(
    "|".join(_AI_DISCLOSURE_PATTERNS), re.IGNORECASE | re.UNICODE
)


def _check_ai_disclosure(visible_text: str) -> list[Finding]:
    match = _AI_DISCLOSURE_RE.search(visible_text)
    if not match:
        return []
    return [
        Finding(
            rule="AI-disclosure",
            severity="RED",
            message=(
                "Forbidden AI-disclosure phrase in visible HTML: "
                f"{match.group(0)!r}"
            ),
        )
    ]


# --------------------------------------------------------------------------
# Rule: R-22 fragment boundary (🔴) + R-43 FAQ accordion (🔴).
# Raw-string scans, matching the rules' own "regex output check" enforcement.
# The [\s/>] suffix distinguishes the forbidden <head>/<html>/<body> from the
# allowed semantic <header>/<footer> (prefix collision guard). Legitimate code
# samples teaching HTML are escaped (&lt;!DOCTYPE…), so they never match.
# --------------------------------------------------------------------------

_R22_RE = re.compile(r"<!doctype|<html[\s/>]|<head[\s/>]|<body[\s/>]", re.IGNORECASE)
_R43_RE = re.compile(r"<(?:details|summary)[\s/>]", re.IGNORECASE)


def _check_fragment_boundary(html: str) -> list[Finding]:
    if _R22_RE.search(html):
        return [
            Finding(
                rule="R-22",
                severity="RED",
                message=(
                    "Document-level tag (<!doctype/<html/<head/<body>) present — "
                    "output must be an <article> fragment (R-22)"
                ),
            )
        ]
    return []


def _check_accordion(html: str) -> list[Finding]:
    if _R43_RE.search(html):
        return [
            Finding(
                rule="R-43",
                severity="RED",
                message=(
                    "FAQ accordion (<details>/<summary>) forbidden — FAQ must be "
                    "static visible HTML (R-43)"
                ),
            )
        ]
    return []


# --------------------------------------------------------------------------
# Rule: R-77 image alt-text (🔴) + R-61 pse- prefix CSS class (🔴).
# One structural parse pass collects both signals.
# --------------------------------------------------------------------------

class _StructuralParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.imgs_without_alt = 0
        self.bad_classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._inspect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self._inspect(tag, attrs)

    def _inspect(self, tag: str, attrs: list) -> None:
        ad = dict(attrs)
        if tag == "img":
            alt = ad.get("alt")
            if alt is None or not alt.strip():
                self.imgs_without_alt += 1
        cls = ad.get("class")
        if cls:
            for token in cls.split():
                if not token.startswith("pse-"):
                    self.bad_classes.append(token)


def _check_structural(html: str) -> list[Finding]:
    parser = _StructuralParser()
    # Strip script/style/template/noscript/svg first: icon-SVG and embed classes
    # are third-party and must not trip the pse- discipline (R-61).
    parser.feed(_STRUCT_STRIP_RE.sub(" ", html))
    parser.close()
    findings: list[Finding] = []
    if parser.imgs_without_alt:
        findings.append(
            Finding(
                rule="R-77",
                severity="RED",
                message=(
                    f"{parser.imgs_without_alt} <img> with missing/empty alt "
                    "attribute (R-77)"
                ),
            )
        )
    if parser.bad_classes:
        offenders = sorted(set(parser.bad_classes))
        findings.append(
            Finding(
                rule="R-61",
                severity="RED",
                message=f"non-'pse-' CSS class(es): {offenders} (R-61)",
            )
        )
    return findings


# --------------------------------------------------------------------------
# Rule: R-106 citation density (🟡). Per 500 words, min 1 max 2 citations
# (universal — not profile-aware). A "citation" is an external-rel <a> or an
# inline parenthetical "(Source, 2024)". Skipped below a one-window floor so
# short content isn't penalised.
# --------------------------------------------------------------------------

_CITATION_FLOOR_WORDS = 400
_CITATION_LINK_RE = re.compile(
    r"<a\b[^>]*\brel\s*=\s*[\"'][^\"']*external", re.IGNORECASE
)
_CITATION_PAREN_RE = re.compile(r"\([^)]*,\s*\d{4}\)")


def _check_citation_density(html: str, visible_text: str) -> list[Finding]:
    words = len(visible_text.split())
    if words < _CITATION_FLOOR_WORDS:
        return []
    # Known minor over-count (advisory-only): a rel="external" <a> whose anchor
    # text is itself a parenthetical "(Source, 2024)" is counted by both
    # patterns. Rare; only nudges an AMBER advisory, never a RED block.
    citations = len(_CITATION_LINK_RE.findall(html)) + len(
        _CITATION_PAREN_RE.findall(visible_text)
    )
    density = citations * 500.0 / words
    if density < 1.0:
        return [
            Finding(
                rule="R-106",
                severity="AMBER",
                message=(
                    f"citation density {density:.2f}/500w below min 1 "
                    f"({citations} citations in {words} words) (R-106)"
                ),
            )
        ]
    if density > 2.0:
        return [
            Finding(
                rule="R-106",
                severity="AMBER",
                message=(
                    f"citation density {density:.2f}/500w above max 2 "
                    f"({citations} citations in {words} words) (R-106)"
                ),
            )
        ]
    return []


# --------------------------------------------------------------------------
# Rule: R-101 self-contained intro (🟡). The first paragraph must stand alone
# — no back-reference to other parts of the page.
# --------------------------------------------------------------------------

_FIRST_P_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_INNER_TAG_RE = re.compile(r"<[^>]+>")
_BACKREF_RE = re.compile(
    r"yukar[ıi]da\s+gördüğünüz|bu\s+yaz[ıi]da|bu\s+makalede|"
    r"as\s+(?:mentioned|shown|we\s+saw|we\s+discussed)\s+above",
    re.IGNORECASE,
)


def _check_self_contained_intro(html: str) -> list[Finding]:
    # Strip <script>/comments first so a <p> encoded inside JSON-LD can't be
    # mistaken for the real intro paragraph.
    match = _FIRST_P_RE.search(_VISIBLE_STRIP_RE.sub(" ", html))
    if not match:
        return []
    intro = _INNER_TAG_RE.sub("", match.group(1))
    if _BACKREF_RE.search(intro):
        return [
            Finding(
                rule="R-101",
                severity="AMBER",
                message=(
                    "intro paragraph has a back-reference; it must be "
                    "self-contained (R-101)"
                ),
            )
        ]
    return []


# --------------------------------------------------------------------------
# Rule: R-104 stats density (🟡, profile-aware). Numeric "stats" (a percent, a
# decimal, or a multi-digit number) per word, against profile min/max bands.
# Profiles without a band (portfolio / unknown / None) are skipped.
# --------------------------------------------------------------------------

# (min_denom_words_per_stat, max_denom_words_per_stat); None = no bound.
_STATS_BANDS: dict[str, tuple[int | None, int | None]] = {
    "ymyl": (500, 200),
    "e-commerce": (800, 300),
    "b2b-saas": (600, 250),
    "local-service": (1000, None),
    "portfolio": (None, None),
}
_STAT_RE = re.compile(r"%\s*\d+|\d+\s*%|\d+[.,]\d+|\d{2,}")


def _check_stats_density(visible_text: str, profile: str | None) -> list[Finding]:
    band = _STATS_BANDS.get(profile) if profile else None
    if band is None:
        return []
    min_denom, max_denom = band
    words = len(visible_text.split())
    stats = len(_STAT_RE.findall(visible_text))
    findings: list[Finding] = []
    if min_denom:
        min_required = words // min_denom
        if min_required >= 1 and stats < min_required:
            findings.append(
                Finding(
                    rule="R-104",
                    severity="AMBER",
                    message=(
                        f"stats density: {stats} stats in {words} words, "
                        f"expected ≥{min_required} (profile {profile}) (R-104)"
                    ),
                )
            )
    if max_denom:
        max_allowed = words // max_denom
        if max_allowed >= 1 and stats > max_allowed:
            findings.append(
                Finding(
                    rule="R-104",
                    severity="AMBER",
                    message=(
                        f"stats density: {stats} stats in {words} words, "
                        f"max {max_allowed} (profile {profile}) (R-104)"
                    ),
                )
            )
    return findings


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

def validate_content(html: str, *, profile: str | None = None) -> ContentReport:
    """Validate ``html`` against the v1 rule set; return a :class:`ContentReport`.

    ``profile`` (one of the project-config profile enum, or ``None``) tunes the
    profile-aware advisory bands; ``None`` uses neutral defaults. RED rules are
    profile-independent.
    """
    visible = extract_visible_text(html)
    findings: list[Finding] = []
    findings.extend(_check_ai_disclosure(visible))
    findings.extend(_check_fragment_boundary(html))
    findings.extend(_check_accordion(html))
    findings.extend(_check_structural(html))
    findings.extend(_check_citation_density(html, visible))
    findings.extend(_check_self_contained_intro(html))
    findings.extend(_check_stats_density(visible, profile))
    return ContentReport(findings=findings)


# --------------------------------------------------------------------------
# CLI — `python -m scripts.validation.content_validator <file> [--profile P]`.
# Exit 1 on a RED verdict (CI gate), 0 otherwise. Findings on stderr.
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="content_validator.py",
        description="Deterministic content gate over generated blog HTML "
        "(audit 2026-06-04 Gap 1). Exit 1 on a RED verdict.",
    )
    ap.add_argument("file", help="Path to the HTML file to validate.")
    ap.add_argument(
        "--profile",
        default=None,
        help="Project profile (ymyl|e-commerce|b2b-saas|local-service|"
        "portfolio) for the profile-aware advisory band (R-104).",
    )
    args = ap.parse_args(argv)

    html = Path(args.file).read_text(encoding="utf-8", errors="ignore")
    report = validate_content(html, profile=args.profile)
    for finding in report.findings:
        print(
            f"{finding.severity} {finding.rule}: {finding.message}",
            file=sys.stderr,
        )
    print(f"verdict: {report.verdict}", file=sys.stderr)
    return 1 if report.has_red else 0


if __name__ == "__main__":
    sys.exit(main())
