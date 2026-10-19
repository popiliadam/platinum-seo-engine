"""D-10 / D-13 — DataForSEO spend is counted from every DFS event and the response's own cost.

The budget check counted only source.kind == dataforseo_mcp events with a
numeric cost.credits (~66 of 197 live events), so ~2/3 of spend was invisible;
cost was a fixed per-keyword estimate and the response's own cost was ignored.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.budget import check_budget as cb
from scripts.util import dfs_response as dr

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def _ev(**kw) -> dict:
    return {"event_kind": "provenance", "timestamp": "2026-10-19T10:00:00Z", **kw}


def _write(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


def test_usage_counts_provider_tagged_and_reports_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path, [
        _ev(source={"kind": "dataforseo_mcp"}, cost={"provider": "dataforseo", "credits": 10}),
        _ev(source={"kind": "tool_computed"}, cost={"provider": "dataforseo", "credits": 5,
                                                    "currency": "USD", "amount": 0.21}),
        _ev(source={"kind": "dataforseo_mcp"}),                       # no cost at all
        _ev(source={"kind": "gsc_mcp"}),                              # not DFS
    ])
    usage = cb.usage_last_24h(path, NOW)
    assert usage == {"credits": 15.0, "usd": 0.21, "dfs_events": 3, "unknown_cost_events": 1}
    assert cb._sum_last_24h(path, NOW) == 15.0


def test_response_cost_reads_dfs_own_field() -> None:
    assert dr.response_cost({"cost": 0.039, "tasks": [{"cost": 0.039}]}) == 0.039
    assert dr.response_cost({"tasks": [{"cost": 0.01}, {"cost": 0.02}]}) == 0.03
    assert dr.response_cost({"items": []}) is None
