"""AMO orchestrator spine (Path A): verify -> transform -> commit -> coverage.

The model makes each step's MCP call and drops a raw artifact at an
orchestrator-dictated path; this package's CODE then verifies that artifact's
identity + content + freshness, runs the pure transform, commits the rows
through the one serialized committer, and records a coverage step. Hooks/code
cannot make MCP calls — so the spine VERIFIES outputs, it does not call tools.
"""
