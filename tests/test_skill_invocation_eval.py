from __future__ import annotations

import json
from pathlib import Path

import pytest

from tooling.skill_invocation_eval import (
    CANDIDATE_PACK_SCHEMA,
    EVALUATION_SCHEMA,
    NO_REPO_SKILL,
    PREDICTION_SCHEMA,
    build_candidate_pack,
    build_invocation_evaluation,
    load_invocation_corpus,
    load_invocation_predictions,
    load_skill_catalog,
    render_invocation_markdown,
    render_prediction_template,
    validate_invocation_evaluation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".codex" / "skills"
CORPUS_PATH = REPO_ROOT / "tests" / "fixtures" / "skill_invocation_cases.yaml"


def _catalog_and_cases():
    catalog = load_skill_catalog(SKILLS_DIR)
    scope, cases = load_invocation_corpus(CORPUS_PATH, catalog=catalog)
    return catalog, scope, cases


def _write_predictions(path: Path, cases, *, replacements: dict[str, list[str]] | None = None) -> None:
    replacements = replacements or {}
    records = []
    for index, case in enumerate(cases):
        if case.id in replacements:
            selected = replacements[case.id]
        elif case.expected_primary == NO_REPO_SKILL:
            selected = ["external-codebase-skill"]
        else:
            selected = [case.expected_primary]
        records.append(
            {
                "schema": PREDICTION_SCHEMA,
                "case_id": case.id,
                "selected_skills": selected,
                "model": "fixture-model",
                "input_tokens": 1000 + index,
                "output_tokens": 20 + index,
                "latency_ms": 50.0 + index,
            }
        )
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_invocation_corpus_covers_lifecycle_and_semantic_boundaries() -> None:
    catalog, scope, cases = _catalog_and_cases()

    assert scope == "research-harness-skills"
    assert len(catalog) == 107
    assert len(cases) == 48
    assert sum(case.split == "baseline" for case in cases) == 30
    assert sum(case.split == "challenge" for case in cases) == 18
    assert all(case.tags for case in cases)
    assert {case.expected_primary for case in cases} >= {
        "artifact-contract-auditor",
        "checkpoint-brief",
        "human-checkpoint",
        "pipeline-router",
        "research-pipeline-runner",
        "unit-executor",
        "workspace-init",
        "arxiv-search",
        "deliverable-selfloop",
        "idea-brief",
        "idea-memo-writer",
        "manuscript-ingest",
        "pipeline-auditor",
        "protocol-writer",
        "rubric-writer",
        "snapshot-writer",
        "source-manifest",
        "subsection-writer",
        "synthesis-writer",
        NO_REPO_SKILL,
    }


def test_perfect_predictions_pass_and_preserve_measured_context(tmp_path: Path) -> None:
    catalog, scope, cases = _catalog_and_cases()
    predictions_path = tmp_path / "predictions.jsonl"
    _write_predictions(predictions_path, cases)
    predictions = load_invocation_predictions(predictions_path, case_ids={case.id for case in cases})

    payload = build_invocation_evaluation(
        scope=scope,
        cases=cases,
        predictions=predictions,
        catalog=catalog,
    )

    assert payload["schema"] == EVALUATION_SCHEMA
    assert payload["verdict"] == "PASS"
    assert payload["summary"]["coverage"] == 1.0
    assert payload["summary"]["primary_accuracy"] == 1.0
    assert payload["summary"]["forbidden_selection_cases"] == 0
    assert payload["summary"]["measured_input_token_cases"] == len(cases)
    assert payload["summary"]["measured_output_token_cases"] == len(cases)
    assert payload["summary"]["measured_latency_cases"] == len(cases)
    assert payload["slices"]["splits"]["baseline"]["verdict"] == "PASS"
    assert payload["slices"]["splits"]["challenge"]["verdict"] == "PASS"
    assert payload["slices"]["tags"]["lexical-trap"]["primary_accuracy"] == 1.0
    assert 0 < payload["catalog"]["description_chars"] < 40000
    assert payload["catalog"]["over_budget_descriptions"] == 0
    assert validate_invocation_evaluation(payload) == []
    legacy_payload = dict(payload)
    legacy_payload.pop("slices")
    assert validate_invocation_evaluation(legacy_payload) == []
    assert "external-codebase-skill" in {
        skill for item in payload["cases"] for skill in item["external_selected_skills"]
    }


def test_forbidden_lifecycle_confusions_are_scored(tmp_path: Path) -> None:
    catalog, scope, cases = _catalog_and_cases()
    predictions_path = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions_path,
        cases,
        replacements={
            "initialize-only": ["research-pipeline-runner"],
            "deep-provenance-audit": ["artifact-contract-auditor"],
        },
    )
    predictions = load_invocation_predictions(predictions_path, case_ids={case.id for case in cases})

    payload = build_invocation_evaluation(
        scope=scope,
        cases=cases,
        predictions=predictions,
        catalog=catalog,
    )

    assert payload["verdict"] == "ATTENTION"
    assert payload["summary"]["primary_correct"] == len(cases) - 2
    assert payload["summary"]["forbidden_selection_cases"] == 2
    assert payload["summary"]["unexpected_selection_cases"] == 2
    markdown = render_invocation_markdown(payload)
    assert "initialize-only" in markdown
    assert "artifact-contract-auditor" in markdown


def test_slice_scores_isolate_challenge_failure(tmp_path: Path) -> None:
    catalog, scope, cases = _catalog_and_cases()
    predictions_path = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions_path,
        cases,
        replacements={"challenge-code-refactor-name-trap": ["pipeline-router"]},
    )
    predictions = load_invocation_predictions(predictions_path, case_ids={case.id for case in cases})

    payload = build_invocation_evaluation(
        scope=scope,
        cases=cases,
        predictions=predictions,
        catalog=catalog,
    )

    assert payload["verdict"] == "ATTENTION"
    assert payload["slices"]["splits"]["baseline"]["verdict"] == "PASS"
    assert payload["slices"]["splits"]["challenge"]["verdict"] == "ATTENTION"
    assert payload["slices"]["tags"]["lexical-trap"]["forbidden_selection_cases"] == 1
    assert "| split | challenge |" in render_invocation_markdown(payload)


def test_prediction_template_is_model_neutral_jsonl() -> None:
    _, _, cases = _catalog_and_cases()
    records = [json.loads(line) for line in render_prediction_template(cases).splitlines()]

    assert len(records) == len(cases)
    assert all(record["schema"] == PREDICTION_SCHEMA for record in records)
    assert all(record["selected_skills"] == [] for record in records)
    assert all(record["model"] == "" for record in records)


def test_candidate_pack_withholds_gold_labels() -> None:
    catalog, scope, cases = _catalog_and_cases()
    payload = build_candidate_pack(scope=scope, cases=cases, catalog=catalog)

    assert payload["schema"] == CANDIDATE_PACK_SCHEMA
    assert len(payload["repository_skills"]) == len(catalog)
    assert len(payload["cases"]) == len(cases)
    assert all(set(item) == {"case_id", "prompt"} for item in payload["cases"])
    serialized = json.dumps(payload)
    assert "expected_primary" not in serialized
    assert "allowed_support" not in serialized
    assert "forbidden" not in serialized
    assert '"split"' not in serialized
    assert '"tags"' not in serialized


def test_corpus_rejects_unknown_repository_skill(tmp_path: Path) -> None:
    catalog = load_skill_catalog(SKILLS_DIR)
    corpus_path = tmp_path / "bad.yaml"
    corpus_path.write_text(
        "schema: skill-invocation-cases.v1\n"
        "scope: bad\n"
        "cases:\n"
        "  - id: bad\n"
        "    prompt: test\n"
        "    expected_primary: missing-repo-skill\n"
        "    allowed_support: []\n"
        "    forbidden: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown expected Skill"):
        load_invocation_corpus(corpus_path, catalog=catalog)
