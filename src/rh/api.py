"""One surface: ``start``, ``continue``, ``decide``, ``inspect`` (plus plan ops,
``escalate`` and the maintainers' ``lessons``).

The agent drives; the harness referees. Every call runs inside one
transaction on ``run.json`` and returns an ``Outcome`` that says exactly
what is expected next: a packet to perform, a Decision to answer, or
nothing because the Run has ended.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

import yaml

from rh.kernel import artifact, decisions, faults, lessons, loop, spec as specmod, steps
from rh.kernel.evidence import EvidenceCorrupt
from rh.kernel.gates import KERNEL_GATES, GateContext, GateResultInvalid, result_text, validate_agent_result
from rh.kernel.kinds import KINDS_DIR, Kind, KindError, load_kind
from rh.kernel.records import (
    BasisEntry,
    Decision,
    DecisionOutcome,
    Executor,
    Fault,
    GateDecl,
    GateResult,
    Goal,
    Ground,
    Pass,
    PassStatus,
    PlanOp,
    Role,
    RunState,
    RunStatus,
    Step,
    StepStatus,
    Stop,
    StopReason,
    Verdict,
    decode,
    encode,
)
from rh.kernel.run import GATE_RESULT_FILE, GOAL_FILE, SPEC_FILE, Workspace, new_run_id, write_json
from rh.kernel.skills import SkillLibrary, default_skills_root


class OutcomeKind(str, Enum):
    NEEDS_DECISION = "NEEDS_DECISION"
    BLOCKED = "BLOCKED"
    PROGRESSED = "PROGRESSED"
    COMPLETED = "COMPLETED"


@dataclass
class Outcome:
    kind: OutcomeKind
    run_id: str
    message: str
    packet: str | None = None  # path of the packet to perform next
    decision: dict | None = None
    stop: dict | None = None
    artifact: dict | None = None

    def to_dict(self) -> dict:
        return encode(self)


class HarnessError(RuntimeError):
    pass


def default_project() -> Path:
    return default_skills_root().parent.parent


ENDED = (RunStatus.COMPLETED, RunStatus.ABANDONED)


class Harness:
    def __init__(
        self,
        workspace: Path | str,
        *,
        skills_root: Path | None = None,
        kinds_dir: Path = KINDS_DIR,
        project: Path | None = None,
    ):
        self.ws = Workspace(Path(workspace))
        self.skills = SkillLibrary(skills_root)
        self.kinds_dir = kinds_dir
        self.project = Path(project) if project else default_project()

    # ------------------------------------------------------------------ surface

    def start(self, goal_text: str, kind_name: str, fmt: str = "md") -> Outcome:
        if self.ws.exists():
            raise HarnessError(f"a Run already exists at {self.ws.root}; use `rh continue`")
        kind = load_kind(kind_name, self.kinds_dir)
        if fmt not in kind.formats:
            raise HarnessError(f"kind {kind.kind!r} delivers {', '.join(kind.formats)}, not {fmt!r}")
        if not goal_text.strip():
            raise HarnessError("the Goal is empty")
        self._check_skills(kind)
        state = RunState(run_id=new_run_id(kind.kind), kind=kind.kind, goal=Goal(goal_text), plan=kind.plan(), format=fmt, budget=kind.budget)
        self.ws.init()
        state.goal.hash = self.ws.evidence.put_text(goal_text, GOAL_FILE, "goal").hash
        (self.ws.root / GOAL_FILE).write_text(goal_text, encoding="utf-8")
        self.ws.create(state)
        self.ws.log("run.started", run_id=state.run_id, kind=kind.kind)
        with self.ws.transaction() as state:
            return self._advance(state, kind)

    def continue_(self) -> Outcome:
        with self.ws.transaction() as state:
            kind = self._kind(state)
            if state.status in ENDED:
                return self._ended(state)
            pending = state.pending_decision()
            if pending is not None:
                changed = decisions.changed_basis(self.ws, pending, kind)
                return self._reviewed_changed(state, kind, pending, changed) if changed else self._await(state, pending)
            current = self._open_pass(state)
            if current is not None and current.closed_at is None:
                return self._take_back(state, kind, current)
            return self._advance(state, kind)

    def decide(
        self,
        decision_id: str,
        outcome: str,
        *,
        reason: str | None = None,
        criterion: str | None = None,
        extend: int | None = None,
        by: str | None = None,
    ) -> Outcome:
        with self.ws.transaction() as state:
            kind = self._kind(state)
            decision = state.decision(decision_id)
            if decision is None:
                raise HarnessError(f"no Decision {decision_id!r} in this Run")
            if decision.pending:
                changed = decisions.changed_basis(self.ws, decision, kind)
                if changed:
                    return self._reviewed_changed(state, kind, decision, changed)
            try:
                answer = DecisionOutcome(outcome)
            except ValueError as exc:
                raise HarnessError(f"unknown outcome {outcome!r}") from exc
            try:
                decisions.resolve(state, decision, answer, reason=reason, criterion=criterion, by=by)
            except decisions.DecisionError as exc:
                raise HarnessError(str(exc)) from exc
            self._project_decision(decision)
            self.ws.log("decision.answered", decision=decision_id, outcome=answer.value, reason=reason, criterion=criterion)
            if decision_id.startswith(decisions.D0):
                return self._after_review(state, kind, decision, "spec")
            if decision_id.startswith(decisions.D_FINAL):
                return self._after_d_final(state, kind, decision)
            review = next((r for r in kind.decisions if decision_id.startswith(r.id)), None)
            if review is not None:
                return self._after_review(state, kind, decision, review.after)
            return self._after_stop_decision(state, kind, decision, extend or 0)

    def inspect(self) -> dict:
        state = self.ws.load()
        kind = self._kind(state)
        pending = state.pending_decision()
        current = self._open_pass(state)
        return {
            "run_id": state.run_id,
            "kind": state.kind,
            "status": state.status.value,
            "version": state.version,
            "workspace": str(self.ws.root),
            "goal": state.goal.text.strip(),
            "budget": {**encode(state.budget), "passes_used": state.passes_used},
            "stop": encode(state.stop),
            "pending_decision": encode(pending),
            "reviewed_changed": decisions.changed_basis(self.ws, pending, kind) if pending else [],
            "pending_pass": None
            if current is None
            else {"id": current.id, "role": current.role.value, "gate": current.gate, "packet": str(self._packet_path(current))},
            "plan": [
                {"step": s.id, "skill": s.skill, "status": s.status.value, "admitted_pass": s.admitted_pass, "serves": s.serves}
                for s in state.plan.steps
            ],
            "plan_ops": [encode(op) for op in state.plan.ops],
            "criteria": [encode(c) for c in state.spec.criteria] if state.spec else [],
            "gates": [
                {"step": r.step, "gate": r.gate, "pass_id": r.pass_id, "verdict": r.verdict.value, "score": r.score, "executor": r.executor.value}
                for r in _latest_results(state)
            ],
            "open_faults": [encode(f) for f in state.open_faults()],
            "decisions": [{"id": d.id, "outcome": encode(d.outcome), "stale": d.stale, "reason": d.reason} for d in state.decisions],
            "artifact": state.artifact,
            "integrity": artifact.reverify(self.ws, state),
        }

    def plan_skip(self, step_id: str) -> Outcome:
        with self.ws.transaction() as state:
            kind = self._kind(state)
            step = self._plan_step(state, step_id)
            if step_id not in kind.adaptivity.skip or step.fixed or step_id == kind.artifact_step().id:
                raise HarnessError(f"kind {kind.kind!r} does not allow skipping {step_id!r}")
            if step.status is not StepStatus.PENDING or state.passes_for(step_id):
                raise HarnessError(f"{step_id!r} has already been worked; it cannot be skipped")
            remaining = [s for s in state.plan.active() if s.id != step_id]
            for name in _unserved_kinds(state, remaining):
                raise HarnessError(f"skipping {step_id!r} leaves criterion kind {name!r} with no step serving it")
            step.status = StepStatus.SKIPPED
            self._record_op(state, PlanOp(op="skip", step=step_id))
            return self._resume(state, kind, f"skipped {step_id}")

    def plan_add(self, step_yaml: str) -> Outcome:
        with self.ws.transaction() as state:
            kind = self._kind(state)
            if not kind.adaptivity.add:
                raise HarnessError(f"kind {kind.kind!r} does not allow adding steps")
            raw = yaml.safe_load(step_yaml) or {}
            after = raw.pop("after", None)
            try:
                step = decode(Step, {"fixed": False, **raw})
            except (KeyError, TypeError, ValueError) as exc:
                raise HarnessError(f"invalid step: {exc}") from exc
            if any(s.id == step.id for s in state.plan.steps):
                raise HarnessError(f"step id {step.id!r} is taken")
            if not self.skills.has(step.skill):
                raise HarnessError(f"Skill {step.skill!r} not found")
            position = len(state.plan.steps) - 1
            if after is not None:
                position = [s.id for s in state.plan.steps].index(self._plan_step(state, after).id) + 1
            produced = {GOAL_FILE, SPEC_FILE} | {o for s in state.plan.steps[:position] for o in s.produces}
            missing = [c for c in step.consumes if c not in produced]
            if missing:
                raise HarnessError(f"step {step.id!r} consumes {missing} that no earlier step produces")
            state.plan.steps.insert(position, step)
            self._record_op(state, PlanOp(op="add", step=step.id, detail={"after": after, "skill": step.skill}))
            return self._resume(state, kind, f"added {step.id}")

    def escalate(self, reason: str) -> Outcome:
        if not reason.strip():
            raise HarnessError("escalation needs a reason")
        with self.ws.transaction() as state:
            self._kind(state)  # refuse to act on a Run whose kind no longer loads
            if state.status is not RunStatus.RUNNING:
                raise HarnessError(f"the Run is {state.status.value}; nothing to escalate")
            current = self._open_pass(state)  # the escalation's basis: the latest outputs of the step in progress
            basis = decisions.latest_basis(state, current.step) if current else decisions.spec_basis(state)
            prompt = f"The agent escalated: {reason.strip()} Extend to resume, revise the Success Spec, or abandon."
            decision = self._stop(state, StopReason.ESCALATED, "D-escalated", prompt, basis, pass_id=state.pending_pass)
            self.ws.log("run.escalated", reason=reason)
            return self._await(state, decision)

    # -------------------------------------------------------------- lessons

    def lessons_list(self) -> list[dict]:
        return lessons.list_lessons(self.project)

    def lesson(self, run_id: str) -> dict:
        return lessons.load_lesson(self.project, run_id)

    # ----------------------------------------------------------- transitions

    def _advance(self, state: RunState, kind: Kind) -> Outcome:
        """Hand out the next producer packet, or raise D-final when every step is admitted."""
        pending = state.pending_decision()
        if pending is not None:
            return self._await(state, pending)
        for step in state.plan.active():
            if step.status is StepStatus.PENDING and steps.inputs_ready(state, step):
                return self._progressed(state, self._open(state, kind, step, Role.PRODUCER), f"step {step.id}: perform the packet")
        left = [s.id for s in state.plan.active() if s.status is StepStatus.PENDING]
        if left:
            raise HarnessError(f"steps {left} wait on inputs no step produces")
        uncovered = _coverage_problems(state, kind)
        if uncovered:
            return self._exhausted(state, "coverage", "; ".join(uncovered), pass_id=None, basis=decisions.spec_basis(state))
        state.artifact = artifact.assemble(self.ws, state, kind)
        state.stop = Stop(StopReason.CONVERGED)
        decision = self._ask(
            state,
            decisions.D_FINAL,
            "Every bound gate passed. Review the Artifact and its proof pack; accept, or reject naming the criterion that fails.",
            decisions.artifact_basis(state, kind),
        )
        self.ws.log("run.converged", artifact=state.artifact)
        return self._await(state, decision)

    def _take_back(self, state: RunState, kind: Kind, pass_: Pass) -> Outcome:
        """The agent finished a packet: hash its outputs into Evidence, then verify or refuse."""
        step = state.plan.get(pass_.step)
        prover = pass_.role is Role.PROVER
        problems = steps.close_pass(self.ws, state, pass_, [GATE_RESULT_FILE] if prover else step.produces)
        state.pending_pass = None
        if problems:
            pass_.status = PassStatus.FAILED
            if prover:
                return self._prover_refused(state, kind, pass_, problems)
            return self._raise_fault(state, kind, faults.INTEGRITY_GATE, step.id, "; ".join(problems), pass_id=pass_.id)
        if not prover:
            return self._verify(state, kind, pass_)
        decl = kind.gate(pass_.gate)
        checked = state.get_pass(pass_.checked)
        try:
            result = validate_agent_result(
                self.ws.evidence.get(pass_.outputs[GATE_RESULT_FILE]),
                decl,
                pass_,
                checked,
                specmod.criteria_for_gate(state.spec, decl.id),
                self.ws.evidence,
                self.skills.load(decl.skill),
                self.skills.load(state.plan.get(checked.step).skill),
                inputs=steps.given_hashes(state, pass_),
            )
        except GateResultInvalid as exc:
            pass_.status = PassStatus.FAILED
            return self._prover_refused(state, kind, pass_, exc.problems)
        pass_.status = PassStatus.VERIFIED
        self._record_result(state, result, produced_by=pass_.id)
        return self._verify(state, kind, checked)

    def _prover_refused(self, state: RunState, kind: Kind, pass_: Pass, problems: list[str]) -> Outcome:
        """A prover produced no admissible GateResult: record it and re-schedule the gate, up to the per-gate budget."""
        checked = state.get_pass(pass_.checked)
        refused = sum(1 for p in state.passes if p.role is Role.PROVER and p.gate == pass_.gate and p.checked == checked.id and p.status is PassStatus.FAILED)
        write_json(self.ws.gates / f"{checked.id}.{pass_.gate}.refused-{refused}.json", {"pass_id": pass_.id, "problems": problems})
        self.ws.log("gate.refused", gate=pass_.gate, pass_id=pass_.id, problems=problems)
        why = "; ".join(problems)
        if refused >= state.budget.passes_per_gate:
            message = f"prover for {pass_.gate!r} produced no admissible GateResult in {refused} passes: {why}"
            return self._exhausted(state, pass_.gate, message, pass_id=checked.id, basis=decisions.outputs_basis(checked))
        retry = self._open(state, kind, state.plan.get(checked.step), Role.PROVER, gate=kind.gate(pass_.gate), checked=checked)
        return self._progressed(state, retry, f"GateResult refused ({why}); prove {pass_.gate} again")

    def _verify(self, state: RunState, kind: Kind, checked: Pass) -> Outcome:
        """Run the kernel gates bound to the step, then schedule its agent gates one prover at a time; admit when all agree."""
        step = state.plan.get(checked.step)
        verifying_spec = state.spec
        if step.id == "spec":
            problems, verifying_spec = specmod.load(self.ws.evidence.get_text(checked.outputs[SPEC_FILE]), kind)
            if problems:
                return self._admit(state, kind, checked)  # spec-valid routes malformed criteria back to repair
        have = {r.gate for r in state.results_for(checked.id)}
        todo = [g for g in kind.gates_for(step.id) if g.id not in have and specmod.criteria_for_gate(verifying_spec, g.id)
                and (step.id != "spec" or g.executor is Executor.KERNEL)]
        kernel_todo = [g for g in todo if g.executor is Executor.KERNEL]
        if kernel_todo:
            ctx = GateContext(
                step=step,
                pass_=checked,
                outputs=steps.output_bytes(self.ws, checked),
                criteria=[],
                store=self.ws.evidence,
                producer=self.skills.load(step.skill),
                deliverable=kind.deliverable,
                statements=kind.statements,
                inputs=steps.given_hashes(state, checked),
            )
            for decl in kernel_todo:
                result = KERNEL_GATES[decl.id].run(replace(ctx, criteria=specmod.criteria_for_gate(verifying_spec, decl.id)))
                self._record_result(state, result, produced_by="kernel")
            failing = [r for r in state.results_for(checked.id) if r.verdict is Verdict.FAIL and r.executor is Executor.KERNEL]
            if failing:
                return self._fail(state, kind, checked, failing)  # the cheap, deterministic check is answered first
        for decl in todo:
            if decl.executor is Executor.AGENT:
                prover = self._open(state, kind, step, Role.PROVER, gate=decl, checked=checked)
                return self._progressed(state, prover, f"prove gate {decl.id} on {checked.id}")
        failing = [r for r in state.results_for(checked.id) if r.verdict is Verdict.FAIL]
        if failing:
            return self._fail(state, kind, checked, failing)
        return self._admit(state, kind, checked)

    def _fail(self, state: RunState, kind: Kind, checked: Pass, failing: list[GateResult]) -> Outcome:
        """One Fault per finding of every failing result, each routed to the step it implicates."""
        new_faults: list[Fault] = []
        for result in failing:
            batch = faults.from_result(state, self.ws.evidence, result, kind.gate(result.gate))
            state.faults.extend(batch)
            new_faults.extend(batch)
        checked.status = PassStatus.FAILED
        return self._after_faults(state, kind, new_faults, failing[0].gate)

    def _admit(self, state: RunState, kind: Kind, pass_: Pass) -> Outcome:
        """Evidence, gate results and Artifact agree: the step leaves the Loop; what consumed it must be redone."""
        step = state.plan.get(pass_.step)
        pass_.status = PassStatus.VERIFIED
        step.status = StepStatus.ADMITTED
        step.admitted_pass = pass_.id
        for fault in state.open_faults():
            if fault.step == step.id:
                fault.resolved = True
                self._project_fault(fault)
        for downstream in state.plan.downstream(step.id):
            if downstream.status is StepStatus.ADMITTED:
                downstream.status = StepStatus.PENDING
                downstream.admitted_pass = None
                self.ws.log("step.invalidated", step=downstream.id, because=step.id)
        self.ws.log("step.admitted", step=step.id, pass_id=pass_.id)
        if step.id == "spec":
            return self._bind_spec(state, kind, pass_)
        review = kind.review_after(step.id)
        if review is None:
            return self._advance(state, kind)
        prompt = review.prompt or f"Step {step.id} is admitted. Review its outputs; accept to continue, or reject with a reason."
        return self._await(state, self._ask(state, review.id, prompt, decisions.outputs_basis(pass_)))

    def _bind_spec(self, state: RunState, kind: Kind, pass_: Pass) -> Outcome:
        problems, parsed = specmod.load(self.ws.evidence.get_text(pass_.outputs[SPEC_FILE]), kind)
        if problems:
            step = state.plan.get("spec")
            step.status = StepStatus.PENDING
            step.admitted_pass = None
            return self._raise_fault(state, kind, faults.SPEC_GATE, "spec", "; ".join(problems), pass_id=pass_.id)
        return self._raise_d0(state, parsed, produced_by=pass_.id)

    def _raise_d0(self, state: RunState, parsed, *, produced_by: str) -> Outcome:
        state.spec = parsed
        state.budget = parsed.budget
        canonical = specmod.dump_spec(parsed)
        state.spec_hash = self.ws.evidence.put_text(canonical, SPEC_FILE, produced_by).hash
        (self.ws.root / SPEC_FILE).write_text(canonical, encoding="utf-8")
        decision = self._ask(
            state,
            decisions.D0,
            "Review the Success Spec against the Goal: are these the criteria, with these grounds, that would make the deliverable count? Accept, or reject with a reason.",
            decisions.spec_basis(state),
        )
        self.ws.log("spec.bound", spec_hash=state.spec_hash, criteria=len(parsed.criteria))
        return self._await(state, decision)

    def _raise_fault(self, state: RunState, kind: Kind, gate: str, step_id: str, message: str, *, pass_id: str = "", ground: Ground = Ground.COMPUTATION, criterion: str | None = None) -> Outcome:
        """One Fault the kernel or a human raised outside a GateResult, then the Loop's answer to it."""
        fault = faults.fault(state, gate, step_id, message, ground=ground, criterion=criterion, pass_id=pass_id)
        state.faults.append(fault)
        return self._after_faults(state, kind, [fault], gate)

    def _after_faults(self, state: RunState, kind: Kind, new_faults: list[Fault], gate_id: str) -> Outcome:
        """Record the Faults, then repair the earliest implicated step or stop if the Loop is exhausted."""
        for fault in new_faults:
            self._project_fault(fault)
            self.ws.log("fault.raised", fault=fault.id, gate=fault.gate, step=fault.step, criterion=fault.criterion)
        target = faults.earliest_step(state, [f.step for f in new_faults])
        why = loop.exhaustion(state, new_faults[0].checked_step, gate_id)
        if why is not None:
            return self._exhausted(state, gate_id, why, pass_id=new_faults[0].pass_id or None, basis=decisions.latest_basis(state, target))
        return self._repair(state, kind, target, f"repair {target}")

    def _repair(self, state: RunState, kind: Kind, target: str, why: str) -> Outcome:
        """Open a repair pass on ``target`` carrying the open Faults routed to it, and only those."""
        mine = [f for f in state.open_faults() if f.step == target]
        repair = self._open(state, kind, state.plan.get(target), Role.REPAIR, faults=mine)
        return self._progressed(state, repair, f"{why} ({'; '.join(f'{f.id} {f.gate}' for f in mine)})")

    def _exhausted(self, state: RunState, gate_id: str, why: str, *, pass_id: str | None, basis: list[BasisEntry]) -> Outcome:
        prompt = f"The Loop is exhausted: {why}. Extend the budget, revise the Success Spec, or abandon the Run."
        decision = self._stop(state, StopReason.EXHAUSTED, f"D-{gate_id}", prompt, basis, pass_id=pass_id, gate=gate_id)
        self.ws.log("run.exhausted", gate=gate_id, why=why)
        return self._await(state, decision)

    # ------------------------------------------------------------ decisions

    def _after_review(self, state: RunState, kind: Kind, decision: Decision, step_id: str) -> Outcome:
        """D0 or a kind's intermediate Decision: accept advances; reject re-enters the Loop as a human Fault on ``step_id``."""
        if decision.outcome is DecisionOutcome.ACCEPT:
            return self._advance(state, kind)
        return self._human_repair(state, kind, step_id, decision)

    def _after_d_final(self, state: RunState, kind: Kind, decision: Decision) -> Outcome:
        if decision.outcome is DecisionOutcome.ACCEPT:
            state.status = RunStatus.COMPLETED
            state.stop = Stop(StopReason.CONVERGED)
            return self._end(state, kind)
        target = kind.artifact_step().id
        if decision.criterion and state.spec:
            wanted = next((c.kind for c in state.spec.criteria if c.id == decision.criterion), None)
            serving = [s.id for s in state.plan.active() if wanted in s.serves and s.status is StepStatus.ADMITTED]
            if serving:
                target = serving[-1]
        state.stop = None
        return self._human_repair(state, kind, target, decision)

    def _after_stop_decision(self, state: RunState, kind: Kind, decision: Decision, extend: int) -> Outcome:
        """An exhausted or escalated Loop was answered: abandon ends the Run, extend resumes it, revise re-runs ``spec``."""
        if decision.outcome is DecisionOutcome.ABANDON:
            state.status = RunStatus.ABANDONED
            state.stop = state.stop or Stop(StopReason.ESCALATED)
            return self._end(state, kind)
        state.status = RunStatus.RUNNING
        state.stop = None
        state.budget_epoch = len(state.passes)  # per-gate and stall counters restart here
        if decision.outcome is DecisionOutcome.REVISE:
            state.budget.passes_total = max(state.budget.passes_total, state.passes_used + 1)
            return self._human_repair(state, kind, "spec", decision)
        state.budget.passes_total += max(0, extend)
        if state.passes_used >= state.budget.passes_total:
            raise HarnessError(f"extend by at least {state.passes_used - state.budget.passes_total + 1} passes to continue")
        return self._resume(state, kind, "budget extended")

    def _human_repair(self, state: RunState, kind: Kind, target: str, decision: Decision) -> Outcome:
        """A rejected Decision is a Fault whose ground is Human, routed to ``target``; what depends on it is reopened."""
        state.status = RunStatus.RUNNING
        step = state.plan.get(target)
        for affected in [step, *state.plan.downstream(target)]:
            if affected.status is StepStatus.ADMITTED or affected is step:
                affected.status = StepStatus.PENDING
                affected.admitted_pass = None
        return self._raise_fault(state, kind, faults.HUMAN_GATE, target, decision.reason or "", ground=Ground.HUMAN, criterion=decision.criterion)

    def _reviewed_changed(self, state: RunState, kind: Kind, decision: Decision, changed: list[str]) -> Outcome:
        """A reviewed projection was edited: a spec edit under D0 is a revision, any other edit is restored from Evidence."""
        if decision.id.startswith(decisions.D0) and SPEC_FILE in changed:
            problems, parsed = specmod.load((self.ws.root / SPEC_FILE).read_text(encoding="utf-8"), kind)
            if problems:
                return self._await(state, decision, message=f"{decision.id} cannot be answered: {SPEC_FILE} was edited but does not validate ({'; '.join(problems)}). Fix or restore the file.")
            decision.stale = True
            self._project_decision(decision)
            self.ws.log("decision.stale", decision=decision.id, changed=changed)
            outcome = self._raise_d0(state, parsed, produced_by="human")
            return replace(outcome, message=f"{decision.id} went stale because {SPEC_FILE} was edited; the edit was taken as a revision and a new Decision was raised.")
        for name in changed:
            entry = next(e for e in decision.basis if e.name == name)
            self.ws.evidence.link_into(entry.hash, self.ws.root / decisions.projections(kind)[name])
        self.ws.log("projection.restored", decision=decision.id, changed=changed)
        return self._await(state, decision, message=f"{', '.join(changed)} had been edited outside the harness; restored from Evidence. {decision.prompt}")

    def _end(self, state: RunState, kind: Kind) -> Outcome:
        """The Run has ended: assemble the final proof pack, distill its Lesson, report."""
        try:
            state.artifact = artifact.assemble(self.ws, state, kind)
        except artifact.ArtifactError:
            pass
        path = lessons.distill(self.ws, state, kind, self.project)
        self.ws.log("lesson.distilled", path=str(path))
        return self._ended(state)

    # -------------------------------------------------------------- outcomes

    def _progressed(self, state: RunState, pass_: Pass, message: str) -> Outcome:
        return Outcome(OutcomeKind.PROGRESSED, state.run_id, message, packet=str(self._packet_path(pass_)))

    def _await(self, state: RunState, decision: Decision, *, message: str | None = None) -> Outcome:
        kind = OutcomeKind.BLOCKED if state.status is RunStatus.BLOCKED else OutcomeKind.NEEDS_DECISION
        return Outcome(kind, state.run_id, message or decision.prompt, decision=encode(decision), stop=encode(state.stop), artifact=state.artifact or None)

    def _ended(self, state: RunState) -> Outcome:
        verb = "completed" if state.status is RunStatus.COMPLETED else "abandoned"
        return Outcome(OutcomeKind.COMPLETED, state.run_id, f"Run {verb}", stop=encode(state.stop), artifact=state.artifact or None)

    def _ask(self, state: RunState, base: str, prompt: str, basis: list[BasisEntry]) -> Decision:
        """Raise and project a review Decision (accept / reject)."""
        decision = decisions.raise_decision(state, base, prompt, basis, decisions.REVIEW_OPTIONS)
        self._project_decision(decision)
        return decision

    def _stop(self, state: RunState, reason: StopReason, base: str, prompt: str, basis: list[BasisEntry], *, pass_id: str | None, gate: str | None = None) -> Decision:
        """Block the Run on a stop Decision (extend / revise / abandon) and record why the Loop stopped."""
        state.status = RunStatus.BLOCKED
        state.stop = Stop(reason, pass_id=pass_id, gate=gate)
        decision = decisions.raise_decision(state, base, prompt, basis, decisions.STOP_OPTIONS)
        self._project_decision(decision)
        return decision

    def _resume(self, state: RunState, kind: Kind, note: str) -> Outcome:
        """Pick the Loop up where it stands: the pending Decision, the open packet, the open Faults, or the next step."""
        if state.status in ENDED:
            return self._ended(state)
        pending = state.pending_decision()
        if pending is not None:
            return self._await(state, pending)
        current = self._open_pass(state)
        if current is not None:
            return self._progressed(state, current, f"{note}; perform the open packet")
        open_faults = state.open_faults()
        if open_faults:
            target = faults.earliest_step(state, [f.step for f in open_faults])
            return self._repair(state, kind, target, f"{note}; repair {target}")
        return self._advance(state, kind)

    # --------------------------------------------------------------- helpers

    def _kind(self, state: RunState) -> Kind:
        try:
            return load_kind(state.kind, self.kinds_dir)
        except KindError as exc:
            raise HarnessError(str(exc)) from exc

    def _check_skills(self, kind: Kind) -> None:
        for step in kind.steps:
            if not self.skills.has(step.skill):
                raise HarnessError(f"kind {kind.kind!r} step {step.id!r} names missing Skill {step.skill!r}")
        for gate in kind.gates:
            if gate.executor is not Executor.AGENT:
                continue
            if not self.skills.has(gate.skill):
                raise HarnessError(f"gate {gate.id!r} names missing prover Skill {gate.skill!r}")
            prover = self.skills.load(gate.skill)
            if prover.role != "prover":
                raise HarnessError(f"Skill {gate.skill!r} must declare `role: prover` to serve gate {gate.id!r}")
            for step in kind.steps:
                if gate.applies(step.id) and self.skills.load(step.skill).identity == prover.identity:
                    raise HarnessError(f"gate {gate.id!r} would let step {step.id!r} verify itself")

    def _open_pass(self, state: RunState) -> Pass | None:
        """The pass the agent is performing, if the pending one is still open."""
        current = state.get_pass(state.pending_pass) if state.pending_pass else None
        return current if current is not None and current.status is PassStatus.OPEN else None

    def _open(self, state: RunState, kind: Kind, step: Step, role: Role, *, gate: GateDecl | None = None, checked: Pass | None = None, faults: list[Fault] = ()) -> Pass:
        """Open a pass on ``step``: a prover follows the gate's Skill and carries its criteria; producers and repairs follow the step's."""
        skill = self.skills.load(gate.skill if gate else step.skill)
        criteria = specmod.criteria_for_gate(state.spec, gate.id) if gate else specmod.criteria_for_step(state.spec, step)
        return steps.open_pass(self.ws, state, kind, step, skill, role, criteria, gate=gate, checked=checked, faults=faults)

    def _plan_step(self, state: RunState, step_id: str) -> Step:
        try:
            return state.plan.get(step_id)
        except KeyError as exc:
            raise HarnessError(f"no step {step_id!r} in the plan") from exc

    def _record_op(self, state: RunState, op: PlanOp) -> None:
        state.plan.ops.append(op)
        self.ws.evidence.put_text(json.dumps(encode(op), ensure_ascii=False), f"plan-op:{op.op}:{op.step}", "agent")
        self.ws.log("plan.op", op=op.op, step=op.step)

    def _packet_path(self, pass_: Pass) -> Path:
        return self.ws.pass_dir(pass_.id) / "packet.md"

    def _record_result(self, state: RunState, result: GateResult, *, produced_by: str) -> None:
        """A GateResult is Evidence: hashed into the store before it counts."""
        name = f"gate_result:{result.gate}:{result.pass_id}"
        result.hash = self.ws.evidence.put_text(result_text(encode(result)), name, produced_by).hash
        state.gate_results.append(result)
        write_json(self.ws.gates / f"{result.pass_id}.{result.gate}.json", encode(result))
        self.ws.log("gate.result", gate=result.gate, pass_id=result.pass_id, verdict=result.verdict.value, score=result.score)

    def _project_fault(self, fault: Fault) -> None:
        write_json(self.ws.faults / f"{fault.id}.json", encode(fault))

    def _project_decision(self, decision: Decision) -> None:
        self.ws.decisions.mkdir(parents=True, exist_ok=True)
        (self.ws.decisions / f"{decision.id}.md").write_text(decisions.render(decision), encoding="utf-8")


# --- pure helpers -------------------------------------------------------------


def _latest_results(state: RunState) -> list[GateResult]:
    seen: set[tuple[str, str]] = set()
    out = []
    for r in reversed(state.gate_results):
        key = (r.step, r.gate)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return list(reversed(out))


def _unserved_kinds(state: RunState, remaining: list[Step]) -> list[str]:
    if state.spec is None:
        return []
    served = {k for s in remaining for k in s.serves}
    return sorted({c.kind for c in state.spec.criteria if c.gates and c.kind not in served})


def _coverage_problems(state: RunState, kind: Kind) -> list[str]:
    problems: list[str] = []
    if state.spec is None:
        return ["no Success Spec is bound"]
    for c in state.spec.criteria:
        if not c.gates:
            continue
        serving = [s for s in state.plan.active() if c.kind in s.serves and s.status is StepStatus.ADMITTED]
        if not serving:
            problems.append(f"{c.id}: no admitted step serves {c.kind!r}")
            continue
        results = [state.latest_result(s.id, g) for s in serving for g in c.gates if kind.gate(g).applies(s.id)]
        results = [r for r in results if r is not None]
        if not results:
            problems.append(f"{c.id}: no gate result for {c.kind!r}")
        elif any(r.verdict is Verdict.FAIL for r in results):
            problems.append(f"{c.id}: a bound gate is failing")
    try:
        state.plan.get(kind.artifact_step().id)
    except KeyError:
        problems.append(f"the artifact step {kind.artifact_step().id!r} is not in the plan")
    return problems


__all__ = ["Harness", "HarnessError", "Outcome", "OutcomeKind", "EvidenceCorrupt"]
