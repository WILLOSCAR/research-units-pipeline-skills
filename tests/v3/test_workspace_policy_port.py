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
