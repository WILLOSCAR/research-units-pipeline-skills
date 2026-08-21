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

    # Non-native skill -> delegated.
    native.check_unit_outputs(skill="arxiv-search", workspace=tmp_path, outputs=[])
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
    ):
        native.check_unit_outputs(
            skill=native_skill, workspace=tmp_path, outputs=[]
        )

    assert ("outputs", "arxiv-search") in calls
    assert ("invariants", "outline-refiner") in calls
    assert ("outputs", "citation-injector") not in calls
    assert ("outputs", "deliverable-selfloop") not in calls
    assert ("outputs", "artifact-contract-auditor") not in calls
    assert ("outputs", "beamer-compile-qa") not in calls


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
