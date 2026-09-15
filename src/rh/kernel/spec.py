"""Success Spec: the criteria a Run is verified against.

Derived by the ``spec`` step from the Goal, reviewed at D0. A criterion
without a ground is not a criterion; a source or computation criterion
that no gate can check is refused before D0 is raised.
"""

from __future__ import annotations

import yaml

from rh.kernel.gates import KERNEL_GATES
from rh.kernel.kinds import Kind
from rh.kernel.records import Budget, Criterion, Executor, Ground, Layer, Step, SuccessSpec, decode, encode
from rh.kernel.run import SPEC_FILE

SPEC_SCHEMA = "rh.success_spec/1"


class SpecError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def parse_spec(text: str, default_budget: Budget) -> SuccessSpec:
    data = yaml.safe_load(text)
    problems: list[str] = []
    if not isinstance(data, dict):
        raise SpecError(["success_spec.yaml must be a mapping"])
    if data.get("schema") != SPEC_SCHEMA:
        problems.append(f"schema must be {SPEC_SCHEMA}")
    raw_criteria = data.get("criteria")
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise SpecError(problems + ["criteria must be a non-empty list"])
    criteria: list[Criterion] = []
    for i, raw in enumerate(raw_criteria):
        if not isinstance(raw, dict):
            problems.append(f"criteria[{i}]: must be a mapping")
            continue
        try:
            criteria.append(decode(Criterion, {"layer": _default_layer(raw), **raw}))
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"criteria[{i}]: {exc}")
    raw_budget = data.get("budget") or {}
    if not isinstance(raw_budget, dict):
        problems.append("budget must be a mapping")
        raw_budget = {}
    try:
        budget = decode(Budget, {**encode(default_budget), **raw_budget})
    except TypeError as exc:
        problems.append(f"budget: {exc}")
        budget = default_budget
    drift = data.get("drift") or []
    if not isinstance(drift, list):
        problems.append("drift must be a list")
        drift = []
    if problems:
        raise SpecError(problems)
    return SuccessSpec(criteria=criteria, scope=str(data.get("scope", "")), drift=[str(d) for d in drift], budget=budget)


def _default_layer(raw: dict) -> str:
    return "quality" if raw.get("ground") == "human" else "contract"


def bind(spec: SuccessSpec, kind: Kind) -> list[str]:
    """Bind every criterion to the gates that serve it. Returns problems."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in spec.criteria:
        if c.id in seen:
            problems.append(f"{c.id}: duplicate criterion id")
        seen.add(c.id)
        if not c.text.strip():
            problems.append(f"{c.id}: empty text")
        human = c.ground is Ground.HUMAN
        if human != (c.layer is Layer.QUALITY):
            problems.append(f"{c.id}: ground=human iff layer=quality (got {c.ground.value}/{c.layer.value})")
        c.gates = [] if human else [g.id for g in kind.gates_serving(c.kind)]
        if not human and not c.gates:
            problems.append(f"{c.id}: no gate in kind {kind.kind!r} can check criterion kind {c.kind!r}")
        if not human and not any(c.kind in s.serves for s in kind.steps):
            problems.append(f"{c.id}: no step in kind {kind.kind!r} serves criterion kind {c.kind!r}")
    bound = {g for c in spec.criteria for g in c.gates}
    for gate in kind.gates:
        if gate.executor is Executor.KERNEL and KERNEL_GATES[gate.id].required and gate.id not in bound:
            kinds = " or ".join(gate.serves)
            problems.append(f"kernel gate {gate.id!r} is unbound: add a criterion of kind {kinds}")
    for key in ("passes_total", "passes_per_gate", "stall_passes"):
        if getattr(spec.budget, key) < 1:
            problems.append(f"budget.{key} must be >= 1")
    return problems


def load(text: str, kind: Kind) -> tuple[list[str], SuccessSpec | None]:
    """Parse and bind ``success_spec.yaml`` text: ``(problems, spec)``; the spec is ``None`` if it does not parse."""
    try:
        spec = parse_spec(text, kind.budget)
    except SpecError as exc:
        return exc.problems, None
    except yaml.YAMLError as exc:
        return [f"{SPEC_FILE} is not valid YAML: {exc}"], None
    return bind(spec, kind), spec


def criteria_for_gate(spec: SuccessSpec | None, gate_id: str) -> list[Criterion]:
    """The criteria bound to ``gate_id``: what a prover judges and a kernel gate is run for."""
    return [c for c in spec.criteria if gate_id in c.gates] if spec else []


def criteria_for_step(spec: SuccessSpec | None, step: Step) -> list[Criterion]:
    """The criteria whose kind ``step`` serves: what a producer packet carries."""
    return [c for c in spec.criteria if c.kind in step.serves] if spec else []


def dump_spec(spec: SuccessSpec) -> str:
    return yaml.safe_dump(encode(spec), sort_keys=False, allow_unicode=True)
