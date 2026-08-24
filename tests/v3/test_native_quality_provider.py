"""Contract tests for the native quality-check provider slice.

``NativeQualityProvider`` is the tooling-free step behind the
``QualityCheckProvider`` Port.  It answers registry introspection from native
constant tables and reimplements the self-contained semantic checks
(``citation-injector``, ``deliverable-selfloop``, ``artifact-contract-auditor``,
and ``beamer-compile-qa``), delegating everything else to the legacy adapter.
These tests lock in:

- Port conformance (``isinstance`` of the runtime-checkable Protocol);
- registry parity with the legacy provider (the native constant tables must
  not drift from ``tooling.quality_gate``);
- native behavior for each natively-covered skill matching the legacy check
  exactly (byte-for-byte codes + messages) across representative inputs;
- delegation to the composed legacy adapter for a non-native skill; and
- that ``native.py`` imports no ``tooling`` symbols at module top.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import research_harness.acceptance.native as native_module
from research_harness.acceptance import (
    LegacyToolingQualityProvider,
    NativeQualityProvider,
    QualityCheckProvider,
    default_quality_provider,
)


def test_native_provider_satisfies_the_port() -> None:
    provider = NativeQualityProvider()
    assert isinstance(provider, QualityCheckProvider)


def test_registered_skills_match_legacy_exactly() -> None:
    # Parity: the native constant table must equal the legacy registry so it
    # cannot silently diverge from tooling.quality_gate.
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    assert isinstance(legacy, LegacyToolingQualityProvider)
    assert native.registered_quality_skills() == legacy.registered_quality_skills()
    assert len(native.registered_quality_skills()) > 0


def test_completion_invariant_flags_match_legacy() -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    for skill in native.registered_quality_skills():
        assert native.has_completion_invariant(skill) == legacy.has_completion_invariant(
            skill
        )
    assert native.has_completion_invariant("no-such-skill-xyz") is False


def test_default_provider_is_still_legacy() -> None:
    # The native provider is added but not yet the default; swapping the
    # default is a later gated step.
    assert isinstance(default_quality_provider(), LegacyToolingQualityProvider)


def _write_report(workspace: Path, body: str) -> None:
    report = workspace / "output" / "CITATION_INJECTION_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(body, encoding="utf-8")


def test_native_citation_injector_pass(tmp_path: Path) -> None:
    _write_report(tmp_path, "# Report\n\n- Status: PASS\n- Injected: 3\n")
    native = NativeQualityProvider()
    assert (
        native.check_unit_outputs(
            skill="citation-injector",
            workspace=tmp_path,
            outputs=["output/CITATION_INJECTION_REPORT.md"],
        )
        == []
    )


def test_native_citation_injector_matches_legacy_across_cases(tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    outputs = ["output/CITATION_INJECTION_REPORT.md"]

    cases = {
        "missing": None,
        "empty": "",
        "placeholder": "# Report\n\n- Status: PASS\nTODO: finish\n",
        "ellipsis": "# Report\n\n- Status: PASS\n- Note: more…\n",
        "not_pass": "# Report\n\n- Status: FAIL\n",
        "pass": "# Report\n\n- Status: PASS\n- Injected: 5\n",
    }
    for name, body in cases.items():
        ws = tmp_path / name
        ws.mkdir()
        if body is not None:
            _write_report(ws, body)

        native_issues = native.check_unit_outputs(
            skill="citation-injector", workspace=ws, outputs=outputs
        )
        legacy_issues = legacy.check_unit_outputs(
            skill="citation-injector", workspace=ws, outputs=outputs
        )
        native_pairs = [(i.code, i.message) for i in native_issues]
        legacy_pairs = [(i.code, i.message) for i in legacy_issues]
        assert native_pairs == legacy_pairs, name


def _write_file(workspace: Path, rel: str, body: str) -> None:
    path = workspace / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# --- deliverable-selfloop parity -------------------------------------------


_DELIVERABLE_OUT = ["output/DELIVERABLE_SELFLOOP_TODO.md"]
_DELIVERABLE_REL = "output/DELIVERABLE_SELFLOOP_TODO.md"

_DELIVERABLE_CASES: dict[str, str | None] = {
    "missing": None,
    "empty": "",
    "placeholder": "# Report\nTODO: finish\n- Status: PASS\n",
    "ellipsis": "# Report\n- Status: PASS\n- Note: more…\n",
    "not_pass": "# Report\n- Status: FAIL\n",
    "pass": "# Report\n- Status: PASS\n- Fixed: 3\n",
}


@pytest.mark.parametrize("name", sorted(_DELIVERABLE_CASES))
def test_native_deliverable_selfloop_matches_legacy(name: str, tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    body = _DELIVERABLE_CASES[name]
    ws = tmp_path / name
    ws.mkdir()
    if body is not None:
        _write_file(ws, _DELIVERABLE_REL, body)

    native_pairs = [
        (i.code, i.message)
        for i in native.check_unit_outputs(
            skill="deliverable-selfloop", workspace=ws, outputs=_DELIVERABLE_OUT
        )
    ]
    legacy_pairs = [
        (i.code, i.message)
        for i in legacy.check_unit_outputs(
            skill="deliverable-selfloop", workspace=ws, outputs=_DELIVERABLE_OUT
        )
    ]
    assert native_pairs == legacy_pairs, name


def test_native_deliverable_selfloop_default_output_path(tmp_path: Path) -> None:
    # With empty outputs both providers fall back to the canonical relative path.
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    _write_file(tmp_path, _DELIVERABLE_REL, "# ok\n- Status: PASS\n")
    assert (
        native.check_unit_outputs(
            skill="deliverable-selfloop", workspace=tmp_path, outputs=[]
        )
        == legacy.check_unit_outputs(
            skill="deliverable-selfloop", workspace=tmp_path, outputs=[]
        )
        == []
    )


# --- artifact-contract-auditor parity --------------------------------------


_CONTRACT_OUT = ["output/CONTRACT_REPORT.md"]
_CONTRACT_REL = "output/CONTRACT_REPORT.md"
_CONTRACT_PASS = "- Status: PASS\n- Pipeline complete (units): yes\n"

_CONTRACT_CASES: dict[str, str | None] = {
    "missing": None,
    "empty": "",
    "whitespace": "   \n  \n",
    "placeholder": "TBD\n" + _CONTRACT_PASS,
    "ellipsis": "…\n" + _CONTRACT_PASS,
    "status_only": "- Status: PASS\n",
    "complete_only": "- Pipeline complete (units): yes\n",
    "pass": _CONTRACT_PASS,
}


@pytest.mark.parametrize("name", sorted(_CONTRACT_CASES))
def test_native_contract_auditor_matches_legacy(name: str, tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    body = _CONTRACT_CASES[name]
    ws = tmp_path / name
    ws.mkdir()
    if body is not None:
        _write_file(ws, _CONTRACT_REL, body)

    native_pairs = [
        (i.code, i.message)
        for i in native.check_unit_outputs(
            skill="artifact-contract-auditor", workspace=ws, outputs=_CONTRACT_OUT
        )
    ]
    legacy_pairs = [
        (i.code, i.message)
        for i in legacy.check_unit_outputs(
            skill="artifact-contract-auditor", workspace=ws, outputs=_CONTRACT_OUT
        )
    ]
    assert native_pairs == legacy_pairs, name


def test_native_contract_auditor_default_output_path(tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    _write_file(tmp_path, _CONTRACT_REL, _CONTRACT_PASS)
    assert (
        native.check_unit_outputs(
            skill="artifact-contract-auditor", workspace=tmp_path, outputs=[]
        )
        == legacy.check_unit_outputs(
            skill="artifact-contract-auditor", workspace=tmp_path, outputs=[]
        )
        == []
    )


# --- beamer-compile-qa parity ----------------------------------------------


_BEAMER_OUT = ["latex/slides/main.pdf", "output/SLIDES_BUILD_REPORT.md"]
_BEAMER_PDF = "latex/slides/main.pdf"
_BEAMER_REPORT = "output/SLIDES_BUILD_REPORT.md"

# Each case is (pdf_body, report_body); ``None`` means the file is absent.
_BEAMER_CASES: dict[str, tuple[str | None, str | None]] = {
    "missing_pdf": (None, "- Status: PASS\n"),
    "missing_report": ("%PDF-1.4\n", None),
    "not_pass": ("%PDF-1.4\n", "# build\n- Status: FAIL\n"),
    "pass_dash": ("%PDF-1.4\n", "# build\n- Status: PASS\n"),
    "pass_bare": ("%PDF-1.4\n", "Status: PASS\n"),
}


@pytest.mark.parametrize("name", sorted(_BEAMER_CASES))
def test_native_beamer_compile_qa_matches_legacy(name: str, tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    pdf_body, report_body = _BEAMER_CASES[name]
    ws = tmp_path / name
    ws.mkdir()
    if pdf_body is not None:
        _write_file(ws, _BEAMER_PDF, pdf_body)
    if report_body is not None:
        _write_file(ws, _BEAMER_REPORT, report_body)

    native_pairs = [
        (i.code, i.message)
        for i in native.check_unit_outputs(
            skill="beamer-compile-qa", workspace=ws, outputs=_BEAMER_OUT
        )
    ]
    legacy_pairs = [
        (i.code, i.message)
        for i in legacy.check_unit_outputs(
            skill="beamer-compile-qa", workspace=ws, outputs=_BEAMER_OUT
        )
    ]
    assert native_pairs == legacy_pairs, name


def test_native_beamer_compile_qa_default_output_paths(tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    _write_file(tmp_path, _BEAMER_PDF, "%PDF-1.4\n")
    _write_file(tmp_path, _BEAMER_REPORT, "- Status: PASS\n")
    assert (
        native.check_unit_outputs(
            skill="beamer-compile-qa", workspace=tmp_path, outputs=[]
        )
        == legacy.check_unit_outputs(
            skill="beamer-compile-qa", workspace=tmp_path, outputs=[]
        )
        == []
    )


def test_delegates_non_native_skill_to_composed_legacy(tmp_path: Path) -> None:
    # A non-native skill's check_unit_outputs is routed to the composed legacy
    # adapter, so behavior matches the legacy provider exactly.
    calls: list[tuple[str, str]] = []

    class _SpyLegacy:
        def registered_quality_skills(self) -> frozenset[str]:
            return frozenset()

        def has_completion_invariant(self, skill: str) -> bool:
            return False

        def check_completion_invariants(
            self, *, skill: str, workspace: Path, outputs: list[str]
        ) -> list[object]:
            calls.append(("invariants", skill))
            return []

        def check_unit_outputs(
            self, *, skill: str, workspace: Path, outputs: list[str]
        ) -> list[object]:
            calls.append(("outputs", skill))
            return []

    native = NativeQualityProvider(legacy=_SpyLegacy())

    # Non-native skill -> delegated. (source-ingest is registered but has no
    # native reimplementation -- the whole survey-retrieval family is native,
    # but source-tutorial checks still delegate -- so it must route to the
    # composed legacy adapter.)
    native.check_unit_outputs(
        skill="source-ingest", workspace=tmp_path, outputs=[]
    )
    # Completion invariants always delegated (none reimplemented yet).
    native.check_completion_invariants(
        skill="outline-refiner", workspace=tmp_path, outputs=[]
    )
    # Native skill -> NOT delegated.
    native.check_unit_outputs(
        skill="citation-injector",
        workspace=tmp_path,
        outputs=["output/CITATION_INJECTION_REPORT.md"],
    )
    for native_skill in (
        "deliverable-selfloop",
        "artifact-contract-auditor",
        "beamer-compile-qa",
        "beamer-scaffold",
        # policy-consuming native skills route through the policy table, still
        # not delegated to legacy.
        "citation-verifier",
        "arxiv-search",
        "pdf-text-extractor",
        "literature-engineer",
        "dedupe-rank",
        "latex-scaffold",
        "latex-compile-qa",
    ):
        native.check_unit_outputs(
            skill=native_skill, workspace=tmp_path, outputs=[]
        )

    assert ("outputs", "source-ingest") in calls
    assert ("invariants", "outline-refiner") in calls
    assert ("outputs", "citation-injector") not in calls
    assert ("outputs", "deliverable-selfloop") not in calls
    assert ("outputs", "artifact-contract-auditor") not in calls
    assert ("outputs", "beamer-compile-qa") not in calls
    assert ("outputs", "beamer-scaffold") not in calls
    assert ("outputs", "citation-verifier") not in calls
    assert ("outputs", "arxiv-search") not in calls
    assert ("outputs", "pdf-text-extractor") not in calls
    assert ("outputs", "literature-engineer") not in calls
    assert ("outputs", "dedupe-rank") not in calls
    assert ("outputs", "latex-scaffold") not in calls
    assert ("outputs", "latex-compile-qa") not in calls


def test_native_module_imports_no_tooling_at_top() -> None:
    # The native provider must not import tooling at module top; delegation may
    # lazy-import the legacy adapter (which itself wraps tooling), but native.py
    # itself stays tooling-free.
    source = Path(native_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("tooling"), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("tooling"), module


# --- cutover-safety: byte-identical parity for *every* registered skill -----


def _pairs(issues: object) -> list[tuple[str, str]]:
    return [(i.code, i.message) for i in issues]  # type: ignore[attr-defined]


def _seed_native_pass_outputs(workspace: Path) -> None:
    """Materialize PASS-state files for each natively-covered skill.

    Exercises the *native* code paths (not just the empty-workspace early
    returns) so the parity sweep compares real output-check outcomes for the
    four skills native reimplements, alongside the delegated remainder.
    """

    (workspace / "output").mkdir(parents=True, exist_ok=True)
    (workspace / "output" / "CITATION_INJECTION_REPORT.md").write_text(
        "# Report\n- Status: PASS\n- Injected: 4\n", encoding="utf-8"
    )
    (workspace / "output" / "DELIVERABLE_SELFLOOP_TODO.md").write_text(
        "# Report\n- Status: PASS\n- Fixed: 2\n", encoding="utf-8"
    )
    (workspace / "output" / "CONTRACT_REPORT.md").write_text(
        "- Status: PASS\n- Pipeline complete (units): yes\n", encoding="utf-8"
    )
    (workspace / "latex" / "slides").mkdir(parents=True, exist_ok=True)
    (workspace / "latex" / "slides" / "main.pdf").write_text(
        "%PDF-1.4\n", encoding="utf-8"
    )
    (workspace / "output" / "SLIDES_BUILD_REPORT.md").write_text(
        "# build\n- Status: PASS\n", encoding="utf-8"
    )


def test_native_matches_legacy_for_every_registered_skill(tmp_path: Path) -> None:
    """Cutover-safety proof: selecting native is byte-identical to legacy.

    For *every* registered skill (the four native ones + all delegated ones),
    both ``check_unit_outputs`` and ``check_completion_invariants`` must return
    the same (code, message) pairs as the legacy provider -- under an empty
    workspace and under one seeded with PASS-state native outputs. This is the
    evidence that flipping ``default_quality_provider`` to native is safe: no
    skill diverges. If any did, this test names it.
    """

    native = NativeQualityProvider()
    legacy = default_quality_provider()
    assert isinstance(legacy, LegacyToolingQualityProvider)

    skills = sorted(legacy.registered_quality_skills())
    assert len(skills) == 68, "expected all 68 registered skills"
    # The four natively reimplemented skills must be inside the swept set.
    for native_skill in (
        "citation-injector",
        "deliverable-selfloop",
        "artifact-contract-auditor",
        "beamer-compile-qa",
    ):
        assert native_skill in skills

    empty_ws = tmp_path / "empty"
    empty_ws.mkdir()
    seeded_ws = tmp_path / "seeded"
    seeded_ws.mkdir()
    _seed_native_pass_outputs(seeded_ws)

    divergences: list[str] = []
    for skill in skills:
        for ws in (empty_ws, seeded_ws):
            native_out = _pairs(
                native.check_unit_outputs(skill=skill, workspace=ws, outputs=[])
            )
            legacy_out = _pairs(
                legacy.check_unit_outputs(skill=skill, workspace=ws, outputs=[])
            )
            if native_out != legacy_out:
                divergences.append(
                    f"{skill} check_unit_outputs @ {ws.name}: "
                    f"native={native_out} legacy={legacy_out}"
                )
            native_ci = _pairs(
                native.check_completion_invariants(
                    skill=skill, workspace=ws, outputs=[]
                )
            )
            legacy_ci = _pairs(
                legacy.check_completion_invariants(
                    skill=skill, workspace=ws, outputs=[]
                )
            )
            if native_ci != legacy_ci:
                divergences.append(
                    f"{skill} check_completion_invariants @ {ws.name}: "
                    f"native={native_ci} legacy={legacy_ci}"
                )

    assert not divergences, "native diverges from legacy:\n" + "\n".join(divergences)


# --- citation-verifier parity (first policy-consuming native check) ---------

_CITATION_OUT = ["citations/ref.bib", "citations/verified.jsonl"]

_GOOD_BIB = "@article{keyA, title={A}}\n@article{keyB, title={B}}\n"


def _verified_line(bibkey: str, **overrides: object) -> str:
    record: dict[str, object] = {
        "bibkey": bibkey,
        "title": f"Title {bibkey}",
        "url": f"https://example.org/{bibkey}",
        "date": "2026-01-01",
        "verification_status": "verified_online",
    }
    record.update(overrides)
    return json.dumps(record)


# Each case is (ref.bib body, verified.jsonl body); ``None`` means absent.
_CITATION_CASES: dict[str, tuple[str | None, str | None]] = {
    "missing_bib": (None, _verified_line("keyA")),
    "missing_verified": (_GOOD_BIB, None),
    "empty_bib": ("% no entries here\n", _verified_line("keyA")),
    "duplicate_keys": (
        "@article{dup, title={A}}\n@article{dup, title={B}}\n",
        _verified_line("dup"),
    ),
    "empty_verified": (_GOOD_BIB, ""),
    "missing_records": (_GOOD_BIB, _verified_line("keyA")),  # keyB unmatched
    "bad_fields_missing": (
        _GOOD_BIB,
        _verified_line("keyA")
        + "\n"
        + json.dumps({"bibkey": "keyB", "title": "", "url": "", "date": ""}),
    ),
    "bad_fields_unknown_status": (
        _GOOD_BIB,
        _verified_line("keyA")
        + "\n"
        + _verified_line("keyB", verification_status="bogus_status"),
    ),
    "pass": (_GOOD_BIB, _verified_line("keyA") + "\n" + _verified_line("keyB")),
}


@pytest.mark.parametrize("name", sorted(_CITATION_CASES))
def test_native_citation_verifier_matches_legacy(name: str, tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    bib_body, verified_body = _CITATION_CASES[name]
    ws = tmp_path / name
    ws.mkdir()
    if bib_body is not None:
        _write_file(ws, "citations/ref.bib", bib_body)
    if verified_body is not None:
        _write_file(ws, "citations/verified.jsonl", verified_body)

    native_pairs = _pairs(
        native.check_unit_outputs(
            skill="citation-verifier", workspace=ws, outputs=_CITATION_OUT
        )
    )
    legacy_pairs = _pairs(
        legacy.check_unit_outputs(
            skill="citation-verifier", workspace=ws, outputs=_CITATION_OUT
        )
    )
    assert native_pairs == legacy_pairs, name


def test_native_citation_verifier_default_output_paths(tmp_path: Path) -> None:
    # With empty outputs both providers fall back to the canonical relative
    # paths (citations/ref.bib, citations/verified.jsonl).
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    _write_file(tmp_path, "citations/ref.bib", _GOOD_BIB)
    _write_file(
        tmp_path,
        "citations/verified.jsonl",
        _verified_line("keyA") + "\n" + _verified_line("keyB"),
    )
    assert (
        _pairs(
            native.check_unit_outputs(
                skill="citation-verifier", workspace=tmp_path, outputs=[]
            )
        )
        == _pairs(
            legacy.check_unit_outputs(
                skill="citation-verifier", workspace=tmp_path, outputs=[]
            )
        )
        == []
    )


def _seed_arxiv_survey_workspace(workspace: Path) -> None:
    """Stand up a real ``arxiv-survey``-profile workspace.

    The profile + core-set target are read from ``PIPELINE.lock.md`` through the
    pipeline spec -- the exact policy surface the native check now consumes via
    the injected ``WorkspacePolicyPort``.  Both providers default to the legacy
    reader, so this drives the ``arxiv-survey`` branch identically on each side.
    """

    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n", encoding="utf-8"
    )


def test_native_citation_verifier_matches_legacy_on_survey_policy_branch(
    tmp_path: Path,
) -> None:
    # The policy-consuming branch: under an arxiv-survey profile, a bib with
    # fewer than the core-set target of entries must fail identically (same
    # code + message, which embeds the resolved target) on both providers.
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    ws = tmp_path / "survey"
    ws.mkdir()
    _seed_arxiv_survey_workspace(ws)
    _write_file(ws, "citations/ref.bib", _GOOD_BIB)  # only 2 entries << target
    _write_file(
        ws,
        "citations/verified.jsonl",
        _verified_line("keyA") + "\n" + _verified_line("keyB"),
    )

    native_pairs = _pairs(
        native.check_unit_outputs(
            skill="citation-verifier", workspace=ws, outputs=_CITATION_OUT
        )
    )
    legacy_pairs = _pairs(
        legacy.check_unit_outputs(
            skill="citation-verifier", workspace=ws, outputs=_CITATION_OUT
        )
    )
    assert native_pairs == legacy_pairs
    # The branch actually fired (not a trivially-equal empty result): the
    # too-few-entries code is present and carries the policy-resolved target.
    assert native_pairs and native_pairs[0][0] == "citations_too_few_entries"


def test_native_citation_verifier_consumes_injected_policy() -> None:
    # Prove the check reads through the injected WorkspacePolicyPort (not a
    # hidden tooling import): a stub policy that reports arxiv-survey with a
    # tiny core-set target changes the outcome deterministically, with no
    # PIPELINE.lock present.
    import tempfile

    class _StubPolicy:
        def pipeline_profile_name(self, workspace: Path) -> str:
            return "arxiv-survey"

        def evidence_mode(self, workspace: Path) -> str:
            return "abstract"

        def core_size(self, workspace: Path) -> int:
            return 5

        def pipeline_quality_contract_value(
            self, workspace: Path, *keys: str, default: object = None
        ) -> object:
            return default

    provider = NativeQualityProvider(policy=_StubPolicy())
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "citations").mkdir()
        (ws / "citations" / "ref.bib").write_text(_GOOD_BIB, encoding="utf-8")
        (ws / "citations" / "verified.jsonl").write_text(
            _verified_line("keyA") + "\n" + _verified_line("keyB"),
            encoding="utf-8",
        )
        pairs = _pairs(
            provider.check_unit_outputs(
                skill="citation-verifier", workspace=ws, outputs=_CITATION_OUT
            )
        )
    # core_size=5 with 2 bib entries -> too-few-entries against target 5.
    assert pairs == [
        (
            "citations_too_few_entries",
            "`citations/ref.bib` has only 2 entries; target >= 5 for a "
            "survey-quality run (expand retrieval / snowball / imports).",
        )
    ]


# --- arxiv-search parity (second policy-consuming native check) -------------

_ARXIV_OUT = ["papers/papers_raw.jsonl"]


def _raw_line(**fields: object) -> str:
    return json.dumps(fields)


# Each case is the ``papers/papers_raw.jsonl`` body; ``None`` means absent.
_ARXIV_CASES: dict[str, str | None] = {
    "missing": None,
    "empty": "",
    "placeholder_title": _raw_line(title="(placeholder) demo", url="x"),
    "placeholder_zero_id": _raw_line(title="Real", url="https://x/0000.00000"),
    # arxiv source, no id_fetch, no queries.md -> delegates to keyword check.
    "arxiv_no_keywords": _raw_line(title="Real paper", url="u", source="arxiv"),
    # arxiv source but id_list fetch -> keywords optional -> pass.
    "arxiv_id_fetch": _raw_line(
        title="Real paper", url="u", source="arxiv", query=["2601.00001"]
    ),
    # non-arxiv source -> no keyword hygiene -> pass.
    "non_arxiv": _raw_line(title="Real paper", url="u", source="openalex"),
    # multiple non-arxiv records, all clean -> pass.
    "multi_clean": _raw_line(title="A", url="a", source="s")
    + "\n"
    + _raw_line(title="B", url="b", source="s"),
}


@pytest.mark.parametrize("name", sorted(_ARXIV_CASES))
def test_native_arxiv_search_matches_legacy(name: str, tmp_path: Path) -> None:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    body = _ARXIV_CASES[name]
    ws = tmp_path / name
    ws.mkdir()
    if body is not None:
        _write_file(ws, "papers/papers_raw.jsonl", body)

    native_pairs = _pairs(
        native.check_unit_outputs(
            skill="arxiv-search", workspace=ws, outputs=_ARXIV_OUT
        )
    )
    legacy_pairs = _pairs(
        legacy.check_unit_outputs(
            skill="arxiv-search", workspace=ws, outputs=_ARXIV_OUT
        )
    )
    assert native_pairs == legacy_pairs, name


def test_native_arxiv_search_keyword_branch_matches_legacy(tmp_path: Path) -> None:
    # arxiv source, no id_fetch, with a queries.md keyword list: both providers
    # route through the keyword-expansion helper. Sweep its own case matrix.
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    raw = _raw_line(title="Real paper", url="u", source="arxiv")

    keyword_cases: dict[str, str | None] = {
        "no_queries_file": None,
        "empty_keywords": "- keywords:\n",
        "one_generic": "- keywords:\n- rag\n",
        "one_strong": "- keywords:\n- retrieval augmented generation\n",
        "many": "- keywords:\n- alpha\n- beta terms\n",
    }
    for name, queries_body in keyword_cases.items():
        ws = tmp_path / name
        ws.mkdir()
        _write_file(ws, "papers/papers_raw.jsonl", raw)
        if queries_body is not None:
            _write_file(ws, "queries.md", queries_body)

        native_pairs = _pairs(
            native.check_unit_outputs(
                skill="arxiv-search", workspace=ws, outputs=_ARXIV_OUT
            )
        )
        legacy_pairs = _pairs(
            legacy.check_unit_outputs(
                skill="arxiv-search", workspace=ws, outputs=_ARXIV_OUT
            )
        )
        assert native_pairs == legacy_pairs, name


def test_native_arxiv_search_consumes_injected_policy_minimum_records() -> None:
    # Prove the check reads the retrieval-policy minimum-records contract through
    # the injected WorkspacePolicyPort: a stub reporting minimum_records=3 makes
    # a 2-record pool fail with raw_pool_too_small, deterministically.
    import tempfile

    class _StubPolicy:
        def pipeline_profile_name(self, workspace: Path) -> str:
            return "default"

        def evidence_mode(self, workspace: Path) -> str:
            return "abstract"

        def core_size(self, workspace: Path) -> int:
            return 0

        def pipeline_quality_contract_value(
            self, workspace: Path, *keys: str, default: object = None
        ) -> object:
            if keys == ("retrieval_policy", "minimum_records"):
                return 3
            return default

    provider = NativeQualityProvider(policy=_StubPolicy())
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "papers").mkdir()
        (ws / "papers" / "papers_raw.jsonl").write_text(
            _raw_line(title="A", url="a", source="s")
            + "\n"
            + _raw_line(title="B", url="b", source="s"),
            encoding="utf-8",
        )
        pairs = _pairs(
            provider.check_unit_outputs(
                skill="arxiv-search", workspace=ws, outputs=_ARXIV_OUT
            )
        )
    assert pairs == [
        (
            "raw_pool_too_small",
            "`papers/papers_raw.jsonl` contains 2 records; the Workflow contract "
            "requires at least 3. Broaden or repair the query before ranking.",
        )
    ]


# --- survey-retrieval family completion: pdf/lit/dedupe parity --------------
#
# These three checks complete native coverage of tooling.quality_checks.
# survey_retrieval. Each is exercised through a REAL workspace (both providers
# on the default legacy policy reader), so policy resolves identically and any
# divergence is in the check's own logic. A companion differential fuzzer
# (.scratch/parity_fuzz.py, git-excluded) sweeps thousands of randomized
# workspaces per skill; these pin the branch-critical cases as regression
# evidence.


def _survey_ws(tmp_path: Path, name: str, *, profile: str = "default") -> Path:
    ws = tmp_path / name
    ws.mkdir()
    # Materialize a real PIPELINE.lock so both providers resolve the profile
    # identically through the default legacy reader. "default" writes no lock
    # (pipeline_profile falls back to "default").
    _lock_by_profile = {
        "arxiv-survey": "pipelines/arxiv-survey.pipeline.md",
        "source-tutorial": "pipelines/source-tutorial.pipeline.md",
    }
    lock = _lock_by_profile.get(profile)
    if lock:
        (ws / "PIPELINE.lock.md").write_text(f"pipeline: {lock}\n", encoding="utf-8")
    return ws


def _both(skill: str, ws: Path, outputs: list[str]) -> list[tuple[str, str]]:
    native = NativeQualityProvider()
    legacy = default_quality_provider()
    n = _pairs(native.check_unit_outputs(skill=skill, workspace=ws, outputs=outputs))
    lg = _pairs(legacy.check_unit_outputs(skill=skill, workspace=ws, outputs=outputs))
    assert n == lg, f"{skill}: native={n} legacy={lg}"
    return n


# pdf-text-extractor -----------------------------------------------------------

_PDF_OUT = ["papers/fulltext_index.jsonl"]


def test_native_pdf_extractor_missing_index(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "missing")
    assert _both("pdf-text-extractor", ws, _PDF_OUT) == [
        ("empty_fulltext_index", "`papers/fulltext_index.jsonl` is missing or empty.")
    ]


def test_native_pdf_extractor_abstract_mode_incomplete(tmp_path: Path) -> None:
    # abstract mode (default): core_set has p1,p2 but index only covers p1.
    ws = _survey_ws(tmp_path, "abs_incomplete")
    _write_file(ws, "queries.md", "- evidence_mode: abstract\n")
    _write_file(ws, "papers/core_set.csv", "paper_id,title\np1,A\np2,B\n")
    _write_file(
        ws,
        "papers/fulltext_index.jsonl",
        json.dumps({"paper_id": "p1", "status": "skip_mode_abstract"}),
    )
    pairs = _both("pdf-text-extractor", ws, _PDF_OUT)
    assert pairs and pairs[0][0] == "abstract_index_incomplete"


def test_native_pdf_extractor_abstract_mode_bad_status(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "abs_status")
    _write_file(ws, "queries.md", "- evidence_mode: abstract\n")
    _write_file(ws, "papers/core_set.csv", "paper_id,title\np1,A\n")
    _write_file(
        ws,
        "papers/fulltext_index.jsonl",
        json.dumps({"paper_id": "p1", "status": "ok"}),
    )
    pairs = _both("pdf-text-extractor", ws, _PDF_OUT)
    assert pairs and pairs[0][0] == "abstract_index_status_invalid"


def test_native_pdf_extractor_abstract_mode_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "abs_pass")
    _write_file(ws, "queries.md", "- evidence_mode: abstract\n")
    _write_file(ws, "papers/core_set.csv", "paper_id,title\np1,A\n")
    _write_file(
        ws,
        "papers/fulltext_index.jsonl",
        json.dumps({"paper_id": "p1", "status": "skip_mode_abstract"}),
    )
    assert _both("pdf-text-extractor", ws, _PDF_OUT) == []


def test_native_pdf_extractor_fulltext_too_few(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "ft_few")
    _write_file(ws, "queries.md", "- evidence_mode: fulltext\n")
    _write_file(
        ws,
        "papers/fulltext_index.jsonl",
        json.dumps({"paper_id": "p1", "status": "fail", "pdf_url": "u"}),
    )
    pairs = _both("pdf-text-extractor", ws, _PDF_OUT)
    assert pairs and pairs[0][0] == "fulltext_too_few"


def test_native_pdf_extractor_fulltext_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "ft_pass")
    _write_file(ws, "queries.md", "- evidence_mode: fulltext\n")
    _write_file(
        ws,
        "papers/fulltext_index.jsonl",
        json.dumps(
            {"paper_id": "p1", "status": "ok", "pdf_url": "u", "chars_extracted": 5000}
        ),
    )
    assert _both("pdf-text-extractor", ws, _PDF_OUT) == []


# literature-engineer ----------------------------------------------------------

_LIT_OUT = ["papers/papers_raw.jsonl", "papers/retrieval_report.md"]


def _good_lit_record(**overrides: object) -> dict[str, object]:
    rec: dict[str, object] = {
        "title": "Real",
        "url": "u",
        "year": "2026",
        "authors": ["A"],
        "abstract": "abs",
        "arxiv_id": "2601.1",
        "provenance": [{"route": "r"}],
    }
    rec.update(overrides)
    return rec


def test_native_literature_missing_raw(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lit_missing")
    assert _both("literature-engineer", ws, _LIT_OUT) == [
        ("missing_raw", "`papers/papers_raw.jsonl` does not exist.")
    ]


def test_native_literature_bad_report(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lit_bad_report")
    _write_file(ws, "papers/papers_raw.jsonl", json.dumps(_good_lit_record()))
    _write_file(ws, "papers/retrieval_report.md", "not a report\n")
    assert _both("literature-engineer", ws, _LIT_OUT) == [
        ("bad_retrieval_report", "`papers/retrieval_report.md` is empty or not a retrieval report.")
    ]


def test_native_literature_metadata_gaps_order(tmp_path: Path) -> None:
    # Multiple simultaneous gaps: verify native emits the SAME ordered list.
    ws = _survey_ws(tmp_path, "lit_gaps")
    rows = [
        json.dumps(_good_lit_record(title="", url="", year="", authors=[], provenance=[])),
        json.dumps(_good_lit_record(title="", url="", year="", authors=[], provenance=[])),
    ]
    _write_file(ws, "papers/papers_raw.jsonl", "\n".join(rows))
    _write_file(ws, "papers/retrieval_report.md", "Retrieval report\n- x: 1\n")
    pairs = _both("literature-engineer", ws, _LIT_OUT)
    codes = [c for c, _ in pairs]
    # missing titles, urls, then ratio-based years/authors/provenance in order.
    assert codes == [
        "raw_missing_titles",
        "raw_missing_urls",
        "raw_missing_years",
        "raw_missing_authors",
        "raw_missing_provenance",
    ]


def test_native_literature_survey_profile_thresholds(tmp_path: Path) -> None:
    # arxiv-survey profile adds raw_too_small (target=max(200, core_size*4)).
    ws = _survey_ws(tmp_path, "lit_survey", profile="arxiv-survey")
    _write_file(ws, "papers/papers_raw.jsonl", json.dumps(_good_lit_record()))
    _write_file(ws, "papers/retrieval_report.md", "Retrieval report\n- x: 1\n")
    pairs = _both("literature-engineer", ws, _LIT_OUT)
    assert "raw_too_small" in {c for c, _ in pairs}


def test_native_literature_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lit_pass")  # default profile, complete metadata
    _write_file(ws, "papers/papers_raw.jsonl", json.dumps(_good_lit_record()))
    _write_file(ws, "papers/retrieval_report.md", "Retrieval report\n- x: 1\n")
    assert _both("literature-engineer", ws, _LIT_OUT) == []


# dedupe-rank ------------------------------------------------------------------

_DEDUPE_OUT = ["papers/papers_dedup.jsonl", "papers/core_set.csv"]


def test_native_dedupe_missing_core(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "dd_missing")
    assert _both("dedupe-rank", ws, _DEDUPE_OUT) == [
        ("missing_core_set", "`papers/core_set.csv` does not exist.")
    ]


def test_native_dedupe_empty_core(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "dd_empty")
    _write_file(ws, "papers/core_set.csv", "paper_id,title\n")
    assert _both("dedupe-rank", ws, _DEDUPE_OUT) == [
        ("empty_core_set", "`papers/core_set.csv` has no rows.")
    ]


def test_native_dedupe_missing_fields_and_dupes(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "dd_fields")
    _write_file(
        ws,
        "papers/core_set.csv",
        "paper_id,title\n,\ndup,A\ndup,B\n",
    )
    pairs = _both("dedupe-rank", ws, _DEDUPE_OUT)
    codes = [c for c, _ in pairs]
    assert "core_set_missing_paper_id" in codes
    assert "core_set_missing_title" in codes
    assert "core_set_duplicate_ids" in codes


def test_native_dedupe_scope_drift_video(tmp_path: Path) -> None:
    # arxiv-survey + text-to-image GOAL + video-heavy core set -> scope drift.
    ws = _survey_ws(tmp_path, "dd_drift", profile="arxiv-survey")
    _write_file(ws, "GOAL.md", "A survey of text-to-image generation\n")
    rows = ["paper_id,title"]
    for i in range(12):
        rows.append(f"p{i},Video model {i}")
    _write_file(ws, "papers/core_set.csv", "\n".join(rows) + "\n")
    pairs = _both("dedupe-rank", ws, _DEDUPE_OUT)
    assert "scope_drift_video" in {c for c, _ in pairs}


def test_native_dedupe_pass_default_profile(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "dd_pass")  # default profile: no survey thresholds
    _write_file(ws, "papers/core_set.csv", "paper_id,title\np1,A\np2,B\n")
    assert _both("dedupe-rank", ws, _DEDUPE_OUT) == []


# --- delivery-family scaffolds: beamer-scaffold, latex-scaffold parity ------


def test_native_beamer_scaffold_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "bs_missing")
    assert _both("beamer-scaffold", ws, ["latex/slides/main.tex"]) == [
        ("missing_beamer_tex", "`latex/slides/main.tex` does not exist.")
    ]


def test_native_beamer_scaffold_all_issues_ordered(tmp_path: Path) -> None:
    # Not a beamer doc, no frames, leaked markdown headings -> all three, in
    # the legacy order.
    ws = _survey_ws(tmp_path, "bs_bad")
    _write_file(ws, "latex/slides/main.tex", "\\documentclass{article}\n## heading\n")
    pairs = _both("beamer-scaffold", ws, ["latex/slides/main.tex"])
    assert [c for c, _ in pairs] == [
        "beamer_missing_class",
        "beamer_missing_frames",
        "beamer_markdown_headings",
    ]


def test_native_beamer_scaffold_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "bs_pass")
    _write_file(
        ws,
        "latex/slides/main.tex",
        "\\documentclass{beamer}\n\\begin{frame}\n\\end{frame}\n",
    )
    assert _both("beamer-scaffold", ws, ["latex/slides/main.tex"]) == []


def test_native_latex_scaffold_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "ls_missing")
    assert _both("latex-scaffold", ws, ["latex/main.tex"]) == [
        ("missing_main_tex", "`latex/main.tex` does not exist.")
    ]


def test_native_latex_scaffold_default_profile_requires_structure(tmp_path: Path) -> None:
    # default profile: missing abstract + bib, plus leaked markdown -> ordered.
    ws = _survey_ws(tmp_path, "ls_default")
    _write_file(ws, "latex/main.tex", "\\documentclass{article}\n[@k]\n**b**\n## h\n")
    pairs = _both("latex-scaffold", ws, ["latex/main.tex"])
    assert [c for c, _ in pairs] == [
        "latex_missing_abstract",
        "latex_missing_bib",
        "latex_markdown_cites",
        "latex_markdown_bold",
        "latex_markdown_headings",
    ]


def test_native_latex_scaffold_source_tutorial_exempts_structure(tmp_path: Path) -> None:
    # source-tutorial profile: abstract/bib NOT required. A clean tutorial tex
    # passes on both providers (proving the policy branch is consumed).
    ws = _survey_ws(tmp_path, "ls_tut", profile="source-tutorial")
    _write_file(ws, "latex/main.tex", "\\documentclass{article}\nplain body\n")
    assert _both("latex-scaffold", ws, ["latex/main.tex"]) == []


def test_native_latex_scaffold_pass_default(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "ls_pass")
    _write_file(
        ws,
        "latex/main.tex",
        "\\documentclass{article}\n\\begin{abstract}\\end{abstract}\n"
        "\\bibliography{../citations/ref}\n",
    )
    assert _both("latex-scaffold", ws, ["latex/main.tex"]) == []


# --- latex-compile-qa parity (completes the delivery family) ----------------
#
# The PDF page count is read via PyMuPDF (fitz) or a pdfinfo fallback. Neither
# may be installed in CI, so the file-existence and log-warning branches are
# exercised through the provider (deterministic: absent tooling -> both sides
# emit pdf_page_count_unavailable identically), while the page-count branches
# (too_short / too_long / placeholders) are pinned by calling the native and
# legacy functions directly with an INJECTED fake pdfinfo, so they compare the
# real page-count logic regardless of the host environment.

_LATEX_QA_OUT = ["latex/main.pdf", "output/LATEX_BUILD_REPORT.md"]


def test_native_latex_compile_qa_missing_pdf(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lq_nopdf")
    assert _both("latex-compile-qa", ws, _LATEX_QA_OUT) == [
        ("missing_main_pdf", "`latex/main.pdf` does not exist.")
    ]


def test_native_latex_compile_qa_missing_report(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lq_norep")
    _write_file(ws, "latex/main.pdf", "%PDF-1.4\n")
    assert _both("latex-compile-qa", ws, _LATEX_QA_OUT) == [
        ("missing_build_report", "`output/LATEX_BUILD_REPORT.md` does not exist.")
    ]


def test_native_latex_compile_qa_log_warnings_match_legacy(tmp_path: Path) -> None:
    # Exercises the not-SUCCESS + undefined-citation + float + missing-glyph
    # branches; page count is unavailable here (no fitz/pdfinfo) so both sides
    # early-return pdf_page_count_unavailable after the log warnings.
    ws = _survey_ws(tmp_path, "lq_warn")
    _write_file(ws, "latex/main.pdf", "not a real pdf")
    _write_file(ws, "output/LATEX_BUILD_REPORT.md", "- Status: FAIL\n")
    _write_file(
        ws,
        "latex/main.log",
        "There were undefined citations\n"
        "LaTeX Warning: Float too large for page\n"
        "Missing character: no glyph\n",
    )
    codes = [c for c, _ in _both("latex-compile-qa", ws, _LATEX_QA_OUT)]
    assert "latex_build_not_success" in codes
    assert "latex_undefined_citations" in codes
    assert "latex_float_too_large" in codes
    assert "latex_missing_character" in codes


def _fake_pdfinfo(tmp_path: Path, pages: int) -> "object":
    """Return a ``which``-shaped callable pointing at a fake pdfinfo script."""
    script = tmp_path / "bin" / "pdfinfo"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f'#!/bin/sh\necho "Pages:           {pages}"\n', encoding="utf-8")
    script.chmod(0o755)

    def which(tool: str) -> str | None:
        return str(script) if tool == "pdfinfo" else None

    return which


def _latex_qa_direct(ws: Path, which: "object") -> tuple[list, list]:
    """Call native + legacy latex-compile-qa directly with an injected which."""
    from tooling.quality_checks.delivery import check_latex_compile_qa as legacy

    from research_harness.acceptance.legacy_tooling import LegacyToolingPolicyReader
    from research_harness.acceptance.native import _check_latex_compile_qa

    policy = LegacyToolingPolicyReader()
    native = _pairs(_check_latex_compile_qa(ws, _LATEX_QA_OUT, policy, which=which))
    leg = _pairs(legacy(ws, _LATEX_QA_OUT, which=which))
    return native, leg


def test_native_latex_compile_qa_pdf_too_short(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lq_short")
    _write_file(ws, "latex/main.pdf", "%PDF-1.4\n")
    _write_file(ws, "output/LATEX_BUILD_REPORT.md", "- Status: SUCCESS\n")
    which = _fake_pdfinfo(tmp_path, pages=3)  # < default min of 8
    native, leg = _latex_qa_direct(ws, which)
    assert native == leg
    assert "pdf_too_short" in {c for c, _ in native}


def test_native_latex_compile_qa_pdf_too_long(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lq_long")
    _write_file(ws, "latex/main.pdf", "%PDF-1.4\n")
    _write_file(ws, "output/LATEX_BUILD_REPORT.md", "- Status: SUCCESS\n")
    # goal.json sets an explicit page_range max so the too-long branch can fire.
    _write_file(
        ws,
        ".harness/goal.json",
        json.dumps({"constraints": {"page_range": {"min": 8, "max": 20}}}),
    )
    which = _fake_pdfinfo(tmp_path, pages=40)
    native, leg = _latex_qa_direct(ws, which)
    assert native == leg
    assert "pdf_too_long" in {c for c, _ in native}


def test_native_latex_compile_qa_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "lq_pass")
    _write_file(ws, "latex/main.pdf", "%PDF-1.4\n")
    _write_file(ws, "output/LATEX_BUILD_REPORT.md", "- Status: SUCCESS\n")
    which = _fake_pdfinfo(tmp_path, pages=12)  # within default [8, inf)
    native, leg = _latex_qa_direct(ws, which)
    assert native == leg == []
