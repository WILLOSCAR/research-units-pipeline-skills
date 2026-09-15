"""Every record the kernel writes, in the story's vocabulary.

Records are plain dataclasses. ``encode`` / ``decode`` turn them into JSON
shapes; every top-level record carries ``schema: rh.<name>/1``.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- enumerations -----------------------------------------------------------


class Ground(str, Enum):
    SOURCE = "source"
    COMPUTATION = "computation"
    HUMAN = "human"


class Layer(str, Enum):
    INTEGRITY = "integrity"
    CONTRACT = "contract"
    QUALITY = "quality"


class GateKind(str, Enum):
    STRUCTURAL = "structural"
    GROUNDED = "grounded"
    CALIBRATED = "calibrated"


class Executor(str, Enum):
    KERNEL = "kernel"
    AGENT = "agent"


class Role(str, Enum):
    PRODUCER = "producer"
    PROVER = "prover"
    REPAIR = "repair"


class StepStatus(str, Enum):
    PENDING = "pending"
    ADMITTED = "admitted"
    SKIPPED = "skipped"


class PassStatus(str, Enum):
    OPEN = "open"
    VERIFIED = "verified"
    FAILED = "failed"


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class RunStatus(str, Enum):
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StopReason(str, Enum):
    CONVERGED = "converged"
    EXHAUSTED = "exhausted"
    ESCALATED = "escalated"


class DecisionOutcome(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    EXTEND = "extend"
    REVISE = "revise"
    ABANDON = "abandon"


class Relation(str, Enum):
    QUOTES = "quotes"
    CONDENSES = "condenses"
    INFERS = "infers"


# --- records ----------------------------------------------------------------


@dataclass
class Budget:
    passes_total: int = 24
    passes_per_gate: int = 3
    stall_passes: int = 2


@dataclass
class Goal:
    text: str
    constraints: dict[str, Any] = field(default_factory=dict)
    hash: str = ""


@dataclass
class Criterion:
    id: str
    text: str
    kind: str
    ground: Ground
    layer: Layer = Layer.CONTRACT
    gates: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuccessSpec:
    criteria: list[Criterion]
    scope: str = ""
    drift: list[str] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    schema: str = "rh.success_spec/1"


@dataclass
class Step:
    id: str
    skill: str
    consumes: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    serves: list[str] = field(default_factory=list)
    fixed: bool = False
    status: StepStatus = StepStatus.PENDING
    admitted_pass: str | None = None


@dataclass
class PlanOp:
    op: str
    step: str
    at: str = field(default_factory=now)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    steps: list[Step]
    ops: list[PlanOp] = field(default_factory=list)

    def get(self, step_id: str) -> Step:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(step_id)

    def active(self) -> list[Step]:
        return [s for s in self.steps if s.status is not StepStatus.SKIPPED]

    def producers_of(self, output: str) -> list[Step]:
        return [s for s in self.active() if output in s.produces]

    def upstream(self, step_id: str) -> list[Step]:
        """Active steps whose outputs feed ``step_id``, transitively, in plan order."""
        wanted = set(self.get(step_id).consumes)
        found: list[Step] = []
        for step in reversed(self.active()):
            if step.id == step_id:
                continue
            if wanted & set(step.produces):
                found.append(step)
                wanted |= set(step.consumes)
        return list(reversed(found))

    def downstream(self, step_id: str) -> list[Step]:
        """Active steps that consume ``step_id``'s outputs, transitively."""
        produced = set(self.get(step_id).produces)
        found: list[Step] = []
        for step in self.active():
            if step.id == step_id:
                continue
            if produced & set(step.consumes):
                found.append(step)
                produced |= set(step.produces)
        return found


@dataclass
class GateDecl:
    id: str
    kind: GateKind
    ground: Ground
    executor: Executor
    serves: list[str] = field(default_factory=list)
    applies_to: list[str] = field(default_factory=list)  # step ids, or ["all"]
    routing: str = "checked_step"
    skill: str | None = None
    calibration: dict[str, Any] = field(default_factory=lambda: {"status": "unmeasured"})

    def applies(self, step_id: str) -> bool:
        return "all" in self.applies_to or step_id in self.applies_to


@dataclass
class Finding:
    message: str
    evidence: list[str] = field(default_factory=list)
    statement: str | None = None
    criterion: str | None = None
    implicates: str | None = None  # an upstream step the prover blames; validated by routing


@dataclass
class GateResult:
    gate: str
    step: str
    pass_id: str
    verdict: Verdict
    criteria: list[str] = field(default_factory=list)
    score: float | None = None
    findings: list[Finding] = field(default_factory=list)
    produced_by: str = ""  # skill identity hash, or "kernel"
    prover_pass: str | None = None  # the prover pass that wrote it; None for kernel gates
    executor: Executor = Executor.KERNEL
    kind: GateKind = GateKind.STRUCTURAL
    ground: Ground = Ground.COMPUTATION
    calibration: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=now)
    hash: str = ""  # this result as Evidence (sha256 of its encoded JSON without this field)
    schema: str = "rh.gate_result/1"


@dataclass
class Fault:
    id: str
    gate: str
    criterion: str | None
    ground: Ground
    step: str  # implicated (earliest) step
    checked_step: str
    message: str
    evidence: list[str] = field(default_factory=list)
    pass_id: str = ""
    budget_remaining: int = 0
    resolved: bool = False
    at: str = field(default_factory=now)
    schema: str = "rh.fault/1"


@dataclass
class Pass:
    id: str
    step: str
    n: int
    role: Role
    gate: str | None = None
    checked: str | None = None  # the producer pass a prover pass judges
    faults: list[str] = field(default_factory=list)  # fault ids a repair pass answers
    context_id: str | None = None
    skill_identity: str = ""
    outputs: dict[str, str] = field(default_factory=dict)  # name -> hash
    status: PassStatus = PassStatus.OPEN
    opened_at: str = field(default_factory=now)
    closed_at: str | None = None


@dataclass
class BasisEntry:
    name: str
    hash: str


@dataclass
class Decision:
    id: str
    prompt: str
    basis: list[BasisEntry]
    options: list[DecisionOutcome]
    outcome: DecisionOutcome | None = None
    reason: str | None = None
    criterion: str | None = None
    by: str | None = None
    at: str | None = None
    stale: bool = False
    raised_at: str = field(default_factory=now)
    schema: str = "rh.decision/1"

    @property
    def pending(self) -> bool:
        return self.outcome is None and not self.stale


@dataclass
class Stop:
    reason: StopReason
    pass_id: str | None = None
    gate: str | None = None
    at: str = field(default_factory=now)


@dataclass
class RunState:
    run_id: str
    kind: str
    goal: Goal
    plan: Plan
    format: str = "md"
    status: RunStatus = RunStatus.RUNNING
    version: int = 0
    spec: SuccessSpec | None = None
    spec_hash: str | None = None
    passes: list[Pass] = field(default_factory=list)
    gate_results: list[GateResult] = field(default_factory=list)
    faults: list[Fault] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    pending_pass: str | None = None
    budget: Budget = field(default_factory=Budget)
    budget_epoch: int = 0  # index into passes; stall/per-gate counts restart here after --extend
    passes_used: int = 0
    stop: Stop | None = None
    artifact: dict[str, str] = field(default_factory=dict)  # name -> hash (deliverable, statements, proof_pack)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    schema: str = "rh.run/1"

    # -- lookups -------------------------------------------------------------

    def get_pass(self, pass_id: str) -> Pass:
        for p in self.passes:
            if p.id == pass_id:
                return p
        raise KeyError(pass_id)

    def passes_for(self, step_id: str) -> list[Pass]:
        return [p for p in self.passes if p.step == step_id]

    def pending_decision(self) -> Decision | None:
        for d in reversed(self.decisions):
            if d.pending:
                return d
        return None

    def decision(self, decision_id: str) -> Decision | None:
        for d in reversed(self.decisions):
            if d.id == decision_id:
                return d
        return None

    def open_faults(self) -> list[Fault]:
        return [f for f in self.faults if not f.resolved]

    def results_for(self, pass_id: str) -> list[GateResult]:
        return [r for r in self.gate_results if r.pass_id == pass_id]

    def latest_result(self, step_id: str, gate_id: str) -> GateResult | None:
        for r in reversed(self.gate_results):
            if r.step == step_id and r.gate == gate_id:
                return r
        return None

    def skill_identities(self) -> dict[str, str]:
        """Skill identity of every admitted step, by step id."""
        return {s.id: self.get_pass(s.admitted_pass).skill_identity for s in self.plan.steps if s.admitted_pass}


# --- codec ------------------------------------------------------------------


def encode(value: Any) -> Any:
    """Dataclass → JSON-ready shape. Enums become their values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


_SCALARS: dict[type, tuple[type, ...]] = {str: (str,), int: (int,), float: (int, float), bool: (bool,)}


def decode(hint: type[T], data: Any) -> T:
    """JSON shape → dataclass, following type hints for nesting.

    Strict about shape: a null where a list belongs, a string where a mapping
    belongs, or a non-integer budget raises ``TypeError`` so that callers
    refuse the record instead of carrying the defect into the Run.
    """
    origin = typing.get_origin(hint)
    if origin in (types.UnionType, typing.Union):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        if data is None:
            return None
        return decode(args[0], data) if len(args) == 1 else data
    if hint is Any:
        return data
    if data is None:
        raise TypeError(f"expected {_name(hint)}, got null")
    if origin is list:
        (item,) = typing.get_args(hint)
        if not isinstance(data, list):
            raise TypeError(f"expected a list of {_name(item)}, got {type(data).__name__}")
        return [decode(item, v) for v in data]
    if origin is dict:
        _, val = typing.get_args(hint)
        if not isinstance(data, dict):
            raise TypeError(f"expected a mapping, got {type(data).__name__}")
        return {str(k): decode(val, v) for k, v in data.items()}
    if isinstance(hint, type) and issubclass(hint, Enum):
        return hint(data)
    if dataclasses.is_dataclass(hint):
        if not isinstance(data, dict):
            raise TypeError(f"expected a {hint.__name__} mapping, got {type(data).__name__}")
        hints = typing.get_type_hints(hint)
        return hint(**{f.name: decode(hints[f.name], data[f.name]) for f in dataclasses.fields(hint) if f.name in data})
    if hint in _SCALARS:
        if isinstance(data, bool) and hint is not bool or not isinstance(data, _SCALARS[hint]):
            raise TypeError(f"expected {hint.__name__}, got {type(data).__name__}")
        return hint(data) if hint is float else data
    return data


def _name(hint: Any) -> str:
    return getattr(hint, "__name__", str(hint))
