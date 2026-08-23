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
  and *all* ``check_completion_invariants`` calls to a composed legacy adapter;
  and
- reimplements the first *policy-consuming* output check, ``citation-verifier``,
  which reads workspace policy (run profile + core-set target) through the
  injected :class:`WorkspacePolicyPort` rather than importing
  ``tooling.quality_checks.survey_policy`` -- exercising that seam for real
  instead of leaving it merely constructed.

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

import json
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


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Native mirror of ``tooling.common.read_jsonl``.

    Reads one JSON object per non-blank line.  Kept byte-identical in behavior
    to the legacy reader (including that a malformed line raises, exactly as
    ``json.loads`` does there) so a check ported to use it stays a faithful
    reproduction.
    """

    records: list[dict[str, object]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


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


def _check_citation_verifier(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_citations``.

    This is the first *policy-consuming* native check: it reads the run profile
    and core-set target through the injected :class:`WorkspacePolicyPort`
    (``pipeline_profile_name`` + ``core_size``) rather than importing
    ``tooling.quality_checks.survey_policy``.  Everything else -- the BibTeX key
    scan, the verification-record join, and the field validation -- is pure
    stdlib.  Byte-for-byte parity (codes + messages, and short-circuit order)
    with the legacy check is pinned by the Port parity sweep; the
    ``arxiv-survey`` branch is exercised through a real workspace so the policy
    seam is proven, not merely constructed.
    """

    bib_rel = outputs[0] if outputs else "citations/ref.bib"
    verified_rel = outputs[1] if len(outputs) >= 2 else "citations/verified.jsonl"

    bib_path = workspace / bib_rel
    verified_path = workspace / verified_rel

    if not bib_path.exists():
        return [
            NativeQualityIssue(
                code="missing_ref_bib", message=f"`{bib_rel}` does not exist."
            )
        ]
    if not verified_path.exists():
        return [
            NativeQualityIssue(
                code="missing_verified_jsonl",
                message=f"`{verified_rel}` does not exist.",
            )
        ]

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
    bib_keys = re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)
    if not bib_keys:
        return [
            NativeQualityIssue(
                code="empty_ref_bib", message=f"`{bib_rel}` has no BibTeX entries."
            )
        ]

    dupes = len(bib_keys) - len(set(bib_keys))
    if dupes:
        return [
            NativeQualityIssue(
                code="citations_duplicate_bibkeys",
                message=(
                    f"`{bib_rel}` has duplicate BibTeX keys ({dupes}); "
                    "dedupe/rename keys before compiling LaTeX."
                ),
            )
        ]

    profile = policy.pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_bib = int(policy.core_size(workspace)) or 150
        if len(bib_keys) < min_bib:
            return [
                NativeQualityIssue(
                    code="citations_too_few_entries",
                    message=(
                        f"`{bib_rel}` has only {len(bib_keys)} entries; target >= "
                        f"{min_bib} for a survey-quality run "
                        "(expand retrieval / snowball / imports)."
                    ),
                )
            ]

    records = _read_jsonl(verified_path)
    recs = [r for r in records if isinstance(r, dict)]
    if not recs:
        return [
            NativeQualityIssue(
                code="empty_verified_jsonl", message=f"`{verified_rel}` is empty."
            )
        ]

    by_key: dict[str, dict[str, object]] = {}
    for rec in recs:
        key = str(rec.get("bibkey") or "").strip()
        if key:
            by_key[key] = rec

    missing = [k for k in bib_keys if k not in by_key]
    if missing:
        sample = ", ".join(missing[:5])
        suffix = "..." if len(missing) > 5 else ""
        return [
            NativeQualityIssue(
                code="citations_missing_verification_records",
                message=(
                    "Some BibTeX keys have no matching verification record in "
                    f"`{verified_rel}` (e.g., {sample}{suffix})."
                ),
            )
        ]

    bad_fields = 0
    for k in bib_keys:
        rec = by_key.get(k) or {}
        title = str(rec.get("title") or "").strip()
        url = str(rec.get("url") or "").strip()
        date = str(rec.get("date") or "").strip()
        if not title or not url or not date:
            bad_fields += 1
            continue
        status = str(rec.get("verification_status") or "").strip()
        if status and status not in {
            "verified_online",
            "offline_generated",
            "verify_failed",
            "needs_manual_verification",
        }:
            bad_fields += 1

    if bad_fields:
        return [
            NativeQualityIssue(
                code="citations_invalid_verification_records",
                message=(
                    f"`{verified_rel}` has {bad_fields} record(s) missing required "
                    "fields or with unknown `verification_status`."
                ),
            )
        ]
    return []


# Dispatch table for the *policy-consuming* native checks.  These take the
# injected ``WorkspacePolicyPort`` as a third argument (the run profile /
# core-set target reads that keep such checks coupled to ``tooling`` today), so
# they route through a distinct table from the self-contained checks above.
# ``_NATIVE_POLICY_CHECKS`` (the routing set) is derived from this so the two
# never drift.
_NativePolicyCheck = Callable[
    [Path, list[str], WorkspacePolicyPort], list[NativeQualityIssue]
]

_NATIVE_POLICY_UNIT_CHECKS: dict[str, _NativePolicyCheck] = {
    "citation-verifier": _check_citation_verifier,
}

_NATIVE_POLICY_CHECKS: frozenset[str] = frozenset(_NATIVE_POLICY_UNIT_CHECKS)


@dataclass(frozen=True)
class NativeQualityProvider(QualityCheckProvider):
    """Composition provider: native registry + native checks, else legacy.

    - :meth:`registered_quality_skills` / :meth:`has_completion_invariant`
      answer from native constant tables, with no ``tooling`` import.
    - :meth:`check_unit_outputs` handles the self-contained native Skills (via
      ``_NATIVE_UNIT_CHECKS``) and the policy-consuming native Skills (via
      ``_NATIVE_POLICY_UNIT_CHECKS``, passing the injected ``policy``), and
      delegates every other Skill to the composed legacy adapter.
    - :meth:`check_completion_invariants` delegates in full: no invariant has a
      native reimplementation yet.

    ``policy`` is the injected :class:`WorkspacePolicyPort` the policy-consuming
    native checks read workspace policy (run profile, evidence mode, core-set
    target, quality contract) through.  It defaults to the legacy adapter so
    runtime behavior is unchanged; ``citation-verifier`` is the first check that
    consumes it, so the seam is now load-bearing rather than merely constructed.
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
        policy_check = _NATIVE_POLICY_UNIT_CHECKS.get(skill)
        if policy_check is not None:
            return list(policy_check(workspace, outputs, self.policy))
        return self.legacy.check_unit_outputs(
            skill=skill, workspace=workspace, outputs=outputs
        )
