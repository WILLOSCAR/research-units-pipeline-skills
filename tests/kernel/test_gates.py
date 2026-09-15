"""gates: kernel gates recompute from Evidence bytes; agent GateResults are admitted or refused."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from helpers import (
    PRODUCER_IDENTITY,
    PROVER_IDENTITY,
    gate_result_json,
    make_ctx,
    make_skill,
    make_store,
    statement,
    statements_json,
)

from rh.kernel.evidence import EvidenceCorrupt
from rh.kernel.gates import (
    GATE_RESULT_SCHEMA,
    KERNEL_GATES,
    STATEMENTS_SCHEMA,
    GateResultInvalid,
    KernelGate,
    Pointer,
    Statement,
    paragraphs,
    parse_statements,
    validate_agent_result,
)
from rh.kernel.records import (
    Criterion,
    Executor,
    GateDecl,
    GateKind,
    Ground,
    Pass,
    Relation,
    Role,
    Verdict,
)

S1 = "Agents retrieve papers before they read them."
S2 = "Retrieval precision drives downstream quality."


def stored(store, text: str) -> str:
    return store.put_text(text, "sources/p1.md", "retrieve#1").hash


# --- parse_statements ---------------------------------------------------------------------


def test_parse_statements_accepts_a_valid_index():
    data = statements_json(statement("s1", S1, "h1", "h2"), statement("s2", S2, "h3", relation="infers"))

    statements, problems = parse_statements(data)

    assert problems == []
    assert statements == [
        Statement("s1", S1, [Pointer("h1", Relation.QUOTES, "p1"), Pointer("h2", Relation.QUOTES, "p1")]),
        Statement("s2", S2, [Pointer("h3", Relation.INFERS, "p1")]),
    ]
    assert statements[1].evidence[0].relation is Relation.INFERS


def test_parse_statements_refuses_bytes_that_are_not_json():
    statements, problems = parse_statements(b"{not json")

    assert statements == []
    assert len(problems) == 1 and problems[0].startswith("statements: not valid JSON")


def test_parse_statements_refuses_bytes_that_are_not_utf8():
    statements, problems = parse_statements(b"\xff\xfe\x00")

    assert statements == [] and problems[0].startswith("statements: not valid JSON")


def test_parse_statements_reports_the_wrong_schema_but_still_parses():
    data = statements_json(statement("s1", S1, "h1"), schema="rh.statements/0")

    statements, problems = parse_statements(data)

    assert problems == [f"statements: schema must be {STATEMENTS_SCHEMA}"]
    assert [s.id for s in statements] == ["s1"]


def test_parse_statements_refuses_a_non_list_body():
    data = json.dumps({"schema": STATEMENTS_SCHEMA, "statements": {"s1": S1}}).encode()

    assert parse_statements(data) == ([], ["statements: 'statements' must be a list"])
    assert parse_statements(b"[]") == (
        [],
        [f"statements: schema must be {STATEMENTS_SCHEMA}", "statements: 'statements' must be a list"],
    )


def test_parse_statements_reports_duplicate_ids():
    data = statements_json(statement("s1", S1, "h1"), statement("s1", S2, "h2"))

    statements, problems = parse_statements(data)

    assert problems == ["statements: duplicate ids"]
    assert len(statements) == 2


def test_parse_statements_reports_a_bad_relation_and_drops_that_statement():
    data = statements_json(statement("s1", S1, "h1", relation="paraphrases"), statement("s2", S2, "h2"))

    statements, problems = parse_statements(data)

    assert [s.id for s in statements] == ["s2"]
    assert len(problems) == 1 and problems[0].startswith("statements[0]:")


def test_parse_statements_reports_a_statement_missing_its_text():
    data = json.dumps({"schema": STATEMENTS_SCHEMA, "statements": [{"id": "s1"}]}).encode()

    statements, problems = parse_statements(data)

    assert statements == [] and problems[0].startswith("statements[0]:")


# --- paragraphs ------------------------------------------------------------------------------


DELIVERABLE = """---
title: Brief
kind: brief
---

# LLM agents for literature review

<!-- scaffold -->

Agents retrieve papers
before they read them.

---

## Findings

Retrieval precision drives downstream quality.\x20\x20

***

<!-- a
multi-line comment -->
"""


def test_paragraphs_keep_only_body_paragraphs():
    assert paragraphs(DELIVERABLE) == [
        "Agents retrieve papers\nbefore they read them.",
        "Retrieval precision drives downstream quality.",
    ]


def test_paragraphs_without_front_matter_start_at_the_first_block():
    assert paragraphs("# Title\n\nOne.\n\nTwo.\n") == ["One.", "Two."]


def test_paragraphs_treat_an_unclosed_leading_rule_as_a_rule_not_front_matter():
    assert paragraphs("---\n\nOne.\n") == ["One."]


def test_paragraphs_of_an_empty_or_heading_only_document():
    assert paragraphs("") == []
    assert paragraphs("# Only\n\n## Headings\n") == []


def test_paragraphs_keep_a_fenced_code_block_with_the_paragraph_it_follows():
    doc = "Run it like this:\n```bash\n# a comment, not a heading\nrh start\n\nrh continue\n```\n\nThen read the packet.\n"

    assert paragraphs(doc) == [
        "Run it like this:\n```bash\n# a comment, not a heading\nrh start\n\nrh continue\n```",
        "Then read the packet.",
    ]


# --- kernel gates: registry and result shape ---------------------------------------------------


def test_kernel_gate_registry_ships_the_five_kernel_gates():
    assert set(KERNEL_GATES) == {
        "pointer-resolution",
        "provenance-present",
        "scaffold-absent",
        "schema-valid",
        "length-bound",
    }
    for gate_id, gate in KERNEL_GATES.items():
        assert isinstance(gate, KernelGate) and gate.id == gate_id
        assert gate.kind is GateKind.STRUCTURAL and gate.ground is Ground.COMPUTATION
    assert KERNEL_GATES["pointer-resolution"].serves == ["provenance"]
    assert KERNEL_GATES["provenance-present"].serves == ["provenance"]
    assert KERNEL_GATES["scaffold-absent"].serves == ["scaffold"]
    assert KERNEL_GATES["schema-valid"].serves == ["format"]
    assert KERNEL_GATES["length-bound"].serves == ["length"]


def test_only_length_bound_is_an_optional_kernel_gate():
    required = sorted(gate_id for gate_id, gate in KERNEL_GATES.items() if gate.required)

    assert required == ["pointer-resolution", "provenance-present", "scaffold-absent", "schema-valid"]
    assert KERNEL_GATES["length-bound"].required is False


def test_kernel_gate_declare_builds_a_kernel_executed_decl():
    decl = KERNEL_GATES["scaffold-absent"].declare(["outline", "write"])

    assert decl.id == "scaffold-absent"
    assert decl.executor is Executor.KERNEL
    assert decl.serves == ["scaffold"] and decl.applies_to == ["outline", "write"]
    assert decl.calibration == {"status": "deterministic"}
    assert decl.applies("write") and not decl.applies("spec")
    assert KERNEL_GATES["scaffold-absent"].declare(["all"]).applies("spec")


def test_kernel_gate_run_records_who_checked_what(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    crit = Criterion("c-prov", "pointers resolve", "provenance", Ground.COMPUTATION)
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, h1))}, [crit], n=3)

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.PASS
    assert result.gate == "pointer-resolution"
    assert result.step == "write" and result.pass_id == "write#3"
    assert result.criteria == ["c-prov"]
    assert result.findings == []
    assert result.produced_by == "kernel"
    assert result.executor is Executor.KERNEL
    assert result.kind is GateKind.STRUCTURAL and result.ground is Ground.COMPUTATION
    assert result.calibration == {"status": "deterministic"}
    assert result.schema == GATE_RESULT_SCHEMA


# --- pointer-resolution ------------------------------------------------------------------------


def test_pointer_resolution_passes_when_every_pointer_resolves(tmp_path):
    store = make_store(tmp_path)
    h1, h2 = stored(store, "passage one"), stored(store, "passage two")
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, h1), statement("s2", S2, h1, h2))})

    assert KERNEL_GATES["pointer-resolution"].run(ctx).verdict is Verdict.PASS


def test_pointer_resolution_fails_on_evidence_the_step_was_not_given(tmp_path):
    store = make_store(tmp_path)
    given, foreign = stored(store, "passage one"), stored(store, "an earlier pass's output")
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, given), statement("s2", S2, foreign))})

    result = KERNEL_GATES["pointer-resolution"].run(replace(ctx, inputs={given}))

    assert result.verdict is Verdict.FAIL
    assert [f.statement for f in result.findings] == ["s2"]
    assert "was not given" in result.findings[0].message
    assert KERNEL_GATES["pointer-resolution"].run(ctx).verdict is Verdict.PASS  # inputs unknown: resolution only


def test_pointer_resolution_fails_on_a_hash_the_store_does_not_have(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    ghost = "f" * 64
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, h1), statement("s2", S2, ghost))})

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.statement == "s2"
    assert "unresolvable evidence" in finding.message and ghost[:12] in finding.message


def test_pointer_resolution_fails_closed_on_a_tampered_object(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    (store.objects / h1).write_bytes(b"rewritten after the fact")
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, h1))})

    with pytest.raises(EvidenceCorrupt, match="does not match"):
        KERNEL_GATES["pointer-resolution"].run(ctx)


def test_pointer_resolution_fails_on_a_statement_with_no_evidence(tmp_path):
    store = make_store(tmp_path)
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1))})

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert [f.message for f in result.findings] == ["statement s1 cites no evidence"]
    assert result.findings[0].statement == "s1"


def test_pointer_resolution_fails_on_a_statement_whose_evidence_is_null(tmp_path):
    store = make_store(tmp_path)
    data = json.dumps({"schema": STATEMENTS_SCHEMA, "statements": [{"id": "s1", "text": S1, "evidence": None}]})
    ctx = make_ctx(store, {"statements.json": data.encode("utf-8")})

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert "statements[0]" in result.findings[0].message and "null" in result.findings[0].message


def test_pointer_resolution_fails_when_statements_are_not_an_output(tmp_path):
    store = make_store(tmp_path)
    ctx = make_ctx(store, {"brief.md": b"Body.\n"})

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message == "statements.json is not an output of step write"


def test_pointer_resolution_surfaces_statement_parse_problems(tmp_path):
    store = make_store(tmp_path)
    ctx = make_ctx(store, {"statements.json": b"{oops"})

    result = KERNEL_GATES["pointer-resolution"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message.startswith("statements: not valid JSON")


# --- provenance-present -------------------------------------------------------------------------


def test_provenance_present_passes_when_each_paragraph_carries_a_statement(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    body = (
        "---\ntitle: Brief\n---\n\n# Title\n\n"
        "Agents retrieve papers\nbefore   they read them.\n\n"
        "In short: Retrieval  precision drives downstream quality. Nothing else matters.\n"
    )
    outputs = {
        "brief.md": body.encode("utf-8"),
        "statements.json": statements_json(statement("s1", S1, h1), statement("s2", S2, h1)),
    }

    result = KERNEL_GATES["provenance-present"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.PASS, [f.message for f in result.findings]


def test_provenance_present_fails_for_a_paragraph_with_no_statement(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    body = f"# Title\n\n{S1}\n\nThis paragraph was written without any statement behind it.\n"
    outputs = {"brief.md": body.encode("utf-8"), "statements.json": statements_json(statement("s1", S1, h1))}

    result = KERNEL_GATES["provenance-present"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.FAIL
    assert len(result.findings) == 1
    assert result.findings[0].message.startswith("paragraph 2 has no statement with evidence")
    assert "written without any statement" in result.findings[0].message


def test_provenance_present_ignores_statements_that_cite_no_evidence(tmp_path):
    store = make_store(tmp_path)
    outputs = {"brief.md": f"{S1}\n".encode("utf-8"), "statements.json": statements_json(statement("s1", S1))}

    result = KERNEL_GATES["provenance-present"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message.startswith("paragraph 1 has no statement with evidence")


def test_provenance_present_fails_when_the_deliverable_is_missing(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    ctx = make_ctx(store, {"statements.json": statements_json(statement("s1", S1, h1))})

    result = KERNEL_GATES["provenance-present"].run(ctx)

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message == "brief.md is not an output of step write"


def test_provenance_present_uses_the_context_deliverable_and_statements_names(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    outputs = {"tutorial.md": f"{S1}\n".encode("utf-8"), "claims.json": statements_json(statement("s1", S1, h1))}
    ctx = make_ctx(store, outputs, deliverable="tutorial.md", statements="claims.json")

    assert KERNEL_GATES["provenance-present"].run(ctx).verdict is Verdict.PASS


# --- scaffold-absent ------------------------------------------------------------------------------


def test_scaffold_absent_passes_on_clean_outputs(tmp_path):
    store = make_store(tmp_path)
    outputs = {"brief.md": b"# Title\n\nAll done.\n", "outline.yml": b"sections: [a]\n"}

    assert KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs)).verdict is Verdict.PASS


def test_scaffold_absent_catches_the_default_scaffold_marker(tmp_path):
    store = make_store(tmp_path)
    outputs = {"brief.md": b"# Title\n\n<!-- scaffold -->\nfill me in\n"}

    result = KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message == "brief.md still contains the scaffold marker '<!-- scaffold -->'"


def test_scaffold_absent_uses_the_producer_skills_declared_marker(tmp_path):
    store = make_store(tmp_path)
    producer = make_skill(front={"scaffold_marker": "[[DRAFT]]"})
    outputs = {"brief.md": b"Intro [[DRAFT]] more\n", "notes.md": b"<!-- scaffold --> is not this producer's marker\n"}

    result = KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs, producer=producer))

    assert [f.message for f in result.findings] == ["brief.md still contains the scaffold marker '[[DRAFT]]'"]


@pytest.mark.parametrize("token", ["TODO", "TBD", "FIXME", "XXX"])
def test_scaffold_absent_catches_placeholder_tokens(tmp_path, token):
    store = make_store(tmp_path)
    outputs = {"outline.yml": f"sections:\n  - {token}: write this later\n".encode("utf-8")}

    result = KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message == f"outline.yml contains placeholder token {token!r}"


def test_scaffold_absent_matches_placeholders_as_whole_words_only(tmp_path):
    store = make_store(tmp_path)
    outputs = {"brief.md": b"The TODOS package and the XXXL size are fine.\n"}

    assert KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs)).verdict is Verdict.PASS


def test_scaffold_absent_reports_every_output_separately(tmp_path):
    store = make_store(tmp_path)
    outputs = {"brief.md": b"TODO\n", "outline.yml": b"<!-- scaffold -->\nTBD\n"}

    result = KERNEL_GATES["scaffold-absent"].run(make_ctx(store, outputs))

    assert [f.message for f in result.findings] == [
        "brief.md contains placeholder token 'TODO'",
        "outline.yml still contains the scaffold marker '<!-- scaffold -->'",
        "outline.yml contains placeholder token 'TBD'",
    ]


# --- schema-valid --------------------------------------------------------------------------------


def test_schema_valid_passes_well_formed_outputs(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "passage one")
    outputs = {
        "brief.md": b"# anything goes in markdown {\n",
        "statements.json": statements_json(statement("s1", S1, h1)),
        "meta.json": b'{"a": [1, 2]}',
        "papers_raw.jsonl": b'{"id": 1}\n\n{"id": 2}\n',
        "outline.yml": b"sections:\n  - intro\n",
        "core_set.csv": b"id,title\n1,A\n2,B\n",
    }

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    assert result.verdict is Verdict.PASS, [f.message for f in result.findings]


def test_schema_valid_catches_bad_json(tmp_path):
    store = make_store(tmp_path)

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, {"meta.json": b'{"a": '}))

    assert result.verdict is Verdict.FAIL
    assert result.findings[0].message.startswith("meta.json does not parse:")


def test_schema_valid_catches_bad_and_empty_jsonl(tmp_path):
    store = make_store(tmp_path)
    outputs = {"bad.jsonl": b'{"id": 1}\nnot json\n', "empty.jsonl": b"\n\n"}

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    messages = [f.message for f in result.findings]
    assert messages[0].startswith("bad.jsonl does not parse:")
    assert messages[1] == "empty.jsonl has no records"


def test_schema_valid_catches_bad_and_empty_yaml(tmp_path):
    store = make_store(tmp_path)
    outputs = {"bad.yaml": b"sections: [intro\n", "empty.yml": b"# only a comment\n"}

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    messages = [f.message for f in result.findings]
    assert messages[0].startswith("bad.yaml does not parse:")
    assert messages[1] == "empty.yml is empty"


def test_schema_valid_catches_headerless_and_ragged_csv_but_allows_an_empty_table(tmp_path):
    store = make_store(tmp_path)
    outputs = {"header.csv": b"id,title\n", "empty.csv": b"", "ragged.csv": b"id,title\n1,A\n2\n"}

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    assert [f.message for f in result.findings] == [
        "empty.csv has no header",
        "ragged.csv has ragged rows",
    ]


def test_schema_valid_reads_tsv_by_tabs(tmp_path):
    store = make_store(tmp_path)
    outputs = {
        "ok.tsv": b"claim_id\trelated\tdelta, with comma\nCL1\tref:3\tnew axis, same task\n",
        "ragged.tsv": b"a\tb\n1\t2\t3\n",
    }

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    assert [f.message for f in result.findings] == ["ragged.tsv has ragged rows"]


def test_schema_valid_checks_the_statements_index_by_its_own_schema(tmp_path):
    store = make_store(tmp_path)
    outputs = {"statements.json": statements_json(statement("s1", S1, "h"), schema="rh.statements/0")}

    result = KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs))

    assert [f.message for f in result.findings] == [f"statements: schema must be {STATEMENTS_SCHEMA}"]


def test_schema_valid_ignores_unknown_extensions(tmp_path):
    store = make_store(tmp_path)
    outputs = {"notes.txt": b"{[not json but nobody asked", "brief.md": b"{"}

    assert KERNEL_GATES["schema-valid"].run(make_ctx(store, outputs)).verdict is Verdict.PASS


# --- length-bound ----------------------------------------------------------------------------------


def eight_words() -> bytes:
    return b"---\ntitle: x\n---\n\n# Heading words do not count\n\none two three four\nfive six seven eight\n"


def test_length_bound_passes_within_the_criterion_bounds(tmp_path):
    store = make_store(tmp_path)
    crit = Criterion("c-length", "short", "length", Ground.COMPUTATION, params={"min_words": 5, "max_words": 8})

    result = KERNEL_GATES["length-bound"].run(make_ctx(store, {"brief.md": eight_words()}, [crit]))

    assert result.verdict is Verdict.PASS
    assert result.criteria == ["c-length"]


def test_length_bound_fails_over_max_words_and_names_the_criterion(tmp_path):
    store = make_store(tmp_path)
    crit = Criterion("c-length", "short", "length", Ground.COMPUTATION, params={"max_words": 5})

    result = KERNEL_GATES["length-bound"].run(make_ctx(store, {"brief.md": eight_words()}, [crit]))

    assert result.verdict is Verdict.FAIL
    assert len(result.findings) == 1
    assert result.findings[0].criterion == "c-length"
    assert result.findings[0].message == "brief.md has 8 words, over 5"


def test_length_bound_fails_under_min_words(tmp_path):
    store = make_store(tmp_path)
    crit = Criterion("c-length", "long enough", "length", Ground.COMPUTATION, params={"min_words": 20})

    result = KERNEL_GATES["length-bound"].run(make_ctx(store, {"brief.md": eight_words()}, [crit]))

    assert result.findings[0].criterion == "c-length"
    assert result.findings[0].message == "brief.md has 8 words, under 20"


def test_length_bound_checks_each_criterion_separately(tmp_path):
    store = make_store(tmp_path)
    criteria = [
        Criterion("c-a", "a", "length", Ground.COMPUTATION, params={"max_words": 3}),
        Criterion("c-b", "b", "length", Ground.COMPUTATION, params={"min_words": 50}),
        Criterion("c-c", "no params", "length", Ground.COMPUTATION),
    ]

    result = KERNEL_GATES["length-bound"].run(make_ctx(store, {"brief.md": eight_words()}, criteria))

    assert [f.criterion for f in result.findings] == ["c-a", "c-b"]


def test_length_bound_passes_when_the_deliverable_is_not_among_the_outputs(tmp_path):
    store = make_store(tmp_path)
    crit = Criterion("c-length", "short", "length", Ground.COMPUTATION, params={"max_words": 1})

    result = KERNEL_GATES["length-bound"].run(make_ctx(store, {"outline.yml": b"a: b\n"}, [crit]))

    assert result.verdict is Verdict.PASS and result.findings == []


# --- validate_agent_result ---------------------------------------------------------------------------


def decl() -> GateDecl:
    return GateDecl(
        id="source-support",
        kind=GateKind.GROUNDED,
        ground=Ground.SOURCE,
        executor=Executor.AGENT,
        serves=["supported"],
        applies_to=["write"],
        routing="upstream_of_cited_evidence",
        skill="source-support-prover",
        calibration={"status": "unmeasured", "corpus": None},
    )


def passes() -> tuple[Pass, Pass]:
    checked = Pass("write#1", "write", 1, Role.PRODUCER, skill_identity=PRODUCER_IDENTITY)
    prover = Pass("source-support#1", "write", 1, Role.PROVER, gate="source-support", skill_identity=PROVER_IDENTITY)
    return prover, checked


CRITERIA = [Criterion("c-supported", "every statement cites a retrieved source", "supported", Ground.SOURCE)]


def admit(store, raw: bytes, *, prover=None, producer=None, criteria=None):
    prover_pass, checked_pass = passes()
    return validate_agent_result(
        raw,
        decl(),
        prover_pass,
        checked_pass,
        CRITERIA if criteria is None else criteria,
        store,
        prover or make_skill("source-support-prover", PROVER_IDENTITY, {"role": "prover"}),
        producer or make_skill(),
    )


def refuse(store, raw: bytes, **kwargs) -> list[str]:
    with pytest.raises(GateResultInvalid) as info:
        admit(store, raw, **kwargs)
    assert str(info.value) == "; ".join(info.value.problems)
    return info.value.problems


def test_validate_admits_a_well_formed_passing_result(tmp_path):
    store = make_store(tmp_path)

    result = admit(store, gate_result_json(score=0.9))

    assert result.verdict is Verdict.PASS
    assert result.gate == "source-support"
    assert result.step == "write" and result.pass_id == "write#1"
    assert result.criteria == ["c-supported"]
    assert result.score == 0.9 and isinstance(result.score, float)
    assert result.findings == []
    assert result.produced_by == PROVER_IDENTITY
    assert result.executor is Executor.AGENT
    assert result.schema == GATE_RESULT_SCHEMA


def test_validate_carries_the_decls_kind_ground_and_calibration(tmp_path):
    store = make_store(tmp_path)
    declared = decl()
    declared.kind = GateKind.CALIBRATED
    declared.ground = Ground.COMPUTATION
    declared.calibration = {"status": "measured", "agreement": 0.8}
    prover_pass, checked_pass = passes()

    result = validate_agent_result(
        gate_result_json(),
        declared,
        prover_pass,
        checked_pass,
        CRITERIA,
        store,
        make_skill("source-support-prover", PROVER_IDENTITY),
        make_skill(),
    )

    assert result.kind is GateKind.CALIBRATED
    assert result.ground is Ground.COMPUTATION
    assert result.calibration == {"status": "measured", "agreement": 0.8}
    assert result.calibration is not declared.calibration  # a copy, not the decl's own dict
    result.calibration["status"] = "edited"
    assert declared.calibration["status"] == "measured"


def test_validate_records_the_skill_used_when_the_packet_was_opened(tmp_path):
    updated = make_skill("source-support-prover", "f" * 64)
    result = admit(make_store(tmp_path), gate_result_json(), prover=updated)
    assert result.produced_by == PROVER_IDENTITY


def test_validate_admits_a_failing_result_whose_findings_cite_evidence(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "the cited passage")
    raw = gate_result_json(
        verdict="fail",
        score=0.2,
        findings=[
            {
                "message": "statement s3 is not supported by the cited passage",
                "evidence": [h1],
                "statement": "s3",
                "criterion": "c-supported",
                "implicates": "retrieve",
            },
            {"message": "a second, evidence-free observation"},
        ],
    )

    result = admit(store, raw)

    assert result.verdict is Verdict.FAIL
    assert result.score == 0.2
    assert [f.statement for f in result.findings] == ["s3", None]
    assert result.findings[0].evidence == [h1]
    assert result.findings[0].implicates == "retrieve"


def test_validate_admits_a_result_without_a_score(tmp_path):
    store = make_store(tmp_path)

    assert admit(store, gate_result_json()).score is None


def test_validate_refuses_bytes_that_are_not_json(tmp_path):
    store = make_store(tmp_path)

    problems = refuse(store, b"PASS\n")

    assert len(problems) == 1 and problems[0].startswith("gate_result.json is not valid JSON")


def test_validate_refuses_a_non_object(tmp_path):
    store = make_store(tmp_path)

    assert refuse(store, b'["pass"]') == ["gate_result.json must be an object"]


def test_validate_refuses_the_wrong_schema(tmp_path):
    store = make_store(tmp_path)

    assert refuse(store, gate_result_json(schema="rh.gate_result/0")) == [f"schema must be {GATE_RESULT_SCHEMA}"]


def test_validate_refuses_the_wrong_gate(tmp_path):
    store = make_store(tmp_path)

    assert refuse(store, gate_result_json(gate="spec-coverage")) == [
        "gate must be 'source-support', got 'spec-coverage'"
    ]


def test_validate_refuses_the_provers_own_pass_id(tmp_path):
    store = make_store(tmp_path)

    problems = refuse(store, gate_result_json(pass_id="source-support#1"))

    assert problems == ["pass_id must be 'write#1' (the pass under check)"]


def test_validate_refuses_the_wrong_step(tmp_path):
    store = make_store(tmp_path)

    assert refuse(store, gate_result_json(step="outline")) == ["step must be 'write'"]


@pytest.mark.parametrize("verdict", ["PASS", "maybe", None, 1])
def test_validate_refuses_an_unknown_verdict(tmp_path, verdict):
    store = make_store(tmp_path)

    problems = refuse(store, gate_result_json(verdict=verdict))

    assert "verdict must be 'pass' or 'fail'" in problems


@pytest.mark.parametrize("score", [-0.1, 1.5, "0.5"])
def test_validate_refuses_a_score_outside_zero_one_or_not_a_number(tmp_path, score):
    store = make_store(tmp_path)

    assert refuse(store, gate_result_json(score=score)) == ["score must be a number in [0, 1]"]


def test_validate_admits_boundary_scores_as_floats(tmp_path):
    store = make_store(tmp_path)

    assert admit(store, gate_result_json(score=0)).score == 0.0
    assert admit(store, gate_result_json(score=1)).score == 1.0


def test_validate_refuses_a_failing_verdict_with_no_findings(tmp_path):
    store = make_store(tmp_path)

    problems = refuse(store, gate_result_json(verdict="fail", findings=[]))

    assert problems == [
        "a failing verdict must carry at least one finding",
        "a failing verdict must cite Evidence in at least one finding",
    ]


def test_validate_refuses_a_failing_verdict_whose_findings_cite_no_evidence(tmp_path):
    store = make_store(tmp_path)
    raw = gate_result_json(verdict="fail", findings=[{"message": "feels unsupported", "statement": "s3"}])

    assert refuse(store, raw) == ["a failing verdict must cite Evidence in at least one finding"]


def test_validate_refuses_a_finding_citing_an_unresolvable_hash(tmp_path):
    store = make_store(tmp_path)
    good = stored(store, "the cited passage")
    ghost = "e" * 64
    raw = gate_result_json(verdict="fail", findings=[{"message": "m", "evidence": [good, ghost]}])

    problems = refuse(store, raw)

    assert problems == [f"findings[0] cites unresolvable evidence {[ghost[:12]]}"]


def test_validate_refuses_a_finding_citing_tampered_evidence(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "the cited passage")
    (store.objects / h1).write_bytes(b"rewritten")
    raw = gate_result_json(verdict="fail", findings=[{"message": "m", "evidence": [h1]}])

    assert refuse(store, raw)[0].startswith("findings[0] cites unresolvable evidence")


def test_validate_refuses_a_finding_naming_an_unknown_criterion(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "the cited passage")
    raw = gate_result_json(verdict="fail", findings=[{"message": "m", "evidence": [h1], "criterion": "c-novelty"}])

    assert refuse(store, raw) == ["finding names unknown criterion 'c-novelty'"]


def test_validate_refuses_a_finding_that_is_not_well_formed(tmp_path):
    store = make_store(tmp_path)
    h1 = stored(store, "the cited passage")
    raw = gate_result_json(verdict="fail", findings=[{"evidence": [h1]}, {"message": "ok", "evidence": [h1]}])

    problems = refuse(store, raw)

    assert len(problems) == 1 and problems[0].startswith("findings[0]:")


def test_validate_refuses_a_prover_that_is_the_producer(tmp_path):
    store = make_store(tmp_path)
    same = make_skill("brief-writer", PRODUCER_IDENTITY)

    problems = refuse(store, gate_result_json(), prover=same, producer=make_skill("brief-writer", PRODUCER_IDENTITY))

    assert problems == ["prover Skill 'brief-writer' is the producer Skill; a step may not verify itself"]


def test_validate_judges_identity_by_hash_not_by_name(tmp_path):
    store = make_store(tmp_path)
    prover = make_skill("brief-writer", PROVER_IDENTITY)  # same name, different SKILL.md bytes
    producer = make_skill("brief-writer", PRODUCER_IDENTITY)

    assert admit(store, gate_result_json(), prover=prover, producer=producer).produced_by == PROVER_IDENTITY

    renamed = make_skill("source-support-prover", PRODUCER_IDENTITY)  # different name, same bytes
    assert refuse(store, gate_result_json(), prover=renamed, producer=producer)[0].startswith("prover Skill")


def test_validate_reports_every_problem_at_once(tmp_path):
    store = make_store(tmp_path)
    raw = gate_result_json(schema="x", gate="y", step="z", pass_id="w", verdict="fail", score=7, findings=[])

    problems = refuse(store, raw, prover=make_skill("brief-writer"))

    assert problems == [
        f"schema must be {GATE_RESULT_SCHEMA}",
        "gate must be 'source-support', got 'y'",
        "step must be 'write'",
        "pass_id must be 'write#1' (the pass under check)",
        "score must be a number in [0, 1]",
        "prover Skill 'brief-writer' is the producer Skill; a step may not verify itself",
        "a failing verdict must carry at least one finding",
        "a failing verdict must cite Evidence in at least one finding",
    ]


def test_validate_refuses_a_finding_whose_evidence_is_null(tmp_path):
    store = make_store(tmp_path)
    raw = gate_result_json(verdict="fail", findings=[{"message": "m", "evidence": None}])

    assert refuse(store, raw)  # any GateResultInvalid is acceptable; a TypeError is not


def test_validate_refuses_a_finding_whose_evidence_entries_are_not_hashes(tmp_path):
    store = make_store(tmp_path)
    raw = gate_result_json(verdict="fail", findings=[{"message": "m", "evidence": [123]}])

    assert refuse(store, raw)


def test_validate_never_admits_a_self_reported_pass_line(tmp_path):
    """The kernel reads a GateResult, never a ``Status: PASS`` line."""
    store = make_store(tmp_path)

    with pytest.raises(GateResultInvalid):
        admit(store, b"Status: PASS\n")
