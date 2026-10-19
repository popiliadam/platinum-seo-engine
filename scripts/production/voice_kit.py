#!/usr/bin/env python3
"""voice_kit.py — a project's own voice & experience material (S-26, S-16).

Each project keeps, in ``{workspace}/projects/<slug>/voice/``:

  voice.md            how the business talks (tone, words it uses)
  opinions.md         what it stands for / argues
  facts.json          its own numbers, each with a source
                      [{"claim": "...", "source": "..."}]
  stories.json        customer stories it may tell (permission given)
                      [{"summary": "...", "source": "...", "consent": true}]
  banned-phrases.txt  stock phrases never to use (one per line)
  authors.json        real people who write / sign the content
                      [{"name", "role", "url", "sameAs": [...]}]

Sources: client interviews, e-mails, Google reviews, social posts. Nothing is
invented here: a missing file is reported in ``missing`` and its material is
empty — the writer then marks the experience as missing instead of making it up
(quality_gates ``experience`` gate), and new-blog stops when there is no real
author.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

KIT_FILES = (
    "voice.md", "opinions.md", "facts.json", "stories.json",
    "banned-phrases.txt", "authors.json",
)


@dataclass(frozen=True)
class VoiceKit:
    voice: str
    opinions: str
    facts: tuple[dict, ...]
    stories: tuple[dict, ...]
    banned_phrases: tuple[str, ...]
    authors: tuple[dict, ...]
    missing: tuple[str, ...]

    def brief_block(self) -> dict:
        """The ``experience`` block quality_gates reads from the Brief."""
        return {
            "facts": [dict(f) for f in self.facts],
            "stories": [dict(s) for s in self.stories],
            "banned_phrases": list(self.banned_phrases),
        }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _read_items(path: Path, required: tuple[str, ...]) -> tuple[dict, ...] | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(
        item for item in data
        if isinstance(item, dict) and all(str(item.get(k) or "").strip() for k in required)
    )


def load_voice_kit(project_dir: Path | str) -> VoiceKit:
    """Load ``<project_dir>/voice/``; absent files are listed in ``missing``.

    Items without their source (facts/stories) or name (authors) are dropped —
    an unsourced claim is not material the writer may use.
    """
    d = Path(project_dir) / "voice"
    missing: list[str] = []

    def text(name: str) -> str:
        value = _read_text(d / name)
        if value is None:
            missing.append(name)
        return value or ""

    def items(name: str, required: tuple[str, ...]) -> tuple[dict, ...]:
        value = _read_items(d / name, required)
        if value is None:
            missing.append(name)
        return value or ()

    voice = text("voice.md")
    opinions = text("opinions.md")
    facts = items("facts.json", ("claim", "source"))
    stories = items("stories.json", ("summary", "source"))
    banned_raw = text("banned-phrases.txt")
    authors = items("authors.json", ("name",))
    banned = tuple(line.strip() for line in banned_raw.split("\n") if line.strip())
    return VoiceKit(voice, opinions, facts, stories, banned, authors, tuple(missing))


__all__ = ("KIT_FILES", "VoiceKit", "load_voice_kit")
