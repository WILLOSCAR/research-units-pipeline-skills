from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

import yaml


CORPUS_SCHEMA = "skill-invocation-cases.v1"
CANDIDATE_PACK_SCHEMA = "skill-invocation-candidate-pack.v1"
PREDICTION_SCHEMA = "skill-invocation-prediction.v1"
EVALUATION_SCHEMA = "skill-invocation-evaluation.v1"
NO_REPO_SKILL = "none"
DESCRIPTION_CONTEXT_LOAD_LIMIT = 420


@dataclass(frozen=True)
class SkillProfile:
    name: str
    path: str
    description: str
    description_chars: int
    body_chars: int
    body_nonempty_lines: int


@dataclass(frozen=True)
class InvocationCase:
    id: str
    prompt: str
    expected_primary: str
    allowed_support: tuple[str, ...]
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class InvocationPrediction:
    case_id: str
    selected_skills: tuple[str, ...]
    model: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    note: str = ""


def load_skill_catalog(skills_dir: Path) -> dict[str, SkillProfile]:
    catalog: dict[str, SkillProfile] = {}
    for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir() and not path.name.startswith((".", "_"))):
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.exists():
            continue
        try:
            frontmatter, body = _split_frontmatter(skill_path.read_text(encoding="utf-8", errors="ignore"))
        except (ValueError, yaml.YAMLError) as exc:
            raise ValueError(f"Cannot parse {skill_path}: {exc}") from exc
        name = str(frontmatter.get("name") or skill_dir.name).strip()
        if not name:
            raise ValueError(f"Skill at {skill_path} has no name.")
        if name in catalog:
            raise ValueError(f"Duplicate Skill name `{name}` in {skill_path} and {catalog[name].path}.")
        description = " ".join(str(frontmatter.get("description") or "").split())
        catalog[name] = SkillProfile(
            name=name,
            path=skill_path.as_posix(),
            description=description,
            description_chars=len(description),
            body_chars=len(body),
            body_nonempty_lines=sum(1 for line in body.splitlines() if line.strip()),
        )
    if not catalog:
        raise ValueError(f"No Skills found under {skills_dir}.")
    return catalog


def load_invocation_corpus(path: Path, *, catalog: dict[str, SkillProfile]) -> tuple[str, list[InvocationCase]]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Cannot parse invocation corpus {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Invocation corpus must be a YAML mapping.")
    if payload.get("schema") != CORPUS_SCHEMA:
        raise ValueError(f"Invocation corpus schema must be `{CORPUS_SCHEMA}`.")
    scope = str(payload.get("scope") or "").strip()
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Invocation corpus must contain a non-empty `cases` list.")

    cases: list[InvocationCase] = []
    seen_ids: set[str] = set()
    issues: list[str] = []
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            issues.append(f"cases[{index}] must be a mapping")
            continue
        case_id = str(raw_case.get("id") or "").strip()
        prompt = str(raw_case.get("prompt") or "").strip()
        expected = str(raw_case.get("expected_primary") or "").strip()
        allowed = _string_tuple(raw_case.get("allowed_support"), field=f"cases[{index}].allowed_support", issues=issues)
        forbidden = _string_tuple(raw_case.get("forbidden"), field=f"cases[{index}].forbidden", issues=issues)

        if not case_id:
            issues.append(f"cases[{index}].id must be non-empty")
        elif case_id in seen_ids:
            issues.append(f"duplicate case id `{case_id}`")
        seen_ids.add(case_id)
        if not prompt:
            issues.append(f"case `{case_id or index}` has an empty prompt")
        if expected != NO_REPO_SKILL and expected not in catalog:
            issues.append(f"case `{case_id or index}` references unknown expected Skill `{expected}`")
        for skill in (*allowed, *forbidden):
            if skill not in catalog:
                issues.append(f"case `{case_id or index}` references unknown repository Skill `{skill}`")
        if expected in forbidden:
            issues.append(f"case `{case_id or index}` forbids its expected primary Skill `{expected}`")
        overlap = sorted(set(allowed).intersection(forbidden))
        if overlap:
            issues.append(f"case `{case_id or index}` both allows and forbids: {', '.join(overlap)}")
        if expected in allowed:
            issues.append(f"case `{case_id or index}` repeats its primary Skill in `allowed_support`")

        cases.append(
            InvocationCase(
                id=case_id,
                prompt=prompt,
                expected_primary=expected,
                allowed_support=allowed,
                forbidden=forbidden,
            )
        )

    if issues:
        raise ValueError("Invalid invocation corpus:\n- " + "\n- ".join(issues))
    return scope, cases


def load_invocation_predictions(path: Path, *, case_ids: set[str]) -> list[InvocationPrediction]:
    predictions: list[InvocationPrediction] = []
    seen_ids: set[str] = set()
    issues: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            issues.append(f"line {line_number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(payload, dict):
            issues.append(f"line {line_number}: prediction must be an object")
            continue
        if payload.get("schema") != PREDICTION_SCHEMA:
            issues.append(f"line {line_number}: schema must be `{PREDICTION_SCHEMA}`")
        case_id = str(payload.get("case_id") or "").strip()
        if case_id not in case_ids:
            issues.append(f"line {line_number}: unknown case id `{case_id}`")
        if case_id in seen_ids:
            issues.append(f"line {line_number}: duplicate prediction for `{case_id}`")
        seen_ids.add(case_id)
        selected = payload.get("selected_skills")
        if not isinstance(selected, list) or any(not isinstance(item, str) or not item.strip() for item in selected):
            issues.append(f"line {line_number}: `selected_skills` must be a list of non-empty strings")
            selected_tuple: tuple[str, ...] = ()
        else:
            selected_tuple = tuple(item.strip() for item in selected)
            if len(set(selected_tuple)) != len(selected_tuple):
                issues.append(f"line {line_number}: `selected_skills` contains duplicates")

        input_tokens = _optional_nonnegative_int(payload.get("input_tokens"), "input_tokens", line_number, issues)
        output_tokens = _optional_nonnegative_int(payload.get("output_tokens"), "output_tokens", line_number, issues)
        latency_ms = _optional_nonnegative_number(payload.get("latency_ms"), "latency_ms", line_number, issues)
        predictions.append(
            InvocationPrediction(
                case_id=case_id,
                selected_skills=selected_tuple,
                model=str(payload.get("model") or "").strip(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                note=str(payload.get("note") or "").strip(),
            )
        )

    if issues:
        raise ValueError("Invalid invocation predictions:\n- " + "\n- ".join(issues))
    return predictions


def build_invocation_evaluation(
    *,
    scope: str,
    cases: list[InvocationCase],
    predictions: Iterable[InvocationPrediction],
    catalog: dict[str, SkillProfile],
) -> dict[str, Any]:
    prediction_by_case = {prediction.case_id: prediction for prediction in predictions}
    catalog_description_chars = sum(skill.description_chars for skill in catalog.values())
    over_budget = sum(
        1 for skill in catalog.values() if skill.description_chars > DESCRIPTION_CONTEXT_LOAD_LIMIT
    )
    case_results: list[dict[str, Any]] = []

    for case in cases:
        prediction = prediction_by_case.get(case.id)
        selected = tuple(prediction.selected_skills) if prediction else ()
        repo_selected = tuple(skill for skill in selected if skill in catalog)
        external_selected = tuple(skill for skill in selected if skill not in catalog)
        observed_primary = repo_selected[0] if repo_selected else NO_REPO_SKILL
        expected_set = set(case.allowed_support)
        if case.expected_primary != NO_REPO_SKILL:
            expected_set.add(case.expected_primary)
        forbidden_hits = tuple(skill for skill in repo_selected if skill in set(case.forbidden))
        unexpected = tuple(skill for skill in repo_selected if skill not in expected_set)
        selected_body_chars = sum(catalog[skill].body_chars for skill in dict.fromkeys(repo_selected))
        case_results.append(
            {
                "case_id": case.id,
                "expected_primary": case.expected_primary,
                "observed_primary": observed_primary if prediction else "missing",
                "selected_skills": list(selected),
                "repo_selected_skills": list(repo_selected),
                "external_selected_skills": list(external_selected),
                "primary_correct": bool(prediction and observed_primary == case.expected_primary),
                "forbidden_hits": list(forbidden_hits),
                "unexpected_repo_skills": list(unexpected),
                "selected_body_chars": selected_body_chars,
                "skill_context_chars": catalog_description_chars + selected_body_chars,
                "model": prediction.model if prediction else "",
                "input_tokens": prediction.input_tokens if prediction else None,
                "output_tokens": prediction.output_tokens if prediction else None,
                "latency_ms": prediction.latency_ms if prediction else None,
                "note": prediction.note if prediction else "",
            }
        )

    predicted_results = [item for item in case_results if item["observed_primary"] != "missing"]
    total_cases = len(cases)
    predictions_received = len(predicted_results)
    primary_correct = sum(1 for item in case_results if item["primary_correct"])
    forbidden_cases = sum(1 for item in case_results if item["forbidden_hits"])
    unexpected_cases = sum(1 for item in case_results if item["unexpected_repo_skills"])
    measured_input_tokens = [item["input_tokens"] for item in predicted_results if item["input_tokens"] is not None]
    measured_output_tokens = [item["output_tokens"] for item in predicted_results if item["output_tokens"] is not None]
    measured_latency = [item["latency_ms"] for item in predicted_results if item["latency_ms"] is not None]

    if predictions_received == 0:
        verdict = "UNSCORED"
    elif predictions_received == total_cases and primary_correct == total_cases and forbidden_cases == 0 and unexpected_cases == 0:
        verdict = "PASS"
    else:
        verdict = "ATTENTION"

    return {
        "schema": EVALUATION_SCHEMA,
        "scope": scope,
        "verdict": verdict,
        "summary": {
            "corpus_cases": total_cases,
            "predictions_received": predictions_received,
            "coverage": _ratio(predictions_received, total_cases),
            "primary_correct": primary_correct,
            "primary_accuracy": _ratio(primary_correct, total_cases),
            "forbidden_selection_cases": forbidden_cases,
            "forbidden_selection_rate": _ratio(forbidden_cases, total_cases),
            "unexpected_selection_cases": unexpected_cases,
            "unexpected_selection_rate": _ratio(unexpected_cases, total_cases),
            "mean_repo_selected_skills": _mean([len(item["repo_selected_skills"]) for item in predicted_results]),
            "mean_selected_body_chars": _mean([item["selected_body_chars"] for item in predicted_results]),
            "mean_skill_context_chars": _mean([item["skill_context_chars"] for item in predicted_results]),
            "measured_input_token_cases": len(measured_input_tokens),
            "mean_input_tokens": _mean(measured_input_tokens),
            "measured_output_token_cases": len(measured_output_tokens),
            "mean_output_tokens": _mean(measured_output_tokens),
            "measured_latency_cases": len(measured_latency),
            "mean_latency_ms": _mean(measured_latency),
        },
        "catalog": {
            "repo_skills": len(catalog),
            "description_chars": catalog_description_chars,
            "over_budget_descriptions": over_budget,
            "description_context_load_limit": DESCRIPTION_CONTEXT_LOAD_LIMIT,
        },
        "cases": case_results,
        "measurement_note": (
            "Skill context characters include all repository descriptions plus bodies of selected repository Skills. "
            "Token and latency fields are reported only when supplied by the model runner; no character-to-token estimate is inferred."
        ),
    }


def render_invocation_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    catalog = payload["catalog"]
    lines = [
        "# Skill Invocation Evaluation",
        "",
        f"- Schema: `{payload['schema']}`",
        f"- Scope: `{payload.get('scope') or 'unspecified'}`",
        f"- Verdict: `{payload['verdict']}`",
        f"- Corpus cases: {summary['corpus_cases']}",
        f"- Predictions: {summary['predictions_received']} ({_percent(summary['coverage'])})",
        f"- Primary accuracy: {summary['primary_correct']}/{summary['corpus_cases']} ({_percent(summary['primary_accuracy'])})",
        f"- Forbidden-selection cases: {summary['forbidden_selection_cases']}",
        f"- Unexpected-selection cases: {summary['unexpected_selection_cases']}",
        "",
        "## Skill Context",
        "",
        f"- Repository Skills: {catalog['repo_skills']}",
        f"- Catalog description characters: {catalog['description_chars']}",
        f"- Descriptions over informational budget: {catalog['over_budget_descriptions']}",
        f"- Mean selected body characters: {_display_number(summary['mean_selected_body_chars'])}",
        f"- Mean Skill context characters: {_display_number(summary['mean_skill_context_chars'])}",
        f"- Measured input-token cases: {summary['measured_input_token_cases']}",
        f"- Measured output-token cases: {summary['measured_output_token_cases']}",
        f"- Measured latency cases: {summary['measured_latency_cases']}",
        "",
        payload["measurement_note"],
        "",
        "## Cases",
        "",
        "| Case | Expected | Observed | Correct | Forbidden | Unexpected | Skill context chars |",
        "|---|---|---|---:|---|---|---:|",
    ]
    for item in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table(item["case_id"]),
                    _escape_table(item["expected_primary"]),
                    _escape_table(item["observed_primary"]),
                    "yes" if item["primary_correct"] else "no",
                    _escape_table(", ".join(item["forbidden_hits"]) or "-"),
                    _escape_table(", ".join(item["unexpected_repo_skills"]) or "-"),
                    str(item["skill_context_chars"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_invocation_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_candidate_pack(
    *, scope: str, cases: Iterable[InvocationCase], catalog: dict[str, SkillProfile]
) -> dict[str, Any]:
    return {
        "schema": CANDIDATE_PACK_SCHEMA,
        "scope": scope,
        "instructions": [
            "Treat each case as an independent user request.",
            "Select the repository Skills that should be invoked, ordered with the primary Skill first.",
            "Return an empty selected_skills list when no repository Skill should be invoked.",
            "Do not execute the request and do not infer hidden expected answers.",
            "Return exactly one JSONL prediction record per case using the supplied output schema.",
        ],
        "repository_skills": [
            {"name": profile.name, "description": profile.description}
            for profile in sorted(catalog.values(), key=lambda item: item.name)
        ],
        "cases": [{"case_id": case.id, "prompt": case.prompt} for case in cases],
        "output_schema": {
            "schema": PREDICTION_SCHEMA,
            "case_id": "<case id>",
            "selected_skills": ["<ordered repository Skill names>"],
            "model": "<exact model label>",
            "input_tokens": "<optional observed non-negative integer>",
            "output_tokens": "<optional observed non-negative integer>",
            "latency_ms": "<optional observed non-negative number>",
            "note": "<optional short explanation>",
        },
    }


def render_candidate_pack(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_prediction_template(cases: Iterable[InvocationCase]) -> str:
    lines = []
    for case in cases:
        lines.append(
            json.dumps(
                {
                    "schema": PREDICTION_SCHEMA,
                    "case_id": case.id,
                    "selected_skills": [],
                    "model": "",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")


def validate_invocation_evaluation(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("schema") != EVALUATION_SCHEMA:
        issues.append(f"`schema` must be `{EVALUATION_SCHEMA}`.")
    if payload.get("verdict") not in {"UNSCORED", "PASS", "ATTENTION"}:
        issues.append("`verdict` must be `UNSCORED`, `PASS`, or `ATTENTION`.")
    if not isinstance(payload.get("summary"), dict):
        issues.append("`summary` must be an object.")
    if not isinstance(payload.get("catalog"), dict):
        issues.append("`catalog` must be an object.")
    if not isinstance(payload.get("cases"), list):
        issues.append("`cases` must be an array.")
    return issues


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML front matter.")
    end_idx = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end_idx is None:
        raise ValueError("SKILL.md has unterminated YAML front matter.")
    frontmatter = yaml.safe_load("\n".join(lines[1:end_idx])) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError("SKILL.md YAML front matter must be a mapping.")
    return frontmatter, "\n".join(lines[end_idx + 1 :])


def _string_tuple(value: Any, *, field: str, issues: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(f"{field} must be a list of non-empty strings")
        return ()
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        issues.append(f"{field} contains duplicates")
    return normalized


def _optional_nonnegative_int(value: Any, field: str, line: int, issues: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        issues.append(f"line {line}: `{field}` must be a non-negative integer")
        return None
    return value


def _optional_nonnegative_number(value: Any, field: str, line: int, issues: list[str]) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        issues.append(f"line {line}: `{field}` must be a non-negative number")
        return None
    return float(value)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: Iterable[int | float]) -> float | None:
    materialized = list(values)
    return round(float(fmean(materialized)), 3) if materialized else None


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _display_number(value: float | None) -> str:
    return "not measured" if value is None else f"{value:.1f}"


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
