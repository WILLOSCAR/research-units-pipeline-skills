"""The Skill library agrees with the six Loop kinds.

Every Skill a kind names exists, carries the role the kind schedules it in,
and declares the inputs and outputs the kind binds. No Skill writes a
self-reported verdict. The kernel schedules from the kind, so this is the
contract a Skill author is held to.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rh.kernel.kinds import list_kinds, load_kind
from rh.kernel.skills import SkillLibrary, default_skills_root
from rh.kernel.steps import GATE_RESULT_FILE, GOAL_FILE, SPEC_FILE

KINDS = list_kinds()
LIBRARY = SkillLibrary(default_skills_root())
TEMPLATE = "_template_reference_first"
FORBIDDEN = re.compile(
    r"Status: PASS|\.refined\.ok|UNITS\.csv|scripts/run\.py|\btooling\b|research_harness|-selfloop\b|prior_outputs|inputs/prior"
)


def _steps():
    for name in KINDS:
        kind = load_kind(name)
        for step in kind.steps:
            yield pytest.param(name, step, id=f"{name}/{step.id}")


def _gates():
    for name in KINDS:
        kind = load_kind(name)
        for gate in kind.gates:
            if gate.skill:
                yield pytest.param(name, gate, id=f"{name}/{gate.id}")


@pytest.mark.parametrize(("kind_name", "step"), list(_steps()))
def test_every_producer_step_names_a_producer_skill_that_declares_its_contract(kind_name, step):
    skill = LIBRARY.load(step.skill)
    assert skill.role == "producer", f"{step.skill} is scheduled as a producer by {kind_name}/{step.id}"
    reads = set(skill.front.get("reads") or [])
    outputs = list(skill.front.get("outputs") or [])
    consumed = {c for c in step.consumes if c not in (GOAL_FILE, SPEC_FILE)}
    assert consumed <= reads, f"{step.skill} reads {sorted(reads)} but {kind_name}/{step.id} consumes {sorted(consumed)}"
    assert set(step.produces) <= set(outputs), f"{step.skill} outputs {outputs} but {kind_name}/{step.id} produces {step.produces}"


@pytest.mark.parametrize(("kind_name", "gate"), list(_gates()))
def test_every_agent_gate_names_a_prover_skill_that_declares_its_gate(kind_name, gate):
    skill = LIBRARY.load(gate.skill)
    assert skill.role == "prover", f"{gate.skill} is scheduled as a prover by {kind_name}/{gate.id}"
    declared = skill.front.get("gate") or {}
    assert declared.get("kind") == gate.kind.value and declared.get("ground") == gate.ground.value
    assert set(gate.serves) <= set(declared.get("serves") or []), f"{gate.skill} does not serve {gate.serves}"
    assert skill.front.get("outputs") == [GATE_RESULT_FILE]
    assert skill.front.get("context") == "fresh"


def test_the_library_holds_exactly_the_skills_the_kinds_name_plus_the_template():
    named = set()
    for name in KINDS:
        kind = load_kind(name)
        named |= {s.skill for s in kind.steps} | {g.skill for g in kind.gates if g.skill}
    present = {p.name for p in Path(LIBRARY.root).iterdir() if p.is_dir()}
    assert present == named | {TEMPLATE}, {
        "unreferenced": sorted(present - named - {TEMPLATE}),
        "missing": sorted(named - present),
    }


@pytest.mark.parametrize("path", sorted(Path(LIBRARY.root).rglob("*.md")), ids=lambda p: str(p.relative_to(LIBRARY.root)))
def test_no_skill_text_carries_a_self_reported_verdict_or_a_removed_engine(path):
    hits = [m.group(0) for m in FORBIDDEN.finditer(path.read_text(encoding="utf-8"))]
    assert not hits, hits
