"""Contract tests for the workspace-policy Port seam.

Several deterministic quality checks read *workspace policy* (run profile,
evidence mode, core-set target, quality contract) before inspecting outputs.
The ``WorkspacePolicyPort`` (declared in ``research_harness`` with no
``tooling`` import) is the seam that lets such reads be satisfied natively
later.  The current backend is the transitional ``LegacyToolingPolicyReader``
adapter.  These tests lock in that seam so:

- it stays a faithful pass-through to ``tooling`` for real workspace policy;
- ``NativeQualityProvider`` accepts an injected reader (defaulting to legacy)
  without changing default behavior; and
- a future native reader has an executable contract to satisfy.
"""

from __future__ import annotations

from pathlib import Path

from research_harness.acceptance import (
    LegacyToolingPolicyReader,
    NativeQualityProvider,
    WorkspacePolicyPort,
    default_workspace_policy_reader,
)


def test_default_reader_satisfies_the_port() -> None:
    reader = default_workspace_policy_reader()
    assert isinstance(reader, LegacyToolingPolicyReader)
    # runtime_checkable Protocol: the adapter structurally satisfies the Port.
    assert isinstance(reader, WorkspacePolicyPort)


def test_port_surface_is_complete() -> None:
    reader = default_workspace_policy_reader()
    for method in (
        "pipeline_profile_name",
        "evidence_mode",
        "core_size",
        "pipeline_quality_contract_value",
        "workspace_goal_constraints",
        "has_pipeline_contract",
        "resolve_idea_contract",
        "evaluate_paper_review",
        "evaluate_evidence_review",
        "draft_profile",
        "global_citation_min_subsections",
        "quality_contract_int",
        "per_subsection",
        "template_residue_document_issues",
        "template_residue_subsection_issues",
        "structure_mode",
        "section_first_artifact_issues",
        "section_first_cutover_issues",
    ):
        assert callable(getattr(reader, method)), method


def _write_queries(workspace: Path, body: str) -> None:
    path = workspace / "queries.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_reader_matches_tooling_on_built_fixture_workspace(tmp_path: Path) -> None:
    # A lightweight but real workspace: `queries.md` drives evidence_mode and
    # core_size (the pipeline spec is unresolved, so both fall back to the
    # materialized query values).  The adapter must return exactly what calling
    # tooling directly returns -- proving it reads real workspace policy.
    from tooling.common import pipeline_quality_contract_value as legacy_qcv
    from tooling.quality_checks.survey_policy import (
        core_size as legacy_core_size,
        evidence_mode as legacy_evidence_mode,
        pipeline_profile_name as legacy_profile,
    )

    _write_queries(
        tmp_path,
        "# Queries\n\n## Primary query\n"
        '- evidence_mode: "fulltext"\n'
        '- core_size: "42"\n',
    )
    reader = default_workspace_policy_reader()

    # Concrete real values, not just "delegates".
    assert reader.evidence_mode(tmp_path) == "fulltext"
    assert reader.core_size(tmp_path) == 42
    assert reader.pipeline_profile_name(tmp_path) == "default"

    # Byte-for-byte parity with calling tooling directly.
    assert reader.pipeline_profile_name(tmp_path) == legacy_profile(tmp_path)
    assert reader.evidence_mode(tmp_path) == legacy_evidence_mode(tmp_path)
    assert reader.core_size(tmp_path) == legacy_core_size(tmp_path)
    assert reader.pipeline_quality_contract_value(
        tmp_path, "retrieval_policy", "minimum_records", default=7
    ) == legacy_qcv(
        tmp_path, "retrieval_policy", "minimum_records", default=7
    )


def test_reader_goal_constraints_pass_through(tmp_path: Path) -> None:
    # workspace_goal_constraints mirrors tooling.common exactly: it reads
    # .harness/goal.json when present, else parses GOAL.md.
    import json

    from tooling.common import load_workspace_goal_constraints as legacy_goal

    # (1) structured goal.json path
    (tmp_path / ".harness").mkdir(parents=True)
    (tmp_path / ".harness" / "goal.json").write_text(
        json.dumps({"constraints": {"page_range": {"min": 8, "max": 20}}}),
        encoding="utf-8",
    )
    reader = default_workspace_policy_reader()
    result = reader.workspace_goal_constraints(tmp_path)
    assert result == {"page_range": {"min": 8, "max": 20}}
    assert result == legacy_goal(tmp_path)

    # (2) empty workspace -> {} on both sides
    empty = tmp_path / "empty"
    empty.mkdir()
    assert reader.workspace_goal_constraints(empty) == legacy_goal(empty) == {}


def test_reader_idea_contract_pass_through(tmp_path: Path) -> None:
    # has_pipeline_contract and resolve_idea_contract mirror tooling exactly.
    from tooling.common import load_workspace_pipeline_spec as legacy_spec
    from tooling.ideation import resolve_idea_contract as legacy_resolve

    reader = default_workspace_policy_reader()

    # (1) empty workspace: no contract; has_pipeline_contract is False and
    # matches the tooling `is not None` predicate.
    assert reader.has_pipeline_contract(tmp_path) is (legacy_spec(tmp_path) is not None)
    assert reader.has_pipeline_contract(tmp_path) is False

    # (2) a resolvable ideation workspace: the resolved contract is identical.
    (tmp_path / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/idea-brainstorm.pipeline.md\n", encoding="utf-8"
    )
    (tmp_path / "output" / "trace").mkdir(parents=True)
    (tmp_path / "output" / "trace" / "IDEA_BRIEF.md").write_text(
        "# Idea Brief\n## Focus lenses after C2\n- Focus clusters: retrieval\n",
        encoding="utf-8",
    )
    (tmp_path / "DECISIONS.md").write_text(
        "# Decisions\n<!-- BEGIN CHECKPOINT:C2 -->\n"
        "- Focus clusters: Memory and retrieval (RAG); Tool interfaces\n"
        "<!-- END CHECKPOINT:C2 -->\n",
        encoding="utf-8",
    )
    assert reader.has_pipeline_contract(tmp_path) is True
    assert reader.resolve_idea_contract(tmp_path) == legacy_resolve(tmp_path)


def test_reader_paper_review_scorecard_pass_through(tmp_path: Path) -> None:
    # evaluate_paper_review mirrors tooling.review_evaluation exactly.
    from tooling.review_evaluation import evaluate_paper_review as legacy_eval

    reader = default_workspace_policy_reader()
    # Empty workspace: the adapter returns the same scorecard tooling does
    # (all dimensions FAIL, but structurally identical).
    native = reader.evaluate_paper_review(tmp_path)
    legacy = legacy_eval(tmp_path)
    assert isinstance(native, dict) and "dimensions" in native
    assert native == legacy


def test_reader_evidence_review_scorecard_pass_through(tmp_path: Path) -> None:
    # evaluate_evidence_review mirrors tooling.evidence_review_evaluation exactly.
    from tooling.evidence_review_evaluation import evaluate_evidence_review as legacy_eval

    reader = default_workspace_policy_reader()
    native = reader.evaluate_evidence_review(tmp_path)
    legacy = legacy_eval(tmp_path)
    assert isinstance(native, dict) and "dimensions" in native
    assert native == legacy


def test_reader_survey_writing_policy_pass_through(tmp_path: Path) -> None:
    # draft_profile / global_citation_min_subsections / quality_contract_int /
    # per_subsection / template-residue evaluators mirror tooling exactly.
    from tooling.quality_checks.survey_policy import (
        draft_profile as legacy_draft_profile,
        global_citation_min_subsections as legacy_gcms,
        per_subsection as legacy_per_sub,
        quality_contract_int as legacy_qci,
    )
    from tooling.quality_checks.template_residue import (
        check_subsection_template_residue as legacy_sub_residue,
        check_template_residue_documents as legacy_doc_residue,
    )

    reader = default_workspace_policy_reader()
    assert reader.draft_profile(tmp_path) == legacy_draft_profile(tmp_path)
    assert reader.global_citation_min_subsections(tmp_path) == legacy_gcms(tmp_path)
    assert reader.per_subsection(tmp_path) == legacy_per_sub(tmp_path)
    assert reader.quality_contract_int(
        tmp_path, keys=("no", "such"), default=7
    ) == legacy_qci(tmp_path, keys=("no", "such"), default=7)
    # template-residue evaluators: same (code, message) pairs on an empty ws.
    native_docs = [
        (i.code, i.message)
        for i in reader.template_residue_document_issues(tmp_path, [])
    ]
    legacy_docs = [
        (i.code, i.message)
        for i in legacy_doc_residue(workspace=tmp_path, documents=[])
    ]
    assert native_docs == legacy_docs
    native_subs = [
        (i.code, i.message)
        for i in reader.template_residue_subsection_issues(tmp_path, [])
    ]
    legacy_subs = [
        (i.code, i.message)
        for i in legacy_sub_residue(workspace=tmp_path, relpaths=[])
    ]
    assert native_subs == legacy_subs


def test_reader_structure_mode_and_section_first_pass_through(tmp_path: Path) -> None:
    # structure_mode / section_first_* mirror tooling.quality_checks.survey_structure.
    from tooling.quality_checks.survey_structure import (
        section_first_artifact_issues as legacy_artifact,
        section_first_cutover_issues as legacy_cutover,
        structure_mode as legacy_structure_mode,
    )

    reader = default_workspace_policy_reader()
    assert reader.structure_mode(tmp_path) == legacy_structure_mode(tmp_path) == ""
    native_a = [
        (i.code, i.message)
        for i in reader.section_first_artifact_issues(tmp_path, consumer="x")
    ]
    legacy_a = [
        (i.code, i.message)
        for i in legacy_artifact(tmp_path, consumer="x")
    ]
    assert native_a == legacy_a
    native_c = [
        (i.code, i.message)
        for i in reader.section_first_cutover_issues(
            tmp_path, consumer="x", require_stable_h3=True
        )
    ]
    legacy_c = [
        (i.code, i.message)
        for i in legacy_cutover(tmp_path, consumer="x", require_stable_h3=True)
    ]
    assert native_c == legacy_c


def test_reader_matches_tooling_on_empty_workspace(tmp_path: Path) -> None:
    # With no queries.md / no resolvable spec, the adapter returns the same
    # defaults tooling does.
    from tooling.common import pipeline_quality_contract_value as legacy_qcv
    from tooling.quality_checks.survey_policy import (
        core_size as legacy_core_size,
        evidence_mode as legacy_evidence_mode,
        pipeline_profile_name as legacy_profile,
    )

    reader = default_workspace_policy_reader()
    assert reader.pipeline_profile_name(tmp_path) == legacy_profile(tmp_path) == "default"
    assert reader.evidence_mode(tmp_path) == legacy_evidence_mode(tmp_path) == "abstract"
    assert reader.core_size(tmp_path) == legacy_core_size(tmp_path) == 0
    sentinel = object()
    assert (
        reader.pipeline_quality_contract_value(tmp_path, "no", "such", default=sentinel)
        is legacy_qcv(tmp_path, "no", "such", default=sentinel)
        is sentinel
    )


def test_native_provider_defaults_to_legacy_policy_reader() -> None:
    # The seam is landed but default behavior is unchanged: the native provider
    # carries the legacy policy reader by default.
    provider = NativeQualityProvider()
    assert isinstance(provider.policy, LegacyToolingPolicyReader)
    assert isinstance(provider.policy, WorkspacePolicyPort)


def test_native_provider_accepts_injected_policy_reader() -> None:
    # A hand-written reader satisfies the Port and can be injected, proving the
    # seam is a real injection point with no tooling dependency.
    class _RecordingReader:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def pipeline_profile_name(self, workspace: Path) -> str:
            self.calls.append("pipeline_profile_name")
            return "arxiv-survey"

        def evidence_mode(self, workspace: Path) -> str:
            self.calls.append("evidence_mode")
            return "fulltext"

        def core_size(self, workspace: Path) -> int:
            self.calls.append("core_size")
            return 300

        def pipeline_quality_contract_value(
            self, workspace: Path, *keys: str, default: object = None
        ) -> object:
            self.calls.append("pipeline_quality_contract_value")
            return default

        def workspace_goal_constraints(self, workspace: Path) -> dict[str, object]:
            self.calls.append("workspace_goal_constraints")
            return {}

        def has_pipeline_contract(self, workspace: Path) -> bool:
            self.calls.append("has_pipeline_contract")
            return True

        def resolve_idea_contract(self, workspace: Path) -> dict[str, object]:
            self.calls.append("resolve_idea_contract")
            return {}

        def evaluate_paper_review(self, workspace: Path) -> dict[str, object]:
            self.calls.append("evaluate_paper_review")
            return {"dimensions": []}

        def evaluate_evidence_review(self, workspace: Path) -> dict[str, object]:
            self.calls.append("evaluate_evidence_review")
            return {"dimensions": []}

        def draft_profile(self, workspace: Path) -> str:
            self.calls.append("draft_profile")
            return "survey"

        def global_citation_min_subsections(self, workspace: Path) -> int:
            self.calls.append("global_citation_min_subsections")
            return 4

        def quality_contract_int(
            self, workspace: Path, *, keys: tuple, default: int
        ) -> int:
            self.calls.append("quality_contract_int")
            return int(default)

        def per_subsection(self, workspace: Path) -> int:
            self.calls.append("per_subsection")
            return 3

        def template_residue_document_issues(
            self, workspace: Path, documents: list
        ) -> list:
            self.calls.append("template_residue_document_issues")
            return []

        def template_residue_subsection_issues(
            self, workspace: Path, relpaths: list
        ) -> list:
            self.calls.append("template_residue_subsection_issues")
            return []

        def structure_mode(self, workspace: Path) -> str:
            self.calls.append("structure_mode")
            return ""

        def section_first_artifact_issues(self, workspace: Path, *, consumer: str) -> list:
            self.calls.append("section_first_artifact_issues")
            return []

        def section_first_cutover_issues(
            self, workspace: Path, *, consumer: str, require_stable_h3: bool
        ) -> list:
            self.calls.append("section_first_cutover_issues")
            return []

    reader = _RecordingReader()
    assert isinstance(reader, WorkspacePolicyPort)
    provider = NativeQualityProvider(policy=reader)
    assert provider.policy is reader
    # Default legacy provider still handles quality checks unchanged.
    assert (
        provider.check_unit_outputs(
            skill="no-such-skill-xyz", workspace=Path("."), outputs=[]
        )
        == []
    )
