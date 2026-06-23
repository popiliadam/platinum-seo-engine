#!/usr/bin/env python3
"""
content_scope.py — content-preserving SITE-CHROME stripper (CCE batch B6).

Surgically removes navigation / header / footer / aside subtrees and link-only
menus from competitor HTML BEFORE the recon transform measures it — WITHOUT
touching the article body. This is the permanent home of B5's proof-time
``strip_chrome.py`` workaround (proof finding #1).

Why this exists (a concrete CCE engine finding):
    ``competitor_recon_transform`` counts EVERY ``<ul>/<table>/<h2>/<strong>``
    in the fetched DOM. On real TR e-commerce / vet sites that inflated
    ``structure_ceiling.lists`` to 87 and ``gap.must_cover_headings`` to 148
    with pure chrome ("Yavru Kedi Maması", "E-BÜLTEN", "İçindekiler"). The
    structure / gap gates then measured navigation, not the competitor's
    article (spec §4a: competitor coverage = the ARTICLE's coverage).

Two naive fixes both fail, so neither is used:
    - trust the raw ``main_content_only`` DOM  → menus still inflate the ceiling
    - drop every chrome-*classed* subtree → destroys content wrapped in
      chrome-named ``<div>``s (some pages collapse to 0 words)

Surgical rule (content-preserving):
    Rule 1  Drop the whole subtree of structural chrome tags: ``nav``,
            ``header``, ``footer``, ``aside`` (nested-depth counted, so an
            inner ``</nav>`` inside a ``<footer>`` does not re-enable output).
    Rule 2  Drop a ``<ul>/<ol>`` ONLY if it is LINK-ONLY: it has ≥1 ``<li>``,
            every ``<li>`` contains an ``<a>``, AND the list's non-anchor prose
            is negligible vs its anchor text
            (``prose_chars <= max(8, anchor_chars // 10)``). That is a
            navigation / footer menu, never a genuine content enumeration.
            Content lists (whose ``<li>`` carry prose, even if some link out)
            are KEPT.
    Everything else is preserved verbatim — headings, paragraphs, content
    tables, content lists, ``<strong>`` emphasis, and HTML entities.

Hardening over the proof workaround:
    The workaround used ``convert_charrefs=False`` but never re-emitted
    entity / char references, so ``&amp;`` / ``&nbsp;`` in article text were
    silently dropped (a content loss). This module keeps ``convert_charrefs``
    off (faithful, idempotent re-emission of raw markup) AND re-emits entity
    and numeric character references verbatim — so no content word is lost.

Discipline (mirrors scripts/validation/content_validator.py):
    - stdlib ``html.parser`` ONLY — zero dependency, no BeautifulSoup.
    - No import side-effects, no file I/O, no MCP.
    - Idempotent: ``strip(strip(x)) == strip(x)``.
    - Plugin-agnostic: no project slug / brand literal anywhere.

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§4a competitor_recon), docs/superpowers/plans/cce/B6-recon-hardening.md.
"""

from __future__ import annotations

from html.parser import HTMLParser

#: Structural chrome tags whose entire subtree is discarded (Rule 1).
_CHROME_TAGS: frozenset[str] = frozenset({"nav", "header", "footer", "aside"})
_LIST_TAGS: frozenset[str] = frozenset({"ul", "ol"})


class _ChromeStripper(HTMLParser):
    """Two-concern parser:

    1. Drop chrome-tag subtrees outright (depth-counted).
    2. Buffer every ``<ul>/<ol>`` and decide at its close whether it is a
       link-only menu (drop) or a content list (emit verbatim).

    Output is re-serialised from the token stream, so it is faithful to the
    input markup and idempotent under a second ``strip``.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self._chrome_depth = 0
        self._chrome_tag: str | None = None
        # List buffering stack: each entry captures one <ul>/<ol> subtree so the
        # link-only decision can be made at its close.
        self._list_stack: list[dict] = []

    # -- emit target: top-level out, or the innermost buffered list -----------
    def _emit(self, s: str) -> None:
        if self._list_stack:
            self._list_stack[-1]["buf"].append(s)
        else:
            self.out.append(s)

    @staticmethod
    def _esc_attr(v: str) -> str:
        """Escape ``&`` and ``"`` so a value re-serialised inside double quotes
        round-trips. Real markup embeds nested quotes in attributes (JSON in
        ``data-settings``, ``style="font-family: "X""``); without escaping the
        re-emitted ``key="..."`` is malformed and a second ``strip`` reparses it
        differently (non-idempotent). ``&`` first so ``&quot;`` is not doubled."""
        return v.replace("&", "&amp;").replace('"', "&quot;")

    @classmethod
    def _attr_str(cls, attrs) -> str:
        return "".join(
            f' {k}="{cls._esc_attr(v)}"' if v is not None else f" {k}"
            for k, v in attrs
        )

    # -- start tags -----------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._chrome_depth > 0:
            if tag == self._chrome_tag:
                self._chrome_depth += 1
            return
        if tag in _CHROME_TAGS:
            self._chrome_depth = 1
            self._chrome_tag = tag
            return
        if tag in _LIST_TAGS:
            self._list_stack.append({
                "tag": tag, "attrs": self._attr_str(attrs), "buf": [],
                "li_count": 0, "li_with_link": 0,
                "anchor_chars": 0, "prose_chars": 0,
                "_li_has_link": False, "_in_anchor": 0,
                "_has_content_child": False,
            })
            return
        if tag == "li" and self._list_stack:
            top = self._list_stack[-1]
            top["li_count"] += 1
            top["_li_has_link"] = False
        if tag == "a" and self._list_stack:
            self._list_stack[-1]["_in_anchor"] += 1
            self._list_stack[-1]["_li_has_link"] = True
        self._emit(f"<{tag}{self._attr_str(attrs)}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self._chrome_depth > 0:
            return
        if tag in _CHROME_TAGS:
            return
        self._emit(f"<{tag}{self._attr_str(attrs)}/>")

    # -- end tags -------------------------------------------------------------
    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._chrome_depth > 0:
            if tag == self._chrome_tag:
                self._chrome_depth -= 1
                if self._chrome_depth == 0:
                    self._chrome_tag = None
            return
        if tag == "a" and self._list_stack and self._list_stack[-1]["_in_anchor"] > 0:
            self._list_stack[-1]["_in_anchor"] -= 1
        if tag == "li" and self._list_stack:
            top = self._list_stack[-1]
            if top["_li_has_link"]:
                top["li_with_link"] += 1
        if tag in _LIST_TAGS and self._list_stack:
            self._close_list()
            return
        self._emit(f"</{tag}>")

    def _close_list(self) -> None:
        lst = self._list_stack.pop()
        inner = "".join(lst["buf"])
        # Link-only menu test: has items, every <li> has a link, the non-anchor
        # prose is negligible vs anchor text, AND it does not wrap a kept
        # content sublist (a list whose <li> link out but which contains a
        # prose child list is content, not navigation — prose must survive).
        link_only = (
            lst["li_count"] >= 1
            and lst["li_with_link"] == lst["li_count"]
            and lst["prose_chars"] <= max(8, lst["anchor_chars"] // 10)
            and not lst["_has_content_child"]
        )
        if link_only:
            return  # drop the menu entirely
        # Kept as content → mark the enclosing list (if any) as content-bearing
        # so it is never mistaken for a menu.
        if self._list_stack:
            self._list_stack[-1]["_has_content_child"] = True
        rebuilt = f"<{lst['tag']}{lst['attrs']}>{inner}</{lst['tag']}>"
        self._emit(rebuilt)

    # -- character data / references ------------------------------------------
    def handle_data(self, data):
        if self._chrome_depth > 0:
            return
        if self._list_stack:
            top = self._list_stack[-1]
            chars = len(data.strip())
            if top["_in_anchor"] > 0:
                top["anchor_chars"] += chars
            else:
                top["prose_chars"] += chars
        self._emit(data)

    def handle_entityref(self, name):
        # Re-emit ``&name;`` verbatim (content faithfulness; convert_charrefs
        # is off). Dropped while inside a chrome subtree, like any other data.
        if self._chrome_depth > 0:
            return
        self._emit(f"&{name};")

    def handle_charref(self, name):
        if self._chrome_depth > 0:
            return
        self._emit(f"&#{name};")

    def result(self) -> str:
        while self._list_stack:  # flush any unclosed lists as content
            self._close_list()
        return "".join(self.out)


def strip(html: str) -> str:
    """Return ``html`` with site chrome removed and article content preserved.

    Idempotent (``strip(strip(x)) == strip(x)``), pure, stdlib-only. A falsy /
    non-string input yields ``""``.
    """
    if not html or not isinstance(html, str):
        return ""
    s = _ChromeStripper()
    s.feed(html)
    s.close()
    return s.result()


__all__ = ("strip",)
