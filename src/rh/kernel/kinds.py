"""Loop kinds: the starting SOP for one kind of deliverable, declared in YAML.

A kind names its steps, the Skill each step calls, which kernel and agent
gates apply to which step, the budget, and what the plan may change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from rh.kernel.gates import KERNEL_GATES
from rh.kernel.records import Budget, Executor, GateDecl, GateKind, Ground, Plan, Step, decode, encode

KINDS_DIR = Path(__file__).resolve().parent.parent / "kinds"
KIND_SCHEMA = "rh.kind/1"


class KindError(ValueError):
    pass


@dataclass
class Adaptivity:
    add: bool = False
    skip: list[str] = field(default_factory=list)
    reorder: bool = False


@dataclass
class Review:
    """An intermediate Decision a kind asks for after one of its steps is admitted."""

    id: str
    after: str
    prompt: str = ""


@dataclass
class Kind:
    kind: str
    title: str
    deliverable: str
    statements: str
    steps: list[Step]
    gates: list[GateDecl]
    formats: list[str] = field(default_factory=lambda: ["md"])
    budget: Budget = field(default_factory=Budget)
    adaptivity: Adaptivity = field(default_factory=Adaptivity)
    decisions: list[Review] = field(default_factory=list)
    source: str = ""

    def review_after(self, step_id: str) -> Review | None:
        return next((r for r in self.decisions if r.after == step_id), None)

    def plan(self) -> Plan:
        return Plan(steps=[decode(Step, encode(s)) for s in self.steps])

    def gate(self, gate_id: str) -> GateDecl:
        for g in self.gates:
            if g.id == gate_id:
                return g
        raise KeyError(gate_id)

    def gates_for(self, step_id: str) -> list[GateDecl]:
        return [g for g in self.gates if g.applies(step_id)]

    def gates_serving(self, criterion_kind: str) -> list[GateDecl]:
        return [g for g in self.gates if criterion_kind in g.serves]

    def artifact_step(self) -> Step:
        for step in reversed(self.steps):
            if self.deliverable in step.produces:
                return step
        raise KindError(f"no step produces the deliverable {self.deliverable!r}")


def list_kinds(kinds_dir: Path = KINDS_DIR) -> list[str]:
    return sorted(p.stem for p in kinds_dir.glob("*.yaml"))


def load_kind(name: str, kinds_dir: Path = KINDS_DIR) -> Kind:
    path = kinds_dir / f"{name}.yaml"
    if not path.is_file():
        raise KindError(f"unknown Loop kind {name!r}; available: {', '.join(list_kinds(kinds_dir))}")
    return parse_kind(yaml.safe_load(path.read_text(encoding="utf-8")), source=str(path))


def parse_kind(data: dict, source: str = "") -> Kind:
    if not isinstance(data, dict):
        raise KindError(f"{source}: a kind is a mapping")
    try:
        return _parse_kind(data, source)
    except KindError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise KindError(f"{source}: malformed kind ({exc})") from exc


def _parse_kind(data: dict, source: str) -> Kind:
    if data.get("schema") != KIND_SCHEMA:
        raise KindError(f"{source}: schema must be {KIND_SCHEMA}")
    for key in ("kind", "title", "deliverable", "statements", "steps"):
        if key not in data:
            raise KindError(f"{source}: missing {key!r}")

    steps = [decode(Step, {"fixed": False, **s}) for s in data["steps"]]
    ids = [s.id for s in steps]
    if len(set(ids)) != len(ids):
        raise KindError(f"{source}: duplicate step ids")
    if not steps or steps[0].id != "spec":
        raise KindError(f"{source}: the first step must be 'spec' (Success Spec derivation)")

    gates: list[GateDecl] = []
    declared = data.get("gates", {}) or {}
    for gate_id, applies_to in (declared.get("kernel") or {}).items():
        if gate_id not in KERNEL_GATES:
            raise KindError(f"{source}: unknown kernel gate {gate_id!r}")
        gates.append(KERNEL_GATES[gate_id].declare(list(applies_to)))
    for raw in declared.get("agent") or []:
        gates.append(
            GateDecl(
                id=raw["id"],
                kind=GateKind(raw.get("kind", "grounded")),
                ground=Ground(raw.get("ground", "source")),
                executor=Executor.AGENT,
                serves=list(raw.get("serves", [])),
                applies_to=list(raw.get("applies_to", [])),
                routing=raw.get("routing", "checked_step"),
                skill=raw["skill"],
                calibration=dict(raw.get("calibration", {"status": "unmeasured"})),
            )
        )
    for g in gates:
        for step_id in g.applies_to:
            if step_id != "all" and step_id not in ids:
                raise KindError(f"{source}: gate {g.id!r} applies to unknown step {step_id!r}")

    produced: set[str] = {"goal.md"}
    for step in steps:
        missing = [c for c in step.consumes if c not in produced]
        if missing:
            raise KindError(f"{source}: step {step.id!r} consumes {missing} before any step produces it")
        produced |= set(step.produces)
    if data["deliverable"] not in produced or data["statements"] not in produced:
        raise KindError(f"{source}: deliverable and statements must be produced by some step")

    reviews: list[Review] = []
    for raw in data.get("decisions") or []:
        if isinstance(raw, str):
            if raw not in ("D0", "D-final"):
                raise KindError(f"{source}: decision {raw!r} needs `after`; D0 and D-final are always raised")
            continue
        review = decode(Review, raw)
        if review.after not in ids or review.after == "spec":
            raise KindError(f"{source}: decision {review.id!r} is after unknown step {review.after!r}")
        if review.id in ("D0", "D-final") or not review.id.startswith("D-"):
            raise KindError(f"{source}: intermediate decision ids look like D-<name>, got {review.id!r}")
        reviews.append(review)

    kind = Kind(
        kind=data["kind"],
        title=data["title"],
        deliverable=data["deliverable"],
        statements=data["statements"],
        steps=steps,
        gates=gates,
        formats=list(data.get("formats", ["md"])),
        budget=decode(Budget, data.get("budget", {})),
        adaptivity=decode(Adaptivity, data.get("adaptivity", {})),
        decisions=reviews,
        source=source,
    )
    return kind
