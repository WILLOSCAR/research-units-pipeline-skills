"""records: the JSON codec and the lookups on Plan and RunState."""

from __future__ import annotations

import json

import pytest
from helpers import four_step_plan, sample_run_state

from rh.kernel.records import (
    Decision,
    DecisionOutcome,
    Finding,
    GateKind,
    GateResult,
    Ground,
    Layer,
    Plan,
    Role,
    RunState,
    RunStatus,
    Step,
    StepStatus,
    StopReason,
    Verdict,
    decode,
    encode,
)

# --- codec ---------------------------------------------------------------------------


def test_encode_turns_records_and_enums_into_json_shapes():
    shape = encode(sample_run_state())

    assert shape["schema"] == "rh.run/1"
    assert shape["status"] == "blocked"
    assert shape["goal"]["constraints"]["sources"] == ["arxiv"]
    assert shape["plan"]["steps"][2]["status"] == "skipped"
    assert shape["plan"]["ops"][0] == {
        "op": "skip",
        "step": "curate",
        "at": "2026-09-12T10:00:00+00:00",
        "detail": {"reason": "single-source Goal"},
    }
    assert shape["spec"]["schema"] == "rh.success_spec/1"
    assert shape["spec"]["criteria"][0]["ground"] == "source"
    assert shape["spec"]["criteria"][2]["layer"] == "quality"
    assert shape["passes"][2]["role"] == "repair"
    assert shape["gate_results"][2]["findings"][0]["evidence"] == ["h-passage"]
    assert shape["decisions"][0]["options"] == ["accept", "reject", "revise"]
    assert shape["decisions"][0]["basis"][0] == {"name": "success_spec.yaml", "hash": "h-spec"}
    assert shape["decisions"][1]["outcome"] is None
    assert shape["stop"]["reason"] == "exhausted"
    json.dumps(shape)  # JSON-ready without a custom encoder


def test_encode_handles_tuples_and_non_string_dict_keys():
    assert encode((Verdict.PASS, 1)) == ["pass", 1]
    assert encode({1: Ground.HUMAN}) == {"1": "human"}
    assert encode("plain") == "plain"
    assert encode(None) is None


def test_round_trip_through_json_preserves_every_field():
    state = sample_run_state()

    back = decode(RunState, json.loads(json.dumps(encode(state))))

    assert back == state
    assert back is not state
    assert back.plan == state.plan and back.plan is not state.plan


def test_round_trip_restores_enum_types_in_nested_records():
    back = decode(RunState, json.loads(json.dumps(encode(sample_run_state()))))

    assert back.status is RunStatus.BLOCKED
    assert back.plan.steps[2].status is StepStatus.SKIPPED
    assert back.spec is not None
    assert back.spec.criteria[0].ground is Ground.SOURCE
    assert back.spec.criteria[2].layer is Layer.QUALITY
    assert back.passes[2].role is Role.REPAIR
    assert back.gate_results[0].verdict is Verdict.FAIL
    assert back.gate_results[2].kind is GateKind.GROUNDED
    assert back.gate_results[2].ground is Ground.SOURCE
    assert isinstance(back.gate_results[2].findings[0], Finding)
    assert back.gate_results[2].findings[0].implicates == "retrieve"
    assert back.faults[1].ground is Ground.SOURCE
    assert back.decisions[0].options == [DecisionOutcome.ACCEPT, DecisionOutcome.REJECT, DecisionOutcome.REVISE]
    assert back.decisions[0].outcome is DecisionOutcome.ACCEPT
    assert back.decisions[1].outcome is None
    assert back.stop is not None and back.stop.reason is StopReason.EXHAUSTED
    assert back.budget.passes_total == 10


def test_decode_ignores_unknown_keys_and_fills_defaults():
    step = decode(Step, {"id": "write", "skill": "brief-writer", "role": "producer"})

    assert step.consumes == [] and step.produces == [] and step.serves == []
    assert step.fixed is False
    assert step.status is StepStatus.PENDING
    assert step.admitted_pass is None


def test_decode_keeps_explicit_nulls_for_optional_fields():
    result = decode(
        GateResult,
        {"gate": "g", "step": "write", "pass_id": "write#1", "verdict": "pass", "score": None},
    )

    assert result.score is None
    assert result.verdict is Verdict.PASS
    assert result.findings == []


def test_decode_rejects_an_unknown_enum_value():
    with pytest.raises(ValueError):
        decode(Step, {"id": "x", "skill": "y", "status": "nope"})


# --- Plan -------------------------------------------------------------------------------


def test_plan_active_excludes_the_skipped_step():
    plan = four_step_plan()

    assert [s.id for s in plan.active()] == ["spec", "retrieve", "write"]
    assert [s.id for s in four_step_plan(skip_curate=False).active()] == ["spec", "retrieve", "curate", "write"]


def test_plan_get_raises_key_error_for_an_unknown_step():
    with pytest.raises(KeyError):
        four_step_plan().get("polish")


def test_plan_producers_of_ignores_skipped_producers():
    plan = four_step_plan()

    assert [s.id for s in plan.producers_of("papers_raw.jsonl")] == ["retrieve"]
    assert plan.producers_of("core_set.jsonl") == []
    assert plan.producers_of("goal.md") == []
    assert [s.id for s in four_step_plan(skip_curate=False).producers_of("core_set.jsonl")] == ["curate"]


def test_plan_upstream_walks_transitively_in_plan_order():
    plan = four_step_plan(skip_curate=False)

    assert [s.id for s in plan.upstream("write")] == ["spec", "retrieve", "curate"]
    assert [s.id for s in plan.upstream("curate")] == ["spec", "retrieve"]
    assert [s.id for s in plan.upstream("retrieve")] == ["spec"]
    assert plan.upstream("spec") == []


def test_plan_upstream_skips_the_skipped_step():
    plan = four_step_plan()

    assert [s.id for s in plan.upstream("write")] == ["spec", "retrieve"]


def test_plan_upstream_is_transitive_through_a_single_consumed_output():
    plan = Plan(
        steps=[
            Step("spec", "s", consumes=["goal.md"], produces=["success_spec.yaml"]),
            Step("retrieve", "r", consumes=["success_spec.yaml"], produces=["papers_raw.jsonl"]),
            Step("curate", "c", consumes=["papers_raw.jsonl"], produces=["core_set.jsonl"]),
            Step("write", "w", consumes=["core_set.jsonl"], produces=["brief.md"]),
        ]
    )

    assert [s.id for s in plan.upstream("write")] == ["spec", "retrieve", "curate"]


def test_plan_downstream_walks_transitively_and_skips_the_skipped_step():
    plan = four_step_plan()

    assert [s.id for s in plan.downstream("spec")] == ["retrieve", "write"]
    assert [s.id for s in plan.downstream("retrieve")] == ["write"]
    assert plan.downstream("write") == []

    full = four_step_plan(skip_curate=False)
    assert [s.id for s in full.downstream("spec")] == ["retrieve", "curate", "write"]
    assert [s.id for s in full.downstream("retrieve")] == ["curate", "write"]


# --- RunState ---------------------------------------------------------------------------


def test_pending_decision_returns_the_latest_undecided_one():
    state = sample_run_state()

    pending = state.pending_decision()

    assert pending is not None and pending.id == "D-budget"
    assert pending.pending is True
    assert state.decisions[0].pending is False  # D0 already has an outcome


def test_pending_decision_ignores_decided_and_stale_ones():
    state = sample_run_state()

    state.decisions[1].outcome = DecisionOutcome.EXTEND
    assert state.pending_decision() is None

    state.decisions.append(
        Decision("D-final", "Deliver?", [], [DecisionOutcome.ACCEPT, DecisionOutcome.REJECT], stale=True)
    )
    assert state.pending_decision() is None

    state.decisions[-1].stale = False
    assert state.pending_decision() is state.decisions[-1]


def test_decision_lookup_returns_the_most_recent_record_with_that_id():
    state = sample_run_state()
    state.decisions.append(Decision("D0", "again", [], [DecisionOutcome.ACCEPT]))

    assert state.decision("D0") is state.decisions[-1]
    assert state.decision("D-nope") is None


def test_latest_result_returns_the_last_result_for_step_and_gate():
    state = sample_run_state()

    latest = state.latest_result("write", "length-bound")

    assert latest is not None
    assert latest.pass_id == "write#2" and latest.verdict is Verdict.PASS
    assert state.latest_result("write", "spec-coverage") is None
    assert state.latest_result("spec", "length-bound") is None


def test_open_faults_excludes_resolved_faults():
    state = sample_run_state()

    assert [f.id for f in state.open_faults()] == ["F2"]

    state.faults[1].resolved = True
    assert state.open_faults() == []


def test_pass_lookups():
    state = sample_run_state()

    assert state.get_pass("write#2").role is Role.REPAIR
    assert [p.id for p in state.passes_for("write")] == ["write#1", "write#2", "source-support#1"]
    assert state.passes_for("curate") == []
    assert [r.gate for r in state.results_for("write#2")] == ["length-bound", "source-support"]
    with pytest.raises(KeyError):
        state.get_pass("write#9")
