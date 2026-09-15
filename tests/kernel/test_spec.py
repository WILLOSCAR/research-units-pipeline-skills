"""spec: the Success Spec is parsed, bound to the kind's gates, and refused when it cannot be checked."""

from __future__ import annotations

import pytest
import yaml
from helpers import minimal_kind_data

from rh.kernel.kinds import parse_kind
from rh.kernel.records import Budget, Criterion, Ground, Layer, SuccessSpec
from rh.kernel.spec import SpecError, bind, criteria_for_gate, dump_spec, parse_spec

VALID = """\
schema: rh.success_spec/1
scope: LLM agents for literature review, 2023-2026
drift:
  - general RAG surveys
criteria:
  - id: c-supported
    text: every statement cites a retrieved source
    kind: supported
    ground: source
  - id: c-length
    text: the brief stays under 800 words
    kind: length
    ground: computation
    params: {max_words: 800}
  - id: c-provenance
    text: every pointer in statements.json resolves
    kind: provenance
    ground: computation
  - id: c-scaffold
    text: no scaffold text survives into the brief
    kind: scaffold
    ground: computation
  - id: c-reads
    text: the brief reads as one argument
    kind: quality
    ground: human
budget:
  passes_total: 10
"""


def fixture_kind():
    """Kernel gates pointer-resolution + scaffold-absent (required), length-bound, and source-support."""
    return parse_kind(minimal_kind_data())


def bare_kind():
    """The fixture kind with no *required* kernel gate, for isolating per-criterion problems."""
    data = minimal_kind_data()
    data["gates"]["kernel"] = {"length-bound": ["write"]}
    return parse_kind(data)


def criterion(cid: str, kind: str, ground: Ground, text: str = "some text", layer: Layer | None = None) -> Criterion:
    if layer is None:
        layer = Layer.QUALITY if ground is Ground.HUMAN else Layer.CONTRACT
    return Criterion(cid, text, kind, ground, layer=layer)


# --- parse_spec ----------------------------------------------------------------------------


def test_parse_spec_reads_criteria_scope_and_drift():
    spec = parse_spec(VALID, Budget())

    assert spec.schema == "rh.success_spec/1"
    assert spec.scope == "LLM agents for literature review, 2023-2026"
    assert spec.drift == ["general RAG surveys"]
    assert [c.id for c in spec.criteria] == ["c-supported", "c-length", "c-provenance", "c-scaffold", "c-reads"]
    first = spec.criteria[0]
    assert first.text == "every statement cites a retrieved source"
    assert first.kind == "supported"
    assert first.ground is Ground.SOURCE
    assert first.gates == [] and first.params == {}
    assert spec.criteria[1].params == {"max_words": 800}


def test_parse_spec_defaults_the_layer_from_the_ground():
    spec = parse_spec(VALID, Budget())

    assert [c.layer for c in spec.criteria[:4]] == [Layer.CONTRACT] * 4
    assert spec.criteria[4].layer is Layer.QUALITY


def test_parse_spec_keeps_an_explicit_layer():
    text = VALID.replace("    kind: supported\n", "    kind: supported\n    layer: integrity\n")

    assert parse_spec(text, Budget()).criteria[0].layer is Layer.INTEGRITY


def test_parse_spec_merges_the_budget_override_over_the_default():
    spec = parse_spec(VALID, Budget(passes_total=24, passes_per_gate=5, stall_passes=4))

    assert spec.budget == Budget(passes_total=10, passes_per_gate=5, stall_passes=4)


def test_parse_spec_uses_the_default_budget_when_none_is_given():
    text = VALID.split("budget:")[0]

    spec = parse_spec(text, Budget(passes_total=7, passes_per_gate=2, stall_passes=1))

    assert spec.budget == Budget(passes_total=7, passes_per_gate=2, stall_passes=1)


@pytest.mark.parametrize("text", ["- just\n- a list\n", "a scalar", "", "null"])
def test_parse_spec_refuses_a_non_mapping(text):
    with pytest.raises(SpecError, match="must be a mapping") as info:
        parse_spec(text, Budget())
    assert info.value.problems == ["success_spec.yaml must be a mapping"]


def test_parse_spec_refuses_the_wrong_schema():
    text = VALID.replace("rh.success_spec/1", "rh.success_spec/0")

    with pytest.raises(SpecError) as info:
        parse_spec(text, Budget())
    assert info.value.problems == ["schema must be rh.success_spec/1"]


@pytest.mark.parametrize("criteria", ["criteria: []\n", "criteria: {}\n", "criteria: none\n", ""])
def test_parse_spec_refuses_empty_or_missing_criteria(criteria):
    text = f"schema: rh.success_spec/1\n{criteria}"

    with pytest.raises(SpecError) as info:
        parse_spec(text, Budget())
    assert info.value.problems == ["criteria must be a non-empty list"]


def test_parse_spec_reports_schema_and_criteria_problems_together():
    with pytest.raises(SpecError) as info:
        parse_spec("schema: nope\ncriteria: []\n", Budget())
    assert info.value.problems == ["schema must be rh.success_spec/1", "criteria must be a non-empty list"]


def test_parse_spec_refuses_a_criterion_with_an_unknown_ground():
    text = VALID.replace("ground: computation\n    params", "ground: vibes\n    params")

    with pytest.raises(SpecError) as info:
        parse_spec(text, Budget())
    assert info.value.problems == ["criteria[1]: 'vibes' is not a valid Ground"]


def test_parse_spec_refuses_a_criterion_missing_required_fields():
    text = "schema: rh.success_spec/1\ncriteria:\n  - id: c1\n    text: no kind or ground\n"

    with pytest.raises(SpecError) as info:
        parse_spec(text, Budget())
    assert info.value.problems[0].startswith("criteria[0]:")


def test_parse_spec_refuses_a_criterion_that_is_not_a_mapping():
    with pytest.raises(SpecError):
        parse_spec("schema: rh.success_spec/1\ncriteria: [just-a-string]\n", Budget())


def test_parse_spec_refuses_a_budget_that_is_not_a_mapping():
    text = "schema: rh.success_spec/1\ncriteria: [{id: c, text: t, kind: k, ground: source}]\nbudget: 5\n"

    with pytest.raises(SpecError):
        parse_spec(text, Budget())


def test_a_non_integer_budget_field_is_refused_not_crashed_on():
    text = "schema: rh.success_spec/1\ncriteria: [{id: c, text: t, kind: supported, ground: source}]\nbudget: {passes_total: lots}\n"

    try:
        spec = parse_spec(text, Budget())
    except SpecError:
        return  # refusing at parse time is the better outcome
    assert any(p.startswith("budget.passes_total") for p in bind(spec, bare_kind()))


def test_spec_error_message_joins_its_problems():
    err = SpecError(["a", "b"])

    assert str(err) == "a; b" and err.problems == ["a", "b"]


# --- bind -------------------------------------------------------------------------------------


def test_bind_fills_gates_from_the_kind_and_reports_no_problems_for_a_checkable_spec():
    spec = parse_spec(VALID, Budget())

    problems = bind(spec, fixture_kind())

    assert problems == []
    assert spec.criteria[0].gates == ["source-support"]
    assert spec.criteria[1].gates == ["length-bound"]
    assert spec.criteria[2].gates == ["pointer-resolution"]
    assert spec.criteria[3].gates == ["scaffold-absent"]
    assert spec.criteria[4].gates == []  # human ground: no gate, a Decision judges it


def test_bind_binds_every_gate_that_serves_a_criterion_kind():
    data = minimal_kind_data()
    data["gates"]["kernel"] = {}
    data["gates"]["agent"].append(
        {"id": "second-support", "skill": "another-prover", "serves": ["supported"], "applies_to": ["write"]}
    )
    spec = SuccessSpec(criteria=[criterion("c1", "supported", Ground.SOURCE)])

    assert bind(spec, parse_kind(data)) == []
    assert spec.criteria[0].gates == ["source-support", "second-support"]


def test_bind_reports_a_human_criterion_placed_in_the_contract_layer():
    spec = SuccessSpec(criteria=[criterion("c-reads", "quality", Ground.HUMAN, layer=Layer.CONTRACT)])

    problems = bind(spec, bare_kind())

    assert problems == ["c-reads: ground=human iff layer=quality (got human/contract)"]
    assert spec.criteria[0].gates == []


def test_bind_reports_a_source_criterion_placed_in_the_quality_layer():
    spec = SuccessSpec(criteria=[criterion("c1", "supported", Ground.SOURCE, layer=Layer.QUALITY)])

    problems = bind(spec, bare_kind())

    assert problems == ["c1: ground=human iff layer=quality (got source/quality)"]
    assert spec.criteria[0].gates == ["source-support"]  # still bound; the layer is what is wrong


def test_bind_reports_a_computation_criterion_no_gate_can_check():
    # 'coverage' is served by the retrieve step but by no gate in the fixture kind.
    spec = SuccessSpec(criteria=[criterion("c-cov", "coverage", Ground.COMPUTATION)])

    problems = bind(spec, bare_kind())

    assert problems == ["c-cov: no gate in kind 'brief-fixture' can check criterion kind 'coverage'"]
    assert spec.criteria[0].gates == []


def test_bind_reports_a_criterion_kind_no_step_serves():
    # 'format' is served by the schema-valid gate but by no step in the fixture kind.
    data = minimal_kind_data()
    data["gates"]["kernel"] = {"schema-valid": ["write"]}
    spec = SuccessSpec(criteria=[criterion("c-fmt", "format", Ground.COMPUTATION)])

    problems = bind(spec, parse_kind(data))

    assert problems == ["c-fmt: no step in kind 'brief-fixture' serves criterion kind 'format'"]
    assert spec.criteria[0].gates == ["schema-valid"]


def test_bind_reports_both_when_neither_gate_nor_step_serves_the_kind():
    spec = SuccessSpec(criteria=[criterion("c-x", "novelty", Ground.SOURCE)])

    problems = bind(spec, bare_kind())

    assert problems == [
        "c-x: no gate in kind 'brief-fixture' can check criterion kind 'novelty'",
        "c-x: no step in kind 'brief-fixture' serves criterion kind 'novelty'",
    ]


def test_bind_reports_duplicate_ids():
    spec = SuccessSpec(
        criteria=[criterion("c1", "supported", Ground.SOURCE), criterion("c1", "length", Ground.COMPUTATION)]
    )

    assert bind(spec, bare_kind()) == ["c1: duplicate criterion id"]


def test_bind_reports_empty_text():
    spec = SuccessSpec(criteria=[criterion("c1", "supported", Ground.SOURCE, text="   \n")])

    assert bind(spec, bare_kind()) == ["c1: empty text"]


@pytest.mark.parametrize("key", ["passes_total", "passes_per_gate", "stall_passes"])
def test_bind_reports_a_budget_field_below_one(key):
    spec = SuccessSpec(criteria=[criterion("c1", "supported", Ground.SOURCE)])
    setattr(spec.budget, key, 0)

    assert bind(spec, bare_kind()) == [f"budget.{key} must be >= 1"]


def test_bind_reports_a_required_kernel_gate_no_criterion_binds():
    spec = SuccessSpec(criteria=[criterion("c1", "supported", Ground.SOURCE)])

    problems = bind(spec, fixture_kind())

    assert problems == [
        "kernel gate 'pointer-resolution' is unbound: add a criterion of kind provenance",
        "kernel gate 'scaffold-absent' is unbound: add a criterion of kind scaffold",
    ]


def test_bind_does_not_demand_a_criterion_for_an_optional_kernel_gate():
    # length-bound is declared by the kind but is not required; a spec without a length criterion is fine.
    spec = SuccessSpec(
        criteria=[
            criterion("c1", "supported", Ground.SOURCE),
            criterion("c-prov", "provenance", Ground.COMPUTATION),
            criterion("c-scaf", "scaffold", Ground.COMPUTATION),
        ]
    )

    assert bind(spec, fixture_kind()) == []
    assert criteria_for_gate(spec, "length-bound") == []


def test_bind_does_not_demand_a_criterion_for_an_agent_gate():
    data = minimal_kind_data()
    data["gates"]["kernel"] = {}
    spec = SuccessSpec(criteria=[criterion("c-len", "length", Ground.COMPUTATION)])

    problems = bind(spec, parse_kind(data))

    # 'length' has no gate in this kind (length-bound was removed), but the unbound
    # agent gate source-support is not itself reported.
    assert problems == ["c-len: no gate in kind 'brief-fixture' can check criterion kind 'length'"]


def test_bind_collects_every_problem_in_order():
    spec = SuccessSpec(
        criteria=[
            criterion("c1", "supported", Ground.SOURCE, text=""),
            criterion("c1", "coverage", Ground.COMPUTATION),
            criterion("c-scaf", "scaffold", Ground.COMPUTATION),
        ],
        budget=Budget(passes_total=0, passes_per_gate=1, stall_passes=1),
    )

    problems = bind(spec, fixture_kind())

    assert problems == [
        "c1: empty text",
        "c1: duplicate criterion id",
        "c1: no gate in kind 'brief-fixture' can check criterion kind 'coverage'",
        "kernel gate 'pointer-resolution' is unbound: add a criterion of kind provenance",
        "budget.passes_total must be >= 1",
    ]


# --- criteria_for_gate / dump_spec ---------------------------------------------------------------


def test_criteria_for_gate_returns_the_bound_criteria():
    spec = parse_spec(VALID, Budget())
    bind(spec, fixture_kind())

    assert [c.id for c in criteria_for_gate(spec, "length-bound")] == ["c-length"]
    assert [c.id for c in criteria_for_gate(spec, "source-support")] == ["c-supported"]
    assert [c.id for c in criteria_for_gate(spec, "scaffold-absent")] == ["c-scaffold"]
    assert criteria_for_gate(spec, "schema-valid") == []


def test_criteria_for_gate_is_empty_before_bind():
    assert criteria_for_gate(parse_spec(VALID, Budget()), "length-bound") == []


def test_dump_spec_round_trips_through_parse_spec():
    spec = parse_spec(VALID, Budget())
    bind(spec, fixture_kind())

    text = dump_spec(spec)
    back = parse_spec(text, Budget(passes_total=1, passes_per_gate=1, stall_passes=1))

    assert back == spec
    assert back.criteria[0].gates == ["source-support"]
    assert back.budget == Budget(passes_total=10, passes_per_gate=3, stall_passes=2)  # dumped budget wins


def test_dump_spec_is_yaml_carrying_the_schema():
    text = dump_spec(parse_spec(VALID, Budget()))
    data = yaml.safe_load(text)

    assert data["schema"] == "rh.success_spec/1"
    assert set(data) == {"criteria", "scope", "drift", "budget", "schema"}
    assert data["criteria"][4]["ground"] == "human" and data["criteria"][4]["layer"] == "quality"
