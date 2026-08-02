from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tooling.quality_checks.common import QualityIssue


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAX_RATIO = 0.10
DEFAULT_MIN_LITERAL_CHARS = 24
MEASUREMENT_SCHEMA = "template-residue-measurement.v1"
SCORECARD_SCHEMA = "template-residue-scorecard.v1"
FRONT_MATTER_CONTEXT_PATH = "output/FRONT_MATTER_CONTEXT.json"
TEMPLATE_ASSETS_BY_SKILL = {
    "front-matter-writer": (
        REPO_ROOT / ".codex" / "skills" / "front-matter-writer" / "assets" / "front_matter_templates.json",
        REPO_ROOT
        / ".codex"
        / "skills"
        / "front-matter-writer"
        / "assets"
        / "domain_templates"
        / "llm_agents.json",
    ),
    "chapter-lead-writer": (
        REPO_ROOT
        / ".codex"
        / "skills"
        / "chapter-lead-writer"
        / "assets"
        / "lead_block_compatibility_defaults.json",
    ),
    "subsection-writer": (
        REPO_ROOT
        / ".codex"
        / "skills"
        / "subsection-writer"
        / "assets"
        / "paragraph_job_templates.json",
        REPO_ROOT
        / ".codex"
        / "skills"
        / "subsection-writer"
        / "assets"
        / "bootstrap_paragraph_templates.json",
    ),
}
DEFAULT_TEMPLATE_ASSETS = tuple(
    path
    for skill_assets in TEMPLATE_ASSETS_BY_SKILL.values()
    for path in skill_assets
)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _template_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _template_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _template_strings(child)]
    return []


def _load_template_fragments(
    *,
    asset_paths: tuple[Path, ...],
    min_literal_chars: int,
) -> tuple[list[dict[str, str]], int, list[str]]:
    fragments_by_text: dict[str, dict[str, str]] = {}
    template_string_count = 0
    missing_assets: list[str] = []
    for path in asset_paths:
        if not path.is_file():
            missing_assets.append(_display_path(path))
            continue
        try:
            strings = _template_strings(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            missing_assets.append(_display_path(path))
            continue
        template_string_count += len(strings)
        owner_skill = _skill_owner(path)
        for template in strings:
            for literal in re.split(r"\{[^{}]+\}", template):
                normalized = re.sub(r"\s+", " ", literal).strip(" \t\r\n.,;:!?-").casefold()
                if len(normalized) < min_literal_chars:
                    continue
                fragments_by_text.setdefault(
                    normalized,
                    {
                        "literal_fragment": normalized,
                        "template_asset": _display_path(path),
                        "template_owner_skill": owner_skill,
                    },
                )
    fragments = sorted(
        fragments_by_text.values(),
        key=lambda item: (-len(item["literal_fragment"]), item["literal_fragment"]),
    )
    return fragments, template_string_count, missing_assets


def _skill_owner(path: Path) -> str:
    parts = path.parts
    try:
        skill_index = parts.index("skills") + 1
    except ValueError:
        return "unknown"
    return parts[skill_index] if skill_index < len(parts) else "unknown"


def _section_kind(*, heading_level: int, heading: str) -> tuple[str, str]:
    normalized = re.sub(r"[^a-z]+", " ", heading.casefold()).strip()
    if heading_level >= 3:
        return "h3_body", "subsection-writer"
    if normalized in {
        "abstract",
        "introduction",
        "related work",
        "discussion",
        "conclusion",
    }:
        return "front_matter", "front-matter-writer"
    if heading_level == 2:
        return "h2_lead", "chapter-lead-writer"
    return "unclassified", "unknown"


def _sentences(text: str) -> list[dict[str, Any]]:
    """Split English or CJK prose while retaining the nearest Markdown heading."""

    records: list[dict[str, Any]] = []
    heading = ""
    heading_level = 0
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        without_citations = re.sub(r"\[@[^\]]+\]", "", "\n".join(block))
        section_kind, owner_skill = _section_kind(
            heading_level=heading_level,
            heading=heading,
        )
        for candidate in re.split(
            r"(?<=[.!?])\s+|(?<=[\u3002\uff01\uff1f])\s*",
            without_citations,
        ):
            normalized = re.sub(r"\s+", " ", candidate).strip()
            if not normalized or not any(character.isalpha() for character in normalized):
                continue
            records.append(
                {
                    "sentence": normalized,
                    "heading": heading,
                    "heading_level": heading_level,
                    "section_kind": section_kind,
                    "section_owner_skill": owner_skill,
                }
            )
        block.clear()

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            heading_level = len(match.group(1))
            heading = match.group(2).strip()
            continue
        block.append(line)
    flush()
    return records


def measure_template_residue(
    *,
    documents: list[tuple[str, str]],
    asset_paths: tuple[Path, ...] = DEFAULT_TEMPLATE_ASSETS,
    min_literal_chars: int = DEFAULT_MIN_LITERAL_CHARS,
) -> dict[str, Any]:
    """Measure a reproducible lower bound on deterministic template residue."""

    fragments, template_string_count, missing_assets = _load_template_fragments(
        asset_paths=asset_paths,
        min_literal_chars=min_literal_chars,
    )
    sentence_count = 0
    matches: list[dict[str, Any]] = []
    matched_fragments: set[str] = set()
    for relpath, text in documents:
        for sentence_record in _sentences(text):
            sentence_count += 1
            sentence = str(sentence_record["sentence"])
            normalized = sentence.casefold()
            fragment = next(
                (
                    item
                    for item in fragments
                    if item["literal_fragment"] in normalized
                ),
                None,
            )
            if fragment is None:
                continue
            matched_fragments.add(fragment["literal_fragment"])
            matches.append(
                {
                    "path": relpath,
                    "sentence": sentence,
                    "heading": sentence_record["heading"],
                    "heading_level": sentence_record["heading_level"],
                    "section_kind": sentence_record["section_kind"],
                    "section_owner_skill": sentence_record["section_owner_skill"],
                    **fragment,
                }
            )

    matched_sentence_count = len(matches)
    ratio = matched_sentence_count / sentence_count if sentence_count else 0.0
    return {
        "schema": MEASUREMENT_SCHEMA,
        "method": (
            "Case-insensitive English/CJK sentence match against fixed template fragments after "
            "Markdown headings and citation markers are removed."
        ),
        "min_literal_chars": min_literal_chars,
        "template_assets": [_display_path(path) for path in asset_paths],
        "template_asset_sha256": {
            _display_path(path): _file_sha256(path)
            for path in asset_paths
            if path.is_file()
        },
        "template_string_count": template_string_count,
        "literal_fragment_count": len(fragments),
        "sentence_count": sentence_count,
        "matched_sentence_count": matched_sentence_count,
        "matched_sentence_ratio": round(ratio, 6),
        "matched_literal_fragment_count": len(matched_fragments),
        "missing_assets": missing_assets,
        "examples": matches[:8],
        # Keep the complete, file-addressable repair surface in the scorecard.
        # The Evaluation ledger only projects aggregate metrics, so this does
        # not inflate normal Run inspection output.  A writer can now repair
        # every matched sentence without reverse-engineering the template
        # banks or repeatedly rerunning the gate to discover the next sample.
        "repair_items": matches,
    }


def template_residue_policy(workspace: Path) -> tuple[float, int]:
    from tooling.common import pipeline_quality_contract_value

    threshold_value = pipeline_quality_contract_value(
        workspace,
        "writing_policy",
        "template_residue_max_ratio",
        default=DEFAULT_MAX_RATIO,
    )
    min_chars_value = pipeline_quality_contract_value(
        workspace,
        "writing_policy",
        "template_literal_min_chars",
        default=DEFAULT_MIN_LITERAL_CHARS,
    )
    try:
        threshold = float(threshold_value)
    except (TypeError, ValueError):
        threshold = DEFAULT_MAX_RATIO
    if not 0 <= threshold <= 1:
        threshold = DEFAULT_MAX_RATIO
    try:
        min_literal_chars = int(min_chars_value)
    except (TypeError, ValueError):
        min_literal_chars = DEFAULT_MIN_LITERAL_CHARS
    if min_literal_chars <= 0:
        min_literal_chars = DEFAULT_MIN_LITERAL_CHARS
    return threshold, min_literal_chars


def selected_template_asset_evidence(workspace: Path) -> dict[str, Any]:
    """Resolve the writer template assets selected for this Run."""

    context_path = workspace / FRONT_MATTER_CONTEXT_PATH
    fixed_assets = (
        *TEMPLATE_ASSETS_BY_SKILL["chapter-lead-writer"],
        *TEMPLATE_ASSETS_BY_SKILL["subsection-writer"],
    )
    if not context_path.is_file():
        return {
            "status": "UNAVAILABLE",
            "context_path": FRONT_MATTER_CONTEXT_PATH,
            "assets": list(DEFAULT_TEMPLATE_ASSETS),
            "asset_paths": [_display_path(path) for path in DEFAULT_TEMPLATE_ASSETS],
            "issues": [f"Missing `{FRONT_MATTER_CONTEXT_PATH}` Run provenance."],
        }
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "status": "INVALID",
            "context_path": FRONT_MATTER_CONTEXT_PATH,
            "assets": list(DEFAULT_TEMPLATE_ASSETS),
            "asset_paths": [_display_path(path) for path in DEFAULT_TEMPLATE_ASSETS],
            "issues": [f"Front-matter context is invalid: {type(exc).__name__}."],
        }
    raw_paths = context.get("template_assets") if isinstance(context, dict) else None
    recorded_hashes = context.get("template_asset_sha256") if isinstance(context, dict) else None
    if not isinstance(raw_paths, list) or not raw_paths or not isinstance(recorded_hashes, dict):
        return {
            "status": "LEGACY_UNVERIFIED",
            "context_path": FRONT_MATTER_CONTEXT_PATH,
            "assets": list(DEFAULT_TEMPLATE_ASSETS),
            "asset_paths": [_display_path(path) for path in DEFAULT_TEMPLATE_ASSETS],
            "issues": ["Front-matter context does not declare selected template assets and hashes."],
        }

    front_assets: list[Path] = []
    issues: list[str] = []
    allowed_root = (
        REPO_ROOT / ".codex" / "skills" / "front-matter-writer" / "assets"
    ).resolve()
    for raw_path in raw_paths:
        relpath = str(raw_path or "").strip()
        candidate = (REPO_ROOT / relpath).resolve()
        try:
            candidate.relative_to(allowed_root)
        except ValueError:
            issues.append(f"Selected template path is outside front-matter-writer assets: {relpath or '<blank>'}.")
            continue
        if not candidate.is_file():
            issues.append(f"Selected template asset is missing: {relpath}.")
            continue
        actual_hash = _file_sha256(candidate)
        if str(recorded_hashes.get(relpath) or "") != actual_hash:
            issues.append(f"Selected template asset hash does not match Run provenance: {relpath}.")
        if candidate not in front_assets:
            front_assets.append(candidate)

    required_base = TEMPLATE_ASSETS_BY_SKILL["front-matter-writer"][0]
    if required_base not in front_assets:
        issues.append(f"Selected template assets omit required base bank: {_display_path(required_base)}.")
    assets = tuple([*front_assets, *fixed_assets])
    return {
        "status": "PASS" if not issues else "INVALID",
        "context_path": FRONT_MATTER_CONTEXT_PATH,
        "assets": list(assets or DEFAULT_TEMPLATE_ASSETS),
        "asset_paths": [_display_path(path) for path in (assets or DEFAULT_TEMPLATE_ASSETS)],
        "issues": issues,
    }


def template_implementation_lock_evidence(workspace: Path) -> dict[str, Any]:
    """Compare template-owning Skill implementations with a v2 Run lock."""

    lock_path = workspace / ".harness" / "harness.lock.json"
    if not lock_path.exists():
        return {
            "status": "UNAVAILABLE",
            "checked": False,
            "lock_path": ".harness/harness.lock.json",
            "skills": [],
            "drifted_skills": [],
        }
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "status": "INVALID",
            "checked": True,
            "lock_path": ".harness/harness.lock.json",
            "skills": [],
            "drifted_skills": sorted(TEMPLATE_ASSETS_BY_SKILL),
        }
    if not isinstance(lock, dict) or lock.get("schema") != "harness-lock.v2":
        return {
            "status": "LEGACY_UNVERIFIED",
            "checked": False,
            "lock_path": ".harness/harness.lock.json",
            "skills": [],
            "drifted_skills": [],
        }

    from tooling.run_state import implementation_fingerprint

    locked_skills = lock.get("skills") if isinstance(lock.get("skills"), dict) else {}
    records: list[dict[str, Any]] = []
    drifted: list[str] = []
    for skill in TEMPLATE_ASSETS_BY_SKILL:
        locked = locked_skills.get(skill) if isinstance(locked_skills, dict) else None
        expected = str(locked.get("implementation_sha256") or "") if isinstance(locked, dict) else ""
        skill_dir = REPO_ROOT / ".codex" / "skills" / skill
        current = implementation_fingerprint(skill_dir) if skill_dir.is_dir() else {"sha256": "", "file_count": 0}
        actual = str(current.get("sha256") or "")
        matches = bool(expected) and expected == actual
        if not matches:
            drifted.append(skill)
        records.append(
            {
                "skill": skill,
                "expected_implementation_sha256": expected,
                "current_implementation_sha256": actual,
                "current_file_count": int(current.get("file_count") or 0),
                "matches": matches,
            }
        )
    return {
        "status": "PASS" if not drifted else "DRIFT",
        "checked": True,
        "lock_path": ".harness/harness.lock.json",
        "skills": records,
        "drifted_skills": drifted,
    }


def evaluate_template_residue(
    *,
    workspace: Path,
    documents: list[tuple[str, str]],
) -> dict[str, Any]:
    threshold, min_literal_chars = template_residue_policy(workspace)
    selection = selected_template_asset_evidence(workspace)
    summary = measure_template_residue(
        documents=documents,
        asset_paths=tuple(selection["assets"]),
        min_literal_chars=min_literal_chars,
    )
    lock_evidence = template_implementation_lock_evidence(workspace)
    measurable = (
        not summary["missing_assets"]
        and bool(summary["literal_fragment_count"])
        and bool(summary["sentence_count"])
    )
    ratio = float(summary["matched_sentence_ratio"])
    return {
        "schema": "template-residue-evaluation.v1",
        "summary": summary,
        "policy": {
            "max_ratio": threshold,
            "min_literal_chars": min_literal_chars,
        },
        "asset_selection": {
            key: value for key, value in selection.items() if key != "assets"
        },
        "implementation_lock": lock_evidence,
        "measurement_pass": measurable and ratio <= threshold,
        "source_provenance_pass": (
            selection["status"] == "PASS" and lock_evidence["status"] == "PASS"
        ),
    }


def build_template_residue_scorecard(
    *,
    workspace: Path,
    documents: list[tuple[str, str]],
    scope: str,
) -> dict[str, Any]:
    from tooling.common import load_workspace_pipeline_spec
    from tooling.scorecards import build_dimension, finalize_scorecard

    evaluation = evaluate_template_residue(workspace=workspace, documents=documents)
    summary = evaluation["summary"]
    policy = evaluation["policy"]
    selection = evaluation["asset_selection"]
    lock_evidence = evaluation["implementation_lock"]
    ratio = float(summary["matched_sentence_ratio"])
    measurement_dimension = build_dimension(
        "template_residue_limit",
        "Literal template residue",
        passed=bool(evaluation["measurement_pass"]),
        partial=False,
        evidence=(
            f"{summary['matched_sentence_count']}/{summary['sentence_count']} sentences "
            f"({ratio:.1%}) match fixed fragments from {len(summary['template_assets'])} Run-selected "
            f"template assets; limit <= {float(policy['max_ratio']):.0%}."
        ),
        repair_surface=[
            "output/DRAFT.md",
            ".codex/skills/front-matter-writer",
            ".codex/skills/chapter-lead-writer",
            ".codex/skills/subsection-writer",
        ],
    )
    measurement_dimension.update(
        {
            "matched_sentence_count": int(summary["matched_sentence_count"]),
            "sentence_count": int(summary["sentence_count"]),
            "matched_sentence_ratio": ratio,
            "max_ratio": float(policy["max_ratio"]),
            "template_asset_count": len(summary["template_assets"]),
        }
    )
    lock_status = str(lock_evidence["status"])
    lock_dimension = build_dimension(
        "template_source_provenance",
        "Template source provenance",
        passed=bool(evaluation["source_provenance_pass"]),
        partial=False,
        evidence=(
            f"Run-selected assets: {selection['status']}; "
            f"template-owning Skill implementations: {lock_status}; "
            f"drifted={len(lock_evidence['drifted_skills'])}."
        ),
        repair_surface=[
            FRONT_MATTER_CONTEXT_PATH,
            ".harness/harness.lock.json",
            "tooling/quality_checks/template_residue.py",
        ],
    )
    lock_dimension.update(
        {
            "selection_status": str(selection["status"]),
            "implementation_lock_status": lock_status,
            "selected_assets": list(selection["asset_paths"]),
            "drifted_skills": list(lock_evidence["drifted_skills"]),
        }
    )
    spec = load_workspace_pipeline_spec(workspace)
    workflow = spec.name if spec is not None else "arxiv-survey"
    payload = finalize_scorecard(
        schema=SCORECARD_SCHEMA,
        workflow=workflow,
        dimensions=[measurement_dimension, lock_dimension],
        pass_score=100,
        critical_dimensions={"template_residue_limit", "template_source_provenance"},
        counts={
            "sentences": int(summary["sentence_count"]),
            "matched_sentences": int(summary["matched_sentence_count"]),
            "template_assets": len(summary["template_assets"]),
            "literal_fragments": int(summary["literal_fragment_count"]),
            "drifted_skills": len(lock_evidence["drifted_skills"]),
        },
        limitations=[
            "Literal-fragment matching is a reproducible lower bound, not an authorship or originality classifier.",
            (
                f"The {float(policy['max_ratio']):.0%} limit is an initial policy target; a passing "
                "Run demonstrates attainability for that Run, not calibration across topics or profiles."
            ),
        ],
    )
    payload.update(
        {
            "scope": scope,
            "measurement": summary,
            "policy": policy,
            "asset_selection": selection,
            "implementation_lock": lock_evidence,
        }
    )
    return payload


def check_subsection_template_residue(
    *,
    workspace: Path,
    relpaths: list[str],
) -> list[QualityIssue]:
    documents = [
        (relpath, path.read_text(encoding="utf-8", errors="ignore"))
        for relpath in relpaths
        if (path := workspace / relpath).is_file()
    ]
    return check_template_residue_documents(workspace=workspace, documents=documents)


def check_template_residue_documents(
    *,
    workspace: Path,
    documents: list[tuple[str, str]],
) -> list[QualityIssue]:
    evaluation = evaluate_template_residue(workspace=workspace, documents=documents)
    summary = evaluation["summary"]
    threshold = float(evaluation["policy"]["max_ratio"])
    issues: list[QualityIssue] = []
    if summary["missing_assets"] or not summary["literal_fragment_count"]:
        issues.append(
            QualityIssue(
                code="template_residue_assets_unavailable",
                message=(
                    "The Run-selected writer template assets could not be loaded; template-residue acceptance "
                    "cannot be evaluated."
                ),
            )
        )
    if not summary["sentence_count"]:
        issues.append(
            QualityIssue(
                code="template_residue_no_sentences",
                message=(
                    "No reader-facing prose sentences were available for template-residue measurement; "
                    "write or restore the declared prose before acceptance."
                ),
            )
        )

    selection = evaluation["asset_selection"]
    lock_evidence = evaluation["implementation_lock"]
    if selection["status"] != "PASS":
        issues.append(
            QualityIssue(
                code="template_residue_asset_selection_unverified",
                message=(
                    "The Run-selected writer template assets are not verified from "
                    f"`{selection['context_path']}`: "
                    f"{'; '.join(selection['issues']) or selection['status']}."
                ),
            )
        )
    if lock_evidence["status"] != "PASS":
        issues.append(
            QualityIssue(
                code="template_residue_implementation_lock_mismatch",
                message=(
                    "The current template-owning Skill implementations do not match this Run's "
                    f"`harness-lock.v2`: {', '.join(lock_evidence['drifted_skills']) or lock_evidence['status']}. "
                    "Start a new Run or restore the locked implementations before evaluating residue."
                ),
            )
        )

    ratio = float(summary["matched_sentence_ratio"])
    if summary["sentence_count"] and ratio > threshold:
        examples = "; ".join(
            f"{item['path']}: {item['sentence'][:100]}"
            for item in summary["examples"][:3]
        )
        issues.append(
            QualityIssue(
                code="template_residue_above_threshold",
                message=(
                    f"Deterministic bootstrap-template residue is {summary['matched_sentence_count']}/"
                    f"{summary['sentence_count']} sentences ({ratio:.0%}), above the {threshold:.0%} "
                    f"Workflow limit. Rewrite the matched prose, refresh the section snapshot and "
                    f"merged draft, then rerun the active check. "
                    f"Examples: {examples}"
                ),
            )
        )
    return issues
