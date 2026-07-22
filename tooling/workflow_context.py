from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from tooling.harness_contracts import EXECUTABLE_PIPELINE_CONTRACTS
from tooling.pipeline_spec import PipelineSpec
from tooling.skill_invocation_eval import SkillProfile, load_skill_catalog


WORKFLOW_CONTEXT_SCHEMA = "workflow-context-footprint.v1"


def build_workflow_context_footprint(*, repo_root: Path) -> dict[str, Any]:
    """Measure declared Workflow-to-Skill context without claiming runtime token usage."""

    repo_root = repo_root.resolve()
    catalog = load_skill_catalog(repo_root / ".codex" / "skills")
    workflows = [
        _workflow_record(
            repo_root=repo_root,
            spec=PipelineSpec.load(repo_root / relpath),
            catalog=catalog,
        )
        for relpath in EXECUTABLE_PIPELINE_CONTRACTS
    ]
    return {
        "schema": WORKFLOW_CONTEXT_SCHEMA,
        "method": {
            "unit_source": "templates/UNITS.<workflow>.csv",
            "skill_source": ".codex/skills/<skill>/SKILL.md",
            "metric": "UTF-8 character count",
            "routing_proxy": "all repository Skill descriptions, counted once",
            "execution_proxy": "the selected Skill body for each declared Unit, counted serially",
            "interpretation": (
                "Two separate static context proxies. They are not observed prompt tokens and are "
                "not added together as one runtime estimate."
            ),
        },
        "catalog": {
            "skill_count": len(catalog),
            "description_chars": sum(profile.description_chars for profile in catalog.values()),
            "body_chars": sum(profile.body_chars for profile in catalog.values()),
        },
        "workflows": workflows,
    }


def render_workflow_context_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Workflow Context Footprint",
        "",
        str(payload["method"]["interpretation"]),
        "",
        "| Workflow | Units | Unique Skills | Repeated invocations | Routing descriptions | Unique selected bodies | Serial selected bodies | Largest body |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for workflow in payload["workflows"]:
        lines.append(
            "| {workflow} | {unit_count} | {unique_skill_count} | {repeated_skill_invocations} | "
            "{routing_description_chars} | {unique_selected_body_chars} | {serial_selected_body_chars} | {largest_skill_body_chars} |".format(
                **workflow
            )
        )
    lines.extend(
        [
            "",
            "`Routing descriptions` counts the full repository description catalog once. "
            "`Unique selected bodies` counts each Workflow Skill body once; `Serial selected bodies` "
            "counts one selected body per Unit, including repeats. These are distinct static models, "
            "not a measured token trace.",
            "",
            "## Largest Declared Skills",
            "",
        ]
    )
    for workflow in payload["workflows"]:
        largest = ", ".join(
            f"`{item['skill']}` ({item['body_chars']})"
            for item in workflow["largest_skills"]
        )
        lines.append(f"- `{workflow['workflow']}`: {largest or 'none'}")
    return "\n".join(lines).rstrip() + "\n"


def _workflow_record(
    *,
    repo_root: Path,
    spec: PipelineSpec,
    catalog: dict[str, SkillProfile],
) -> dict[str, Any]:
    template_path = repo_root / spec.units_template
    with template_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    invocations = [str(row.get("skill") or "").strip() for row in rows]
    invocations = [skill for skill in invocations if skill]
    unknown = sorted(set(invocations).difference(catalog))
    if unknown:
        raise ValueError(
            f"Workflow `{spec.name}` references Skills missing from the catalog: {', '.join(unknown)}"
        )
    counts = Counter(invocations)
    unique_skills = list(dict.fromkeys(invocations))
    profiles = [catalog[skill] for skill in unique_skills]
    serial_body_chars = sum(catalog[skill].body_chars for skill in invocations)
    largest = sorted(profiles, key=lambda profile: (-profile.body_chars, profile.name))[:5]
    return {
        "workflow": spec.name,
        "pipeline": str(spec.path.relative_to(repo_root)),
        "units_template": spec.units_template,
        "unit_count": len(rows),
        "skill_invocation_count": len(invocations),
        "unique_skill_count": len(unique_skills),
        "repeated_skill_invocations": sum(count - 1 for count in counts.values()),
        "routing_description_chars": sum(profile.description_chars for profile in catalog.values()),
        "unique_selected_body_chars": sum(profile.body_chars for profile in profiles),
        "serial_selected_body_chars": serial_body_chars,
        "largest_skill_body_chars": largest[0].body_chars if largest else 0,
        "required_skills": unique_skills,
        "largest_skills": [
            {
                "skill": profile.name,
                "description_chars": profile.description_chars,
                "body_chars": profile.body_chars,
            }
            for profile in largest
        ],
    }
