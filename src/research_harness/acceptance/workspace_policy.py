"""Typed acceptance Port for workspace-policy reads.

Several deterministic quality checks (the survey-retrieval / delivery family)
do not merely inspect a Unit's declared output file: they first read *workspace
policy* -- the run profile, evidence mode, core-set target, and the pipeline's
quality contract -- which today lives in ``PIPELINE.lock.md`` / ``queries.md``
resolved through the pipeline spec.  Those reads are the real coupling that
keeps such checks in ``tooling``.

This module declares the seam for that policy surface, expressed entirely
inside ``research_harness`` with no ``tooling`` import (mirroring
``quality_provider``).  A concrete backend implements
:class:`WorkspacePolicyPort` and is injected as an adapter; the transitional
implementation is ``LegacyToolingPolicyReader`` in ``legacy_tooling`` (the
single named seam that wraps ``tooling``).

The method surface is a deliberately small, coherent subset: the policy reads
the siblings of ``check_citation_injection`` in
``tooling.quality_checks.survey_retrieval`` depend on, plus the Goal-constraint
read the delivery ``latex-compile-qa`` check needs.  It is the seam that lets
those checks go native without hauling in the whole of ``tooling.common``.
Generic file readers (e.g. ``read_jsonl``) are intentionally *not* here: they
are not workspace policy.

Signatures mirror the module-level helpers in
``tooling.quality_checks.survey_policy`` and ``tooling.common`` exactly so a
future native reader can be swapped in without touching call sites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkspacePolicyPort(Protocol):
    """Port for the workspace-policy reads a native survey check would need.

    Methods mirror the current ``tooling.quality_checks.survey_policy`` /
    ``tooling.common`` functions exactly so the coupling is expressed as this
    single named seam plus one adapter.
    """

    def pipeline_profile_name(self, workspace: Path) -> str:
        """Return the run's pipeline profile (``"default"`` when unresolved)."""
        ...

    def evidence_mode(self, workspace: Path) -> str:
        """Return the run's research-evidence mode (``"abstract"`` or ``"fulltext"``)."""
        ...

    def core_size(self, workspace: Path) -> int:
        """Return the core-set size contract for the run."""
        ...

    def pipeline_quality_contract_value(
        self, workspace: Path, *keys: str, default: Any = None
    ) -> Any:
        """Return a nested value from the pipeline's quality contract, or ``default``."""
        ...

    def workspace_goal_constraints(self, workspace: Path) -> dict[str, Any]:
        """Return the run's structured Goal constraints (``{}`` when unresolved).

        Mirrors ``tooling.common.load_workspace_goal_constraints``: reads
        ``.harness/goal.json`` first, falling back to parsing ``GOAL.md``.  A
        native delivery check (``latex-compile-qa``) reads the ``page_range``
        constraint through this rather than importing ``tooling.common``.
        """
        ...

    def has_pipeline_contract(self, workspace: Path) -> bool:
        """Return whether the run has a resolvable active pipeline contract.

        Mirrors ``tooling.common.load_workspace_pipeline_spec(workspace) is not
        None``.  The native ideation checks use this as the pre-flight guard
        before resolving the full ideation contract.
        """
        ...

    def resolve_idea_contract(self, workspace: Path) -> dict[str, Any]:
        """Return the resolved ideation runtime contract for the run.

        Mirrors ``tooling.ideation.resolve_idea_contract``: reads the pipeline
        spec's ``query_defaults`` / ``quality_contract``, the ``DECISIONS.md``
        C2 focus selection, and ``IDEA_BRIEF.md`` into the validated size/policy
        contract the native ``research_idea`` checks read (raising on an invalid
        or missing contract).  Kept behind the Port because resolution is a
        heavyweight workspace-policy read, not output inspection.
        """
        ...

    def evaluate_paper_review(self, workspace: Path) -> dict[str, Any]:
        """Return the paper-review scorecard for the run.

        Mirrors ``tooling.review_evaluation.evaluate_paper_review``: reads the
        review artifacts (``CLAIMS.jsonl``, ``EVIDENCE_AUDIT.jsonl``,
        ``NOVELTY_MATRIX.tsv``, ``REVIEW.md``) and the rubric policy into a
        scorecard whose ``dimensions`` the native ``paper_review`` checks read.
        Kept behind the Port because scoring is a heavyweight evaluator, not
        output inspection.
        """
        ...

    def evaluate_evidence_review(self, workspace: Path) -> dict[str, Any]:
        """Return the evidence-review scorecard for the run.

        Mirrors ``tooling.evidence_review_evaluation.evaluate_evidence_review``:
        reads protocol / screening / extraction / synthesis artifacts and the
        candidate pool into a scorecard whose ``synthesis_traceability``
        dimension the native ``check_synthesis`` reads.  Kept behind the Port
        because scoring is a heavyweight evaluator, not output inspection.
        """
        ...

    def draft_profile(self, workspace: Path) -> str:
        """Return the draft strictness profile (``survey`` / ``deep`` / ``course_paper``).

        Mirrors ``tooling.quality_checks.survey_policy.draft_profile``.
        """
        ...

    def global_citation_min_subsections(self, workspace: Path) -> int:
        """Return the min subsection-mapping count for a globally in-scope bibkey.

        Mirrors ``tooling.quality_checks.survey_policy.global_citation_min_subsections``.
        """
        ...

    def quality_contract_int(
        self, workspace: Path, *, keys: tuple[str, ...], default: int
    ) -> int:
        """Return a positive int from the quality contract, or ``default``.

        Mirrors ``tooling.quality_checks.survey_policy.quality_contract_int``.
        """
        ...

    def per_subsection(self, workspace: Path) -> int:
        """Return the per-H3 mapping contract for the run.

        Mirrors ``tooling.quality_checks.survey_policy.per_subsection``.
        """
        ...

    def template_residue_document_issues(
        self, workspace: Path, documents: list[tuple[str, str]]
    ) -> list[Any]:
        """Return template-residue issues for a set of (relpath, text) documents.

        Mirrors ``tooling.quality_checks.template_residue.check_template_residue_documents``.
        Kept behind the Port because it runs a heavyweight evaluator that reads
        Run-state implementation fingerprints and repo template assets, not just
        the passed documents.  Returns objects with ``code`` + ``message``.
        """
        ...

    def template_residue_subsection_issues(
        self, workspace: Path, relpaths: list[str]
    ) -> list[Any]:
        """Return template-residue issues for subsection files named by relpath.

        Mirrors ``tooling.quality_checks.template_residue.check_subsection_template_residue``
        (reads each relpath under the workspace, then evaluates).  Kept behind
        the Port for the same reason as ``template_residue_document_issues``.
        """
        ...

    def structure_mode(self, workspace: Path) -> str:
        """Return the run's structure mode (``"section_first"`` or ``""``).

        Mirrors ``tooling.quality_checks.survey_structure.structure_mode`` (reads
        the pipeline spec's ``structure_mode``).
        """
        ...

    def section_first_artifact_issues(self, workspace: Path, *, consumer: str) -> list[Any]:
        """Return section-first C2-artifact gate issues for a consumer.

        Mirrors ``tooling.quality_checks.survey_structure.section_first_artifact_issues``:
        under section_first mode, requires the C2 artifacts to exist and be
        non-empty.  Returns objects with ``code`` + ``message``.
        """
        ...

    def section_first_cutover_issues(
        self, workspace: Path, *, consumer: str, require_stable_h3: bool
    ) -> list[Any]:
        """Return section-first cutover-state gate issues for a consumer.

        Mirrors ``tooling.quality_checks.survey_structure.section_first_cutover_issues``:
        under section_first mode, validates ``outline/outline_state.jsonl``
        cutover state.  Returns objects with ``code`` + ``message``.
        """
        ...
