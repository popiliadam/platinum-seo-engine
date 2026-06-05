"""Hard-coded ORDERED workflow definitions for the AMO orchestrator (Path A).

Each module here is a data-driven STEP table plus a thin driver that runs every
step through the batch-1b spine (verify -> loader-transform -> commit ->
coverage) and writes ONE coverage record. There is no DAG engine: the order is
a plain Python sequence. The model makes each step's MCP call and drops the raw
artifact + the transform output; this package's CODE verifies + commits + records.
"""
