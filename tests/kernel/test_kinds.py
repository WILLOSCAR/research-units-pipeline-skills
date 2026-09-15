"""kinds: a Loop kind's YAML SOP is parsed and checked before any Run starts from it."""

from __future__ import annotations

import pytest
import yaml
from helpers import minimal_kind_data

from rh.kernel.kinds import KINDS_DIR, Kind, KindError, list_kinds, load_kind, parse_kind
from rh.kernel.records import Executor, GateKind, Ground, StepStatus

SHIPPED_KINDS = sorted(KINDS_DIR.glob("*.yaml")) if KINDS_DIR.is_dir() else []


# --- parse_kind: accept ------------------------------------------------------------------------


def test_parse_kind_accepts_the_minimal_kind():
    kind = parse_kind(minimal_kind_data(), source="fixture")

    assert isinstance(kind, Kind)
    assert kind.kind == "brief-fixture"
    assert kind.title == "One-page brief (fixture)"
    assert kind.deliverable == "brief.md" and kind.statements == "statements.json"
    assert kind.source == "fixture"
    assert [s.id for s in kind.steps] == ["spec", "retrieve", "write"]
    assert kind.steps[0].fixed is True and kind.steps[1].fixed is False
    assert kind.steps[0].status is StepStatus.PENDING
    assert kind.formats == ["md"]


def test_parse_kind_merges_budget_and_adaptivity_with_defaults():
    kind = parse_kind(minimal_kind_data())

    assert kind.budget.passes_total == 12
    assert kind.budget.passes_per_gate == 3 and kind.budget.stall_passes == 2
    assert kind.adaptivity.add is True
    assert kind.adaptivity.skip == ["retrieve"]
    assert kind.adaptivity.reorder is False


def test_parse_kind_declares_kernel_gates_from_the_kernel_registry():
    kind = parse_kind(minimal_kind_data())

    pointer = kind.gate("pointer-resolution")
    assert pointer.executor is Executor.KERNEL
    assert pointer.kind is GateKind.STRUCTURAL and pointer.ground is Ground.COMPUTATION
    assert pointer.serves == ["provenance"]
    assert pointer.applies_to == ["write"]
    assert pointer.calibration == {"status": "deterministic"}
    assert pointer.skill is None
    assert kind.gate("scaffold-absent").applies_to == ["all"]
    assert kind.gate("length-bound").serves == ["length"]


def test_parse_kind_declares_agent_gates_with_their_prover_skill():
    kind = parse_kind(minimal_kind_data())

    gate = kind.gate("source-support")
    assert gate.executor is Executor.AGENT
    assert gate.skill == "source-support-prover"
    assert gate.kind is GateKind.GROUNDED
    assert gate.ground is Ground.SOURCE
    assert gate.serves == ["supported"]
    assert gate.applies_to == ["write"]
    assert gate.routing == "upstream_of_cited_evidence"
    assert gate.calibration == {"status": "unmeasured"}


def test_parse_kind_agent_gate_defaults():
    data = minimal_kind_data()
    data["gates"]["agent"] = [{"id": "spec-coverage", "skill": "spec-coverage-prover"}]

    gate = parse_kind(data).gate("spec-coverage")

    assert gate.kind is GateKind.GROUNDED
    assert gate.ground is Ground.SOURCE
    assert gate.routing == "checked_step"
    assert gate.serves == [] and gate.applies_to == []


def test_parse_kind_accepts_a_kind_without_gates():
    data = minimal_kind_data()
    del data["gates"]

    assert parse_kind(data).gates == []


# --- parse_kind: refuse ------------------------------------------------------------------------


def test_parse_kind_refuses_the_wrong_schema():
    data = minimal_kind_data()
    data["schema"] = "rh.kind/2"

    with pytest.raises(KindError, match="schema must be rh.kind/1"):
        parse_kind(data, source="fixture.yaml")


@pytest.mark.parametrize("key", ["kind", "title", "deliverable", "statements", "steps"])
def test_parse_kind_refuses_a_missing_required_key(key):
    data = minimal_kind_data()
    del data[key]

    with pytest.raises(KindError, match=f"missing '{key}'"):
        parse_kind(data)


def test_parse_kind_refuses_a_first_step_that_is_not_spec():
    data = minimal_kind_data()
    data["steps"][0]["id"] = "derive"
    data["steps"][1]["consumes"] = ["success_spec.yaml"]

    with pytest.raises(KindError, match="first step must be 'spec'"):
        parse_kind(data)


def test_parse_kind_refuses_an_empty_step_list():
    data = minimal_kind_data()
    data["steps"] = []

    with pytest.raises(KindError, match="first step must be 'spec'"):
        parse_kind(data)


def test_parse_kind_refuses_duplicate_step_ids():
    data = minimal_kind_data()
    data["steps"][2]["id"] = "retrieve"

    with pytest.raises(KindError, match="duplicate step ids"):
        parse_kind(data)


def test_parse_kind_refuses_consuming_an_input_no_step_produces():
    data = minimal_kind_data()
    data["steps"][2]["consumes"].append("core_set.csv")

    with pytest.raises(KindError, match=r"step 'write' consumes \['core_set.csv'\] before any step produces it"):
        parse_kind(data)


def test_parse_kind_refuses_consuming_an_output_produced_only_later():
    data = minimal_kind_data()
    data["steps"][1]["consumes"].append("brief.md")  # retrieve wants what write produces

    with pytest.raises(KindError, match="step 'retrieve' consumes"):
        parse_kind(data)


def test_parse_kind_refuses_an_unknown_kernel_gate():
    data = minimal_kind_data()
    data["gates"]["kernel"]["outputs-present"] = ["all"]

    with pytest.raises(KindError, match="unknown kernel gate 'outputs-present'"):
        parse_kind(data)


def test_parse_kind_refuses_a_kernel_gate_applying_to_an_unknown_step():
    data = minimal_kind_data()
    data["gates"]["kernel"]["length-bound"] = ["polish"]

    with pytest.raises(KindError, match="gate 'length-bound' applies to unknown step 'polish'"):
        parse_kind(data)


def test_parse_kind_refuses_an_agent_gate_applying_to_an_unknown_step():
    data = minimal_kind_data()
    data["gates"]["agent"][0]["applies_to"] = ["write", "polish"]

    with pytest.raises(KindError, match="gate 'source-support' applies to unknown step 'polish'"):
        parse_kind(data)


def test_parse_kind_refuses_a_deliverable_no_step_produces():
    data = minimal_kind_data()
    data["deliverable"] = "report.md"

    with pytest.raises(KindError, match="deliverable and statements must be produced"):
        parse_kind(data)


def test_parse_kind_refuses_statements_no_step_produces():
    data = minimal_kind_data()
    data["statements"] = "claims.json"

    with pytest.raises(KindError, match="deliverable and statements must be produced"):
        parse_kind(data)


def malformed_kinds() -> list:
    without_skill = minimal_kind_data()
    without_skill["steps"][1] = {"id": "retrieve"}
    agent_without_skill = minimal_kind_data()
    agent_without_skill["gates"]["agent"] = [{"id": "x"}]
    agent_bad_kind = minimal_kind_data()
    agent_bad_kind["gates"]["agent"] = [{"id": "x", "skill": "s", "kind": "fuzzy"}]
    return [
        pytest.param(None, id="not-a-mapping"),
        pytest.param(without_skill, id="step-without-skill"),
        pytest.param(agent_without_skill, id="agent-gate-without-skill"),
        pytest.param(agent_bad_kind, id="agent-gate-bad-kind"),
    ]


@pytest.mark.parametrize("data", malformed_kinds())
def test_parse_kind_wraps_malformed_input_in_kind_error(data):
    with pytest.raises(KindError):
        parse_kind(data, source="fixture.yaml")


# --- Kind methods -----------------------------------------------------------------------------


def test_plan_returns_an_independent_copy_of_the_steps():
    kind = parse_kind(minimal_kind_data())

    plan = kind.plan()

    assert plan.steps == kind.steps
    assert plan.ops == []
    assert all(a is not b for a, b in zip(plan.steps, kind.steps))
    plan.steps[1].status = StepStatus.SKIPPED
    plan.steps[2].consumes.append("extra")
    assert kind.steps[1].status is StepStatus.PENDING
    assert "extra" not in kind.steps[2].consumes
    assert kind.plan().steps[1].status is StepStatus.PENDING  # a second plan starts fresh too


def test_gates_for_selects_by_step_id_or_all():
    kind = parse_kind(minimal_kind_data())

    assert sorted(g.id for g in kind.gates_for("write")) == [
        "length-bound",
        "pointer-resolution",
        "scaffold-absent",
        "source-support",
    ]
    assert [g.id for g in kind.gates_for("spec")] == ["scaffold-absent"]
    assert [g.id for g in kind.gates_for("retrieve")] == ["scaffold-absent"]


def test_gates_serving_selects_by_criterion_kind():
    kind = parse_kind(minimal_kind_data())

    assert [g.id for g in kind.gates_serving("supported")] == ["source-support"]
    assert [g.id for g in kind.gates_serving("provenance")] == ["pointer-resolution"]
    assert [g.id for g in kind.gates_serving("length")] == ["length-bound"]
    assert kind.gates_serving("coverage") == []


def test_gate_lookup_raises_key_error_for_an_unknown_gate():
    with pytest.raises(KeyError):
        parse_kind(minimal_kind_data()).gate("spec-coverage")


def test_artifact_step_is_the_last_step_producing_the_deliverable():
    data = minimal_kind_data()
    data["steps"].append(
        {"id": "polish", "skill": "draft-polisher", "consumes": ["brief.md"], "produces": ["brief.md"]}
    )

    assert parse_kind(data).artifact_step().id == "polish"
    assert parse_kind(minimal_kind_data()).artifact_step().id == "write"


def test_artifact_step_raises_kind_error_when_nothing_produces_the_deliverable():
    kind = parse_kind(minimal_kind_data())
    kind.deliverable = "report.md"

    with pytest.raises(KindError, match="no step produces the deliverable"):
        kind.artifact_step()


# --- load_kind / list_kinds -------------------------------------------------------------------


def test_load_kind_reads_a_yaml_file_and_records_its_source(tmp_path):
    path = tmp_path / "brief-fixture.yaml"
    path.write_text(yaml.safe_dump(minimal_kind_data()), encoding="utf-8")

    kind = load_kind("brief-fixture", tmp_path)

    assert kind.kind == "brief-fixture"
    assert kind.source == str(path)
    assert list_kinds(tmp_path) == ["brief-fixture"]


def test_load_kind_raises_kind_error_for_an_unknown_name(tmp_path):
    (tmp_path / "brief-fixture.yaml").write_text(yaml.safe_dump(minimal_kind_data()), encoding="utf-8")

    with pytest.raises(KindError, match="unknown Loop kind 'novel'; available: brief-fixture"):
        load_kind("novel", tmp_path)


def test_load_kind_raises_kind_error_when_the_kinds_dir_is_empty(tmp_path):
    with pytest.raises(KindError, match="unknown Loop kind"):
        load_kind("brief", tmp_path / "nowhere")
    assert list_kinds(tmp_path / "nowhere") == []


def test_load_kind_surfaces_parse_errors_with_the_file_as_source(tmp_path):
    data = minimal_kind_data()
    data["deliverable"] = "report.md"
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(KindError, match=str(path)):
        load_kind("broken", tmp_path)


# --- shipped kinds ----------------------------------------------------------------------------


@pytest.mark.skipif(not SHIPPED_KINDS, reason="no Loop kind YAML under src/rh/kinds yet")
@pytest.mark.parametrize("path", SHIPPED_KINDS, ids=[p.stem for p in SHIPPED_KINDS])
def test_every_shipped_kind_parses(path):
    kind = load_kind(path.stem)

    assert kind.kind
    assert kind.source == str(path)
    assert kind.steps[0].id == "spec"
    assert kind.deliverable in kind.artifact_step().produces
    assert kind.plan().steps == kind.steps
    assert path.stem in list_kinds()
    for gate in kind.gates:
        for step_id in gate.applies_to:
            assert step_id == "all" or any(s.id == step_id for s in kind.steps)
