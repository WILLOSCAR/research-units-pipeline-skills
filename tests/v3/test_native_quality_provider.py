"""Contract tests for the first native quality-check provider slice.

``NativeQualityProvider`` is the first tooling-free step behind the
``QualityCheckProvider`` Port.  It answers registry introspection from native
constant tables and reimplements the single smallest self-contained semantic
check (``citation-injector``), delegating everything else to the legacy
adapter.  These tests lock in:

- Port conformance (``isinstance`` of the runtime-checkable Protocol);
- registry parity with the legacy provider (the native constant tables must
  not drift from ``tooling.quality_gate``);
- native behavior for ``citation-injector`` matching the legacy check exactly;
- delegation to the composed legacy adapter for a non-native skill; and
- that ``native.py`` imports no ``tooling`` symbols at module top.
"""

from __future__ import annotations

import ast
from pathlib import Path

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

    assert ("outputs", "arxiv-search") in calls
    assert ("invariants", "outline-refiner") in calls
    assert ("outputs", "citation-injector") not in calls


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
