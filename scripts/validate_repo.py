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
        findings.extend(_validate_skill_quality())

    return _report(findings, strict=bool(args.strict), report_path=Path(args.report) if args.report else None)


def _validate_pipeline(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [Finding("ERROR", f"{path}: {exc}")]

    units_template = str(fm.get("units_template") or "").strip()
    if not units_template:
        findings.append(Finding("ERROR", f"{path}: missing `units_template` in YAML front matter."))
        return findings

    units_path = (REPO_ROOT / units_template).resolve()
    if not units_path.exists():
        findings.append(Finding("ERROR", f"{path}: units template not found: `{units_template}`."))
        return findings

    target_artifacts = fm.get("target_artifacts") or []
    if target_artifacts and not isinstance(target_artifacts, list):
        findings.append(Finding("WARN", f"{path}: `target_artifacts` should be a YAML list."))
        target_artifacts = []

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

            for row in reader:
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
    deps_doc = DOCS_DIR / "SKILL_DEPENDENCIES.md"

    if not graph_script.exists():
        findings.append(Finding("WARN", "Missing `scripts/generate_skill_graph.py` (see TODO Sprint 1.2)."))

    if not deps_doc.exists():
        findings.append(Finding("WARN", "Missing `docs/SKILL_DEPENDENCIES.md` (run `python scripts/generate_skill_graph.py`)."))
    else:
        text = deps_doc.read_text(encoding="utf-8", errors="ignore")
        if "```mermaid" not in text:
            findings.append(Finding("WARN", "`docs/SKILL_DEPENDENCIES.md` has no Mermaid blocks (expected ` ```mermaid `)."))

    pipeline_flows = DOCS_DIR / "PIPELINE_FLOWS.md"
    if not pipeline_flows.exists():
        findings.append(Finding("WARN", "Missing `docs/PIPELINE_FLOWS.md` (see TODO Sprint 5.1)."))
    else:
        text = pipeline_flows.read_text(encoding="utf-8", errors="ignore")
        if "```mermaid" not in text:
            findings.append(Finding("WARN", "`docs/PIPELINE_FLOWS.md` has no Mermaid blocks (expected ` ```mermaid `)."))

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


def _validate_skill_quality() -> list[Finding]:
    findings: list[Finding] = []

    skill_docs = _load_skill_docs(SKILLS_DIR)
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
                        "ERROR",
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
    for skill_dir in sorted([p for p in skills_dir.iterdir() if p.is_dir()]):
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
            if section == "in":
                inputs.add(token)
            else:
                outputs.add(token)

    return inputs, outputs


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
