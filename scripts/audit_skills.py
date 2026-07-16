from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_DIR = REPO_ROOT / ".codex" / "skills"
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".sh",
    ".js",
    ".ts",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
}
SEVERITY_ORDER = {"INFO": 10, "WARN": 20, "ERROR": 30}
SKILL_AUDIT_REPORT_SCHEMA = "skill-audit-report.v1"
DESCRIPTION_CONTEXT_LOAD_LIMIT = 420
SKILL_BODY_SPRAWL_LIMIT = 180

GENERIC_DOMAIN_PATTERNS = (
    re.compile(r"\bLLM agents\b", re.IGNORECASE),
    re.compile(r"\bLarge language model agents?\b", re.IGNORECASE),
)
PIPELINE_VOICE_PATTERNS = (
    re.compile(r"\bthis pipeline aims\b", re.IGNORECASE),
    re.compile(r"\bacross the pipeline\b", re.IGNORECASE),
)
ELLIPSIS_PATTERNS = (
    re.compile(r"…"),
    re.compile(r"\.\.\. \([0-9]+ more\)", re.IGNORECASE),
    re.compile(r"\.\.\. \(N more\)", re.IGNORECASE),
    re.compile(r"\.\.\."),
)
SCRIPT_REFERENCE_TOKENS = (
    "scripts/",
    "run.py",
    "helper script",
    "bootstrap script",
    "quick start",
    "all options",
    "## script",
    "### script",
)
DIAGNOSTIC_ELLIPSIS_MARKERS = (
    "ellipsis",
    "truncation dots",
    "e.g.",
    "for example",
    "example",
    "exemplar",
    "opener",
    "stem",
    "voice",
    "narration",
    "navigation",
    "transition",
    "synthesis",
    "decision-rule",
    "enumerator",
    "guidance",
    "template",
    "planner-talk",
    "mechanical",
    "stock opener",
    "shorthand",
    "no real modules",
    "leak",
    "avoid",
    "rewrite",
    "remove",
    "vary",
    "de-template",
)
RULE_GUIDANCE = {
    "forced_paragraph_count": (
        "forced_shape_error",
        "Remove forced paragraph-count padding; let acceptance criteria validate substance instead.",
    ),
    "pipeline_voice": (
        "skill_voice_leak",
        "Rewrite skill-facing content so pipeline/internal narration cannot leak into generated artifacts.",
    ),
    "script_heavy_without_references": (
        "script_reference_surface",
        "Mention the substantial helper scripts from `SKILL.md` so future agents can find the deterministic surface.",
    ),
    "description_context_load": (
        "invocation_context_load",
        "Keep the description as a compact invocation pointer; move execution contract and examples into the Skill body.",
    ),
    "skill_body_sprawl": (
        "information_hierarchy",
        "Keep common steps visible and move branch-only reference behind explicit context pointers.",
    ),
}


@dataclass(frozen=True)
class Finding:
    severity: str
    rule_id: str
    skill: str
    path: str
    line: int
    message: str
    excerpt: str
    review_category: str = ""
    next_action: str = ""

    def __post_init__(self) -> None:
        category, action = _default_review_guidance(self)
        if not self.review_category:
            object.__setattr__(self, "review_category", category)
        if not self.next_action:
            object.__setattr__(self, "next_action", action)


@dataclass(frozen=True)
class ScanStats:
    skills_scanned: int
    files_scanned: int


@dataclass(frozen=True)
class SkillSummary:
    name: str
    skill_md: Path | None
    script_files: list[Path]
    script_nonempty_lines: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Static auditor for repository skills under `.codex/skills/**`.")
    parser.add_argument(
        "--skills-dir",
        default=str(DEFAULT_SKILLS_DIR),
        help="Skills root to scan (default: repo `.codex/skills`).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--fail-on",
        choices=("NONE", "ERROR", "WARN", "INFO"),
        default="ERROR",
        help="Exit 2 if findings at or above this severity exist (default: ERROR).",
    )
    parser.add_argument(
        "--review-category",
        action="append",
        default=[],
        help="Only include findings for this review category. Repeat to include multiple categories.",
    )
    parser.add_argument(
        "--limit",
        type=_nonnegative_int,
        default=0,
        help="Maximum finding details to display after filtering (0 means no limit).",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only the grouped summary; omit individual finding details.",
    )
    parser.add_argument("--report", default="", help="Optional report output path.")
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir).resolve()
    if not skills_dir.exists():
        raise SystemExit(f"Skills directory not found: {skills_dir}")

    findings, stats = audit_skills(skills_dir)
    review_categories = _normalize_review_categories(args.review_category)
    filtered_findings = _filter_findings_by_review_category(findings, review_categories)
    display_findings = [] if args.summary_only else _limit_findings(filtered_findings, args.limit)
    rendered = render_report(
        findings=filtered_findings,
        stats=stats,
        fmt=args.format,
        display_findings=display_findings,
        filters=_rendered_filters(
            review_categories=review_categories,
            limit=args.limit,
            summary_only=bool(args.summary_only),
        ),
    )

    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")

    sys.stdout.write(rendered)
    if args.format == "text" and not rendered.endswith("\n"):
        sys.stdout.write("\n")

    threshold = str(args.fail_on).upper()
    if threshold != "NONE" and any(SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[threshold] for f in filtered_findings):
        return 2
    return 0


def audit_skills(skills_dir: Path) -> tuple[list[Finding], ScanStats]:
    findings: list[Finding] = []
    skill_dirs = [path for path in sorted(skills_dir.iterdir()) if path.is_dir() and not path.name.startswith((".", "_"))]
    files_scanned = 0

    for skill_dir in skill_dirs:
        text_files = list(iter_skill_text_files(skill_dir))
        files_scanned += len(text_files)
        for path in text_files:
            findings.extend(_audit_text_file(skill_dir.name, path, skills_dir))
        findings.extend(_audit_script_heavy_without_references(skill_dir, skills_dir))
        findings.extend(_audit_skill_information_hierarchy(skill_dir))

    findings.sort(key=lambda item: (-SEVERITY_ORDER[item.severity], item.path, item.line, item.rule_id))
    stats = ScanStats(skills_scanned=len(skill_dirs), files_scanned=files_scanned)
    return findings, stats


def iter_skill_text_files(skill_dir: Path) -> Iterable[Path]:
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        if path.name == "SKILL.md" or path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def _audit_text_file(skill_name: str, path: Path, skills_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return findings

    is_script = "scripts" in path.parts
    is_reference = "references" in path.parts
    is_asset = "assets" in path.parts
    is_support_doc = is_asset or is_reference
    rel_path = path.relative_to(REPO_ROOT).as_posix()

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        for pattern in GENERIC_DOMAIN_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(
                        severity="INFO" if is_support_doc else "WARN",
                        rule_id="generic_domain_hardcoding",
                        skill=skill_name,
                        path=rel_path,
                        line=line_no,
                        message=f"Hardcoded domain phrase `{match.group(0)}` reduces skill portability.",
                        excerpt=_excerpt(line),
                    )
                )
                break

        for pattern in PIPELINE_VOICE_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(
                        severity="WARN",
                        rule_id="pipeline_voice",
                        skill=skill_name,
                        path=rel_path,
                        line=line_no,
                        message=f"Pipeline/internal voice phrase `{match.group(0)}` appears in skill content.",
                        excerpt=_excerpt(line),
                    )
                )
                break

        if is_script:
            match = re.search(r"while\s+len\s*\(\s*paragraphs\s*\)\s*<", line)
            if match:
                findings.append(
                    Finding(
                        severity="ERROR",
                        rule_id="forced_paragraph_count",
                        skill=skill_name,
                        path=rel_path,
                        line=line_no,
                        message="Forced paragraph-count loop detected (`while len(paragraphs) < ...`).",
                        excerpt=_excerpt(line),
                    )
                )

        ellipsis_match = _ellipsis_match(line, is_script=is_script)
        if ellipsis_match:
            severity = "WARN" if is_script else "INFO"
            findings.append(
                Finding(
                    severity=severity,
                    rule_id="reader_facing_ellipsis",
                    skill=skill_name,
                    path=rel_path,
                    line=line_no,
                    message=f"Ellipsis-like token `{ellipsis_match}` may leak into reader-facing artifacts.",
                    excerpt=_excerpt(line),
                )
            )

    return findings


def _audit_script_heavy_without_references(skill_dir: Path, skills_dir: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    script_files = [
        path
        for path in sorted((skill_dir / "scripts").rglob("*"))
        if path.is_file() and path.suffix in {".py", ".sh", ".js", ".ts"} and "__pycache__" not in path.parts
    ]
    if not script_files:
        return []

    script_nonempty_lines = 0
    for path in script_files:
        try:
            script_nonempty_lines += sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
        except Exception:
            continue

    is_script_heavy = len(script_files) >= 2 or script_nonempty_lines >= 80
    if not is_script_heavy:
        return []

    if skill_md.exists():
        skill_md_text = skill_md.read_text(encoding="utf-8", errors="ignore").lower()
        has_reference = any(token in skill_md_text for token in SCRIPT_REFERENCE_TOKENS)
        if has_reference:
            return []
        path = skill_md.relative_to(REPO_ROOT).as_posix()
        return [
            Finding(
                severity="WARN",
                rule_id="script_heavy_without_references",
                skill=skill_dir.name,
                path=path,
                line=1,
                message=(
                    "Skill has substantial script logic but `SKILL.md` does not reference its scripts "
                    f"({len(script_files)} files, {script_nonempty_lines} non-empty lines)."
                ),
                excerpt=_excerpt(_first_nonempty_line(skill_md)),
            )
        ]

    path = script_files[0].relative_to(REPO_ROOT).as_posix()
    return [
        Finding(
            severity="WARN",
            rule_id="script_heavy_without_references",
            skill=skill_dir.name,
            path=path,
            line=1,
            message=(
                "Skill has substantial script logic but no `SKILL.md` reference surface was found "
                f"({len(script_files)} files, {script_nonempty_lines} non-empty lines)."
            ),
            excerpt=_excerpt(_first_nonempty_line(script_files[0])),
        )
    ]


def _audit_skill_information_hierarchy(skill_dir: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = _split_skill_frontmatter(text)
    except Exception:
        return []

    findings: list[Finding] = []
    rel_path = skill_md.relative_to(REPO_ROOT).as_posix()
    description = " ".join(str(frontmatter.get("description") or "").split())
    if len(description) > DESCRIPTION_CONTEXT_LOAD_LIMIT:
        findings.append(
            Finding(
                severity="INFO",
                rule_id="description_context_load",
                skill=skill_dir.name,
                path=rel_path,
                line=_frontmatter_field_line(text, "description"),
                message=(
                    f"Description uses {len(description)} characters; the informational context-load budget is "
                    f"{DESCRIPTION_CONTEXT_LOAD_LIMIT}."
                ),
                excerpt=_excerpt(description),
            )
        )

    body_nonempty_lines = sum(1 for line in body.splitlines() if line.strip())
    if body_nonempty_lines > SKILL_BODY_SPRAWL_LIMIT:
        findings.append(
            Finding(
                severity="INFO",
                rule_id="skill_body_sprawl",
                skill=skill_dir.name,
                path=rel_path,
                line=1,
                message=(
                    f"Skill body has {body_nonempty_lines} non-empty lines; the informational sprawl budget is "
                    f"{SKILL_BODY_SPRAWL_LIMIT}."
                ),
                excerpt=_excerpt(_first_nonempty_line(skill_md)),
            )
        )
    return findings


def _split_skill_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML front matter")
    end_idx = next((idx for idx, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end_idx is None:
        raise ValueError("SKILL.md has unterminated YAML front matter")
    payload = yaml.safe_load("\n".join(lines[1:end_idx])) or {}
    if not isinstance(payload, dict):
        raise ValueError("SKILL.md front matter must be a mapping")
    return payload, "\n".join(lines[end_idx + 1 :])


def _frontmatter_field_line(text: str, field: str) -> int:
    pattern = re.compile(rf"^{re.escape(field)}\s*:")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if pattern.match(line):
            return line_number
    return 1


def _ellipsis_match(line: str, *, is_script: bool) -> str | None:
    if is_script:
        return _script_ellipsis_match(line)
    for pattern in ELLIPSIS_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def _script_ellipsis_match(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "re.compile(" in stripped:
        return None
    if re.search(r"\bif\s+[\'\"].*(?:\.\.\.|…).*[\'\"]\s+in\s+", stripped):
        return None
    if re.search(r"tuple\[[^\]]*\.\.\.[^\]]*\]", stripped):
        return None

    for match in re.finditer(r"([\'\"])(.*?)(?<!\\)\1", stripped):
        content = match.group(2)
        for pattern in ELLIPSIS_PATTERNS:
            hit = pattern.search(content)
            if hit:
                if _is_diagnostic_ellipsis_context(stripped, content):
                    continue
                return hit.group(0)
    return None


def _is_diagnostic_ellipsis_context(line: str, content: str) -> bool:
    text = f"{line}\n{content}".lower()
    return any(marker in text for marker in DIAGNOSTIC_ELLIPSIS_MARKERS)


def _excerpt(text: str, limit: int = 160) -> str:
    compact = " ".join(str(text or "").strip().split())
    if len(compact) <= limit:
        return compact
    clipped = compact[: limit - 3].rsplit(" ", 1)[0].strip()
    return (clipped or compact[: limit - 3]).rstrip() + "..."


def _first_nonempty_line(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip():
                return line
    except Exception:
        return ""
    return ""


def render_report(
    *,
    findings: list[Finding],
    stats: ScanStats,
    fmt: str,
    display_findings: list[Finding] | None = None,
    filters: dict[str, object] | None = None,
) -> str:
    shown_findings = findings if display_findings is None else display_findings
    active_filters = filters or {}
    if fmt == "json":
        payload = build_report_payload(
            findings=findings,
            stats=stats,
            display_findings=shown_findings,
            filters=active_filters,
        )
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    lines = [
        "# Skill Audit Report",
        "",
        f"- Skills scanned: {stats.skills_scanned}",
        f"- Files scanned: {stats.files_scanned}",
        f"- Findings: {len(findings)}",
        f"- Displayed findings: {len(shown_findings)} of {len(findings)}",
        f"- By severity: {_format_counts(_count_by_severity(findings))}",
        f"- By rule: {_format_counts(_count_by_rule(findings))}",
        f"- By review category: {_format_counts(_count_by_review_category(findings))}",
    ]
    if active_filters:
        lines.append(f"- Filters: {_format_filter_summary(active_filters)}")
    lines.append("")
    if not findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"
    if not shown_findings:
        lines.append("Finding details omitted by filter settings.")
        return "\n".join(lines) + "\n"

    for item in shown_findings:
        lines.extend(
            [
                f"[{item.severity}] {item.rule_id} {item.path}:{item.line}",
                f"  skill: {item.skill}",
                f"  review_category: {item.review_category}",
                f"  message: {item.message}",
                f"  next_action: {item.next_action}",
                f"  excerpt: {item.excerpt}",
                "",
            ]
        )
    return "\n".join(lines)


def build_report_payload(
    *,
    findings: list[Finding],
    stats: ScanStats,
    display_findings: list[Finding] | None = None,
    filters: dict[str, object] | None = None,
) -> dict[str, Any]:
    shown_findings = findings if display_findings is None else display_findings
    return {
        "schema": SKILL_AUDIT_REPORT_SCHEMA,
        "summary": {
            "skills_scanned": stats.skills_scanned,
            "files_scanned": stats.files_scanned,
            "findings": len(findings),
            "displayed_findings": len(shown_findings),
            "by_severity": _count_by_severity(findings),
            "by_rule": _count_by_rule(findings),
            "by_review_category": _count_by_review_category(findings),
            "filters": filters or {},
        },
        "findings": [asdict(item) for item in shown_findings],
    }


def validate_skill_audit_payload(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("schema") != SKILL_AUDIT_REPORT_SCHEMA:
        issues.append(f"`schema` must be `{SKILL_AUDIT_REPORT_SCHEMA}`.")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        issues.append("`summary` must be an object.")
        summary = {}
    findings = payload.get("findings")
    if not isinstance(findings, list):
        issues.append("`findings` must be a list.")
        findings = []

    for key in ("skills_scanned", "files_scanned", "findings", "displayed_findings"):
        if not isinstance(summary.get(key), int):
            issues.append(f"`summary.{key}` must be an integer.")
    for key in ("by_severity", "by_rule", "by_review_category", "filters"):
        if not isinstance(summary.get(key), dict):
            issues.append(f"`summary.{key}` must be an object.")

    if isinstance(summary.get("displayed_findings"), int) and len(findings) != summary["displayed_findings"]:
        issues.append("`summary.displayed_findings` must match the number of displayed `findings`.")

    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            issues.append(f"`findings[{idx}]` must be an object.")
            continue
        for key in ("severity", "rule_id", "skill", "path", "message", "excerpt", "review_category", "next_action"):
            if not isinstance(item.get(key), str):
                issues.append(f"`findings[{idx}].{key}` must be a string.")
        if not isinstance(item.get("line"), int):
            issues.append(f"`findings[{idx}].line` must be an integer.")
    return issues


def _count_by_severity(findings: Iterable[Finding]) -> dict[str, int]:
    counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for item in findings:
        counts[item.severity] = counts.get(item.severity, 0) + 1
    return {key: value for key, value in counts.items() if value}


def _count_by_rule(findings: Iterable[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        counts[item.rule_id] = counts.get(item.rule_id, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _count_by_review_category(findings: Iterable[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        counts[item.review_category] = counts.get(item.review_category, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _normalize_review_categories(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(item for item in (str(value or "").strip() for value in values) if item)


def _filter_findings_by_review_category(findings: list[Finding], categories: tuple[str, ...]) -> list[Finding]:
    if not categories:
        return findings
    allowed = set(categories)
    return [item for item in findings if item.review_category in allowed]


def _limit_findings(findings: list[Finding], limit: int) -> list[Finding]:
    if limit <= 0:
        return findings
    return findings[:limit]


def _rendered_filters(*, review_categories: tuple[str, ...], limit: int, summary_only: bool) -> dict[str, object]:
    filters: dict[str, object] = {}
    if review_categories:
        filters["review_category"] = list(review_categories)
    if limit:
        filters["limit"] = limit
    if summary_only:
        filters["summary_only"] = True
    return filters


def _format_filter_summary(filters: dict[str, object]) -> str:
    parts: list[str] = []
    categories = filters.get("review_category")
    if categories:
        parts.append("review_category=" + ",".join(str(item) for item in categories))
    if filters.get("limit"):
        parts.append(f"limit={filters['limit']}")
    if filters.get("summary_only"):
        parts.append("summary_only=true")
    return ", ".join(parts) if parts else "none"


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _default_review_guidance(finding: Finding) -> tuple[str, str]:
    if finding.rule_id == "reader_facing_ellipsis":
        return _reader_facing_ellipsis_guidance(finding)
    if finding.rule_id == "generic_domain_hardcoding":
        if finding.severity == "WARN":
            return (
                "routing_portability",
                "Generalize skill routing text or move domain-specific wording into an explicit domain pack.",
            )
        return (
            "domain_pack_reference",
            "Keep if this is an intentionally scoped domain pack or example; promote to WARN if it appears in portable routing text.",
        )
    return RULE_GUIDANCE.get(
        finding.rule_id,
        (
            "manual_review",
            "Inspect the finding and decide whether it should remain informational or become a blocking skill hygiene rule.",
        ),
    )


def _reader_facing_ellipsis_guidance(finding: Finding) -> tuple[str, str]:
    if finding.severity == "WARN":
        return (
            "output_placeholder_leak",
            "Replace reader-facing ellipsis or truncation text with explicit wording or an omitted-item count.",
        )

    path = finding.path.lower()
    excerpt = finding.excerpt.lower()
    if "/assets/" in path:
        return (
            "asset_palette_reference",
            "Keep if this is a source palette or generated-output smell list; promote to WARN if copied into emitted artifacts.",
        )
    if "/references/" in path:
        return (
            "reference_example_phrase",
            "Keep if this is a reference example or anti-pattern corpus; promote to WARN if a skill emits it directly.",
        )
    if _looks_like_syntax_placeholder(excerpt):
        return (
            "syntax_placeholder",
            "Keep if this is command, path, citation, or markup syntax; prefer named placeholders when agents might copy it.",
        )
    if _looks_like_placeholder_policy(excerpt):
        return (
            "placeholder_policy",
            "Keep as policy guidance; consider rewriting if the example text itself is likely to be copied.",
        )
    if _looks_like_anti_pattern_guidance(excerpt):
        return (
            "anti_pattern_guidance",
            "Keep if it is warning against a phrase; promote to WARN if it appears as recommended output text.",
        )
    return (
        "template_placeholder",
        "Keep if this is a writer-facing template slot; replace with a named placeholder if it can be copied into output.",
    )


def _looks_like_syntax_placeholder(text: str) -> bool:
    return any(
        token in text
        for token in (
            "--inputs",
            "--outputs",
            "<a;b;...>",
            "[@...]",
            "\\url{...}",
            "howpublished=\\url{...}",
            "/...",
        )
    )


def _looks_like_placeholder_policy(text: str) -> bool:
    return any(token in text for token in ("placeholder", "todo", "tbd", "fixme", "scaffold"))


def _looks_like_anti_pattern_guidance(text: str) -> bool:
    return any(
        token in text
        for token in (
            "avoid",
            "bad:",
            "better:",
            "do not",
            "delete",
            "rewrite",
            "no explicit",
            "no planner",
            "no “",
            "no \"",
        )
    )


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


if __name__ == "__main__":
    raise SystemExit(main())
