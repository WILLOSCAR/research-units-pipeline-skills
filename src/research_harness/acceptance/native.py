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
- reimplements the *policy-consuming* output checks of the survey-retrieval
  family in full -- ``citation-verifier``, ``arxiv-search``,
  ``pdf-text-extractor``, ``literature-engineer``, and ``dedupe-rank`` -- which
  read workspace policy (run profile, evidence mode, core-set target, and the
  retrieval / candidate-pool contracts) through the injected
  :class:`WorkspacePolicyPort` rather than importing
  ``tooling.quality_checks.survey_policy`` / ``tooling.common``.  With these,
  every check in ``tooling.quality_checks.survey_retrieval`` has a native
  equivalent, exercising the policy seam for real instead of leaving it merely
  constructed.

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
    runtime behavior is unchanged; the whole survey-retrieval family
    (``citation-verifier``, ``arxiv-search``, ``pdf-text-extractor``,
    ``literature-engineer``, ``dedupe-rank``) consumes it, so the seam is
    load-bearing rather than merely constructed.
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
