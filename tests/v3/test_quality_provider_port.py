"""Contract tests for the acceptance quality-check Port seam.

The acceptance layer talks to deterministic quality checks only through the
``QualityCheckProvider`` Port (declared in ``research_harness`` with no
``tooling`` import). The current backend is the transitional
``LegacyToolingQualityProvider`` adapter. These tests lock in that seam so:

- the decoupling cannot silently regress (a call site re-importing ``tooling``
  directly would not be caught by these, but a broken Port surface would);
- the adapter stays a faithful pass-through to ``tooling.quality_gate``; and
- a future *native* provider has an executable contract to satisfy.
"""

from __future__ import annotations

from pathlib import Path

from research_harness.acceptance import (
    LegacyToolingQualityProvider,
    QualityCheckProvider,
    RepositoryQualityEvaluator,
    build_repository_acceptance_policy,
    default_quality_provider,
)


def test_default_provider_satisfies_the_port() -> None:
    provider = default_quality_provider()
    assert isinstance(provider, LegacyToolingQualityProvider)
    # runtime_checkable Protocol: the adapter structurally satisfies the Port.
    assert isinstance(provider, QualityCheckProvider)


def test_port_surface_is_complete() -> None:
    provider = default_quality_provider()
    for method in (
        "registered_quality_skills",
        "has_completion_invariant",
        "check_completion_invariants",
        "check_unit_outputs",
    ):
        assert callable(getattr(provider, method)), method


def test_registered_skills_pass_through_to_tooling() -> None:
    # The adapter must mirror tooling.quality_gate exactly; this is the
    # invariant a future native provider must also preserve.
    from tooling.quality_gate import registered_quality_skills as legacy

    provider = default_quality_provider()
    assert provider.registered_quality_skills() == legacy()
    assert len(provider.registered_quality_skills()) > 0


def test_has_completion_invariant_pass_through() -> None:
    from tooling.quality_gate import registered_quality_skills

    provider = default_quality_provider()
    # For every registered skill, the adapter's invariant flag agrees with the
    # legacy predicate.
    from tooling.quality_gate import has_completion_invariant as legacy_has

    for skill in registered_quality_skills():
        assert provider.has_completion_invariant(skill) == legacy_has(skill)
    # An unknown skill has no invariant.
    assert provider.has_completion_invariant("no-such-skill-xyz") is False


def test_check_methods_return_lists_for_unknown_skill(tmp_path: Path) -> None:
    provider = default_quality_provider()
    # An unregistered skill yields no issues (empty list), not an error.
    assert (
        provider.check_completion_invariants(
            skill="no-such-skill-xyz", workspace=tmp_path, outputs=[]
        )
        == []
    )
    assert (
        provider.check_unit_outputs(
            skill="no-such-skill-xyz", workspace=tmp_path, outputs=[]
        )
        == []
    )


class _RecordingProvider:
    """A minimal native-shaped provider, proving the seam is injectable."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def registered_quality_skills(self) -> frozenset[str]:
        self.calls.append("registered_quality_skills")
        return frozenset()

    def has_completion_invariant(self, skill: str) -> bool:
        self.calls.append(f"has_completion_invariant:{skill}")
        return False

    def check_completion_invariants(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[object]:
        self.calls.append(f"check_completion_invariants:{skill}")
        return []

    def check_unit_outputs(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[object]:
        self.calls.append(f"check_unit_outputs:{skill}")
        return []


def test_seam_is_injectable_without_tooling() -> None:
    # A hand-written provider satisfies the Port and can be injected into both
    # the evaluator and the policy builder, with no tooling dependency.
    provider = _RecordingProvider()
    assert isinstance(provider, QualityCheckProvider)

    evaluator = RepositoryQualityEvaluator(
        workspace_for_run=lambda _run_id: Path("."),
        provider=provider,
    )
    assert evaluator.provider is provider

    policy = build_repository_acceptance_policy(
        workflows=(),
        workspace_for_run=lambda _run_id: Path("."),
        provider=provider,
    )
    assert policy is not None
