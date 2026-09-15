"""A scripted agent for conformance tests.

It performs packets the way a model-driven agent would: read ``packet.json``,
write the declared outputs under ``outputs/``, call ``continue``. Behaviours
are keyed by step id (producers and repairs) or gate id (provers), and tests
override them to misbehave on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import yaml

from rh.api import Harness, Outcome, OutcomeKind

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOAL = "Give me a brief on stopping criteria for verify-repair loops in long-horizon agents.\n"

Behaviour = Callable[[dict, Path], None]

SOURCES = {
    "a.md": "# Mirror Loop\n\nA verify-repair loop should stop when the verifier's ground stops moving.\n",
    "b.md": "# Contextual drag\n\nRepairs that inherit the failed attempt inherit its errors.\n",
}
STATEMENTS = [
    ("s1", "A verify-repair loop should stop when the verifier's ground stops moving.", "a.md", "quotes"),
    ("s2", "Repairs that inherit the failed attempt inherit its errors.", "b.md", "quotes"),
]


# --- default behaviours -------------------------------------------------------


def spec_text(**overrides) -> str:
    criteria = [
        {"id": "C1", "text": "The brief answers when a verify-repair loop should stop.", "kind": "answers", "ground": "source"},
        {"id": "C2", "text": "Every statement is supported by the cited source.", "kind": "supported", "ground": "source"},
        {"id": "C3", "text": "Every paragraph carries a resolving provenance pointer.", "kind": "provenance", "ground": "computation"},
        {"id": "C4", "text": "No scaffold or placeholder remains.", "kind": "scaffold", "ground": "computation"},
        {"id": "C5", "text": "Outputs parse.", "kind": "format", "ground": "computation"},
        {"id": "C6", "text": "Reads as a decision memo.", "kind": "quality", "ground": "human", "layer": "quality"},
    ]
    data = {"schema": "rh.success_spec/1", "scope": "Stopping criteria only.", "criteria": criteria, "drift": ["a survey of agents"]}
    data.update(overrides)
    return yaml.safe_dump(data, sort_keys=False)


def write_spec(packet: dict, out: Path, **overrides) -> None:
    (out / "success_spec.yaml").write_text(spec_text(**overrides), encoding="utf-8")


def write_sources(packet: dict, out: Path) -> None:
    (out / "sources").mkdir(exist_ok=True)
    for name, body in SOURCES.items():
        (out / "sources" / name).write_text(body, encoding="utf-8")


def write_core_set(packet: dict, out: Path) -> None:
    (out / "core_set.csv").write_text("id,title\na,Mirror Loop\nb,Contextual drag\n", encoding="utf-8")


def inputs_by_name(packet: dict) -> dict[str, str]:
    return {i["name"]: i["hash"] for i in packet["inputs"]}


def write_brief(packet: dict, out: Path, *, drop_pointer: str | None = None, scaffold: bool = False, extra: str = "") -> None:
    hashes = inputs_by_name(packet)
    paragraphs = [f"## Brief\n"]
    statements = []
    for sid, text, source, relation in STATEMENTS:
        paragraphs.append(text + " This matters for long-horizon agents.")
        evidence = [] if sid == drop_pointer else [{"hash": hashes[f"sources/{source}"], "relation": relation, "locator": "p.1"}]
        statements.append({"id": sid, "text": text, "evidence": evidence})
    body = "\n\n".join(paragraphs) + "\n" + extra
    if scaffold:
        body += "\n<!-- scaffold -->\n"
    (out / "brief.md").write_text(body, encoding="utf-8")
    (out / "statements.json").write_text(json.dumps({"schema": "rh.statements/1", "statements": statements}, indent=2), encoding="utf-8")


def gate_result(packet: dict, out: Path, verdict: str = "pass", score: float | None = 1.0, findings: list[dict] | None = None) -> None:
    gate = packet["gate"]
    data = {
        "schema": "rh.gate_result/1",
        "gate": gate["id"],
        "step": gate["checked_step"],
        "pass_id": gate["checked_pass"],
        "verdict": verdict,
        "score": score,
        "findings": findings or [],
    }
    (out / "gate_result.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


DEFAULTS: dict[str, Behaviour] = {
    "spec": write_spec,
    "retrieve": write_sources,
    "curate": write_core_set,
    "write": write_brief,
    "source-support": gate_result,
    "spec-coverage": gate_result,
}


# --- the agent -------------------------------------------------------------------


class Agent:
    def __init__(self, harness: Harness, **overrides: Behaviour):
        self.harness = harness
        self.behaviours = {**DEFAULTS, **overrides}
        self.performed: list[dict] = []

    @staticmethod
    def packet_of(outcome: Outcome) -> dict:
        return json.loads((Path(outcome.packet).parent / "packet.json").read_text(encoding="utf-8"))

    def perform(self, outcome: Outcome) -> dict:
        packet = self.packet_of(outcome)
        key = packet["gate"]["id"] if packet["role"] == "prover" else packet["step"]
        self.behaviours[key](packet, Path(outcome.packet).parent / "outputs")
        self.performed.append(packet)
        return packet

    def drive(self, outcome: Outcome, limit: int = 60, until: Callable[[dict], bool] | None = None) -> Outcome:
        """Perform packets until the harness needs a Decision, is blocked, the Run ends,
        or ``until(packet)`` is true for the packet just handed out."""
        while outcome.kind is OutcomeKind.PROGRESSED and limit > 0:
            if until is not None and until(self.packet_of(outcome)):
                return outcome
            self.perform(outcome)
            outcome = self.harness.continue_()
            limit -= 1
        assert limit > 0, "the Loop did not settle"
        return outcome

    def drive_to_repair(self, outcome: Outcome) -> Outcome:
        return self.drive(outcome, until=lambda packet: packet["role"] == "repair")


def fresh(tmp_path: Path, project: Path | None = None, **overrides: Behaviour) -> tuple[Harness, Agent]:
    harness = Harness(
        tmp_path / "ws",
        skills_root=FIXTURES / "skills",
        kinds_dir=FIXTURES / "kinds",
        project=project or tmp_path / "project",
    )
    return harness, Agent(harness, **overrides)


def to_d0(tmp_path: Path, project: Path | None = None, **overrides: Behaviour) -> tuple[Harness, Agent, Outcome]:
    harness, agent = fresh(tmp_path, project, **overrides)
    outcome = agent.drive(harness.start(GOAL, "brief-fixture"))
    assert outcome.kind is OutcomeKind.NEEDS_DECISION and outcome.decision["id"] == "D0", outcome
    return harness, agent, outcome


def to_d_final(tmp_path: Path, project: Path | None = None, **overrides: Behaviour) -> tuple[Harness, Agent, Outcome]:
    harness, agent, _ = to_d0(tmp_path, project, **overrides)
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.kind is OutcomeKind.NEEDS_DECISION and outcome.decision["id"] == "D-final", outcome
    return harness, agent, outcome


def to_completed(tmp_path: Path, project: Path | None = None, **overrides: Behaviour) -> tuple[Harness, Agent, Outcome]:
    harness, agent, _ = to_d_final(tmp_path, project, **overrides)
    outcome = harness.decide("D-final", "accept", by="tests")
    assert outcome.kind is OutcomeKind.COMPLETED, outcome
    return harness, agent, outcome
