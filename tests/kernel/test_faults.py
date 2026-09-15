"""Faults: one per finding, each routed on its own evidence."""

from __future__ import annotations

from helpers import make_store, sample_run_state

from rh.kernel import faults
from rh.kernel.records import Executor, Finding, GateDecl, GateKind, GateResult, Ground, Verdict


def decl(routing: str) -> GateDecl:
    return GateDecl("source-support", GateKind.GROUNDED, Ground.SOURCE, Executor.AGENT, serves=["supported"], routing=routing)


def failing(*findings: Finding) -> GateResult:
    return GateResult("source-support", "write", "write#2", Verdict.FAIL, criteria=["c-supported"], findings=list(findings), ground=Ground.SOURCE)


def test_one_fault_per_finding_each_with_its_own_message_and_evidence(tmp_path):
    state, store = sample_run_state(), make_store(tmp_path)
    h1, h2 = store.put_text("a", "sources/a.md", "retrieve#1").hash, store.put_text("b", "sources/b.md", "retrieve#1").hash

    out = faults.from_result(state, store, failing(Finding("s1 overstates", [h1], statement="s1"), Finding("s3 misreads", [h2], criterion="c-supported")), decl("checked_step"))

    assert [f.message for f in out] == ["s1 overstates", "s3 misreads"]
    assert [f.evidence for f in out] == [[h1], [h2]]
    assert [f.id for f in out] == [f"F{len(state.faults) + 1:03d}", f"F{len(state.faults) + 2:03d}"]
    assert {f.criterion for f in out} == {"c-supported"} and {f.step for f in out} == {"write"}


def test_a_finding_less_failure_still_yields_one_fault(tmp_path):
    state, store = sample_run_state(), make_store(tmp_path)

    out = faults.from_result(state, store, failing(), decl("checked_step"))

    assert len(out) == 1 and out[0].message == "gate source-support failed on write#2"


def test_upstream_routing_honours_implicates_only_when_that_step_produced_the_cited_evidence(tmp_path):
    state, store = sample_run_state(), make_store(tmp_path)
    upstream = store.put_text("paper", "sources/a.md", "retrieve#1").hash
    own = store.put_text("brief", "brief.md", "write#1").hash
    result = failing(
        Finding("wrong paper retrieved", [upstream], implicates="retrieve"),
        Finding("claims what the source does not say", [own], implicates="retrieve"),
        Finding("implicates a step that is not upstream", [upstream], implicates="curate-not-a-step"),
    )

    out = faults.from_result(state, store, result, decl("upstream_of_cited_evidence"))

    assert [f.step for f in out] == ["retrieve", "write", "write"]
    assert [f.step for f in faults.from_result(state, store, result, decl("checked_step"))] == ["write", "write", "write"]
