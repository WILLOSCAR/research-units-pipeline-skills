from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


_KNOWN_SECTION_NAMES = {
    "Goal",
    "Scope",
    "Audience",
    "Constraints",
    "Exclusions",
    "Rubric",
    "Targets",
    "Focus lenses after C2",
    "Query buckets",
    "Table policy",
    "Open questions",
}

_REQUIRED_QUERY_DEFAULT_KEYS = (
    "draft_profile",
    "max_results",
    "core_size",
    "direction_pool_min",
    "direction_pool_max",
    "idea_screen_top_n",
    "idea_shortlist_size",
    "report_top_n",
    "evidence_mode",
)


def _topic_tokens(topic: str) -> list[str]:
    toks = [t for t in re.findall(r"[A-Za-z0-9]+", str(topic or "")) if t]
    return toks[:6] if toks else ["research", "ideas"]


def _require_string(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SystemExit(f"`{field_name}` must be a non-empty string in idea-brief/assets/brief_contract.json.")
    return text


def _require_string_list(value: object, *, field_name: str, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise SystemExit(f"`{field_name}` must be a JSON array in idea-brief/assets/brief_contract.json.")
    items = [str(item or "").strip() for item in value if str(item or "").strip()]
    if len(items) < min_items:
        raise SystemExit(f"`{field_name}` must contain at least {min_items} non-empty item(s) in idea-brief/assets/brief_contract.json.")
    return items


def _require_mapping(value: object, *, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise SystemExit(f"`{field_name}` must be a JSON object in idea-brief/assets/brief_contract.json.")
    return dict(value)


def _validate_contract(raw: dict) -> dict:
    required_sections = _require_string_list(raw.get("required_sections"), field_name="required_sections")
    unknown_sections = sorted(set(required_sections) - _KNOWN_SECTION_NAMES)
    if unknown_sections:
        raise SystemExit(
            "idea-brief/assets/brief_contract.json declares unknown `required_sections`: "
            + ", ".join(unknown_sections)
        )

    goal = _require_mapping(raw.get("goal"), field_name="goal")
    goal = {
        "deliverable": _require_string(goal.get("deliverable"), field_name="goal.deliverable"),
        "objective": _require_string(goal.get("objective"), field_name="goal.objective"),
    }

    scope = _require_mapping(raw.get("scope"), field_name="scope")
    scope = {
        "in_scope": _require_string_list(scope.get("in_scope"), field_name="scope.in_scope"),
        "out_of_scope": _require_string_list(scope.get("out_of_scope"), field_name="scope.out_of_scope"),
    }

    rubric_rows = []
    rubric = raw.get("rubric")
    if not isinstance(rubric, list) or not rubric:
        raise SystemExit("`rubric` must be a non-empty JSON array in idea-brief/assets/brief_contract.json.")
    for idx, row in enumerate(rubric):
        if not isinstance(row, dict):
            raise SystemExit(f"`rubric[{idx}]` must be a JSON object in idea-brief/assets/brief_contract.json.")
        try:
            weight = float(row.get("weight"))
        except Exception as exc:
            raise SystemExit(f"`rubric[{idx}].weight` must be numeric in idea-brief/assets/brief_contract.json.") from exc
        rubric_rows.append(
            {
                "name": _require_string(row.get("name"), field_name=f"rubric[{idx}].name"),
                "weight": weight,
                "note": _require_string(row.get("note"), field_name=f"rubric[{idx}].note"),
            }
        )

    targets_template = _require_mapping(raw.get("targets_template"), field_name="targets_template")
    for key in ("candidate_retrieval_pool", "signal_table_rows", "memo_lead_directions", "reading_guide_rows_per_lead_direction"):
        targets_template[key] = _require_string(targets_template.get(key), field_name=f"targets_template.{key}")

    validated = {
        "required_sections": required_sections,
        "goal": goal,
        "audience": _require_string_list(raw.get("audience"), field_name="audience"),
        "scope": scope,
        "constraints": _require_string_list(raw.get("constraints"), field_name="constraints"),
        "default_exclusions": _require_string_list(raw.get("default_exclusions"), field_name="default_exclusions"),
        "query_bucket_templates": _require_string_list(raw.get("query_bucket_templates"), field_name="query_bucket_templates"),
        "rubric": rubric_rows,
        "targets_template": targets_template,
        "focus_placeholder": _require_string(raw.get("focus_placeholder"), field_name="focus_placeholder"),
        "table_policy": _require_string_list(raw.get("table_policy"), field_name="table_policy"),
        "open_questions": _require_string_list(raw.get("open_questions"), field_name="open_questions"),
        "decisions_template": _require_string_list(raw.get("decisions_template"), field_name="decisions_template"),
    }
    return validated


def _load_contract() -> dict:
    asset_path = Path(__file__).resolve().parents[1] / "assets" / "brief_contract.json"
    data = json.loads(asset_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("idea-brief/assets/brief_contract.json must be a JSON object.")
    required_keys = {
        "required_sections",
        "goal",
        "audience",
        "scope",
        "constraints",
        "default_exclusions",
        "query_bucket_templates",
        "rubric",
        "targets_template",
        "focus_placeholder",
        "table_policy",
        "open_questions",
        "decisions_template",
    }
    missing = sorted(key for key in required_keys if key not in data)
    if missing:
        raise SystemExit(f"idea-brief/assets/brief_contract.json is missing required keys: {', '.join(missing)}")
    return _validate_contract(data)


def _load_query_defaults(workspace: Path) -> dict[str, str]:
    from tooling.common import pipeline_query_defaults

    def _parse_positive_int(raw_value: object, *, field_name: str) -> int:
        try:
            parsed = int(str(raw_value or "").strip())
        except Exception as exc:
            raise SystemExit(f"`query_defaults.{field_name}` must be a positive integer in the active pipeline contract.") from exc
        if parsed <= 0:
            raise SystemExit(f"`query_defaults.{field_name}` must be a positive integer in the active pipeline contract.")
        return parsed

    raw = pipeline_query_defaults(workspace)
    missing = [key for key in _REQUIRED_QUERY_DEFAULT_KEYS if not str(raw.get(key) or "").strip()]
    if missing:
        raise SystemExit(
            "Missing required `query_defaults` in the active pipeline contract for idea-brief: "
            + ", ".join(missing)
        )
    out = {key: str(raw.get(key) or "").strip() for key in _REQUIRED_QUERY_DEFAULT_KEYS}
    direction_pool_min = _parse_positive_int(out["direction_pool_min"], field_name="direction_pool_min")
    direction_pool_max = _parse_positive_int(out["direction_pool_max"], field_name="direction_pool_max")
    idea_screen_top_n = _parse_positive_int(out["idea_screen_top_n"], field_name="idea_screen_top_n")
    idea_shortlist_size = _parse_positive_int(out["idea_shortlist_size"], field_name="idea_shortlist_size")
    report_top_n = _parse_positive_int(out["report_top_n"], field_name="report_top_n")
    _parse_positive_int(out["max_results"], field_name="max_results")
    _parse_positive_int(out["core_size"], field_name="core_size")
    if direction_pool_min > direction_pool_max:
        raise SystemExit("Invalid ideation contract: `direction_pool_min` exceeds `direction_pool_max`.")
    if idea_screen_top_n > direction_pool_max:
        raise SystemExit("Invalid ideation contract: `idea_screen_top_n` exceeds `direction_pool_max`.")
    if report_top_n > idea_shortlist_size:
        raise SystemExit("Invalid ideation contract: `report_top_n` exceeds `idea_shortlist_size`.")
    return out


def _normalize_topic_for_query_buckets(topic: str) -> str:
    text = re.sub(r"\s+", " ", str(topic or "")).strip(" ,;:-")
    if not text:
        return "research ideas"
    patterns = [
        r"(?i)^(?:build|create|generate|develop|draft|write|brainstorm|find|explore|identify|propose)\s+.+?\b(?:research\s+ideas?|research\s+directions?|ideas?|directions?)\b\s+(?:for|on|about)\s+(.+)$",
        r"(?i)^(?:research\s+ideas?|research\s+directions?|ideas?|directions?)\s+(?:for|on|about)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:-")
            if candidate:
                return candidate
    return text


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

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list
    from tooling.ideation import extract_goal_from_goal_md

    workspace = Path(args.workspace).resolve()
    contract = _load_contract()
    outputs = parse_semicolon_list(args.outputs) or ["output/trace/IDEA_BRIEF.md", "queries.md", "DECISIONS.md"]
    brief_rel = next((x for x in outputs if x.endswith("IDEA_BRIEF.md")), "output/trace/IDEA_BRIEF.md")
    queries_rel = next((x for x in outputs if x.endswith("queries.md")), "queries.md")
    decisions_rel = next((x for x in outputs if x.endswith("DECISIONS.md")), "DECISIONS.md")

    brief_path = workspace / brief_rel
    queries_path = workspace / queries_rel
    decisions_path = workspace / decisions_rel
    ensure_dir(brief_path.parent)
    ensure_dir(queries_path.parent)
    ensure_dir(decisions_path.parent)

    topic = extract_goal_from_goal_md(workspace / "GOAL.md")
    query_defaults = _load_query_defaults(workspace)
    draft_profile = query_defaults["draft_profile"]
    max_results = query_defaults["max_results"]
    core_size = query_defaults["core_size"]
    direction_pool_min = query_defaults["direction_pool_min"]
    direction_pool_max = query_defaults["direction_pool_max"]
    screen_top_n = query_defaults["idea_screen_top_n"]
    shortlist_size = query_defaults["idea_shortlist_size"]
    report_top_n = query_defaults["report_top_n"]
    evidence_mode = query_defaults["evidence_mode"]
    toks = _topic_tokens(_normalize_topic_for_query_buckets(topic))
    topic_query = " ".join(toks)
    query_buckets = [str(template).format(topic=topic_query) for template in (contract.get("query_bucket_templates") or [])]
    default_exclusions = [str(item) for item in (contract.get("default_exclusions") or []) if str(item).strip()]
    rubric_rows = contract.get("rubric") or []
    scope = contract.get("scope") or {}
    targets_template = contract.get("targets_template") or {}
    section_blocks: dict[str, list[str]] = {
        "Goal": [
            "## Goal",
            f"- Topic: {topic}",
            f"- Deliverable: {contract.get('goal', {}).get('deliverable', '`output/REPORT.md` + `output/APPENDIX.md` + `output/REPORT.json`')}",
            f"- Objective: {contract.get('goal', {}).get('objective', '')}",
        ],
        "Scope": [
            "## Scope",
            "- In scope:",
            *[f"  - {str(line).format(topic=topic)}" for line in (scope.get("in_scope") or [])],
            "- Out of scope:",
            *[f"  - {str(line).format(topic=topic)}" for line in (scope.get("out_of_scope") or [])],
        ],
        "Audience": [
            "## Audience",
            *[f"- {line}" for line in (contract.get("audience") or [])],
        ],
        "Constraints": [
            "## Constraints",
            *[f"- {str(line).format(evidence_mode=evidence_mode)}" for line in (contract.get("constraints") or [])],
        ],
        "Exclusions": [
            "## Exclusions",
            *[f"- {line}" for line in default_exclusions],
        ],
        "Rubric": [
            "## Rubric",
            "| criterion | weight | note |",
            "|---|---:|---|",
            *[
                f"| {str(row.get('name') or '').strip()} | {float(row.get('weight') or 0.0):.2f} | {str(row.get('note') or '').strip()} |"
                for row in rubric_rows
                if str(row.get("name") or "").strip() and str(row.get("note") or "").strip()
            ],
        ],
        "Targets": [
            "## Targets",
            f"- Candidate retrieval pool: {targets_template.get('candidate_retrieval_pool', '80-240 focused candidates')}",
            f"- Core set size: {core_size}",
            f"- Signal table rows: {targets_template.get('signal_table_rows', '10-20')}",
            f"- Direction pool size: {direction_pool_min}-{direction_pool_max}",
            f"- Screened directions: {screen_top_n}",
            f"- Final shortlist size: {shortlist_size}",
            f"- Memo lead directions: {report_top_n or targets_template.get('memo_lead_directions', '3')}",
            f"- Reading-guide rows per lead direction: {targets_template.get('reading_guide_rows_per_lead_direction', '>=3 anchor papers')}",
        ],
        "Focus lenses after C2": [
            "## Focus lenses after C2",
            f"- Focus clusters: {contract.get('focus_placeholder', '(to be filled after C2 approval)')}",
        ],
        "Query buckets": [
            "## Query Buckets",
            *[f"{idx}. {q}" for idx, q in enumerate(query_buckets, start=1)],
        ],
        "Table policy": [
            "## Table Policy",
            *[f"- {line}" for line in (contract.get("table_policy") or [])],
        ],
        "Open questions": [
            "## Open Questions",
            *[f"- {line}" for line in (contract.get("open_questions") or [])],
        ],
    }

    brief_lines = ["# IDEA_BRIEF", ""]
    for section_name in contract.get("required_sections") or []:
        block = section_blocks.get(str(section_name))
        if not block:
            raise SystemExit(f"Unknown idea-brief section in contract: {section_name}")
        brief_lines.extend(block)
        brief_lines.append("")
    atomic_write_text(brief_path, "\n".join(brief_lines).rstrip() + "\n")

    query_lines = [
        "# queries",
        "",
        f'- draft_profile: "{draft_profile}"',
        f'- max_results: "{max_results}"',
        f'- core_size: "{core_size}"',
        f'- direction_pool_min: "{direction_pool_min}"',
        f'- direction_pool_max: "{direction_pool_max}"',
        f'- idea_screen_top_n: "{screen_top_n}"',
        f'- idea_shortlist_size: "{shortlist_size}"',
        f'- report_top_n: "{report_top_n}"',
        f'- evidence_mode: "{evidence_mode}"',
        '- keywords:',
    ]
    for q in query_buckets:
        query_lines.append(f"  - {q}")
    query_lines.extend([
        '- exclude:',
    ])
    for item in default_exclusions:
        query_lines.append(f"  - {item}")
    query_lines.extend([
        '',
    ])
    atomic_write_text(queries_path, "\n".join(query_lines).rstrip() + "\n")

    if not decisions_path.exists() or decisions_path.stat().st_size == 0:
        atomic_write_text(decisions_path, "\n".join(contract.get("decisions_template") or []).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
