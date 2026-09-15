"""Shared builders for the kernel tests.

A plain module (not a conftest) so the suite runs under ``--noconftest``.
Everything here speaks the story's vocabulary: Step, Pass, Gate, Decision,
Fault, Run.
"""

from __future__ import annotations

import json
from pathlib import Path

from rh.kernel.evidence import EvidenceStore
from rh.kernel.gates import STATEMENTS_SCHEMA, GateContext
from rh.kernel.records import (
    BasisEntry,
    Budget,
    Criterion,
    Decision,
    DecisionOutcome,
    Executor,
    Fault,
    Finding,
    GateKind,
    GateResult,
    Goal,
    Ground,
    Layer,
    Pass,
    PassStatus,
    Plan,
    PlanOp,
    Role,
    RunState,
    RunStatus,
    Step,
    StepStatus,
    Stop,
    StopReason,
    SuccessSpec,
    Verdict,
)
from rh.kernel.skills import Skill

PRODUCER_IDENTITY = "a" * 64
PROVER_IDENTITY = "b" * 64
T0 = "2026-09-12T10:00:00+00:00"
T1 = "2026-09-12T10:05:00+00:00"


# --- evidence / skills ---------------------------------------------------------


def make_store(root: Path) -> EvidenceStore:
    store = EvidenceStore(root / "evidence")
    store.init()
    return store


def make_skill(
    name: str = "brief-writer",
    identity: str = PRODUCER_IDENTITY,
    front: dict | None = None,
) -> Skill:
    """A Skill record built by hand; the path need not exist."""
    return Skill(name=name, path=Path("/skills") / name / "SKILL.md", identity=identity, front=dict(front or {}))


def write_skill(root: Path, name: str, front: str = "", body: str = "# Skill body\n") -> Path:
    """Write ``<root>/<name>/SKILL.md`` with optional YAML front matter text."""
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"---\n{front}---\n{body}" if front else body
    path.write_text(text, encoding="utf-8")
    return path


# --- plan / run state ------------------------------------------------------------


def four_step_plan(skip_curate: bool = True) -> Plan:
    """spec -> retrieve -> curate -> write, with ``curate`` skipped by default."""
    curate_status = StepStatus.SKIPPED if skip_curate else StepStatus.PENDING
    ops = [PlanOp("skip", "curate", at=T0, detail={"reason": "single-source Goal"})] if skip_curate else []
    return Plan(
        steps=[
            Step(
                "spec",
                "success-spec",
                consumes=["goal.md"],
                produces=["success_spec.yaml"],
                fixed=True,
                status=StepStatus.ADMITTED,
                admitted_pass="spec#1",
            ),
            Step(
                "retrieve",
                "arxiv-search",
                consumes=["success_spec.yaml"],
                produces=["papers_raw.jsonl"],
                serves=["coverage"],
                status=StepStatus.ADMITTED,
                admitted_pass="retrieve#1",
            ),
            Step(
                "curate",
                "dedupe-rank",
                consumes=["papers_raw.jsonl"],
                produces=["core_set.jsonl"],
                serves=["coverage"],
                status=curate_status,
            ),
            Step(
                "write",
                "brief-writer",
                consumes=["core_set.jsonl", "papers_raw.jsonl", "success_spec.yaml"],
                produces=["brief.md", "statements.json"],
                serves=["answers", "supported", "length"],
            ),
        ],
        ops=ops,
    )


def sample_spec() -> SuccessSpec:
    return SuccessSpec(
        criteria=[
            Criterion(
                "c-supported",
                "every statement cites a retrieved source",
                "supported",
                Ground.SOURCE,
                gates=["source-support"],
            ),
            Criterion(
                "c-length",
                "the brief stays under 800 words",
                "length",
                Ground.COMPUTATION,
                gates=["length-bound"],
                params={"max_words": 800},
            ),
            Criterion(
                "c-reads",
                "the brief reads as one argument",
                "quality",
                Ground.HUMAN,
                layer=Layer.QUALITY,
            ),
        ],
        scope="LLM agents for literature review, 2023-2026",
        drift=["general RAG surveys"],
        budget=Budget(passes_total=10, passes_per_gate=2, stall_passes=1),
    )


def sample_run_state() -> RunState:
    """A Run mid-Loop: one resolved Fault, one open Fault, one pending Decision."""
    return RunState(
        run_id="brief-20260912-100000-beef",
        kind="brief",
        goal=Goal(
            text="Survey LLM agents for literature review",
            constraints={"scope": "2023-2026", "sources": ["arxiv"], "budget": {"passes_total": 10}},
            hash="h-goal",
        ),
        plan=four_step_plan(),
        format="md",
        status=RunStatus.BLOCKED,
        version=7,
        spec=sample_spec(),
        spec_hash="h-spec",
        passes=[
            Pass(
                "spec#1",
                "spec",
                1,
                Role.PRODUCER,
                skill_identity=PRODUCER_IDENTITY,
                outputs={"success_spec.yaml": "h-spec"},
                status=PassStatus.VERIFIED,
                opened_at=T0,
                closed_at=T1,
            ),
            Pass(
                "write#1",
                "write",
                1,
                Role.PRODUCER,
                context_id="ctx-1",
                skill_identity=PRODUCER_IDENTITY,
                outputs={"brief.md": "h-brief-1", "statements.json": "h-stmts-1"},
                status=PassStatus.FAILED,
                opened_at=T0,
                closed_at=T1,
            ),
            Pass(
                "write#2",
                "write",
                2,
                Role.REPAIR,
                faults=["F1"],
                context_id="ctx-2",
                skill_identity=PRODUCER_IDENTITY,
                outputs={"brief.md": "h-brief-2", "statements.json": "h-stmts-2"},
                status=PassStatus.OPEN,
                opened_at=T1,
            ),
            Pass(
                "source-support#1",
                "write",
                1,
                Role.PROVER,
                gate="source-support",
                checked="write#2",
                context_id="ctx-3",
                skill_identity=PROVER_IDENTITY,
                outputs={"gate_result.json": "h-gr-1"},
                status=PassStatus.VERIFIED,
                opened_at=T1,
                closed_at=T1,
            ),
        ],
        gate_results=[
            GateResult(
                "length-bound",
                "write",
                "write#1",
                Verdict.FAIL,
                criteria=["c-length"],
                findings=[Finding("brief.md has 812 words, over 800", criterion="c-length")],
                produced_by="kernel",
                calibration={"status": "deterministic"},
                at=T0,
            ),
            GateResult(
                "length-bound",
                "write",
                "write#2",
                Verdict.PASS,
                criteria=["c-length"],
                produced_by="kernel",
                calibration={"status": "deterministic"},
                at=T1,
            ),
            GateResult(
                "source-support",
                "write",
                "write#2",
                Verdict.FAIL,
                criteria=["c-supported"],
                score=0.4,
                findings=[
                    Finding(
                        "statement s3 is not supported by the cited passage",
                        evidence=["h-passage"],
                        statement="s3",
                        criterion="c-supported",
                        implicates="retrieve",
                    )
                ],
                produced_by=PROVER_IDENTITY,
                executor=Executor.AGENT,
                kind=GateKind.GROUNDED,
                ground=Ground.SOURCE,
                calibration={"status": "unmeasured"},
                at=T1,
            ),
        ],
        faults=[
            Fault(
                "F1",
                "length-bound",
                "c-length",
                Ground.COMPUTATION,
                "write",
                "write",
                "brief.md has 812 words, over 800",
                pass_id="write#1",
                budget_remaining=9,
                resolved=True,
                at=T0,
            ),
            Fault(
                "F2",
                "source-support",
                "c-supported",
                Ground.SOURCE,
                "retrieve",
                "write",
                "statement s3 is not supported by the cited passage",
                evidence=["h-passage"],
                pass_id="write#2",
                budget_remaining=8,
                at=T1,
            ),
        ],
        decisions=[
            Decision(
                "D0",
                "Accept these criteria?",
                [BasisEntry("success_spec.yaml", "h-spec"), BasisEntry("goal.md", "h-goal")],
                [DecisionOutcome.ACCEPT, DecisionOutcome.REJECT, DecisionOutcome.REVISE],
                outcome=DecisionOutcome.ACCEPT,
                reason="criteria match the Goal",
                by="logic",
                at=T0,
                raised_at=T0,
            ),
            Decision(
                "D-budget",
                "The source-support gate stalled; extend, revise or abandon?",
                [BasisEntry("run.json", "h-run")],
                [DecisionOutcome.EXTEND, DecisionOutcome.REVISE, DecisionOutcome.ABANDON],
                raised_at=T1,
            ),
        ],
        pending_pass="write#2",
        budget=Budget(passes_total=10, passes_per_gate=2, stall_passes=1),
        budget_epoch=0,
        passes_used=3,
        stop=Stop(StopReason.EXHAUSTED, pass_id="write#2", gate="source-support", at=T1),
        artifact={"brief.md": "h-brief-2", "statements.json": "h-stmts-2"},
        created_at=T0,
        updated_at=T1,
    )


# --- Loop kind -------------------------------------------------------------------


def minimal_kind_data() -> dict:
    """A small kind ``parse_kind`` accepts, with kernel gates and one agent gate.

    Kernel gates: ``pointer-resolution`` (serves provenance) and
    ``scaffold-absent`` (serves scaffold) are *required* — a Success Spec bound
    to this kind must carry a criterion of each of those kinds — while
    ``length-bound`` is optional. The ``write`` step serves every kind those
    gates check so a full spec binds cleanly.
    """
    return {
        "schema": "rh.kind/1",
        "kind": "brief-fixture",
        "title": "One-page brief (fixture)",
        "deliverable": "brief.md",
        "statements": "statements.json",
        "steps": [
            {
                "id": "spec",
                "skill": "success-spec",
                "consumes": ["goal.md"],
                "produces": ["success_spec.yaml"],
                "fixed": True,
            },
            {
                "id": "retrieve",
                "skill": "arxiv-search",
                "consumes": ["success_spec.yaml"],
                "produces": ["papers_raw.jsonl"],
                "serves": ["coverage"],
            },
            {
                "id": "write",
                "skill": "brief-writer",
                "consumes": ["papers_raw.jsonl", "success_spec.yaml"],
                "produces": ["brief.md", "statements.json"],
                "serves": ["answers", "supported", "length", "provenance", "scaffold"],
            },
        ],
        "gates": {
            "kernel": {
                "pointer-resolution": ["write"],
                "scaffold-absent": ["all"],
                "length-bound": ["write"],
            },
            "agent": [
                {
                    "id": "source-support",
                    "skill": "source-support-prover",
                    "kind": "grounded",
                    "ground": "source",
                    "applies_to": ["write"],
                    "serves": ["supported"],
                    "routing": "upstream_of_cited_evidence",
                }
            ],
        },
        "budget": {"passes_total": 12},
        "adaptivity": {"add": True, "skip": ["retrieve"]},
    }


# --- statements / gate contexts ----------------------------------------------------


def statement(sid: str, text: str, *hashes: str, relation: str = "quotes") -> dict:
    return {
        "id": sid,
        "text": text,
        "evidence": [{"hash": h, "relation": relation, "locator": "p1"} for h in hashes],
    }


def statements_json(*items: dict, schema: str = STATEMENTS_SCHEMA) -> bytes:
    return json.dumps({"schema": schema, "statements": list(items)}).encode("utf-8")


def make_ctx(
    store: EvidenceStore,
    outputs: dict[str, bytes],
    criteria: list[Criterion] | tuple[Criterion, ...] = (),
    *,
    step_id: str = "write",
    n: int = 1,
    producer: Skill | None = None,
    deliverable: str = "brief.md",
    statements: str = "statements.json",
) -> GateContext:
    step = Step(step_id, "brief-writer", produces=list(outputs))
    pass_ = Pass(f"{step_id}#{n}", step_id, n, Role.PRODUCER, skill_identity=PRODUCER_IDENTITY)
    return GateContext(
        step=step,
        pass_=pass_,
        outputs=dict(outputs),
        criteria=list(criteria),
        store=store,
        producer=producer or make_skill(),
        deliverable=deliverable,
        statements=statements,
    )


def gate_result_json(**overrides: object) -> bytes:
    """A prover's ``gate_result.json`` for the ``write#1`` pass under ``source-support``."""
    data: dict[str, object] = {
        "schema": "rh.gate_result/1",
        "gate": "source-support",
        "step": "write",
        "pass_id": "write#1",
        "verdict": "pass",
        "findings": [],
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")
