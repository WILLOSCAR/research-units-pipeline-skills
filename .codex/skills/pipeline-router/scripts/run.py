from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--checkpoint", default="C0")
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import (
        ensure_decisions_approval_checklist,
        parse_semicolon_list,
        seed_queries_from_topic,
        upsert_checkpoint_block,
    )

    checkpoint = str(args.checkpoint or "C0").strip() or "C0"
    if checkpoint != "C0":
        from tooling.checkpoint_brief import write_checkpoint_brief

        print(
            "warning: legacy pipeline-router checkpoint invocation delegated to checkpoint-brief; "
            "migrate the Workspace Unit contract when convenient",
            file=sys.stderr,
        )
        write_checkpoint_brief(
            workspace=Path(args.workspace),
            checkpoint=checkpoint,
            inputs=parse_semicolon_list(args.inputs),
        )
        return 0

    workspace = Path(args.workspace).resolve()
    decisions_path = workspace / "DECISIONS.md"
    ensure_decisions_approval_checklist(decisions_path)
    goal = _read_goal(workspace)
    pipeline = _read_pipeline_lock(workspace)
    goal_line = goal or "(fill your topic or goal in GOAL.md)"
    pipeline_line = pipeline or "(unbound; select a Workflow before execution)"
    constraint_questions = [
        f"## Kickoff - {goal_line}",
        "",
        f"- Pipeline: `{pipeline_line}`",
        f"- Workspace: `{_workspace_hint(workspace, repo_root)}`",
        "",
        "Confirm only constraints that change execution:",
        "- reader, language, length, and output format",
        "- evidence depth and time window",
        "- must-include and hard-exclude scope",
        "- required human checkpoints",
    ]
    if _pipeline_name(pipeline) == "source-tutorial":
        constraint_questions.extend(
            [
                "",
                "Source intake:",
                "- fixed source pack: local paths or URLs and accepted source formats",
                "- which sources are required versus optional, plus the missing-source policy",
                "- keep the corpus fixed; do not expand it unless the Goal explicitly changes",
                "- audience, prerequisites, and target tutorial output formats",
            ]
        )
    constraint_questions.append("")
    block = "\n".join(constraint_questions)
    upsert_checkpoint_block(decisions_path, "C0", block)
    seed_queries_from_topic(workspace / "queries.md", goal)
    return 0


def _read_goal(workspace: Path) -> str:
    path = workspace / "GOAL.md"
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "-", ">", "<!--")):
            continue
        if "写一句话描述" in line or "fill" in line.lower():
            continue
        return line
    return ""


def _read_pipeline_lock(workspace: Path) -> str:
    path = workspace / "PIPELINE.lock.md"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("pipeline:"):
            return line.split("pipeline:", 1)[1].strip()
    return ""


def _workspace_hint(workspace: Path, repo_root: Path) -> str:
    try:
        return str(workspace.relative_to(repo_root))
    except ValueError:
        return str(workspace)


def _pipeline_name(pipeline: str) -> str:
    name = Path(str(pipeline or "")).name
    return name[: -len(".pipeline.md")] if name.endswith(".pipeline.md") else name


if __name__ == "__main__":
    raise SystemExit(main())
