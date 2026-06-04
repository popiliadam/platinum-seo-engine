"""codex-audit finding 6: the runtime documents that calling
events_writer.next_run_id() and then passing the result to an append_* call is
RACY (the max-id read happens outside the append flock; two concurrent callers
can collide). scripts/ingestion/sf_import.py already uses the corrected
auto-allocation (omit run_id / pass None). This guard fails if any SKILL.md
still demonstrates the racy pattern, so the doc fix cannot regress.
"""
import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"

# The racy *usage*: assigning next_run_id() into a run_id argument or a variable
# later handed to append_*(). A bare mention in an import inventory is allowed.
_RACY = re.compile(r"(run_id|rid)\s*=\s*events_writer\.next_run_id\(")


def test_no_racy_next_run_id_usage():
    offenders = []
    for f in sorted(SKILLS.rglob("SKILL.md")):
        for i, line in enumerate(f.read_text("utf-8").splitlines(), 1):
            if _RACY.search(line):
                offenders.append(f"{f.relative_to(SKILLS)}:{i}: {line.strip()}")
    assert not offenders, (
        f"{len(offenders)} racy next_run_id() usage(s) remain — remove the "
        "run_id=... line so the id auto-allocates race-free inside the append "
        "flock (mirror scripts/ingestion/sf_import.py):\n" + "\n".join(offenders)
    )
