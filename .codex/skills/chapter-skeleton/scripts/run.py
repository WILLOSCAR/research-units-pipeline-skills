from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _is_placeholder(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    return "(placeholder)" in low or "<!-- scaffold" in low or "todo" in low


def _chapter_h3_budgets(*, chapter_count: int, total_limit: int, preferred_per_chapter: int) -> list[int]:
    if chapter_count <= 0:
        return []
    preferred = max(1, int(preferred_per_chapter))
    usable_total = max(chapter_count, min(max(1, int(total_limit)), chapter_count * preferred))
    base, remainder = divmod(usable_total, chapter_count)
    return [min(preferred, base + (1 if index < remainder else 0)) for index in range(chapter_count)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
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
        backup_existing,
        dump_yaml,
        load_workspace_pipeline_spec,
        load_yaml,
        parse_semicolon_list,
        refinement_marker_is_current,
        workspace_query_scalar,
    )

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["outline/taxonomy.yml", "GOAL.md"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/chapter_skeleton.yml"]
    taxonomy_path = workspace / inputs[0]
    goal_path = workspace / inputs[1] if len(inputs) > 1 else workspace / "GOAL.md"
    out_path = workspace / outputs[0]

    freeze_marker = out_path.parent / "chapter_skeleton.refined.ok"
    prerequisites = [out_path, taxonomy_path, goal_path, Path(__file__)]
    if refinement_marker_is_current(freeze_marker, prerequisites):
        return 0
    if freeze_marker.exists():
        freeze_marker.unlink()
    if out_path.exists() and out_path.stat().st_size > 0:
        if not _is_placeholder(out_path.read_text(encoding="utf-8", errors="ignore")):
            backup_existing(out_path)

    taxonomy = load_yaml(taxonomy_path) if taxonomy_path.exists() else None
    if not isinstance(taxonomy, list) or not taxonomy:
        raise SystemExit(f"Invalid taxonomy in {taxonomy_path}")

    spec = load_workspace_pipeline_spec(workspace)
    preferred_h3 = int(getattr(spec, "core_chapter_h3_target", 0) or 3)
    draft_profile = str(workspace_query_scalar(workspace, "draft_profile", "survey") or "survey").strip().lower()
    structure_policy = (getattr(spec, "quality_contract", {}) or {}).get("structure_policy") or {}
    max_by_profile = structure_policy.get("max_h3_by_profile") or {}
    default_limit = {"course_paper": 6, "deep": 12}.get(draft_profile, 10)
    try:
        total_h3_limit = int(max_by_profile.get(draft_profile) or default_limit)
    except Exception:
        total_h3_limit = default_limit
    goal_line = ""
    if goal_path.exists():
        for raw in goal_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                goal_line = line
                break

    topics = [topic for topic in taxonomy if isinstance(topic, dict) and str(topic.get("name") or "").strip()]
    budgets = _chapter_h3_budgets(
        chapter_count=len(topics),
        total_limit=total_h3_limit,
        preferred_per_chapter=preferred_h3,
    )
    skeleton: list[dict[str, Any]] = []
    section_no = 3
    for topic, budget in zip(topics, budgets):
        title = str(topic.get("name") or "").strip()
        desc = str(topic.get("description") or "").strip()
        children = topic.get("children") or []
        explicit_children = [
            child
            for child in children
            if isinstance(child, dict) and str(child.get("name") or "").strip()
        ]
        target_h3 = min(budget, len(explicit_children)) if explicit_children else budget
        seed_topics = [
            str(child.get("name") or "").strip()
            for child in explicit_children
        ][:target_h3]
        rationale = desc or (f"retrieval-informed chapter for {title}" if not goal_line else f"{title} within {goal_line}")
        skeleton.append(
            {
                "id": str(section_no),
                "title": title,
                "rationale": rationale,
                "seed_topics": seed_topics,
                "target_h3_count": target_h3,
            }
        )
        section_no += 1

    dump_yaml(out_path, skeleton)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
