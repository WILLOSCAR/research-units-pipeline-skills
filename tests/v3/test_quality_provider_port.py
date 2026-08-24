"""Contract tests for the acceptance quality-check Port seam.

The acceptance layer talks to deterministic quality checks only through the
``QualityCheckProvider`` Port (declared in ``research_harness`` with no
``tooling`` import). The default backend is the tooling-free
``NativeQualityProvider``; ``LegacyToolingQualityProvider`` is retained as a
reversible escape hatch. These tests lock in that seam so:

- the decoupling cannot silently regress (a call site re-importing ``tooling``
  directly would not be caught by these, but a broken Port surface would);
- the legacy adapter stays a faithful pass-through to ``tooling.quality_gate``; and
- the native provider keeps satisfying the executable contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.acceptance import (
    LegacyToolingQualityProvider,
    NativeQualityProvider,
    QualityCheckProvider,
    RepositoryQualityEvaluator,
    build_repository_acceptance_policy,
    default_quality_provider,
)
from research_harness.acceptance.legacy_tooling import _QUALITY_PROVIDER_ENV_VAR


def test_default_provider_satisfies_the_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The default is now the native provider (byte-identical, proven by the
    # 68-skill sweep); clear the opt-in so this reflects the real default
    # regardless of ambient env, then confirm it satisfies the Port.
    monkeypatch.delenv(_QUALITY_PROVIDER_ENV_VAR, raising=False)
    provider = default_quality_provider()
    assert isinstance(provider, NativeQualityProvider)
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
    # The legacy adapter must mirror tooling.quality_gate exactly; the native
    # provider (now default) mirrors the same registry via its constant tables.
    from tooling.quality_gate import registered_quality_skills as legacy

    provider = LegacyToolingQualityProvider()
    assert provider.registered_quality_skills() == legacy()
    assert len(provider.registered_quality_skills()) > 0


def test_has_completion_invariant_pass_through() -> None:
    from tooling.quality_gate import registered_quality_skills

    provider = LegacyToolingQualityProvider()
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


# --- provider selection (post-cutover: native is the default) --------------


def test_default_is_native_when_opt_in_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # After the cutover, no opt-in resolves to the native provider.
    monkeypatch.delenv(_QUALITY_PROVIDER_ENV_VAR, raising=False)
    assert isinstance(default_quality_provider(), NativeQualityProvider)


def test_native_selected_by_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_QUALITY_PROVIDER_ENV_VAR, "native")
    assert isinstance(default_quality_provider(), NativeQualityProvider)


def test_legacy_selected_when_opt_in_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `legacy` is the retained escape hatch back to the tooling adapter.
    monkeypatch.setenv(_QUALITY_PROVIDER_ENV_VAR, "legacy")
    assert isinstance(default_quality_provider(), LegacyToolingQualityProvider)


def test_opt_in_parsing_is_case_and_whitespace_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_QUALITY_PROVIDER_ENV_VAR, "  LeGaCy \t")
    assert isinstance(default_quality_provider(), LegacyToolingQualityProvider)


@pytest.mark.parametrize("value", ["", "  ", "legacy-ish", "legac", "1", "true", "?"])
def test_unrecognized_opt_in_falls_back_to_native(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    # Defensive parsing: any value that is not exactly ``native``/``legacy``
    # (after strip + case-fold) resolves to native (the default), so a typo can
    # never silently revert acceptance to the legacy path.
    monkeypatch.setenv(_QUALITY_PROVIDER_ENV_VAR, value)
    assert isinstance(default_quality_provider(), NativeQualityProvider)


def test_clearing_opt_in_returns_to_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Selecting legacy then clearing the opt-in reverts to the native default,
    # proving the toggle is fully reversible and leaks no global state.
    monkeypatch.setenv(_QUALITY_PROVIDER_ENV_VAR, "legacy")
    assert isinstance(default_quality_provider(), LegacyToolingQualityProvider)
    monkeypatch.delenv(_QUALITY_PROVIDER_ENV_VAR, raising=False)
    assert isinstance(default_quality_provider(), NativeQualityProvider)
