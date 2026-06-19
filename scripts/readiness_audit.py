from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.harness_contracts import (
    CURRENT_WORKFLOWS,
    EXECUTABLE_PIPELINE_CONTRACTS,
    EXECUTABLE_UNIT_TEMPLATES,
    HARNESS_LOCAL_CHECKS,
    HARNESS_README_LINKS,
    HARNESS_SKILL_AUDIT_GATE,
    READINESS_AUDIT_SCHEMA,
    READINESS_MIN_ITERATIONS,
    READINESS_PROGRESS_PATH,
    READINESS_REQUIRED_DOCS,
    READINESS_VALIDATION_SURFACES,
)

DEFAULT_PROGRESS_PATH = READINESS_PROGRESS_PATH
SCHEMA = READINESS_AUDIT_SCHEMA
MIN_ITERATIONS = READINESS_MIN_ITERATIONS
REQUIRED_DOCS = READINESS_REQUIRED_DOCS
README_LINKS = HARNESS_README_LINKS
WORKFLOWS = CURRENT_WORKFLOWS
EXECUTABLE_PIPELINES = EXECUTABLE_PIPELINE_CONTRACTS
SKILL_AUDIT_GATE = HARNESS_SKILL_AUDIT_GATE
LOCAL_CHECKS = HARNESS_LOCAL_CHECKS
VALIDATION_SURFACES = READINESS_VALIDATION_SURFACES


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    status: str
    evidence: str
    next_action: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether harness-upgrade completion evidence surfaces exist. "
            "This does not run the final verification commands or mark the goal complete."
        )
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root to inspect.")
    parser.add_argument(
        "--progress",
        default=DEFAULT_PROGRESS_PATH,
        help="Progress ledger path, relative to repo root unless absolute.",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--report", default="", help="Optional output report path.")
    parser.add_argument("--strict", action="store_true", help="Exit 2 when any readiness check is WARN.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    progress_path = Path(args.progress)
    if not progress_path.is_absolute():
        progress_path = repo_root / progress_path

    payload = build_readiness_audit(repo_root=repo_root, progress_path=progress_path)
    rendered = render_json(payload) if args.format == "json" else render_markdown(payload)

    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")

    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")

    if args.strict and payload["verdict"] != "PASS":
        return 2
    return 0


def build_readiness_audit(*, repo_root: Path, progress_path: Path) -> dict[str, object]:
    checks = [
        _check_progress_iterations(progress_path),
        _check_progress_active(progress_path),
        _check_required_paths(repo_root=repo_root, rel_paths=REQUIRED_DOCS, check_id="docs", label="required docs"),
        _check_readme_links(repo_root=repo_root),
        _check_adr_set(repo_root=repo_root),
        _check_workflow_taxonomy(repo_root=repo_root),
        _check_required_paths(
            repo_root=repo_root,
            rel_paths=EXECUTABLE_PIPELINES,
            check_id="executable_pipeline_contracts",
            label="executable pipeline contracts",
        ),
        _check_required_paths(
            repo_root=repo_root,
            rel_paths=EXECUTABLE_UNIT_TEMPLATES,
            check_id="unit_templates",
            label="executable unit templates",
        ),
        _check_local_harness_checks(repo_root=repo_root),
        _check_required_paths(
            repo_root=repo_root,
            rel_paths=VALIDATION_SURFACES,
            check_id="validation_surfaces",
            label="validation surfaces",
        ),
    ]
    verdict = "PASS" if all(check.status == "PASS" for check in checks) else "ATTENTION"
    return {
        "schema": SCHEMA,
        "repo": str(repo_root),
        "progress": str(progress_path),
        "verdict": verdict,
        "checks": [asdict(check) for check in checks],
        "note": (
            "This audit checks completion evidence surfaces only. Final closure still requires "
            "running the commands listed in docs/HARNESS_READINESS.md."
        ),
    }


def _check_progress_iterations(progress_path: Path) -> ReadinessCheck:
    if not progress_path.exists():
        return ReadinessCheck(
            "progress_iterations",
            "WARN",
            f"Missing progress ledger `{progress_path}`.",
            "Restore or create the long-running progress ledger before considering closure.",
        )
    text = progress_path.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_iteration_progress(text)
    if parsed is None:
        return ReadinessCheck(
            "progress_iterations",
            "WARN",
            f"`{progress_path}` does not expose `Iterations completed: N of at least M`.",
            "Record the iteration count in the progress ledger.",
        )
    completed, required = parsed
    threshold = max(required, MIN_ITERATIONS)
    if completed < threshold:
        return ReadinessCheck(
            "progress_iterations",
            "WARN",
            f"Progress ledger records {completed} of at least {threshold} iterations.",
            "Continue substantive iterations and update the progress ledger.",
        )
    return ReadinessCheck(
        "progress_iterations",
        "PASS",
        f"Progress ledger records {completed} of at least {threshold} iterations.",
        "Keep the ledger current after each iteration.",
    )


def _check_progress_active(progress_path: Path) -> ReadinessCheck:
    if not progress_path.exists():
        return ReadinessCheck(
            "progress_state",
            "WARN",
            f"Missing progress ledger `{progress_path}`.",
            "Restore the progress ledger and keep the goal state explicit.",
        )
    text = progress_path.read_text(encoding="utf-8", errors="ignore")
    if "Goal state: active" not in text:
        return ReadinessCheck(
            "progress_state",
            "WARN",
            "Progress ledger does not currently say `Goal state: active`.",
            "Keep the goal active until a final requirement-by-requirement closure audit passes.",
        )
    return ReadinessCheck(
        "progress_state",
        "PASS",
        "Progress ledger says `Goal state: active`.",
        "Do not mark complete until final closure evidence is verified.",
    )


def parse_iteration_progress(text: str) -> tuple[int, int] | None:
    match = re.search(r"Iterations completed:\s*(\d+)\s+of at least\s+(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _check_required_paths(*, repo_root: Path, rel_paths: Iterable[str], check_id: str, label: str) -> ReadinessCheck:
    rel_list = list(rel_paths)
    missing = [rel for rel in rel_list if not (repo_root / rel).exists()]
    if missing:
        return ReadinessCheck(
            check_id,
            "WARN",
            f"Missing {label}: {', '.join(missing)}.",
            f"Restore the missing {label} before closure.",
        )
    return ReadinessCheck(
        check_id,
        "PASS",
        f"Found {len(rel_list)} {label}.",
        "Keep these entrypoints protected by validation.",
    )


def _check_readme_links(*, repo_root: Path) -> ReadinessCheck:
    missing: list[str] = []
    for readme in ("README.md", "README.zh-CN.md"):
        path = repo_root / readme
        if not path.exists():
            missing.append(readme)
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        missing.extend(f"{readme}:{link}" for link in README_LINKS if link not in text)
    if missing:
        return ReadinessCheck(
            "readme_links",
            "WARN",
            "Missing README links: " + ", ".join(missing) + ".",
            "Update README entrypoints so new contributors can find the harness docs.",
        )
    return ReadinessCheck(
        "readme_links",
        "PASS",
        "English and Chinese READMEs link the harness docs entrypoints.",
        "Keep README as a compact map, not a duplicate architecture spec.",
    )


def _check_adr_set(*, repo_root: Path) -> ReadinessCheck:
    adr_dir = repo_root / "docs" / "adr"
    adr_files = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")) if adr_dir.exists() else []
    index_path = adr_dir / "README.md"
    if len(adr_files) < 3 or not index_path.exists():
        return ReadinessCheck(
            "adr_set",
            "WARN",
            f"Found {len(adr_files)} ADR files; ADR index exists={index_path.exists()}.",
            "Keep at least the current architecture ADR set and index before closure.",
        )
    return ReadinessCheck(
        "adr_set",
        "PASS",
        f"Found {len(adr_files)} ADR files and an ADR index.",
        "Add ADRs when new hard-to-reverse architecture decisions appear.",
    )


def _check_workflow_taxonomy(*, repo_root: Path) -> ReadinessCheck:
    taxonomy_path = repo_root / "docs" / "PIPELINE_TAXONOMY.md"
    if not taxonomy_path.exists():
        return ReadinessCheck(
            "workflow_taxonomy",
            "WARN",
            "Missing `docs/PIPELINE_TAXONOMY.md`.",
            "Restore the pipeline taxonomy before closure.",
        )
    text = taxonomy_path.read_text(encoding="utf-8", errors="ignore")
    missing = [workflow for workflow in WORKFLOWS if f"`{workflow}`" not in text]
    if missing:
        return ReadinessCheck(
            "workflow_taxonomy",
            "WARN",
            "Pipeline taxonomy is missing workflows: " + ", ".join(missing) + ".",
            "Update the taxonomy so all current workflows are represented.",
        )
    return ReadinessCheck(
        "workflow_taxonomy",
        "PASS",
        f"Pipeline taxonomy references all {len(WORKFLOWS)} current workflows.",
        "Keep maturity and executable status explicit as workflows evolve.",
    )


def _check_local_harness_checks(*, repo_root: Path) -> ReadinessCheck:
    readiness_path = repo_root / "docs" / "HARNESS_READINESS.md"
    if not readiness_path.exists():
        return ReadinessCheck(
            "local_harness_checks",
            "WARN",
            "Missing `docs/HARNESS_READINESS.md`.",
            "Restore the readiness document before closure.",
        )
    text = readiness_path.read_text(encoding="utf-8", errors="ignore")
    missing = [check for check in LOCAL_CHECKS if check not in text]
    if missing:
        return ReadinessCheck(
            "local_harness_checks",
            "WARN",
            "Readiness docs do not list local harness check(s): " + _format_check_list(missing) + ".",
            "Keep validation, readiness, and skill hygiene visible as local checks.",
        )
    return ReadinessCheck(
        "local_harness_checks",
        "PASS",
        "Readiness docs list " + _format_check_list(LOCAL_CHECKS) + ".",
        "Treat new WARN findings as actionable harness issues.",
    )


def _format_check_list(checks: Iterable[str]) -> str:
    return " and ".join(f"`{check}`" for check in checks)


def render_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Harness Readiness Audit",
        "",
        f"- Schema: `{payload['schema']}`",
        f"- Verdict: `{payload['verdict']}`",
        f"- Repo: `{payload['repo']}`",
        f"- Progress ledger: `{payload['progress']}`",
        "",
        str(payload["note"]),
        "",
        "| Check | Status | Evidence | Next action |",
        "|---|---|---|---|",
    ]
    for item in payload["checks"]:
        check = dict(item)
        lines.append(
            "| {id} | {status} | {evidence} | {next_action} |".format(
                id=_escape_cell(str(check["id"])),
                status=_escape_cell(str(check["status"])),
                evidence=_escape_cell(str(check["evidence"])),
                next_action=_escape_cell(str(check["next_action"])),
            )
        )
    return "\n".join(lines) + "\n"


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
