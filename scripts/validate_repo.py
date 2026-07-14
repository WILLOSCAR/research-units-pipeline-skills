from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "pipelines"
TEMPLATES_DIR = REPO_ROOT / "templates"
SKILLS_DIR = REPO_ROOT / ".codex" / "skills"
DOCS_DIR = REPO_ROOT / "docs"

sys.path.insert(0, str(REPO_ROOT))

from tooling.pipeline_spec import PipelineSpec
from tooling.harness_contracts import (
    ADR_ALLOWED_STATUSES,
    ADR_REQUIRED_METADATA,
    ADR_REQUIRED_SECTIONS,
    AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS,
    EVIDENCE_REVIEW_TAXONOMY_ARTIFACTS,
    HARNESS_LOCAL_CHECKS,
    HARNESS_DOC_ENTRYPOINTS,
    HARNESS_README_LINKS,
    HARNESS_SKILL_AUDIT_GATE,
    FORBIDDEN_OVERLAY_PIPELINE_FILENAMES,
    IDEA_BRAINSTORM_TAXONOMY_ARTIFACTS,
    PAPER_REVIEW_TAXONOMY_ARTIFACTS,
    RESEARCH_BRIEF_TAXONOMY_ARTIFACTS,
    PIPELINE_TAXONOMY_ROW_REQUIREMENTS,
    PIPELINE_TAXONOMY_REQUIRED_TERMS,
    PIPELINE_TAXONOMY_VARIANT_REQUIREMENTS,
    PROJECT_LANGUAGE_REQUIRED_TERMS,
    REPORT_SCHEMA_TERMS,
)

REQUIRED_UNITS_COLS = {
    "unit_id",
    "title",
    "type",
    "skill",
    "inputs",
    "outputs",
    "acceptance",
    "checkpoint",
    "status",
    "depends_on",
    "owner",
}


@dataclass(frozen=True)
class Finding:
    level: str  # ERROR|WARN|INFO
    message: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pipeline ↔ units template ↔ skills alignment.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN as errors (exit 2) and prefer blocking issues over soft warnings.",
    )
    parser.add_argument(
        "--check-docs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check repository docs/graphs presence (default: enabled).",
    )
    parser.add_argument(
        "--check-quality",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check skill doc quality conventions (default: enabled).",
    )
    parser.add_argument(
        "--quality-scope",
        choices=("pipeline", "all"),
        default="pipeline",
        help="Skill quality scope: active executable-pipeline skills or all skill packages (default: pipeline).",
    )
    parser.add_argument("--check-claude-symlink", action="store_true", help="Also check `.claude/skills` presence.")
    parser.add_argument("--report", default="", help="Optional Markdown report output path.")
    args = parser.parse_args()

    findings: list[Finding] = []
    pipeline_paths = sorted(PIPELINES_DIR.glob("*.pipeline.md"))
    if not pipeline_paths:
        findings.append(Finding("ERROR", f"No pipelines found under `{PIPELINES_DIR}`."))
        return _report(findings, strict=bool(args.strict), report_path=Path(args.report) if args.report else None)

    for pipeline_path in pipeline_paths:
        findings.extend(_validate_pipeline(pipeline_path))

    if args.check_docs:
        findings.extend(_validate_docs())

    if args.check_claude_symlink:
        findings.extend(_validate_claude_skills())

    if args.check_quality:
        active_skills = None
        if args.quality_scope == "pipeline":
            active_skills = _skills_from_units_templates(pipeline_paths)
        findings.extend(_validate_skill_quality(active_skill_names=active_skills))

    return _report(findings, strict=bool(args.strict), report_path=Path(args.report) if args.report else None)


def _validate_pipeline(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        spec = PipelineSpec.load(path)
    except Exception as exc:
        return [Finding("ERROR", f"{path}: {exc}")]

    units_template = str(spec.units_template or "").strip()
    if not units_template:
        findings.append(Finding("ERROR", f"{path}: missing `units_template` in YAML front matter."))
        return findings

    units_path = (REPO_ROOT / units_template).resolve()
    if not units_path.exists():
        findings.append(Finding("ERROR", f"{path}: units template not found: `{units_template}`."))
        return findings

    target_artifacts = list(spec.target_artifacts)

    findings.extend(_validate_machine_readable_contract(path=path, fm=fm, spec=spec))

    required_skills = _required_skills_from_spec(spec)
    if not required_skills:
        required_skills = _parse_required_skills(body)

    template_skills: set[str] = set()
    template_outputs: set[str] = set()
    missing_skill_dirs: set[str] = set()
    missing_skill_md: set[str] = set()
    skills_without_scripts: set[str] = set()

    try:
        with units_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            cols = set(reader.fieldnames or [])
            missing_cols = sorted(REQUIRED_UNITS_COLS - cols)
            if missing_cols:
                findings.append(
                    Finding("ERROR", f"{units_template}: missing required columns: {', '.join(missing_cols)}")
                )
                return findings

            for line_number, row in enumerate(reader, start=2):
                row_shape_error = _units_row_shape_error(row)
                if row_shape_error:
                    findings.append(
                        Finding("ERROR", f"{units_template}:{line_number}: malformed CSV row: {row_shape_error}")
                    )
                    continue
                skill = (row.get("skill") or "").strip()
                if not skill:
                    continue
                template_skills.add(skill)

                for out in _split_semicolon(row.get("outputs") or ""):
                    out = out.lstrip("?").strip()
                    if out:
                        template_outputs.add(out)

                skill_dir = SKILLS_DIR / skill
                if not skill_dir.exists():
                    missing_skill_dirs.add(skill)
                    continue

                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    missing_skill_md.add(skill)

                script = skill_dir / "scripts" / "run.py"
                if not script.exists():
                    skills_without_scripts.add(skill)
    except Exception as exc:
        findings.append(Finding("ERROR", f"Failed to read `{units_template}`: {exc}"))
        return findings

    for skill in sorted(missing_skill_dirs):
        findings.append(Finding("ERROR", f"{path.name}: `{units_template}` references missing skill dir: `{skill}`"))
    for skill in sorted(missing_skill_md):
        findings.append(Finding("ERROR", f"{path.name}: skill `{skill}` is missing `SKILL.md`"))

    missing_required = sorted(required_skills - template_skills)
    if missing_required:
        findings.append(
            Finding(
                "ERROR",
                f"{path.name}: pipeline `required_skills` missing from `{units_template}`: {', '.join(missing_required)}",
            )
        )

    if target_artifacts:
        missing_artifacts = sorted(set(map(str, target_artifacts)) - template_outputs)
        if missing_artifacts:
            findings.append(
                Finding(
                    "WARN",
                    f"{path.name}: `target_artifacts` not present in `{units_template}` outputs: {', '.join(missing_artifacts)}",
                )
            )

    if skills_without_scripts:
        findings.append(
            Finding(
                "INFO",
                f"{path.name}: skills without scripts (LLM-first expected): {', '.join(sorted(skills_without_scripts))}",
            )
        )

    return findings


def _validate_machine_readable_contract(*, path: Path, fm: dict[str, Any], spec: PipelineSpec) -> list[Finding]:
    findings: list[Finding] = []
    contract_model = str(spec.contract_model or "").strip()
    if not contract_model:
        return findings

    if contract_model != "pipeline.frontmatter/v1":
        findings.append(Finding("ERROR", f"{path.name}: unsupported `contract_model`: `{contract_model}`"))

    if not spec.stages:
        findings.append(Finding("ERROR", f"{path.name}: `contract_model` is set but `stages` is missing/empty."))
        return findings

    stage_ids = tuple(spec.stages.keys())
    if stage_ids != spec.default_checkpoints:
        findings.append(
            Finding(
                "ERROR",
                f"{path.name}: `default_checkpoints` must match `stages` order exactly "
                f"({list(spec.default_checkpoints)} != {list(stage_ids)})",
            )
        )

    stage_outputs: set[str] = set()
    for stage_id, stage in spec.stages.items():
        if not re.match(r"^C[0-9]+$", stage_id):
            findings.append(Finding("ERROR", f"{path.name}: invalid stage id `{stage_id}` (expected `C<number>`)."))
        if stage.mode not in {"no_prose", "short_prose_ok", "prose_allowed"}:
            findings.append(Finding("ERROR", f"{path.name}: `stages.{stage_id}.mode` must be one of `no_prose|short_prose_ok|prose_allowed`."))
        if not stage.required_skills:
            findings.append(Finding("ERROR", f"{path.name}: `stages.{stage_id}.required_skills` must be non-empty."))
        if not stage.produces:
            findings.append(Finding("ERROR", f"{path.name}: `stages.{stage_id}.produces` must be non-empty."))
        stage_outputs.update(stage.produces)
        if stage.human_checkpoint:
            write_to = str(stage.human_checkpoint.get("write_to") or "").strip()
            approve = str(stage.human_checkpoint.get("approve") or stage.human_checkpoint.get("question") or "").strip()
            if not approve:
                findings.append(Finding("ERROR", f"{path.name}: `stages.{stage_id}.human_checkpoint` is missing `approve`/`question`."))
            if write_to != "DECISIONS.md":
                findings.append(Finding("ERROR", f"{path.name}: `stages.{stage_id}.human_checkpoint.write_to` must be `DECISIONS.md`."))

    if spec.query_defaults and not spec.overridable_query_fields:
        findings.append(Finding("WARN", f"{path.name}: `query_defaults` is present but `overridable_query_fields` is empty."))

    if spec.variant_of and not spec.variant_overrides:
        findings.append(Finding("ERROR", f"{path.name}: `variant_of` requires a non-empty `variant_overrides` mapping."))
    if spec.variant_of:
        allowed_raw_keys = {"name", "version", "variant_of", "variant_overrides"}
        extra_raw_keys = sorted(set(fm.keys()) - allowed_raw_keys)
        if extra_raw_keys:
            findings.append(
                Finding(
                    "ERROR",
                    f"{path.name}: variant files may only keep top-level keys "
                    f"`name`, `version`, `variant_of`, `variant_overrides`; move others under `variant_overrides`: "
                    f"{', '.join(extra_raw_keys)}",
                )
            )

    uncovered_targets = sorted(set(spec.target_artifacts) - stage_outputs)
    if uncovered_targets:
        findings.append(
            Finding(
                "ERROR",
                f"{path.name}: `target_artifacts` not covered by any stage `produces`: {', '.join(uncovered_targets)}",
            )
        )

    structure_mode = str(spec.structure_mode or "").strip()
    if structure_mode == "section_first":
        expected_layers = {"chapter_skeleton", "section_bindings", "section_briefs", "subsection_mapping"}
        binding_layers = set(spec.binding_layers)
        missing_layers = sorted(expected_layers - binding_layers)
        if missing_layers:
            findings.append(
                Finding(
                    "ERROR",
                    f"{path.name}: `structure_mode: section_first` is missing required `binding_layers`: {', '.join(missing_layers)}",
                )
            )
        if int(spec.core_chapter_h3_target or 0) <= 0:
            findings.append(Finding("ERROR", f"{path.name}: `structure_mode: section_first` requires positive `core_chapter_h3_target`."))
        shell = spec.pre_retrieval_shell
        if not shell:
            findings.append(Finding("ERROR", f"{path.name}: `structure_mode: section_first` requires `pre_retrieval_shell`."))
        else:
            allowed_h2 = shell.get("allowed_h2")
            if not isinstance(allowed_h2, list) or not [x for x in allowed_h2 if str(x).strip()]:
                findings.append(Finding("ERROR", f"{path.name}: `pre_retrieval_shell.allowed_h2` must be a non-empty list."))
            if "approval_surface" not in shell:
                findings.append(Finding("ERROR", f"{path.name}: `pre_retrieval_shell` must declare `approval_surface`."))
        required_artifacts = {
            "outline/chapter_skeleton.yml",
            "outline/section_bindings.jsonl",
            "outline/section_binding_report.md",
            "outline/section_briefs.jsonl",
            "outline/outline.yml",
            "outline/outline_state.jsonl",
        }
        missing = sorted(required_artifacts - set(spec.target_artifacts))
        if missing:
            findings.append(
                Finding(
                    "ERROR",
                    f"{path.name}: `structure_mode: section_first` is missing required target artifacts: {', '.join(missing)}",
                )
            )

    return findings


def _required_skills_from_spec(spec: PipelineSpec) -> set[str]:
    skills: set[str] = set()
    for stage in spec.stages.values():
        skills.update(stage.required_skills)
    return skills


def _validate_claude_skills() -> list[Finding]:
    skills_path = REPO_ROOT / ".claude" / "skills"
    if skills_path.exists():
        return [Finding("INFO", f"Claude Code skills path present: `{skills_path}`")]
    return [
        Finding(
            "WARN",
            "Claude Code skills path missing: `.claude/skills` (consider symlinking/copying `.codex/skills`).",
        )
    ]


def _validate_docs() -> list[Finding]:
    findings: list[Finding] = []

    skill_index = REPO_ROOT / "SKILL_INDEX.md"
    if not skill_index.exists():
        findings.append(Finding("WARN", "Missing `SKILL_INDEX.md` (see TODO Sprint 1.1)."))

    graph_script = REPO_ROOT / "scripts" / "generate_skill_graph.py"
    if not graph_script.exists():
        findings.append(Finding("WARN", "Missing `scripts/generate_skill_graph.py` (see TODO Sprint 1.2)."))

    architecture_doc = DOCS_DIR / "AUTO_RESEARCH_DESIGN_SYSTEM.md"
    if not architecture_doc.exists():
        findings.append(Finding("WARN", "Missing `docs/AUTO_RESEARCH_DESIGN_SYSTEM.md` (main architecture document)."))
    else:
        text = architecture_doc.read_text(encoding="utf-8", errors="ignore")
        if "```mermaid" not in text:
            findings.append(
                Finding(
                    "WARN",
                    "`docs/AUTO_RESEARCH_DESIGN_SYSTEM.md` has no Mermaid architecture diagram.",
                )
            )

    findings.extend(_validate_harness_docs(repo_root=REPO_ROOT, docs_dir=DOCS_DIR))

    return findings


def _validate_harness_docs(*, repo_root: Path, docs_dir: Path) -> list[Finding]:
    findings: list[Finding] = []

    for rel_path, label in HARNESS_DOC_ENTRYPOINTS.items():
        if not (repo_root / rel_path).exists():
            findings.append(Finding("WARN", f"Missing `{rel_path}` ({label} entrypoint)."))

    for readme_name in ("README.md", "README.zh-CN.md"):
        readme_path = repo_root / readme_name
        if not readme_path.exists():
            findings.append(Finding("WARN", f"Missing `{readme_name}` (should link harness docs entrypoints)."))
            continue
        text = readme_path.read_text(encoding="utf-8", errors="ignore")
        missing_links = [link for link in HARNESS_README_LINKS if link not in text]
        if missing_links:
            findings.append(
                Finding(
                    "WARN",
                    f"`{readme_name}` is missing harness docs links: {', '.join(missing_links)}.",
                )
            )

    findings.extend(
        _validate_pipeline_taxonomy(
            repo_root=repo_root,
            pipelines_dir=repo_root / "pipelines",
            docs_dir=docs_dir,
        )
    )
    findings.extend(_validate_adr_index(repo_root=repo_root, docs_dir=docs_dir))
    findings.extend(_validate_adr_contracts(repo_root=repo_root, docs_dir=docs_dir))
    findings.extend(_validate_schema_summary_doc(repo_root=repo_root))
    findings.extend(_validate_auto_research_design_system_doc(repo_root=repo_root))
    findings.extend(_validate_project_language_doc(repo_root=repo_root))
    findings.extend(_validate_local_harness_checks(repo_root=repo_root))

    return findings


def _validate_auto_research_design_system_doc(*, repo_root: Path) -> list[Finding]:
    rel_path = "docs/AUTO_RESEARCH_DESIGN_SYSTEM.md"
    doc_path = repo_root / rel_path
    if not doc_path.exists():
        return []

    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    missing = [term for term in AUTO_RESEARCH_DESIGN_SYSTEM_REQUIRED_TERMS if term not in text]
    if missing:
        return [
            Finding(
                "WARN",
                f"`{rel_path}` is missing Auto Research Design System terms: "
                + ", ".join(f"`{term}`" for term in missing)
                + ".",
            )
        ]
    return []


def _validate_project_language_doc(*, repo_root: Path) -> list[Finding]:
    rel_path = "docs/PROJECT_LANGUAGE.md"
    doc_path = repo_root / rel_path
    if not doc_path.exists():
        return []

    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    missing = [term for term in PROJECT_LANGUAGE_REQUIRED_TERMS if term not in text]
    if missing:
        return [
            Finding(
                "WARN",
                f"`{rel_path}` is missing project language terms: "
                + ", ".join(f"`{term}`" for term in missing)
                + ".",
            )
        ]
    return []


def _validate_local_harness_checks(*, repo_root: Path) -> list[Finding]:
    readiness_path = repo_root / "docs" / "HARNESS_READINESS.md"
    if not readiness_path.exists():
        return []

    text = readiness_path.read_text(encoding="utf-8", errors="ignore")
    missing = [check for check in HARNESS_LOCAL_CHECKS if check not in text]
    if missing:
        return [
            Finding(
                "WARN",
                "`docs/HARNESS_READINESS.md` should list local harness checks: "
                + ", ".join(f"`{check}`" for check in missing)
                + ".",
            )
        ]
    return []


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _validate_adr_index(*, repo_root: Path, docs_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    adr_dir = docs_dir / "adr"
    if not adr_dir.exists():
        return findings
    index_path = adr_dir / "README.md"
    if not index_path.exists():
        findings.append(Finding("WARN", "Missing `docs/adr/README.md` (ADR index)."))
        return findings

    index_text = index_path.read_text(encoding="utf-8", errors="ignore")
    adr_paths = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    for adr_path in adr_paths:
        if adr_path.name not in index_text:
            findings.append(
                Finding(
                    "WARN",
                    f"`docs/adr/README.md` is missing ADR index entry for `{_rel_path(adr_path, repo_root)}`.",
                )
            )

    adr_filenames = {path.name for path in adr_paths}
    for link in re.findall(r"\]\((\d{4}[^)]*?\.md)\)", index_text):
        filename = Path(link).name
        if filename not in adr_filenames:
            findings.append(
                Finding(
                    "WARN",
                    f"`docs/adr/README.md` links missing ADR file `{link}`.",
                )
            )

    return findings


def _validate_adr_contracts(*, repo_root: Path, docs_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    adr_dir = docs_dir / "adr"
    if not adr_dir.exists():
        return findings

    for adr_path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = adr_path.read_text(encoding="utf-8", errors="ignore")
        rel_path = _rel_path(adr_path, repo_root)
        adr_number = adr_path.name[:4]
        first_line = text.splitlines()[0] if text.splitlines() else ""

        missing: list[str] = []
        if f"ADR {adr_number}" not in first_line:
            missing.append(f"title `# ADR {adr_number}: ...`")

        status_match = re.search(r"(?im)^\s*-?\s*Status:\s*([A-Za-z-]+)\s*$", text)
        if status_match is None:
            missing.append("metadata `Status`")
        else:
            status = status_match.group(1).lower()
            if status not in ADR_ALLOWED_STATUSES:
                findings.append(
                    Finding(
                        "WARN",
                        f"`{rel_path}` has unsupported ADR status `{status}`; "
                        f"expected one of {', '.join(ADR_ALLOWED_STATUSES)}.",
                    )
                )

        if re.search(r"(?im)^\s*-?\s*Date:\s*\d{4}-\d{2}-\d{2}\s*$", text) is None:
            missing.append("metadata `Date`")

        for section in ADR_REQUIRED_SECTIONS:
            if section not in text:
                missing.append(f"section `{section}`")

        if missing:
            findings.append(
                Finding(
                    "WARN",
                    f"`{rel_path}` is missing ADR contract metadata: {', '.join(missing)}.",
                )
            )

    return findings


def _validate_schema_summary_doc(*, repo_root: Path) -> list[Finding]:
    rel_path = "docs/SCHEMAS.md"
    doc_path = repo_root / rel_path
    if not doc_path.exists():
        return []
    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    missing = [term for term in REPORT_SCHEMA_TERMS if term not in text]
    if not missing:
        return []
    return [
        Finding(
            "WARN",
            f"`{rel_path}` is missing report schema terms: "
            + ", ".join(f"`{term}`" for term in missing)
            + ".",
        )
    ]


def _validate_pipeline_taxonomy(*, repo_root: Path, pipelines_dir: Path, docs_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    taxonomy_doc = docs_dir / "PIPELINE_TAXONOMY.md"
    if not taxonomy_doc.exists():
        return findings

    text = taxonomy_doc.read_text(encoding="utf-8", errors="ignore")
    missing_taxonomy_terms = [term for term in PIPELINE_TAXONOMY_REQUIRED_TERMS if term not in text]
    if missing_taxonomy_terms:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing taxonomy terms: "
                + ", ".join(f"`{term}`" for term in missing_taxonomy_terms)
                + ".",
            )
        )

    row_findings = _validate_taxonomy_rows(text)
    findings.extend(row_findings)

    missing_variant_terms = [term for term in PIPELINE_TAXONOMY_VARIANT_REQUIREMENTS if term not in text]
    if missing_variant_terms:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing arxiv-survey-latex variant semantics: "
                + ", ".join(f"`{term}`" for term in missing_variant_terms)
                + ".",
            )
        )

    missing_paper_review_artifacts = [artifact for artifact in PAPER_REVIEW_TAXONOMY_ARTIFACTS if artifact not in text]
    if missing_paper_review_artifacts:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing paper-review contract artifacts: "
                + ", ".join(f"`{artifact}`" for artifact in missing_paper_review_artifacts)
                + ".",
            )
        )

    missing_research_brief_artifacts = [artifact for artifact in RESEARCH_BRIEF_TAXONOMY_ARTIFACTS if artifact not in text]
    if missing_research_brief_artifacts:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing research-brief contract artifacts: "
                + ", ".join(f"`{artifact}`" for artifact in missing_research_brief_artifacts)
                + ".",
            )
        )

    missing_idea_artifacts = [artifact for artifact in IDEA_BRAINSTORM_TAXONOMY_ARTIFACTS if artifact not in text]
    if missing_idea_artifacts:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing idea-brainstorm contract artifacts: "
                + ", ".join(f"`{artifact}`" for artifact in missing_idea_artifacts)
                + ".",
            )
        )

    missing_evidence_artifacts = [artifact for artifact in EVIDENCE_REVIEW_TAXONOMY_ARTIFACTS if artifact not in text]
    if missing_evidence_artifacts:
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing evidence-review contract artifacts: "
                + ", ".join(f"`{artifact}`" for artifact in missing_evidence_artifacts)
                + ".",
            )
        )

    forbidden_pipeline_paths = [pipelines_dir / filename for filename in FORBIDDEN_OVERLAY_PIPELINE_FILENAMES]
    present_forbidden = [path for path in forbidden_pipeline_paths if path.exists()]
    if present_forbidden:
        findings.append(
            Finding(
                "WARN",
                "Use-case overlays must not become separate pipeline contracts; remove or reclassify: "
                + ", ".join(f"`{_rel_path(path, repo_root)}`" for path in present_forbidden)
                + ".",
            )
        )

    if not pipelines_dir.exists():
        return findings

    for pipeline_path in sorted(pipelines_dir.glob("*.pipeline.md")):
        try:
            spec = PipelineSpec.load(pipeline_path)
        except Exception as exc:
            findings.append(
                Finding(
                    "WARN",
                    f"`docs/PIPELINE_TAXONOMY.md` could not load `{_rel_path(pipeline_path, repo_root)}` for drift check: {exc}",
                )
            )
            continue

        required_bits = {
            "pipeline name": f"`{spec.name}`",
            "contract path": f"`{_rel_path(spec.path, repo_root)}`",
            "unit template": f"`{_rel_path(repo_root / spec.units_template, repo_root)}`",
        }
        missing = [f"{label} {needle}" for label, needle in required_bits.items() if needle not in text]
        if missing:
            findings.append(
                Finding(
                    "WARN",
                    f"`docs/PIPELINE_TAXONOMY.md` is missing executable pipeline metadata for "
                    f"`{spec.name}`: {', '.join(missing)}.",
                )
            )

    graduate_doc = repo_root / "pipelines" / "graduate-paper-pipeline.md"
    if graduate_doc.exists():
        required_bits = {
            "pipeline name": "`graduate-paper`",
            "contract document": f"`{_rel_path(graduate_doc, repo_root)}`",
            "research-stage maturity": "`Research-stage`",
            "missing unit template marker": "Unit template: none yet",
        }
        missing = [f"{label} {needle}" for label, needle in required_bits.items() if needle not in text]
        if missing:
            findings.append(
                Finding(
                    "WARN",
                    "`docs/PIPELINE_TAXONOMY.md` is missing graduate-paper research-stage metadata: "
                    + ", ".join(missing)
                    + ".",
                )
            )

    return findings


def _validate_taxonomy_rows(text: str) -> list[Finding]:
    table_rows = [line for line in text.splitlines() if line.strip().startswith("|")]
    findings: list[Finding] = []
    for required_bits in PIPELINE_TAXONOMY_ROW_REQUIREMENTS:
        if any(all(bit in row for bit in required_bits) for row in table_rows):
            continue
        workflow = required_bits[1]
        findings.append(
            Finding(
                "WARN",
                "`docs/PIPELINE_TAXONOMY.md` is missing taxonomy row semantics for "
                f"{workflow}: " + ", ".join(f"`{bit}`" for bit in required_bits) + ".",
            )
        )
    return findings


HIGH_FREQUENCY_SKILLS = {
    "arxiv-search",
    "taxonomy-builder",
    "outline-builder",
    "paper-notes",
    "prose-writer",
    "citation-verifier",
    "section-mapper",
    "dedupe-rank",
    "survey-visuals",
    "latex-compile-qa",
}


@dataclass(frozen=True)
class SkillDoc:
    key: str
    path: Path
    description: str
    body: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    has_script: bool


def _validate_skill_quality(*, active_skill_names: set[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []

    skill_docs = _load_skill_docs(SKILLS_DIR)
    if active_skill_names is not None:
        skill_docs = {key: doc for key, doc in skill_docs.items() if key in active_skill_names}
    if not skill_docs:
        return [Finding("WARN", f"No skills found under `{SKILLS_DIR}`.")]

    all_inputs: set[str] = set()
    for doc in skill_docs.values():
        all_inputs.update(doc.inputs)

    template_outputs = _load_template_outputs(TEMPLATES_DIR)

    for doc in skill_docs.values():
        desc = str(doc.description or "").strip()
        if not re.search(r"(?i)\*\*trigger\*\*\s*:", desc):
            findings.append(Finding("WARN", f"{doc.path}: YAML description missing `**Trigger**:` line."))

        first_line = (desc.splitlines()[0] if desc else "").strip()
        if first_line and len(first_line) > 200:
            findings.append(Finding("WARN", f"{doc.path}: description first line is >200 chars (routing may degrade)."))

        if doc.key in HIGH_FREQUENCY_SKILLS and not re.search(r"(?im)^##\s+Troubleshooting\s*$", doc.body):
            findings.append(Finding("WARN", f"{doc.path}: missing `## Troubleshooting` (high-frequency skill)."))

        if doc.has_script and not _has_command_examples(doc.body):
            findings.append(
                Finding(
                    "WARN",
                    f"{doc.path}: has `scripts/run.py` but is missing `### Quick Start`/`### All Options`/`### Examples` sections.",
                )
            )

        body_wo_inputs = _strip_section(doc.body, headings={"input", "inputs"})
        for inp in doc.inputs:
            if inp and inp not in body_wo_inputs:
                findings.append(
                    Finding(
                        "WARN",
                        f"{doc.path}: declared input `{inp}` is not referenced outside the Inputs section (mention it in workflow/script/examples).",
                    )
                )

        for out in doc.outputs:
            if not out:
                continue
            if out in all_inputs:
                continue
            if out in template_outputs:
                continue
            if _is_known_sink_output(out):
                continue
            findings.append(
                Finding(
                    "WARN",
                    f"{doc.path}: output `{out}` is not used as any skill input and not present in any `templates/UNITS.*.csv` outputs.",
                )
            )

    return findings


def _load_skill_docs(skills_dir: Path) -> dict[str, SkillDoc]:
    out: dict[str, SkillDoc] = {}
    if not skills_dir.exists():
        return out
    for skill_dir in sorted([p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))]):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm, body = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
        except Exception:
            continue
        desc = str(fm.get("description") or "")
        inputs, outputs = _parse_inputs_outputs(body)
        has_script = (skill_dir / "scripts" / "run.py").exists()
        out[skill_dir.name] = SkillDoc(
            key=skill_dir.name,
            path=skill_md,
            description=desc,
            body=body,
            inputs=tuple(sorted(inputs)),
            outputs=tuple(sorted(outputs)),
            has_script=has_script,
        )
    return out


def _parse_inputs_outputs(body: str) -> tuple[set[str], set[str]]:
    inputs: set[str] = set()
    outputs: set[str] = set()

    section: str | None = None
    for raw in (body or "").splitlines():
        line = raw.rstrip()
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            heading = m.group(1).strip().lower()
            if heading in {"input", "inputs"}:
                section = "in"
            elif heading in {"output", "outputs"}:
                section = "out"
            else:
                section = None
            continue
        if section not in {"in", "out"}:
            continue
        if not line.strip().startswith("- "):
            continue
        for token in re.findall(r"`([^`]+)`", line):
            token = token.strip()
            if not _looks_like_path(token):
                continue
            if _is_skill_local_support_path(token):
                continue
            if section == "in":
                inputs.add(token)
            else:
                outputs.add(token)

    return inputs, outputs


def _is_skill_local_support_path(value: str) -> bool:
    normalized = str(value or "").strip().lstrip("./")
    return normalized.startswith(("assets/", "references/"))


def _skills_from_units_templates(pipeline_paths: list[Path]) -> set[str]:
    skills: set[str] = set()
    for pipeline_path in pipeline_paths:
        try:
            spec = PipelineSpec.load(pipeline_path)
        except Exception:
            continue
        units_template = str(spec.units_template or "").strip()
        if not units_template:
            continue
        units_path = REPO_ROOT / units_template
        if not units_path.exists():
            continue
        try:
            with units_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    skill = str(row.get("skill") or "").strip()
                    if skill:
                        skills.add(skill)
        except Exception:
            continue
    return skills


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("--", "python ")):
        return False
    if " " in value:
        return False
    if not any(ch in value for ch in ["/", "."]):
        return False
    if value.endswith((".py", ".md", ".yml", ".yaml", ".csv", ".tsv", ".jsonl", ".bib", ".pdf")):
        return True
    if "/" in value:
        return True
    return False


def _units_row_shape_error(row: dict[str | None, str | list[str] | None]) -> str | None:
    extras = row.get(None)
    if extras:
        return "unexpected extra columns; quote commas inside a field or use non-delimiter punctuation"
    missing = sorted(str(key) for key, value in row.items() if key is not None and value is None)
    if missing:
        return f"missing values for columns: {', '.join(missing)}"
    return None


def _strip_section(body: str, *, headings: set[str]) -> str:
    out: list[str] = []
    in_section = False
    for raw in (body or "").splitlines():
        line = raw.rstrip("\n")
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            name = m.group(1).strip().lower()
            in_section = name in headings
            if not in_section:
                out.append(line)
            continue
        if in_section:
            continue
        out.append(line)
    return "\n".join(out)


def _has_command_examples(body: str) -> bool:
    has_quick = re.search(r"(?im)^###\s+Quick Start\s*$", body or "") is not None
    has_opts = re.search(r"(?im)^###\s+All Options\s*$", body or "") is not None
    has_examples = re.search(r"(?im)^###\s+Examples\s*$", body or "") is not None
    return has_quick and has_opts and has_examples


def _load_template_outputs(templates_dir: Path) -> set[str]:
    out: set[str] = set()
    if not templates_dir.exists():
        return out
    for path in templates_dir.glob("UNITS.*.csv"):
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    for token in _split_semicolon(row.get("outputs") or ""):
                        out.add(token.lstrip("?").strip())
        except Exception:
            continue
    return {p for p in out if p}


def _is_known_sink_output(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return True
    # Placeholders and directory markers are side artifacts, not contract outputs.
    if "<" in p or ">" in p:
        return True
    if p.endswith("/"):
        return True
    if p.startswith(("output/", "docs/")):
        return True
    if p.startswith("latex/"):
        return True
    if p.endswith("_report.md") or p.endswith("report.md"):
        return True
    if p == "papers/papers_raw.csv":
        return True
    return False


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("pipeline file must start with YAML front matter (`---`).")
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("unterminated YAML front matter (missing closing `---`).")
    raw = "\n".join(lines[1:end_idx])
    fm = yaml.safe_load(raw) or {}
    if not isinstance(fm, dict):
        raise ValueError("pipeline YAML front matter must be a mapping.")
    body = "\n".join(lines[end_idx + 1 :])
    return fm, body


def _parse_required_skills(body: str) -> set[str]:
    skills: set[str] = set()
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() != "required_skills:":
            i += 1
            continue
        i += 1
        while i < len(lines):
            line = lines[i].rstrip()
            if not line.strip():
                break
            m = re.match(r"^\s*-\s*(\S+)\s*$", line)
            if not m:
                break
            skills.add(m.group(1))
            i += 1
        continue
    return skills


def _split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _report(findings: list[Finding], *, strict: bool, report_path: Path | None) -> int:
    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]
    infos = [f for f in findings if f.level == "INFO"]

    for f in errors + warns + infos:
        prefix = {"ERROR": "ERROR", "WARN": "WARN", "INFO": "INFO"}.get(f.level, f.level)
        print(f"{prefix}: {f.message}")

    print("")
    print(f"Summary: {len(errors)} error(s), {len(warns)} warning(s), {len(infos)} info.")

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_report(errors=errors, warns=warns, infos=infos), encoding="utf-8")
        print(f"Report: `{report_path}`")

    if errors:
        return 2
    if strict and warns:
        return 2
    return 0


def _render_report(*, errors: list[Finding], warns: list[Finding], infos: list[Finding]) -> str:
    def _section(title: str, items: list[Finding]) -> list[str]:
        lines = [f"## {title}", ""]
        if not items:
            lines.append("- (none)")
            lines.append("")
            return lines
        for f in items:
            lines.append(f"- {f.message}")
        lines.append("")
        return lines

    lines: list[str] = [
        "# Validation report",
        "",
        *_section("Errors", errors),
        *_section("Warnings", warns),
        *_section("Info", infos),
    ]
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
