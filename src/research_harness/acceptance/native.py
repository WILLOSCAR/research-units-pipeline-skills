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
  the stdlib, and pure helpers ported here -- the delivery-family
  ``citation-injector``, ``deliverable-selfloop``, ``artifact-contract-auditor``,
  ``beamer-compile-qa``, ``beamer-scaffold``, and the **entire
  ``tooling.quality_checks.source_tutorial`` module** (``source-manifest``,
  ``source-ingest``, ``source-tutorial-spec``, ``module-source-coverage``,
  ``tutorial-context-pack``, ``tutorial-selfloop``) -- delegating every other
  ``check_unit_outputs`` call and *all* ``check_completion_invariants`` calls to
  a composed legacy adapter; and
- reimplements the *policy-consuming* output checks of the survey-retrieval
  family in full -- ``citation-verifier``, ``arxiv-search``,
  ``pdf-text-extractor``, ``literature-engineer``, and ``dedupe-rank`` -- plus
  the delivery family in full -- ``latex-scaffold`` and ``latex-compile-qa`` --
  which read workspace policy (run profile, evidence mode, core-set target, the
  retrieval / candidate-pool contracts, and the Goal page-range constraint)
  through the injected :class:`WorkspacePolicyPort` rather than importing
  ``tooling.quality_checks.survey_policy`` / ``tooling.common``.  With these,
  every check in both ``tooling.quality_checks.survey_retrieval`` and
  ``tooling.quality_checks.delivery`` has a native equivalent, exercising the
  policy seam for real instead of leaving it merely constructed.

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

import csv
import json
import re
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

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


def _check_beamer_scaffold(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_beamer_scaffold``.

    Self-contained (no policy): the generated Beamer ``main.tex`` must exist,
    declare the ``beamer`` class, contain frame structure, and be free of
    leaked markdown headings.  Byte-for-byte parity (codes + messages, and
    issue ORDER) with the legacy check is pinned by the Port parity sweep.
    """

    out_rel = outputs[0] if outputs else "latex/slides/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_beamer_tex", message=f"`{out_rel}` does not exist."
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[NativeQualityIssue] = []
    if "\\documentclass" not in text or "beamer" not in text:
        issues.append(
            NativeQualityIssue(
                code="beamer_missing_class",
                message=f"`{out_rel}` is not a Beamer document.",
            )
        )
    if "\\begin{frame}" not in text:
        issues.append(
            NativeQualityIssue(
                code="beamer_missing_frames",
                message=f"`{out_rel}` has no frame structure.",
            )
        )
    if "## " in text or "### " in text:
        issues.append(
            NativeQualityIssue(
                code="beamer_markdown_headings",
                message=f"`{out_rel}` still contains markdown headings.",
            )
        )
    return issues


# --- source-tutorial family (self-contained) --------------------------------
#
# Native reimplementation of the whole ``tooling.quality_checks.source_tutorial``
# module.  These six checks read only their declared JSONL/YAML/Markdown outputs
# -- no workspace policy -- so they are self-contained.  Their only ``tooling``
# couplings are the tiny helpers ``load_yaml`` (a ``yaml.safe_load`` wrapper) and
# ``load_source_tutorial_spec_data`` (an 8-line regex/json extractor), both
# reimplemented natively below.  The shared grounding/provenance helpers and the
# cross-check calls (``check_tutorial_context_packs`` -> ``check_module_source_
# coverage``; ``check_tutorial_selfloop_report`` -> ``tutorial_contract_issues``
# -> ``check_tutorial_context_packs``) are preserved exactly so behavior --
# including issue ORDER and the JSONL-error short-circuits -- matches legacy.


class _InvalidJsonl(ValueError):
    """Native mirror of ``source_tutorial._InvalidJsonl``."""

    def __init__(self, path: Path, line_number: int, detail: str) -> None:
        location = f" line {line_number}" if line_number else ""
        super().__init__(f"`{path.as_posix()}`{location} is invalid JSONL: {detail}")


def _st_read_jsonl_records(path: Path) -> list[Any]:
    """Native mirror of ``source_tutorial._read_jsonl_records``.

    Distinct from ``_read_jsonl``: this raises ``_InvalidJsonl`` on a malformed
    line (carrying path + line number + detail) rather than propagating the raw
    ``JSONDecodeError``, and returns raw records (not filtered to dicts).
    """

    if not path.exists():
        return []
    records: list[Any] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise _InvalidJsonl(path, 0, f"{type(exc).__name__}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise _InvalidJsonl(path, line_number, exc.msg) from exc
    return records


def _st_load_yaml(path: Path) -> Any:
    """Native mirror of ``tooling.common.load_yaml`` (``yaml.safe_load``)."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _st_load_source_tutorial_spec_data(path: Path) -> dict[str, Any]:
    """Native mirror of ``tooling.tutorial_workflows.load_source_tutorial_spec_data``."""

    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r"## Structured data\s+```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL
    )
    if match:
        payload = json.loads(match.group(1))
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"Could not read structured spec data from {path}")


def _st_resolve_workspace_path(workspace: Path, value: object) -> Path | None:
    raw = str(value or "").strip()
    candidate = Path(raw)
    if not raw or candidate.is_absolute():
        return None
    resolved = (workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace.resolve()) or not resolved.exists():
        return None
    return resolved


def _st_provenance_path_matches_index(index_path: Path, provenance_path: Path) -> bool:
    if index_path.is_dir():
        return provenance_path == index_path or provenance_path.is_relative_to(
            index_path
        )
    return provenance_path == index_path


def _st_source_grounding(workspace: Path) -> dict[str, dict[str, object]]:
    """Native mirror of ``source_tutorial._source_grounding``."""

    indexed: dict[str, Path] = {}
    for record in _st_read_jsonl_records(workspace / "sources" / "index.jsonl"):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id") or "").strip()
        index_path = _st_resolve_workspace_path(workspace, record.get("local_path"))
        if (
            str(record.get("status") or "").strip() == "success"
            and source_id
            and index_path is not None
        ):
            indexed[source_id] = index_path

    pointers: dict[str, dict[str, Path]] = {}
    for record in _st_read_jsonl_records(workspace / "sources" / "provenance.jsonl"):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id") or "").strip()
        pointer = str(record.get("pointer") or "").strip()
        origin = str(record.get("origin_url_or_path") or "").strip()
        provenance_path = _st_resolve_workspace_path(
            workspace, record.get("local_path")
        )
        index_path = indexed.get(source_id)
        if (
            source_id
            and pointer
            and origin
            and provenance_path is not None
            and index_path is not None
            and _st_provenance_path_matches_index(index_path, provenance_path)
        ):
            pointers.setdefault(source_id, {})[pointer] = provenance_path

    return {
        source_id: {"index_path": index_path, "pointers": pointers[source_id]}
        for source_id, index_path in indexed.items()
        if pointers.get(source_id)
    }


def _st_snippet_grounding_issue(
    *,
    workspace: Path,
    snippet: dict[str, object],
    grounding: dict[str, dict[str, object]],
    source_text_cache: dict[Path, str] | None = None,
) -> str:
    source_id = str(snippet.get("source_id") or "").strip()
    pointer = str(snippet.get("pointer") or "").strip()
    text = str(snippet.get("snippet") or "").strip()
    source = grounding.get(source_id)
    if source is None:
        return "source"
    pointer_paths = source.get("pointers")
    if not isinstance(pointer_paths, dict) or pointer not in pointer_paths:
        return "pointer"
    provenance_path = pointer_paths[pointer]
    if (
        not isinstance(provenance_path, Path)
        or not provenance_path.is_file()
        or not text
    ):
        return "content"
    cache = source_text_cache if source_text_cache is not None else {}
    normalized_source = cache.get(provenance_path)
    if normalized_source is None:
        source_text = provenance_path.read_text(encoding="utf-8", errors="ignore")
        normalized_source = re.sub(r"\s+", " ", source_text).strip().casefold()
        cache[provenance_path] = normalized_source
    normalized_snippet = re.sub(r"\s+", " ", text).strip().casefold()
    return (
        ""
        if normalized_snippet and normalized_snippet in normalized_source
        else "content"
    )


def _check_source_manifest(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_source_manifest``."""

    from collections import Counter

    out_rel = outputs[0] if outputs else "sources/manifest.yml"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_source_manifest", message=f"`{out_rel}` does not exist."
            )
        ]
    try:
        data = _st_load_yaml(path)
    except Exception as exc:  # noqa: BLE001 - mirror legacy broad catch + message
        return [
            NativeQualityIssue(
                code="invalid_source_manifest_yaml",
                message=f"`{out_rel}` is not valid YAML ({type(exc).__name__}: {exc}).",
            )
        ]
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list) or not sources:
        return [
            NativeQualityIssue(
                code="empty_source_manifest",
                message=f"`{out_rel}` must contain a non-empty `sources` list.",
            )
        ]
    invalid = 0
    source_ids: list[str] = []
    for rec in sources:
        if not isinstance(rec, dict):
            invalid += 1
            continue
        if (
            not rec.get("source_id")
            or not rec.get("kind")
            or not rec.get("locator")
            or not rec.get("label")
        ):
            invalid += 1
            continue
        source_ids.append(str(rec.get("source_id")).strip())
    if invalid:
        return [
            NativeQualityIssue(
                code="source_manifest_missing_fields",
                message=f"`{out_rel}` has {invalid} invalid source record(s).",
            )
        ]
    duplicate_ids = sorted(
        source_id for source_id, count in Counter(source_ids).items() if count > 1
    )
    if duplicate_ids:
        return [
            NativeQualityIssue(
                code="source_manifest_duplicate_ids",
                message=f"`{out_rel}` repeats source IDs: {', '.join(duplicate_ids)}.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "example-source" in text or "replace this scaffold" in text:
        return [
            NativeQualityIssue(
                code="source_manifest_placeholders",
                message=f"`{out_rel}` still contains scaffold placeholders.",
            )
        ]
    return []


def _check_source_ingest(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_source_ingest``."""

    from collections import Counter

    index_rel = outputs[0] if outputs else "sources/index.jsonl"
    prov_rel = outputs[1] if len(outputs) > 1 else "sources/provenance.jsonl"
    index_path = workspace / index_rel
    prov_path = workspace / prov_rel
    if not index_path.exists():
        return [
            NativeQualityIssue(
                code="missing_source_index", message=f"`{index_rel}` does not exist."
            )
        ]
    if not prov_path.exists():
        return [
            NativeQualityIssue(
                code="missing_source_provenance",
                message=f"`{prov_rel}` does not exist.",
            )
        ]
    manifest_path = workspace / "sources" / "manifest.yml"
    try:
        manifest = _st_load_yaml(manifest_path)
    except Exception as exc:  # noqa: BLE001
        return [
            NativeQualityIssue(
                code="invalid_source_manifest_yaml",
                message=(
                    f"`sources/manifest.yml` could not be loaded "
                    f"({type(exc).__name__}: {exc})."
                ),
            )
        ]
    manifest_rows = manifest.get("sources") if isinstance(manifest, dict) else None
    if not isinstance(manifest_rows, list) or not manifest_rows:
        return [
            NativeQualityIssue(
                code="empty_source_manifest",
                message="`sources/manifest.yml` has no source records.",
            )
        ]
    manifest_by_id = {
        str(rec.get("source_id") or "").strip(): rec
        for rec in manifest_rows
        if isinstance(rec, dict) and str(rec.get("source_id") or "").strip()
    }

    try:
        records = _st_read_jsonl_records(index_path)
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(
                code="source_index_invalid_jsonl", message=str(exc)
            )
        ]
    if not records:
        return [
            NativeQualityIssue(
                code="empty_source_index", message=f"`{index_rel}` is empty."
            )
        ]
    issues: list[NativeQualityIssue] = []
    success = 0
    bad = 0
    index_ids: list[str] = []
    index_by_id: dict[str, dict[str, object]] = {}
    invalid_local_paths: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            bad += 1
            continue
        source_id = str(rec.get("source_id") or "").strip()
        if not source_id or not rec.get("kind") or not rec.get("status"):
            bad += 1
            continue
        index_ids.append(source_id)
        index_by_id[source_id] = rec
        if str(rec.get("status") or "").strip() == "success":
            success += 1
            local_value = str(rec.get("local_path") or "").strip()
            candidate = Path(local_value)
            local_path = (
                (workspace / candidate).resolve()
                if local_value and not candidate.is_absolute()
                else candidate
            )
            if (
                not local_value
                or candidate.is_absolute()
                or not local_path.is_relative_to(workspace.resolve())
                or not local_path.exists()
            ):
                invalid_local_paths.append(source_id)
    if bad:
        issues.append(
            NativeQualityIssue(
                code="source_index_missing_fields",
                message=f"`{index_rel}` has {bad} invalid record(s).",
            )
        )
    duplicate_index_ids = sorted(
        source_id for source_id, count in Counter(index_ids).items() if count > 1
    )
    if duplicate_index_ids:
        issues.append(
            NativeQualityIssue(
                code="source_index_duplicate_ids",
                message=(
                    f"`{index_rel}` repeats source IDs: "
                    f"{', '.join(duplicate_index_ids)}."
                ),
            )
        )
    manifest_ids = set(manifest_by_id)
    indexed_ids = set(index_ids)
    if manifest_ids != indexed_ids:
        issues.append(
            NativeQualityIssue(
                code="source_index_manifest_mismatch",
                message=(
                    "Source index IDs must exactly match the manifest; "
                    f"missing={sorted(manifest_ids - indexed_ids)}, "
                    f"unexpected={sorted(indexed_ids - manifest_ids)}."
                ),
            )
        )
    if invalid_local_paths:
        issues.append(
            NativeQualityIssue(
                code="source_index_local_path_invalid",
                message=(
                    "Successful sources have missing or unsafe local paths: "
                    + ", ".join(sorted(invalid_local_paths))
                    + "."
                ),
            )
        )
    if success == 0:
        issues.append(
            NativeQualityIssue(
                code="source_ingest_no_success",
                message=f"`{index_rel}` contains no successful ingests.",
            )
        )
    failed_required_ids = sorted(
        source_id
        for source_id, source in manifest_by_id.items()
        if source.get("required") is True
        and str(index_by_id.get(source_id, {}).get("status") or "").strip()
        != "success"
    )
    if failed_required_ids:
        issues.append(
            NativeQualityIssue(
                code="required_source_ingest_failed",
                message=(
                    "Required sources did not ingest successfully: "
                    + ", ".join(sorted(failed_required_ids))
                    + "."
                ),
            )
        )
    try:
        prov_records = _st_read_jsonl_records(prov_path)
    except _InvalidJsonl as exc:
        issues.append(
            NativeQualityIssue(
                code="source_provenance_invalid_jsonl", message=str(exc)
            )
        )
        return issues
    if not prov_records:
        issues.append(
            NativeQualityIssue(
                code="empty_source_provenance", message=f"`{prov_rel}` is empty."
            )
        )
        return issues
    provenance_ids = {
        str(rec.get("source_id") or "").strip()
        for rec in prov_records
        if isinstance(rec, dict) and str(rec.get("source_id") or "").strip()
    }
    successful_ids = {
        source_id
        for source_id, rec in index_by_id.items()
        if str(rec.get("status") or "").strip() == "success"
    }
    missing_provenance = sorted(successful_ids - provenance_ids)
    unexpected_provenance = sorted(provenance_ids - indexed_ids)
    if missing_provenance or unexpected_provenance:
        issues.append(
            NativeQualityIssue(
                code="source_provenance_index_mismatch",
                message=(
                    "Provenance must cover every successful indexed source and no "
                    f"unknown source; missing={missing_provenance}, "
                    f"unexpected={unexpected_provenance}."
                ),
            )
        )
    invalid_provenance: list[str] = []
    mismatched_provenance_paths: list[str] = []
    for rec in prov_records:
        if not isinstance(rec, dict):
            invalid_provenance.append("<invalid-record>")
            continue
        source_id = str(rec.get("source_id") or "").strip()
        if source_id not in successful_ids:
            continue
        pointer = str(rec.get("pointer") or "").strip()
        origin = str(rec.get("origin_url_or_path") or "").strip()
        local_value = str(rec.get("local_path") or "").strip()
        candidate = Path(local_value)
        local_path = (
            (workspace / candidate).resolve()
            if local_value and not candidate.is_absolute()
            else candidate
        )
        if (
            not pointer
            or not origin
            or not local_value
            or candidate.is_absolute()
            or not local_path.is_relative_to(workspace.resolve())
            or not local_path.exists()
        ):
            invalid_provenance.append(source_id or "<missing-source-id>")
            continue
        index_local_path = _st_resolve_workspace_path(
            workspace,
            index_by_id.get(source_id, {}).get("local_path"),
        )
        if index_local_path is not None and not _st_provenance_path_matches_index(
            index_local_path, local_path
        ):
            mismatched_provenance_paths.append(source_id)
    if invalid_provenance:
        issues.append(
            NativeQualityIssue(
                code="source_provenance_missing_fields",
                message=(
                    "Successful source provenance requires pointer, "
                    "origin_url_or_path, and a safe existing local_path: "
                    + ", ".join(sorted(set(invalid_provenance)))
                    + "."
                ),
            )
        )
    if mismatched_provenance_paths:
        issues.append(
            NativeQualityIssue(
                code="source_provenance_path_mismatch",
                message=(
                    "Provenance local paths must equal the indexed file or remain "
                    "inside the indexed source directory: "
                    + ", ".join(sorted(set(mismatched_provenance_paths)))
                    + "."
                ),
            )
        )
    return issues


def _check_source_tutorial_spec(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_source_tutorial_spec``."""

    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_source_tutorial_spec",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text):
        return [
            NativeQualityIssue(
                code="source_tutorial_spec_placeholders",
                message=f"`{out_rel}` contains placeholders.",
            )
        ]
    required_headings = [
        "## Audience",
        "## Prerequisites",
        "## Learning objectives",
        "## Non-goals",
        "## Source scope",
        "## Running example policy",
        "## Delivery shape",
        "## Structured data",
    ]
    missing = [heading for heading in required_headings if heading not in text]
    if missing:
        return [
            NativeQualityIssue(
                code="source_tutorial_spec_missing_sections",
                message=f"`{out_rel}` is missing key sections: {', '.join(missing)}.",
            )
        ]
    try:
        data = _st_load_source_tutorial_spec_data(path)
    except Exception as exc:  # noqa: BLE001
        return [
            NativeQualityIssue(
                code="source_tutorial_spec_invalid_data",
                message=(
                    f"`{out_rel}` has no readable structured contract "
                    f"({type(exc).__name__}: {exc})."
                ),
            )
        ]
    required_values = (
        "audience",
        "prerequisites",
        "learning_objectives",
        "non_goals",
        "source_scope",
        "delivery_shape",
    )
    empty_values = [key for key in required_values if not data.get(key)]
    if empty_values:
        return [
            NativeQualityIssue(
                code="source_tutorial_spec_empty_fields",
                message=(
                    f"`{out_rel}` has empty structured fields: "
                    f"{', '.join(empty_values)}."
                ),
            )
        ]
    return []


def _check_module_source_coverage(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_module_source_coverage``."""

    from collections import Counter

    out_rel = outputs[0] if outputs else "outline/source_coverage.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_source_coverage", message=f"`{out_rel}` does not exist."
            )
        ]
    try:
        records = _st_read_jsonl_records(path)
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(code="source_coverage_invalid_jsonl", message=str(exc))
        ]
    if not records:
        return [
            NativeQualityIssue(
                code="empty_source_coverage", message=f"`{out_rel}` is empty."
            )
        ]
    try:
        grounding = _st_source_grounding(workspace)
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(
                code="source_coverage_grounding_invalid_jsonl", message=str(exc)
            )
        ]
    backed_source_ids = set(grounding)

    bad = 0
    unknown_sources: set[str] = set()
    record_ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("module_id"):
            bad += 1
            continue
        record_ids.append(str(rec.get("module_id")))
        source_ids = rec.get("source_ids")
        gaps = rec.get("gaps")
        if not isinstance(source_ids, list) or not isinstance(gaps, list):
            bad += 1
            continue
        normalized_sources = [
            str(item or "").strip() for item in source_ids if str(item or "").strip()
        ]
        normalized_gaps = [
            str(item or "").strip() for item in gaps if str(item or "").strip()
        ]
        if not normalized_sources and not normalized_gaps:
            bad += 1
        unknown_sources.update(
            source_id
            for source_id in normalized_sources
            if source_id not in backed_source_ids
        )
    issues: list[NativeQualityIssue] = []
    if bad:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_missing_fields",
                message=f"`{out_rel}` has {bad} invalid coverage record(s).",
            )
        )
    duplicate_ids = sorted(
        module_id for module_id, count in Counter(record_ids).items() if count > 1
    )
    if duplicate_ids:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_duplicate_modules",
                message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}.",
            )
        )
    if unknown_sources:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_unresolved_sources",
                message=(
                    "Coverage references sources without a successful index/"
                    "provenance join: "
                    + ", ".join(sorted(unknown_sources))
                    + "."
                ),
            )
        )
    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_plan_missing",
                message=(
                    "Missing or empty `outline/module_plan.yml` for source "
                    "coverage checks."
                ),
            )
        )
        return issues
    try:
        plan = _st_load_yaml(plan_path)
    except Exception as exc:  # noqa: BLE001
        issues.append(
            NativeQualityIssue(
                code="source_coverage_plan_invalid",
                message=f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.",
            )
        )
        return issues
    plan_ids = (
        {
            str(module.get("id") or module.get("module_id") or "").strip()
            for module in (plan.get("modules") or [])
            if isinstance(module, dict)
            and str(module.get("id") or module.get("module_id") or "").strip()
        }
        if isinstance(plan, dict)
        else set()
    )
    coverage_ids = set(record_ids)
    if not plan_ids or coverage_ids != plan_ids:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_module_mismatch",
                message=(
                    "Coverage modules must equal the module plan; "
                    f"missing={sorted(plan_ids - coverage_ids)}, "
                    f"unexpected={sorted(coverage_ids - plan_ids)}."
                ),
            )
        )
    return issues


def _check_tutorial_context_packs(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_tutorial_context_packs``."""

    from collections import Counter

    out_rel = outputs[0] if outputs else "outline/tutorial_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_tutorial_context_packs",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    try:
        records = _st_read_jsonl_records(path)
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(
                code="tutorial_context_packs_invalid_jsonl", message=str(exc)
            )
        ]
    if not records:
        return [
            NativeQualityIssue(
                code="empty_tutorial_context_packs", message=f"`{out_rel}` is empty."
            )
        ]
    try:
        coverage_records = _st_read_jsonl_records(
            workspace / "outline" / "source_coverage.jsonl"
        )
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(
                code="tutorial_context_packs_coverage_invalid_jsonl",
                message=str(exc),
            )
        ]
    coverage_by_id = {
        str(record.get("module_id") or "").strip(): record
        for record in coverage_records
        if isinstance(record, dict) and str(record.get("module_id") or "").strip()
    }
    try:
        grounding = _st_source_grounding(workspace)
    except _InvalidJsonl as exc:
        return [
            NativeQualityIssue(
                code="tutorial_context_packs_grounding_invalid_jsonl",
                message=str(exc),
            )
        ]
    backed_source_ids = set(grounding)
    bad = 0
    ungrounded = 0
    coverage_mismatches: list[str] = []
    unresolved_sources: set[str] = set()
    missing_snippet_sources: list[str] = []
    unexpected_snippet_sources: list[str] = []
    pointer_mismatches: list[str] = []
    content_mismatches: list[str] = []
    source_text_cache: dict[Path, str] = {}
    record_ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("module_id") or not rec.get(
            "objective"
        ):
            bad += 1
            continue
        module_id = str(rec.get("module_id")).strip()
        record_ids.append(module_id)
        raw_source_ids = rec.get("source_ids")
        snippets = rec.get("source_snippets")
        if not isinstance(raw_source_ids, list) or not isinstance(snippets, list):
            bad += 1
            continue
        source_ids = {
            str(item or "").strip()
            for item in raw_source_ids
            if str(item or "").strip()
        }
        coverage_values = (coverage_by_id.get(module_id) or {}).get("source_ids")
        coverage_source_ids = (
            {
                str(item or "").strip()
                for item in coverage_values
                if str(item or "").strip()
            }
            if isinstance(coverage_values, list)
            else set()
        )
        if source_ids != coverage_source_ids:
            coverage_mismatches.append(module_id)
        unresolved_sources.update(source_ids - backed_source_ids)
        valid_snippets: list[dict[str, object]] = []
        for snippet in snippets:
            if not isinstance(snippet, dict):
                continue
            snippet_source_id = str(snippet.get("source_id") or "").strip()
            if snippet_source_id not in source_ids:
                if snippet_source_id:
                    unexpected_snippet_sources.append(
                        f"{module_id}:{snippet_source_id}"
                    )
                continue
            if snippet_source_id not in backed_source_ids:
                continue
            grounding_issue = _st_snippet_grounding_issue(
                workspace=workspace,
                snippet=snippet,
                grounding=grounding,
                source_text_cache=source_text_cache,
            )
            if grounding_issue == "pointer":
                pointer_mismatches.append(f"{module_id}:{snippet_source_id}")
            elif grounding_issue == "content":
                content_mismatches.append(f"{module_id}:{snippet_source_id}")
            else:
                valid_snippets.append(snippet)
        snippet_source_ids = {
            str(snippet.get("source_id") or "").strip() for snippet in valid_snippets
        }
        if source_ids - snippet_source_ids:
            missing_snippet_sources.append(module_id)
        if not source_ids or source_ids != snippet_source_ids:
            ungrounded += 1
    issues = _check_module_source_coverage(workspace, ["outline/source_coverage.jsonl"])
    if bad:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_missing_fields",
                message=f"`{out_rel}` has {bad} invalid context pack(s).",
            )
        )
    if ungrounded:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_ungrounded",
                message=(
                    f"`{out_rel}` has {ungrounded} pack(s) without source-backed "
                    "snippets and pointers."
                ),
            )
        )
    if coverage_mismatches:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_coverage_mismatch",
                message=(
                    "Context-pack source IDs must exactly match approved module "
                    "coverage: "
                    + ", ".join(sorted(set(coverage_mismatches)))
                    + "."
                ),
            )
        )
    if unresolved_sources:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_unresolved_sources",
                message=(
                    "Context packs reference sources without a successful index/"
                    "provenance join: "
                    + ", ".join(sorted(unresolved_sources))
                    + "."
                ),
            )
        )
    if missing_snippet_sources:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_incomplete_snippets",
                message=(
                    "Every approved module source needs a non-empty snippet and "
                    "pointer: "
                    + ", ".join(sorted(set(missing_snippet_sources)))
                    + "."
                ),
            )
        )
    if unexpected_snippet_sources:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_unapproved_snippets",
                message=(
                    "Context packs contain snippets from sources outside approved "
                    "module coverage: "
                    + ", ".join(sorted(set(unexpected_snippet_sources)))
                    + "."
                ),
            )
        )
    if pointer_mismatches:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_pointer_mismatch",
                message=(
                    "Context-pack pointers must match provenance pointers for their "
                    "source: "
                    + ", ".join(sorted(set(pointer_mismatches)))
                    + "."
                ),
            )
        )
    if content_mismatches:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_snippet_content_mismatch",
                message=(
                    "Context-pack snippets must occur in the provenance file "
                    "selected by their pointer: "
                    + ", ".join(sorted(set(content_mismatches)))
                    + "."
                ),
            )
        )
    duplicate_ids = sorted(
        module_id for module_id, count in Counter(record_ids).items() if count > 1
    )
    if duplicate_ids:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_duplicate_modules",
                message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}.",
            )
        )
    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_plan_missing",
                message=(
                    "Missing or empty `outline/module_plan.yml` for context-pack "
                    "checks."
                ),
            )
        )
        return issues
    try:
        plan = _st_load_yaml(plan_path)
    except Exception as exc:  # noqa: BLE001
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_plan_invalid",
                message=f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.",
            )
        )
        return issues
    plan_ids = (
        {
            str(module.get("id") or module.get("module_id") or "").strip()
            for module in (plan.get("modules") or [])
            if isinstance(module, dict)
            and str(module.get("id") or module.get("module_id") or "").strip()
        }
        if isinstance(plan, dict)
        else set()
    )
    pack_ids = set(record_ids)
    if not plan_ids or pack_ids != plan_ids:
        issues.append(
            NativeQualityIssue(
                code="tutorial_context_packs_module_mismatch",
                message=(
                    "Context-pack modules must equal the module plan; "
                    f"missing={sorted(plan_ids - pack_ids)}, "
                    f"unexpected={sorted(pack_ids - plan_ids)}."
                ),
            )
        )
    return issues


_TUTORIAL_PREFACE_GROUPS = (
    ("who this is for", "受众"),
    ("prerequisites", "先修"),
    ("what you will learn", "学习目标"),
)
_TUTORIAL_MODULE_REQUIREMENTS = (
    ("why it matters", "为什么重要"),
    ("key idea", "核心概念"),
    ("worked example", "示例"),
    ("check yourself", "练习"),
    ("source notes", "来源"),
)


def _st_tutorial_structure_issues(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return ["Missing `output/TUTORIAL.md`."]
    text = path.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    issues = [
        f"Tutorial is missing the reader-orientation section for `{en}`."
        for en, zh in _TUTORIAL_PREFACE_GROUPS
        if en not in low and zh not in text
    ]
    sections: list[tuple[str, str]] = []
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[body_start:body_end].strip()))
    orientation = {
        "who this is for",
        "prerequisites",
        "what you will learn",
        "how to use this tutorial",
        "further reading",
    }
    modules = [
        (title, body) for title, body in sections if title.casefold() not in orientation
    ]
    if not modules:
        issues.append(
            "Tutorial has no real modules (`## ...`) beyond orientation sections."
        )
    for title, body in modules:
        block = body.casefold()
        missing = [
            label
            for label, zh in _TUTORIAL_MODULE_REQUIREMENTS
            if label not in block and zh not in body
        ]
        if missing:
            issues.append(
                f"Module `{title}` is missing teaching sections: {', '.join(missing)}."
            )
    return issues


def _st_tutorial_contract_issues(workspace: Path) -> list[str]:
    """Native mirror of ``source_tutorial.tutorial_contract_issues``."""

    tutorial_path = workspace / "output" / "TUTORIAL.md"
    issues = _st_tutorial_structure_issues(tutorial_path)
    if not tutorial_path.exists() or tutorial_path.stat().st_size == 0:
        return issues

    context_issues = _check_tutorial_context_packs(
        workspace,
        ["outline/tutorial_context_packs.jsonl"],
    )
    issues.extend(
        f"Context-pack contract `{issue.code}` failed: {issue.message}"
        for issue in context_issues
    )

    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append(
            "Missing or empty `outline/module_plan.yml` for tutorial fidelity checks."
        )
        return issues
    try:
        plan = _st_load_yaml(plan_path)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.")
        return issues
    modules = (
        [module for module in (plan.get("modules") or []) if isinstance(module, dict)]
        if isinstance(plan, dict)
        else []
    )
    if not modules:
        issues.append(
            "Missing or empty `outline/module_plan.yml` for tutorial fidelity checks."
        )
        return issues

    text = tutorial_path.read_text(encoding="utf-8", errors="ignore")
    sections: list[tuple[str, str]] = []
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[body_start:body_end].strip()))
    orientation = {
        "who this is for",
        "prerequisites",
        "what you will learn",
        "how to use this tutorial",
        "further reading",
    }
    tutorial_modules = [
        (title, body) for title, body in sections if title.casefold() not in orientation
    ]
    expected_titles = [
        f"Module {index}: {str(module.get('title') or module.get('id') or '').strip()}"
        for index, module in enumerate(modules, start=1)
    ]
    actual_titles = [title for title, _ in tutorial_modules]
    if actual_titles != expected_titles:
        issues.append(
            "Tutorial module order/titles do not match `outline/module_plan.yml`: "
            f"expected={expected_titles}, actual={actual_titles}."
        )
        return issues

    try:
        packs = _st_read_jsonl_records(
            workspace / "outline" / "tutorial_context_packs.jsonl"
        )
    except _InvalidJsonl as exc:
        issues.append(
            f"Context-pack contract `tutorial_context_packs_invalid_jsonl` failed: {exc}"
        )
        return issues
    packs_by_id = {
        str(pack.get("module_id") or "").strip(): pack
        for pack in packs
        if isinstance(pack, dict) and str(pack.get("module_id") or "").strip()
    }
    for module, (_, body) in zip(modules, tutorial_modules):
        module_id = str(module.get("id") or module.get("module_id") or "").strip()
        pack = packs_by_id.get(module_id, {})
        source_ids = [
            str(item or "").strip()
            for item in pack.get("source_ids") or []
            if str(item or "").strip()
        ]
        source_notes_match = re.search(
            r"(?ims)^###\s+Source notes\s*$\n(?P<body>.*?)(?=^###\s+|\Z)",
            body,
        )
        source_notes = source_notes_match.group("body") if source_notes_match else ""
        snippets = pack.get("source_snippets") if isinstance(pack, dict) else []
        pointers_by_source: dict[str, set[str]] = {}
        for snippet in snippets if isinstance(snippets, list) else []:
            if not isinstance(snippet, dict):
                continue
            source_id = str(snippet.get("source_id") or "").strip()
            pointer = str(snippet.get("pointer") or "").strip()
            if source_id and pointer:
                pointers_by_source.setdefault(source_id, set()).add(pointer)
        missing_sources = [
            source_id
            for source_id in source_ids
            if f"`{source_id}`" not in source_notes
        ]
        missing_pointers = [
            pointer
            for source_id in source_ids
            for pointer in sorted(pointers_by_source.get(source_id, set()))
            if pointer not in source_notes
        ]
        if not source_ids or missing_sources or missing_pointers:
            issues.append(
                f"Module `{module_id}` Source notes do not preserve every approved "
                f"source and pointer; missing_sources={missing_sources}, "
                f"missing_pointers={missing_pointers}."
            )
    return issues


def _check_tutorial_selfloop_report(
    workspace: Path, outputs: list[str]
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``source_tutorial.check_tutorial_selfloop_report``."""

    out_rel = outputs[0] if outputs else "output/TUTORIAL_SELFLOOP_TODO.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_tutorial_selfloop_report",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="tutorial_selfloop_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis.",
            )
        ]
    if "- Status: PASS" not in text:
        return [
            NativeQualityIssue(
                code="tutorial_selfloop_not_pass",
                message=f"`{out_rel}` is not PASS.",
            )
        ]
    structure_issues = _st_tutorial_contract_issues(workspace)
    if structure_issues:
        return [
            NativeQualityIssue(
                code="tutorial_selfloop_stale_or_invalid",
                message=(
                    "The PASS report does not match the current tutorial: "
                    + structure_issues[0]
                ),
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
    "beamer-scaffold": _check_beamer_scaffold,
    "source-manifest": _check_source_manifest,
    "source-ingest": _check_source_ingest,
    "source-tutorial-spec": _check_source_tutorial_spec,
    "module-source-coverage": _check_module_source_coverage,
    "tutorial-context-pack": _check_tutorial_context_packs,
    "tutorial-selfloop": _check_tutorial_selfloop_report,
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


def _check_keyword_expansion(workspace: Path) -> list[NativeQualityIssue]:
    """Native mirror of ``survey_retrieval.check_keyword_expansion``.

    Self-contained (no policy): parses ``queries.md`` for a non-empty
    ``keywords`` list.  Byte-for-byte parity (codes + messages) with the legacy
    check is pinned by the Port parity sweep.  This is a plain helper -- it is
    called from :func:`_check_arxiv_search` exactly as the legacy check calls
    its counterpart, so it is not itself registered as a native Skill.

    The legacy check contains a dead ``has_placeholder_markers`` call whose
    result is discarded (``pass``); it is intentionally dropped here because it
    has no observable effect.
    """

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return [
            NativeQualityIssue(
                code="missing_queries",
                message="Missing `queries.md`; expected keyword list for retrieval.",
            )
        ]

    text = queries_path.read_text(encoding="utf-8", errors="ignore")

    mode: str | None = None
    keywords: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- keywords:"):
            mode = "keywords"
            continue
        if line.startswith("- exclude:"):
            mode = "exclude"
            continue
        if not line.startswith("- "):
            continue
        if mode != "keywords":
            continue
        value = line[2:].split("#", 1)[0].strip().strip('"').strip("'")
        if value:
            keywords.append(value)

    if not keywords:
        return [
            NativeQualityIssue(
                code="queries_missing_keywords",
                message=(
                    "`queries.md` has no non-empty `keywords` entries; "
                    "fill keywords (or use offline import)."
                ),
            )
        ]
    if len(keywords) == 1 and len(keywords[0]) < 6:
        return [
            NativeQualityIssue(
                code="queries_keywords_too_generic",
                message=(
                    "`queries.md` keyword list looks too weak; add synonyms/"
                    "acronyms or use `keyword-expansion` before retrieval."
                ),
            )
        ]
    return []


def _check_arxiv_search(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_arxiv_search``.

    Policy-consuming: reads the retrieval-policy minimum-records contract
    through the injected :class:`WorkspacePolicyPort`
    (``pipeline_quality_contract_value``); the raw-pool scan and online-arXiv
    keyword-hygiene branch are pure stdlib.  Records are iterated unfiltered,
    exactly as the legacy check does, so a non-dict record raises identically.
    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity sweep.
    """

    out_rel = outputs[0] if outputs else "papers/papers_raw.jsonl"
    path = workspace / out_rel
    records = _read_jsonl(path)
    if not records:
        return [
            NativeQualityIssue(
                code="empty_raw", message=f"No records found in `{out_rel}`."
            )
        ]

    minimum_records = int(
        policy.pipeline_quality_contract_value(
            workspace,
            "retrieval_policy",
            "minimum_records",
            default=1,
        )
        or 1
    )
    if len(records) < minimum_records:
        return [
            NativeQualityIssue(
                code="raw_pool_too_small",
                message=(
                    f"`{out_rel}` contains {len(records)} records; the Workflow "
                    f"contract requires at least {minimum_records}. Broaden or "
                    "repair the query before ranking."
                ),
            )
        ]

    placeholders = 0
    arxiv_sources = 0
    id_fetch = 0
    for rec in records:
        title = str(rec.get("title") or "").strip()
        url = str(rec.get("url") or rec.get("id") or "").strip()
        if title.lower().startswith("(placeholder)") or "0000.00000" in url:
            placeholders += 1
        if str(rec.get("source") or "").strip().lower() == "arxiv":
            arxiv_sources += 1
        q = rec.get("query")
        if isinstance(q, list) and len(q) == 1:
            v = str(q[0] or "").strip()
            if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", v) or re.fullmatch(
                r"[a-z-]+(?:\.[a-z-]+)?/\d{7}(?:v\d+)?", v
            ):
                id_fetch += 1
    if placeholders:
        return [
            NativeQualityIssue(
                code="placeholder_records",
                message=(
                    f"`{out_rel}` contains placeholder/demo records "
                    f"({placeholders}); workspace template should start empty."
                ),
            )
        ]
    # Only enforce keyword hygiene when this looks like an online arXiv retrieval.
    if arxiv_sources:
        # A direct id_list fetch makes queries.md keywords optional.
        if id_fetch:
            return []
        return _check_keyword_expansion(workspace)
    return []


def _check_pdf_text_extractor(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_pdf_text_extractor``.

    Policy-consuming: reads the run's evidence mode through the injected
    :class:`WorkspacePolicyPort` (``evidence_mode``).  In abstract mode it
    diffs the full-text index against ``papers/core_set.csv`` (native ``csv`` +
    ``_read_jsonl``); in fulltext mode it enforces a real-extraction floor.
    Byte-for-byte parity (codes + messages) with the legacy check is pinned by
    the Port parity sweep.
    """

    out_rel = outputs[0] if outputs else "papers/fulltext_index.jsonl"
    path = workspace / out_rel
    records = _read_jsonl(path) if path.exists() else []
    if not records:
        return [
            NativeQualityIssue(
                code="empty_fulltext_index",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]

    mode = policy.evidence_mode(workspace)
    if mode != "fulltext":
        core_path = workspace / "papers" / "core_set.csv"
        core_ids: set[str] = set()
        if core_path.exists():
            with core_path.open(encoding="utf-8", newline="") as handle:
                core_ids = {
                    str(row.get("paper_id") or "").strip()
                    for row in csv.DictReader(handle)
                    if str(row.get("paper_id") or "").strip()
                }
        indexed_ids = {
            str(record.get("paper_id") or "").strip()
            for record in records
            if isinstance(record, dict) and str(record.get("paper_id") or "").strip()
        }
        missing_ids = sorted(core_ids - indexed_ids)
        if missing_ids:
            preview = ", ".join(missing_ids[:8])
            suffix = " ..." if len(missing_ids) > 8 else ""
            return [
                NativeQualityIssue(
                    code="abstract_index_incomplete",
                    message=(
                        f"`{out_rel}` is missing {len(missing_ids)}/{len(core_ids)} "
                        f"core paper(s): {preview}{suffix}. Abstract mode must "
                        "index the complete core set."
                    ),
                )
            ]
        unexpected_statuses = sorted(
            {
                str(record.get("status") or "").strip()
                for record in records
                if isinstance(record, dict)
                and str(record.get("paper_id") or "").strip() in core_ids
                and str(record.get("status") or "").strip() != "skip_mode_abstract"
            }
        )
        if unexpected_statuses:
            return [
                NativeQualityIssue(
                    code="abstract_index_status_invalid",
                    message=(
                        f"`{out_rel}` contains non-abstract skip statuses: "
                        + ", ".join(unexpected_statuses)
                        + "."
                    ),
                )
            ]
        return []

    ok = 0
    missing_url = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        status = str(rec.get("status") or "").strip()
        pdf_url = str(rec.get("pdf_url") or "").strip()
        chars = int(rec.get("chars_extracted") or 0)
        if not pdf_url:
            missing_url += 1
        if status.startswith("ok") and chars >= 1500:
            ok += 1

    total = max(1, len([r for r in records if isinstance(r, dict)]))
    # In strict mode, we want at least some real full-text extraction before synthesis.
    min_ok = 5 if total >= 10 else 1
    if ok < min_ok:
        hint = (
            "Run with network access, or reduce scope, or provide PDFs manually "
            "under `papers/pdfs/`."
        )
        return [
            NativeQualityIssue(
                code="fulltext_too_few",
                message=(
                    f"Only {ok}/{total} papers have extracted text (>=1500 chars). "
                    f"{hint}"
                ),
            )
        ]
    if missing_url / total >= 0.7:
        return [
            NativeQualityIssue(
                code="fulltext_missing_pdf_urls",
                message=(
                    "Most records have empty `pdf_url`; ensure `core_set.csv` "
                    "includes `pdf_url`/`arxiv_id` or use arXiv online mode."
                ),
            )
        ]
    return []


def _check_literature_engineer(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_literature_engineer``.

    Policy-consuming: reads the retrieval-policy minimum-records contract, the
    run profile, the core-set target, and the evidence mode through the injected
    :class:`WorkspacePolicyPort`.  The metadata-completeness scan over
    ``papers/papers_raw.jsonl`` and the retrieval-report check are pure stdlib.
    Byte-for-byte parity (codes + messages, and issue ORDER) with the legacy
    check is pinned by the Port parity sweep.
    """

    out_rel = outputs[0] if outputs else "papers/papers_raw.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "papers/retrieval_report.md"

    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_raw", message=f"`{out_rel}` does not exist."
            )
        ]
    records = _read_jsonl(path)
    if not records:
        return [
            NativeQualityIssue(
                code="empty_raw", message=f"No records found in `{out_rel}`."
            )
        ]

    report_path = workspace / report_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_retrieval_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report or "Retrieval report" not in report:
        return [
            NativeQualityIssue(
                code="bad_retrieval_report",
                message=f"`{report_rel}` is empty or not a retrieval report.",
            )
        ]

    total = len([r for r in records if isinstance(r, dict)])
    missing_title = 0
    missing_url = 0
    missing_year = 0
    missing_authors = 0
    missing_abstract = 0
    missing_stable_id = 0
    missing_prov = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not str(rec.get("title") or "").strip():
            missing_title += 1
        if not str(rec.get("url") or rec.get("id") or "").strip():
            missing_url += 1
        year = str(rec.get("year") or "").strip()
        if not year:
            missing_year += 1
        authors = rec.get("authors") or []
        if not isinstance(authors, list) or not [a for a in authors if str(a).strip()]:
            missing_authors += 1
        if not str(rec.get("abstract") or "").strip():
            missing_abstract += 1
        if not str(rec.get("arxiv_id") or "").strip() and not str(
            rec.get("doi") or ""
        ).strip():
            missing_stable_id += 1
        prov = rec.get("provenance")
        if not isinstance(prov, list) or len([p for p in prov if isinstance(p, dict)]) == 0:
            missing_prov += 1

    issues: list[NativeQualityIssue] = []
    minimum_records = int(
        policy.pipeline_quality_contract_value(
            workspace,
            "retrieval_policy",
            "minimum_records",
            default=1,
        )
        or 1
    )
    if total < minimum_records:
        issues.append(
            NativeQualityIssue(
                code="raw_pool_too_small",
                message=(
                    f"`{out_rel}` contains {total} records; the Workflow contract "
                    f"requires at least {minimum_records}. Expand the approved "
                    "retrieval plan before screening."
                ),
            )
        )
    if missing_title:
        issues.append(
            NativeQualityIssue(
                code="raw_missing_titles",
                message=f"`{out_rel}` has {missing_title} record(s) missing `title`.",
            )
        )
    if missing_url:
        issues.append(
            NativeQualityIssue(
                code="raw_missing_urls",
                message=f"`{out_rel}` has {missing_url} record(s) missing `url`.",
            )
        )
    if missing_year / max(1, total) >= 0.25:
        issues.append(
            NativeQualityIssue(
                code="raw_missing_years",
                message=(
                    f"Many records are missing `year` ({missing_year}/{total}); "
                    "prefer richer exports or enable online metadata backfill."
                ),
            )
        )
    if missing_authors / max(1, total) >= 0.25:
        issues.append(
            NativeQualityIssue(
                code="raw_missing_authors",
                message=(
                    f"Many records are missing `authors` ({missing_authors}/{total}); "
                    "prefer richer exports or enable online metadata backfill."
                ),
            )
        )
    if missing_prov / max(1, total) >= 0.1:
        issues.append(
            NativeQualityIssue(
                code="raw_missing_provenance",
                message=(
                    f"Many records are missing `provenance` ({missing_prov}/{total}); "
                    "ensure imports are labeled and provenance is preserved through "
                    "dedupe."
                ),
            )
        )

    profile = policy.pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_raw = max(200, int(policy.core_size(workspace)) * 4)
        if total < min_raw:
            issues.append(
                NativeQualityIssue(
                    code="raw_too_small",
                    message=(
                        f"`{out_rel}` has {total} records; target >= {min_raw} for "
                        "survey-quality runs (expand queries/imports/snowballing; "
                        "raise `max_results` and add more buckets)."
                    ),
                )
            )
        if missing_stable_id / max(1, total) >= 0.2:
            issues.append(
                NativeQualityIssue(
                    code="raw_missing_stable_ids",
                    message=(
                        f"Too many records lack stable IDs (arxiv_id/doi) "
                        f"({missing_stable_id}/{total}); filter bad exports or "
                        "enrich metadata before citations."
                    ),
                )
            )
        # Evidence-first: without full text we need abstracts for grounded notes.
        mode = policy.evidence_mode(workspace)
        if mode != "fulltext" and missing_abstract / max(1, total) >= 0.7:
            issues.append(
                NativeQualityIssue(
                    code="raw_missing_abstracts",
                    message=(
                        f"Most records are missing `abstract` "
                        f"({missing_abstract}/{total}); "
                        "provide richer exports (e.g., Semantic Scholar/OpenAlex "
                        "JSONL/CSV, Zotero export with abstracts) "
                        "or enable online metadata enrichment, otherwise "
                        "notes/claims/draft will collapse into title-only templates."
                    ),
                )
            )

    return issues


def _check_dedupe_rank(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_retrieval.check_dedupe_rank``.

    Policy-consuming: reads the candidate-pool contract, the run profile, and
    the core-set target through the injected :class:`WorkspacePolicyPort`.  The
    core-set CSV validation, GOAL scope-drift heuristic, and dedup-pool size
    check are pure stdlib over native ``csv`` + ``_read_jsonl``.  Byte-for-byte
    parity (codes + messages, and issue ORDER) with the legacy check is pinned
    by the Port parity sweep.
    """

    dedup_rel = outputs[0] if outputs else "papers/papers_dedup.jsonl"
    core_rel = outputs[1] if len(outputs) >= 2 else "papers/core_set.csv"
    path = workspace / core_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_core_set", message=f"`{core_rel}` does not exist."
            )
        ]

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [row for row in reader]
    except Exception as exc:  # noqa: BLE001 - mirror legacy broad catch + message
        return [
            NativeQualityIssue(
                code="invalid_core_set",
                message=f"Failed to read `{core_rel}`: {exc}",
            )
        ]

    if not rows:
        return [
            NativeQualityIssue(
                code="empty_core_set", message=f"`{core_rel}` has no rows."
            )
        ]

    missing_id = 0
    missing_title = 0
    ids: list[str] = []
    for row in rows:
        pid = str(row.get("paper_id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not pid:
            missing_id += 1
        else:
            ids.append(pid)
        if not title:
            missing_title += 1

    issues: list[NativeQualityIssue] = []
    if missing_id:
        issues.append(
            NativeQualityIssue(
                code="core_set_missing_paper_id",
                message=(
                    f"`{core_rel}` has {missing_id} row(s) missing `paper_id`; "
                    "ensure stable IDs for downstream mapping/citations."
                ),
            )
        )
    if missing_title:
        issues.append(
            NativeQualityIssue(
                code="core_set_missing_title",
                message=(
                    f"`{core_rel}` has {missing_title} row(s) missing `title`; "
                    "fix upstream normalization/dedupe."
                ),
            )
        )
    if ids and len(set(ids)) != len(ids):
        issues.append(
            NativeQualityIssue(
                code="core_set_duplicate_ids",
                message=f"`{core_rel}` contains duplicate `paper_id` values.",
            )
        )

    core_size_min = int(
        policy.pipeline_quality_contract_value(
            workspace,
            "candidate_pool_policy",
            "core_size_min",
            default=0,
        )
        or 0
    )
    core_size_max = int(
        policy.pipeline_quality_contract_value(
            workspace,
            "candidate_pool_policy",
            "core_size_max",
            default=0,
        )
        or 0
    )
    if core_size_min and len(rows) < core_size_min:
        issues.append(
            NativeQualityIssue(
                code="core_set_too_small",
                message=(
                    f"`{core_rel}` has {len(rows)} rows; the Workflow contract "
                    f"requires at least {core_size_min}."
                ),
            )
        )
    if core_size_max and len(rows) > core_size_max:
        issues.append(
            NativeQualityIssue(
                code="core_set_too_large",
                message=(
                    f"`{core_rel}` has {len(rows)} rows; the Workflow contract "
                    f"allows at most {core_size_max}."
                ),
            )
        )

    profile = policy.pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_core = int(policy.core_size(workspace))
        if len(rows) < min_core:
            issues.append(
                NativeQualityIssue(
                    code="core_set_too_small",
                    message=(
                        f"`{core_rel}` has {len(rows)} rows; target >= {min_core} "
                        "for survey-quality coverage (increase candidate pool and "
                        "set `core_size`)."
                    ),
                )
            )

        # Scope drift heuristic (evidence-first): a text-to-image GOAL with a
        # video-heavy core set blocks early so C2 scope can be tightened.
        goal_path = workspace / "GOAL.md"
        goal = ""
        if goal_path.exists():
            for raw in goal_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(("-", ">", "<!--")):
                    continue
                low = line.lower()
                if "写一句话描述" in line or "fill" in low:
                    continue
                goal = line
                break
        goal_low = goal.lower()
        if goal_low and (
            "text-to-image" in goal_low
            or "text to image" in goal_low
            or "t2i" in goal_low
        ):
            # Only flag drift when video isn't explicitly part of the goal.
            if (
                "video" not in goal_low
                and "text-to-video" not in goal_low
                and "text to video" not in goal_low
                and "t2v" not in goal_low
            ):
                video_titles = sum(
                    1 for r in rows if "video" in str(r.get("title") or "").lower()
                )
                audio_titles = sum(
                    1 for r in rows if "audio" in str(r.get("title") or "").lower()
                )
                denom = max(1, len(rows))
                if video_titles >= 10 and (video_titles / denom) >= 0.15:
                    issues.append(
                        NativeQualityIssue(
                            code="scope_drift_video",
                            message=(
                                f"GOAL suggests text-to-image, but "
                                f"{video_titles}/{len(rows)} core papers mention "
                                f"video (audio={audio_titles}). Tighten "
                                "`queries.md` excludes / filters, or explicitly "
                                "broaden scope at C2."
                            ),
                        )
                    )
        dedup_path = workspace / dedup_rel
        dedup = _read_jsonl(dedup_path)
        min_dedup = max(200, int(min_core) * 4) if min_core else 200
        if len([r for r in dedup if isinstance(r, dict)]) < min_dedup:
            issues.append(
                NativeQualityIssue(
                    code="dedup_pool_too_small",
                    message=(
                        f"`{dedup_rel}` has too few deduplicated records for a "
                        f"survey run; target >= {min_dedup} (expand retrieval/"
                        "snowballing first)."
                    ),
                )
            )
    return issues


def _check_latex_scaffold(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_latex_scaffold``.

    Policy-consuming: reads the run profile through the injected
    :class:`WorkspacePolicyPort` (``pipeline_profile_name``) to decide whether
    the abstract/bibliography structure is required (``source-tutorial`` is
    exempt).  The markdown-leak heuristics are pure string scans.  Byte-for-byte
    parity (codes + messages, and issue ORDER) with the legacy check is pinned
    by the Port parity sweep.
    """

    out_rel = outputs[0] if outputs else "latex/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_main_tex", message=f"`{out_rel}` does not exist."
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    profile = policy.pipeline_profile_name(workspace)

    issues: list[NativeQualityIssue] = []
    if profile not in {"source-tutorial"} and "\\begin{abstract}" not in text:
        issues.append(
            NativeQualityIssue(
                code="latex_missing_abstract",
                message="LaTeX output has no `\\begin{abstract}` block.",
            )
        )
    if profile not in {"source-tutorial"} and "\\bibliography{../citations/ref}" not in text:
        issues.append(
            NativeQualityIssue(
                code="latex_missing_bib",
                message="LaTeX output does not reference `../citations/ref.bib`.",
            )
        )
    # Heuristics: markdown artifacts should not leak into TeX.
    if "[@" in text:
        issues.append(
            NativeQualityIssue(
                code="latex_markdown_cites",
                message="LaTeX still contains markdown cite markers like `[@...]`.",
            )
        )
    if "**" in text:
        issues.append(
            NativeQualityIssue(
                code="latex_markdown_bold",
                message="LaTeX still contains markdown bold markers `**...**`.",
            )
        )
    if "## " in text or "### " in text:
        issues.append(
            NativeQualityIssue(
                code="latex_markdown_headings",
                message="LaTeX still contains markdown headings like `##`/`###`.",
            )
        )
    return issues


def _check_latex_compile_qa(
    workspace: Path,
    outputs: list[str],
    policy: WorkspacePolicyPort,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``delivery.check_latex_compile_qa``.

    Policy-consuming: reads the run profile (``pipeline_profile_name``) and the
    Goal ``page_range`` constraint (``workspace_goal_constraints``) through the
    injected :class:`WorkspacePolicyPort`.  The compiled PDF is inspected for a
    page count -- preferring PyMuPDF (``fitz``), falling back to ``pdfinfo`` via
    the injectable ``which`` (defaulting to ``shutil.which``, exactly as legacy)
    -- and the build log/report is scanned for undefined-citation, float, and
    missing-glyph warnings.  Byte-for-byte parity (codes + messages, issue
    ORDER, and the same early-return on an unavailable page count) with the
    legacy check is pinned by the Port parity sweep.
    """

    pdf_rel = outputs[0] if outputs else "latex/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/LATEX_BUILD_REPORT.md"

    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    log_path = workspace / "latex" / "main.log"

    if not pdf_path.exists():
        return [
            NativeQualityIssue(
                code="missing_main_pdf", message=f"`{pdf_rel}` does not exist."
            )
        ]
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_build_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]

    report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    issues: list[NativeQualityIssue] = []
    profile = policy.pipeline_profile_name(workspace)

    if "Status: SUCCESS" not in report_text and "- Status: SUCCESS" not in report_text:
        issues.append(
            NativeQualityIssue(
                code="latex_build_not_success",
                message=(
                    f"`{report_rel}` does not report SUCCESS; fix LaTeX build "
                    "errors and re-run compile."
                ),
            )
        )

    # Prefer the final LaTeX log for undefined-citation checks. The build report
    # may include warning counters that are not proof the final PDF still has
    # unresolved cites.
    if log_path.exists():
        undefined_text = log_path.read_text(encoding="utf-8", errors="ignore")
    else:
        undefined_text = report_text

    if (
        re.search(
            r"(?im)^Package\s+natbib\s+Warning: Citation.+undefined", undefined_text
        )
        or re.search(r"(?im)There were undefined citations", undefined_text)
        or re.search(r"(?im)There were undefined references", undefined_text)
        or re.search(r"(?im)^LaTeX\s+Warning: Reference.+undefined", undefined_text)
    ):
        issues.append(
            NativeQualityIssue(
                code="latex_undefined_citations",
                message=(
                    "LaTeX build reports undefined citations/references; ensure "
                    "all cited keys exist in `citations/ref.bib` and rerun until "
                    "warnings disappear."
                ),
            )
        )

    if re.search(r"(?im)^LaTeX Warning: Float too large for page", undefined_text):
        issues.append(
            NativeQualityIssue(
                code="latex_float_too_large",
                message=(
                    "LaTeX build still has `Float too large for page` warnings; "
                    "shrink or split oversized tables/figures and recompile."
                ),
            )
        )

    if re.search(r"(?im)^Missing character:", undefined_text):
        issues.append(
            NativeQualityIssue(
                code="latex_missing_character",
                message=(
                    "LaTeX build still reports missing Unicode glyphs; add an "
                    "explicit mapping or sanitize the generated TeX before "
                    "recompiling."
                ),
            )
        )

    sample_text = ""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = int(len(doc))
        sample_pages = min(pages, 4)
        for i in range(sample_pages):
            try:
                sample_text += doc.load_page(i).get_text("text") + "\n"
            except Exception:
                continue
        doc.close()
    except Exception as exc:
        try:
            import subprocess

            pdfinfo = which("pdfinfo")
            if not pdfinfo:
                raise exc
            proc = subprocess.run(
                [pdfinfo, str(pdf_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    proc.stderr.strip() or proc.stdout.strip() or "pdfinfo failed"
                )
            m = re.search(r"(?im)^Pages:\s+(\d+)\b", proc.stdout or "")
            if not m:
                raise RuntimeError("pdfinfo output missing page count")
            pages = int(m.group(1))
        except Exception as inner_exc:
            issues.append(
                NativeQualityIssue(
                    code="pdf_page_count_unavailable",
                    message=(
                        f"Could not compute PDF page count for `{pdf_rel}` "
                        f"({type(inner_exc).__name__}: {inner_exc})."
                    ),
                )
            )
            return issues

    constraints = policy.workspace_goal_constraints(workspace)
    page_range = (
        constraints.get("page_range")
        if isinstance(constraints.get("page_range"), dict)
        else {}
    )
    min_pages = int(page_range.get("min") or (4 if profile == "source-tutorial" else 8))
    max_pages = int(page_range.get("max") or 0)
    if pages < min_pages:
        issues.append(
            NativeQualityIssue(
                code="pdf_too_short",
                message=(
                    f"`{pdf_rel}` is too short ({pages} pages); expand the draft "
                    f"until the compiled PDF has >= {min_pages} pages."
                ),
            )
        )
    if max_pages and pages > max_pages:
        issues.append(
            NativeQualityIssue(
                code="pdf_too_long",
                message=(
                    f"`{pdf_rel}` exceeds the Goal page limit ({pages} pages; "
                    f"target {min_pages}-{max_pages} total PDF pages). "
                    "Compress layout or prose without dropping required evidence, "
                    "then recompile."
                ),
            )
        )

    if (
        re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", sample_text)
        or "(placeholder)" in sample_text.lower()
        or "<!-- SCAFFOLD" in sample_text
    ):
        issues.append(
            NativeQualityIssue(
                code="pdf_contains_placeholders",
                message=(
                    "PDF still contains placeholder text (TODO/TBD/FIXME/"
                    "SCAFFOLD); rewrite the draft and recompile."
                ),
            )
        )

    return issues




# --- research-idea family (policy-consuming) --------------------------------
#
# Native reimplementation of the whole ``tooling.quality_checks.research_idea``
# module (six checks).  The ideation runtime contract is a heavyweight
# workspace-policy resolution (pipeline spec + DECISIONS.md focus + IDEA_BRIEF.md),
# so it stays behind the ``WorkspacePolicyPort`` (``has_pipeline_contract`` +
# ``resolve_idea_contract``); both are legacy-backed so contract values are
# byte-identical.  The join validator ``shortlist_report_join_errors`` is pure
# (two lists in, error strings out) and is reimplemented natively.  The
# ``idea-brief`` contract asset is read from the repo tree exactly as legacy.


_IDEA_REPO_ROOT = Path(__file__).resolve().parents[3]


def _ri_shortlist_report_join_errors(
    shortlist: list[dict[str, Any]],
    top: list[dict[str, Any]],
) -> list[str]:
    """Native mirror of ``tooling.idea_evaluation.shortlist_report_join_errors``."""

    if not top:
        return ["report has no top directions"]
    if len(shortlist) < len(top):
        return [
            f"report has {len(top)} top directions but shortlist has "
            f"{len(shortlist)} records"
        ]

    errors: list[str] = []
    for index, (shortlist_record, report_record) in enumerate(
        zip(shortlist[: len(top)], top),
        start=1,
    ):
        for field_name in ("rank", "direction_id", "title"):
            expected = str(shortlist_record.get(field_name) or "").strip()
            actual = str(report_record.get(field_name) or "").strip()
            if not expected or actual != expected:
                errors.append(
                    f"rank {index} {field_name} mismatch: "
                    f"shortlist={expected or '<missing>'}, "
                    f"report={actual or '<missing>'}"
                )
        for field_name in ("signal_ids", "paper_ids"):
            expected_values = shortlist_record.get(field_name)
            actual_values = report_record.get(field_name)
            expected_list = (
                sorted(
                    str(item or "").strip()
                    for item in expected_values
                    if str(item or "").strip()
                )
                if isinstance(expected_values, list)
                else []
            )
            actual_list = (
                sorted(
                    str(item or "").strip()
                    for item in actual_values
                    if str(item or "").strip()
                )
                if isinstance(actual_values, list)
                else []
            )
            if actual_list != expected_list:
                errors.append(
                    f"rank {index} {field_name} mismatch: "
                    f"shortlist={expected_list}, report={actual_list}"
                )
    return errors


def _ri_sidecar_output_rel(outputs: list[str], *, filename: str) -> str:
    explicit = next((p for p in outputs if p.endswith(filename)), "")
    if explicit:
        return explicit
    target_stem = Path(filename).stem
    for output in outputs:
        p = Path(output)
        if p.suffix.lower() == ".md" and p.stem == target_stem:
            return str(p.with_suffix(".jsonl"))
    return f"output/{filename}"


def _ri_load_idea_contract(
    workspace: Path, policy: WorkspacePolicyPort
) -> tuple[dict[str, Any] | None, list[NativeQualityIssue]]:
    """Native mirror of ``research_idea._load_idea_contract_for_quality``.

    Reads the ideation contract through the Port (both calls legacy-backed), so
    the returned dict and the two failure issues are byte-identical to legacy.
    """

    if not policy.has_pipeline_contract(workspace):
        return None, [
            NativeQualityIssue(
                code="missing_idea_pipeline_contract",
                message=(
                    "Missing or invalid active ideation pipeline contract; check "
                    "`PIPELINE.lock.md` and pipeline metadata."
                ),
            )
        ]
    try:
        return policy.resolve_idea_contract(workspace), []
    except Exception as exc:  # noqa: BLE001 - mirror legacy broad catch + message
        return None, [
            NativeQualityIssue(
                code="invalid_idea_pipeline_contract",
                message=(
                    f"Failed to resolve the ideation runtime contract "
                    f"({type(exc).__name__}: {exc})."
                ),
            )
        ]


def _ri_markdown_table_data_rows(text: str, *, header_token: str) -> list[str]:
    data_rows: list[str] = []
    for ln in (text or "").splitlines():
        stripped = ln.strip()
        if not stripped.startswith("|"):
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if cols and cols[0].lower() == header_token.lower():
            continue
        is_separator = bool(cols) and all(
            re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cols
        )
        if is_separator:
            continue
        data_rows.append(ln)
    return data_rows


def _ri_missing_structured_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _ri_load_jsonl_dict_records(
    workspace: Path, *, sidecar_rel: str, code_prefix: str
) -> tuple[list[dict[str, Any]], list[NativeQualityIssue]]:
    sidecar_path = workspace / sidecar_rel
    if not sidecar_path.exists() or sidecar_path.stat().st_size == 0:
        return [], [
            NativeQualityIssue(
                code=f"missing_{code_prefix}_jsonl",
                message=f"`{sidecar_rel}` is missing or empty.",
            )
        ]
    try:
        records = [r for r in _read_jsonl(sidecar_path) if isinstance(r, dict)]
    except Exception as exc:  # noqa: BLE001
        return [], [
            NativeQualityIssue(
                code=f"invalid_{code_prefix}_jsonl",
                message=(
                    f"`{sidecar_rel}` could not be parsed as JSONL "
                    f"({type(exc).__name__}: {exc})."
                ),
            )
        ]
    if not records:
        return [], [
            NativeQualityIssue(
                code=f"empty_{code_prefix}_jsonl",
                message=f"`{sidecar_rel}` has no JSON objects.",
            )
        ]
    return records, []


def _ri_audit_sidecar_records(
    *,
    records: Sequence[dict[str, Any]],
    sidecar_rel: str,
    code_prefix: str,
    required_fields: Sequence[str],
    expected_rows: int | None = None,
    id_key: str | None = None,
) -> list[NativeQualityIssue]:
    issues: list[NativeQualityIssue] = []
    if expected_rows is not None and len(records) != int(expected_rows):
        issues.append(
            NativeQualityIssue(
                code=f"{code_prefix}_row_mismatch",
                message=(
                    f"`{sidecar_rel}` row count ({len(records)}) should match the "
                    f"Markdown table row count ({expected_rows})."
                ),
            )
        )

    bad_records = 0
    missing_fields: set[str] = set()
    for rec in records:
        missing = [
            field_name
            for field_name in required_fields
            if _ri_missing_structured_value(rec.get(field_name))
        ]
        if missing:
            bad_records += 1
            missing_fields.update(missing)
    if bad_records:
        issues.append(
            NativeQualityIssue(
                code=f"{code_prefix}_missing_fields",
                message=(
                    f"`{sidecar_rel}` has {bad_records} record(s) missing required "
                    f"fields ({', '.join(sorted(missing_fields))})."
                ),
            )
        )

    if id_key:
        ids = [
            str(rec.get(id_key) or "").strip()
            for rec in records
            if str(rec.get(id_key) or "").strip()
        ]
        dupes = len(ids) - len(set(ids))
        if dupes:
            issues.append(
                NativeQualityIssue(
                    code=f"{code_prefix}_duplicate_ids",
                    message=(
                        f"`{sidecar_rel}` contains duplicate `{id_key}` values "
                        f"({dupes})."
                    ),
                )
            )
    return issues


def _check_idea_brief(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_idea_brief``.

    Reads the ``idea-brief`` contract asset from the repo tree, exactly as
    legacy does.  Does not consume the ideation contract itself (kept on the
    policy table only for a uniform dispatch signature).
    """

    brief_rel = next(
        (path for path in outputs if path.endswith("IDEA_BRIEF.md")),
        "output/trace/IDEA_BRIEF.md",
    )
    brief_path = workspace / brief_rel
    if not brief_path.exists() or brief_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_idea_brief",
                message=f"`{brief_rel}` is missing or empty.",
            )
        ]

    contract_path = (
        _IDEA_REPO_ROOT
        / ".codex"
        / "skills"
        / "idea-brief"
        / "assets"
        / "brief_contract.json"
    )
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        sections = contract.get("required_sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("required_sections is missing or empty")
        required = [
            f"## {str(section or '').strip()}"
            for section in sections
            if str(section or "").strip()
        ]
    except Exception as exc:  # noqa: BLE001
        return [
            NativeQualityIssue(
                code="idea_brief_contract_unreadable",
                message=(
                    f"Failed to load `idea-brief` contract asset "
                    f"({type(exc).__name__}: {exc})."
                ),
            )
        ]

    text = brief_path.read_text(encoding="utf-8", errors="ignore")
    missing = [heading for heading in required if heading not in text]
    if missing:
        return [
            NativeQualityIssue(
                code="idea_brief_missing_sections",
                message=(
                    f"`{brief_rel}` is missing required sections: "
                    f"{', '.join(missing)}"
                ),
            )
        ]

    queries_path = workspace / "queries.md"
    if not queries_path.exists() or queries_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="idea_brief_missing_queries",
                message="`queries.md` is missing after `idea-brief`.",
            )
        ]
    queries = queries_path.read_text(encoding="utf-8", errors="ignore")
    profile_tokens = (
        'draft_profile: "idea_brainstorm"',
        "draft_profile: 'idea_brainstorm'",
        "draft_profile: idea_brainstorm",
    )
    if not any(token in queries for token in profile_tokens):
        return [
            NativeQualityIssue(
                code="idea_brief_missing_draft_profile",
                message="`queries.md` should set `draft_profile: idea_brainstorm`.",
            )
        ]

    keyword_count = 0
    in_keywords = False
    for raw in queries.splitlines():
        stripped = raw.strip()
        if stripped.startswith("- keywords:"):
            in_keywords = True
            continue
        if stripped.startswith("- ") and not raw.startswith("  - "):
            if in_keywords:
                break
        if in_keywords and raw.startswith("  - ") and stripped[4:].strip():
            keyword_count += 1
    if keyword_count < 3:
        return [
            NativeQualityIssue(
                code="idea_brief_too_few_query_buckets",
                message=(
                    "`queries.md` should contain at least 3 keyword buckets for "
                    "ideation retrieval."
                ),
            )
        ]
    return []


def _check_signal_table(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_signal_table``."""

    out_rel = next(
        (p for p in outputs if p.endswith("IDEA_SIGNAL_TABLE.md")),
        "output/trace/IDEA_SIGNAL_TABLE.md",
    )
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_idea_signal_table",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    contract, issues = _ri_load_idea_contract(workspace, policy)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="idea_signal_table_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis.",
            )
        ]
    needed = [
        "Signal ID",
        "Cluster",
        "Theme",
        "Claim / observation",
        "Tension",
        "Missing piece",
        "Possible axis",
        "Academic value",
        "Confidence",
        "Paper IDs",
    ]
    if not all(h.lower() in text.lower() for h in needed):
        return [
            NativeQualityIssue(
                code="idea_signal_table_missing_columns",
                message=(
                    f"`{out_rel}` should expose a signal table with the expected "
                    "columns."
                ),
            )
        ]
    data_rows = _ri_markdown_table_data_rows(text, header_token="Signal ID")
    min_rows = int(contract["signal_table_min"])
    if len(data_rows) < min_rows:
        return [
            NativeQualityIssue(
                code="idea_signal_table_too_small",
                message=(
                    f"`{out_rel}` should contain at least {min_rows} signal rows "
                    f"(found {len(data_rows)})."
                ),
            )
        ]
    sidecar_rel = _ri_sidecar_output_rel(outputs, filename="IDEA_SIGNAL_TABLE.jsonl")
    records, issues = _ri_load_jsonl_dict_records(
        workspace, sidecar_rel=sidecar_rel, code_prefix="idea_signal_table"
    )
    if issues:
        return issues
    issues.extend(
        _ri_audit_sidecar_records(
            records=records,
            sidecar_rel=sidecar_rel,
            code_prefix="idea_signal_table",
            required_fields=[
                "signal_id",
                "cluster",
                "direction_type",
                "theme",
                "claim_or_observation",
                "tension",
                "missing_piece",
                "possible_axis",
                "academic_value",
                "evidence_confidence",
                "paper_ids",
            ],
            expected_rows=len(data_rows),
            id_key="signal_id",
        )
    )
    bad_pids = 0
    for rec in records:
        paper_ids = rec.get("paper_ids")
        valid = [
            pid
            for pid in (paper_ids or [])
            if re.fullmatch(r"P\d{4}", str(pid).strip())
        ]
        if not isinstance(paper_ids, list) or len(valid) < 1:
            bad_pids += 1
    if bad_pids:
        issues.append(
            NativeQualityIssue(
                code="idea_signal_table_bad_paper_ids",
                message=(
                    f"`{sidecar_rel}` has {bad_pids} record(s) without valid "
                    "`paper_ids` lists."
                ),
            )
        )
    return issues


def _check_direction_pool(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_direction_pool``."""

    out_rel = next(
        (p for p in outputs if p.endswith("IDEA_DIRECTION_POOL.md")),
        "output/trace/IDEA_DIRECTION_POOL.md",
    )
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_idea_direction_pool",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    contract, issues = _ri_load_idea_contract(workspace, policy)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="idea_direction_pool_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis.",
            )
        ]
    needed = [
        "Direction ID",
        "Cluster",
        "Type",
        "Title",
        "One-line thesis",
        "Why interesting",
        "Missing piece",
        "Possible variants",
        "Academic value",
        "First probes",
        "Confidence",
        "Paper IDs",
    ]
    if not all(h.lower() in text.lower() for h in needed):
        return [
            NativeQualityIssue(
                code="idea_direction_pool_missing_columns",
                message=(
                    f"`{out_rel}` should expose a direction pool table with the "
                    "expected columns."
                ),
            )
        ]
    data_rows = _ri_markdown_table_data_rows(text, header_token="Direction ID")
    pool_min = int(contract["direction_pool_min"])
    pool_max = int(contract["direction_pool_max"])
    if len(data_rows) < pool_min or len(data_rows) > pool_max:
        return [
            NativeQualityIssue(
                code="idea_direction_pool_size_out_of_range",
                message=(
                    f"`{out_rel}` should contain {pool_min}-{pool_max} direction "
                    f"rows (found {len(data_rows)})."
                ),
            )
        ]
    sidecar_rel = _ri_sidecar_output_rel(outputs, filename="IDEA_DIRECTION_POOL.jsonl")
    records, issues = _ri_load_jsonl_dict_records(
        workspace, sidecar_rel=sidecar_rel, code_prefix="idea_direction_pool"
    )
    if issues:
        return issues
    issues.extend(
        _ri_audit_sidecar_records(
            records=records,
            sidecar_rel=sidecar_rel,
            code_prefix="idea_direction_pool",
            required_fields=[
                "direction_id",
                "cluster",
                "direction_type",
                "title",
                "focus_axis",
                "main_confound",
                "program_kind",
                "contribution_shape",
                "time_to_clarity",
                "one_line_thesis",
                "why_interesting",
                "literature_suggests",
                "missing_piece",
                "possible_variants",
                "academic_value",
                "first_probes",
                "weakness_conditions",
                "kill_criteria",
                "best_fit",
                "evidence_confidence",
                "paper_ids",
                "signal_ids",
                "anchor_reading_notes",
            ],
            expected_rows=len(data_rows),
            id_key="direction_id",
        )
    )
    return issues


def _check_screening_table(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_screening_table``."""

    out_rel = next(
        (p for p in outputs if p.endswith("IDEA_SCREENING_TABLE.md")),
        "output/trace/IDEA_SCREENING_TABLE.md",
    )
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_idea_screening_table",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    contract, issues = _ri_load_idea_contract(workspace, policy)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="idea_screening_table_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis.",
            )
        ]
    needed = [
        "Direction ID",
        "Cluster",
        "Type",
        "Title",
        "Total",
        "Discussion",
        "Academic value",
        "Evidence",
        "Distinctness",
        "First probe",
        "Thesis potential",
        "Decision",
        "Rationale",
    ]
    if not all(h.lower() in text.lower() for h in needed):
        return [
            NativeQualityIssue(
                code="idea_screening_table_missing_columns",
                message=(
                    f"`{out_rel}` should expose a scored screening table with the "
                    "expected columns."
                ),
            )
        ]
    data_rows = _ri_markdown_table_data_rows(text, header_token="Direction ID")
    min_rows = int(contract["idea_screen_top_n"])
    if len(data_rows) < min_rows:
        return [
            NativeQualityIssue(
                code="idea_screening_table_too_small",
                message=(
                    f"`{out_rel}` should contain at least {min_rows} screened "
                    f"directions (found {len(data_rows)})."
                ),
            )
        ]
    sidecar_rel = _ri_sidecar_output_rel(
        outputs, filename="IDEA_SCREENING_TABLE.jsonl"
    )
    records, issues = _ri_load_jsonl_dict_records(
        workspace, sidecar_rel=sidecar_rel, code_prefix="idea_screening_table"
    )
    if issues:
        return issues
    issues.extend(
        _ri_audit_sidecar_records(
            records=records,
            sidecar_rel=sidecar_rel,
            code_prefix="idea_screening_table",
            required_fields=[
                "direction_id",
                "cluster",
                "direction_type",
                "title",
                "total_score",
                "discussion_worthiness",
                "academic_value_score",
                "evidence_grounding",
                "direction_distinctness",
                "first_probe_clarity",
                "thesis_potential",
                "recommendation",
                "rationale",
            ],
            expected_rows=len(data_rows),
            id_key="direction_id",
        )
    )
    decisions = [
        str(rec.get("recommendation") or "").strip().lower() for rec in records
    ]
    bad = sorted({d for d in decisions if d not in {"keep", "maybe", "drop"}})
    if bad:
        issues.append(
            NativeQualityIssue(
                code="idea_screening_table_bad_decisions",
                message=(
                    f"`{sidecar_rel}` contains unsupported decisions: "
                    f"{', '.join(bad)}."
                ),
            )
        )
    keep_min = int(contract["keep_min"])
    if sum(1 for d in decisions if d == "keep") < keep_min:
        issues.append(
            NativeQualityIssue(
                code="idea_screening_table_too_few_kept",
                message=(
                    f"`{sidecar_rel}` should mark at least {keep_min} candidates as "
                    "`keep` for the shortlist."
                ),
            )
        )
    return issues


def _check_shortlist(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_shortlist``."""

    out_rel = next(
        (p for p in outputs if p.endswith("IDEA_SHORTLIST.md")),
        "output/trace/IDEA_SHORTLIST.md",
    )
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_idea_shortlist",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    if not policy.has_pipeline_contract(workspace):
        return [
            NativeQualityIssue(
                code="missing_idea_pipeline_contract",
                message=(
                    "Missing or invalid active ideation pipeline contract; check "
                    "`PIPELINE.lock.md` and pipeline metadata."
                ),
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="idea_shortlist_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis.",
            )
        ]
    contract, issues = _ri_load_idea_contract(workspace, policy)
    if issues:
        return issues
    ideas = len(re.findall(r"(?m)^###\s+Direction\s+\d+\.", text))
    shortlist_min = int(contract["shortlist_min"])
    shortlist_max = int(contract["shortlist_max"])
    if ideas < shortlist_min or ideas > shortlist_max:
        return [
            NativeQualityIssue(
                code="idea_shortlist_size_out_of_range",
                message=(
                    f"`{out_rel}` should contain {shortlist_min}-{shortlist_max} "
                    f"shortlisted directions (found {ideas})."
                ),
            )
        ]
    expected_shortlist_size = int(contract["shortlist_size"])
    if ideas != expected_shortlist_size:
        return [
            NativeQualityIssue(
                code="idea_shortlist_size_mismatch",
                message=(
                    f"`{out_rel}` should contain exactly {expected_shortlist_size} "
                    "shortlisted directions for the active ideation contract "
                    f"(found {ideas})."
                ),
            )
        ]
    required_labels = [
        "Focus axis:",
        "Program kind:",
        "Main confound:",
        "Time to clarity:",
        "One-line thesis:",
        "Why this ranks here:",
        "Why this is interesting:",
        "What the literature already suggests:",
        "Closest prior work and why it does not settle the question:",
        "What is still missing:",
        "Possible variants:",
        "Contribution shape:",
        "Why this could matter academically:",
        "First probes:",
        "What would count as actual insight:",
        "What would make this weak or unconvincing:",
        "Quick kill criteria:",
        "Best fit:",
        "Evidence confidence:",
        "Anchor papers:",
        "Why prioritized now:",
    ]
    missing = [lab for lab in required_labels if lab not in text]
    if missing:
        return [
            NativeQualityIssue(
                code="idea_shortlist_missing_fields",
                message=(
                    f"`{out_rel}` is missing required shortlist fields: "
                    f"{', '.join(missing)}"
                ),
            )
        ]
    sidecar_rel = _ri_sidecar_output_rel(outputs, filename="IDEA_SHORTLIST.jsonl")
    records, issues = _ri_load_jsonl_dict_records(
        workspace, sidecar_rel=sidecar_rel, code_prefix="idea_shortlist"
    )
    if issues:
        return issues
    issues.extend(
        _ri_audit_sidecar_records(
            records=records,
            sidecar_rel=sidecar_rel,
            code_prefix="idea_shortlist",
            required_fields=[
                "rank",
                "direction_id",
                "cluster",
                "direction_type",
                "title",
                "focus_axis",
                "main_confound",
                "program_kind",
                "contribution_shape",
                "time_to_clarity",
                "one_line_thesis",
                "why_interesting",
                "literature_suggests",
                "closest_prior_gap",
                "missing_piece",
                "possible_variants",
                "academic_value",
                "first_probes",
                "what_counts_as_insight",
                "weakness_conditions",
                "kill_criteria",
                "best_fit",
                "evidence_confidence",
                "paper_ids",
                "signal_ids",
                "anchor_reading_notes",
                "why_this_ranks_here",
                "why_prioritized",
            ],
            expected_rows=ideas,
            id_key="direction_id",
        )
    )
    ranks = []
    bad_ranks = 0
    for rec in records:
        try:
            ranks.append(int(rec.get("rank")))
        except Exception:  # noqa: BLE001 - mirror legacy bare-except tolerance
            bad_ranks += 1
    if bad_ranks:
        issues.append(
            NativeQualityIssue(
                code="idea_shortlist_bad_ranks",
                message=(
                    f"`{sidecar_rel}` has {bad_ranks} record(s) with non-integer "
                    "`rank`."
                ),
            )
        )
    elif sorted(ranks) != list(range(1, len(records) + 1)):
        issues.append(
            NativeQualityIssue(
                code="idea_shortlist_noncontiguous_ranks",
                message=(
                    f"`{sidecar_rel}` should rank shortlisted directions "
                    f"contiguously from 1 to {len(records)}."
                ),
            )
        )
    clusters = {
        str(rec.get("cluster") or "").strip()
        for rec in records
        if str(rec.get("cluster") or "").strip()
    }
    cluster_diversity_min = int(contract["cluster_diversity_min"])
    if len(clusters) < cluster_diversity_min:
        issues.append(
            NativeQualityIssue(
                code="idea_shortlist_low_cluster_diversity",
                message=(
                    f"`{sidecar_rel}` should cover at least {cluster_diversity_min} "
                    f"clusters (found {len(clusters)})."
                ),
            )
        )
    return issues


def _check_report_bundle(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``research_idea.check_report_bundle``."""

    report_rel = next(
        (p for p in outputs if p.endswith("REPORT.md")), "output/REPORT.md"
    )
    appendix_rel = next(
        (p for p in outputs if p.endswith("APPENDIX.md")), "output/APPENDIX.md"
    )
    json_rel = next(
        (p for p in outputs if p.endswith("REPORT.json")), "output/REPORT.json"
    )
    report_path = workspace / report_rel
    appendix_path = workspace / appendix_rel
    json_path = workspace / json_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_brainstorm_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]
    if not appendix_path.exists() or appendix_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_brainstorm_appendix",
                message=f"`{appendix_rel}` is missing or empty.",
            )
        ]
    if not json_path.exists() or json_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_brainstorm_report_json",
                message=f"`{json_rel}` is missing or empty.",
            )
        ]
    contract, issues = _ri_load_idea_contract(workspace, policy)
    if issues:
        return issues
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="brainstorm_report_placeholders",
                message=f"`{report_rel}` contains placeholders/ellipsis.",
            )
        ]
    report_top_n = int(contract["report_top_n"])
    deferred_idx = 3 + report_top_n
    discussion_idx = deferred_idx + 1
    uncertainty_idx = deferred_idx + 2
    next_idx = deferred_idx + 3
    appendix_idx = deferred_idx + 4
    required_sections = [
        "## 0. Scope and framing",
        "## 1. Big-picture takeaways",
        "## 2. Top directions at a glance",
        f"## {deferred_idx}. Other promising but not prioritized directions",
        f"## {discussion_idx}. Cross-cutting discussion questions",
        f"## {uncertainty_idx}. Uncertainty and disagreement",
        f"## {next_idx}. Suggested next reading / next discussion step",
        f"## {appendix_idx}. Appendix guide",
    ]
    missing = [h for h in required_sections if h not in text]
    if missing:
        return [
            NativeQualityIssue(
                code="brainstorm_report_missing_sections",
                message=(
                    f"`{report_rel}` is missing required sections: "
                    f"{', '.join(missing)}"
                ),
            )
        ]
    appendix_text = appendix_path.read_text(encoding="utf-8", errors="ignore")
    if (
        "Anchor paper" not in appendix_text
        or "Why read now" not in appendix_text
        or "What to extract" not in appendix_text
        or "Kill signal" not in appendix_text
    ):
        return [
            NativeQualityIssue(
                code="brainstorm_appendix_missing_reading_guide",
                message=(
                    f"`{appendix_rel}` should provide a paper-specific reading "
                    "guide table (Anchor paper / Why read now / What to extract / "
                    "Kill signal)."
                ),
            )
        ]
    generic_phrases = []
    if text.count("reports a meaningful gain") >= 2:
        generic_phrases.append("reports a meaningful gain")
    if "Sharper mechanism question;" in text:
        generic_phrases.append("Sharper mechanism question;")
    if appendix_text.count("read it to extract what it really attributes gains to") >= 1:
        generic_phrases.append("read it to extract what it really attributes gains to")
    if text.count("may be over-attributing progress to broad agent quality") >= 2:
        generic_phrases.append("may be over-attributing progress to broad agent quality")
    if generic_phrases:
        return [
            NativeQualityIssue(
                code="brainstorm_report_generic_language",
                message=(
                    f"`{report_rel}` / `{appendix_rel}` still contain generic "
                    f"templated language: {', '.join(generic_phrases)}"
                ),
            )
        ]
    direction_sections = re.findall(
        r"(?m)^##\s+\d+\.\s+Direction\s+\d+\s+—\s+(.+)$", text
    )
    if len(direction_sections) != report_top_n:
        return [
            NativeQualityIssue(
                code="brainstorm_report_wrong_direction_count",
                message=(
                    f"`{report_rel}` should contain exactly {report_top_n} expanded "
                    f"lead directions (found {len(direction_sections)})."
                ),
            )
        ]
    if re.search(r"\bP\d{4}\b", text):
        return [
            NativeQualityIssue(
                code="brainstorm_report_leaks_internal_ids",
                message=(
                    f"`{report_rel}` should not expose raw `paper_id` values in the "
                    "main memo."
                ),
            )
        ]
    compare_rows = _ri_markdown_table_data_rows(text, header_token="Rank")
    if len(compare_rows) < report_top_n:
        return [
            NativeQualityIssue(
                code="brainstorm_report_thin_snapshot",
                message=(
                    f"`{report_rel}` should include a top-directions comparison "
                    f"table with at least {report_top_n} rows."
                ),
            )
        ]
    shortlist: list[dict[str, Any]] = []
    shortlist_path = workspace / "output" / "trace" / "IDEA_SHORTLIST.jsonl"
    if shortlist_path.exists() and shortlist_path.stat().st_size > 0:
        shortlist = [r for r in _read_jsonl(shortlist_path) if isinstance(r, dict)]
        expected_titles = [
            str(r.get("title") or "").strip()
            for r in shortlist[:report_top_n]
            if str(r.get("title") or "").strip()
        ]
        if (
            len(expected_titles) == report_top_n
            and direction_sections[:report_top_n] != expected_titles
        ):
            return [
                NativeQualityIssue(
                    code="brainstorm_report_shortlist_mismatch",
                    message=(
                        f"`{report_rel}` should expand the top {report_top_n} titles "
                        "from `output/trace/IDEA_SHORTLIST.jsonl` in rank order."
                    ),
                )
            ]
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [
            NativeQualityIssue(
                code="brainstorm_report_json_invalid",
                message=(
                    f"`{json_rel}` is not valid JSON ({type(exc).__name__}: {exc})."
                ),
            )
        ]
    needed_keys = {
        "topic",
        "takeaways",
        "top_directions",
        "deferred_directions",
        "discussion_questions",
        "uncertainties",
        "next_steps",
        "trace_artifacts",
    }
    missing_keys = sorted(needed_keys - set(payload.keys()))
    if missing_keys:
        return [
            NativeQualityIssue(
                code="brainstorm_report_json_missing_keys",
                message=(
                    f"`{json_rel}` is missing required keys: {', '.join(missing_keys)}"
                ),
            )
        ]
    top_directions = payload.get("top_directions") or []
    if not isinstance(top_directions, list):
        return [
            NativeQualityIssue(
                code="brainstorm_report_json_bad_top_directions",
                message=f"`{json_rel}` `top_directions` should be a JSON array.",
            )
        ]
    if len(top_directions) != report_top_n:
        return [
            NativeQualityIssue(
                code="brainstorm_report_json_wrong_direction_count",
                message=(
                    f"`{json_rel}` should contain exactly {report_top_n} top "
                    f"directions (found {len(top_directions)})."
                ),
            )
        ]
    for idx, rec in enumerate(top_directions, start=1):
        if not isinstance(rec, dict):
            return [
                NativeQualityIssue(
                    code="brainstorm_report_json_bad_top_direction",
                    message=(
                        f"`{json_rel}` top direction #{idx} should be a JSON object."
                    ),
                )
            ]
        required_rec = {
            "title",
            "focus_axis",
            "main_confound",
            "program_kind",
            "contribution_shape",
            "time_to_clarity",
            "one_line_thesis",
            "why_this_ranks_here",
            "literature_suggests",
            "closest_prior_gap",
            "missing_piece",
            "what_counts_as_insight",
            "first_probes",
            "kill_criteria",
            "anchor_reading_notes",
        }
        rec_missing = sorted(required_rec - set(rec.keys()))
        if rec_missing:
            return [
                NativeQualityIssue(
                    code="brainstorm_report_json_thin_top_direction",
                    message=(
                        f"`{json_rel}` top direction #{idx} is missing fields: "
                        f"{', '.join(rec_missing)}"
                    ),
                )
            ]
    if shortlist:
        join_errors = _ri_shortlist_report_join_errors(shortlist, top_directions)
        if join_errors:
            return [
                NativeQualityIssue(
                    code="brainstorm_report_shortlist_trace_mismatch",
                    message=(
                        f"`{json_rel}` top directions must preserve shortlist rank "
                        "and evidence identity: "
                        + "; ".join(join_errors[:3])
                    ),
                )
            ]
    return []



# --- paper-review family (policy-consuming) ---------------------------------
#
# Native reimplementation of the whole ``tooling.quality_checks.paper_review``
# module (four checks).  Each is a thin reader of the paper-review scorecard,
# which is a heavyweight evaluator (reads CLAIMS.jsonl / EVIDENCE_AUDIT.jsonl /
# NOVELTY_MATRIX.tsv / REVIEW.md plus the rubric policy).  That evaluator stays
# behind the ``WorkspacePolicyPort`` (``evaluate_paper_review``), legacy-backed
# so the scorecard is byte-identical; only the thin dimension-status projection
# is reimplemented here, matching ``paper_review._check_dimensions`` exactly.


def _pr_check_dimensions(
    workspace: Path,
    policy: WorkspacePolicyPort,
    dimension_ids: tuple[str, ...],
) -> list[NativeQualityIssue]:
    """Native mirror of ``paper_review._check_dimensions``."""

    scorecard = policy.evaluate_paper_review(workspace)
    dimensions = {
        str(item.get("id") or ""): item
        for item in scorecard.get("dimensions") or []
        if isinstance(item, dict)
    }
    issues: list[NativeQualityIssue] = []
    for dimension_id in dimension_ids:
        dimension = dimensions.get(dimension_id)
        if dimension is None:
            issues.append(
                NativeQualityIssue(
                    code=f"paper_review_{dimension_id}_missing",
                    message=f"Paper-review evaluation did not emit `{dimension_id}`.",
                )
            )
            continue
        if str(dimension.get("status") or "").upper() == "PASS":
            continue
        issues.append(
            NativeQualityIssue(
                code=f"paper_review_{dimension_id}",
                message=(
                    f"Paper-review `{dimension_id}` is "
                    f"{dimension.get('status') or 'unavailable'}: "
                    f"{dimension.get('evidence') or 'no evidence summary'}"
                ),
            )
        )
    return issues


def _check_claims(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``paper_review.check_claims``."""

    return _pr_check_dimensions(workspace, policy, ("claim_traceability",))


def _check_evidence_audit(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``paper_review.check_evidence_audit``."""

    return _pr_check_dimensions(workspace, policy, ("evidence_coverage",))


def _check_novelty_matrix(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``paper_review.check_novelty_matrix``."""

    return _pr_check_dimensions(workspace, policy, ("novelty_positioning",))


def _check_review(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``paper_review.check_review``."""

    return _pr_check_dimensions(
        workspace,
        policy,
        ("review_traceability", "recommendation_consistency"),
    )




# --- evidence-review family (policy-consuming) ------------------------------
#
# Native reimplementation of the whole ``tooling.quality_checks.evidence_review``
# module (five registered checks: protocol-writer, screening-manager,
# extraction-form + bias-assessor -> check_extraction with/without require_bias,
# synthesis-writer).  The protocol parser, candidate-pool loader, stable-id
# helper, and the two canonical constant tuples are self-contained and are
# reimplemented natively.  The one heavyweight dependency -- the evidence-review
# scorecard read by check_synthesis -- stays behind the ``WorkspacePolicyPort``
# (``evaluate_evidence_review``), legacy-backed so the scorecard is
# byte-identical; only the ``synthesis_traceability`` dimension is consulted.


_ER_CANONICAL_EXTRACTION_FIELDS = (
    "population_or_setting",
    "task",
    "metric",
    "study_type",
    "result_summary",
    "evidence_pointer",
)
_ER_REQUIRED_SYNTHESIS_SECTIONS = (
    "## Research questions + scope",
    "## Included studies summary",
    "## Extracted evidence table",
    "## Findings by theme",
    "## Risk of bias",
    "## Supported conclusions",
    "## Needs more evidence",
)


def _er_parse_protocol_extraction_fields(text: str) -> list[dict[str, str]]:
    """Native mirror of ``tooling.review_protocol.parse_protocol_extraction_fields``."""

    lines = (text or "").splitlines()
    fields: list[dict[str, str]] = []
    in_table = False
    for raw in lines:
        line = raw.strip()
        if line == "## Extraction Schema":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cols = [col.strip() for col in line.strip("|").split("|")]
        if not cols or cols[0] in {"field", "---"}:
            continue
        if len(cols) < 4:
            continue
        fields.append(
            {
                "field": cols[0],
                "definition": cols[1],
                "allowed_values": cols[2],
                "notes": cols[3],
            }
        )
    return fields


def _er_parse_protocol(text: str) -> dict[str, Any]:
    """Native mirror of ``tooling.review_protocol.parse_protocol``."""

    data: dict[str, Any] = {
        "review_questions": [],
        "include_keywords": [],
        "exclude_keywords": [],
        "time_window_from": "",
        "time_window_to": "",
        "inclusion": [],
        "exclusion": [],
        "extraction_fields": [],
    }
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("- RQ"):
            data["review_questions"].append(stripped[2:].strip())
        elif stripped.startswith("- include_keywords:"):
            data["include_keywords"] = [
                item.strip()
                for item in stripped.split(":", 1)[1].split(";")
                if item.strip()
            ]
        elif stripped.startswith("- exclude_keywords:"):
            data["exclude_keywords"] = [
                item.strip()
                for item in stripped.split(":", 1)[1].split(";")
                if item.strip()
            ]
        elif stripped.startswith("- time_window_from:"):
            data["time_window_from"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- time_window_to:"):
            data["time_window_to"] = stripped.split(":", 1)[1].strip()
        elif re.match(r"^- I[0-9]+:", stripped):
            code, body = stripped[2:].split(":", 1)
            data["inclusion"].append((code.strip(), body.strip()))
        elif re.match(r"^- E[0-9]+:", stripped):
            code, body = stripped[2:].split(":", 1)
            data["exclusion"].append((code.strip(), body.strip()))
    data["extraction_fields"] = _er_parse_protocol_extraction_fields(text)
    return data


def _er_load_candidate_records(workspace: Path) -> list[dict[str, Any]]:
    """Native mirror of ``tooling.review_artifacts.load_candidate_records``."""

    papers_dir = workspace / "papers"
    for path in (
        papers_dir / "papers_dedup.jsonl",
        papers_dir / "papers_raw.jsonl",
        papers_dir / "core_set.csv",
    ):
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            return [rec for rec in _read_jsonl(path) if isinstance(rec, dict)]
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
    return []


def _er_stable_paper_id(record: dict[str, Any], *, index: int) -> str:
    """Native mirror of ``tooling.review_artifacts.stable_paper_id``."""

    value = str(record.get("paper_id") or "").strip()
    return value if value else f"P{index:04d}"


def _check_protocol(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``evidence_review.check_protocol``.

    Self-contained (does not consume ``policy``); routed through the policy
    dispatch table only so it sits beside its evidence-review siblings.
    """

    out_rel = outputs[0] if outputs else "output/PROTOCOL.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_protocol", message=f"`{out_rel}` does not exist."
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[NativeQualityIssue] = []
    if _has_placeholder_markers(text):
        issues.append(
            NativeQualityIssue(
                code="protocol_placeholders",
                message="Protocol contains placeholder markers (TODO/TBD/FIXME).",
            )
        )

    protocol = _er_parse_protocol(text)
    field_names = {
        str(item.get("field") or "").strip()
        for item in protocol.get("extraction_fields") or []
    }
    missing_fields = [
        field for field in _ER_CANONICAL_EXTRACTION_FIELDS if field not in field_names
    ]
    missing_parts: list[str] = []
    if "## Databases and Sources" not in text:
        missing_parts.append("databases and sources")
    if "## Time Window" not in text:
        missing_parts.append("time window")
    if len(protocol.get("review_questions") or []) < 1:
        missing_parts.append("review questions")
    if len(protocol.get("inclusion") or []) < 2:
        missing_parts.append("numbered inclusion clauses")
    if len(protocol.get("exclusion") or []) < 2:
        missing_parts.append("numbered exclusion clauses")
    if missing_fields:
        missing_parts.append("extraction fields: " + ", ".join(missing_fields))
    if missing_parts:
        issues.append(
            NativeQualityIssue(
                code="protocol_missing_sections",
                message=(
                    "Protocol is missing operational contract parts: "
                    f"{', '.join(missing_parts)}."
                ),
            )
        )
    return issues


def _check_screening(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``evidence_review.check_screening``.

    Self-contained (does not consume ``policy``); routed through the policy
    dispatch table only so it sits beside its evidence-review siblings.
    """

    from collections import Counter

    out_rel = outputs[0] if outputs else "papers/screening_log.csv"
    path = workspace / out_rel
    protocol_path = workspace / "output" / "PROTOCOL.md"
    if not path.exists() or not protocol_path.exists():
        return [
            NativeQualityIssue(
                code="missing_screening_inputs",
                message="Evidence screening requires the protocol and screening log.",
            )
        ]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    candidates = _er_load_candidate_records(workspace)
    candidate_ids = {
        _er_stable_paper_id(record, index=index)
        for index, record in enumerate(candidates, start=1)
    }
    screened_ids = [str(row.get("paper_id") or "").strip() for row in rows]
    screened_id_set = {paper_id for paper_id in screened_ids if paper_id}
    protocol = _er_parse_protocol(
        protocol_path.read_text(encoding="utf-8", errors="ignore")
    )
    valid_codes = {
        code
        for code, _ in (protocol.get("inclusion") or [])
        + (protocol.get("exclusion") or [])
    }
    invalid = 0
    included = 0
    for row in rows:
        decision = str(row.get("decision") or "").strip().lower()
        included += int(decision == "include")
        codes = {
            value.strip()
            for value in re.split(r"[;,\s]+", str(row.get("reason_codes") or ""))
            if value.strip()
        }
        if (
            decision not in {"include", "exclude"}
            or not str(row.get("paper_id") or "").strip()
            or not codes
            or not codes.issubset(valid_codes)
            or not str(row.get("reason") or "").strip()
        ):
            invalid += 1
    issues: list[NativeQualityIssue] = []
    if not rows:
        issues.append(
            NativeQualityIssue(
                code="empty_screening_log",
                message=f"`{out_rel}` has no screening decisions.",
            )
        )
    if not candidates:
        issues.append(
            NativeQualityIssue(
                code="missing_screening_candidate_pool",
                message="No candidate pool is available to verify screening completeness.",
            )
        )
    elif candidate_ids != screened_id_set:
        missing = sorted(candidate_ids - screened_id_set)
        unexpected = sorted(screened_id_set - candidate_ids)
        issues.append(
            NativeQualityIssue(
                code="screening_candidate_coverage",
                message=(
                    f"`{out_rel}` covers "
                    f"{len(screened_id_set & candidate_ids)}/{len(candidate_ids)} "
                    f"candidate IDs; missing={missing[:5] or 'none'}, "
                    f"unexpected={unexpected[:5] or 'none'}."
                ),
            )
        )
    id_counts = Counter(paper_id for paper_id in screened_ids if paper_id)
    duplicate_ids = sorted(
        paper_id for paper_id, count in id_counts.items() if count > 1
    )
    if duplicate_ids:
        issues.append(
            NativeQualityIssue(
                code="duplicate_screening_decisions",
                message=(
                    f"`{out_rel}` contains duplicate decisions for: "
                    f"{', '.join(duplicate_ids[:5])}."
                ),
            )
        )
    if invalid:
        issues.append(
            NativeQualityIssue(
                code="untraceable_screening_rows",
                message=(
                    f"`{out_rel}` has {invalid} row(s) without valid "
                    "protocol-linked decisions and reasons."
                ),
            )
        )
    if rows and included == 0:
        issues.append(
            NativeQualityIssue(
                code="screening_includes_nothing",
                message=(
                    f"`{out_rel}` includes no studies; revise the protocol or "
                    "candidate pool before extraction."
                ),
            )
        )
    return issues


def _check_extraction(
    workspace: Path, outputs: list[str], *, require_bias: bool
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``evidence_review.check_extraction``.

    ``require_bias`` selects the bias-assessor variant (risk-of-bias fields
    required) vs the extraction-form variant, exactly as the legacy quality_gate
    wrappers pass it.
    """

    from collections import Counter

    out_rel = outputs[0] if outputs else "papers/extraction_table.csv"
    path = workspace / out_rel
    screening_path = workspace / "papers" / "screening_log.csv"
    if not path.exists() or not screening_path.exists():
        return [
            NativeQualityIssue(
                code="missing_extraction_inputs",
                message="Evidence extraction requires the screening log and extraction table.",
            )
        ]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    with screening_path.open("r", encoding="utf-8", newline="") as handle:
        screening = [dict(row) for row in csv.DictReader(handle)]
    included_ids = {
        str(row.get("paper_id") or "").strip()
        for row in screening
        if str(row.get("decision") or "").strip().lower() == "include"
    }
    extracted_ids = {
        str(row.get("paper_id") or "").strip()
        for row in rows
        if str(row.get("paper_id") or "").strip()
    }
    extracted_id_list = [
        str(row.get("paper_id") or "").strip()
        for row in rows
        if str(row.get("paper_id") or "").strip()
    ]
    issues: list[NativeQualityIssue] = []
    if not rows:
        return [
            NativeQualityIssue(
                code="empty_extraction_table",
                message=f"`{out_rel}` has no extracted studies.",
            )
        ]
    missing_columns = [
        field for field in _ER_CANONICAL_EXTRACTION_FIELDS if field not in set(rows[0])
    ]
    if missing_columns:
        issues.append(
            NativeQualityIssue(
                code="extraction_missing_columns",
                message=(
                    f"`{out_rel}` is missing canonical fields: "
                    f"{', '.join(missing_columns)}."
                ),
            )
        )
    missing_ids = sorted(included_ids - extracted_ids)
    unexpected_ids = sorted(extracted_ids - included_ids)
    if missing_ids or unexpected_ids:
        issues.append(
            NativeQualityIssue(
                code="extraction_screening_mismatch",
                message=(
                    "Extraction IDs must equal included screening IDs; "
                    f"missing={missing_ids}, unexpected={unexpected_ids}."
                ),
            )
        )
    duplicate_ids = sorted(
        paper_id
        for paper_id, count in Counter(extracted_id_list).items()
        if count > 1
    )
    if duplicate_ids:
        issues.append(
            NativeQualityIssue(
                code="duplicate_extraction_rows",
                message=(
                    f"`{out_rel}` contains duplicate extraction rows for: "
                    f"{', '.join(duplicate_ids[:5])}."
                ),
            )
        )
    thin_rows = sum(
        1
        for row in rows
        if any(
            not value
            or value.startswith("not reported")
            or value.startswith("not classifiable")
            for value in [
                str(row.get(field) or "").strip().lower()
                for field in _ER_CANONICAL_EXTRACTION_FIELDS
            ]
        )
    )
    if thin_rows:
        issues.append(
            NativeQualityIssue(
                code="extraction_rows_not_substantive",
                message=(
                    f"`{out_rel}` has {thin_rows} row(s) with missing or explicitly "
                    "unavailable canonical evidence fields; enrich or exclude them "
                    "before synthesis."
                ),
            )
        )
    if require_bias:
        allowed = {"low", "unclear", "high"}
        rob_fields = (
            "rob_selection",
            "rob_measurement",
            "rob_confounding",
            "rob_reporting",
            "rob_overall",
        )
        invalid_bias = sum(
            1
            for row in rows
            if any(
                str(row.get(field) or "").strip().lower() not in allowed
                for field in rob_fields
            )
            or not str(row.get("rob_notes") or "").strip()
        )
        if invalid_bias:
            issues.append(
                NativeQualityIssue(
                    code="incomplete_bias_assessment",
                    message=(
                        f"`{out_rel}` has {invalid_bias} row(s) with incomplete "
                        "risk-of-bias fields."
                    ),
                )
            )
    return issues


def _check_extraction_form(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native mirror of the ``extraction-form`` wrapper (require_bias=False)."""

    return _check_extraction(workspace, outputs, require_bias=False)


def _check_bias_assessor(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native mirror of the ``bias-assessor`` wrapper (require_bias=True)."""

    return _check_extraction(workspace, outputs, require_bias=True)


def _check_synthesis(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``evidence_review.check_synthesis``.

    Reads the evidence-review scorecard's ``synthesis_traceability`` dimension
    through the injected Port (legacy-backed, byte-identical); the required
    section scan is native.
    """

    out_rel = outputs[0] if outputs else "output/SYNTHESIS.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_evidence_synthesis",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues = [
        NativeQualityIssue(
            code="evidence_synthesis_missing_section",
            message=f"`{out_rel}` is missing `{heading}`.",
        )
        for heading in _ER_REQUIRED_SYNTHESIS_SECTIONS
        if heading not in text
    ]
    payload = policy.evaluate_evidence_review(workspace)
    trace = next(
        (item for item in payload["dimensions"] if item["id"] == "synthesis_traceability"),
        None,
    )
    if trace and trace["status"] != "PASS":
        issues.append(
            NativeQualityIssue(
                code="evidence_synthesis_untraceable",
                message=str(trace["evidence"]),
            )
        )
    return issues


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
    "arxiv-search": _check_arxiv_search,
    "pdf-text-extractor": _check_pdf_text_extractor,
    "literature-engineer": _check_literature_engineer,
    "dedupe-rank": _check_dedupe_rank,
    "latex-scaffold": _check_latex_scaffold,
    "latex-compile-qa": _check_latex_compile_qa,
    "idea-brief": _check_idea_brief,
    "idea-signal-mapper": _check_signal_table,
    "idea-direction-generator": _check_direction_pool,
    "idea-screener": _check_screening_table,
    "idea-shortlist-curator": _check_shortlist,
    "idea-memo-writer": _check_report_bundle,
    "claims-extractor": _check_claims,
    "evidence-auditor": _check_evidence_audit,
    "novelty-matrix": _check_novelty_matrix,
    "rubric-writer": _check_review,
    "extraction-form": _check_extraction_form,
    "bias-assessor": _check_bias_assessor,
    "synthesis-writer": _check_synthesis,
    "protocol-writer": _check_protocol,
    "screening-manager": _check_screening,
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
    target, quality contract, Goal page-range) through.  It defaults to the
    legacy adapter so runtime behavior is unchanged; the whole survey-retrieval
    family (``citation-verifier``, ``arxiv-search``, ``pdf-text-extractor``,
    ``literature-engineer``, ``dedupe-rank``) and the whole delivery family
    (``latex-scaffold``, ``latex-compile-qa``, plus the self-contained
    scaffold/report checks above) consume it, so the seam is load-bearing
    rather than merely constructed.
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
