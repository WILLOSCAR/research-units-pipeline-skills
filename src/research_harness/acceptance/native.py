"""Native (tooling-free) slice of the acceptance quality-check Port.

This module is a growing step toward a native
:class:`~.quality_provider.QualityCheckProvider` that does not import
``tooling`` at all.  It:

- answers the registry-introspection methods
  (:meth:`~NativeQualityProvider.registered_quality_skills` and
  :meth:`~NativeQualityProvider.has_completion_invariant`) from native
  constant tables that mirror ``tooling.quality_gate`` -- removing the registry
  coupling for those two methods; and
- natively reimplements the self-contained semantic output checks whose
  faithful reproduction needs only the ``QualityIssue`` shape (code + message),
  the stdlib, and pure helpers ported here -- currently ``citation-injector``,
  ``deliverable-selfloop``, ``artifact-contract-auditor``, and
  ``beamer-compile-qa`` -- delegating every other ``check_unit_outputs`` call
  and *all* ``check_completion_invariants`` calls to a composed legacy adapter.

Unlike ``legacy_tooling``, this module imports no ``tooling`` symbols -- not
even lazily.  Composition delegates to ``LegacyToolingQualityProvider``, which
is the only module that wraps ``tooling`` (and it does so lazily).

This provider is intentionally *not* the default: ``default_quality_provider``
still returns the legacy adapter, so runtime behavior is unchanged.  Swapping
the default is a later, separately gated step.  The native constant tables are
kept honest by the Port parity test, which asserts they equal the legacy
provider's registry, and every native check is pinned to byte-for-byte parity
(codes + messages) with its legacy counterpart.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .legacy_tooling import LegacyToolingPolicyReader, LegacyToolingQualityProvider
from .quality_provider import QualityCheckProvider, QualityIssueLike
from .workspace_policy import WorkspacePolicyPort

# Native mirror of ``tooling.quality_gate._QUALITY_CHECKS`` keys: Skills with a
# semantic check beyond output existence.  The Port parity test pins this to
# the legacy registry so drift is caught rather than silently diverging.
_NATIVE_QUALITY_SKILLS: frozenset[str] = frozenset(
    {
        "anchor-sheet",
        "appendix-table-writer",
        "argument-selfloop",
        "artifact-contract-auditor",
        "arxiv-search",
        "beamer-compile-qa",
        "beamer-scaffold",
        "bias-assessor",
        "chapter-briefs",
        "chapter-skeleton",
        "citation-injector",
        "citation-verifier",
        "claim-evidence-matrix",
        "claim-matrix-rewriter",
        "claims-extractor",
        "dedupe-rank",
        "deliverable-selfloop",
        "draft-polisher",
        "evaluation-anchor-checker",
        "evidence-auditor",
        "evidence-binder",
        "evidence-draft",
        "evidence-selfloop",
        "extraction-form",
        "front-matter-writer",
        "global-reviewer",
        "idea-brief",
        "idea-direction-generator",
        "idea-memo-writer",
        "idea-screener",
        "idea-shortlist-curator",
        "idea-signal-mapper",
        "latex-compile-qa",
        "latex-scaffold",
        "literature-engineer",
        "module-source-coverage",
        "novelty-matrix",
        "outline-builder",
        "outline-refiner",
        "paper-notes",
        "paragraph-curator",
        "pdf-text-extractor",
        "pipeline-auditor",
        "prose-writer",
        "protocol-writer",
        "rubric-writer",
        "schema-normalizer",
        "screening-manager",
        "section-bindings",
        "section-briefs",
        "section-logic-polisher",
        "section-mapper",
        "section-merger",
        "source-ingest",
        "source-manifest",
        "source-tutorial-spec",
        "subsection-briefs",
        "subsection-writer",
        "survey-visuals",
        "synthesis-writer",
        "table-filler",
        "table-schema",
        "taxonomy-builder",
        "transition-weaver",
        "tutorial-context-pack",
        "tutorial-selfloop",
        "writer-context-pack",
        "writer-selfloop",
    }
)

# Native mirror of ``tooling.quality_gate._COMPLETION_INVARIANTS`` keys: Skills
# with a mandatory Workflow-domain invariant.  No invariant is reimplemented
# natively yet, so ``check_completion_invariants`` delegates in full; this
# table only serves the (pure introspection) ``has_completion_invariant``.
_NATIVE_COMPLETION_INVARIANTS: frozenset[str] = frozenset({"outline-refiner"})

# Skills whose semantic output check this provider answers natively, with zero
# tooling delegation.  Everything else composes onto the legacy adapter.  The
# dispatch table below binds each Skill to its native reimplementation; the set
# is derived from it so the two never drift.


@dataclass(frozen=True, slots=True)
class NativeQualityIssue:
    """A native quality issue; structurally satisfies :class:`QualityIssueLike`."""

    code: str
    message: str


def _has_placeholder_markers(text: str) -> bool:
    """Native mirror of ``tooling.quality_checks.common.has_placeholder_markers``."""

    if not text:
        return False
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return True
    lowered = text.lower()
    return "(placeholder)" in lowered or "<!-- scaffold" in lowered


def _check_citation_injector(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_citation_injection``.

    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity test.  The report must exist, be non-empty, be free of
    placeholder/ellipsis residue, and self-report ``Status: PASS``.
    """

    report_rel = next(
        (p for p in outputs if p.endswith("CITATION_INJECTION_REPORT.md")),
        "output/CITATION_INJECTION_REPORT.md",
    )
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_citation_injection_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]

    text = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_citation_injection_report",
                message=f"`{report_rel}` is empty.",
            )
        ]
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="citation_injection_report_placeholders",
                message=(
                    f"`{report_rel}` contains placeholders/ellipsis; "
                    "regenerate after fixing the injection step."
                ),
            )
        ]
    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []
    return [
        NativeQualityIssue(
            code="citation_injection_failed",
            message=(
                f"`{report_rel}` is not PASS; add more in-scope unused citations "
                "(or expand C1/C2 mapping), then rerun citation injection."
            ),
        )
    ]


def _check_deliverable_selfloop(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_deliverable_selfloop_report``.

    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity test.  The self-loop TODO must exist, be non-empty, be free
    of placeholder/ellipsis residue, and self-report ``- Status: PASS``.
    """

    report_rel = next(
        (path for path in outputs if path.endswith("DELIVERABLE_SELFLOOP_TODO.md")),
        "output/DELIVERABLE_SELFLOOP_TODO.md",
    )
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_deliverable_selfloop_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="deliverable_selfloop_placeholders",
                message=f"`{report_rel}` contains placeholders/ellipsis.",
            )
        ]
    if "- Status: PASS" not in text:
        return [
            NativeQualityIssue(
                code="deliverable_selfloop_not_pass",
                message=f"`{report_rel}` is not PASS.",
            )
        ]
    return []


def _check_artifact_contract_auditor(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_contract_report``.

    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity test.  The contract report must exist, be non-empty, be
    free of placeholder/ellipsis residue, and self-report both ``- Status:
    PASS`` and ``- Pipeline complete (units): yes``.
    """

    out_rel = next(
        (p for p in outputs if p.endswith("CONTRACT_REPORT.md")),
        "output/CONTRACT_REPORT.md",
    )
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_contract_report",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_contract_report",
                message=f"`{out_rel}` is empty.",
            )
        ]
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="contract_report_placeholders",
                message=(
                    f"`{out_rel}` contains placeholders/ellipsis; "
                    "regenerate after fixing missing artifacts."
                ),
            )
        ]

    ok_status = bool(re.search(r"(?im)^-\s*Status:\s*PASS\b", text))
    ok_complete = bool(
        re.search(r"(?im)^-\s*Pipeline complete \(units\):\s*yes\b", text)
    )
    if ok_status and ok_complete:
        return []

    return [
        NativeQualityIssue(
            code="contract_report_not_pass",
            message=(
                f"`{out_rel}` is not PASS (or pipeline not complete). "
                "Fix missing artifacts / unit statuses and rerun "
                "`artifact-contract-auditor`."
            ),
        )
    ]


def _check_beamer_compile_qa(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_beamer_compile_qa``.

    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity test.  The compiled PDF and its build report must both
    exist, and the report must self-report ``Status: PASS``.
    """

    pdf_rel = outputs[0] if outputs else "latex/slides/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/SLIDES_BUILD_REPORT.md"
    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    if not pdf_path.exists():
        return [
            NativeQualityIssue(
                code="missing_beamer_pdf",
                message=f"`{pdf_rel}` does not exist.",
            )
        ]
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_slides_build_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if "- Status: PASS" not in text and "Status: PASS" not in text:
        return [
            NativeQualityIssue(
                code="beamer_build_not_pass",
                message=f"`{report_rel}` is not PASS.",
            )
        ]
    return []


# Dispatch table binding each natively covered Skill to its reimplementation.
# ``_NATIVE_OUTPUT_CHECKS`` (the routing set used by ``check_unit_outputs``) is
# derived from this so the table and the set can never drift apart.
_NativeUnitCheck = Callable[[Path, list[str]], list[NativeQualityIssue]]

_NATIVE_UNIT_CHECKS: dict[str, _NativeUnitCheck] = {
    "citation-injector": _check_citation_injector,
    "deliverable-selfloop": _check_deliverable_selfloop,
    "artifact-contract-auditor": _check_artifact_contract_auditor,
    "beamer-compile-qa": _check_beamer_compile_qa,
}

_NATIVE_OUTPUT_CHECKS: frozenset[str] = frozenset(_NATIVE_UNIT_CHECKS)


@dataclass(frozen=True)
class NativeQualityProvider(QualityCheckProvider):
    """Composition provider: native registry + native checks, else legacy.

    - :meth:`registered_quality_skills` / :meth:`has_completion_invariant`
      answer from native constant tables, with no ``tooling`` import.
    - :meth:`check_unit_outputs` handles the natively reimplemented Skill(s)
      directly (via ``_NATIVE_UNIT_CHECKS``) and delegates every other Skill to
      the composed legacy adapter.
    - :meth:`check_completion_invariants` delegates in full: no invariant has a
      native reimplementation yet.

    ``policy`` is the injected :class:`WorkspacePolicyPort` a future native
    survey check reads workspace policy (run profile, evidence mode, core-set
    target, quality contract) through.  It defaults to the legacy adapter so
    runtime behavior is unchanged; no native check consumes it yet, so it is
    only a landed seam at this step.
    """

    legacy: QualityCheckProvider = field(default_factory=LegacyToolingQualityProvider)
    policy: WorkspacePolicyPort = field(default_factory=LegacyToolingPolicyReader)

    def registered_quality_skills(self) -> frozenset[str]:
        return _NATIVE_QUALITY_SKILLS

    def has_completion_invariant(self, skill: str) -> bool:
        return skill in _NATIVE_COMPLETION_INVARIANTS

    def check_completion_invariants(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        return self.legacy.check_completion_invariants(
            skill=skill, workspace=workspace, outputs=outputs
        )

    def check_unit_outputs(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        native_check = _NATIVE_UNIT_CHECKS.get(skill)
        if native_check is not None:
            return list(native_check(workspace, outputs))
        return self.legacy.check_unit_outputs(
            skill=skill, workspace=workspace, outputs=outputs
        )
