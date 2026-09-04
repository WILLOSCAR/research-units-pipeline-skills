"""Native (tooling-free) implementation of the acceptance quality-check Port.

This module is the native :class:`~.quality_provider.QualityCheckProvider`:
it reimplements **every** registered semantic output check (all 68 Skills)
and the single registered completion invariant (``outline-refiner``) without
importing ``tooling`` -- not even lazily.  It is the runtime default;
``default_quality_provider`` returns it, and the transitional
``LegacyToolingQualityProvider`` adapter is retained only as a reversible
escape hatch (``RESEARCH_HARNESS_QUALITY_PROVIDER=legacy``).

Two dispatch tables route the work:

- ``_NATIVE_UNIT_CHECKS`` -- self-contained checks, signature
  ``(Path, list[str]) -> list[NativeQualityIssue]``; and
- ``_NATIVE_POLICY_UNIT_CHECKS`` -- policy-consuming checks, signature
  ``(Path, list[str], WorkspacePolicyPort) -> list[NativeQualityIssue]``.

A third table, ``_NATIVE_COMPLETION_INVARIANT_CHECKS``, routes
``check_completion_invariants``.  The registry-introspection methods
(:meth:`~NativeQualityProvider.registered_quality_skills` and
:meth:`~NativeQualityProvider.has_completion_invariant`) answer from routing
sets derived from these tables, so the tables and the introspection answers
can never drift.

Policy-consuming checks read workspace policy (run profile, evidence mode,
core-set target, the retrieval / candidate-pool / quality contracts, the Goal
page-range constraint, and the heavyweight evaluators -- template residue,
section-first gates, review scorecards, the ideation contract) through the
injected :class:`WorkspacePolicyPort` rather than importing
``tooling.quality_checks.survey_policy`` / ``tooling.common``.  The default
reader delegates to ``tooling``, so resolved policy values are byte-identical
by construction; only each check's own logic is reimplemented here.

Composition: a check with no native entry (only possible for an unregistered
Skill) falls through to the composed ``LegacyToolingQualityProvider``.  That
adapter is the only module in ``research_harness`` that wraps ``tooling``
(and it does so lazily).

The native tables and checks are kept honest by the Port parity tests, which
assert the registry equals the legacy provider's and pin every native check
to byte-for-byte parity (codes + messages + issue order) with its legacy
counterpart. Exception behavior is pinned for the completion invariant only.
"""

from __future__ import annotations

import csv
import hashlib
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

# Native mirror of ``tooling.quality_gate._COMPLETION_INVARIANTS``: Skills with
# a mandatory Workflow-domain invariant.  The invariants themselves are
# reimplemented natively and dispatched through ``_NATIVE_COMPLETION_INVARIANT_CHECKS``
# (defined below, next to the provider, since they reuse the policy-check
# signature); ``_NATIVE_COMPLETION_INVARIANTS`` (the routing set used by
# ``has_completion_invariant``) is derived from that table so the two never
# drift.

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
    reconciliation_records: list[dict] = []
    for rec in records:
        if isinstance(rec, dict) and str(rec.get("record_type") or "").strip() == "corpus_reconciliation":
            reconciliation_records.append(rec)
            continue
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
    if not reconciliation_records:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_missing_reconciliation",
                message=(
                    "Missing a `corpus_reconciliation` record; coverage cannot show whether "
                    "every ingested source contributed to a module."
                ),
            )
        )
    elif len(reconciliation_records) > 1:
        issues.append(
            NativeQualityIssue(
                code="source_coverage_duplicate_reconciliation",
                message=f"`{out_rel}` has {len(reconciliation_records)} `corpus_reconciliation` records; expected exactly one.",
            )
        )
    else:
        recon = reconciliation_records[0]
        ingested = [str(sid or "").strip() for sid in recon.get("ingested_source_ids") or [] if str(sid or "").strip()]
        attributed = {str(sid or "").strip() for sid in recon.get("attributed_source_ids") or [] if str(sid or "").strip()}
        declared_unused = [str(sid or "").strip() for sid in recon.get("unused_source_ids") or [] if str(sid or "").strip()]
        recon_gaps = [str(item or "").strip() for item in recon.get("gaps") or [] if str(item or "").strip()]
        expected_unused = [sid for sid in ingested if sid not in attributed]
        missing_ingested = sorted(backed_source_ids - set(ingested))
        if missing_ingested:
            issues.append(
                NativeQualityIssue(
                    code="source_coverage_reconciliation_incomplete",
                    message=(
                        "`corpus_reconciliation` omits successfully ingested source(s): "
                        + ", ".join(missing_ingested)
                        + "."
                    ),
                )
            )
        if sorted(declared_unused) != sorted(expected_unused):
            issues.append(
                NativeQualityIssue(
                    code="source_coverage_reconciliation_unused_mismatch",
                    message=(
                        "`corpus_reconciliation` unused_source_ids "
                        f"{sorted(declared_unused)} != ingested-minus-attributed {sorted(expected_unused)}."
                    ),
                )
            )
        if expected_unused and not recon_gaps:
            issues.append(
                NativeQualityIssue(
                    code="source_coverage_unused_source_not_flagged",
                    message=(
                        "Ingested source(s) contributed to no module ("
                        + ", ".join(sorted(expected_unused))
                        + ") but `corpus_reconciliation.gaps` is empty."
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




# --- survey-structure family (self-contained) -------------------------------
#
# Native reimplementation of the three *registered* checks in
# ``tooling.quality_checks.survey_structure`` (chapter-skeleton, section-bindings,
# section-briefs).  They read only YAML/JSONL outputs -- no workspace policy --
# via the native ``_st_load_yaml`` / ``_read_jsonl`` helpers.  (The module's
# ``section_first_*`` gates are heavyweight evaluators that stay behind the
# ``WorkspacePolicyPort`` rather than being reimplemented here; the
# ``outline-refiner`` completion invariant calls them through that Port.)
# These are routed through the policy dispatch table with an ignored
# ``policy`` arg only because they are defined after the self-contained
# dispatch table.


def _check_chapter_skeleton(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_structure.check_chapter_skeleton``."""

    out_rel = outputs[0] if outputs else "outline/chapter_skeleton.yml"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_chapter_skeleton",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    data = _st_load_yaml(path)
    if not isinstance(data, list) or not data:
        return [
            NativeQualityIssue(
                code="invalid_chapter_skeleton",
                message=f"`{out_rel}` must be a non-empty YAML list.",
            )
        ]
    missing = 0
    for rec in data:
        if not isinstance(rec, dict):
            missing += 1
            continue
        required = ("id", "title", "rationale", "seed_topics", "target_h3_count")
        if any(not rec.get(key) for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("seed_topics"), list):
            missing += 1
            continue
    if missing:
        return [
            NativeQualityIssue(
                code="chapter_skeleton_missing_fields",
                message=f"`{out_rel}` has {missing} invalid chapter skeleton record(s).",
            )
        ]
    return []


def _check_section_bindings(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_structure.check_section_bindings``."""

    bindings_rel = outputs[0] if outputs else "outline/section_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/section_binding_report.md"
    bindings_path = workspace / bindings_rel
    report_path = workspace / report_rel
    if not bindings_path.exists():
        return [
            NativeQualityIssue(
                code="missing_section_bindings",
                message=f"`{bindings_rel}` does not exist.",
            )
        ]
    records = [r for r in _read_jsonl(bindings_path) if isinstance(r, dict)]
    if not records:
        return [
            NativeQualityIssue(
                code="invalid_section_bindings",
                message=f"`{bindings_rel}` has no JSON objects.",
            )
        ]
    missing = 0
    invalid_status = 0
    invalid_semantics = 0
    derived_records: list[dict[str, Any]] = []
    for rec in records:
        required = (
            "section_id",
            "section_title",
            "paper_ids_primary",
            "paper_ids_support",
            "coverage_count",
            "status",
            "blocking_gaps",
            "decomposition_recommendation",
        )
        if any(key not in rec for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("paper_ids_primary"), list) or not isinstance(
            rec.get("paper_ids_support"), list
        ):
            missing += 1
            continue
        if not isinstance(rec.get("blocking_gaps"), list):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status != status:
            invalid_semantics += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            invalid_semantics += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            invalid_semantics += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            invalid_semantics += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            invalid_semantics += 1
            continue
        derived_records.append(
            {
                "section_id": str(rec.get("section_id") or "").strip(),
                "binding_status": binding_status or status,
                "decomposition_recommendation": recommendation,
                "blocking_gaps": list(blocking_gaps),
            }
        )
    if missing:
        return [
            NativeQualityIssue(
                code="section_bindings_missing_fields",
                message=f"`{bindings_rel}` has {missing} invalid section-binding record(s).",
            )
        ]
    if invalid_status:
        return [
            NativeQualityIssue(
                code="section_bindings_invalid_status",
                message=(
                    f"`{bindings_rel}` has {invalid_status} record(s) with unknown "
                    "binding status (expected PASS/BLOCKED/REROUTE)."
                ),
            )
        ]
    if invalid_semantics:
        return [
            NativeQualityIssue(
                code="section_bindings_invalid_semantics",
                message=(
                    f"`{bindings_rel}` has {invalid_semantics} record(s) where "
                    "status, blocking_gaps, and decomposition_recommendation disagree."
                ),
            )
        ]
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_section_binding_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    rows = _ss_parse_section_binding_report_rows(report)
    if "| Section |" not in report or "| Status |" not in report or not rows:
        return [
            NativeQualityIssue(
                code="invalid_section_binding_report",
                message=f"`{report_rel}` is missing the section binding summary table.",
            )
        ]
    by_section_id: dict[str, dict[str, Any]] = {}
    for rec in derived_records:
        section_id = str(rec.get("section_id") or "").strip()
        if section_id:
            by_section_id[section_id] = rec
    if len(rows) != len(derived_records):
        return [
            NativeQualityIssue(
                code="section_binding_report_row_mismatch",
                message=(
                    f"`{report_rel}` should report one status row per section "
                    f"binding (report rows={len(rows)}, binding "
                    f"rows={len(derived_records)})."
                ),
            )
        ]
    bad_statuses = sorted(
        {
            str(row.get("status") or "").strip().upper()
            for row in rows
            if str(row.get("status") or "").strip().upper()
            not in {"PASS", "BLOCKED", "REROUTE"}
        }
    )
    if bad_statuses:
        return [
            NativeQualityIssue(
                code="section_binding_report_bad_status",
                message=(
                    f"`{report_rel}` contains unsupported binding statuses: "
                    f"{', '.join(bad_statuses)}."
                ),
            )
        ]
    inconsistent: list[str] = []
    for row in rows:
        label = str(row.get("section") or "").strip()
        section_id = label.split(" ", 1)[0].strip()
        rec = by_section_id.get(section_id) or {}
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        report_status = str(row.get("status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if binding_status != report_status:
            inconsistent.append(
                f"{section_id}: report={report_status} jsonl={binding_status or 'missing'}"
            )
            continue
        if report_status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            inconsistent.append(f"{section_id}: PASS with non-decompose semantics")
        if report_status == "BLOCKED" and not blocking_gaps:
            inconsistent.append(f"{section_id}: BLOCKED without blocking_gaps")
        if report_status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            inconsistent.append(f"{section_id}: REROUTE without hold_or_merge semantics")
    if inconsistent:
        return [
            NativeQualityIssue(
                code="section_binding_report_drift",
                message=(
                    f"`{bindings_rel}` and `{report_rel}` disagree about "
                    "section-binding gate state: "
                    f"{', '.join(inconsistent[:6])}."
                ),
            )
        ]
    return []


def _ss_parse_section_binding_report_rows(text: str) -> list[dict[str, str]]:
    """Native mirror of ``survey_structure._parse_section_binding_report_rows``."""

    rows: list[dict[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "section" and cells[2].lower() == "status":
            continue
        rows.append(
            {
                "section": cells[0],
                "coverage": cells[1],
                "status": cells[2].upper(),
                "recommendation": cells[3],
            }
        )
    return rows


def _check_section_briefs(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_structure.check_section_briefs``."""

    out_rel = outputs[0] if outputs else "outline/section_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_section_briefs",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    records = [r for r in _read_jsonl(path) if isinstance(r, dict)]
    if not records:
        return [
            NativeQualityIssue(
                code="invalid_section_briefs",
                message=f"`{out_rel}` has no JSON objects.",
            )
        ]
    missing = 0
    for rec in records:
        required = (
            "section_id",
            "section_title",
            "section_rationale",
            "contrast_lens",
            "must_cover",
            "target_h3_count",
            "subsection_seeds",
            "status",
            "decomposition_recommendation",
            "blocking_gaps",
        )
        if any(key not in rec for key in required):
            missing += 1
            continue
        if (
            not isinstance(rec.get("contrast_lens"), list)
            or not isinstance(rec.get("must_cover"), list)
            or not isinstance(rec.get("subsection_seeds"), list)
            or not isinstance(rec.get("blocking_gaps"), list)
        ):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and status != binding_status:
            missing += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            missing += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            missing += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            missing += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            missing += 1
            continue
    if missing:
        return [
            NativeQualityIssue(
                code="section_briefs_missing_fields",
                message=f"`{out_rel}` has {missing} invalid section brief record(s).",
            )
        ]
    return []




# --- survey-text helpers (pure, shared by survey_writing + survey_planning) --
#
# Native mirror of ``tooling.quality_checks.survey_text`` (pure text utilities:
# short-description counts, repeated-template / repeated-sentence boilerplate
# detection, H3-block splitting, section-body extraction).  Stdlib only.


def _sx_short_description_counts(
    values: Sequence[str], *, min_chars: int
) -> tuple[int, int]:
    total = 0
    short = 0
    for v in values:
        v = str(v or "").strip()
        if not v:
            continue
        total += 1
        if len(v) < int(min_chars):
            short += 1
    return short, total


def _sx_repeated_template_text(
    *, text: str, min_len: int = 32, min_repeats: int = 6
) -> tuple[str, int] | None:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    counts: dict[str, int] = {}
    for ln in lines:
        if len(ln) < int(min_len):
            continue
        norm = re.sub(r"\[@[^\]]+\]", "", ln)
        norm = re.sub(r"\s+", " ", norm).strip().lower()
        if len(norm) < int(min_len):
            continue
        counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return None
    top_norm, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if top_count >= int(min_repeats):
        example = top_norm[:120]
        return example, top_count
    return None


def _sx_repeated_sentences(
    *, text: str, min_len: int = 80, min_repeats: int = 6
) -> tuple[str, int] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    compact = re.sub(r"\[@[^\]]+\]", "", raw)
    compact = re.sub(r"\s+", " ", compact).strip()
    if not compact:
        return None
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]
    counts: dict[str, int] = {}
    for s in sents:
        if len(s) < int(min_len):
            continue
        norm = re.sub(r"\s+", " ", s).strip().lower()
        if len(norm) < int(min_len):
            continue
        counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return None
    top_norm, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if top_count >= int(min_repeats):
        return top_norm[:140], top_count
    return None


def _sx_split_h3_blocks(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    cur_title = ""
    cur_lines: list[str] = []

    def _flush() -> None:
        nonlocal cur_title, cur_lines
        if not cur_title:
            return
        out.append((cur_title, "\n".join(cur_lines).strip()))

    for raw in (text or "").splitlines():
        if raw.startswith("### "):
            _flush()
            cur_title = raw[4:].strip()
            cur_lines = []
            continue
        if raw.startswith("## "):
            _flush()
            cur_title = ""
            cur_lines = []
            continue
        if cur_title:
            cur_lines.append(raw)

    _flush()
    return out


def _sx_extract_section_body(text: str, *, heading_re: str) -> str | None:
    m = re.search(heading_re, text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"(?m)^##\s+", text[start:])
    end = start + nxt.start() if nxt else len(text)
    return text[start:end].strip()




# --- survey-writing family (policy-consuming) -------------------------------
#
# Native reimplementation of tooling.quality_checks.survey_writing (the largest
# check module).  Policy reads (profile, draft_profile, core_size,
# global_citation_min_subsections, quality_contract_int) and the heavyweight
# template-residue evaluators go through the WorkspacePolicyPort (legacy-backed,
# byte-identical); survey-text helpers use the native _sx_* mirrors; the
# reader-request-leakage detector is reimplemented natively.  Every check reads
# YAML/JSONL/Markdown outputs and produces identical (code, message) lists to
# legacy.


_SW_BOUNDED_SURVEY_DELIVERABLE_EN = (
    r"(?:(?:course\s+paper|term\s+paper|course\s+report|class\s+report|"
    r"seminar\s+paper|seminar\s+report|end(?:-|\s+)of(?:-|\s+)term\s+"
    r"(?:paper|report)|short\s+literature(?:-|\s+)review(?:\s+report)?|"
    r"literature\s+review\s+report)|(?:topic\s+report|"
    r"technical\s+(?:literature|survey|research)\s+report|"
    r"research(?:-|\s+)landscape\s+report))"
)
_SW_BOUNDED_SURVEY_DELIVERABLE_ZH = (
    r"(?:(?:课程论文|课程报告|期末论文|期末报告|结课论文|结课报告|研讨课论文|"
    r"研讨课报告|文献综述报告|短文献综述|短篇文献综述)|"
    r"(?:专题报告|专题调研报告|技术调研报告|技术综述报告|研究现状报告))"
)


def _sw_reader_request_leakage(text: str) -> list[str]:
    """Native mirror of ``tooling.common.reader_request_leakage``."""

    checks = [
        (
            "imperative paper request",
            r"(?i)\b(?:please\s+)?(?:write|draft|prepare|create)\s+(?:an?\s+)?"
            r"(?:(?:\d+\s*(?:-|–|to)\s*\d+|\d+)\s*(?:-\s*)?pages?\s+)?"
            rf"(?:compact\s+)?{_SW_BOUNDED_SURVEY_DELIVERABLE_EN}\s+(?:on|about)\b",
        ),
        (
            "delivery-format request",
            r"(?i)\bwith\s+(?:a\s+)?(?:final\s+)?(?:latex(?:\s*/\s*pdf)?|pdf|markdown)"
            r"(?:\s+(?:output|deliverable|version))?\b",
        ),
        (
            "Chinese paper request",
            r"(?:请?(?:帮我)?(?:写|生成|准备)(?:一篇)?(?:\s*\d+\s*(?:-|—|–|到|至)\s*\d+\s*页)?(?:关于)?)"
            rf"[^\n。]{{0,180}}{_SW_BOUNDED_SURVEY_DELIVERABLE_ZH}",
        ),
    ]
    return [label for label, pattern in checks if re.search(pattern, text or "")]


def _sw_expected_h3_ids(workspace: Path) -> list[str]:
    outline_path = workspace / "outline" / "outline.yml"
    outline = _st_load_yaml(outline_path) if outline_path.exists() else []
    expected: list[str] = []
    if not isinstance(outline, list):
        return expected
    for section in outline:
        if not isinstance(section, dict):
            continue
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sub_id = str(subsection.get("id") or "").strip()
            if sub_id:
                expected.append(sub_id)
    return expected


def _sw_section_path_for_id(sub_id: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in str(sub_id or "")).strip("_")
    return f"sections/S{safe}.md"


def _sw_draft_h3_cite_sets(text: str) -> dict[str, set[str]]:
    def _extract_keys(block: str) -> set[str]:
        keys: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", block or ""):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    keys.add(k)
        return keys

    out: dict[str, set[str]] = {}
    cur_title = ""
    cur_lines: list[str] = []

    def _flush() -> None:
        nonlocal cur_title, cur_lines
        if not cur_title:
            return
        out[cur_title] = _extract_keys("\n".join(cur_lines))

    for raw in (text or "").splitlines():
        if raw.startswith("### "):
            _flush()
            cur_title = raw[4:].strip()
            cur_lines = []
            continue
        if raw.startswith("## "):
            _flush()
            cur_title = ""
            cur_lines = []
            continue
        if cur_title:
            cur_lines.append(raw)

    _flush()
    return out


def _check_writer_selfloop(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_writer_selfloop``."""

    out_rel = outputs[0] if outputs else "output/WRITER_SELFLOOP_TODO.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_writer_selfloop_report",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_writer_selfloop_report", message=f"`{out_rel}` is empty."
            )
        ]
    if "<!--" in text and "scaffold" in text.lower():
        return [
            NativeQualityIssue(
                code="writer_selfloop_scaffold_markers",
                message=f"`{out_rel}` contains scaffold markers; regenerate the self-loop report.",
            )
        ]
    if "…" in text:
        return [
            NativeQualityIssue(
                code="writer_selfloop_contains_ellipsis",
                message=(
                    f"`{out_rel}` contains unicode ellipsis (`…`); regenerate the "
                    "report without truncation markers."
                ),
            )
        ]
    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []
    return [
        NativeQualityIssue(
            code="writer_selfloop_not_pass",
            message=(
                f"`{out_rel}` is not PASS; fix the listed failing `sections/*.md` "
                "files and rerun `writer-selfloop`."
            ),
        )
    ]


def _check_front_matter_writer(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_front_matter_writer``."""

    report_rel = next(
        (item for item in outputs if item.endswith("FRONT_MATTER_REPORT.md")),
        "output/FRONT_MATTER_REPORT.md",
    )
    report_path = workspace / report_rel
    issues: list[NativeQualityIssue] = []
    if not report_path.is_file() or report_path.stat().st_size <= 0:
        issues.append(
            NativeQualityIssue(
                code="missing_front_matter_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        )
    elif not re.search(
        r"(?im)^\s*(?:[-*]\s*)?(?:status\s*:\s*)?PASS\s*$",
        report_path.read_text(encoding="utf-8", errors="ignore"),
    ):
        issues.append(
            NativeQualityIssue(
                code="front_matter_report_not_pass",
                message=f"`{report_rel}` is not PASS.",
            )
        )

    prose_relpaths = [
        item
        for item in outputs
        if item.startswith("sections/") and item.endswith(".md")
    ] or [
        "sections/abstract.md",
        "sections/S1.md",
        "sections/S2.md",
        "sections/discussion.md",
        "sections/conclusion.md",
    ]
    missing = [relpath for relpath in prose_relpaths if not (workspace / relpath).is_file()]
    if missing:
        issues.append(
            NativeQualityIssue(
                code="front_matter_files_missing",
                message="Missing front-matter prose: " + ", ".join(missing),
            )
        )
    documents = [
        (relpath, (workspace / relpath).read_text(encoding="utf-8", errors="ignore"))
        for relpath in prose_relpaths
        if (workspace / relpath).is_file()
    ]
    issues.extend(
        _as_native_issues(policy.template_residue_document_issues(workspace, documents))
    )
    return issues


def _check_eval_anchor_report(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_eval_anchor_report``."""

    out_rel = outputs[0] if outputs else "output/EVAL_ANCHOR_REPORT.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_eval_anchor_report",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_eval_anchor_report", message=f"`{out_rel}` is empty."
            )
        ]
    checked_match = re.search(r"(?im)^-\s*Files checked:\s*(\d+)\b", text)
    if not checked_match:
        return [
            NativeQualityIssue(
                code="eval_anchor_report_missing_counts",
                message=(
                    f"`{out_rel}` is missing the `Files checked` summary; rerun "
                    "`evaluation-anchor-checker`."
                ),
            )
        ]
    if int(checked_match.group(1)) <= 0:
        return [
            NativeQualityIssue(
                code="eval_anchor_report_zero_files",
                message=(
                    f"`{out_rel}` reports zero checked files; ensure subsection "
                    "files exist, then rerun `evaluation-anchor-checker`."
                ),
            )
        ]
    return []


def _check_paragraph_curator(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_paragraph_curator``."""

    report_rel = next(
        (item for item in outputs if item.endswith("PARAGRAPH_CURATION_REPORT.md")),
        "output/PARAGRAPH_CURATION_REPORT.md",
    )
    marker_rel = next(
        (item for item in outputs if item.endswith(".refined.ok")),
        "sections/paragraphs_curated.refined.ok",
    )
    report_path = workspace / report_rel
    marker_path = workspace / marker_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_paragraph_curation_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]
    issues: list[NativeQualityIssue] = []
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^-\s*Status:\s*PASS\s*$", report):
        issues.append(
            NativeQualityIssue(
                code="paragraph_curation_not_pass",
                message=f"`{report_rel}` does not report PASS.",
            )
        )
    if not marker_path.exists():
        issues.append(
            NativeQualityIssue(
                code="paragraph_curation_marker_missing",
                message=f"`{marker_rel}` does not exist.",
            )
        )
    profile = policy.draft_profile(workspace)
    minimum, maximum = {
        "course_paper": (5, 7),
        "survey": (10, 12),
        "deep": (11, 13),
    }.get(profile, (1, 14))
    off_budget: list[str] = []
    for sub_id in _sw_expected_h3_ids(workspace):
        relpath = _sw_section_path_for_id(sub_id)
        path = workspace / relpath
        if not path.exists():
            off_budget.append(f"{sub_id}=missing")
            continue
        count = len(
            [
                part
                for part in re.split(
                    r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip()
                )
                if part.strip()
            ]
        )
        if count < minimum or count > maximum:
            off_budget.append(f"{sub_id}={count}")
    if off_budget:
        issues.append(
            NativeQualityIssue(
                code="paragraph_curation_outside_profile_budget",
                message=(
                    f"H3 paragraph counts fall outside the `{profile}` budget "
                    f"{minimum}-{maximum}: {', '.join(off_budget[:8])}."
                ),
            )
        )
    return issues


def _check_argument_snapshot(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_argument_snapshot``."""

    todo_rel = next(
        (item for item in outputs if item.endswith("ARGUMENT_SELFLOOP_TODO.md")),
        "output/ARGUMENT_SELFLOOP_TODO.md",
    )
    summaries_rel = next(
        (item for item in outputs if item.endswith("SECTION_ARGUMENT_SUMMARIES.jsonl")),
        "output/SECTION_ARGUMENT_SUMMARIES.jsonl",
    )
    skeleton_rel = next(
        (item for item in outputs if item.endswith("ARGUMENT_SKELETON.md")),
        "output/ARGUMENT_SKELETON.md",
    )
    manifest_rel = next(
        (item for item in outputs if item.endswith("sections_manifest.jsonl")),
        "sections/sections_manifest.jsonl",
    )
    required = [todo_rel, summaries_rel, skeleton_rel, manifest_rel]
    missing = [relpath for relpath in required if not (workspace / relpath).exists()]
    if missing:
        return [
            NativeQualityIssue(
                code="argument_snapshot_missing_outputs",
                message=f"Argument snapshot is missing: {', '.join(missing)}.",
            )
        ]
    issues: list[NativeQualityIssue] = []
    report = (workspace / todo_rel).read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^-\s*Status:\s*PASS\s*$", report):
        issues.append(
            NativeQualityIssue(
                code="argument_snapshot_not_pass",
                message=f"`{todo_rel}` does not report PASS.",
            )
        )
    skeleton = (workspace / skeleton_rel).read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^##\s+Consistency Contract\s*$", skeleton):
        issues.append(
            NativeQualityIssue(
                code="argument_snapshot_missing_contract",
                message=f"`{skeleton_rel}` lacks `## Consistency Contract`.",
            )
        )
    allowed_moves = {
        "setup",
        "thesis",
        "contrast",
        "evidence",
        "evaluation",
        "limitation",
        "synthesis",
        "takeaway",
    }
    summaries = [
        record
        for record in _read_jsonl(workspace / summaries_rel)
        if isinstance(record, dict)
    ]
    by_id = {
        str(record.get("id") or "").strip(): record
        for record in summaries
        if str(record.get("id") or "").strip()
    }
    incomplete: list[str] = []
    for sub_id in _sw_expected_h3_ids(workspace):
        record = by_id.get(sub_id)
        paragraphs = record.get("paragraphs") if isinstance(record, dict) else None
        if not isinstance(paragraphs, list) or not paragraphs:
            incomplete.append(sub_id)
            continue
        for paragraph in paragraphs:
            moves = paragraph.get("moves") if isinstance(paragraph, dict) else None
            if (
                not isinstance(moves, list)
                or not moves
                or any(str(move) not in allowed_moves for move in moves)
            ):
                incomplete.append(sub_id)
                break
    if incomplete:
        issues.append(
            NativeQualityIssue(
                code="argument_snapshot_incomplete_moves",
                message=(
                    "Argument summaries are missing valid paragraph moves for: "
                    f"{', '.join(dict.fromkeys(incomplete))}."
                ),
            )
        )
    manifest = [
        record
        for record in _read_jsonl(workspace / manifest_rel)
        if isinstance(record, dict)
    ]
    manifest_by_path = {str(record.get("path") or "").strip(): record for record in manifest}
    stale: list[str] = []
    for sub_id in _sw_expected_h3_ids(workspace):
        relpath = _sw_section_path_for_id(sub_id)
        path = workspace / relpath
        record = manifest_by_path.get(relpath)
        if not path.exists() or not isinstance(record, dict):
            stale.append(relpath)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (
            str(record.get("sha256") or "") != digest
            or int(record.get("bytes") or 0) != path.stat().st_size
        ):
            stale.append(relpath)
    if stale:
        issues.append(
            NativeQualityIssue(
                code="sections_manifest_stale",
                message=(
                    f"`{manifest_rel}` does not fingerprint the current section "
                    f"content: {', '.join(stale[:8])}."
                ),
            )
        )
    return issues


def _check_section_logic_polisher(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_section_logic_polisher``."""

    report_rel = outputs[0] if outputs else "output/SECTION_LOGIC_REPORT.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_section_logic_report",
                message=f"`{report_rel}` does not exist.",
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report:
        return [
            NativeQualityIssue(
                code="empty_section_logic_report",
                message=f"`{report_rel}` is empty.",
            )
        ]
    if _has_placeholder_markers(report) or "…" in report:
        return [
            NativeQualityIssue(
                code="section_logic_report_placeholders",
                message=(
                    f"`{report_rel}` contains placeholders/ellipsis; regenerate the "
                    "report after fixing section files."
                ),
            )
        ]
    if "- Status: PASS" not in report:
        return [
            NativeQualityIssue(
                code="section_logic_report_not_pass",
                message=(
                    f"`{report_rel}` is not PASS; fix paragraph-1 thesis / "
                    "template-opener issues in the flagged H3 files and rerun "
                    "`section-logic-polisher`."
                ),
            )
        ]
    return []


def _check_merge_report(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_merge_report``."""

    draft_rel = outputs[0] if outputs else "output/DRAFT.md"
    report_rel = outputs[1] if len(outputs) > 1 else "output/MERGE_REPORT.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_merge_report", message=f"`{report_rel}` does not exist."
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    if "- Status: PASS" not in report:
        return [
            NativeQualityIssue(
                code="merge_not_pass",
                message=f"`{report_rel}` is not PASS; fix missing section files and rerun merge.",
            )
        ]
    draft_path = workspace / draft_rel
    if not draft_path.exists():
        return [
            NativeQualityIssue(
                code="missing_merged_draft", message=f"`{draft_rel}` does not exist."
            )
        ]
    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"(?m)^TODO:\s+MISSING\s+`", draft):
        return [
            NativeQualityIssue(
                code="merge_contains_missing_markers",
                message=(
                    "Merged draft still contains `TODO: MISSING ...` markers; write "
                    "the missing `sections/*.md` units and merge again."
                ),
            )
        ]
    return []


def _check_audit_report(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_audit_report``."""

    out_rel = outputs[0] if outputs else "output/AUDIT_REPORT.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_audit_report", message=f"`{out_rel}` does not exist."
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_audit_report", message=f"`{out_rel}` is empty."
            )
        ]
    if "- Status: PASS" not in text:
        return [
            NativeQualityIssue(
                code="audit_report_not_pass",
                message=f"`{out_rel}` does not report PASS; fix issues and rerun auditor.",
            )
        ]
    draft_rel = "output/DRAFT.md"
    draft_path = workspace / draft_rel
    if not draft_path.exists():
        return [
            NativeQualityIssue(
                code="missing_audited_draft", message=f"`{draft_rel}` does not exist."
            )
        ]
    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    return _as_native_issues(
        policy.template_residue_document_issues(workspace, [(draft_rel, draft)])
    )


def _sw_check_draft(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_draft``."""

    out_rel = outputs[0] if outputs else "output/DRAFT.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(code="missing_draft", message=f"`{out_rel}` does not exist.")
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[NativeQualityIssue] = []
    request_leaks = _sw_reader_request_leakage(text)
    if request_leaks:
        issues.append(
            NativeQualityIssue(
                code="draft_delivery_request_leakage",
                message=(
                    "Draft contains user delivery instructions instead of a "
                    "reader-facing research subject "
                    f"({', '.join(request_leaks)}). Normalize the paper title/front "
                    "matter from `GOAL.md` before merging."
                ),
            )
        )
    if re.search(r"\bTODO\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_contains_todo",
                message="Draft still contains `TODO` placeholders.",
            )
        )
    if re.search(r"(?i)\b(?:TBD|FIXME)\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_contains_placeholders",
                message="Draft still contains `TBD/FIXME` placeholders.",
            )
        )
    if "<!-- SCAFFOLD" in text:
        issues.append(
            NativeQualityIssue(
                code="draft_contains_scaffold",
                message="Draft still contains `<!-- SCAFFOLD ... -->` markers.",
            )
        )
    if "[@" not in text:
        issues.append(
            NativeQualityIssue(
                code="draft_no_citations",
                message="Draft contains no citation markers like `[@BibKey]`.",
            )
        )
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        issues.append(
            NativeQualityIssue(
                code="draft_placeholder_cites",
                message=(
                    "Draft still contains placeholder citation keys like `[@Key1]`; "
                    "replace with real keys from `citations/ref.bib`."
                ),
            )
        )
    profile = policy.pipeline_profile_name(workspace)
    if "…" in text:
        issues.append(
            NativeQualityIssue(
                code="draft_contains_ellipsis_placeholders",
                message=(
                    "Draft contains unicode ellipsis (`…`), which is treated as a "
                    "hard failure signal (usually truncated scaffold text); "
                    "regenerate after fixing outline/claims/visuals."
                ),
            )
        )
    if re.search(r"(?m)\.\.\.+", text):
        issues.append(
            NativeQualityIssue(
                code="draft_contains_truncation_dots",
                message=(
                    "Draft contains `...` truncation markers, which read as scaffold "
                    "leakage; remove truncation and rewrite into complete "
                    "sentences/cells."
                ),
            )
        )
    if re.search(r"(?i)enumerate\s+2-4\s+recurring", text):
        issues.append(
            NativeQualityIssue(
                code="draft_scaffold_instructions",
                message=(
                    "Draft still contains scaffold instructions like 'enumerate 2-4 "
                    "recurring ...'; rewrite outline/claims into concrete content "
                    "before drafting."
                ),
            )
        )
    if re.search(
        r"(?i)\b(?:scope and definitions for|design space in|evaluation practice for)\b",
        text,
    ):
        issues.append(
            NativeQualityIssue(
                code="draft_scaffold_phrases",
                message=(
                    "Draft still contains outline scaffold phrases (scope/design "
                    "space/evaluation practice). Replace with subsection-specific "
                    "content grounded in evidence fields and mapped papers."
                ),
            )
        )
    if re.search(r"(?i)\babstracts are treated as verification targets\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_pipeline_voice_abstract_only",
                message=(
                    "Draft contains pipeline-style evidence-mode boilerplate "
                    "('abstracts are treated as verification targets'). Move evidence "
                    "caveats into a single, short evidence-policy paragraph (once, in "
                    "front matter), and keep subsections focused on concrete "
                    "comparisons."
                ),
            )
        )
    if re.search(r"(?i)\bthe main axes we track are\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_pipeline_voice_axes_template",
                message=(
                    "Draft contains the repeated axes template ('The main axes we "
                    "track are ...'), which reads as scaffolding. Use "
                    "subsection-specific axes from `outline/subsection_briefs.jsonl` "
                    "/ `outline/evidence_drafts.jsonl` and avoid repeating a global "
                    "template sentence."
                ),
            )
        )
    dangling_numeric_caveats = re.findall(
        r"(?i)\b(?:that number|the cited number|this numeric margin|the numeric margin)\b",
        text,
    )
    if dangling_numeric_caveats:
        issues.append(
            NativeQualityIssue(
                code="draft_dangling_numeric_caveat",
                message=(
                    "Draft contains anaphoric numeric caveats after the underlying "
                    f"number was removed ({len(dangling_numeric_caveats)} "
                    "occurrence(s)). Rewrite each caveat as a standalone, "
                    "evidence-bounded claim about the cited setup."
                ),
            )
        )
    bib_path = workspace / "citations" / "ref.bib"
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))
        cited: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", text):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    cited.add(k)
        missing = sorted([k for k in cited if k not in bib_keys])
        if missing:
            sample = ", ".join(missing[:8])
            suffix = "..." if len(missing) > 8 else ""
            issues.append(
                NativeQualityIssue(
                    code="draft_cites_missing_in_bib",
                    message=(
                        f"Draft cites keys that are missing from `citations/ref.bib` "
                        f"(e.g., {sample}{suffix})."
                    ),
                )
            )
        if profile == "arxiv-survey":
            min_bib = int(policy.core_size(workspace)) or 150
            if len(bib_keys) < min_bib:
                issues.append(
                    NativeQualityIssue(
                        code="draft_bib_too_small",
                        message=(
                            f"`citations/ref.bib` has {len(bib_keys)} entries; target "
                            f">= {min_bib} for survey-quality coverage."
                        ),
                    )
                )
    adj_cite_pat = r"\[@[^\]]+\]\s*\[@[^\]]+\]"
    adj_hits = len(re.findall(adj_cite_pat, text))
    if adj_hits:
        issues.append(
            NativeQualityIssue(
                code="draft_adjacent_citation_blocks",
                message=(
                    f"Draft contains adjacent citation blocks ({adj_hits}×, e.g., "
                    "`[@a] [@b]`); merge same-sentence citations into a single "
                    "citation block."
                ),
            )
        )
    dup_in_block = 0
    for m in re.finditer(r"\[@([^\]]+)\]", text):
        keys = [k for k in re.findall(r"[A-Za-z0-9:_-]+", (m.group(1) or "")) if k]
        if keys and len(set(keys)) != len(keys):
            dup_in_block += 1
    if dup_in_block:
        issues.append(
            NativeQualityIssue(
                code="draft_duplicate_keys_in_citation_block",
                message=(
                    f"Draft contains citation blocks with duplicate keys "
                    f"({dup_in_block}×, e.g., `[@x; @x]`); deduplicate keys inside "
                    "each citation block."
                ),
            )
        )
    if profile == "arxiv-survey":
        h3_blocks = _sx_split_h3_blocks(text)
        floor = 0.30 if policy.draft_profile(workspace) in {"survey", "deep"} else 0.20
        low_ratio: list[str] = []
        for title, body in h3_blocks:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]
            cited = 0
            mid = 0
            for para in paras:
                if "[@" not in para:
                    continue
                cited += 1
                cites = list(re.finditer(r"\[@[^\]]+\]", para))
                if any(m.start() < max(0, len(para) - 45) for m in cites):
                    mid += 1
            if cited < 4:
                continue
            ratio = mid / max(1, cited)
            if ratio < floor:
                short = title[:48] + ("..." if len(title) > 48 else "")
                low_ratio.append(f"{short} ({mid}/{cited}={ratio:.0%})")
        if low_ratio:
            issues.append(
                NativeQualityIssue(
                    code="draft_low_mid_sentence_citation_ratio",
                    message=(
                        f"Some subsections have low mid-sentence citation ratio "
                        f"(<{int(floor * 100)}%): "
                        + "; ".join(low_ratio[:8])
                        + ". Move some citations into the claim sentences they "
                        "support (not only paragraph tails)."
                    ),
                )
            )
    open_lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip().lower().startswith(("open problems:", "开放问题："))
    ]
    if open_lines:
        counts: dict[str, int] = {}
        for ln in open_lines:
            counts[ln] = counts.get(ln, 0) + 1
        top_line, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_count >= 5 and top_count / len(open_lines) >= 0.6:
            issues.append(
                NativeQualityIssue(
                    code="draft_repeated_open_problems",
                    message=(
                        f"Open-problems text repeats across sections (e.g., "
                        f"`{top_line}`); make it subsection-specific and concrete."
                    ),
                )
            )
    take_lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip().lower().startswith(("takeaways:", "takeaway:", "小结："))
    ]
    if take_lines:
        counts = {}
        for ln in take_lines:
            counts[ln] = counts.get(ln, 0) + 1
        top_line, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_count >= 5 and top_count / len(take_lines) >= 0.6:
            issues.append(
                NativeQualityIssue(
                    code="draft_repeated_takeaways",
                    message=(
                        f"Takeaways text repeats across sections (e.g., `{top_line}`); "
                        "rewrite to reflect subsection-specific synthesis."
                    ),
                )
            )
    template_phrases = [
        "Representative works:",
        "Discussion: 当前证据主要来自标题/摘要级信息",
        "本节围绕",
        "本小节围绕",
        "本小节聚焦",
        "从可复核的对比维度出发",
        "总结主要趋势与挑战",
        "对比维度（按已批准的 outline）包括：",
        "小结：综合这些工作，主要权衡通常落在以下维度：",
        "Takeaways: 综合这些工作，主要权衡通常落在以下维度：",
        "是 LLM 智能体系统中的一个关键维度",
        "We use the following working claim to guide synthesis:",
        "Across representative works, the dominant trade-offs",
        "This section summarizes the main design patterns and empirical lessons",
        "is best understood by comparing how adjacent designs trade off competing requirements",
        "The subsection therefore asks",
        "That is why the subsection returns to",
        "What survives synthesis is a bounded conclusion",
        "Beyond the central comparison cards",
        "One useful contrast in",
        "One concrete anchor in",
        "A recurring limitation is that",
    ]
    template_hits = sum(text.count(p) for p in template_phrases)
    if template_hits >= 3:
        issues.append(
            NativeQualityIssue(
                code="draft_template_text",
                message=(
                    "Draft still contains repeated template boilerplate; rewrite into "
                    "paragraph-style synthesis grounded in notes/evidence."
                ),
            )
        )
    if profile == "arxiv-survey":
        paras_all = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        content_paras = 0
        uncited_paras = 0
        for para in paras_all:
            if para.startswith(("#", "|", "```")):
                continue
            if len(para) < 240:
                continue
            if "\n|" in para:
                continue
            content_paras += 1
            if "[@" not in para:
                uncited_paras += 1
        if content_paras and (uncited_paras / content_paras) > 0.25:
            issues.append(
                NativeQualityIssue(
                    code="draft_too_many_uncited_paragraphs",
                    message=(
                        f"Too many content paragraphs lack citations "
                        f"({uncited_paras}/{content_paras}); survey drafting should be "
                        "evidence-first with paragraph-level cites."
                    ),
                )
            )
    blocks = re.split(r"\n###\s+", text)
    subsection_blocks = blocks[1:] if len(blocks) > 1 else []
    if subsection_blocks:
        draft_profile = policy.draft_profile(workspace)
        min_h3_cites = policy.quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_unique_citations"),
            default={"course_paper": 4, "deep": 14}.get(draft_profile, 12),
        )
        min_h3_chars = policy.quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_chars"),
            default={"course_paper": 1600, "deep": 6000}.get(draft_profile, 5000),
        )
        no_cite = 0
        too_short = 0
        low_cite_density = 0
        for block in subsection_blocks:
            lines = [ln for ln in block.splitlines() if ln.strip()]
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            body = re.sub(r"\[@[^\]]+\]", "", body)
            if len(body) < min_h3_chars:
                too_short += 1
            if "[@" not in block:
                no_cite += 1
            if profile == "arxiv-survey":
                cite_keys: set[str] = set()
                for m in re.finditer(r"\[@([^\]]+)\]", block):
                    inside = (m.group(1) or "").strip()
                    for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                        if k:
                            cite_keys.add(k)
                if len(cite_keys) < min_h3_cites:
                    low_cite_density += 1
        total = max(1, len(subsection_blocks))
        if no_cite / total >= 0.5:
            issues.append(
                NativeQualityIssue(
                    code="draft_sparse_citations",
                    message=(
                        "Many subsections have no citations; ensure each subsection "
                        "cites representative works from `citations/ref.bib`."
                    ),
                )
            )
        if too_short / total >= 0.5:
            issues.append(
                NativeQualityIssue(
                    code="draft_sections_too_short",
                    message=(
                        f"Many subsections are very short (<~{min_h3_chars} chars sans "
                        "citations); expand with concrete comparisons, evaluation "
                        "anchors, synthesis paragraphs, and limitations from evidence "
                        "packs/paper notes."
                    ),
                )
            )
        if profile == "arxiv-survey" and low_cite_density / total >= 0.2:
            issues.append(
                NativeQualityIssue(
                    code="draft_sparse_subsection_citations",
                    message=(
                        f"Many subsections have <{min_h3_cites} unique citations "
                        f"({low_cite_density}/{len(subsection_blocks)}); increase "
                        "section-level evidence binding and cite density."
                    ),
                )
            )

        def _cite_keys(block_text: str) -> set[str]:
            keys: set[str] = set()
            for m in re.finditer(r"\[@([^\]]+)\]", block_text):
                inside = (m.group(1) or "").strip()
                for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                    if k:
                        keys.add(k)
            return keys

        def _has_multi_cite_paragraph(block_text: str) -> bool:
            for para in re.split(r"\n\s*\n", block_text):
                para = para.strip()
                if not para:
                    continue
                pkeys = _cite_keys(para)
                if len(pkeys) >= 2:
                    return True
            return False

        synth_total = 0
        synth_missing = 0
        for block in subsection_blocks:
            if len(_cite_keys(block)) < 3:
                continue
            synth_total += 1
            if not _has_multi_cite_paragraph(block):
                synth_missing += 1
        if synth_total and synth_missing / synth_total >= 0.4:
            issues.append(
                NativeQualityIssue(
                    code="draft_low_cross_paper_synthesis",
                    message=(
                        "Many cite-rich subsections still read like per-paper "
                        "summaries; ensure each subsection has at least one paragraph "
                        "that compares multiple works (>=2 citations in the same "
                        "paragraph)."
                        f" Missing synthesis in {synth_missing}/{synth_total} "
                        "subsections."
                    ),
                )
            )
    if not re.search(r"(?im)^##\s+(introduction|引言)\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_missing_introduction",
                message="Draft is missing an `Introduction/引言` section.",
            )
        )
    if not re.search(r"(?im)^##\s+(conclusion|结论)\b", text):
        issues.append(
            NativeQualityIssue(
                code="draft_missing_conclusion",
                message="Draft is missing a `Conclusion/结论` section.",
            )
        )
    if not re.search(
        r"(?im)^##\s+(discussion|discussion and future work|discussion & future work|讨论|讨论与未来工作|讨论与未来方向)\b",
        text,
    ):
        issues.append(
            NativeQualityIssue(
                code="draft_missing_discussion",
                message=(
                    "Draft is missing a `Discussion` (or `Discussion & Future Work`) "
                    "section."
                ),
            )
        )
    intro = _sx_extract_section_body(text, heading_re=r"(?im)^##\s+(introduction|引言)\b")
    if intro is not None:
        words = len(re.findall(r"\b\w+\b", intro))
        if words and words < 180:
            issues.append(
                NativeQualityIssue(
                    code="draft_intro_too_short",
                    message=(
                        "Introduction looks too short (<~180 words); expand "
                        "motivation, scope, contributions, and positioning vs. "
                        "related work."
                    ),
                )
            )
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    para_norm_counts: dict[str, int] = {}
    para_example: dict[str, str] = {}
    for para in paras:
        if para.startswith("|") or "\n|" in para or para.startswith("```"):
            continue
        if len(para) < 220:
            continue
        norm = re.sub(r"\[@[^\]]+\]", "", para)
        norm = re.sub(r"\s+", " ", norm).strip().lower()
        if len(norm) < 180:
            continue
        para_norm_counts[norm] = para_norm_counts.get(norm, 0) + 1
        para_example.setdefault(norm, para)
    if para_norm_counts:
        top_norm, top_count = sorted(
            para_norm_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[0]
        if top_count >= 3:
            example = para_example.get(top_norm, "")[:140].replace("\n", " ").strip()
            issues.append(
                NativeQualityIssue(
                    code="draft_repeated_paragraphs",
                    message=(
                        f"Draft contains repeated long paragraphs (e.g., "
                        f"`{example}...`); rewrite to be subsection-specific and avoid "
                        "copy-paste boilerplate."
                    ),
                )
            )
    repeated = _sx_repeated_template_text(text=text, min_len=48, min_repeats=10)
    if repeated is not None:
        example, count = repeated
        issues.append(
            NativeQualityIssue(
                code="draft_repeated_lines",
                message=(
                    f"Draft contains repeated template-like lines ({count}×), e.g., "
                    f"`{example}...`; rewrite to be section-specific."
                ),
            )
        )
    repeated_sent = _sx_repeated_sentences(text=text, min_len=90, min_repeats=6)
    if repeated_sent is not None:
        example, count = repeated_sent
        issues.append(
            NativeQualityIssue(
                code="draft_repeated_sentences",
                message=(
                    f"Draft contains repeated boilerplate sentences ({count}×), e.g., "
                    f"`{example}`; remove template repetition and make each "
                    "subsection's thesis/comparisons specific."
                ),
            )
        )
    return issues


def _check_citation_anchoring(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_citation_anchoring``."""

    draft_rel = outputs[0] if outputs else "output/DRAFT.md"
    baseline_rel = "output/citation_anchors.prepolish.jsonl"
    baseline_path = workspace / baseline_rel
    draft_path = workspace / draft_rel
    if not baseline_path.exists():
        return []
    if not draft_path.exists():
        return []
    baseline_records = [r for r in _read_jsonl(baseline_path) if isinstance(r, dict)]
    baseline_map: dict[str, set[str]] = {}
    for rec in baseline_records:
        if str(rec.get("kind") or "").strip() != "h3":
            continue
        title = str(rec.get("title") or "").strip()
        keys = rec.get("cite_keys") or []
        if not title or not isinstance(keys, list):
            continue
        baseline_map[title] = set(str(k).strip() for k in keys if str(k).strip())
    if not baseline_map:
        return [
            NativeQualityIssue(
                code="citation_anchors_empty",
                message=(
                    f"`{baseline_rel}` exists but has no H3 citation anchors; delete "
                    "it and rerun `draft-polisher` to regenerate a baseline."
                ),
            )
        ]
    draft_text = draft_path.read_text(encoding="utf-8", errors="ignore")
    current_map = _sw_draft_h3_cite_sets(draft_text)
    issues: list[NativeQualityIssue] = []
    for title, before_keys in baseline_map.items():
        after_keys = current_map.get(title)
        if after_keys is None:
            issues.append(
                NativeQualityIssue(
                    code="citation_anchor_missing_h3",
                    message=(
                        f"After polishing, H3 heading `{title}` is missing or renamed; "
                        f"keep headings stable (or delete `{baseline_rel}` to reset the "
                        "baseline)."
                    ),
                )
            )
            continue
        if before_keys != after_keys:
            removed = sorted([k for k in before_keys if k not in after_keys])
            added = sorted([k for k in after_keys if k not in before_keys])
            sample_removed = ", ".join(removed[:6])
            sample_added = ", ".join(added[:6])
            issues.append(
                NativeQualityIssue(
                    code="citation_anchoring_drift",
                    message=(
                        f"Citation anchoring drift in H3 `{title}`: "
                        f"removed {{{sample_removed}}}, added {{{sample_added}}}. "
                        f"Polishing must not move citations across subsections; keep "
                        f"cite keys in the same H3, or delete `{baseline_rel}` to "
                        "intentionally reset."
                    ).rstrip(),
                )
            )
    return issues


def _check_global_review(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_global_review``."""

    report_rel = outputs[0] if outputs else "output/GLOBAL_REVIEW.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_global_review", message=f"`{report_rel}` does not exist."
            )
        ]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    issues: list[NativeQualityIssue] = []
    if _has_placeholder_markers(text):
        issues.append(
            NativeQualityIssue(
                code="global_review_placeholders",
                message=(
                    "Global review still contains placeholder markers "
                    "(TODO/TBD/FIXME/(placeholder)); fill the review and set "
                    "`Status: PASS`."
                ),
            )
        )
    if not re.search(r"(?im)^-\s*Status:\s*(PASS|OK)\b", text):
        issues.append(
            NativeQualityIssue(
                code="global_review_status_missing",
                message=(
                    "Global review should include a bullet like `- Status: PASS` once "
                    "issues are addressed."
                ),
            )
        )
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    if len(bullets) < 12:
        issues.append(
            NativeQualityIssue(
                code="global_review_too_short",
                message=(
                    "Global review looks too short; include top issues + glossary + "
                    "ready-for-LaTeX checklist (>=12 bullets)."
                ),
            )
        )
    required = ["A.", "B.", "C.", "D.", "E."]
    missing = [k for k in required if not re.search(rf"(?m)^##\s+{re.escape(k)}", text)]
    if missing:
        issues.append(
            NativeQualityIssue(
                code="global_review_missing_audit_sections",
                message=(
                    f"Global review is missing required audit sections: "
                    f"{', '.join(missing)} (add A–E to cover input integrity, "
                    "narrative, scope, citations, and tables)."
                ),
            )
        )
    issues.extend(_sw_check_draft(workspace, ["output/DRAFT.md"], policy))
    return issues


def _check_sections_manifest_index(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_sections_manifest_index``."""

    out_rel = outputs[0] if outputs else "sections/sections_manifest.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_sections_manifest",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    records = _read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [
            NativeQualityIssue(
                code="empty_sections_manifest",
                message=f"`{out_rel}` is empty or has no JSON objects.",
            )
        ]
    outline_path = workspace / "outline" / "outline.yml"
    outline = _st_load_yaml(outline_path) if outline_path.exists() else []

    def _slug_unit_id(unit_id: str) -> str:
        raw = str(unit_id or "").strip()
        out: list[str] = []
        for ch in raw:
            out.append(ch if ch.isalnum() else "_")
        safe = "".join(out).strip("_")
        return f"S{safe}" if safe else "S"

    expected: set[str] = {
        "sections/abstract.md",
        "sections/discussion.md",
        "sections/conclusion.md",
    }
    expected_h3: set[str] = set()
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            subs = sec.get("subsections") or []
            if isinstance(subs, list) and subs:
                if sec_id:
                    expected.add(f"sections/{_slug_unit_id(sec_id)}_lead.md")
                for sub in subs:
                    if not isinstance(sub, dict):
                        continue
                    sub_id = str(sub.get("id") or "").strip()
                    if sub_id:
                        relpath = f"sections/{_slug_unit_id(sub_id)}.md"
                        expected.add(relpath)
                        expected_h3.add(relpath)
            else:
                if sec_id:
                    expected.add(f"sections/{_slug_unit_id(sec_id)}.md")
    by_path: dict[str, dict[str, Any]] = {}
    dupes = 0
    for rec in items:
        rel = str(rec.get("path") or "").strip()
        if not rel:
            continue
        if rel in by_path:
            dupes += 1
        by_path[rel] = rec
    issues: list[NativeQualityIssue] = []
    if dupes:
        issues.append(
            NativeQualityIssue(
                code="sections_manifest_duplicate_paths",
                message=f"`{out_rel}` contains duplicate `path` entries ({dupes}).",
            )
        )
    missing = sorted([p for p in expected if p not in by_path])
    if missing:
        sample = ", ".join(missing[:8])
        suffix = "..." if len(missing) > 8 else ""
        issues.append(
            NativeQualityIssue(
                code="sections_manifest_missing_expected_paths",
                message=(
                    f"`{out_rel}` is missing some expected entries (e.g., {sample}"
                    f"{suffix}). Regenerate the manifest from the current outline."
                ),
            )
        )
    missing_files: list[str] = []
    for rel in sorted(expected):
        p = workspace / rel
        if not p.exists() or p.stat().st_size <= 0:
            missing_files.append(rel)
    if missing_files:
        sample = ", ".join(missing_files[:8])
        suffix = "..." if len(missing_files) > 8 else ""
        issues.append(
            NativeQualityIssue(
                code="sections_missing_files",
                message=(
                    f"Missing per-section files under `sections/` (e.g., {sample}"
                    f"{suffix})."
                ),
            )
        )
    marker_rel = next(
        (item for item in outputs if item.endswith(".refined.ok")),
        "sections/h3_bodies.refined.ok",
    )
    if (workspace / marker_rel).exists():
        issues.extend(
            _as_native_issues(
                policy.template_residue_subsection_issues(
                    workspace, sorted(expected_h3)
                )
            )
        )
    return issues




def _as_native_issues(issues: list) -> list[NativeQualityIssue]:
    """Adapt Port-returned issue objects (legacy QualityIssue) to NativeQualityIssue.

    The template-residue evaluators run behind the WorkspacePolicyPort and return
    ``tooling`` ``QualityIssue`` objects (code + message).  This normalizes them to
    the native issue type so acceptance sees a uniform shape; codes and messages
    are preserved byte-for-byte.
    """

    out: list[NativeQualityIssue] = []
    for issue in issues:
        out.append(
            NativeQualityIssue(
                code=str(getattr(issue, "code", "") or ""),
                message=str(getattr(issue, "message", "") or ""),
            )
        )
    return out


def _check_sections_manifest(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of ``survey_writing.check_sections_manifest`` (prose-writer)."""

    out_rel = outputs[0] if outputs else "sections/sections_manifest.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_sections_manifest",
                message=f"`{out_rel}` does not exist.",
            )
        ]
    records = _read_jsonl(path)
    if not records:
        return [
            NativeQualityIssue(
                code="empty_sections_manifest", message=f"`{out_rel}` is empty."
            )
        ]
    base_dir = Path(out_rel).parent

    def _slug_unit_id(unit_id: str) -> str:
        raw = str(unit_id or "").strip()
        out: list[str] = []
        for ch in raw:
            if ch.isalnum():
                out.append(ch)
            else:
                out.append("_")
        safe = "".join(out).strip("_")
        return f"S{safe}" if safe else "S"

    outline_path = workspace / "outline" / "outline.yml"
    outline = _st_load_yaml(outline_path) if outline_path.exists() else []
    expected_units: list[dict[str, str]] = []
    expected_leads: list[dict[str, str]] = []
    sub_to_section: dict[str, str] = {}
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            subs = sec.get("subsections") or []
            if subs and isinstance(subs, list):
                if sec_id and sec_title:
                    expected_leads.append(
                        {"kind": "h2_lead", "id": sec_id, "title": sec_title}
                    )
                for sub in subs:
                    if not isinstance(sub, dict):
                        continue
                    sub_id = str(sub.get("id") or "").strip()
                    sub_title = str(sub.get("title") or "").strip()
                    if sub_id and sub_title:
                        expected_units.append(
                            {
                                "kind": "h3",
                                "id": sub_id,
                                "title": sub_title,
                                "section_id": sec_id,
                                "section_title": sec_title,
                            }
                        )
                        if sec_id:
                            sub_to_section[sub_id] = sec_id
            else:
                if sec_id and sec_title:
                    expected_units.append(
                        {"kind": "h2", "id": sec_id, "title": sec_title, "section_title": sec_title}
                    )
    h2_title_by_id: dict[str, str] = {}
    ordered_h2_ids: list[str] = []
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            if sec_id and sec_title:
                h2_title_by_id[sec_id] = sec_title
                ordered_h2_ids.append(sec_id)
    required_globals = [
        ("abstract", "Abstract", base_dir / "abstract.md"),
        ("discussion", "Discussion", base_dir / "discussion.md"),
        ("conclusion", "Conclusion", base_dir / "conclusion.md"),
    ]
    optional_globals: list[tuple[str, str, Path]] = []
    expected_files: list[tuple[str, str, str]] = []
    for gid, title, rel in required_globals:
        expected_files.append(("global", gid, rel.as_posix()))
    for gid, title, rel in optional_globals:
        expected_files.append(("global_optional", gid, rel.as_posix()))
    for u in expected_leads:
        rel = (base_dir / f"{_slug_unit_id(u['id'])}_lead.md").as_posix()
        expected_files.append((u["kind"], u["id"], rel))
    for u in expected_units:
        rel = (base_dir / f"{_slug_unit_id(u['id'])}.md").as_posix()
        expected_files.append((u["kind"], u["id"], rel))

    issues: list[NativeQualityIssue] = []
    missing_required: list[str] = []
    for kind, uid, rel in expected_files:
        p = workspace / rel
        if kind == "global_optional":
            continue
        if not p.exists() or p.stat().st_size <= 0:
            missing_required.append(rel)
    if missing_required:
        sample = ", ".join(missing_required[:8])
        suffix = "..." if len(missing_required) > 8 else ""
        issues.append(
            NativeQualityIssue(
                code="sections_missing_files",
                message=(
                    f"Missing per-section files under `{base_dir.as_posix()}` "
                    f"(e.g., {sample}{suffix})."
                ),
            )
        )
    issues.extend(
        _as_native_issues(
            policy.template_residue_subsection_issues(
                workspace, [rel for kind, _, rel in expected_files if kind == "h3"]
            )
        )
    )
    bib_path = workspace / "citations" / "ref.bib"
    bib_keys: set[str] = set()
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))
    bindings_path = workspace / "outline" / "evidence_bindings.jsonl"
    mapped_by_sub: dict[str, set[str]] = {}
    if bindings_path.exists():
        for rec in _read_jsonl(bindings_path):
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            mapped = rec.get("mapped_bibkeys") or []
            if sid and isinstance(mapped, list):
                mapped_by_sub[sid] = set(str(x).strip() for x in mapped if str(x).strip())
    else:
        issues.append(
            NativeQualityIssue(
                code="missing_evidence_bindings",
                message=(
                    "Missing `outline/evidence_bindings.jsonl`; run `evidence-binder` "
                    "before subsection writing so citations can be scoped per H3."
                ),
            )
        )
    mapped_by_section: dict[str, set[str]] = {}
    for sub_id, sec_id in sub_to_section.items():
        allowed = mapped_by_sub.get(sub_id)
        if not allowed or not sec_id:
            continue
        bucket = mapped_by_section.setdefault(sec_id, set())
        bucket.update(allowed)
    mapped_counts: dict[str, int] = {}
    for keys in mapped_by_sub.values():
        for k in keys:
            mapped_counts[k] = mapped_counts.get(k, 0) + 1
    global_threshold = policy.global_citation_min_subsections(workspace)
    mapped_global = {k for k, n in mapped_counts.items() if n >= global_threshold}

    def _extract_keys(text: str) -> set[str]:
        keys: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", text):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    keys.add(k)
        return keys

    numeric_available: set[str] = set()
    packs_path = workspace / "outline" / "evidence_drafts.jsonl"
    if packs_path.exists() and packs_path.stat().st_size > 0:
        try:
            for rec in _read_jsonl(packs_path):
                if not isinstance(rec, dict):
                    continue
                sid = str(rec.get("sub_id") or "").strip()
                if not sid:
                    continue
                blob_parts: list[str] = []
                for sn in rec.get("evidence_snippets") or []:
                    if isinstance(sn, dict):
                        blob_parts.append(str(sn.get("text") or ""))
                for comp in rec.get("concrete_comparisons") or []:
                    if not isinstance(comp, dict):
                        continue
                    for hl in comp.get("A_highlights") or []:
                        if isinstance(hl, dict):
                            blob_parts.append(str(hl.get("excerpt") or ""))
                    for hl in comp.get("B_highlights") or []:
                        if isinstance(hl, dict):
                            blob_parts.append(str(hl.get("excerpt") or ""))
                blob = " ".join([p for p in blob_parts if p]).strip()
                if blob and re.search(r"\d", blob):
                    numeric_available.add(sid)
        except Exception:
            numeric_available = set()

    for kind, uid, rel in expected_files:
        p = workspace / rel
        if not p.exists() or p.stat().st_size <= 0:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if _has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
            issues.append(
                NativeQualityIssue(
                    code="sections_contains_placeholders",
                    message=(
                        f"`{rel}` contains placeholders/ellipsis (`TODO`/`…`/`...`); "
                        "rewrite this unit into complete, checkable prose."
                    ),
                )
            )
            break
        if re.search(
            r"(?im)^(?:intent|rq|question|scope cues|evidence needs|expected cites|concrete comparisons|evaluation anchors|comparison axes)\s*[:：]",
            text,
        ):
            issues.append(
                NativeQualityIssue(
                    code="sections_contains_outline_meta",
                    message=(
                        f"`{rel}` contains outline/brief meta markers "
                        "(Intent/RQ/Evidence needs/etc.). These belong in "
                        "`outline/outline.yml` or briefs, not in final prose; rewrite "
                        "to remove meta prefixes."
                    ),
                )
            )
            break
        if (
            re.search(r"(?i)\babstracts are treated as verification targets\b", text)
            or re.search(r"(?i)\bthe main axes we track are\b", text)
            or re.search(r"(?i)\bevidence\s+packs?\b", text)
        ):
            issues.append(
                NativeQualityIssue(
                    code="sections_contains_pipeline_voice",
                    message=(
                        f"`{rel}` contains pipeline-style boilerplate; rewrite to be "
                        "subsection-specific and avoid repeated template sentences."
                    ),
                )
            )
        if re.search(r"(?m)^\\[@[^\\]]+\\]\\s*$", text):
            issues.append(
                NativeQualityIssue(
                    code="sections_citation_dump_line",
                    message=(
                        f"`{rel}` contains a stand-alone citation line (e.g., a line "
                        "that is only `[@...]`). Embed citations into the sentence "
                        "they support (system name + claim), not as end-of-paragraph "
                        "tags."
                    ),
                )
            )
            break
        if kind == "h3":
            for ln in text.splitlines():
                if ln.strip().startswith("#"):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_has_headings",
                            message=(
                                f"`{rel}` should be body-only (no `#`/`##`/`###` "
                                "headings); headings are added by `section-merger`."
                            ),
                        )
                    )
                    break
            cite_keys = _extract_keys(text)
            profile = policy.pipeline_profile_name(workspace)
            draft_profile = policy.draft_profile(workspace)
            if profile == "arxiv-survey":
                min_cites = (
                    4
                    if draft_profile == "course_paper"
                    else (8 if draft_profile == "deep" else 6)
                )
                if len(cite_keys) < min_cites:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_sparse_citations",
                            message=(
                                f"`{rel}` has <{min_cites} unique citations "
                                f"({len(cite_keys)}); each H3 should be evidence-first "
                                "for survey-quality runs."
                            ),
                        )
                    )
            if profile == "arxiv-survey":
                if draft_profile == "course_paper":
                    min_paragraphs = 5
                    min_chars = 1600
                elif draft_profile == "deep":
                    min_paragraphs = 9
                    min_chars = 4300
                else:
                    min_paragraphs = 8
                    min_chars = 3300
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
                first_para = paragraphs[0] if paragraphs else ""
                first_no_cites = re.sub(r"\[@[^\]]+\]", "", first_para)
                first_no_cites = re.sub(r"\s+", " ", first_no_cites).strip()
                if re.search(
                    r"(?i)\b(?:this\s+(?:section|subsection)\s+(?:surveys|reviews|discusses|covers|presents|introduces|outlines|summarizes|describes|argues|shows|highlights|demonstrates|contends)|in\s+this\s+(?:section|subsection))\b",
                    first_no_cites,
                ):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_narration_template_opener",
                            message=(
                                f"`{rel}` starts with narration-style template phrasing "
                                "(e.g., 'This subsection ...'). Rewrite paragraph 1 as a "
                                "content claim (tension/decision/lens) and end with the "
                                "thesis."
                            ),
                        )
                    )
                if re.search(
                    r"(?i)\b(?:next,\s+we\s+move\s+from|we\s+now\s+(?:turn|move)\s+to|in\s+the\s+next\s+(?:section|subsection))\b",
                    text,
                ):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_slide_narration",
                            message=(
                                f"`{rel}` contains slide-like navigation narration "
                                "(e.g., 'We now turn to ...'). Rewrite as argument "
                                "bridges (no navigation commentary)."
                            ),
                        )
                    )
                if re.search(
                    r"(?i)\b(?:abstract(?:-|\s+)(?:only|level)\s+evidence|title(?:-|\s+)only\s+evidence|claims?\s+remain\s+provisional\s+under\s+abstract(?:-|\s+)(?:only|level)\s+evidence)\b",
                    text,
                ):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_evidence_policy_disclaimer_spam",
                            message=(
                                f"`{rel}` repeats evidence-policy/disclaimer phrasing "
                                "(abstract/title-only/provisional claims). Keep evidence "
                                "policy once in front matter (Intro/Related Work) and "
                                "avoid repeating it in H3 bodies."
                            ),
                        )
                    )
                if re.search(r"(?i)\bsurvey\s+(?:synthesis|comparisons?)\s+should\b", text):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_meta_survey_guidance",
                            message=(
                                f"`{rel}` contains meta survey-guidance phrasing "
                                "('survey ... should ...'). Rewrite as literature-facing "
                                "observations grounded in cited work (no new facts)."
                            ),
                        )
                    )
                stock_template_patterns = [
                    r"(?i)\bread together,\s+.+?\bdiverge less on headline performance\b",
                    r"(?i)\bwhat matters operationally in\b",
                    r"(?i)\bthe comparison only becomes actionable after\b",
                    r"(?i)\bthe relevant implementation split in\b",
                    r"(?i)\bthe evaluation story for\b",
                    r"(?i)\bby contrast, another strand in\b",
                    r"(?i)\bthe subsection-level contrast between\b",
                    r"(?i)\bacross those neighboring studies,\b",
                    r"(?i)\bthose mapped papers still tie\b",
                    r"(?i)\bthese gains remain provisional because\b",
                ]
                stock_template_hits = sum(
                    len(re.findall(pattern, text)) for pattern in stock_template_patterns
                )
                if stock_template_hits >= 5:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_template_density",
                            message=(
                                f"`{rel}` still contains too many stock "
                                f"subsection-writer stems ({stock_template_hits} hits). "
                                "Reduce scaffold phrasing and replace repeated bridge "
                                "sentences with section-specific synthesis."
                            ),
                        )
                    )
                if len(paragraphs) < min_paragraphs:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_too_few_paragraphs",
                            message=(
                                f"`{rel}` has too few paragraphs ({len(paragraphs)}); "
                                f"aim for {min_paragraphs}–{max(min_paragraphs, 12)} "
                                "paragraphs per H3 for this draft profile."
                            ),
                        )
                    )
                dump_paras = 0
                for para in paragraphs:
                    m = re.search(r"\[@([^\]]+)\]\s*$", para)
                    if not m:
                        continue
                    keys_in_tail = set(re.findall(r"[A-Za-z0-9:_-]+", m.group(1) or ""))
                    if len(keys_in_tail) < 3:
                        continue
                    if para.count("[@") != 1:
                        continue
                    dump_paras += 1
                if dump_paras:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_citation_dump_paragraphs",
                            message=(
                                f"`{rel}` has {dump_paras} paragraph(s) where citations "
                                "appear only as a trailing dump (e.g., ending with "
                                "`[@a; @b; @c]`). Embed citations into the sentence they "
                                "support (system name + claim), rather than tagging the "
                                "paragraph at the end."
                            ),
                        )
                    )
                content = re.sub(r"\[@[^\]]+\]", "", text)
                content = re.sub(r"\s+", " ", content).strip()
                if len(content) < min_chars:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_too_short",
                            message=(
                                f"`{rel}` looks too short ({len(content)} chars after "
                                f"removing citations; min={min_chars}). Expand with "
                                "concrete comparisons + evaluation details + synthesis + "
                                "limitations from the evidence pack."
                            ),
                        )
                    )
                has_multi_cite = any(len(_extract_keys(p)) >= 2 for p in paragraphs)
                if not has_multi_cite:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_no_multi_cite_paragraph",
                            message=(
                                f"`{rel}` has no paragraph with >=2 citations; add at "
                                "least one cross-paper synthesis paragraph (contrast A "
                                "vs B with multiple cites)."
                            ),
                        )
                    )
                contrast_re = r"(?i)\b(?:whereas|however|in\s+contrast|by\s+contrast|versus|vs\.)\b|相比|不同于|相较|对比|反之"
                eval_re = (
                    r"(?i)\b(?:benchmark|dataset|datasets|metric|metrics|evaluation|eval\.|protocol|human|ablation|"
                    r"latency|cost|budget|token|tokens|throughput|compute)\b|评测|基准|数据集|指标|协议|人工|实验|成本|预算|延迟"
                )
                limitation_re = r"(?i)\b(?:limitations?|limited|provisional|unclear|sensitive|caveat|downside|failure|risk|open\s+question|remains)\b|受限|尚不明确|缺乏|需要核验|局限|失败|风险|待验证"
                if uid in numeric_available:
                    has_cited_numeric = any(
                        re.search(r"\d", p) and "[@" in p for p in paragraphs
                    )
                    if not has_cited_numeric:
                        issues.append(
                            NativeQualityIssue(
                                code="sections_h3_missing_cited_numeric",
                                message=(
                                    f"`{rel}` has no cited numeric anchor (no digit in "
                                    "the same paragraph as a citation). Evidence packs "
                                    "for this subsection contain quantitative snippets; "
                                    "include at least one concrete number/result with "
                                    "citations."
                                ),
                            )
                        )
                if draft_profile == "course_paper":
                    min_contrast = 1
                    min_eval = 1
                    min_lim = 1
                    min_anchor_paras = 2
                elif draft_profile == "deep":
                    min_contrast = 3
                    min_eval = 3
                    min_lim = 2
                    min_anchor_paras = 4
                else:
                    min_contrast = 2
                    min_eval = 2
                    min_lim = 1
                    min_anchor_paras = 3
                contrast_n = len(re.findall(contrast_re, text))
                eval_n = len(re.findall(eval_re, text))
                lim_n = len(re.findall(limitation_re, text))
                if contrast_n < min_contrast:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_missing_contrast",
                            message=(
                                f"`{rel}` lacks explicit contrast phrasing (need >= "
                                f"{min_contrast}; found {contrast_n}). Use whereas/in "
                                "contrast/相比/不同于 to compare routes, not only "
                                "summarize."
                            ),
                        )
                    )
                if eval_n < min_eval:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_missing_eval_anchor",
                            message=(
                                f"`{rel}` lacks evaluation anchors (need >= {min_eval}; "
                                f"found {eval_n}). Include "
                                "benchmark/dataset/metric/protocol/评测 even at abstract "
                                "level."
                            ),
                        )
                    )
                if lim_n < min_lim:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_missing_limitation",
                            message=(
                                f"`{rel}` lacks limitation/provisional signals (need >= "
                                f"{min_lim}; found {lim_n}). Add explicit caveats "
                                "(limited/unclear/受限/待验证) to avoid overclaiming."
                            ),
                        )
                    )
                anchored_paras = 0
                for p in paragraphs:
                    if "[@" not in p:
                        continue
                    if re.search(r"\d", p) or re.search(eval_re, p) or re.search(limitation_re, p):
                        anchored_paras += 1
                if anchored_paras < min_anchor_paras:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h3_weak_anchor_density",
                            message=(
                                f"`{rel}` has too few anchored+cited paragraphs "
                                f"({anchored_paras}; min={min_anchor_paras}). Ensure "
                                "multiple paragraphs include citations along with "
                                "numbers, evaluation anchors, or concrete limitations."
                            ),
                        )
                    )
            if bib_keys:
                missing = sorted([k for k in cite_keys if k not in bib_keys])
                if missing:
                    sample = ", ".join(missing[:8])
                    suffix = "..." if len(missing) > 8 else ""
                    issues.append(
                        NativeQualityIssue(
                            code="sections_cites_missing_in_bib",
                            message=(
                                f"`{rel}` cites keys missing from `citations/ref.bib` "
                                f"(e.g., {sample}{suffix})."
                            ),
                        )
                    )
            if mapped_by_sub.get(uid):
                allowed_sub = mapped_by_sub.get(uid) or set()
                sec_id = sub_to_section.get(uid) or ""
                allowed_chapter = mapped_by_section.get(sec_id, set()) if sec_id else set()
                profile = policy.pipeline_profile_name(workspace)
                if profile == "arxiv-survey":
                    sub_specific = {k for k in cite_keys if k in allowed_sub}
                    min_sub_specific = 2 if draft_profile == "course_paper" else 3
                    if len(sub_specific) < min_sub_specific:
                        issues.append(
                            NativeQualityIssue(
                                code="sections_h3_sparse_subsection_cites",
                                message=(
                                    f"`{rel}` cites too few subsection-specific papers "
                                    f"({len(sub_specific)}). Chapter-scoped reuse is "
                                    "allowed, but each H3 should still ground itself in "
                                    f">={min_sub_specific} papers mapped to that "
                                    "subsection."
                                ),
                            )
                        )
                outside = sorted(
                    [
                        k
                        for k in cite_keys
                        if k not in allowed_sub
                        and k not in allowed_chapter
                        and k not in mapped_global
                    ]
                )
                if outside:
                    sample = ", ".join(outside[:8])
                    suffix = "..." if len(outside) > 8 else ""
                    issues.append(
                        NativeQualityIssue(
                            code="sections_cites_outside_mapping",
                            message=(
                                f"`{rel}` cites keys not mapped to subsection {uid}"
                                + (f" (or its chapter {sec_id})" if sec_id else "")
                                + f" (e.g., {sample}{suffix}); keep citations "
                                "subsection- or chapter-scoped (or fix "
                                "mapping/bindings)."
                            ),
                        )
                    )
        elif kind == "h2_lead":
            for ln in text.splitlines():
                if ln.strip().startswith("#"):
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h2_lead_has_headings",
                            message=(
                                f"`{rel}` should be body-only (no headings); it is "
                                "injected under the chapter H2 heading by "
                                "`section-merger`."
                            ),
                        )
                    )
                    break
            cite_keys = _extract_keys(text)
            if policy.pipeline_profile_name(workspace) == "arxiv-survey" and len(cite_keys) < 2:
                issues.append(
                    NativeQualityIssue(
                        code="sections_h2_lead_sparse_citations",
                        message=(
                            f"`{rel}` has too few citations ({len(cite_keys)}); chapter "
                            "leads should be grounded (>=2) to avoid generic glue text."
                        ),
                    )
                )
        elif kind == "global":
            if uid == "abstract" and not re.search(r"(?im)^##\s+(abstract|摘要)\b", text):
                issues.append(
                    NativeQualityIssue(
                        code="sections_abstract_missing_heading",
                        message=f"`{rel}` should start with `## Abstract` (or `## 摘要`).",
                    )
                )
            if uid == "discussion" and not re.search(
                r"(?im)^##\s+(discussion|discussion and future work|discussion & future work|讨论|讨论与未来工作|讨论与未来方向)\b",
                text,
            ):
                issues.append(
                    NativeQualityIssue(
                        code="sections_discussion_missing_heading",
                        message=f"`{rel}` should include an `## Discussion` heading (or equivalent).",
                    )
                )
            if uid == "conclusion" and not re.search(r"(?im)^##\s+(conclusion|结论)\b", text):
                issues.append(
                    NativeQualityIssue(
                        code="sections_conclusion_missing_heading",
                        message=f"`{rel}` should include an `## Conclusion/结论` heading.",
                    )
                )
        else:
            if kind == "h2":
                cite_keys = _extract_keys(text)
                if "[@" not in text:
                    issues.append(
                        NativeQualityIssue(
                            code="sections_h2_no_citations",
                            message=(
                                f"`{rel}` contains no citations; H2 sections should be "
                                "grounded with citations (or keep claims purely "
                                "structural)."
                            ),
                        )
                    )
                sec_title = h2_title_by_id.get(uid, "")
                t_norm = re.sub(r"\s+", " ", (sec_title or "")).strip().lower()
                is_intro = bool(
                    re.search(r"\b(introduction|intro)\b", t_norm)
                    or re.search(r"(引言|简介|概述)", sec_title)
                )
                is_related = bool(
                    re.search(
                        r"\b(related work|related works|literature review|prior work|related surveys)\b",
                        t_norm,
                    )
                    or re.search(r"(相关工作|文献综述)", sec_title)
                )
                if ordered_h2_ids:
                    if uid == ordered_h2_ids[0]:
                        is_intro = True
                    if len(ordered_h2_ids) > 1 and uid == ordered_h2_ids[1]:
                        is_related = True
                if policy.pipeline_profile_name(workspace) == "arxiv-survey" and (
                    is_intro or is_related
                ):
                    draft_profile = policy.draft_profile(workspace)
                    front_kind = "introduction" if is_intro else "related_work"
                    default_front = (
                        {"min_cites": 6, "min_paras": 3, "min_chars": 1200}
                        if draft_profile == "course_paper" and is_intro
                        else {"min_cites": 8, "min_paras": 3, "min_chars": 1400}
                        if draft_profile == "course_paper"
                        else {"min_cites": 40, "min_paras": 3, "min_chars": 3600}
                        if draft_profile == "deep" and is_intro
                        else {"min_cites": 55, "min_paras": 2, "min_chars": 4200}
                        if draft_profile == "deep"
                        else {"min_cites": 35, "min_paras": 2, "min_chars": 3200}
                        if is_intro
                        else {"min_cites": 50, "min_paras": 1, "min_chars": 3800}
                    )
                    min_cites = policy.quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_cites"),
                        default=default_front["min_cites"],
                    )
                    min_paras = policy.quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_paras"),
                        default=default_front["min_paras"],
                    )
                    min_chars = policy.quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_chars"),
                        default=default_front["min_chars"],
                    )
                    if is_intro:
                        front_fix = (
                            "Fix: expand motivation + scope boundary + one "
                            "evidence-policy paragraph + organization preview; keep "
                            "paper voice (avoid outline narration like 'This "
                            "subsection...')."
                        )
                    else:
                        front_fix = (
                            "Fix: expand positioning vs adjacent lines of work + survey "
                            "coverage + one evidence-policy paragraph + organization "
                            "preview; avoid a dedicated 'Prior Surveys' mini-section by "
                            "default; keep third-person academic voice (avoid "
                            "'this/current survey' deictic phrasing)."
                        )
                    content = re.sub(r"\[@[^\]]+\]", "", text)
                    content = re.sub(r"\s+", " ", content).strip()
                    paras = [
                        p.strip()
                        for p in re.split(r"\n\s*\n", re.sub(r"\[@[^\]]+\]", "", text))
                        if p.strip()
                    ]
                    long_paras = [
                        p
                        for p in paras
                        if len(re.sub(r"\s+", " ", p).strip()) >= 200
                        and not p.lstrip().startswith(("-", "*", "|", "```"))
                    ]
                    if len(set(cite_keys)) < min_cites:
                        code = (
                            "sections_intro_sparse_citations"
                            if is_intro
                            else "sections_related_work_sparse_citations"
                        )
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            NativeQualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) cites too few unique papers "
                                    f"({len(set(cite_keys))}; min={min_cites}). Increase "
                                    f"concrete, cite-grounded positioning and coverage. "
                                    f"{front_fix}"
                                ),
                            )
                        )
                    if len(content) < min_chars:
                        code = (
                            "sections_intro_too_short"
                            if is_intro
                            else "sections_related_work_too_short"
                        )
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            NativeQualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) looks too short ({len(content)} "
                                    f"chars after removing citations; min={min_chars}). "
                                    f"Expand motivation/scope/contributions and keep "
                                    f"claims citation-grounded. {front_fix}"
                                ),
                            )
                        )
                    if len(long_paras) < min_paras:
                        code = (
                            "sections_intro_too_few_paragraphs"
                            if is_intro
                            else "sections_related_work_too_few_paragraphs"
                        )
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            NativeQualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) has too few substantive "
                                    f"paragraphs ({len(long_paras)}; min={min_paras}). "
                                    f"Avoid bullet-only structure; write full paragraphs "
                                    f"with citations. {front_fix}"
                                ),
                            )
                        )
    return issues



def _check_draft_polisher(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native mirror of the ``draft-polisher`` wrapper (check_draft + anchoring)."""

    issues = _sw_check_draft(workspace, outputs, policy)
    issues.extend(_check_citation_anchoring(workspace, outputs, policy))
    return issues




# --- survey-planning family (policy-consuming) ------------------------------
#
# Native reimplementation of the entire tooling.quality_checks.survey_planning
# module (~2487 lines, 15 registered checks + helpers), completing native
# coverage of every quality-check module.  Policy reads (profile, draft_profile,
# per_subsection, quality_contract_int), structure-mode + section-first gates,
# and template-residue are read through the WorkspacePolicyPort (legacy-backed,
# byte-identical); survey-text helpers use the _sx_* mirrors; the small pure
# common helpers (tokenize / candidate_keywords / normalize_axis_label /
# subsection_brief_generic_axis_norms / read_tsv) are reimplemented as _sp_*.
# Every check reads YAML/JSONL/TSV/Markdown outputs and produces identical
# (code, message) lists to legacy, preserving issue ORDER and short-circuits.
#
# One deliberate fidelity note: check_evidence_bindings' legacy regex
# `r"^E-(P\\d+)-"` contains a LITERAL backslash-d (not the digit class); it is
# reproduced verbatim for byte-for-byte parity even though it never matches.


_SP_EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "be", "between", "beyond",
    "by", "for", "from", "in", "into", "is", "it", "new", "of", "on", "or",
    "our", "over", "that", "the", "this", "to", "toward", "towards", "under",
    "use", "using", "via", "we", "with", "within", "without",
}
_SP_GENERIC_PAPER_WORDS = {
    "analysis", "approach", "based", "benchmark", "benchmarks", "dataset",
    "datasets", "deep", "evaluating", "evaluation", "framework", "frameworks",
    "learning", "method", "methods", "model", "models", "network", "networks",
    "neural", "paper", "review", "studies", "study", "survey", "system",
    "systems", "towards", "tutorial", "using",
}


def _sp_tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if token]


def _sp_candidate_keywords(titles, *, top_k: int, min_freq: int) -> list[str]:
    freq: dict[str, int] = {}
    for title in titles:
        for token in _sp_tokenize(title):
            if token in _SP_EN_STOPWORDS or token in _SP_GENERIC_PAPER_WORDS:
                continue
            if len(token) < 3:
                continue
            freq[token] = freq.get(token, 0) + 1
    candidates = [
        t for t, c in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])) if c >= min_freq
    ]
    return candidates[:top_k]


def _sp_normalize_axis_label(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip().lower())
    text = text.rstrip(" .;:，；。")
    text = re.sub(r"\s*/\s*", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _sp_subsection_brief_generic_axis_norms() -> set[str]:
    axes = {
        "core mechanism and system architecture",
        "training and data setup",
        "evaluation protocol",
        "evaluation protocol (benchmarks / metrics / human)",
        "evaluation protocol (datasets / metrics / human)",
        "evaluation protocol (datasets, metrics, human evaluation)",
        "compute and efficiency",
        "compute and latency constraints",
        "efficiency and compute",
        "tool interface contract (schemas / protocols)",
        "tool selection / routing policy",
        "sandboxing / permissions / observability",
        "failure modes and limitations",
    }
    return {_sp_normalize_axis_label(axis) for axis in axes}


def _sp_read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _sp_iter_taxonomy_nodes(items) -> "Any":
    for item in items:
        if not isinstance(item, dict):
            continue
        yield item
        children = item.get("children") or []
        if isinstance(children, list):
            yield from _sp_iter_taxonomy_nodes(children)


def _check_sp_taxonomy(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/taxonomy.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if _has_placeholder_markers(raw):
            return [
                NativeQualityIssue(
                    code="taxonomy_scaffold",
                    message="Taxonomy still contains placeholder/TODO text; rewrite node names/descriptions and remove TODOs.",
                )
            ]
    data = _st_load_yaml(path) if path.exists() else None
    if not isinstance(data, list) or not data:
        return [
            NativeQualityIssue(
                code="invalid_taxonomy",
                message=f"`{out_rel}` is missing or not a YAML list.",
            )
        ]
    nodes = list(_sp_iter_taxonomy_nodes(data))
    if not any(node.get("children") for node in nodes if isinstance(node, dict)):
        return [
            NativeQualityIssue(
                code="taxonomy_depth",
                message="Taxonomy has no `children` (needs ≥2 levels).",
            )
        ]
    template_desc = 0
    template_child_names = 0
    total_desc = 0
    total_child_names = 0
    desc_values: list[str] = []
    child_name_templates = {"Overview", "Representative Approaches", "Benchmarks", "Open Problems"}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        desc = str(node.get("description") or "").strip()
        if desc:
            total_desc += 1
            desc_values.append(desc)
            if desc.startswith(
                (
                    "Papers and ideas centered on '",
                    "Key aspects of '",
                    "Cluster capturing work where '",
                    "Subtopic under '",
                )
            ):
                template_desc += 1
        name = str(node.get("name") or "").strip()
        if name:
            total_child_names += 1
            if name in child_name_templates:
                template_child_names += 1
    issues: list[NativeQualityIssue] = []
    if total_desc and template_desc / total_desc >= 0.6:
        issues.append(
            NativeQualityIssue(
                code="taxonomy_template_descriptions",
                message="Most taxonomy descriptions look auto-templated (keyword-based); rewrite with domain-meaningful categories.",
            )
        )
    if total_child_names and template_child_names / total_child_names >= 0.6:
        issues.append(
            NativeQualityIssue(
                code="taxonomy_template_children",
                message="Many taxonomy node names look like generic placeholders (Overview/Benchmarks/Open Problems); rename to content-based subtopics.",
            )
        )
    short, denom = _sx_short_description_counts(desc_values, min_chars=32)
    if denom and short / denom >= 0.6:
        issues.append(
            NativeQualityIssue(
                code="taxonomy_short_descriptions",
                message="Many taxonomy node descriptions are very short; expand descriptions with concrete scope cues and representative works.",
            )
        )
    core_path = workspace / "papers" / "core_set.csv"
    if core_path.exists():
        try:
            with core_path.open("r", encoding="utf-8", newline="") as handle:
                titles = [
                    str(row.get("title") or "").strip()
                    for row in csv.DictReader(handle)
                    if str(row.get("title") or "").strip()
                ]
        except Exception:
            titles = []
        core_topics = _sp_candidate_keywords(titles, top_k=6, min_freq=max(2, len(titles) // 12))
        taxonomy_tokens = set(
            _sp_tokenize(
                " ".join(
                    f"{str(node.get('name') or '')} {str(node.get('description') or '')}"
                    for node in nodes
                    if isinstance(node, dict)
                )
            )
        )
        required_overlap = min(2, len(core_topics))
        overlap = [topic for topic in core_topics if topic in taxonomy_tokens]
        if required_overlap and len(overlap) < required_overlap:
            issues.append(
                NativeQualityIssue(
                    code="taxonomy_domain_drift",
                    message=(
                        "Taxonomy does not reflect the core-set vocabulary: "
                        f"expected at least {required_overlap} of {core_topics}, found {overlap}. "
                        "Rebuild from the current GOAL/queries/core set; do not reuse an unrelated domain pack."
                    ),
                )
            )
    return issues


def _check_sp_outline(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/outline.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if _has_placeholder_markers(raw):
            return [
                NativeQualityIssue(
                    code="outline_scaffold",
                    message="Outline still contains placeholder/TODO bullets; rewrite each subsection with topic-specific, checkable bullets.",
                )
            ]
    outline = _st_load_yaml(path) if path.exists() else None
    if not isinstance(outline, list) or not outline:
        return [
            NativeQualityIssue(
                code="invalid_outline",
                message=f"`{out_rel}` is missing or not a YAML list.",
            )
        ]
    section_first_issues = _as_native_issues(
        policy.section_first_artifact_issues(workspace, consumer=out_rel)
    )
    if section_first_issues:
        return section_first_issues
    template_bullets = {
        "Define problem setting and terminology",
        "Representative approaches and design choices",
        "Benchmarks / datasets / evaluation metrics",
        "Limitations and open problems",
    }
    scaffold_re = re.compile(
        r"(?i)^(?:Scope and definitions for|Design space in|Evaluation practice for|Limitations for|Connections: how)\b"
    )
    bullets_total = 0
    bullets_template = 0
    bullets_scaffold = 0
    for section in outline:
        if not isinstance(section, dict):
            continue
        for sub in section.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            for b in sub.get("bullets") or []:
                b = str(b).strip()
                if not b:
                    continue
                bullets_total += 1
                if b in template_bullets:
                    bullets_template += 1
                if scaffold_re.match(b):
                    bullets_scaffold += 1
    if bullets_total and bullets_template / bullets_total >= 0.7:
        return [
            NativeQualityIssue(
                code="outline_template_bullets",
                message="Outline bullets are mostly generic templates; replace with specific axes, comparisons, and concrete terms for each subsection.",
            )
        ]
    if bullets_total and bullets_scaffold / bullets_total >= 0.7:
        return [
            NativeQualityIssue(
                code="outline_scaffold_bullets",
                message=(
                    "Outline bullets still look like scaffold prompts (scope/design space/evaluation/limitations/connections). "
                    "Rewrite each subsection with concrete mechanisms, benchmarks, and comparison axes."
                ),
            )
        ]
    profile = policy.pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        draft_profile = policy.draft_profile(workspace)
        missing_meta = 0
        subs_total = 0
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                bullets = [str(b).strip() for b in (sub.get("bullets") or []) if str(b).strip()]
                if not bullets:
                    continue
                subs_total += 1
                has_intent = any(re.match(r"(?i)^intent\s*[:：]", b) for b in bullets)
                has_rq = any(re.match(r"(?i)^(?:rq|question)\s*[:：]", b) for b in bullets)
                has_evidence = any(re.match(r"(?i)^evidence needs\s*[:：]", b) for b in bullets)
                has_expected = any(re.match(r"(?i)^expected cites\s*[:：]", b) for b in bullets)
                if not (has_intent and has_rq and has_evidence and has_expected):
                    missing_meta += 1
        sec_total = 0
        for section in outline:
            if not isinstance(section, dict):
                continue
            if str(section.get("title") or "").strip():
                sec_total += 1
        extra_global_h2 = 2
        max_final_h2 = policy.quality_contract_int(
            workspace,
            keys=("structure_policy", "max_final_h2_by_profile", draft_profile),
            default={"course_paper": 7, "deep": 9}.get(draft_profile, 8),
        )
        max_outline_h2 = max(1, max_final_h2 - extra_global_h2)
        if sec_total > max_outline_h2:
            return [
                NativeQualityIssue(
                    code="outline_too_many_sections",
                    message=(
                        f"Outline has too many top-level sections for paper-like readability ({sec_total}). "
                        f"The final draft adds Discussion+Conclusion, so this would likely render as ~{sec_total + extra_global_h2} H2 sections. "
                        f"Prefer <= {max_final_h2} final H2 sections (Intro → Related Work → 3–4 core chapters → Discussion → Conclusion). "
                        "Merge/simplify the taxonomy so each chapter is thicker and each H3 can sustain deeper evidence-first prose. "
                        "If you already have an outline but it is over-fragmented, use `outline-budgeter` (NO PROSE) to merge/simplify, then rerun `section-mapper` → `outline-refiner`."
                    ),
                )
            ]
        max_h3 = policy.quality_contract_int(
            workspace,
            keys=("structure_policy", "max_h3_by_profile", draft_profile),
            default={"course_paper": 6, "deep": 12}.get(draft_profile, 10),
        )
        if subs_total > max_h3:
            return [
                NativeQualityIssue(
                    code="outline_too_many_subsections",
                    message=(
                        f"Outline has too many subsections for survey-quality writing ({subs_total}). "
                        f"Prefer <= {max_h3} H3 subsections for this draft profile (fewer, thicker sections). "
                        "Merge/simplify the taxonomy/outline so each H3 can sustain deeper evidence-first prose. "
                        "Fix (skills-first): run `outline-budgeter` (NO PROSE) to merge adjacent H3s, then rerun `section-mapper` → `outline-refiner`."
                    ),
                )
            ]
        if subs_total and missing_meta:
            return [
                NativeQualityIssue(
                    code="outline_missing_stage_a_fields",
                    message=(
                        f"{missing_meta}/{subs_total} subsections are missing required Stage A bullets "
                        "(Intent/RQ/Evidence needs/Expected cites). Add these fields so later mapping/claims/drafting are verifiable."
                    ),
                )
            ]
    return []


def _check_sp_mapping(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/mapping.tsv"
    path = workspace / out_rel
    rows = _sp_read_tsv(path)
    if not rows:
        return [
            NativeQualityIssue(code="empty_mapping", message=f"`{out_rel}` has no rows.")
        ]
    issues: list[NativeQualityIssue] = []
    issues.extend(
        _as_native_issues(policy.section_first_artifact_issues(workspace, consumer=out_rel))
    )
    placeholder_rows = 0
    for row in rows:
        why = str(row.get("why") or "").strip()
        title = str(row.get("section_title") or "").strip()
        low = f"{why} {title}".lower()
        if "(placeholder)" in low or "placeholder" in low:
            placeholder_rows += 1
    if placeholder_rows:
        issues.append(
            NativeQualityIssue(
                code="mapping_contains_placeholders",
                message=f"`{out_rel}` still contains placeholder rows/rationales; regenerate mapping or edit it to cover all subsections with real rationales.",
            )
        )
    low_confidence_rows = 0
    for row in rows:
        why = str(row.get("why") or "").strip().lower()
        if any(
            marker in why
            for marker in (
                "weak lexical overlap",
                "low-confidence candidate",
                "sparse explicit term overlap",
                "based on overall similarity",
            )
        ):
            low_confidence_rows += 1
    if low_confidence_rows:
        issues.append(
            NativeQualityIssue(
                code="mapping_low_confidence",
                message=(
                    f"`{out_rel}` contains {low_confidence_rows} low-confidence mapping row(s); "
                    "expand the evidence set, refine subsection concepts, or replace them with reviewed semantic mappings."
                ),
            )
        )
    generic_why = 0
    why_total = 0
    for row in rows:
        why = str(row.get("why") or "").strip()
        if not why:
            continue
        why_total += 1
        if why.startswith(("token_overlap=", "matched_terms=")) or "matched_terms=" in why:
            generic_why += 1
    if why_total and generic_why / why_total >= 0.8:
        issues.append(
            NativeQualityIssue(
                code="mapping_generic_rationale",
                message="Mapping rationale looks mostly token/term overlap; add brief semantic reasons (method/task/benchmark) or refine mapping manually.",
            )
        )
    outline_path = workspace / "outline" / "outline.yml"
    outline = _st_load_yaml(outline_path) if outline_path.exists() else None
    expected: dict[str, str] = {}
    if isinstance(outline, list):
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                title = str(sub.get("title") or "").strip()
                if sid and title:
                    expected[sid] = title
    if expected:
        counts: dict[str, int] = {sid: 0 for sid in expected}
        unknown = 0
        title_mismatch = 0
        for row in rows:
            sid = str(row.get("section_id") or "").strip()
            if sid in counts:
                counts[sid] += 1
                want = expected.get(sid) or ""
                got = str(row.get("section_title") or "").strip()
                if want and got:
                    want_norm = re.sub(r"\s+", " ", want).strip().lower()
                    got_norm = re.sub(r"\s+", " ", got).strip().lower()
                    if want_norm != got_norm:
                        title_mismatch += 1
            else:
                unknown += 1
        profile = policy.pipeline_profile_name(workspace)
        per_subsection = int(policy.per_subsection(workspace)) if profile == "arxiv-survey" else 3
        ok = sum(1 for _, c in counts.items() if c >= per_subsection)
        total = max(1, len(counts))
        required_ratio = 1.0 if profile == "arxiv-survey" else 0.8
        if ok / total < required_ratio:
            low = sorted([(sid, c) for sid, c in counts.items() if c < per_subsection], key=lambda kv: (kv[1], kv[0]))
            sample = ", ".join([f"{sid}({c})" for sid, c in low[:10]])
            suffix = "..." if len(low) > 10 else ""
            issues.append(
                NativeQualityIssue(
                    code="mapping_low_coverage",
                    message=(
                        f"Only {ok}/{len(counts)} subsections have >= {per_subsection} mapped papers; "
                        f"low-coverage examples: {sample}{suffix}. "
                        "Increase `--per-subsection` (survey default) or refine `outline/outline.yml` so each H3 can sustain evidence-first writing."
                    ),
                )
            )
        if unknown:
            issues.append(
                NativeQualityIssue(
                    code="mapping_unknown_sections",
                    message=f"`{out_rel}` contains {unknown} row(s) with section_id not present in `outline/outline.yml`; regenerate mapping after updating outline.",
                )
            )
        if title_mismatch / max(1, len(rows)) >= 0.3:
            issues.append(
                NativeQualityIssue(
                    code="mapping_section_title_mismatch",
                    message="Many mapping rows have section_title not matching the outline title; ensure mapping.tsv corresponds to the current outline.",
                )
            )
    sections: set[str] = set()
    paper_to_sections: dict[str, set[str]] = {}
    for row in rows:
        sid = str(row.get("section_id") or "").strip()
        pid = str(row.get("paper_id") or "").strip()
        if sid:
            sections.add(sid)
        if sid and pid:
            paper_to_sections.setdefault(pid, set()).add(sid)
    if sections and paper_to_sections:
        top_pid, top_secs = max(paper_to_sections.items(), key=lambda kv: len(kv[1]))
        top_count = len(top_secs)
        if policy.draft_profile(workspace) == "course_paper":
            import math

            threshold = max(3, math.ceil(len(sections) * 0.60))
        else:
            threshold = max(6, int(len(sections) * 0.35))
        if top_count > threshold:
            issues.append(
                NativeQualityIssue(
                    code="mapping_repeated_papers",
                    message=(
                        f"Paper `{top_pid}` appears in {top_count}/{len(sections)} subsections; "
                        "mapping likely over-reuses a few works across unrelated sections. Diversify `outline/mapping.tsv`."
                    ),
                )
            )
    return issues


def _check_sp_paper_notes(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "papers/paper_notes.jsonl"
    path = workspace / out_rel
    notes = _read_jsonl(path)
    if not notes:
        return [
            NativeQualityIssue(code="empty_paper_notes", message=f"`{out_rel}` is empty.")
        ]
    notes = [n for n in notes if isinstance(n, dict)]
    if not notes:
        return [
            NativeQualityIssue(
                code="invalid_paper_notes", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    issues: list[NativeQualityIssue] = []
    seen: set[str] = set()
    dupes = 0
    missing_pid = 0
    missing_title = 0
    bad_level = 0
    missing_lims = 0
    for n in notes:
        pid = str(n.get("paper_id") or "").strip()
        title = str(n.get("title") or "").strip()
        lvl = str(n.get("evidence_level") or "").strip().lower()
        lims = n.get("limitations") or []
        if not pid:
            missing_pid += 1
            continue
        if pid in seen:
            dupes += 1
        seen.add(pid)
        if not title:
            missing_title += 1
        if lvl not in {"fulltext", "abstract", "title"}:
            bad_level += 1
        if not isinstance(lims, list) or len([x for x in lims if str(x).strip()]) < 1:
            missing_lims += 1
    if missing_pid:
        issues.append(
            NativeQualityIssue(
                code="paper_notes_missing_paper_id",
                message=f"`{out_rel}` has {missing_pid} record(s) missing `paper_id`.",
            )
        )
    if dupes:
        issues.append(
            NativeQualityIssue(
                code="paper_notes_duplicate_paper_id",
                message=f"`{out_rel}` has duplicate `paper_id` entries ({dupes}).",
            )
        )
    if missing_title:
        issues.append(
            NativeQualityIssue(
                code="paper_notes_missing_title",
                message=f"`{out_rel}` has {missing_title} record(s) missing `title`.",
            )
        )
    if bad_level:
        issues.append(
            NativeQualityIssue(
                code="paper_notes_bad_evidence_level",
                message=f"`{out_rel}` has {bad_level} record(s) with invalid `evidence_level` (expected fulltext|abstract|title).",
            )
        )
    if missing_lims:
        issues.append(
            NativeQualityIssue(
                code="paper_notes_missing_limitations",
                message=f"`{out_rel}` has {missing_lims} record(s) missing `limitations` (need at least one item).",
            )
        )
    core_path = workspace / "papers" / "core_set.csv"
    if core_path.exists():
        expected: set[str] = set()
        try:
            with core_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = str(row.get("paper_id") or "").strip()
                    if pid:
                        expected.add(pid)
        except Exception:
            expected = set()
        if expected:
            missing = sorted([pid for pid in expected if pid not in seen])
            if missing:
                sample = ", ".join(missing[:8])
                suffix = "..." if len(missing) > 8 else ""
                issues.append(
                    NativeQualityIssue(
                        code="paper_notes_missing_core_coverage",
                        message=f"`{out_rel}` is missing notes for some core-set papers (e.g., {sample}{suffix}).",
                    )
                )
    if len(outputs) >= 2:
        bank_rel = outputs[1]
        bank_path = workspace / bank_rel
        bank = _read_jsonl(bank_path) if bank_path.exists() else []
        bank = [b for b in bank if isinstance(b, dict)]
        if not bank_path.exists():
            issues.append(
                NativeQualityIssue(
                    code="missing_evidence_bank", message=f"`{bank_rel}` does not exist."
                )
            )
        elif not bank:
            issues.append(
                NativeQualityIssue(
                    code="empty_evidence_bank", message=f"`{bank_rel}` is empty."
                )
            )
        else:
            seen_eid: set[str] = set()
            dup_eid = 0
            bad_items = 0
            pids_in_bank: set[str] = set()
            for it in bank:
                eid = str(it.get("evidence_id") or "").strip()
                pid = str(it.get("paper_id") or "").strip()
                bibkey = str(it.get("bibkey") or "").strip()
                claim_type = str(it.get("claim_type") or "").strip()
                snippet = str(it.get("snippet") or "").strip()
                locator = it.get("locator")
                lvl = str(it.get("evidence_level") or "").strip()
                if not eid or not pid or not bibkey or not claim_type or not snippet or not lvl or not isinstance(locator, dict):
                    bad_items += 1
                    continue
                src = str(locator.get("source") or "").strip()
                ptr = str(locator.get("pointer") or "").strip()
                if not src or not ptr:
                    bad_items += 1
                    continue
                if eid in seen_eid:
                    dup_eid += 1
                seen_eid.add(eid)
                pids_in_bank.add(pid)
            if dup_eid:
                issues.append(
                    NativeQualityIssue(
                        code="evidence_bank_duplicate_ids",
                        message=f"`{bank_rel}` has duplicate evidence_id entries ({dup_eid}).",
                    )
                )
            if bad_items:
                issues.append(
                    NativeQualityIssue(
                        code="evidence_bank_bad_items",
                        message=f"`{bank_rel}` has {bad_items} malformed item(s) (missing fields/locator).",
                    )
                )
            missing_pid_l = sorted([pid for pid in seen if pid not in pids_in_bank])
            if missing_pid_l:
                sample = ", ".join(missing_pid_l[:8])
                suffix = "..." if len(missing_pid_l) > 8 else ""
                issues.append(
                    NativeQualityIssue(
                        code="evidence_bank_missing_papers",
                        message=f"`{bank_rel}` has no evidence items for some papers in notes (e.g., {sample}{suffix}).",
                    )
                )
            if policy.pipeline_profile_name(workspace) == "arxiv-survey":
                items_per_paper = 4 if policy.draft_profile(workspace) == "course_paper" else 7
                min_items = max(len(seen), int(len(seen) * items_per_paper))
                if len(bank) < min_items:
                    issues.append(
                        NativeQualityIssue(
                            code="evidence_bank_too_small",
                            message=(
                                f"`{bank_rel}` has {len(bank)} items for {len(seen)} papers; "
                                f"The `{policy.draft_profile(workspace)}` profile expects >= {min_items} "
                                f"(>={items_per_paper} items/paper on average)."
                            ),
                        )
                    )
            else:
                if len(bank) < len(seen):
                    issues.append(
                        NativeQualityIssue(
                            code="evidence_bank_too_small",
                            message=f"`{bank_rel}` has only {len(bank)} items for {len(seen)} papers; expect >=1 evidence item per paper on average.",
                        )
                    )
    return issues


def _check_sp_claim_evidence_matrix(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/claim_evidence_matrix.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_claim_matrix", message=f"`{out_rel}` does not exist."
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "<!-- SCAFFOLD" in text:
        return [
            NativeQualityIssue(
                code="claim_matrix_scaffold",
                message="Claim–evidence matrix still contains scaffold markers; rewrite claims and remove the `<!-- SCAFFOLD ... -->` line.",
            )
        ]
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return [
            NativeQualityIssue(
                code="claim_matrix_todo",
                message="Claim–evidence matrix still contains placeholder markers (TODO/TBD/FIXME); rewrite claims into specific statements and remove placeholders.",
            )
        ]
    if "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            NativeQualityIssue(
                code="claim_matrix_contains_ellipsis",
                message="Claim–evidence matrix contains ellipsis, which usually indicates truncated scaffold text; rewrite into concrete, checkable claims/axes.",
            )
        ]
    if re.search(r"(?i)enumerate\s+2-4", text):
        return [
            NativeQualityIssue(
                code="claim_matrix_scaffold_instructions",
                message="Claim–evidence matrix contains scaffold instructions like 'enumerate 2-4 ...'; replace with specific mechanisms/axes grounded in the mapped papers.",
            )
        ]
    if re.search(r"(?i)\b(?:scope and definitions for|design space in|evaluation practice for)\b", text):
        return [
            NativeQualityIssue(
                code="claim_matrix_scaffold_phrases",
                message="Claim–evidence matrix still contains outline scaffold phrases (scope/design space/evaluation practice). Rewrite claims/axes using evidence needs + paper notes, not prompt-like bullets.",
            )
        ]
    claim_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- Claim:")]
    if not claim_lines:
        return [
            NativeQualityIssue(
                code="empty_claims",
                message="No `- Claim:` lines found in claim–evidence matrix.",
            )
        ]
    templ = 0
    around_template = 0
    for ln in claim_lines:
        low = ln.lower()
        if "key approaches in **" in low and "can be compared along" in low:
            templ += 1
        if "clusters around recurring themes" in low or "trade-offs tend to show up along" in low:
            templ += 1
        if ln.split("- Claim:", 1)[-1].strip().startswith("围绕 "):
            around_template += 1
    if templ / max(1, len(claim_lines)) >= 0.7:
        return [
            NativeQualityIssue(
                code="generic_claims",
                message="Claims are mostly generic template sentences; replace with specific, falsifiable claims grounded in the mapped papers.",
            )
        ]
    if around_template / max(1, len(claim_lines)) >= 0.8:
        return [
            NativeQualityIssue(
                code="claim_matrix_same_template",
                message="Most claims start with the same '围绕 …' template; rewrite claims to be specific (mechanism/assumption/result) per subsection.",
            )
        ]
    blocks = re.split(r"(?m)^##\s+", text)
    low_evidence = 0
    total = 0
    for block in blocks[1:]:
        if not block.strip():
            continue
        total += 1
        evidence_lines = [ln for ln in block.splitlines() if "Evidence:" in ln]
        if len(evidence_lines) < 2:
            low_evidence += 1
    if total and (low_evidence / total) >= 0.2:
        return [
            NativeQualityIssue(
                code="claim_matrix_too_few_evidence_items",
                message=f"Many subsections have <2 evidence items in the matrix ({low_evidence}/{total}); add mapped paper IDs + cite keys per subsection before drafting.",
            )
        ]
    return []


def _check_sp_subsection_briefs(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/subsection_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_subsection_briefs", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [
            NativeQualityIssue(
                code="empty_subsection_briefs", message=f"`{out_rel}` is empty."
            )
        ]
    if "…" in raw:
        return [
            NativeQualityIssue(
                code="subsection_briefs_contains_ellipsis",
                message="Subsection briefs contain unicode ellipsis (`…`), which is treated as placeholder leakage; fill axes/clusters explicitly.",
            )
        ]
    if _has_placeholder_markers(raw):
        return [
            NativeQualityIssue(
                code="subsection_briefs_placeholders",
                message="Subsection briefs contain placeholder markers (TODO/TBD/FIXME/(placeholder)/SCAFFOLD); refine briefs before writing.",
            )
        ]
    records = _read_jsonl(path)
    briefs = [r for r in records if isinstance(r, dict)]
    if not briefs:
        return [
            NativeQualityIssue(
                code="invalid_subsection_briefs", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    cutover_issues = _as_native_issues(
        policy.section_first_artifact_issues(workspace, consumer=out_rel)
    )
    cutover_issues.extend(
        _as_native_issues(
            policy.section_first_cutover_issues(
                workspace, consumer=out_rel, require_stable_h3=True
            )
        )
    )
    if cutover_issues:
        return cutover_issues
    outline_path = workspace / "outline" / "outline.yml"
    expected_ids: set[str] = set()
    if outline_path.exists():
        try:
            outline = _st_load_yaml(outline_path) or []
            for section in outline if isinstance(outline, list) else []:
                if not isinstance(section, dict):
                    continue
                for sub in section.get("subsections") or []:
                    if not isinstance(sub, dict):
                        continue
                    sid = str(sub.get("id") or "").strip()
                    if sid:
                        expected_ids.add(sid)
        except Exception:
            expected_ids = set()
    by_id: dict[str, dict] = {}
    dupes = 0
    for rec in briefs:
        sid = str(rec.get("sub_id") or "").strip()
        if not sid:
            continue
        if sid in by_id:
            dupes += 1
        by_id[sid] = rec
    issues: list[NativeQualityIssue] = []
    if dupes:
        issues.append(
            NativeQualityIssue(
                code="subsection_briefs_duplicate_ids",
                message=f"`{out_rel}` has duplicate `sub_id` entries ({dupes}).",
            )
        )
    if expected_ids:
        missing = sorted([sid for sid in expected_ids if sid not in by_id])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            issues.append(
                NativeQualityIssue(
                    code="subsection_briefs_missing_sections",
                    message=f"Briefs missing some subsections from `outline/outline.yml` (e.g., {sample}{suffix}).",
                )
            )
    profile = policy.pipeline_profile_name(workspace)
    min_plan_len = (6 if policy.draft_profile(workspace) == "course_paper" else 8) if profile == "arxiv-survey" else 2
    required_top = {
        "sub_id", "title", "section_id", "section_title", "scope_rule", "rq",
        "thesis", "tension_statement", "evaluation_anchor_minimal", "axes",
        "clusters", "paragraph_plan", "evidence_level_summary",
    }
    bad = 0
    for sid, rec in by_id.items():
        missing_top = [k for k in required_top if k not in rec]
        if missing_top:
            bad += 1
            continue
        rq = str(rec.get("rq") or "").strip()
        if len(rq) < 12:
            bad += 1
            continue
        thesis = str(rec.get("thesis") or "").strip()
        if len(thesis) < 24 or _has_placeholder_markers(thesis) or "…" in thesis:
            bad += 1
            continue
        tension = str(rec.get("tension_statement") or "").strip()
        if len(tension) < 24 or _has_placeholder_markers(tension) or "…" in tension:
            bad += 1
            continue
        eva = rec.get("evaluation_anchor_minimal")
        if not isinstance(eva, dict):
            bad += 1
            continue
        if not all(str(eva.get(k) or "").strip() for k in ("task", "metric", "constraint")):
            bad += 1
            continue
        axes = rec.get("axes")
        if not isinstance(axes, list) or len([a for a in axes if str(a).strip()]) < 3:
            bad += 1
            continue
        scope_rule = rec.get("scope_rule")
        if not isinstance(scope_rule, dict):
            bad += 1
            continue
        clusters = rec.get("clusters")
        if not isinstance(clusters, list) or len(clusters) < 2:
            bad += 1
            continue
        cluster_ok = 0
        for c in clusters:
            if not isinstance(c, dict):
                continue
            label = str(c.get("label") or "").strip()
            pids = c.get("paper_ids") or []
            if not label or not isinstance(pids, list) or len([p for p in pids if str(p).strip()]) < 2:
                continue
            cluster_ok += 1
        if cluster_ok < 2:
            bad += 1
            continue
        plan = rec.get("paragraph_plan")
        if not isinstance(plan, list) or len(plan) < min_plan_len:
            bad += 1
            continue
        plan_ok = 0
        sample_p = plan[:min_plan_len] if min_plan_len > 2 else plan[:3]
        for item in sample_p:
            if not isinstance(item, dict):
                continue
            intent = str(item.get("intent") or "").strip()
            role = str(item.get("argument_role") or "").strip()
            connector_to_prev = str(item.get("connector_to_prev") or "").strip()
            connector_phrase = str(item.get("connector_phrase") or "").strip()
            try:
                para_no = int(item.get("para") or 0)
            except Exception:
                para_no = 0
            if not (intent and role):
                continue
            if para_no and para_no > 1:
                if not (connector_to_prev and connector_phrase):
                    continue
                if len(connector_phrase) > 140:
                    continue
                if connector_phrase.strip().endswith((".", "?", "!")):
                    continue
                words = re.findall(r"[A-Za-z0-9]+", connector_phrase)
                if len(words) > 18:
                    continue
            plan_ok += 1
        required_ok = 4 if min_plan_len >= 6 else (3 if min_plan_len >= 4 else 2)
        if plan_ok < required_ok:
            bad += 1
            continue
        ev = rec.get("evidence_level_summary")
        if not isinstance(ev, dict):
            bad += 1
            continue
    if bad:
        issues.append(
            NativeQualityIssue(
                code="subsection_briefs_incomplete",
                message=f"`{out_rel}` has {bad} subsection brief(s) missing required fields or lacking axes/clusters/plan depth.",
            )
        )
    generic_axis_norms = _sp_subsection_brief_generic_axis_norms()
    generic_heavy: list[str] = []
    axis_signature_to_ids: dict[tuple[str, ...], list[str]] = {}
    for sid, rec in by_id.items():
        axes = [str(a).strip() for a in (rec.get("axes") or []) if str(a).strip()]
        norm_axes = [_sp_normalize_axis_label(a) for a in axes]
        if not norm_axes:
            continue
        generic_n = sum(1 for a in norm_axes if a in generic_axis_norms)
        if len(norm_axes) >= 4 and generic_n >= 3:
            generic_heavy.append(sid)
        sig = tuple(norm_axes[:4])
        if len(sig) >= 3:
            axis_signature_to_ids.setdefault(sig, []).append(sid)
    if generic_heavy:
        issues.append(
            NativeQualityIssue(
                code="subsection_briefs_generic_axes",
                message=(
                    f"`{out_rel}` has subsection briefs dominated by generic axes (e.g., {', '.join(generic_heavy[:8])}"
                    f"{'...' if len(generic_heavy) > 8 else ''}); add subsection-specific mechanism/protocol/risk axes before writing."
                ),
            )
        )
    repeated_axis_sets = [ids for ids in axis_signature_to_ids.values() if len(ids) >= 3]
    if repeated_axis_sets:
        sample = ", ".join(["/".join(ids[:3]) + ("..." if len(ids) > 3 else "") for ids in repeated_axis_sets[:3]])
        issues.append(
            NativeQualityIssue(
                code="subsection_briefs_repeated_axes",
                message=(
                    f"`{out_rel}` repeats the same leading axis sets across multiple subsections (e.g., {sample}); "
                    "make axes subsection-specific so downstream packs and prose do not collapse into the same template."
                ),
            )
        )
    if profile == "arxiv-survey":
        def _norm_sentence(s: str) -> str:
            s = re.sub(r"\[@[^\]]+\]", "", s or "")
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        tension_to_ids: dict[str, list[str]] = {}
        for sid, rec in by_id.items():
            t = _norm_sentence(str(rec.get("tension_statement") or ""))
            if not t:
                continue
            tension_to_ids.setdefault(t, []).append(sid)
        dup_tensions = [ids for _, ids in tension_to_ids.items() if len(ids) >= 2]
        if dup_tensions:
            sample = ", ".join([",".join(ids[:3]) + ("..." if len(ids) > 3 else "") for ids in dup_tensions[:3]])
            issues.append(
                NativeQualityIssue(
                    code="subsection_briefs_repeated_tension",
                    message=(
                        f"`{out_rel}` contains repeated `tension_statement` across subsections (e.g., {sample}). "
                        "Rewrite tensions to be subsection-specific (this prevents repeated H3 openers / generator voice in C5)."
                    ),
                )
            )
    return issues


def _check_sp_chapter_briefs(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/chapter_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_chapter_briefs", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [
            NativeQualityIssue(
                code="empty_chapter_briefs", message=f"`{out_rel}` is empty."
            )
        ]
    if _has_placeholder_markers(raw) or "…" in raw:
        return [
            NativeQualityIssue(
                code="chapter_briefs_placeholders",
                message="Chapter briefs contain placeholder markers/ellipsis; refine throughline/key contrasts/lead plan before writing.",
            )
        ]
    records = _read_jsonl(path)
    briefs = [r for r in records if isinstance(r, dict)]
    if not briefs:
        return [
            NativeQualityIssue(
                code="invalid_chapter_briefs", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    outline_path = workspace / "outline" / "outline.yml"
    expected: set[str] = set()
    if outline_path.exists():
        try:
            outline = _st_load_yaml(outline_path) or []
            if isinstance(outline, list):
                for sec in outline:
                    if not isinstance(sec, dict):
                        continue
                    sec_id = str(sec.get("id") or "").strip()
                    subs = sec.get("subsections") or []
                    if sec_id and isinstance(subs, list) and subs:
                        expected.add(sec_id)
        except Exception:
            expected = set()
    by_id: dict[str, dict] = {}
    dupes = 0
    for rec in briefs:
        sid = str(rec.get("section_id") or "").strip()
        if not sid:
            continue
        if sid in by_id:
            dupes += 1
        by_id[sid] = rec
    issues: list[NativeQualityIssue] = []
    if dupes:
        issues.append(
            NativeQualityIssue(
                code="chapter_briefs_duplicate_ids",
                message=f"`{out_rel}` has duplicate `section_id` entries ({dupes}).",
            )
        )
    if expected:
        missing = sorted([sid for sid in expected if sid not in by_id])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            issues.append(
                NativeQualityIssue(
                    code="chapter_briefs_missing_sections",
                    message=f"Chapter briefs missing some H2 sections with subsections (e.g., {sample}{suffix}).",
                )
            )
    bad = 0
    allowed_modes = {"clusters", "timeline", "tradeoff_matrix", "case_study", "tension_resolution"}
    for sid, rec in by_id.items():
        if not str(rec.get("section_title") or "").strip():
            bad += 1
            continue
        subs = rec.get("subsections")
        if not isinstance(subs, list) or not subs:
            bad += 1
            continue
        mode = str(rec.get("synthesis_mode") or "").strip()
        preview = rec.get("synthesis_preview") or []
        if mode not in allowed_modes:
            bad += 1
            continue
        if not isinstance(preview, list) or len([t for t in preview if str(t).strip()]) < 1:
            bad += 1
            continue
        throughline = rec.get("throughline")
        if not isinstance(throughline, list) or len([t for t in throughline if str(t).strip()]) < 2:
            bad += 1
            continue
        lead_plan = rec.get("lead_paragraph_plan")
        if not isinstance(lead_plan, list) or len([t for t in lead_plan if str(t).strip()]) < 2:
            bad += 1
            continue
        bridge = rec.get("bridge_terms")
        if not isinstance(bridge, list) or len([t for t in bridge if str(t).strip()]) < 3:
            bad += 1
            continue
    if bad:
        issues.append(
            NativeQualityIssue(
                code="chapter_briefs_incomplete",
                message=f"`{out_rel}` has {bad} chapter brief(s) missing required fields (subsections/throughline/lead plan/bridge terms).",
            )
        )
    return issues


def _check_sp_coverage_report(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    report_rel = outputs[0] if outputs else "outline/coverage_report.md"
    state_rel = outputs[1] if len(outputs) >= 2 else "outline/outline_state.jsonl"
    reroute_rel = outputs[2] if len(outputs) >= 3 else "output/REROUTE_STATE.json"
    report_path = workspace / report_rel
    state_path = workspace / state_rel
    reroute_path = workspace / reroute_rel
    if not report_path.exists():
        return [
            NativeQualityIssue(
                code="missing_coverage_report", message=f"`{report_rel}` does not exist."
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report:
        return [
            NativeQualityIssue(
                code="empty_coverage_report", message=f"`{report_rel}` is empty."
            )
        ]
    if _has_placeholder_markers(report) or "…" in report:
        return [
            NativeQualityIssue(
                code="coverage_report_placeholders",
                message=f"`{report_rel}` contains placeholders; regenerate planner report.",
            )
        ]
    if "| Subsection |" not in report:
        return [
            NativeQualityIssue(
                code="coverage_report_missing_table",
                message=f"`{report_rel}` is missing the per-subsection table.",
            )
        ]
    section_only = report
    m = re.search(r"(?s)##\s+Per-subsection\s+summary\s*(.*?)\n##\s+Per-chapter\s+sizing", report)
    if m:
        section_only = m.group(1)
    row_lines = [
        ln.strip()
        for ln in section_only.splitlines()
        if ln.strip().startswith("|") and not ln.strip().startswith("|---")
    ]
    evidence_zero = 0
    axes_missing = 0
    data_rows = 0
    for ln in row_lines:
        if "Subsection" in ln and "Evidence levels" in ln:
            continue
        data_rows += 1
        if "fulltext=0, abstract=0, title=0" in ln:
            evidence_zero += 1
        if re.search(r"\|\s*[—-]\s*\|", ln):
            axes_missing += 1
    if not state_path.exists():
        return [
            NativeQualityIssue(
                code="missing_outline_state", message=f"`{state_rel}` does not exist."
            )
        ]
    recs = _read_jsonl(state_path)
    recs = [r for r in recs if isinstance(r, dict)]
    if not recs:
        return [
            NativeQualityIssue(
                code="empty_outline_state", message=f"`{state_rel}` has no JSON records."
            )
        ]
    cutover_issues = _as_native_issues(
        policy.section_first_artifact_issues(workspace, consumer=report_rel)
    )
    cutover_issues.extend(
        _as_native_issues(
            policy.section_first_cutover_issues(
                workspace, consumer=report_rel, require_stable_h3=True
            )
        )
    )
    if cutover_issues:
        return cutover_issues
    if policy.structure_mode(workspace) == "section_first":
        if not reroute_path.exists():
            return [
                NativeQualityIssue(
                    code="missing_reroute_state",
                    message=f"`{reroute_rel}` does not exist.",
                )
            ]
        try:
            reroute_state = json.loads(reroute_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        except Exception as exc:
            return [
                NativeQualityIssue(
                    code="invalid_reroute_state",
                    message=f"`{reroute_rel}` is not valid JSON ({type(exc).__name__}: {exc}).",
                )
            ]
        if not isinstance(reroute_state, dict):
            return [
                NativeQualityIssue(
                    code="invalid_reroute_state",
                    message=f"`{reroute_rel}` must be a JSON object.",
                )
            ]
        required = {"structure_phase", "h3_status", "reroute_target", "retry_budget_remaining", "status"}
        missing = sorted(key for key in required if key not in reroute_state)
        if missing:
            return [
                NativeQualityIssue(
                    code="reroute_state_missing_fields",
                    message=f"`{reroute_rel}` is missing required fields: {', '.join(missing)}.",
                )
            ]
        latest = recs[-1]
        for key in ("structure_phase", "h3_status", "reroute_target", "retry_budget_remaining"):
            if reroute_state.get(key) != latest.get(key):
                return [
                    NativeQualityIssue(
                        code="reroute_state_mismatch",
                        message=f"`{reroute_rel}` is out of sync with latest `{state_rel}` for field `{key}`.",
                    )
                ]
    return []


def _check_sp_evidence_drafts(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/evidence_drafts.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_evidence_drafts", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [
            NativeQualityIssue(
                code="empty_evidence_drafts", message=f"`{out_rel}` is empty."
            )
        ]
    if "…" in raw:
        return [
            NativeQualityIssue(
                code="evidence_drafts_contains_ellipsis",
                message="Evidence drafts contain unicode ellipsis (`…`), which is treated as placeholder leakage; rewrite evidence packs explicitly.",
            )
        ]
    if _has_placeholder_markers(raw):
        return [
            NativeQualityIssue(
                code="evidence_drafts_placeholders",
                message="Evidence drafts contain placeholder markers (TODO/TBD/FIXME/(placeholder)/SCAFFOLD); fill evidence packs before writing.",
            )
        ]
    records = _read_jsonl(path)
    packs = [r for r in records if isinstance(r, dict)]
    if not packs:
        return [
            NativeQualityIssue(
                code="invalid_evidence_drafts", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    bib_path = workspace / "citations" / "ref.bib"
    bib_keys: set[str] = set()
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    def _collect_keys(citations: Any) -> set[str]:
        out: set[str] = set()
        if not isinstance(citations, list):
            return out
        for c in citations:
            c = str(c or "").strip()
            if not c:
                continue
            if c.startswith("@"):
                c = c[1:]
            for k in re.findall(r"[A-Za-z0-9:_-]+", c):
                if k:
                    out.add(k)
        return out

    issues: list[NativeQualityIssue] = []
    profile = policy.pipeline_profile_name(workspace)
    draft_profile = policy.draft_profile(workspace)
    min_comparisons = 3
    if profile == "arxiv-survey":
        thresholds = {
            "course_paper": (3, 6, 3, 3),
            "deep": (6, 14, 6, 6),
            "survey": (4, 12, 5, 5),
        }
        min_comparisons, min_snippets, min_eval, min_fail = thresholds.get(draft_profile, thresholds["survey"])
    else:
        min_snippets = 1
        min_eval = 1
        min_fail = 1
    bad = 0
    missing_bib = 0
    blocking_missing = 0
    weak_comparisons = 0
    missing_snippets = 0
    bad_snippet_prov = 0
    weak_eval = 0
    weak_fail = 0
    for pack in packs:
        sub_id = str(pack.get("sub_id") or "").strip()
        title = str(pack.get("title") or "").strip()
        if not sub_id or not title:
            bad += 1
            continue
        miss = pack.get("blocking_missing") or []
        if isinstance(miss, list) and any(str(x).strip() for x in miss):
            blocking_missing += 1
            continue
        snippets = pack.get("evidence_snippets") or []
        if not isinstance(snippets, list) or len([s for s in snippets if isinstance(s, dict) and str(s.get("text") or "").strip()]) < min_snippets:
            missing_snippets += 1
            continue
        for snip in snippets[:6]:
            if not isinstance(snip, dict):
                continue
            prov = snip.get("provenance")
            if not isinstance(prov, dict):
                bad_snippet_prov += 1
                break
            src = str(prov.get("source") or "").strip()
            ptr = str(prov.get("pointer") or "").strip()
            if not src or not ptr:
                bad_snippet_prov += 1
                break
        comps = pack.get("concrete_comparisons") or []
        if not isinstance(comps, list) or len([c for c in comps if isinstance(c, dict)]) < min_comparisons:
            weak_comparisons += 1
            continue
        required_blocks = ["definitions_setup", "claim_candidates", "concrete_comparisons", "evaluation_protocol", "failures_limitations"]
        for name in required_blocks:
            block = pack.get(name)
            if not isinstance(block, list) or not block:
                bad += 1
                break
        else:
            eval_block = pack.get("evaluation_protocol") or []
            if not isinstance(eval_block, list) or len([x for x in eval_block if isinstance(x, dict)]) < min_eval:
                weak_eval += 1
                continue
            fail_block = pack.get("failures_limitations") or []
            if not isinstance(fail_block, list) or len([x for x in fail_block if isinstance(x, dict)]) < min_fail:
                weak_fail += 1
                continue
            cited: set[str] = set()
            for name in required_blocks:
                for item in pack.get(name) or []:
                    if not isinstance(item, dict):
                        continue
                    cited |= _collect_keys(item.get("citations"))
            if bib_keys:
                missing = [k for k in cited if k not in bib_keys]
                if missing:
                    missing_bib += 1
                    continue
    if blocking_missing:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_blocking_missing",
                message=f"{blocking_missing} evidence pack(s) declare `blocking_missing`; enrich evidence (abstract/fulltext/meta) and complete packs before writing.",
            )
        )
    if missing_snippets:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_missing_snippets",
                message=f"{missing_snippets} evidence pack(s) have too few `evidence_snippets` (<{min_snippets}); enrich paper notes/evidence bank before writing.",
            )
        )
    if bad_snippet_prov:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_bad_snippet_provenance",
                message=f"{bad_snippet_prov} evidence pack(s) have evidence snippets missing provenance `source/pointer`; fix evidence-draft provenance fields.",
            )
        )
    if weak_comparisons:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_too_few_comparisons",
                message=f"{weak_comparisons} evidence pack(s) have <{min_comparisons} concrete comparisons; expand comparisons per subsection before writing.",
            )
        )
    if weak_eval:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_thin_evaluation_protocol",
                message=f"{weak_eval} evidence pack(s) have <{min_eval} evaluation protocol items; add cite-backed protocol anchors (task/metric/constraint) before writing.",
            )
        )
    if weak_fail:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_thin_failures_limitations",
                message=f"{weak_fail} evidence pack(s) have <{min_fail} failures/limitations items; add cite-backed caveats so prose does not overclaim.",
            )
        )
    if missing_bib:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_bad_citations",
                message=f"{missing_bib} evidence pack(s) cite keys missing from `citations/ref.bib`; fix citation keys or regenerate bib.",
            )
        )
    if bad:
        issues.append(
            NativeQualityIssue(
                code="evidence_drafts_incomplete",
                message=f"`{out_rel}` has {bad} invalid pack(s) (missing required blocks or missing sub_id/title).",
            )
        )
    return issues


def _check_sp_evidence_selfloop(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    report_rel = next(
        (path for path in outputs if path.endswith("EVIDENCE_SELFLOOP_TODO.md")),
        "output/EVIDENCE_SELFLOOP_TODO.md",
    )
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_evidence_selfloop_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    status_match = re.search(r"(?im)^-\s*Status:\s*(PASS|OK|FAIL)\s*$", report)
    recorded_status = status_match.group(1).upper() if status_match else ""
    if not recorded_status:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_status_missing",
                message=f"`{report_rel}` must declare `- Status: PASS`, `OK`, or `FAIL`.",
            )
        ]
    required = (
        workspace / "outline" / "subsection_briefs.jsonl",
        workspace / "outline" / "evidence_bindings.jsonl",
        workspace / "outline" / "evidence_drafts.jsonl",
    )
    missing = [
        str(path.relative_to(workspace))
        for path in required
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_inputs_missing",
                message=f"Evidence self-loop inputs are missing or empty: {', '.join(missing)}.",
            )
        ]
    try:
        briefs = _read_jsonl(workspace / "outline" / "subsection_briefs.jsonl")
        bindings = _read_jsonl(workspace / "outline" / "evidence_bindings.jsonl")
        drafts = _read_jsonl(workspace / "outline" / "evidence_drafts.jsonl")
    except (json.JSONDecodeError, OSError) as exc:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_inputs_invalid",
                message=f"Evidence self-loop inputs are not readable JSONL: {type(exc).__name__}: {exc}.",
            )
        ]

    def inspect_records(records, *, list_field=None):
        ids: list[str] = []
        problems: list[str] = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                problems.append(f"record {index} is not an object")
                continue
            sub_id = str(record.get("sub_id") or "").strip()
            if not sub_id:
                problems.append(f"record {index} has no sub_id")
            else:
                ids.append(sub_id)
            if list_field and not isinstance(record.get(list_field), list):
                problems.append(f"{sub_id or f'record {index}'}.{list_field} is not a list")
        duplicates = sorted({sub_id for sub_id in ids if ids.count(sub_id) > 1})
        if duplicates:
            problems.append("duplicate sub_id values: " + ", ".join(duplicates))
        return set(ids), problems

    brief_ids, brief_problems = inspect_records(briefs)
    binding_ids, binding_problems = inspect_records(bindings, list_field="binding_gaps")
    draft_ids, draft_problems = inspect_records(drafts, list_field="blocking_missing")
    schema_problems = brief_problems + binding_problems + draft_problems
    if schema_problems:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_inputs_invalid",
                message="Evidence self-loop records violate their schema: " + "; ".join(schema_problems) + ".",
            )
        ]
    if not brief_ids or brief_ids != binding_ids or brief_ids != draft_ids:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_coverage_mismatch",
                message=(
                    "Subsection IDs must match exactly across briefs, bindings, and drafts; "
                    f"briefs={sorted(brief_ids)}, bindings={sorted(binding_ids)}, drafts={sorted(draft_ids)}."
                ),
            )
        ]
    blocking_count = sum(
        1
        for record in drafts
        if any(str(item or "").strip() for item in record["blocking_missing"])
    )
    gap_count = sum(
        1
        for record in bindings
        if any(str(item or "").strip() for item in record["binding_gaps"])
    )
    expected_status = "FAIL" if blocking_count else "OK" if gap_count else "PASS"
    if expected_status == "FAIL":
        return [
            NativeQualityIssue(
                code="evidence_selfloop_blocked",
                message=(
                    f"{blocking_count} evidence pack(s) still declare `blocking_missing`; "
                    "repair C2/C3/C4 evidence before writing."
                ),
            )
        ]
    if recorded_status != expected_status:
        return [
            NativeQualityIssue(
                code="evidence_selfloop_status_stale",
                message=(
                    f"`{report_rel}` records {recorded_status}, but current evidence requires "
                    f"{expected_status} (binding gaps={gap_count}). Rerun `evidence-selfloop`."
                ),
            )
        ]
    if expected_status == "OK":
        missing_repairs: list[str] = []
        for record in bindings:
            sub_id = str(record.get("sub_id") or "").strip()
            gaps = [str(item or "").strip() for item in record["binding_gaps"] if str(item or "").strip()]
            if not gaps:
                continue
            section_match = re.search(
                rf"(?ims)^###\s+{re.escape(sub_id)}(?:\s+[^\n]*)?$\n(?P<body>.*?)(?=^###\s+|^##\s+|\Z)",
                report,
            )
            section = section_match.group("body") if section_match else ""
            if not section:
                missing_repairs.append(f"{sub_id}: subsection TODO")
                continue
            missing_repairs.extend(
                f"{sub_id}: {gap}"
                for gap in gaps
                if gap not in section
            )
            if "Suggested fix path:" not in section or not re.search(r"\bC[34](?:/C[34])?:", section):
                missing_repairs.append(f"{sub_id}: staged Suggested fix path")
        if missing_repairs:
            return [
                NativeQualityIssue(
                    code="evidence_selfloop_repair_plan_missing",
                    message=(
                        f"`{report_rel}` must locate each binding gap and provide its smallest C3/C4 repair path; "
                        "missing=" + "; ".join(missing_repairs[:8]) + "."
                    ),
                )
            ]
    return []


def _check_sp_anchor_sheet(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/anchor_sheet.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_anchor_sheet", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [
            NativeQualityIssue(
                code="empty_anchor_sheet", message=f"`{out_rel}` is empty."
            )
        ]
    if _has_placeholder_markers(raw) or "(placeholder)" in raw.lower():
        return [
            NativeQualityIssue(
                code="anchor_sheet_placeholders",
                message=f"`{out_rel}` contains placeholder markers; regenerate anchors from evidence packs.",
            )
        ]
    records = _read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [
            NativeQualityIssue(
                code="invalid_anchor_sheet", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    profile = policy.pipeline_profile_name(workspace)
    draft_profile = policy.draft_profile(workspace)
    if profile == "arxiv-survey":
        min_anchors = {"course_paper": 6, "deep": 12}.get(draft_profile, 10)
    else:
        min_anchors = 1
    bad = 0
    empty_anchors = 0
    for rec in items:
        sub_id = str(rec.get("sub_id") or "").strip()
        title = str(rec.get("title") or "").strip()
        anchors = rec.get("anchors")
        if not sub_id or not title:
            bad += 1
            continue
        if not isinstance(anchors, list):
            bad += 1
            continue
        if not anchors:
            empty_anchors += 1
            continue
        ok = 0
        for a in anchors:
            if not isinstance(a, dict):
                continue
            if not str(a.get("text") or "").strip():
                continue
            cites = a.get("citations") or []
            if not isinstance(cites, list):
                continue
            has_key = False
            for c in cites:
                s = str(c).strip()
                if not s:
                    continue
                if s.startswith("[@") and s.endswith("]"):
                    s = s[2:-1].strip()
                if s.startswith("@"):
                    s = s[1:].strip()
                if re.search(r"[A-Za-z0-9:_-]+", s):
                    has_key = True
                    break
            if not has_key:
                continue
            ok += 1
        if ok < int(min_anchors):
            bad += 1
    issues: list[NativeQualityIssue] = []
    if empty_anchors:
        issues.append(
            NativeQualityIssue(
                code="anchor_sheet_empty_anchors",
                message=f"`{out_rel}` has {empty_anchors} record(s) with empty anchors; evidence packs may be too thin or anchor extraction failed.",
            )
        )
    if bad:
        issues.append(
            NativeQualityIssue(
                code="anchor_sheet_too_few_anchors",
                message=f"`{out_rel}` has {bad} record(s) with too few cite-backed anchors (<{min_anchors}); strengthen evidence packs and regenerate anchors.",
            )
        )
    return issues


def _check_sp_schema_normalization_report(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "output/SCHEMA_NORMALIZATION_REPORT.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [
            NativeQualityIssue(
                code="missing_schema_normalization_report",
                message=f"`{out_rel}` is missing or empty.",
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [
            NativeQualityIssue(
                code="empty_schema_normalization_report",
                message=f"`{out_rel}` is empty.",
            )
        ]
    if _has_placeholder_markers(text) or "…" in text:
        return [
            NativeQualityIssue(
                code="schema_normalization_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis; fix upstream JSONL artifacts and rerun schema normalization.",
            )
        ]
    m = re.search(r"(?ims)^##\s+Summary\s*\n\s*-\s*Status:\s*(\w+)\b", text)
    if m:
        status = (m.group(1) or "").strip().upper()
        if status == "PASS":
            return []
        return [
            NativeQualityIssue(
                code="schema_normalization_not_pass",
                message=f"`{out_rel}` summary status is {status} (expected PASS).",
            )
        ]
    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []
    return [
        NativeQualityIssue(
            code="schema_normalization_not_pass",
            message=f"`{out_rel}` does not contain a PASS status; check the report and fix schema drift.",
        )
    ]


def _check_sp_writer_context_packs(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/writer_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_writer_context_packs", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [
            NativeQualityIssue(
                code="empty_writer_context_packs", message=f"`{out_rel}` is empty."
            )
        ]
    if _has_placeholder_markers(raw) or "(placeholder)" in raw.lower():
        return [
            NativeQualityIssue(
                code="writer_context_packs_placeholders",
                message=f"`{out_rel}` contains placeholder markers; regenerate after fixing briefs/evidence/anchors.",
            )
        ]
    records = _read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [
            NativeQualityIssue(
                code="invalid_writer_context_packs",
                message=f"`{out_rel}` has no JSON objects.",
            )
        ]
    cutover_issues = _as_native_issues(
        policy.section_first_artifact_issues(workspace, consumer=out_rel)
    )
    cutover_issues.extend(
        _as_native_issues(
            policy.section_first_cutover_issues(
                workspace, consumer=out_rel, require_stable_h3=True
            )
        )
    )
    if cutover_issues:
        return cutover_issues
    outline_path = workspace / "outline" / "outline.yml"
    outline = _st_load_yaml(outline_path) if outline_path.exists() else []
    expected_subs: list[str] = []
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                if sid:
                    expected_subs.append(sid)
    expected = set(expected_subs)
    profile = policy.pipeline_profile_name(workspace)
    draft_profile = policy.draft_profile(workspace)
    if profile == "arxiv-survey":
        min_plan = 5 if draft_profile == "course_paper" else 10
    else:
        min_plan = 4
    seen: set[str] = set()
    bad = 0
    missing_rq: list[str] = []
    missing_thesis: list[str] = []
    missing_axes: list[str] = []
    short_plan: list[str] = []
    empty_anchors: list[str] = []
    sparse_anchors: list[str] = []
    sparse_comparisons: list[str] = []
    empty_eval_proto: list[str] = []
    sparse_lim_hooks: list[str] = []
    missing_allowed_bib: list[str] = []
    missing_synthesis_mode: list[str] = []
    missing_must_use: list[str] = []
    if profile == "arxiv-survey":
        per_subsection = int(policy.per_subsection(workspace))
        if draft_profile == "course_paper":
            min_comparisons = 3
            min_lim_hooks = 2
            min_anchors = 6
        elif draft_profile == "deep":
            min_comparisons = 6
            min_lim_hooks = 3
            min_anchors = 12
        else:
            min_comparisons = 4
            min_lim_hooks = 3
            min_anchors = 10
    else:
        min_comparisons = 1
        min_lim_hooks = 1
        min_anchors = 1
        per_subsection = 0
    for rec in items:
        sub_id = str(rec.get("sub_id") or "").strip()
        title = str(rec.get("title") or "").strip()
        sec_id = str(rec.get("section_id") or "").strip()
        sec_title = str(rec.get("section_title") or "").strip()
        if not sub_id or not title or not sec_id or not sec_title:
            bad += 1
            continue
        if expected and sub_id not in expected:
            bad += 1
            continue
        if sub_id in seen:
            bad += 1
            continue
        seen.add(sub_id)
        rq = str(rec.get("rq") or "").strip()
        thesis = str(rec.get("thesis") or "").strip()
        axes = rec.get("axes") or []
        plan = rec.get("paragraph_plan") or []
        if not rq:
            missing_rq.append(sub_id)
        if not thesis:
            missing_thesis.append(sub_id)
        if not isinstance(axes, list) or not any(str(a).strip() for a in axes):
            missing_axes.append(sub_id)
        if not isinstance(plan, list) or len([p for p in plan if str(p).strip()]) < min_plan:
            short_plan.append(sub_id)
        anchors = rec.get("anchor_facts") or []
        if not isinstance(anchors, list) or len([a for a in anchors if isinstance(a, dict) and str(a.get("text") or "").strip()]) < min_anchors:
            sparse_anchors.append(sub_id)
        comps = rec.get("comparison_cards") or []
        if not isinstance(comps, list) or len([c for c in comps if isinstance(c, dict)]) < min_comparisons:
            sparse_comparisons.append(sub_id)
        eval_proto = rec.get("evaluation_protocol") or []
        if not isinstance(eval_proto, list) or not eval_proto:
            empty_eval_proto.append(sub_id)
        lim_hooks = rec.get("limitation_hooks") or []
        if not isinstance(lim_hooks, list) or len([l for l in lim_hooks if isinstance(l, dict) and str(l.get("excerpt") or l.get("text") or "").strip()]) < min_lim_hooks:
            sparse_lim_hooks.append(sub_id)
        allowed = rec.get("allowed_bibkeys_mapped") or []
        allowed_count = len([k for k in allowed if str(k).strip()]) if isinstance(allowed, list) else 0
        if profile == "arxiv-survey":
            if allowed_count < int(per_subsection):
                missing_allowed_bib.append(sub_id)
        elif allowed_count < 1:
            missing_allowed_bib.append(sub_id)
        mode = str(rec.get("chapter_synthesis_mode") or "").strip()
        if profile == "arxiv-survey" and not mode:
            missing_synthesis_mode.append(sub_id)
        mu = rec.get("must_use")
        if profile == "arxiv-survey" and not isinstance(mu, dict):
            missing_must_use.append(sub_id)
    issues: list[NativeQualityIssue] = []
    if expected and seen != expected:
        missing = sorted([sid for sid in expected if sid not in seen])
        extra = sorted([sid for sid in seen if sid not in expected])
        msg_parts = []
        if missing:
            msg_parts.append(f"missing: {', '.join(missing[:6])}{'...' if len(missing) > 6 else ''}")
        if extra:
            msg_parts.append(f"extra: {', '.join(extra[:6])}{'...' if len(extra) > 6 else ''}")
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_outline_mismatch",
                message=f"`{out_rel}` does not match outline H3 set ({'; '.join(msg_parts) or 'mismatch'}).",
            )
        )
    if bad:
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_invalid_records",
                message=f"`{out_rel}` has {bad} invalid record(s) (missing ids/titles, duplicate sub_id, or not in outline).",
            )
        )
    total = max(1, len(items))
    if missing_rq:
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_rq",
                message=(
                    f"`{out_rel}` has {len(missing_rq)}/{len(items)} record(s) with empty `rq` "
                    f"(e.g., {', '.join(missing_rq[:10])}{'...' if len(missing_rq) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )
    if missing_thesis and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_thesis",
                message=(
                    f"`{out_rel}` has {len(missing_thesis)}/{len(items)} record(s) with empty `thesis` "
                    f"(e.g., {', '.join(missing_thesis[:10])}{'...' if len(missing_thesis) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate so C5 has a central claim per H3."
                ),
            )
        )
    if missing_axes:
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_axes",
                message=(
                    f"`{out_rel}` has {len(missing_axes)}/{len(items)} record(s) with empty `axes` "
                    f"(e.g., {', '.join(missing_axes[:10])}{'...' if len(missing_axes) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )
    if short_plan:
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_short_plan",
                message=(
                    f"`{out_rel}` has {len(short_plan)}/{len(items)} record(s) with too-short `paragraph_plan` (<{min_plan}) "
                    f"(e.g., {', '.join(short_plan[:10])}{'...' if len(short_plan) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )
    if missing_synthesis_mode and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_chapter_synthesis_mode",
                message=(
                    f"Some writer context packs are missing `chapter_synthesis_mode` ({len(missing_synthesis_mode)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_synthesis_mode[:10])}{'...' if len(missing_synthesis_mode) > 10 else ''}); "
                    "fix `chapter-briefs` and regenerate."
                ),
            )
        )
    if missing_must_use and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_must_use",
                message=(
                    f"Some writer context packs are missing `must_use` contract ({len(missing_must_use)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_must_use[:10])}{'...' if len(missing_must_use) > 10 else ''}); "
                    "regenerate `writer-context-pack` so C5 has explicit minima (anchors/comparisons/limitations)."
                ),
            )
        )
    if sparse_anchors and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_sparse_anchors",
                message=(
                    f"Some writer context packs have too few `anchor_facts` (<{min_anchors}) ({len(sparse_anchors)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_anchors[:10])}{'...' if len(sparse_anchors) > 10 else ''}); "
                    "strengthen `anchor-sheet` / evidence packs before drafting."
                ),
            )
        )
    if sparse_comparisons and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_sparse_comparisons",
                message=(
                    f"Some writer context packs have too few `comparison_cards` (<{min_comparisons}) ({len(sparse_comparisons)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_comparisons[:10])}{'...' if len(sparse_comparisons) > 10 else ''}); "
                    "strengthen `evidence-draft` excerpt-level comparisons (with citations) before drafting."
                ),
            )
        )
    if empty_eval_proto and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_eval_protocol",
                message=(
                    f"Some writer context packs lack `evaluation_protocol` ({len(empty_eval_proto)}/{len(items)}) "
                    f"(e.g., {', '.join(empty_eval_proto[:10])}{'...' if len(empty_eval_proto) > 10 else ''}); "
                    "ensure each subsection has at least one cite-backed evaluation anchor in `evidence-draft`."
                ),
            )
        )
    if sparse_lim_hooks and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_limitation_hooks",
                message=(
                    f"Some writer context packs have too few `limitation_hooks` (<{min_lim_hooks}) ({len(sparse_lim_hooks)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_lim_hooks[:10])}{'...' if len(sparse_lim_hooks) > 10 else ''}); "
                    "ensure each subsection has cite-backed limitations/failure modes in `evidence-draft` / `anchor-sheet`."
                ),
            )
        )
    if missing_allowed_bib and profile == "arxiv-survey":
        issues.append(
            NativeQualityIssue(
                code="writer_context_packs_missing_allowed_bibkeys",
                message=(
                    f"Some writer context packs have too few `allowed_bibkeys_mapped` (<{per_subsection}) ({len(missing_allowed_bib)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_allowed_bib[:10])}{'...' if len(missing_allowed_bib) > 10 else ''}); "
                    "fix `section-mapper` / `evidence-binder` so each subsection has in-scope citations."
                ),
            )
        )
    if profile != "arxiv-survey":
        if (len(sparse_anchors) / total) >= 0.5:
            issues.append(
                NativeQualityIssue(
                    code="writer_context_packs_sparse_anchors",
                    message=f"Many writer context packs lack `anchor_facts` ({len(sparse_anchors)}/{len(items)}); strengthen `anchor-sheet` / evidence packs before drafting.",
                )
            )
        if (len(sparse_comparisons) / total) >= 0.5:
            issues.append(
                NativeQualityIssue(
                    code="writer_context_packs_sparse_comparisons",
                    message=f"Many writer context packs lack `comparison_cards` ({len(sparse_comparisons)}/{len(items)}); strengthen `evidence-draft` concrete comparisons before drafting.",
                )
            )
    return issues


def _check_sp_evidence_bindings(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/evidence_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/evidence_binding_report.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            NativeQualityIssue(
                code="missing_evidence_bindings", message=f"`{out_rel}` does not exist."
            )
        ]
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return [
            NativeQualityIssue(
                code="empty_evidence_bindings", message=f"`{out_rel}` is empty."
            )
        ]
    if _has_placeholder_markers(raw) or "…" in raw:
        return [
            NativeQualityIssue(
                code="evidence_bindings_placeholders",
                message=f"`{out_rel}` contains placeholders; regenerate evidence bindings.",
            )
        ]
    records = _read_jsonl(path)
    binds = [r for r in records if isinstance(r, dict)]
    if not binds:
        return [
            NativeQualityIssue(
                code="invalid_evidence_bindings", message=f"`{out_rel}` has no JSON objects."
            )
        ]
    by_sub = {str(r.get("sub_id") or "").strip(): r for r in binds if str(r.get("sub_id") or "").strip()}
    expected: set[str] = set()
    outline_path = workspace / "outline" / "outline.yml"
    if outline_path.exists():
        outline = _st_load_yaml(outline_path) or []
        for sec in outline if isinstance(outline, list) else []:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                if sid:
                    expected.add(sid)
    if expected:
        missing = sorted([sid for sid in expected if sid not in by_sub])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            return [
                NativeQualityIssue(
                    code="evidence_bindings_missing_sections",
                    message=f"`{out_rel}` missing some subsections (e.g., {sample}{suffix}).",
                )
            ]
    bank_path = workspace / "papers" / "evidence_bank.jsonl"
    bank_ids: set[str] = set()
    if bank_path.exists():
        for it in _read_jsonl(bank_path):
            if isinstance(it, dict):
                eid = str(it.get("evidence_id") or "").strip()
                if eid:
                    bank_ids.add(eid)
    profile = policy.pipeline_profile_name(workspace)
    draft_profile = policy.draft_profile(workspace)
    per_subsection = int(policy.per_subsection(workspace)) if profile == "arxiv-survey" else 0
    min_mapped = per_subsection if per_subsection else 0
    if profile == "arxiv-survey" and draft_profile == "course_paper":
        min_ids = max(6, per_subsection - 2) if per_subsection else 6
        min_selected = max(6, int(round(per_subsection * 0.70))) if per_subsection else 6
        min_distinct_papers = max(4, int(min_ids) - 2)
    else:
        min_ids = max(10, per_subsection - 4) if per_subsection else (10 if profile == "arxiv-survey" else 6)
        min_selected = max(12, int(round(per_subsection * 0.70))) if per_subsection else (12 if profile == "arxiv-survey" else 6)
        min_distinct_papers = max(10, int(min_ids) - 6) if profile == "arxiv-survey" else 0
    bad = 0
    missing_bank = 0
    bad_samples: list[str] = []
    for sid, rec in by_sub.items():
        title = str(rec.get("title") or "").strip()
        eids = rec.get("evidence_ids") or []
        eid_count = len([e for e in eids if str(e).strip()]) if isinstance(eids, list) else 0
        mapped = rec.get("mapped_bibkeys") or []
        mapped_count = len([k for k in mapped if str(k).strip()]) if isinstance(mapped, list) else 0
        selected = rec.get("bibkeys") or []
        selected_count = len([k for k in selected if str(k).strip()]) if isinstance(selected, list) else 0
        paper_ids = rec.get("paper_ids") or []
        pids = set([str(p).strip() for p in paper_ids if str(p).strip()]) if isinstance(paper_ids, list) else set()
        if isinstance(eids, list):
            for e in eids:
                m = re.match(r"^E-(P\\d+)-", str(e or "").strip())
                if m:
                    pids.add(m.group(1))
        if (
            not title
            or not isinstance(eids, list)
            or eid_count < int(min_ids)
            or (min_mapped and mapped_count < int(min_mapped))
            or (min_selected and selected_count < int(min_selected))
            or (min_distinct_papers and len(pids) < int(min_distinct_papers))
        ):
            bad += 1
            bad_samples.append(
                f"{sid}(eids={eid_count}, mapped={mapped_count}, selected={selected_count}, papers={len(pids)})"
            )
            continue
        if bank_ids and any(str(e).strip() and str(e).strip() not in bank_ids for e in eids):
            missing_bank += 1
    if bad:
        bad_samples.sort()
        sample = ", ".join(bad_samples[:8])
        suffix = "..." if len(bad_samples) > 10 else ""
        return [
            NativeQualityIssue(
                code="evidence_bindings_incomplete",
                message=(
                    f"`{out_rel}` has {bad} record(s) failing binding density (need mapped>={min_mapped}, "
                    f"selected>={min_selected}, evidence_ids>={min_ids}, distinct_papers>={min_distinct_papers}). "
                    f"Examples: {sample}{suffix}. "
                    "Fix mapping (breadth/diversity) and rerun binder; do not rely on prose to compensate for thin bindings."
                ),
            )
        ]
    if missing_bank:
        return [
            NativeQualityIssue(
                code="evidence_bindings_missing_bank_ids",
                message=f"`{out_rel}` references evidence_ids not found in `papers/evidence_bank.jsonl` ({missing_bank} subsection(s)).",
            )
        ]
    report_path = workspace / report_rel
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
        if report and (_has_placeholder_markers(report) or "…" in report):
            return [
                NativeQualityIssue(
                    code="evidence_binding_report_placeholders",
                    message=f"`{report_rel}` contains placeholders; regenerate binder report.",
                )
            ]
    return []


def _check_sp_survey_visuals(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    tables_rel: str | None
    timeline_rel: str
    figures_rel: str
    if outputs and len(outputs) == 2:
        tables_rel = None
        timeline_rel = outputs[0]
        figures_rel = outputs[1]
    else:
        tables_rel = outputs[0] if outputs else "outline/tables_index.md"
        timeline_rel = outputs[1] if len(outputs) >= 2 else "outline/timeline.md"
        figures_rel = outputs[2] if len(outputs) >= 3 else "outline/figures.md"
    issues: list[NativeQualityIssue] = []

    def _read(rel: str) -> str | None:
        path = workspace / rel
        if not path.exists():
            issues.append(NativeQualityIssue(code="missing_visuals_file", message=f"`{rel}` does not exist."))
            return None
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            issues.append(NativeQualityIssue(code="empty_visuals_file", message=f"`{rel}` is empty."))
            return None
        if "<!-- SCAFFOLD" in text:
            issues.append(NativeQualityIssue(code="visuals_scaffold", message=f"`{rel}` still contains scaffold markers."))
        if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
            issues.append(NativeQualityIssue(code="visuals_todo", message=f"`{rel}` still contains placeholder markers (TODO/TBD/FIXME)."))
        if "…" in text:
            issues.append(
                NativeQualityIssue(
                    code="visuals_contains_ellipsis",
                    message=f"`{rel}` contains unicode ellipsis (`…`), which usually indicates truncated scaffold text; rewrite into concrete table/timeline/figure content.",
                )
            )
        if re.search(r"\[@(?:Key|KEY)\d+", text):
            issues.append(NativeQualityIssue(code="visuals_placeholder_cites", message=f"`{rel}` contains placeholder cite keys like `[@Key1]`."))
        return text

    tables = _read(tables_rel) if tables_rel is not None else None
    timeline = _read(timeline_rel)
    figures = _read(figures_rel)
    if tables is not None:
        table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", tables)
        if len(table_seps) < 2:
            issues.append(
                NativeQualityIssue(
                    code="visuals_missing_tables",
                    message=f"`{tables_rel}` should contain at least 2 Markdown tables (found {len(table_seps)}).",
                )
            )
        if "[@" not in tables:
            issues.append(
                NativeQualityIssue(
                    code="visuals_tables_no_cites",
                    message=f"`{tables_rel}` should include citations in table rows (e.g., `[@BibKey]`).",
                )
            )
    if timeline is not None:
        bullets = [ln.strip() for ln in timeline.splitlines() if ln.strip().startswith("- ")]
        year_bullets = [ln for ln in bullets if re.search(r"\b20\d{2}\b", ln)]
        cited = [ln for ln in year_bullets if "[@" in ln]
        if len(year_bullets) < 8:
            issues.append(
                NativeQualityIssue(
                    code="visuals_timeline_too_short",
                    message=f"`{timeline_rel}` should include >=8 year bullets (found {len(year_bullets)}).",
                )
            )
        if year_bullets and len(cited) / len(year_bullets) < 0.8:
            issues.append(
                NativeQualityIssue(
                    code="visuals_timeline_sparse_cites",
                    message=f"Most timeline bullets should include citations (>=80%); currently {len(cited)}/{len(year_bullets)}.",
                )
            )
    if figures is not None:
        fig_lines = [ln.strip() for ln in figures.splitlines() if ln.strip().lower().startswith(("- figure", "- fig"))]
        if len(fig_lines) < 2:
            issues.append(
                NativeQualityIssue(
                    code="visuals_missing_figures",
                    message=f"`{figures_rel}` should include >=2 figure specs (lines starting with `- Figure ...`).",
                )
            )
        if "[@" not in figures:
            issues.append(
                NativeQualityIssue(
                    code="visuals_figures_no_cites",
                    message=f"`{figures_rel}` should mention supporting works with citations (e.g., `[@BibKey]`).",
                )
            )
    return issues


def _check_sp_table_schema(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/table_schema.md"
    path = workspace / out_rel
    if not path.exists():
        return [NativeQualityIssue(code="missing_table_schema", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [NativeQualityIssue(code="empty_table_schema", message=f"`{out_rel}` is empty.")]
    if _has_placeholder_markers(text) or "…" in text:
        return [NativeQualityIssue(code="table_schema_placeholders", message=f"`{out_rel}` contains placeholders; fill schema with real table definitions.")]
    n = len(re.findall(r"(?m)^##\s+Table\s+[IA]\d+:", text))
    min_tables = 2 if policy.draft_profile(workspace) == "course_paper" else 4
    if n < min_tables:
        return [NativeQualityIssue(code="table_schema_too_few", message=f"`{out_rel}` should define >={min_tables} tables across the index and Appendix layers (found {n}).")]
    return []


def _check_sp_tables_index(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_index.md"
    path = workspace / out_rel
    if not path.exists():
        return [NativeQualityIssue(code="missing_tables_md", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [NativeQualityIssue(code="empty_tables_md", message=f"`{out_rel}` is empty.")]
    if _has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            NativeQualityIssue(
                code="tables_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis (including `...` truncation); fill tables from evidence packs and remove truncation markers.",
            )
        ]
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    min_tables = 1 if policy.draft_profile(workspace) == "course_paper" else 2
    if len(table_seps) < min_tables:
        return [NativeQualityIssue(code="tables_missing", message=f"`{out_rel}` should contain >={min_tables} Markdown tables (found {len(table_seps)}).")]
    if "[@" not in text:
        return [NativeQualityIssue(code="tables_no_cites", message=f"`{out_rel}` should include citations in table rows (e.g., `[@BibKey]`).")]
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return [NativeQualityIssue(code="tables_placeholder_cites", message=f"`{out_rel}` contains placeholder cite keys like `[@Key1]`.")]
    return []


def _check_sp_tables_appendix(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_appendix.md"
    expected_report = any(p.endswith("TABLES_APPENDIX_REPORT.md") for p in (outputs or []))
    report_rel = next((p for p in outputs if p.endswith("TABLES_APPENDIX_REPORT.md")), "output/TABLES_APPENDIX_REPORT.md")
    path = workspace / out_rel
    if not path.exists():
        return [NativeQualityIssue(code="missing_tables_appendix", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [NativeQualityIssue(code="empty_tables_appendix", message=f"`{out_rel}` is empty.")]
    if _has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            NativeQualityIssue(
                code="tables_appendix_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis (including `...` truncation); curate clean Appendix tables and remove truncation markers.",
            )
        ]
    if any(ln.lstrip().startswith("#") for ln in text.splitlines() if ln.strip()):
        return [
            NativeQualityIssue(
                code="tables_appendix_contains_headings",
                message=f"`{out_rel}` should not contain Markdown headings; keep it heading-free so the merger can insert it cleanly under a single Appendix heading.",
            )
        ]
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    min_tables = 1 if policy.draft_profile(workspace) == "course_paper" else 2
    if len(table_seps) < min_tables:
        return [NativeQualityIssue(code="tables_appendix_missing", message=f"`{out_rel}` should contain >={min_tables} Markdown tables (found {len(table_seps)}).")]
    if "[@" not in text:
        return [NativeQualityIssue(code="tables_appendix_no_cites", message=f"`{out_rel}` should include citations in table rows (e.g., `[@BibKey]`).")]
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return [NativeQualityIssue(code="tables_appendix_placeholder_cites", message=f"`{out_rel}` contains placeholder cite keys like `[@Key1]`.")]
    if re.search(r"(?im)^\|\s*subsection\s*\|", text) and re.search(r"(?im)\|\s*axes\s*\|", text):
        return [
            NativeQualityIssue(
                code="tables_appendix_looks_indexy",
                message=f"`{out_rel}` looks like an internal subsection/axes index table; curate reader-facing Appendix tables (methods/benchmarks/risks) instead of pasting the index.",
            )
        ]
    report_path = workspace / report_rel
    if expected_report:
        if not report_path.exists() or report_path.stat().st_size == 0:
            return [NativeQualityIssue(code="missing_tables_appendix_report", message=f"`{report_rel}` is missing or empty.")]
        rep = report_path.read_text(encoding="utf-8", errors="ignore")
        if "- Status: PASS" not in rep:
            return [NativeQualityIssue(code="tables_appendix_report_not_pass", message=f"`{report_rel}` is not PASS; fix Appendix tables and rerun `appendix-table-writer`.")]
    return []


def _check_sp_transitions(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    out_rel = outputs[0] if outputs else "outline/transitions.md"
    path = workspace / out_rel
    if not path.exists():
        return [NativeQualityIssue(code="missing_transitions", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [NativeQualityIssue(code="empty_transitions", message=f"`{out_rel}` is empty.")]
    if _has_placeholder_markers(text) or "…" in text:
        return [NativeQualityIssue(code="transitions_placeholders", message=f"`{out_rel}` contains placeholders; rewrite transitions into concrete, title/RQ-driven sentences.")]
    banned = [
        (r"(?i)\bafter\b[^\n]{0,180}\bmakes\s+the\s+bridge\s+explicit\s+via\b", "transitions_planner_talk_after_via"),
        (r"(?i)\bfollows\s+naturally\s+by\s+turning\b", "transitions_planner_talk_turning"),
        (r"(?i)\bthe\s+remaining\s+uncertainty\s+is\b", "transitions_planner_talk_remaining_uncertainty"),
        (r"(?i)\bto\s+keep\s+the\s+chapter(?:'|’)?s\b", "transitions_planner_talk_keep_chapter"),
    ]
    for pat, code in banned:
        if re.search(pat, text):
            return [
                NativeQualityIssue(
                    code=code,
                    message=(
                        f"`{out_rel}` contains planner-talk transition phrasing ({code}); "
                        "rewrite transitions into content argument bridges (no construction notes)."
                    ),
                )
            ]
    if re.search(r"(?m)^-\s+[^:\n]{1,80}:\s+[^\n]*;\s*[^\n]+", text):
        return [
            NativeQualityIssue(
                code="transitions_semicolon_enumeration",
                message=(
                    f"`{out_rel}` contains semicolon-style enumerations; "
                    "rewrite each transition as a single content sentence (no list-like construction notes)."
                ),
            )
        ]
    if re.search(
        r"\b[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\b",
        text,
    ):
        return [
            NativeQualityIssue(
                code="transitions_slash_list_axes",
                message=(
                    f"`{out_rel}` contains slash-list axis markers (A/B/C); "
                    "rewrite into natural prose (use 'and/or', avoid axis-label strings)."
                ),
            )
        ]
    if "[@" in text:
        return [
            NativeQualityIssue(
                code="transitions_has_citations",
                message=f"`{out_rel}` contains citation markers; transitions must not introduce new citations.",
            )
        ]
    if re.search(r"(?i)\bwhat\s+are\s+the\s+main\s+approaches\b", text):
        return [
            NativeQualityIssue(
                code="transitions_scaffold_questions",
                message=(
                    f"`{out_rel}` contains template RQ phrasing ('What are the main approaches...'); "
                    "rewrite transitions into short, paper-like handoffs (no explicit RQ questions)."
                ),
            )
        ]
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    expected_h3 = 0
    try:
        outline_path = workspace / "outline" / "outline.yml"
        if outline_path.exists():
            outline = _st_load_yaml(outline_path)
            if isinstance(outline, list):
                for sec in outline:
                    if not isinstance(sec, dict):
                        continue
                    subs = sec.get("subsections") or []
                    if isinstance(subs, list) and len(subs) >= 2:
                        expected_h3 += (len(subs) - 1)
    except Exception:
        expected_h3 = 0
    h3_bullets = [
        ln
        for ln in bullets
        if re.search(r"^\-\s*\d+\.\d+\s*(?:→|->)\s*\d+\.\d+\s*:", ln.strip())
    ]
    if expected_h3 and len(h3_bullets) < expected_h3:
        return [
            NativeQualityIssue(
                code="transitions_too_short",
                message=(
                    f"`{out_rel}` has too few within-chapter H3→H3 transitions "
                    f"(found={len(h3_bullets)}, expected>={expected_h3} from `outline/outline.yml`)."
                ),
            )
        ]
    rep = _sx_repeated_template_text(text=text, min_len=60, min_repeats=8)
    if rep:
        example, count = rep
        return [
            NativeQualityIssue(
                code="transitions_repeated_text",
                message=f"`{out_rel}` contains repeated transition boilerplate ({count}×), e.g., `{example}`; rewrite to be more subsection-specific.",
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
    "chapter-skeleton": _check_chapter_skeleton,
    "section-bindings": _check_section_bindings,
    "section-briefs": _check_section_briefs,
    "writer-selfloop": _check_writer_selfloop,
    "front-matter-writer": _check_front_matter_writer,
    "evaluation-anchor-checker": _check_eval_anchor_report,
    "paragraph-curator": _check_paragraph_curator,
    "argument-selfloop": _check_argument_snapshot,
    "subsection-writer": _check_sections_manifest_index,
    "prose-writer": _sw_check_draft,
    "draft-polisher": _check_draft_polisher,
    "section-logic-polisher": _check_section_logic_polisher,
    "section-merger": _check_merge_report,
    "pipeline-auditor": _check_audit_report,
    "global-reviewer": _check_global_review,
    "taxonomy-builder": _check_sp_taxonomy,
    "outline-builder": _check_sp_outline,
    "section-mapper": _check_sp_mapping,
    "paper-notes": _check_sp_paper_notes,
    "claim-evidence-matrix": _check_sp_claim_evidence_matrix,
    "claim-matrix-rewriter": _check_sp_claim_evidence_matrix,
    "subsection-briefs": _check_sp_subsection_briefs,
    "chapter-briefs": _check_sp_chapter_briefs,
    "outline-refiner": _check_sp_coverage_report,
    "evidence-draft": _check_sp_evidence_drafts,
    "evidence-selfloop": _check_sp_evidence_selfloop,
    "anchor-sheet": _check_sp_anchor_sheet,
    "schema-normalizer": _check_sp_schema_normalization_report,
    "writer-context-pack": _check_sp_writer_context_packs,
    "evidence-binder": _check_sp_evidence_bindings,
    "survey-visuals": _check_sp_survey_visuals,
    "table-schema": _check_sp_table_schema,
    "table-filler": _check_sp_tables_index,
    "appendix-table-writer": _check_sp_tables_appendix,
    "transition-weaver": _check_sp_transitions,
}

_NATIVE_POLICY_CHECKS: frozenset[str] = frozenset(_NATIVE_POLICY_UNIT_CHECKS)


# --- native completion invariants ------------------------------------------
#
# The single registered completion invariant (``outline-refiner``) guards on
# the declared ``outline/outline_state.jsonl`` output and then runs the
# section-first cutover gate.  That gate already runs behind the
# ``WorkspacePolicyPort`` (the default reader delegates to
# ``tooling.quality_checks.survey_structure``, so the resolved issues are
# byte-identical by construction); only the output-declaration guard is
# reimplemented here.  ``_NATIVE_COMPLETION_INVARIANTS`` (the routing set used
# by ``has_completion_invariant``) is derived from this table so the two never
# drift.


def _check_completion_outline_refiner(
    workspace: Path, outputs: list[str], policy: WorkspacePolicyPort
) -> list[NativeQualityIssue]:
    """Native reimplementation of the ``outline-refiner`` completion invariant.

    Mirrors ``tooling.quality_gate._check_outline_cutover`` exactly: a no-op
    unless the run declared ``outline/outline_state.jsonl``, in which case it
    runs the section-first cutover gate for that consumer.  Exceptions from the
    gate propagate unchanged -- the legacy path has no try/except wrapper
    either.
    """

    if "outline/outline_state.jsonl" not in outputs:
        return []
    return _as_native_issues(
        policy.section_first_cutover_issues(
            workspace,
            consumer="outline/outline_state.jsonl",
            require_stable_h3=True,
        )
    )


_NATIVE_COMPLETION_INVARIANT_CHECKS: dict[str, _NativePolicyCheck] = {
    "outline-refiner": _check_completion_outline_refiner,
}

_NATIVE_COMPLETION_INVARIANTS: frozenset[str] = frozenset(
    _NATIVE_COMPLETION_INVARIANT_CHECKS
)


@dataclass(frozen=True)
class NativeQualityProvider(QualityCheckProvider):
    """Composition provider: native registry + native checks, else legacy.

    - :meth:`registered_quality_skills` / :meth:`has_completion_invariant`
      answer from native constant tables, with no ``tooling`` import.
    - :meth:`check_unit_outputs` handles the self-contained native Skills (via
      ``_NATIVE_UNIT_CHECKS``) and the policy-consuming native Skills (via
      ``_NATIVE_POLICY_UNIT_CHECKS``, passing the injected ``policy``), and
      delegates every other Skill to the composed legacy adapter.
    - :meth:`check_completion_invariants` handles the ``outline-refiner``
      invariant natively (via ``_NATIVE_COMPLETION_INVARIANT_CHECKS``) and
      delegates every other Skill to the composed legacy adapter.

    ``policy`` is the injected :class:`WorkspacePolicyPort` the policy-consuming
    native checks read workspace policy (run profile, evidence mode, core-set
    target, quality contract, Goal page-range, and the heavyweight evaluators)
    through.  It defaults to the legacy reader so resolved policy values are
    byte-identical by construction; every policy-consuming family (survey
    retrieval, delivery, research idea, paper/evidence review, survey
    structure/writing/planning) consumes it, so the seam is load-bearing rather
    than merely constructed.
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
        invariant = _NATIVE_COMPLETION_INVARIANT_CHECKS.get(skill)
        if invariant is not None:
            return list(invariant(workspace, outputs, self.policy))
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
