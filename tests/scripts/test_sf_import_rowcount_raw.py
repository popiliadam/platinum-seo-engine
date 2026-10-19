"""D-18 — sf_import counts CSV records and never loses the raw export."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ingestion import sf_import


def test_multiline_field_counts_as_one_row(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "internal_all.csv").write_text(
        'Address,Title 1\n"https://x.test/a","line one\nline two"\n"https://x.test/b",B\n',
        encoding="utf-8")
    matched, _, _ = sf_import.match_tiers(raw)
    row = next(m for m in matched if m.canonical_name == "internal_all")
    assert row.row_count == 2


def test_ndjson_conversion_keeps_the_original(tmp_path: Path) -> None:
    path = tmp_path / "page_titles_all.csv"
    lines = [{"Address": "https://x.test/a", "Title 1": "A"}]
    original = "\n".join(json.dumps(x) for x in lines) + "\n"
    path.write_text(original, encoding="utf-8")
    assert sf_import._normalize_ndjson_csv_in_place(path)
    assert path.read_text(encoding="utf-8").startswith("Address")
    assert (tmp_path / "page_titles_all.csv.ndjson-original").read_text(encoding="utf-8") == original
