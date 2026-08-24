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
import subprocess
import sys
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
    legacy = LegacyToolingQualityProvider()
    assert native.registered_quality_skills() == legacy.registered_quality_skills()
    assert len(native.registered_quality_skills()) > 0


def test_completion_invariant_flags_match_legacy() -> None:
    native = NativeQualityProvider()
    legacy = LegacyToolingQualityProvider()
    for skill in native.registered_quality_skills():
        assert native.has_completion_invariant(skill) == legacy.has_completion_invariant(
            skill
        )
    assert native.has_completion_invariant("no-such-skill-xyz") is False


def test_default_provider_is_now_native(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cutover complete: every registered check has a byte-identical native
    # equivalent (proven by the 68-skill sweep), so native is the default.
    # `RESEARCH_HARNESS_QUALITY_PROVIDER=legacy` is the retained escape hatch;
    # clear it so the assertion reflects the real default regardless of ambient env.
    monkeypatch.delenv("RESEARCH_HARNESS_QUALITY_PROVIDER", raising=False)
    assert isinstance(default_quality_provider(), NativeQualityProvider)


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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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

    # Non-native skill -> delegated. Every *registered* skill is now natively
    # covered (68/68), so an unregistered skill exercises the fallback
    # delegation path: check_unit_outputs routes it to the composed legacy
    # adapter (which returns [] for an unknown skill, matching legacy).
    native.check_unit_outputs(
        skill="no-such-skill-xyz", workspace=tmp_path, outputs=[]
    )
    # An unregistered completion invariant -> delegated (fallback path). The
    # registered ``outline-refiner`` invariant is now natively handled, so it
    # must NOT be delegated (asserted below).
    native.check_completion_invariants(
        skill="no-such-skill-xyz", workspace=tmp_path, outputs=[]
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
        "source-manifest",
        "source-ingest",
        "source-tutorial-spec",
        "module-source-coverage",
        "tutorial-context-pack",
        "tutorial-selfloop",
        # policy-consuming native skills route through the policy table, still
        # not delegated to legacy.
        "citation-verifier",
        "arxiv-search",
        "pdf-text-extractor",
        "literature-engineer",
        "dedupe-rank",
        "latex-scaffold",
        "latex-compile-qa",
        "idea-brief",
        "idea-signal-mapper",
        "idea-direction-generator",
        "idea-screener",
        "idea-shortlist-curator",
        "idea-memo-writer",
        "claims-extractor",
        "evidence-auditor",
        "novelty-matrix",
        "rubric-writer",
        "protocol-writer",
        "screening-manager",
        "extraction-form",
        "bias-assessor",
        "synthesis-writer",
        "chapter-skeleton",
        "section-bindings",
        "section-briefs",
        "writer-selfloop",
        "front-matter-writer",
        "evaluation-anchor-checker",
        "paragraph-curator",
        "argument-selfloop",
        "subsection-writer",
        "prose-writer",
        "draft-polisher",
        "section-logic-polisher",
        "section-merger",
        "pipeline-auditor",
        "global-reviewer",
        "taxonomy-builder",
        "outline-builder",
        "section-mapper",
        "paper-notes",
        "claim-evidence-matrix",
        "claim-matrix-rewriter",
        "subsection-briefs",
        "chapter-briefs",
        "outline-refiner",
        "evidence-draft",
        "evidence-selfloop",
        "anchor-sheet",
        "schema-normalizer",
        "writer-context-pack",
        "evidence-binder",
        "survey-visuals",
        "table-schema",
        "table-filler",
        "appendix-table-writer",
        "transition-weaver",
    ):
        native.check_unit_outputs(
            skill=native_skill, workspace=tmp_path, outputs=[]
        )

    assert ("outputs", "no-such-skill-xyz") in calls
    assert ("invariants", "no-such-skill-xyz") in calls
    # The registered outline-refiner completion invariant is native now.
    assert ("invariants", "outline-refiner") not in calls
    assert ("outputs", "taxonomy-builder") not in calls
    assert ("outputs", "outline-builder") not in calls
    assert ("outputs", "section-mapper") not in calls
    assert ("outputs", "evidence-draft") not in calls
    assert ("outputs", "writer-context-pack") not in calls
    assert ("outputs", "transition-weaver") not in calls
    assert ("outputs", "citation-injector") not in calls
    assert ("outputs", "deliverable-selfloop") not in calls
    assert ("outputs", "artifact-contract-auditor") not in calls
    assert ("outputs", "beamer-compile-qa") not in calls
    assert ("outputs", "beamer-scaffold") not in calls
    assert ("outputs", "source-manifest") not in calls
    assert ("outputs", "source-ingest") not in calls
    assert ("outputs", "source-tutorial-spec") not in calls
    assert ("outputs", "module-source-coverage") not in calls
    assert ("outputs", "tutorial-context-pack") not in calls
    assert ("outputs", "tutorial-selfloop") not in calls
    assert ("outputs", "citation-verifier") not in calls
    assert ("outputs", "arxiv-search") not in calls
    assert ("outputs", "pdf-text-extractor") not in calls
    assert ("outputs", "literature-engineer") not in calls
    assert ("outputs", "dedupe-rank") not in calls
    assert ("outputs", "latex-scaffold") not in calls
    assert ("outputs", "latex-compile-qa") not in calls
    assert ("outputs", "idea-brief") not in calls
    assert ("outputs", "idea-signal-mapper") not in calls
    assert ("outputs", "idea-direction-generator") not in calls
    assert ("outputs", "idea-screener") not in calls
    assert ("outputs", "idea-shortlist-curator") not in calls
    assert ("outputs", "idea-memo-writer") not in calls
    assert ("outputs", "claims-extractor") not in calls
    assert ("outputs", "evidence-auditor") not in calls
    assert ("outputs", "novelty-matrix") not in calls
    assert ("outputs", "rubric-writer") not in calls
    assert ("outputs", "protocol-writer") not in calls
    assert ("outputs", "screening-manager") not in calls
    assert ("outputs", "extraction-form") not in calls
    assert ("outputs", "bias-assessor") not in calls
    assert ("outputs", "synthesis-writer") not in calls
    assert ("outputs", "chapter-skeleton") not in calls
    assert ("outputs", "section-bindings") not in calls
    assert ("outputs", "section-briefs") not in calls
    assert ("outputs", "writer-selfloop") not in calls
    assert ("outputs", "front-matter-writer") not in calls
    assert ("outputs", "evaluation-anchor-checker") not in calls
    assert ("outputs", "paragraph-curator") not in calls
    assert ("outputs", "argument-selfloop") not in calls
    assert ("outputs", "subsection-writer") not in calls
    assert ("outputs", "prose-writer") not in calls
    assert ("outputs", "draft-polisher") not in calls
    assert ("outputs", "section-logic-polisher") not in calls
    assert ("outputs", "section-merger") not in calls
    assert ("outputs", "pipeline-auditor") not in calls
    assert ("outputs", "global-reviewer") not in calls


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


def test_native_self_contained_check_does_not_import_tooling_at_runtime(
    tmp_path: Path,
) -> None:
    # Runtime strengthening of the AST guard above: a self-contained native
    # check must not lazy-import tooling either (the AST guard only sees
    # top-level imports). Runs in a clean subprocess so ``sys.modules``
    # reflects exactly what the native provider pulls in -- the legacy
    # equivalent imports 23 ``tooling.*`` modules for the same check.
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "sources").mkdir()
    (workspace / "sources" / "manifest.yml").write_text(
        "sources:\n"
        "  - source_id: s1\n"
        "    kind: pdf\n"
        "    locator: http://x/s1\n"
        "    label: S1\n",
        encoding="utf-8",
    )
    code = f"""
import sys
from pathlib import Path
from research_harness.acceptance.native import NativeQualityProvider
ws = Path({str(workspace)!r})
NativeQualityProvider().check_unit_outputs(
    skill="source-manifest", workspace=ws, outputs=["sources/manifest.yml"]
)
print("|".join(sorted(m for m in sys.modules if m.startswith("tooling"))))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert result.stdout.strip() == "", (
        f"native self-contained check imported tooling: {result.stdout!r}"
    )


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
    legacy = LegacyToolingQualityProvider()
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


# --- outline-refiner completion invariant parity ----------------------------
#
# The single registered completion invariant.  It guards on the declared
# ``outline/outline_state.jsonl`` output and then runs the section-first
# cutover gate (behind the WorkspacePolicyPort, byte-identical by construction).
# These tests pin both branches of the guard and the gate's section_first
# outcomes as regression evidence.


def test_outline_refiner_invariant_noop_without_declared_output(
    tmp_path: Path,
) -> None:
    # Without ``outline/outline_state.jsonl`` in the declared outputs, the
    # guard short-circuits before the gate is consulted: no-op on both sides.
    ws = tmp_path / "noop"
    ws.mkdir()
    assert _both_ci("outline-refiner", ws, outputs=[]) == []
    assert _both_ci(
        "outline-refiner", ws, outputs=["outline/coverage_report.md"]
    ) == []


def test_outline_refiner_invariant_non_section_first_is_noop(
    tmp_path: Path,
) -> None:
    # Output declared but the workspace is NOT in section-first mode: the gate
    # returns no issues on both sides.
    ws = tmp_path / "non_sf"
    ws.mkdir()
    _write_file(
        ws, "outline/outline_state.jsonl", json.dumps({"structure_phase": "done"})
    )
    assert _both_ci(
        "outline-refiner", ws, outputs=["outline/outline_state.jsonl"]
    ) == []


def test_outline_refiner_invariant_section_first_missing_state(
    tmp_path: Path,
) -> None:
    # section-first mode (arxiv-survey pipeline) + declared output + missing
    # outline_state.jsonl -> the gate flags it on both sides, byte-identical.
    ws = tmp_path / "sf_missing"
    ws.mkdir()
    _write_file(ws, "PIPELINE.lock.md", "pipeline: pipelines/arxiv-survey.pipeline.md\n")
    assert _both_ci(
        "outline-refiner", ws, outputs=["outline/outline_state.jsonl"]
    ) == [
        (
            "section_first_missing_outline_state",
            "`outline/outline_state.jsonl` requires `outline/outline_state.jsonl` "
            "to record section-first cutover state.",
        )
    ]


def test_outline_refiner_invariant_section_first_empty_state(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "sf_empty"
    ws.mkdir()
    _write_file(ws, "PIPELINE.lock.md", "pipeline: pipelines/arxiv-survey.pipeline.md\n")
    _write_file(ws, "outline/outline_state.jsonl", "")
    assert _both_ci(
        "outline-refiner", ws, outputs=["outline/outline_state.jsonl"]
    ) == [
        (
            "section_first_empty_outline_state",
            "`outline/outline_state.jsonl` requires `outline/outline_state.jsonl` "
            "to contain at least one cutover-state record.",
        )
    ]


def test_outline_refiner_invariant_section_first_valid_state(
    tmp_path: Path,
) -> None:
    # A complete, stable cutover record (decomposed + stable) -> no issues on
    # either side.
    ws = tmp_path / "sf_ok"
    ws.mkdir()
    _write_file(ws, "PIPELINE.lock.md", "pipeline: pipelines/arxiv-survey.pipeline.md\n")
    _write_file(
        ws,
        "outline/outline_state.jsonl",
        json.dumps(
            {
                "structure_phase": "decomposed",
                "h3_status": "stable",
                "approval_status": "approved",
                "reroute_target": "",
                "retry_budget_remaining": 3,
            }
        ),
    )
    assert _both_ci(
        "outline-refiner", ws, outputs=["outline/outline_state.jsonl"]
    ) == []


def test_outline_refiner_invariant_propagates_gate_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The legacy path has no try/except around the gate, so a gate crash must
    # propagate identically on the native side (not be swallowed).
    from research_harness.acceptance import native as native_mod

    class _BoomPolicy:
        def section_first_cutover_issues(self, workspace, *, consumer, require_stable_h3):
            raise RuntimeError("boom")

    provider = native_mod.NativeQualityProvider(policy=_BoomPolicy())
    with pytest.raises(RuntimeError, match="boom"):
        provider.check_completion_invariants(
            skill="outline-refiner",
            workspace=tmp_path,
            outputs=["outline/outline_state.jsonl"],
        )


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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
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
    legacy = LegacyToolingQualityProvider()
    n = _pairs(native.check_unit_outputs(skill=skill, workspace=ws, outputs=outputs))
    lg = _pairs(legacy.check_unit_outputs(skill=skill, workspace=ws, outputs=outputs))
    assert n == lg, f"{skill}: native={n} legacy={lg}"
    return n


def _both_ci(skill: str, ws: Path, outputs: list[str]) -> list[tuple[str, str]]:
    """Parity helper for completion invariants (native vs legacy)."""
    native = NativeQualityProvider()
    legacy = LegacyToolingQualityProvider()
    n = _pairs(
        native.check_completion_invariants(skill=skill, workspace=ws, outputs=outputs)
    )
    lg = _pairs(
        legacy.check_completion_invariants(skill=skill, workspace=ws, outputs=outputs)
    )
    assert n == lg, f"{skill} completion invariant: native={n} legacy={lg}"
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


# --- source-tutorial family parity (whole module native) --------------------
#
# All six checks are self-contained (no workspace policy). Each is exercised
# through a real workspace with backing files so the index/provenance grounding
# join can succeed; `_both` asserts native == legacy. A companion differential
# fuzzer (.scratch/parity_fuzz.py) sweeps thousands of randomized source-tutorial
# workspaces; these pin the branch-critical cases as regression evidence.


def _st_backed_sources(ws: Path, source_ids: list[str]) -> dict[str, str]:
    """Write backing files + manifest/index/provenance for a valid grounding join."""
    backing: dict[str, str] = {}
    rows = []
    index = []
    prov = []
    for sid in source_ids:
        rel = f"sources/{sid}.txt"
        _write_file(ws, rel, f"grounded snippet for {sid} here")
        backing[sid] = rel
        rows.append({"source_id": sid, "kind": "pdf", "locator": f"http://x/{sid}", "label": sid})
        index.append({"source_id": sid, "kind": "pdf", "status": "success", "local_path": rel})
        prov.append({"source_id": sid, "pointer": "p.1", "origin_url_or_path": f"http://x/{sid}", "local_path": rel})
    import yaml as _yaml

    _write_file(ws, "sources/manifest.yml", _yaml.safe_dump({"sources": rows}))
    _write_file(ws, "sources/index.jsonl", "\n".join(json.dumps(r) for r in index))
    _write_file(ws, "sources/provenance.jsonl", "\n".join(json.dumps(r) for r in prov))
    return backing


# source-manifest --------------------------------------------------------------


def test_native_source_manifest_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sm_missing")
    assert _both("source-manifest", ws, ["sources/manifest.yml"]) == [
        ("missing_source_manifest", "`sources/manifest.yml` does not exist.")
    ]


def test_native_source_manifest_invalid_yaml(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sm_badyaml")
    _write_file(ws, "sources/manifest.yml", "sources: [oops\n")
    codes = [c for c, _ in _both("source-manifest", ws, ["sources/manifest.yml"])]
    assert codes == ["invalid_source_manifest_yaml"]


def test_native_source_manifest_missing_fields_and_dupes(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sm_fields")
    _write_file(
        ws,
        "sources/manifest.yml",
        "sources:\n  - source_id: s1\n    kind: pdf\n",  # missing locator + label
    )
    assert [c for c, _ in _both("source-manifest", ws, ["sources/manifest.yml"])] == [
        "source_manifest_missing_fields"
    ]


def test_native_source_manifest_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sm_pass")
    _write_file(
        ws,
        "sources/manifest.yml",
        "sources:\n  - source_id: s1\n    kind: pdf\n    locator: http://x\n    label: S1\n",
    )
    assert _both("source-manifest", ws, ["sources/manifest.yml"]) == []


# source-ingest ----------------------------------------------------------------


def test_native_source_ingest_missing_index(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "si_missing")
    assert _both(
        "source-ingest", ws, ["sources/index.jsonl", "sources/provenance.jsonl"]
    ) == [("missing_source_index", "`sources/index.jsonl` does not exist.")]


def test_native_source_ingest_invalid_jsonl(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "si_badjsonl")
    _write_file(ws, "sources/manifest.yml", "sources:\n  - source_id: s1\n    kind: pdf\n    locator: x\n    label: S1\n")
    _write_file(ws, "sources/index.jsonl", "{not json\n")
    _write_file(ws, "sources/provenance.jsonl", "{}\n")
    codes = [c for c, _ in _both("source-ingest", ws, ["sources/index.jsonl", "sources/provenance.jsonl"])]
    assert codes == ["source_index_invalid_jsonl"]


def test_native_source_ingest_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "si_pass")
    _st_backed_sources(ws, ["s1", "s2"])
    assert _both(
        "source-ingest", ws, ["sources/index.jsonl", "sources/provenance.jsonl"]
    ) == []


def test_native_source_ingest_manifest_mismatch(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "si_mismatch")
    _st_backed_sources(ws, ["s1", "s2"])
    # Drop s2 from the manifest so index has an unexpected id.
    import yaml as _yaml

    _write_file(
        ws,
        "sources/manifest.yml",
        _yaml.safe_dump(
            {"sources": [{"source_id": "s1", "kind": "pdf", "locator": "x", "label": "S1"}]}
        ),
    )
    codes = {c for c, _ in _both("source-ingest", ws, ["sources/index.jsonl", "sources/provenance.jsonl"])}
    assert "source_index_manifest_mismatch" in codes


# source-tutorial-spec ---------------------------------------------------------


def test_native_source_tutorial_spec_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sts_missing")
    assert _both("source-tutorial-spec", ws, ["output/TUTORIAL_SPEC.md"]) == [
        ("missing_source_tutorial_spec", "`output/TUTORIAL_SPEC.md` does not exist.")
    ]


def test_native_source_tutorial_spec_missing_sections(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sts_sections")
    _write_file(ws, "output/TUTORIAL_SPEC.md", "## Audience\nx\n")
    codes = [c for c, _ in _both("source-tutorial-spec", ws, ["output/TUTORIAL_SPEC.md"])]
    assert codes == ["source_tutorial_spec_missing_sections"]


def test_native_source_tutorial_spec_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "sts_pass")
    struct = {
        "audience": "x",
        "prerequisites": "x",
        "learning_objectives": ["a"],
        "non_goals": ["n"],
        "source_scope": "s",
        "delivery_shape": "d",
    }
    body = (
        "## Audience\nx\n## Prerequisites\nx\n## Learning objectives\nx\n"
        "## Non-goals\nx\n## Source scope\nx\n## Running example policy\nx\n"
        "## Delivery shape\nx\n## Structured data\n```json\n" + json.dumps(struct) + "\n```\n"
    )
    _write_file(ws, "output/TUTORIAL_SPEC.md", body)
    assert _both("source-tutorial-spec", ws, ["output/TUTORIAL_SPEC.md"]) == []


# module-source-coverage -------------------------------------------------------


def test_native_module_source_coverage_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "msc_missing")
    assert _both("module-source-coverage", ws, ["outline/source_coverage.jsonl"]) == [
        ("missing_source_coverage", "`outline/source_coverage.jsonl` does not exist.")
    ]


def test_native_module_source_coverage_unresolved_and_mismatch(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "msc_unresolved")
    # coverage references s9 (no grounding join) and no module plan present.
    _write_file(
        ws,
        "outline/source_coverage.jsonl",
        json.dumps({"module_id": "m1", "source_ids": ["s9"], "gaps": []}),
    )
    codes = {c for c, _ in _both("module-source-coverage", ws, ["outline/source_coverage.jsonl"])}
    assert "source_coverage_unresolved_sources" in codes
    assert "source_coverage_plan_missing" in codes


def test_native_module_source_coverage_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "msc_pass")
    _st_backed_sources(ws, ["s1"])
    import yaml as _yaml

    _write_file(ws, "outline/module_plan.yml", _yaml.safe_dump({"modules": [{"id": "m1"}]}))
    _write_file(
        ws,
        "outline/source_coverage.jsonl",
        json.dumps({"module_id": "m1", "source_ids": ["s1"], "gaps": []}),
    )
    assert _both("module-source-coverage", ws, ["outline/source_coverage.jsonl"]) == []


# tutorial-context-pack (cross-calls module-source-coverage) -------------------


def test_native_tutorial_context_packs_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "tcp_missing")
    assert _both(
        "tutorial-context-pack", ws, ["outline/tutorial_context_packs.jsonl"]
    ) == [
        (
            "missing_tutorial_context_packs",
            "`outline/tutorial_context_packs.jsonl` does not exist.",
        )
    ]


def test_native_tutorial_context_packs_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "tcp_pass")
    _st_backed_sources(ws, ["s1"])
    import yaml as _yaml

    _write_file(ws, "outline/module_plan.yml", _yaml.safe_dump({"modules": [{"id": "m1"}]}))
    _write_file(
        ws,
        "outline/source_coverage.jsonl",
        json.dumps({"module_id": "m1", "source_ids": ["s1"], "gaps": []}),
    )
    _write_file(
        ws,
        "outline/tutorial_context_packs.jsonl",
        json.dumps(
            {
                "module_id": "m1",
                "objective": "learn",
                "source_ids": ["s1"],
                "source_snippets": [
                    {"source_id": "s1", "pointer": "p.1", "snippet": "grounded snippet for s1"}
                ],
            }
        ),
    )
    assert _both("tutorial-context-pack", ws, ["outline/tutorial_context_packs.jsonl"]) == []


def test_native_tutorial_context_packs_content_mismatch(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "tcp_content")
    _st_backed_sources(ws, ["s1"])
    import yaml as _yaml

    _write_file(ws, "outline/module_plan.yml", _yaml.safe_dump({"modules": [{"id": "m1"}]}))
    _write_file(
        ws,
        "outline/source_coverage.jsonl",
        json.dumps({"module_id": "m1", "source_ids": ["s1"], "gaps": []}),
    )
    _write_file(
        ws,
        "outline/tutorial_context_packs.jsonl",
        json.dumps(
            {
                "module_id": "m1",
                "objective": "learn",
                "source_ids": ["s1"],
                "source_snippets": [
                    {"source_id": "s1", "pointer": "p.1", "snippet": "text that is not in the source"}
                ],
            }
        ),
    )
    codes = {c for c, _ in _both("tutorial-context-pack", ws, ["outline/tutorial_context_packs.jsonl"])}
    assert "tutorial_context_packs_snippet_content_mismatch" in codes


# tutorial-selfloop (cross-calls tutorial_contract_issues) ---------------------


def test_native_tutorial_selfloop_missing(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "tsl_missing")
    assert _both("tutorial-selfloop", ws, ["output/TUTORIAL_SELFLOOP_TODO.md"]) == [
        (
            "missing_tutorial_selfloop_report",
            "`output/TUTORIAL_SELFLOOP_TODO.md` is missing or empty.",
        )
    ]


def test_native_tutorial_selfloop_not_pass(tmp_path: Path) -> None:
    ws = _survey_ws(tmp_path, "tsl_fail")
    _write_file(ws, "output/TUTORIAL_SELFLOOP_TODO.md", "- Status: FAIL\n")
    assert [c for c, _ in _both("tutorial-selfloop", ws, ["output/TUTORIAL_SELFLOOP_TODO.md"])] == [
        "tutorial_selfloop_not_pass"
    ]


def test_native_tutorial_selfloop_stale(tmp_path: Path) -> None:
    # PASS report but the tutorial does not match its contract -> stale/invalid.
    ws = _survey_ws(tmp_path, "tsl_stale")
    _write_file(ws, "output/TUTORIAL_SELFLOOP_TODO.md", "- Status: PASS\n")
    # No TUTORIAL.md -> structure issues -> stale_or_invalid on both sides.
    assert [c for c, _ in _both("tutorial-selfloop", ws, ["output/TUTORIAL_SELFLOOP_TODO.md"])] == [
        "tutorial_selfloop_stale_or_invalid"
    ]


# --- research-idea family parity (whole module native, policy-consuming) ----
#
# All six checks resolve the ideation contract through the WorkspacePolicyPort
# (has_pipeline_contract + resolve_idea_contract), both legacy-backed, so the
# contract is byte-identical on each side. `_both` asserts native == legacy. A
# companion differential fuzzer sweeps thousands of randomized ideation
# workspaces; these pin the branch-critical cases as regression evidence.


def _idea_ws(tmp_path: Path, name: str, *, resolvable: bool = True) -> Path:
    """Stand up an ideation workspace whose contract resolves (or not)."""
    ws = tmp_path / name
    (ws / "output" / "trace").mkdir(parents=True)
    ws_pipeline = ws / "PIPELINE.lock.md"
    ws_pipeline.write_text(
        "pipeline: pipelines/idea-brainstorm.pipeline.md\n", encoding="utf-8"
    )
    (ws / "output" / "trace" / "IDEA_BRIEF.md").write_text(
        "# Idea Brief\n## Focus lenses after C2\n- Focus clusters: retrieval\n",
        encoding="utf-8",
    )
    focus = (
        "Memory and retrieval (RAG); Tool interfaces and orchestration"
        if resolvable
        else "(select after retrieval)"
    )
    (ws / "DECISIONS.md").write_text(
        "# Decisions\n<!-- BEGIN CHECKPOINT:C2 -->\n"
        f"- Focus clusters: {focus}\n<!-- END CHECKPOINT:C2 -->\n",
        encoding="utf-8",
    )
    return ws


def test_native_idea_brief_missing(tmp_path: Path) -> None:
    ws = _idea_ws(tmp_path, "ib_missing")
    # Overwrite IDEA_BRIEF.md as empty to hit the missing/empty branch.
    _write_file(ws, "output/trace/IDEA_BRIEF.md", "")
    assert _both("idea-brief", ws, ["output/trace/IDEA_BRIEF.md"]) == [
        ("missing_idea_brief", "`output/trace/IDEA_BRIEF.md` is missing or empty.")
    ]


def test_native_idea_brief_missing_queries(tmp_path: Path) -> None:
    # A brief with all required sections but no queries.md -> missing_queries.
    ws = _idea_ws(tmp_path, "ib_noqueries")
    import json as _json

    contract_path = (
        Path(native_module.__file__).resolve().parents[3]
        / ".codex" / "skills" / "idea-brief" / "assets" / "brief_contract.json"
    )
    sections = _json.loads(contract_path.read_text())["required_sections"]
    body = "# Idea Brief\n" + "".join(f"## {s}\nx\n" for s in sections)
    _write_file(ws, "output/trace/IDEA_BRIEF.md", body)
    codes = [c for c, _ in _both("idea-brief", ws, ["output/trace/IDEA_BRIEF.md"])]
    assert codes == ["idea_brief_missing_queries"]


def test_native_signal_table_contract_error(tmp_path: Path) -> None:
    # Unresolvable contract (no C2 focus) -> invalid_idea_pipeline_contract,
    # identical on both sides.
    ws = _idea_ws(tmp_path, "st_badcontract", resolvable=False)
    _write_file(ws, "output/trace/IDEA_SIGNAL_TABLE.md", "| Signal ID |\n|---|\n| S0 |\n")
    codes = [c for c, _ in _both("idea-signal-mapper", ws, ["output/trace/IDEA_SIGNAL_TABLE.md"])]
    assert codes == ["invalid_idea_pipeline_contract"]


def test_native_signal_table_too_small(tmp_path: Path) -> None:
    # Resolvable contract, table present with the columns but too few rows.
    ws = _idea_ws(tmp_path, "st_small")
    header = (
        "| Signal ID | Cluster | Theme | Claim / observation | Tension | "
        "Missing piece | Possible axis | Academic value | Confidence | Paper IDs |"
    )
    sep = "|---|---|---|---|---|---|---|---|---|---|"
    _write_file(
        ws,
        "output/trace/IDEA_SIGNAL_TABLE.md",
        header + "\n" + sep + "\n| S0 | c | t | claim | x | m | a | v | hi | P0001 |\n",
    )
    codes = {c for c, _ in _both("idea-signal-mapper", ws, ["output/trace/IDEA_SIGNAL_TABLE.md"])}
    assert "idea_signal_table_too_small" in codes


def test_native_shortlist_missing_contract(tmp_path: Path) -> None:
    # Shortlist present but no pipeline lock -> missing_idea_pipeline_contract.
    ws = tmp_path / "sl_nocontract"
    (ws / "output" / "trace").mkdir(parents=True)
    _write_file(ws, "output/trace/IDEA_SHORTLIST.md", "### Direction 1. X\n")
    codes = [c for c, _ in _both("idea-shortlist-curator", ws, ["output/trace/IDEA_SHORTLIST.md"])]
    assert codes == ["missing_idea_pipeline_contract"]


def test_native_report_bundle_missing_parts(tmp_path: Path) -> None:
    ws = _idea_ws(tmp_path, "rb_missing")
    # No REPORT.md -> missing_brainstorm_report (first gate, before contract).
    assert _both(
        "idea-memo-writer",
        ws,
        ["output/REPORT.md", "output/APPENDIX.md", "output/REPORT.json"],
    ) == [("missing_brainstorm_report", "`output/REPORT.md` is missing or empty.")]


def test_native_direction_pool_and_screening_contract_error(tmp_path: Path) -> None:
    # Both checks share the contract-error branch; verify parity for each.
    for skill, out_rel in (
        ("idea-direction-generator", "output/trace/IDEA_DIRECTION_POOL.md"),
        ("idea-screener", "output/trace/IDEA_SCREENING_TABLE.md"),
    ):
        ws = _idea_ws(tmp_path, f"ce_{skill}", resolvable=False)
        _write_file(ws, out_rel, "| Direction ID |\n|---|\n| D0 |\n")
        codes = [c for c, _ in _both(skill, ws, [out_rel])]
        assert codes == ["invalid_idea_pipeline_contract"], skill


# --- paper-review family parity (whole module native, scorecard-gated) ------
#
# All four checks project dimension statuses from the paper-review scorecard,
# which both providers compute via the same legacy evaluate_paper_review (behind
# the WorkspacePolicyPort), so the scorecard is byte-identical. `_both` asserts
# native == legacy across empty, all-FAIL, and all-PASS review workspaces.


def _write_passing_review(ws: Path) -> None:
    """Materialize review artifacts that make every scorecard dimension PASS."""
    claims = [
        {"claim_id": f"C{i}", "text": "a claim", "claim_type": "empirical", "source_pointer": "p.1"}
        for i in range(3)
    ]
    _write_file(ws, "output/CLAIMS.jsonl", "\n".join(json.dumps(c) for c in claims))
    audit = [
        {
            "gap_id": f"G{i}",
            "claim_id": f"C{i}",
            "evidence_present": "yes",
            "gap": "none",
            "minimal_fix": "n/a",
            "severity": "minor",
        }
        for i in range(3)
    ]
    _write_file(ws, "output/EVIDENCE_AUDIT.jsonl", "\n".join(json.dumps(a) for a in audit))
    rows = ["claim_id\trelated_work\toverlap\tdelta\tevidence"]
    for i in range(3):
        rows.append(f"C{i}\tWork {i}\tov\tdelta\tev")
    # need >= 5 unique related works overall
    rows.append("C0\tWork 3\tov\tdelta\tev")
    rows.append("C1\tWork 4\tov\tdelta\tev")
    _write_file(ws, "output/NOVELTY_MATRIX.tsv", "\n".join(rows) + "\n")
    review = (
        "### Summary\nx\n### Novelty\nx\n### Soundness\nx\n### Clarity\nx\n"
        "### Impact\nx\n### Major Concerns\nx\n### Minor Comments\nx\n"
        "### Recommendation\nx\n- accept\n"
    )
    _write_file(ws, "output/REVIEW.md", review)


_PAPER_REVIEW_SKILLS = {
    "claims-extractor": "paper_review_claim_traceability",
    "evidence-auditor": "paper_review_evidence_coverage",
    "novelty-matrix": "paper_review_novelty_positioning",
    "rubric-writer": "paper_review_review_traceability",  # (+ recommendation)
}


@pytest.mark.parametrize("skill", sorted(_PAPER_REVIEW_SKILLS))
def test_native_paper_review_empty_matches_legacy(skill: str, tmp_path: Path) -> None:
    # Empty workspace: every dimension FAILs; native projection matches legacy.
    ws = tmp_path / f"pr_empty_{skill}"
    ws.mkdir()
    native_pairs = _both(skill, ws, [])
    assert native_pairs  # at least one FAIL issue
    assert native_pairs[0][0] == _PAPER_REVIEW_SKILLS[skill]


@pytest.mark.parametrize("skill", sorted(_PAPER_REVIEW_SKILLS))
def test_native_paper_review_passing_matches_legacy(skill: str, tmp_path: Path) -> None:
    # A fully-populated review makes all dimensions PASS -> no issues on either
    # provider (proves the scorecard flows through the Port identically).
    ws = tmp_path / f"pr_pass_{skill}"
    ws.mkdir()
    _write_passing_review(ws)
    assert _both(skill, ws, []) == []


def test_native_rubric_writer_covers_two_dimensions(tmp_path: Path) -> None:
    # rubric-writer reads BOTH review_traceability and recommendation_consistency;
    # a review missing sections + recommendation fails both, in order, identically.
    ws = tmp_path / "pr_rubric_two"
    ws.mkdir()
    _write_file(ws, "output/CLAIMS.jsonl", json.dumps({"claim_id": "C0", "text": "t", "claim_type": "empirical", "source_pointer": "p"}))
    _write_file(ws, "output/REVIEW.md", "### Summary\nonly one section\n")
    codes = [c for c, _ in _both("rubric-writer", ws, [])]
    assert codes == [
        "paper_review_review_traceability",
        "paper_review_recommendation_consistency",
    ]


def test_native_paper_review_consumes_injected_scorecard() -> None:
    # Prove the check reads the scorecard through the injected Port: a stub
    # policy returning a PASS dimension yields no issue; a FAIL yields one.
    import tempfile

    class _StubPolicy:
        def __init__(self, status: str) -> None:
            self._status = status

        def pipeline_profile_name(self, workspace: Path) -> str:
            return "default"

        def evidence_mode(self, workspace: Path) -> str:
            return "abstract"

        def core_size(self, workspace: Path) -> int:
            return 0

        def pipeline_quality_contract_value(self, workspace, *keys, default=None):
            return default

        def workspace_goal_constraints(self, workspace: Path) -> dict:
            return {}

        def has_pipeline_contract(self, workspace: Path) -> bool:
            return True

        def resolve_idea_contract(self, workspace: Path) -> dict:
            return {}

        def evaluate_paper_review(self, workspace: Path) -> dict:
            return {
                "dimensions": [
                    {
                        "id": "claim_traceability",
                        "status": self._status,
                        "evidence": "stub",
                    }
                ]
            }

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        passing = NativeQualityProvider(policy=_StubPolicy("PASS"))
        failing = NativeQualityProvider(policy=_StubPolicy("FAIL"))
        assert passing.check_unit_outputs(skill="claims-extractor", workspace=ws, outputs=[]) == []
        failed = _pairs(
            failing.check_unit_outputs(skill="claims-extractor", workspace=ws, outputs=[])
        )
        assert failed == [
            ("paper_review_claim_traceability", "Paper-review `claim_traceability` is FAIL: stub")
        ]


# --- evidence-review family parity (whole module native) --------------------
#
# protocol-writer / screening-manager / extraction-form / bias-assessor are
# self-contained CSV/text checks; synthesis-writer additionally reads the
# evidence-review scorecard's synthesis_traceability dimension through the Port
# (legacy-backed, byte-identical). `_both` asserts native == legacy.

_ER_CANON = [
    "population_or_setting",
    "task",
    "metric",
    "study_type",
    "result_summary",
    "evidence_pointer",
]


def _write_good_protocol(ws: Path) -> None:
    parts = [
        "# Protocol\n",
        "## Databases and Sources\narxiv\n",
        "## Time Window\n- time_window_from: 2020\n- time_window_to: 2026\n",
        "- RQ1: a question\n",
        "- I1: include a\n- I2: include b\n",
        "- E1: exclude a\n- E2: exclude b\n",
        "## Extraction Schema\n| field | definition | allowed_values | notes |\n| --- | --- | --- | --- |\n",
    ]
    for f in _ER_CANON:
        parts.append(f"| {f} | def | any | notes |\n")
    _write_file(ws, "output/PROTOCOL.md", "".join(parts))


def test_native_protocol_missing(tmp_path: Path) -> None:
    ws = tmp_path / "pr_missing"
    ws.mkdir()
    assert _both("protocol-writer", ws, ["output/PROTOCOL.md"]) == [
        ("missing_protocol", "`output/PROTOCOL.md` does not exist.")
    ]


def test_native_protocol_missing_parts_and_placeholders(tmp_path: Path) -> None:
    ws = tmp_path / "pr_thin"
    ws.mkdir()
    _write_file(ws, "output/PROTOCOL.md", "# Protocol\nTODO finish\n")
    codes = {c for c, _ in _both("protocol-writer", ws, ["output/PROTOCOL.md"])}
    assert "protocol_placeholders" in codes
    assert "protocol_missing_sections" in codes


def test_native_protocol_pass(tmp_path: Path) -> None:
    ws = tmp_path / "pr_ok"
    ws.mkdir()
    _write_good_protocol(ws)
    assert _both("protocol-writer", ws, ["output/PROTOCOL.md"]) == []


def test_native_screening_missing_inputs(tmp_path: Path) -> None:
    ws = tmp_path / "sc_missing"
    ws.mkdir()
    assert _both("screening-manager", ws, ["papers/screening_log.csv"]) == [
        (
            "missing_screening_inputs",
            "Evidence screening requires the protocol and screening log.",
        )
    ]


def test_native_screening_untraceable_and_coverage(tmp_path: Path) -> None:
    ws = tmp_path / "sc_bad"
    ws.mkdir()
    _write_good_protocol(ws)
    _write_file(ws, "papers/papers_dedup.jsonl", json.dumps({"paper_id": "P0001"}))
    # decision covers a different id, invalid code, no reason
    _write_file(
        ws,
        "papers/screening_log.csv",
        "paper_id,decision,reason_codes,reason\nP0002,maybe,ZZ,\n",
    )
    codes = {c for c, _ in _both("screening-manager", ws, ["papers/screening_log.csv"])}
    assert "screening_candidate_coverage" in codes
    assert "untraceable_screening_rows" in codes


def test_native_extraction_missing_inputs(tmp_path: Path) -> None:
    ws = tmp_path / "ex_missing"
    ws.mkdir()
    for skill in ("extraction-form", "bias-assessor"):
        assert _both(skill, ws, ["papers/extraction_table.csv"]) == [
            (
                "missing_extraction_inputs",
                "Evidence extraction requires the screening log and extraction table.",
            )
        ]


def test_native_extraction_bias_variant_differs(tmp_path: Path) -> None:
    # A table missing risk-of-bias fields passes extraction-form's bias check
    # but fails bias-assessor's -- verify each matches legacy independently.
    ws = tmp_path / "ex_bias"
    ws.mkdir()
    _write_file(
        ws,
        "papers/screening_log.csv",
        "paper_id,decision,reason_codes,reason\nP0001,include,I1,ok\n",
    )
    header = "paper_id," + ",".join(_ER_CANON)
    _write_file(
        ws,
        "papers/extraction_table.csv",
        header + "\nP0001," + ",".join("value" for _ in _ER_CANON) + "\n",
    )
    form_codes = {c for c, _ in _both("extraction-form", ws, ["papers/extraction_table.csv"])}
    bias_codes = {c for c, _ in _both("bias-assessor", ws, ["papers/extraction_table.csv"])}
    assert "incomplete_bias_assessment" not in form_codes
    assert "incomplete_bias_assessment" in bias_codes


def test_native_synthesis_missing(tmp_path: Path) -> None:
    ws = tmp_path / "sy_missing"
    ws.mkdir()
    assert _both("synthesis-writer", ws, ["output/SYNTHESIS.md"]) == [
        ("missing_evidence_synthesis", "`output/SYNTHESIS.md` does not exist.")
    ]


def test_native_synthesis_missing_sections_and_traceability(tmp_path: Path) -> None:
    # A synthesis missing sections + with untraceable pointers fails both the
    # native section scan and the Port-provided synthesis_traceability dimension.
    ws = tmp_path / "sy_thin"
    ws.mkdir()
    _write_file(ws, "output/SYNTHESIS.md", "## Research questions + scope\nx\n")
    codes = [c for c, _ in _both("synthesis-writer", ws, ["output/SYNTHESIS.md"])]
    assert "evidence_synthesis_missing_section" in codes


def test_native_synthesis_consumes_injected_scorecard() -> None:
    # Prove check_synthesis reads synthesis_traceability through the Port.
    import tempfile

    class _StubPolicy:
        def __init__(self, status: str) -> None:
            self._status = status

        def pipeline_profile_name(self, workspace: Path) -> str:
            return "default"

        def evidence_mode(self, workspace: Path) -> str:
            return "abstract"

        def core_size(self, workspace: Path) -> int:
            return 0

        def pipeline_quality_contract_value(self, workspace, *keys, default=None):
            return default

        def workspace_goal_constraints(self, workspace: Path) -> dict:
            return {}

        def has_pipeline_contract(self, workspace: Path) -> bool:
            return True

        def resolve_idea_contract(self, workspace: Path) -> dict:
            return {}

        def evaluate_paper_review(self, workspace: Path) -> dict:
            return {"dimensions": []}

        def evaluate_evidence_review(self, workspace: Path) -> dict:
            return {
                "dimensions": [
                    {
                        "id": "synthesis_traceability",
                        "status": self._status,
                        "evidence": "stub trace",
                    }
                ]
            }

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        # All required sections present so only the traceability dimension matters.
        (ws / "output").mkdir()
        (ws / "output" / "SYNTHESIS.md").write_text(
            "".join(
                f"{h}\nx\n"
                for h in (
                    "## Research questions + scope",
                    "## Included studies summary",
                    "## Extracted evidence table",
                    "## Findings by theme",
                    "## Risk of bias",
                    "## Supported conclusions",
                    "## Needs more evidence",
                )
            ),
            encoding="utf-8",
        )
        passing = NativeQualityProvider(policy=_StubPolicy("PASS"))
        failing = NativeQualityProvider(policy=_StubPolicy("FAIL"))
        assert passing.check_unit_outputs(skill="synthesis-writer", workspace=ws, outputs=[]) == []
        failed = _pairs(
            failing.check_unit_outputs(skill="synthesis-writer", workspace=ws, outputs=[])
        )
        assert failed == [("evidence_synthesis_untraceable", "stub trace")]


# --- survey-structure family parity (self-contained YAML/JSONL checks) -------


def test_native_chapter_skeleton(tmp_path: Path) -> None:
    ws = tmp_path / "cs"
    ws.mkdir()
    assert _both("chapter-skeleton", ws, ["outline/chapter_skeleton.yml"]) == [
        ("missing_chapter_skeleton", "`outline/chapter_skeleton.yml` does not exist.")
    ]
    # invalid (not a list)
    _write_file(ws, "outline/chapter_skeleton.yml", "not: a-list\n")
    assert [c for c, _ in _both("chapter-skeleton", ws, ["outline/chapter_skeleton.yml"])] == [
        "invalid_chapter_skeleton"
    ]
    # a valid single record passes
    ws2 = tmp_path / "cs_ok"
    ws2.mkdir()
    import yaml as _y

    _write_file(
        ws2,
        "outline/chapter_skeleton.yml",
        _y.safe_dump([{"id": "S0", "title": "t", "rationale": "r", "seed_topics": ["a"], "target_h3_count": 3}]),
    )
    assert _both("chapter-skeleton", ws2, ["outline/chapter_skeleton.yml"]) == []


def test_native_section_bindings_report_drift(tmp_path: Path) -> None:
    ws = tmp_path / "sb"
    ws.mkdir()
    # jsonl PASS but report says BLOCKED -> drift
    _write_file(
        ws,
        "outline/section_bindings.jsonl",
        json.dumps(
            {
                "section_id": "S0",
                "section_title": "t",
                "paper_ids_primary": ["P1"],
                "paper_ids_support": [],
                "coverage_count": 1,
                "status": "PASS",
                "blocking_gaps": [],
                "decomposition_recommendation": "decompose",
            }
        ),
    )
    _write_file(
        ws,
        "outline/section_binding_report.md",
        "| Section | Coverage | Status | Recommendation |\n|---|---|---|---|\n| S0 sec | 1 | BLOCKED | decompose |\n",
    )
    codes = {c for c, _ in _both("section-bindings", ws, ["outline/section_bindings.jsonl", "outline/section_binding_report.md"])}
    assert "section_binding_report_drift" in codes


def test_native_section_bindings_pass(tmp_path: Path) -> None:
    ws = tmp_path / "sb_ok"
    ws.mkdir()
    _write_file(
        ws,
        "outline/section_bindings.jsonl",
        json.dumps(
            {
                "section_id": "S0",
                "section_title": "t",
                "paper_ids_primary": ["P1"],
                "paper_ids_support": [],
                "coverage_count": 1,
                "status": "PASS",
                "blocking_gaps": [],
                "decomposition_recommendation": "decompose",
            }
        ),
    )
    _write_file(
        ws,
        "outline/section_binding_report.md",
        "| Section | Coverage | Status | Recommendation |\n|---|---|---|---|\n| S0 sec | 1 | PASS | decompose |\n",
    )
    assert _both("section-bindings", ws, ["outline/section_bindings.jsonl", "outline/section_binding_report.md"]) == []


def test_native_section_briefs(tmp_path: Path) -> None:
    ws = tmp_path / "sbr"
    ws.mkdir()
    assert _both("section-briefs", ws, ["outline/section_briefs.jsonl"]) == [
        ("missing_section_briefs", "`outline/section_briefs.jsonl` does not exist.")
    ]
    # invalid semantics: BLOCKED without blocking_gaps
    _write_file(
        ws,
        "outline/section_briefs.jsonl",
        json.dumps(
            {
                "section_id": "S0",
                "section_title": "t",
                "section_rationale": "r",
                "contrast_lens": ["l"],
                "must_cover": ["m"],
                "target_h3_count": 3,
                "subsection_seeds": ["s"],
                "status": "BLOCKED",
                "decomposition_recommendation": "hold_or_merge",
                "blocking_gaps": [],
            }
        ),
    )
    assert [c for c, _ in _both("section-briefs", ws, ["outline/section_briefs.jsonl"])] == [
        "section_briefs_missing_fields"
    ]


# --- survey-writing family parity (largest module, policy + template-residue) -


@pytest.mark.parametrize(
    "skill,out_rel,missing_code",
    [
        ("writer-selfloop", "output/WRITER_SELFLOOP_TODO.md", "missing_writer_selfloop_report"),
        ("evaluation-anchor-checker", "output/EVAL_ANCHOR_REPORT.md", "missing_eval_anchor_report"),
        ("section-logic-polisher", "output/SECTION_LOGIC_REPORT.md", "missing_section_logic_report"),
        ("pipeline-auditor", "output/AUDIT_REPORT.md", "missing_audit_report"),
        ("global-reviewer", "output/GLOBAL_REVIEW.md", "missing_global_review"),
        ("prose-writer", "output/DRAFT.md", "missing_draft"),
        ("subsection-writer", "sections/sections_manifest.jsonl", "missing_sections_manifest"),
    ],
)
def test_native_survey_writing_missing_matches_legacy(
    skill: str, out_rel: str, missing_code: str, tmp_path: Path
) -> None:
    ws = tmp_path / f"sw_{skill}"
    ws.mkdir()
    pairs = _both(skill, ws, [out_rel])
    assert pairs and pairs[0][0] == missing_code


def test_native_writer_selfloop_pass_and_notpass(tmp_path: Path) -> None:
    ws = tmp_path / "sw_wsl_pass"
    ws.mkdir()
    _write_file(ws, "output/WRITER_SELFLOOP_TODO.md", "# plan\n- Status: PASS\n")
    assert _both("writer-selfloop", ws, ["output/WRITER_SELFLOOP_TODO.md"]) == []
    ws2 = tmp_path / "sw_wsl_fail"
    ws2.mkdir()
    _write_file(ws2, "output/WRITER_SELFLOOP_TODO.md", "# plan\n- Status: FAIL\n")
    assert [c for c, _ in _both("writer-selfloop", ws2, ["output/WRITER_SELFLOOP_TODO.md"])] == [
        "writer_selfloop_not_pass"
    ]


def test_native_draft_delivery_leak_and_placeholders(tmp_path: Path) -> None:
    # A draft with a delivery-request leak + TODO + no citations fails on the
    # same codes as legacy (reader_request_leakage native mirror).
    ws = tmp_path / "sw_draft"
    ws.mkdir()
    _write_file(
        ws,
        "output/DRAFT.md",
        "Please write a course paper on agents with pdf output.\n"
        "## Introduction\nTODO more\n## Conclusion\ndone\n",
    )
    codes = {c for c, _ in _both("prose-writer", ws, ["output/DRAFT.md"])}
    assert "draft_delivery_request_leakage" in codes
    assert "draft_contains_todo" in codes
    assert "draft_no_citations" in codes


def test_native_global_review_reruns_draft_checks(tmp_path: Path) -> None:
    # global-reviewer composes check_draft; a missing draft surfaces the draft
    # code alongside the review-structure codes, identically to legacy.
    ws = tmp_path / "sw_global"
    ws.mkdir()
    _write_file(ws, "output/GLOBAL_REVIEW.md", "- Status: PASS\n")
    native_pairs = _both("global-reviewer", ws, ["output/GLOBAL_REVIEW.md"])
    codes = {c for c, _ in native_pairs}
    assert "global_review_too_short" in codes
    assert "missing_draft" in codes  # from the composed check_draft


def test_native_draft_polisher_composes_anchoring(tmp_path: Path) -> None:
    # draft-polisher = check_draft + check_citation_anchoring; with a baseline
    # anchor file whose H3 is renamed, the anchoring code appears (matching legacy).
    ws = tmp_path / "sw_polish"
    ws.mkdir()
    _write_file(
        ws,
        "output/DRAFT.md",
        "## Introduction\n" + "grounded [@k0]. " * 40 + "\n### Kept\ntext [@k0]\n## Conclusion\nx\n## Discussion\nx\n",
    )
    _write_file(ws, "citations/ref.bib", "@article{k0, title={T}}\n")
    _write_file(
        ws,
        "output/citation_anchors.prepolish.jsonl",
        json.dumps({"kind": "h3", "title": "Renamed Away", "cite_keys": ["k0"]}),
    )
    codes = {c for c, _ in _both("draft-polisher", ws, ["output/DRAFT.md"])}
    assert "citation_anchor_missing_h3" in codes


# --- survey-planning family parity (final module -> 68/68 native) -----------


@pytest.mark.parametrize(
    "skill,out_rel,missing_code",
    [
        ("taxonomy-builder", "outline/taxonomy.yml", "invalid_taxonomy"),
        ("outline-builder", "outline/outline.yml", "invalid_outline"),
        ("section-mapper", "outline/mapping.tsv", "empty_mapping"),
        ("paper-notes", "papers/paper_notes.jsonl", "empty_paper_notes"),
        ("claim-evidence-matrix", "outline/claim_evidence_matrix.md", "missing_claim_matrix"),
        ("subsection-briefs", "outline/subsection_briefs.jsonl", "missing_subsection_briefs"),
        ("chapter-briefs", "outline/chapter_briefs.jsonl", "missing_chapter_briefs"),
        ("outline-refiner", "outline/coverage_report.md", "missing_coverage_report"),
        ("evidence-draft", "outline/evidence_drafts.jsonl", "missing_evidence_drafts"),
        ("evidence-selfloop", "output/EVIDENCE_SELFLOOP_TODO.md", "missing_evidence_selfloop_report"),
        ("anchor-sheet", "outline/anchor_sheet.jsonl", "missing_anchor_sheet"),
        ("schema-normalizer", "output/SCHEMA_NORMALIZATION_REPORT.md", "missing_schema_normalization_report"),
        ("writer-context-pack", "outline/writer_context_packs.jsonl", "missing_writer_context_packs"),
        ("evidence-binder", "outline/evidence_bindings.jsonl", "missing_evidence_bindings"),
        ("table-schema", "outline/table_schema.md", "missing_table_schema"),
        ("table-filler", "outline/tables_index.md", "missing_tables_md"),
        ("appendix-table-writer", "outline/tables_appendix.md", "missing_tables_appendix"),
        ("transition-weaver", "outline/transitions.md", "missing_transitions"),
    ],
)
def test_native_survey_planning_missing_matches_legacy(
    skill: str, out_rel: str, missing_code: str, tmp_path: Path
) -> None:
    ws = tmp_path / f"sp_{skill}"
    ws.mkdir()
    pairs = _both(skill, ws, [out_rel])
    assert pairs and pairs[0][0] == missing_code


def test_native_taxonomy_domain_and_template_branches(tmp_path: Path) -> None:
    ws = tmp_path / "sp_tax"
    ws.mkdir()
    import yaml as _y

    # depth ok, but all descriptions templated + short-desc -> template + short codes
    tax = [
        {
            "name": "Overview",
            "description": "Papers and ideas centered on 'x'",
            "children": [{"name": "Benchmarks", "description": "Key aspects of 'y'"}],
        }
    ]
    _write_file(ws, "outline/taxonomy.yml", _y.safe_dump(tax))
    codes = {c for c, _ in _both("taxonomy-builder", ws, ["outline/taxonomy.yml"])}
    assert "taxonomy_template_descriptions" in codes


def test_native_survey_visuals_multi_file(tmp_path: Path) -> None:
    # survey-visuals reads timeline + figures; short timeline + sparse cites fire.
    ws = tmp_path / "sp_vis"
    ws.mkdir()
    _write_file(ws, "outline/timeline.md", "- 2021 event\n- 2022 event\n")
    _write_file(ws, "outline/figures.md", "- Figure 1: x\n")
    codes = {
        c
        for c, _ in _both(
            "survey-visuals", ws, ["outline/timeline.md", "outline/figures.md"]
        )
    }
    assert "visuals_timeline_too_short" in codes
    assert "visuals_missing_figures" in codes


def test_native_transitions_planner_talk(tmp_path: Path) -> None:
    ws = tmp_path / "sp_trans"
    ws.mkdir()
    _write_file(ws, "outline/transitions.md", "- 1.1 follows naturally by turning to X\n")
    codes = [c for c, _ in _both("transition-weaver", ws, ["outline/transitions.md"])]
    assert codes == ["transitions_planner_talk_turning"]


def test_native_evidence_binder_regex_fidelity(tmp_path: Path) -> None:
    # The legacy evidence_id paper regex is literally `^E-(P\\d+)-` (a literal
    # backslash-d that never matches); native reproduces it so a binding whose
    # only paper signal is an evidence_id prefix still fails distinct-papers.
    ws = tmp_path / "sp_bind"
    ws.mkdir()
    _write_file(
        ws,
        "outline/evidence_bindings.jsonl",
        json.dumps(
            {
                "sub_id": "1.1",
                "title": "t",
                "evidence_ids": ["E-P0001-a"],
                "mapped_bibkeys": ["k0"],
                "bibkeys": ["k0"],
            }
        ),
    )
    native = NativeQualityProvider()
    legacy = LegacyToolingQualityProvider()
    n = _pairs(native.check_unit_outputs(skill="evidence-binder", workspace=ws, outputs=["outline/evidence_bindings.jsonl"]))
    lg = _pairs(legacy.check_unit_outputs(skill="evidence-binder", workspace=ws, outputs=["outline/evidence_bindings.jsonl"]))
    assert n == lg
