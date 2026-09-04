"""Contract invariant: every checkpoint-brief Unit must consume DECISIONS.md.

`tooling.checkpoint_brief.write_checkpoint_brief` unconditionally reads and
upserts the existing DECISIONS.md (ensure_decisions_approval_checklist +
upsert_checkpoint_block). So any checkpoint-brief Unit that lists DECISIONS.md as
an output but NOT as an input is an untruthful contract: the v3 in-place-lineage
guard then treats it as a non-consuming producer, which can make an earlier
DECISIONS.md-binding required check (e.g. idea-brief) go stale and BLOCK the run
(see tests/v3/test_idea_brainstorm_v3_completion.py). This fast, deterministic
test pins the invariant across ALL executable pipelines so the class of defect
cannot silently return in any UNITS template.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = sorted((REPO_ROOT / "templates").glob("UNITS.*.csv"))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_checkpoint_brief_units_consume_decisions(template: Path) -> None:
    rows = list(csv.DictReader(template.read_text(encoding="utf-8").splitlines()))
    offenders = []
    for row in rows:
        if row.get("skill") != "checkpoint-brief":
            continue
        outputs = (row.get("outputs") or "").split(";")
        inputs = (row.get("inputs") or "").split(";")
        if "DECISIONS.md" in outputs and "DECISIONS.md" not in inputs:
            offenders.append(row.get("unit_id"))
    assert not offenders, (
        f"{template.name}: checkpoint-brief Unit(s) {offenders} write DECISIONS.md "
        "without declaring it as an input; checkpoint-brief reads+merges the "
        "existing DECISIONS.md, so this breaks the v3 in-place-lineage guard"
    )
