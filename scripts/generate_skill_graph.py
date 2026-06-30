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
SKILLS_DIR = REPO_ROOT / ".codex" / "skills"
PIPELINES_DIR = REPO_ROOT / "pipelines"
sys.path.insert(0, str(REPO_ROOT))

from tooling.pipeline_spec import PipelineSpec


@dataclass(frozen=True)
class SkillIO:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class UnitRow:
    unit_id: str
    skill: str
    checkpoint: str
    depends_on: tuple[str, ...]
    owner: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Mermaid graphs for skills/pipelines.")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "workspaces" / "skill-graph.md"),
        help="Output Markdown path (default: workspaces/skill-graph.md).",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    skills = _load_skill_ios(SKILLS_DIR)
    pipelines = _load_pipelines(PIPELINES_DIR)

    md = _render_markdown(skills=skills, pipelines=pipelines)
    output_path.write_text(md, encoding="utf-8")
    return 0


def _render_markdown(*, skills: list[SkillIO], pipelines: list[tuple[Path, dict[str, Any], str, PipelineSpec | None]]) -> str:
    lines: list[str] = [
        "# Skill Graph",
        "",
        "- Regenerate: `uv run python scripts/generate_skill_graph.py`",
        "- This is a generated developer aid. Keep durable architecture docs in `docs/`.",
        "",
        "## Global skill ⇄ artifact graph (from SKILL.md Inputs/Outputs)",
        "",
        "```mermaid",
        *_render_global_graph(skills),
        "```",
        "",
        "## Pipeline execution graphs (from templates/UNITS.*.csv)",
        "",
    ]

    for pipeline_path, fm, body, spec in pipelines:
        if spec is not None and spec.docs_hidden:
            continue
        pipeline_name = str(fm.get("name") or pipeline_path.stem).strip()
        units_template = str((spec.units_template if spec is not None else fm.get("units_template")) or "").strip()
        stage_titles = _parse_stage_titles(body, spec=spec)

        units_path = (REPO_ROOT / units_template).resolve() if units_template else None
        if not units_path or not units_path.exists():
            lines.extend([f"### {pipeline_name}", "", f"- Missing units template: `{units_template}`", ""])
            continue

        units = _load_units_template(units_path)
        lines.extend(
            [
                f"### {pipeline_name}",
                "",
                "```mermaid",
                *_render_pipeline_graph(
                    pipeline_name=pipeline_name,
                    units=units,
                    stage_titles=stage_titles,
                ),
                "```",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _load_skill_ios(skills_dir: Path) -> list[SkillIO]:
    out: list[SkillIO] = []
    for skill_dir in sorted([p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))]):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm, body = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = str(fm.get("name") or skill_dir.name).strip()
        inputs, outputs = _parse_inputs_outputs(body)
        out.append(SkillIO(name=name, inputs=tuple(sorted(inputs)), outputs=tuple(sorted(outputs))))
    return out


def _parse_inputs_outputs(body: str) -> tuple[set[str], set[str]]:
    inputs: set[str] = set()
    outputs: set[str] = set()

    section = None  # "in" | "out" | None
    for raw in body.splitlines():
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


def _render_global_graph(skills: list[SkillIO]) -> list[str]:
    lines: list[str] = [
        "flowchart LR",
        "  classDef skill fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1;",
        "  classDef file fill:#f1f8e9,stroke:#7cb342,color:#1b5e20;",
        "",
    ]

    file_nodes: dict[str, str] = {}
    skill_nodes: dict[str, str] = {}
    declared: set[str] = set()

    def file_id(path: str) -> str:
        if path not in file_nodes:
            file_nodes[path] = f"F_{_safe_id(path)}"
        return file_nodes[path]

    def skill_id(name: str) -> str:
        if name not in skill_nodes:
            skill_nodes[name] = f"S_{_safe_id(name)}"
        return skill_nodes[name]

    for skill in skills:
        sid = skill_id(skill.name)
        if sid not in declared:
            lines.append(f'  {sid}["`{skill.name}`"]:::skill')
            declared.add(sid)
        for inp in skill.inputs:
            fid = file_id(inp)
            if fid not in declared:
                lines.append(f'  {fid}["`{inp}`"]:::file')
                declared.add(fid)
            lines.append(f"  {fid} --> {sid}")
        for out in skill.outputs:
            fid = file_id(out)
            if fid not in declared:
                lines.append(f'  {fid}["`{out}`"]:::file')
                declared.add(fid)
            lines.append(f"  {sid} --> {fid}")
    return lines


def _load_pipelines(pipelines_dir: Path) -> list[tuple[Path, dict[str, Any], str, PipelineSpec | None]]:
    out: list[tuple[Path, dict[str, Any], str, PipelineSpec | None]] = []
    for pipeline_path in sorted(pipelines_dir.glob("*.pipeline.md")):
        try:
            fm, body = _split_frontmatter(pipeline_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            spec = PipelineSpec.load(pipeline_path)
        except Exception:
            spec = None
        out.append((pipeline_path, fm, body, spec))
    return out


def _parse_stage_titles(body: str, *, spec: PipelineSpec | None = None) -> dict[str, str]:
    if spec is not None and spec.stages:
        return {stage_id: stage.title for stage_id, stage in spec.stages.items()}

    titles: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        m = re.match(r"^##\s+Stage\s+\d+\s*-\s*(.+?)\s*\((C\d+)\)", line)
        if not m:
            continue
        stage_title = m.group(1).strip()
        checkpoint = m.group(2).strip()
        titles[checkpoint] = stage_title
    return titles


def _load_units_template(path: Path) -> list[UnitRow]:
    rows: list[UnitRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            unit_id = str(row.get("unit_id") or "").strip()
            if not unit_id:
                continue
            depends = tuple(_split_semicolon(row.get("depends_on") or ""))
            rows.append(
                UnitRow(
                    unit_id=unit_id,
                    skill=str(row.get("skill") or "").strip(),
                    checkpoint=str(row.get("checkpoint") or "").strip(),
                    depends_on=depends,
                    owner=str(row.get("owner") or "").strip(),
                )
            )
    return rows


def _render_pipeline_graph(
    *,
    pipeline_name: str,
    units: list[UnitRow],
    stage_titles: dict[str, str],
) -> list[str]:
    lines: list[str] = [
        "flowchart LR",
        "  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;",
        "  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;",
        "",
    ]

    by_checkpoint: dict[str, list[UnitRow]] = {}
    for u in units:
        by_checkpoint.setdefault(u.checkpoint or "?", []).append(u)

    for checkpoint in sorted(by_checkpoint.keys()):
        title = stage_titles.get(checkpoint)
        label = f"{checkpoint} - {title}" if title else checkpoint
        lines.append(f'  subgraph "{label}"')
        for u in by_checkpoint[checkpoint]:
            uid = f"U_{_safe_id(u.unit_id)}"
            skill = u.skill or "(no-skill)"
            lines.append(f'    {uid}["`{u.unit_id}`\\n`{skill}`"]:::unit')
            if u.owner.upper() == "HUMAN":
                lines.append(f"    class {uid} human")
        lines.append("  end")
        lines.append("")

    unit_ids = {u.unit_id for u in units}
    for u in units:
        dst = f"U_{_safe_id(u.unit_id)}"
        for dep in u.depends_on:
            if dep not in unit_ids:
                continue
            src = f"U_{_safe_id(dep)}"
            lines.append(f"  {src} --> {dst}")

    return lines


def _safe_id(value: str) -> str:
    # Mermaid node IDs: keep to [A-Za-z0-9_]
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "X"


def _split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("file must start with YAML front matter (`---`).")
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
        raise ValueError("YAML front matter must be a mapping.")
    body = "\n".join(lines[end_idx + 1 :])
    return fm, body


if __name__ == "__main__":
    raise SystemExit(main())
