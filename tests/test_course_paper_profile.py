from __future__ import annotations

import subprocess
import sys
import tempfile
import importlib.util
import csv
import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from scripts.pipeline import _auto_pick_pipeline
from tooling.pipeline_spec import PipelineSpec
from tooling.common import (
    _query_seed_variants,
    _sanitize_topic_for_query_seed,
    _materialize_missing_query_defaults,
    bounded_complete_text,
    bounded_survey_profile_requested,
    goal_constraints_from_request,
    load_yaml,
    normalize_title_for_dedupe,
    reader_request_leakage,
    requested_evidence_mode,
    requested_delivery_formats,
    refinement_marker_is_current,
    research_subject_from_request,
    research_title_from_request,
    split_sentences,
    tokenize,
)
from tooling.quality_gate import (
    _check_argument_snapshot,
    _check_draft,
    _check_latex_compile_qa,
    _check_evidence_bindings,
    _check_mapping,
    _check_pdf_text_extractor,
    _check_taxonomy,
    _check_table_schema,
    _check_tables_appendix_md,
    _check_tables_index_md,
    _draft_profile,
    check_completion_acceptance,
    survey_citation_policy,
)
from tooling.quality_checks.template_residue import (
    FRONT_MATTER_CONTEXT_PATH,
    MEASUREMENT_SCHEMA,
    SCORECARD_SCHEMA,
    TEMPLATE_ASSETS_BY_SKILL,
    build_template_residue_scorecard,
    check_subsection_template_residue,
    measure_template_residue,
    selected_template_asset_evidence,
)
from tooling.quality_checks.survey_text import split_h3_blocks
from tooling.run_state import implementation_fingerprint
from tooling.scorecards import validate_scorecard


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_template_provenance(workspace: Path) -> None:
    front_asset = TEMPLATE_ASSETS_BY_SKILL["front-matter-writer"][0]
    front_relpath = str(front_asset.relative_to(REPO_ROOT))
    context_path = workspace / FRONT_MATTER_CONTEXT_PATH
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        json.dumps(
            {
                "template_assets": [front_relpath],
                "template_asset_sha256": {
                    front_relpath: hashlib.sha256(front_asset.read_bytes()).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    skills = {
        name: {
            "implementation_sha256": implementation_fingerprint(
                REPO_ROOT / ".codex" / "skills" / name
            )["sha256"]
        }
        for name in TEMPLATE_ASSETS_BY_SKILL
    }
    lock_path = workspace / ".harness" / "harness.lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"schema": "harness-lock.v2", "skills": skills}),
        encoding="utf-8",
    )


def _load_skill_script(skill_name: str):
    script = REPO_ROOT / ".codex" / "skills" / skill_name / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location(f"{skill_name.replace('-', '_')}_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_course_paper_pilot_records_measured_template_residue_lower_bound() -> None:
    draft_path = REPO_ROOT / "examples" / "course-paper-pilot" / "DRAFT.md"
    draft = draft_path.read_text(encoding="utf-8")

    summary = measure_template_residue(
        documents=[
            (
                "examples/course-paper-pilot/DRAFT.md",
                draft,
            )
        ]
    )

    assert summary["sentence_count"] == 140
    assert summary["schema"] == MEASUREMENT_SCHEMA
    assert summary["matched_sentence_count"] == 96
    assert summary["matched_sentence_ratio"] == 0.685714
    assert len(summary["template_assets"]) == 5
    assert len(summary["repair_items"]) == 96
    assert {
        "path",
        "heading",
        "sentence",
        "template_asset",
        "template_owner_skill",
        "literal_fragment",
    } <= summary["repair_items"][0].keys()

    h3_summary = measure_template_residue(
        documents=[
            (f"examples/course-paper-pilot/DRAFT.md#{title}", body)
            for title, body in split_h3_blocks(draft)
        ]
    )
    assert h3_summary["sentence_count"] == 90
    assert h3_summary["matched_sentence_count"] == 49
    assert h3_summary["matched_sentence_ratio"] == 0.544444

    front_matter_titles = {"Abstract", "Introduction", "Related Work", "Discussion", "Conclusion"}
    front_matter_blocks: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in draft.splitlines():
        if line.startswith("## "):
            if current_title in front_matter_titles:
                front_matter_blocks.append((current_title, "\n".join(current_lines)))
            current_title = line[3:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)
    if current_title in front_matter_titles:
        front_matter_blocks.append((current_title, "\n".join(current_lines)))
    front_matter_summary = measure_template_residue(documents=front_matter_blocks)
    assert front_matter_summary["sentence_count"] == 41
    assert front_matter_summary["matched_sentence_count"] == 41
    assert front_matter_summary["matched_sentence_ratio"] == 1.0


def test_template_residue_gate_rejects_unedited_bootstrap_prose(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    relpath = "sections/S3_1.md"
    section_path = tmp_path / relpath
    section_path.parent.mkdir(parents=True)
    section_path.write_text(
        "The literature on retrieval evaluation becomes hard to compare when papers keep the same label "
        "but change the conditions that give their gains meaning.\n\n"
        "This is the central pressure point: benchmarks preserve different assumptions.\n",
        encoding="utf-8",
    )

    issues = check_subsection_template_residue(workspace=tmp_path, relpaths=[relpath])

    assert [issue.code for issue in issues] == ["template_residue_above_threshold"]
    assert "2/2 sentences (100%)" in issues[0].message


def test_template_residue_gate_accepts_prose_without_literal_asset_fragments(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    relpath = "sections/S3_1.md"
    section_path = tmp_path / relpath
    section_path.parent.mkdir(parents=True)
    section_path.write_text(
        "Retrieval metrics answer different questions, so a useful comparison must name the user task "
        "and the evidence failure it is intended to expose.\n\n"
        "A rank-based score can improve while answer support remains incomplete, which makes the two "
        "signals complementary rather than interchangeable.\n",
        encoding="utf-8",
    )

    assert check_subsection_template_residue(workspace=tmp_path, relpaths=[relpath]) == []


def test_front_matter_writer_blocks_unedited_bootstrap_before_completion(
    tmp_path: Path,
) -> None:
    from tooling.quality_gate import check_unit_outputs

    _write_template_provenance(tmp_path)
    outputs = [
        "sections/abstract.md",
        "sections/S1.md",
        "sections/S2.md",
        "sections/discussion.md",
        "sections/conclusion.md",
        "output/FRONT_MATTER_REPORT.md",
        FRONT_MATTER_CONTEXT_PATH,
    ]
    for relpath in outputs[:5]:
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("A reader-facing sentence grounded in cited evidence.\n", encoding="utf-8")
    (tmp_path / "sections" / "abstract.md").write_text(
        "Recent research on agent evaluation now spans multiple methodological families, "
        "task settings, and evaluation regimes, yet those threads are still often compared "
        "under mismatched protocols.\n",
        encoding="utf-8",
    )
    report = tmp_path / "output" / "FRONT_MATTER_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Front matter report\n\n- Status: PASS\n", encoding="utf-8")

    issues = check_unit_outputs(
        skill="front-matter-writer",
        workspace=tmp_path,
        outputs=outputs,
    )

    assert "template_residue_above_threshold" in {issue.code for issue in issues}


def test_front_matter_writer_accepts_agent_authored_prose(tmp_path: Path) -> None:
    from tooling.quality_gate import check_unit_outputs

    _write_template_provenance(tmp_path)
    outputs = [
        "sections/abstract.md",
        "sections/S1.md",
        "sections/S2.md",
        "sections/discussion.md",
        "sections/conclusion.md",
        "output/FRONT_MATTER_REPORT.md",
        FRONT_MATTER_CONTEXT_PATH,
    ]
    for index, relpath in enumerate(outputs[:5], start=1):
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"Evaluation layer {index} links a named failure to a target-domain decision and "
            "reports the evidence boundary explicitly.\n",
            encoding="utf-8",
        )
    report = tmp_path / "output" / "FRONT_MATTER_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Front matter report\n\n- Status: PASS\n", encoding="utf-8")

    assert check_unit_outputs(
        skill="front-matter-writer",
        workspace=tmp_path,
        outputs=outputs,
    ) == []


def test_template_residue_gate_fails_closed_without_run_provenance(tmp_path: Path) -> None:
    relpath = "sections/S3_1.md"
    section_path = tmp_path / relpath
    section_path.parent.mkdir(parents=True)
    section_path.write_text("A clean reader-facing sentence.\n", encoding="utf-8")

    issues = check_subsection_template_residue(workspace=tmp_path, relpaths=[relpath])

    assert {issue.code for issue in issues} == {
        "template_residue_asset_selection_unverified",
        "template_residue_implementation_lock_mismatch",
    }


def test_template_residue_uses_the_run_selected_domain_overlay(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    overlay = TEMPLATE_ASSETS_BY_SKILL["front-matter-writer"][1]
    overlay_relpath = str(overlay.relative_to(REPO_ROOT))
    context_path = tmp_path / FRONT_MATTER_CONTEXT_PATH
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["template_assets"].append(overlay_relpath)
    context["template_asset_sha256"][overlay_relpath] = hashlib.sha256(
        overlay.read_bytes()
    ).hexdigest()
    context_path.write_text(json.dumps(context), encoding="utf-8")

    selection = selected_template_asset_evidence(tmp_path)

    assert selection["status"] == "PASS"
    assert len(selection["asset_paths"]) == 5
    assert overlay_relpath in selection["asset_paths"]


def test_template_residue_measurement_counts_cjk_sentences() -> None:
    summary = measure_template_residue(
        documents=[("draft.md", "这是第一句话。这里是第二句话！这是第三个问题？")]
    )

    assert summary["sentence_count"] == 3
    assert summary["matched_sentence_count"] == 0


def test_subsection_writer_marker_cannot_bypass_template_residue_gate(tmp_path: Path) -> None:
    from tooling.quality_gate import check_unit_outputs

    _write_template_provenance(tmp_path)
    outline = tmp_path / "outline" / "outline.yml"
    outline.parent.mkdir(parents=True)
    outline.write_text(
        "- id: 3\n"
        "  title: Retrieval evaluation\n"
        "  subsections:\n"
        "    - id: 3.1\n"
        "      title: Evidence coverage\n",
        encoding="utf-8",
    )
    section_paths = {
        "sections/abstract.md": "A bounded abstract.\n",
        "sections/discussion.md": "A bounded discussion.\n",
        "sections/conclusion.md": "A bounded conclusion.\n",
        "sections/S3_lead.md": "A chapter lead grounded in the reviewed structure.\n",
        "sections/S3_1.md": (
            "The literature on evidence coverage becomes hard to compare when papers keep the same label "
            "but change the conditions that give their gains meaning.\n"
        ),
    }
    for relpath, text in section_paths.items():
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    manifest = tmp_path / "sections" / "sections_manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps({"path": relpath}) for relpath in section_paths) + "\n",
        encoding="utf-8",
    )

    bootstrap_issues = check_unit_outputs(
        skill="subsection-writer",
        workspace=tmp_path,
        outputs=["sections/sections_manifest.jsonl"],
    )
    assert not any(issue.code == "template_residue_above_threshold" for issue in bootstrap_issues)

    (tmp_path / "sections" / "h3_bodies.refined.ok").touch()
    certified_issues = check_unit_outputs(
        skill="subsection-writer",
        workspace=tmp_path,
        outputs=["sections/sections_manifest.jsonl", "sections/h3_bodies.refined.ok"],
    )
    assert any(issue.code == "template_residue_above_threshold" for issue in certified_issues)


def test_pipeline_auditor_rechecks_template_residue_in_entire_merged_draft(tmp_path: Path) -> None:
    from tooling.quality_gate import check_unit_outputs

    _write_template_provenance(tmp_path)
    output = tmp_path / "output"
    output.mkdir(exist_ok=True)
    (output / "AUDIT_REPORT.md").write_text("# Audit\n\n- Status: PASS\n", encoding="utf-8")
    (output / "DRAFT.md").write_text(
        "# Draft\n\n"
        "## Abstract\n\n"
        "A central finding is that many reported gains depend as much on evaluation design and "
        "experimental assumptions as on the nominal methodology itself.\n",
        encoding="utf-8",
    )

    issues = check_unit_outputs(
        skill="pipeline-auditor",
        workspace=tmp_path,
        outputs=["output/AUDIT_REPORT.md"],
    )

    assert [issue.code for issue in issues] == ["template_residue_above_threshold"]


def test_template_residue_rejects_v2_template_skill_drift(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    relpath = "sections/S3_1.md"
    section_path = tmp_path / relpath
    section_path.parent.mkdir(parents=True)
    section_path.write_text(
        "Retrieval metrics answer different questions, so comparisons must identify the user task "
        "and the failure mode that each measure is intended to expose.\n",
        encoding="utf-8",
    )
    lock_path = tmp_path / ".harness" / "harness.lock.json"
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    skills = lock_payload["skills"]
    skills["front-matter-writer"]["implementation_sha256"] = "0" * 64
    lock_path.write_text(
        json.dumps({"schema": "harness-lock.v2", "skills": skills}),
        encoding="utf-8",
    )

    issues = check_subsection_template_residue(workspace=tmp_path, relpaths=[relpath])

    assert [issue.code for issue in issues] == [
        "template_residue_implementation_lock_mismatch"
    ]
    assert "front-matter-writer" in issues[0].message


def test_template_residue_scorecard_records_whole_draft_measurement(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    draft_path = REPO_ROOT / "examples" / "course-paper-pilot" / "DRAFT.md"
    scorecard = build_template_residue_scorecard(
        workspace=tmp_path,
        documents=[("output/DRAFT.md", draft_path.read_text(encoding="utf-8"))],
        scope="entire merged reader-facing draft",
    )

    assert validate_scorecard(scorecard, schema=SCORECARD_SCHEMA) == []
    assert scorecard["verdict"] == "FAIL"
    assert scorecard["measurement"]["matched_sentence_count"] == 96
    assert scorecard["measurement"]["sentence_count"] == 140
    assert scorecard["asset_selection"]["status"] == "PASS"
    assert scorecard["implementation_lock"]["status"] == "PASS"
    assert len(scorecard["measurement"]["template_assets"]) == 4
    assert scorecard["measurement"]["examples"][0]["section_owner_skill"] == (
        "front-matter-writer"
    )
    assert len(scorecard["measurement"]["repair_items"]) == 96
    assert any(
        "demonstrates attainability for that Run" in limitation
        for limitation in scorecard["limitations"]
    )


def test_pipeline_auditor_writes_template_residue_scorecard(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    draft = tmp_path / "output" / "DRAFT.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        "# Draft\n\n## Abstract\n\n"
        "A central finding is that many reported gains depend as much on evaluation design and "
        "experimental assumptions as on the nominal methodology itself.\n",
        encoding="utf-8",
    )
    script = REPO_ROOT / ".codex" / "skills" / "pipeline-auditor" / "scripts" / "run.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(tmp_path),
            "--outputs",
            "output/AUDIT_REPORT.md;output/TEMPLATE_RESIDUE_SCORECARD.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(
        (tmp_path / "output" / "TEMPLATE_RESIDUE_SCORECARD.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_scorecard(payload, schema=SCORECARD_SCHEMA) == []
    assert payload["measurement"]["matched_sentence_count"] == 1
    assert len(payload["measurement"]["repair_items"]) == 1
    assert payload["measurement"]["repair_items"][0]["heading"] == "Abstract"
    assert payload["scope"] == "entire merged reader-facing draft"


def test_pipeline_auditor_blocks_pipeline_voice_for_course_papers(tmp_path: Path) -> None:
    _write_template_provenance(tmp_path)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "DRAFT.md").write_text(
        "# Draft\n\n## Abstract\n\n"
        "Because the evidence available in this run is abstract-level, the analysis keeps "
        "its conclusions bounded.\n",
        encoding="utf-8",
    )
    citations = tmp_path / "citations"
    citations.mkdir(parents=True, exist_ok=True)
    (citations / "ref.bib").write_text(
        "@article{Example2026, title={Example}, author={Example, Ada}, year={2026}}\n",
        encoding="utf-8",
    )
    script = REPO_ROOT / ".codex" / "skills" / "pipeline-auditor" / "scripts" / "run.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(tmp_path),
            "--outputs",
            "output/AUDIT_REPORT.md;output/TEMPLATE_RESIDUE_SCORECARD.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    report = (output / "AUDIT_REPORT.md").read_text(encoding="utf-8")
    assert result.returncode == 2
    blocking_section = report.split("## Blocking issues", 1)[1].split("## Warnings", 1)[0]
    assert "pipeline voice ('this run')" in blocking_section


def test_pipeline_auditor_allows_domain_pipeline_language_in_course_papers(
    tmp_path: Path,
) -> None:
    _write_template_provenance(tmp_path)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "DRAFT.md").write_text(
        "# Draft\n\n## Abstract\n\n"
        "This pipeline carries retrieved passages through a reranking stage. "
        "A manufacturing quality gate rejects damaged samples before assembly.\n",
        encoding="utf-8",
    )
    script = REPO_ROOT / ".codex" / "skills" / "pipeline-auditor" / "scripts" / "run.py"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(tmp_path),
            "--outputs",
            "output/AUDIT_REPORT.md;output/TEMPLATE_RESIDUE_SCORECARD.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    report = (output / "AUDIT_REPORT.md").read_text(encoding="utf-8")
    blocking_section = report.split("## Blocking issues", 1)[1].split("## Warnings", 1)[0]
    assert "pipeline voice" not in blocking_section


def test_pipeline_auditor_blocks_ambiguous_pipeline_terms_with_harness_context(
    tmp_path: Path,
) -> None:
    _write_template_provenance(tmp_path)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "DRAFT.md").write_text(
        "# Draft\n\n## Abstract\n\n"
        "This pipeline completed checkpoint C2 before writer Unit U060 ran.\n",
        encoding="utf-8",
    )
    script = REPO_ROOT / ".codex" / "skills" / "pipeline-auditor" / "scripts" / "run.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(tmp_path),
            "--outputs",
            "output/AUDIT_REPORT.md;output/TEMPLATE_RESIDUE_SCORECARD.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    report = (output / "AUDIT_REPORT.md").read_text(encoding="utf-8")
    blocking_section = report.split("## Blocking issues", 1)[1].split("## Warnings", 1)[0]
    assert result.returncode == 2
    assert "pipeline voice (Harness context)" in blocking_section


def test_front_matter_voice_lint_allows_domain_terms_but_blocks_harness_leaks() -> None:
    module = _load_skill_script("front-matter-writer")
    contract = json.loads(
        (
            REPO_ROOT
            / ".codex"
            / "skills"
            / "front-matter-writer"
            / "assets"
            / "front_matter_contract.json"
        ).read_text(encoding="utf-8")
    )

    module._lint_reader_facing(
        label="abstract",
        text=(
            "This pipeline carries retrieved passages through a reranking stage, and a "
            "manufacturing quality gate rejects damaged samples."
        ),
        contract=contract,
    )

    with pytest.raises(SystemExit, match="run-local narration"):
        module._lint_reader_facing(
            label="abstract",
            text="This run retains enough evidence for the final paper.",
            contract=contract,
        )
    with pytest.raises(SystemExit, match="pipeline narration"):
        module._lint_reader_facing(
            label="abstract",
            text="This pipeline completed checkpoint C2 before Unit U060 ran.",
            contract=contract,
        )


def test_writer_selfloop_invokes_shared_strict_sections_checker() -> None:
    source = (
        REPO_ROOT / ".codex" / "skills" / "writer-selfloop" / "scripts" / "run.py"
    ).read_text(encoding="utf-8")

    assert "from tooling.quality_gate import QualityIssue, _check_sections_manifest" in source
    assert "section_issues = _check_sections_manifest(workspace, [manifest_rel])" in source


def test_delivery_request_normalizes_to_reader_facing_subject_and_title() -> None:
    request = (
        "Write an 8-10 page course paper on how retrieval-augmented generation systems "
        "should be evaluated, with a final PDF."
    )

    assert research_subject_from_request(request) == (
        "the evaluation of retrieval-augmented generation systems"
    )
    assert research_title_from_request(request) == (
        "Evaluating Retrieval-Augmented Generation Systems"
    )
    assert reader_request_leakage(request) == [
        "imperative paper request",
        "delivery-format request",
    ]
    assert reader_request_leakage(research_title_from_request(request)) == []
    assert goal_constraints_from_request(request) == {
        "page_range": {"min": 8, "max": 10, "scope": "compiled_pdf_total"},
        "deliverable_formats": ["pdf"],
    }


def test_bounded_report_requests_share_the_compact_survey_profile() -> None:
    requests = {
        "Write a seminar report on robot foundation models, target 6-8 pages, with PDF output.": "robot foundation models",
        "Prepare a technical survey report about test-time adaptation as a Markdown deliverable.": "test-time adaptation",
        "写一篇关于检索增强生成评测的课程报告，8-10 页，并生成 PDF": "检索增强生成评测",
        "准备一份关于具身智能的研讨课报告，6 到 8 页": "具身智能",
        "生成关于多智能体评测的专题调研报告": "多智能体评测",
        "Write a topic report on evaluation leakage across language-model benchmarks.": "evaluation leakage across language-model benchmarks.",
        "准备一份关于机器人基础模型的短文献综述": "机器人基础模型",
    }

    for request, subject in requests.items():
        assert bounded_survey_profile_requested(request)
        assert _sanitize_topic_for_query_seed(request) == subject

    assert not bounded_survey_profile_requested("Write a laboratory experiment report")
    assert not bounded_survey_profile_requested("Review this single manuscript")
    assert not bounded_survey_profile_requested("Analyze research landscape report generation models")
    assert not bounded_survey_profile_requested("Write a technical survey report on semiconductor memory market pricing")
    assert _sanitize_topic_for_query_seed("生成模型评估") == "生成模型评估"
    assert _sanitize_topic_for_query_seed("Analyze methods for research landscape report") == (
        "Analyze methods for research landscape report"
    )


def test_survey_literature_completion_check_does_not_crash(tmp_path: Path) -> None:
    for workflow in ("arxiv-survey", "arxiv-survey-latex"):
        workspace = tmp_path / workflow
        (workspace / "papers").mkdir(parents=True, exist_ok=True)
        (workspace / "PIPELINE.lock.md").write_text(
            f"pipeline: pipelines/{workflow}.pipeline.md\n",
            encoding="utf-8",
        )
        (workspace / "papers" / "papers_raw.jsonl").write_text(
            json.dumps(
                {
                    "title": "Grounded survey source",
                    "authors": ["Researcher"],
                    "year": 2026,
                    "url": "https://arxiv.org/abs/2601.00001",
                    "arxiv_id": "2601.00001",
                    "abstract": "A grounded abstract for the retrieval quality check.",
                    "provenance": [{"route": "fixture"}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "papers" / "retrieval_report.md").write_text(
            "# Retrieval report\n\n- Fixture route: 1\n",
            encoding="utf-8",
        )

        issues = check_completion_acceptance(
            skill="literature-engineer",
            workspace=workspace,
            outputs=["papers/papers_raw.jsonl", "papers/retrieval_report.md"],
        )

        assert "completion_check_exception" not in {issue.code for issue in issues}


def test_evidence_selfloop_is_a_mandatory_prewrite_gate(tmp_path: Path) -> None:
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "arxiv-survey.pipeline.md")
    assert "evidence-selfloop" in spec.quality_contract["completion_policy"]["required_checks"]
    assert "front-matter-writer" in spec.quality_contract["completion_policy"]["required_checks"]
    assert spec.quality_contract["writing_policy"] == {
        "template_residue_max_ratio": 0.10,
        "template_literal_min_chars": 24,
    }

    workspace = tmp_path / "survey"
    outline = workspace / "outline"
    output = workspace / "output"
    outline.mkdir(parents=True)
    output.mkdir(parents=True)
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (outline / "subsection_briefs.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "title": "Grounded section"}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_bindings.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "binding_gaps": []}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_drafts.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "blocking_missing": ["no usable citation keys"]}) + "\n",
        encoding="utf-8",
    )
    (output / "EVIDENCE_SELFLOOP_TODO.md").write_text(
        "# Evidence self-loop TODO\n\n- Status: FAIL\n",
        encoding="utf-8",
    )

    issues = check_completion_acceptance(
        skill="evidence-selfloop",
        workspace=workspace,
        outputs=["output/EVIDENCE_SELFLOOP_TODO.md"],
    )

    assert [issue.code for issue in issues] == ["evidence_selfloop_blocked"]


def test_evidence_selfloop_rejects_stale_status_after_binding_change(tmp_path: Path) -> None:
    workspace = tmp_path / "survey"
    outline = workspace / "outline"
    output = workspace / "output"
    outline.mkdir(parents=True)
    output.mkdir(parents=True)
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (outline / "subsection_briefs.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "title": "Grounded section"}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_bindings.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "binding_gaps": ["evaluation protocol"]}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_drafts.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "blocking_missing": []}) + "\n",
        encoding="utf-8",
    )
    (output / "EVIDENCE_SELFLOOP_TODO.md").write_text(
        "# Evidence self-loop TODO\n\n- Status: PASS\n",
        encoding="utf-8",
    )

    issues = check_completion_acceptance(
        skill="evidence-selfloop",
        workspace=workspace,
        outputs=["output/EVIDENCE_SELFLOOP_TODO.md"],
    )

    assert [issue.code for issue in issues] == ["evidence_selfloop_status_stale"]


def test_evidence_selfloop_requires_located_repair_plan_for_ok_status(tmp_path: Path) -> None:
    from tooling.quality_checks.survey_planning import check_evidence_selfloop

    workspace = tmp_path / "survey"
    outline = workspace / "outline"
    output = workspace / "output"
    outline.mkdir(parents=True)
    output.mkdir(parents=True)
    (outline / "subsection_briefs.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "title": "Grounded section"}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_bindings.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "binding_gaps": ["evaluation protocol"]}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_drafts.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "blocking_missing": []}) + "\n",
        encoding="utf-8",
    )
    report = output / "EVIDENCE_SELFLOOP_TODO.md"
    report.write_text("# Evidence self-loop TODO\n\n- Status: OK\n", encoding="utf-8")

    issues = check_evidence_selfloop(workspace, ["output/EVIDENCE_SELFLOOP_TODO.md"])

    assert [issue.code for issue in issues] == ["evidence_selfloop_repair_plan_missing"]

    report.write_text(
        "\n".join(
            [
                "# Evidence self-loop TODO",
                "",
                "- Status: OK",
                "",
                "## C. Per-subsection TODO (smallest upstream fix path)",
                "",
                "### 3.1 Grounded section",
                "",
                "- binding_gaps:",
                "  - evaluation protocol",
                "- Suggested fix path:",
                "  - C4: enrich the evidence bank, then rerun `evidence-binder`.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert check_evidence_selfloop(workspace, ["output/EVIDENCE_SELFLOOP_TODO.md"]) == []


def test_evidence_selfloop_rejects_subsection_coverage_drift(tmp_path: Path) -> None:
    workspace = tmp_path / "survey"
    outline = workspace / "outline"
    output = workspace / "output"
    outline.mkdir(parents=True)
    output.mkdir(parents=True)
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (outline / "subsection_briefs.jsonl").write_text(
        "\n".join(
            json.dumps({"sub_id": sub_id, "title": f"Section {sub_id}"})
            for sub_id in ("3.1", "3.2")
        )
        + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_bindings.jsonl").write_text(
        "\n".join(
            json.dumps({"sub_id": sub_id, "binding_gaps": []})
            for sub_id in ("3.1", "3.2")
        )
        + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_drafts.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "blocking_missing": []}) + "\n",
        encoding="utf-8",
    )
    (output / "EVIDENCE_SELFLOOP_TODO.md").write_text(
        "# Evidence self-loop TODO\n\n- Status: PASS\n",
        encoding="utf-8",
    )

    issues = check_completion_acceptance(
        skill="evidence-selfloop",
        workspace=workspace,
        outputs=["output/EVIDENCE_SELFLOOP_TODO.md"],
    )

    assert [issue.code for issue in issues] == ["evidence_selfloop_coverage_mismatch"]


def test_evidence_selfloop_rejects_non_list_gap_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "survey"
    outline = workspace / "outline"
    output = workspace / "output"
    outline.mkdir(parents=True)
    output.mkdir(parents=True)
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (outline / "subsection_briefs.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "title": "Grounded section"}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_bindings.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "binding_gaps": "none"}) + "\n",
        encoding="utf-8",
    )
    (outline / "evidence_drafts.jsonl").write_text(
        json.dumps({"sub_id": "3.1", "blocking_missing": []}) + "\n",
        encoding="utf-8",
    )
    (output / "EVIDENCE_SELFLOOP_TODO.md").write_text(
        "# Evidence self-loop TODO\n\n- Status: PASS\n",
        encoding="utf-8",
    )

    issues = check_completion_acceptance(
        skill="evidence-selfloop",
        workspace=workspace,
        outputs=["output/EVIDENCE_SELFLOOP_TODO.md"],
    )

    assert [issue.code for issue in issues] == ["evidence_selfloop_inputs_invalid"]


def test_workflow_instruction_is_removed_before_query_seeding() -> None:
    request = (
        "Use arxiv-survey-latex to write an 8-10 page course report on RAG evaluation "
        "and produce a final PDF."
    )

    assert bounded_survey_profile_requested(request)
    assert _sanitize_topic_for_query_seed(request) == "RAG evaluation"
    chinese_request = (
        "使用 arxiv-survey-latex 写一篇 8-10 页的检索增强生成评测课程报告，并生成 PDF"
    )
    assert bounded_survey_profile_requested(chinese_request)
    assert _sanitize_topic_for_query_seed(chinese_request) == "检索增强生成评测"


def test_research_brief_goal_seeds_the_research_subject_not_delivery_language() -> None:
    request = (
        "Produce a compact, traceable research brief on reliable adaptation of "
        "embodied agents under distribution shift, with a bounded reading path "
        "and explicit open risks."
    )

    assert _sanitize_topic_for_query_seed(request) == (
        "reliable adaptation of embodied agents under distribution shift"
    )

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        queries = _kickoff(
            workspace=Path(tmp),
            topic=request,
            pipeline="research-brief",
        )

    assert '  - "reliable adaptation of embodied agents under distribution shift"' in queries
    assert "(all:robot OR all:robotic OR all:embodied) AND" in queries
    assert '  - "robot policy adaptation"' in queries
    assert '  - "robot learning distribution shift"' in queries
    assert "bounded reading path" not in queries
    assert '  - "LLM agent"' not in queries
    assert '  - "embodied AI survey"' not in queries


def test_delivery_format_detection_requires_delivery_context() -> None:
    assert requested_delivery_formats("Analyze PDF output fidelity in multimodal models") == []
    assert requested_delivery_formats("Analyze LaTeX parsing failures in research corpora") == []
    assert _sanitize_topic_for_query_seed("Analyze PDF output fidelity in multimodal models") == (
        "Analyze PDF output fidelity in multimodal models"
    )
    assert requested_delivery_formats("Write a course report on RAG and produce a final PDF") == ["pdf"]
    assert requested_delivery_formats("写一篇 RAG 课程报告，并生成 PDF") == ["pdf"]
    assert goal_constraints_from_request("Analyze PDF output fidelity in multimodal models") == {}


def test_fulltext_evidence_request_is_a_goal_constraint_and_query_control() -> None:
    request = "Write a course paper on RAG evaluation using full-text evidence."

    assert requested_evidence_mode(request) == "fulltext"
    assert requested_evidence_mode("研究 full-text search 的索引方法") == ""
    assert goal_constraints_from_request(request)["evidence_mode"] == "fulltext"

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        queries = _kickoff(
            workspace=Path(tmp),
            topic=request,
            pipeline="arxiv-survey",
        )
    assert '- evidence_mode: "fulltext"' in queries


def test_auto_router_selects_research_intent_before_delivery_variant() -> None:
    payload = load_yaml(REPO_ROOT / "tests" / "fixtures" / "workflow_routing_cases.yaml")
    assert payload["schema"] == "workflow-routing-cases/v1"
    cases = payload["cases"]
    assert len({case["id"] for case in cases}) == len(cases)

    observed_workflows = set()
    for case in cases:
        expected = case["expected_workflow"]
        observed_workflows.add(expected)
        assert _auto_pick_pipeline(case["prompt"]) == expected, case["id"]

    assert observed_workflows == {
        "arxiv-survey",
        "arxiv-survey-latex",
        "evidence-review",
        "idea-brainstorm",
        "paper-review",
        "research-brief",
        "source-tutorial",
    }


def test_latex_gate_enforces_goal_page_range_not_only_a_minimum(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "latex").mkdir(parents=True)
        (workspace / "output").mkdir(parents=True)
        (workspace / "GOAL.md").write_text(
            "# Goal\n\nWrite an 8-10 page course paper on RAG evaluation, with a final PDF.\n",
            encoding="utf-8",
        )
        (workspace / "latex" / "main.pdf").write_bytes(b"%PDF-1.4\n")
        (workspace / "latex" / "main.log").write_text("", encoding="utf-8")
        (workspace / "output" / "LATEX_BUILD_REPORT.md").write_text(
            "# LaTeX build report\n\n- Status: SUCCESS\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "tooling.quality_gate.shutil.which",
            lambda name: "/usr/bin/pdfinfo" if name == "pdfinfo" else None,
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="Pages:          13\n",
                stderr="",
            ),
        )

        issues = _check_latex_compile_qa(
            workspace,
            ["latex/main.pdf", "output/LATEX_BUILD_REPORT.md"],
        )
        assert "pdf_too_long" in {issue.code for issue in issues}


def test_front_matter_deduplicates_projected_chapter_themes() -> None:
    module = _load_skill_script("front-matter-writer")

    assert module._series_text(
        [
            "measurement validity and evaluator design",
            "measurement validity and evaluator design",
            "robustness, transfer, and deployment",
        ]
    ) == "measurement validity and evaluator design and robustness, transfer, and deployment"


def test_course_paper_paragraph_curation_preserves_five_paragraph_floor() -> None:
    module = _load_skill_script("paragraph-curator")
    paragraphs = [
        f"Paragraph {index} makes one concise evidence-backed move [@Key{index}]."
        for index in range(1, 7)
    ]

    curated = module._curate(
        "\n\n".join(paragraphs),
        max_paragraphs=7,
        min_paragraphs=5,
        tail_keep=2,
        min_chars=1600,
    )
    assert len([p for p in curated.split("\n\n") if p.strip()]) == 5

    already_at_floor = module._curate(
        "\n\n".join(paragraphs[:5]),
        max_paragraphs=7,
        min_paragraphs=5,
        tail_keep=2,
        min_chars=1600,
    )
    assert len([p for p in already_at_floor.split("\n\n") if p.strip()]) == 5


def test_global_review_blocks_delivery_request_leakage_and_uses_course_profile_targets() -> None:
    module = _load_skill_script("global-reviewer")
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "output").mkdir(parents=True)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "citations").mkdir(parents=True)
        (workspace / "queries.md").write_text(
            '# Queries\n\n- draft_profile: "course_paper"\n- evidence_mode: "abstract"\n',
            encoding="utf-8",
        )
        (workspace / "outline" / "tables_appendix.md").write_text(
            "| A | B |\n|---|---|\n| x | y |\n",
            encoding="utf-8",
        )
        (workspace / "output" / "DRAFT.md").write_text(
            "# Write an 8-10 page course paper on RAG evaluation, with a final PDF.\n\n"
            "## Introduction\n\nBackground.\n\n"
            "## Discussion\n\nDiscussion.\n\n"
            "## Conclusion\n\nConclusion.\n",
            encoding="utf-8",
        )

        report = module._global_review_report(workspace=workspace)
        assert "- Status: FAIL" in report
        assert "Delivery-request leakage: imperative paper request, delivery-format request" in report
        assert "course-paper target: >=1 comparison table" in report
        assert "Timeline: year-like milestone bullets = 0 (optional for this profile)" in report
        assert "aim for 5-7 paragraphs per H3" in report

        issues = _check_draft(workspace, ["output/DRAFT.md"])
        assert "draft_delivery_request_leakage" in {issue.code for issue in issues}


def test_course_paper_delivery_constraints_are_removed_from_query_seed() -> None:
    assert _sanitize_topic_for_query_seed(
        "Write an 8-10 page course paper on how retrieval-augmented generation systems should be evaluated, with a final PDF."
    ) == "how retrieval-augmented generation systems should be evaluated"
    assert _sanitize_topic_for_query_seed(
        "写一篇 8-10 页关于检索增强生成评测的课程论文，最后输出PDF"
    ) == "检索增强生成评测"
    assert _query_seed_variants(
        "how retrieval-augmented generation systems should be evaluated"
    ) == [
        "how retrieval-augmented generation systems should be evaluated",
        "retrieval-augmented generation",
        "retrieval-augmented generation evaluation",
    ]


def test_evidence_text_bounds_preserve_complete_sentences_or_drop_fragments() -> None:
    sentence = (
        "AttributionBench compares generated-answer attribution across four human-labeled datasets, "
        + "including protocol-specific calibration evidence " * 8
        + "and the metric rankings invert across evaluation settings."
    )

    assert len(sentence) > 280
    assert bounded_complete_text(sentence, max_chars=280, overflow_factor=3.0) == sentence
    assert bounded_complete_text(sentence[:-1] + " and", max_chars=280, overflow_factor=1.1) == ""

    sentence_with_vs = (
        "In the construct with the most multi-dataset human-labeled coverage, the metric rankings "
        "invert on AttributedQA vs. LFQA, while a second evaluator remains stable across both settings."
    )
    assert bounded_complete_text(
        sentence_with_vs,
        max_chars=100,
        overflow_factor=3.0,
    ) == sentence_with_vs
    assert split_sentences(sentence_with_vs) == [sentence_with_vs]


def test_section_logic_recognizes_content_theses_without_stock_labels() -> None:
    module = _load_skill_script("section-logic-polisher")

    assert module._has_thesis(
        "Retrieval evaluation should separate rank quality, evidence coverage, and downstream "
        "answer utility because each answers a different question [@Salemi2024Evaluating]."
    )
    assert module._has_thesis(
        "Automated evaluators are useful only to the extent that their scores remain calibrated "
        "against human judgments and the constructs they are intended to measure [@SaadFalcon2023Ares]."
    )
    assert module._has_thesis(
        "The useful lens is not a single architecture name, but the coupled choices that give "
        "the comparison its meaning."
    )


def test_section_logic_rejects_background_sentences_as_theses() -> None:
    module = _load_skill_script("section-logic-polisher")

    assert not module._has_thesis(
        "The literature on retrieval quality includes several recent studies and benchmark papers."
    )
    assert not module._has_thesis(
        "Tool interfaces vary across agent systems, and many recent works explore different designs."
    )


def test_taxonomy_domain_pack_requires_explicit_intent() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "taxonomy-builder" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("taxonomy_builder_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "GOAL.md").write_text(
            "# Goal\n\nEvaluate retrieval-augmented generation systems.\n",
            encoding="utf-8",
        )
        (workspace / "queries.md").write_text(
            "# Queries\n\n- keywords:\n  - \"retrieval-augmented generation evaluation\"\n",
            encoding="utf-8",
        )
        noisy_corpus = "embodied robot manipulation policy control foundation model world model"
        assert module._detect_profile(workspace=workspace, text_blob=noisy_corpus) == "rag_evaluation"

        taxonomy = module._load_domain_pack_taxonomy(
            profile="rag_evaluation",
            core_rows=[
                {
                    "paper_id": "P001",
                    "title": "Automated Evaluation of Retrieval-Augmented Generation",
                }
            ],
        )
        assert [node["name"] for node in taxonomy] == [
            "Evaluation Targets & Failure Decomposition",
            "Evaluation Protocols & Measurement Validity",
            "Robustness, Transfer & Operational Validity",
        ]
        assert taxonomy[1]["children"][1]["name"] == "Automated evaluators and human validation"

        (workspace / "GOAL.md").write_text(
            "# Goal\n\nSurvey tool-using LLM agents and their evaluation.\n",
            encoding="utf-8",
        )
        assert module._detect_profile(workspace=workspace, text_blob="") == "llm_agents"


def test_taxonomy_gate_catches_unrelated_domain_pack() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "papers").mkdir(parents=True)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "papers" / "core_set.csv").write_text(
            "paper_id,title\n"
            "P001,Retrieval-Augmented Generation Evaluation Benchmarks\n"
            "P002,Robust Retrieval-Augmented Generation\n"
            "P003,Evaluating Retrieval and Generation Quality\n",
            encoding="utf-8",
        )
        (workspace / "outline" / "taxonomy.yml").write_text(
            "- name: Robot Control\n"
            "  description: Control policies and embodied manipulation interfaces for physical robots.\n"
            "  children:\n"
            "    - name: Navigation Policies\n"
            "      description: Navigation and action-space constraints in deployed robotic systems.\n",
            encoding="utf-8",
        )

        issues = _check_taxonomy(workspace, ["outline/taxonomy.yml"])
        assert "taxonomy_domain_drift" in {issue.code for issue in issues}


def _kickoff(*, workspace: Path, topic: str, pipeline: str = "arxiv-survey-latex") -> str:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/pipeline.py",
            "kickoff",
            "--topic",
            topic,
            "--pipeline",
            pipeline,
            "--workspace",
            str(workspace),
            "--overwrite",
            "--overwrite-units",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return (workspace / "queries.md").read_text(encoding="utf-8")


def test_course_paper_intent_materializes_compact_profile_without_new_workflow() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        queries = _kickoff(
            workspace=workspace,
            topic="Write a compact course paper on retrieval-augmented generation",
        )

        assert '- max_results: "320"' in queries
        assert '- core_size: "48"' in queries
        assert '- per_subsection: "6"' in queries
        assert '- global_citation_min_subsections: "3"' in queries
        assert '- draft_profile: "course_paper"' in queries
        assert '- citation_target: "hard"' in queries
        assert '  - "retrieval-augmented generation"' in queries
        assert '  - "retrieval-augmented generation"' in queries
        assert "course paper on retrieval-augmented generation" not in queries.lower()
        assert "pipelines/arxiv-survey-latex.pipeline.md" in (workspace / "PIPELINE.lock.md").read_text(encoding="utf-8")
        assert not (REPO_ROOT / "pipelines" / "course-paper.pipeline.md").exists()


def test_course_report_pdf_auto_routes_and_materializes_compact_profile() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        request = "写一篇关于检索增强生成评测的课程报告，8-10 页，并生成 PDF"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/pipeline.py",
                "kickoff",
                "--topic",
                request,
                "--workspace",
                str(workspace),
                "--overwrite",
                "--overwrite-units",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        lock = (workspace / "PIPELINE.lock.md").read_text(encoding="utf-8")
        queries = (workspace / "queries.md").read_text(encoding="utf-8")
        assert "pipelines/arxiv-survey-latex.pipeline.md" in lock
        assert '- draft_profile: "course_paper"' in queries
        assert '- max_results: "320"' in queries
        assert '  - "检索增强生成评测"' in queries
        assert "课程报告" not in queries
        assert "8-10" not in queries


def test_external_workspace_keeps_variant_defaults_and_bounded_profile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        queries = _kickoff(
            workspace=Path(tmp),
            topic="Write a seminar report on agent evaluation, target 6-8 pages, with PDF output.",
        )

        assert '- draft_profile: "course_paper"' in queries
        assert '- core_size: "48"' in queries
        assert '  - "agent evaluation"' in queries


def test_external_workspace_below_foreign_repo_marker_uses_executing_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        foreign_root = Path(tmp)
        (foreign_root / "AGENTS.md").write_text("# unrelated checkout\n", encoding="utf-8")
        workspace = foreign_root / "runs" / "w1"
        queries = _kickoff(
            workspace=workspace,
            topic="Write a seminar report on agent evaluation, target 6-8 pages, with PDF output.",
        )

        assert '- draft_profile: "course_paper"' in queries
        assert '- core_size: "48"' in queries
        assert '  - "agent evaluation"' in queries


def test_non_retrieval_workflow_does_not_materialize_unused_query_controls() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        queries = _kickoff(
            workspace=Path(tmp),
            topic="Review this manuscript and trace every major concern",
            pipeline="paper-review",
        )

        assert "Review this manuscript" not in queries
        assert '- max_results: ""' in queries
        assert '- draft_profile: ""' in queries


def test_retrieval_workflow_materializes_only_declared_query_controls() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        queries = _kickoff(
            workspace=Path(tmp),
            topic="Systematic review of tutoring agents",
            pipeline="evidence-review",
        )

        assert '  - "Systematic review of tutoring agents"' in queries
        assert '- max_results: ""' in queries
        assert '- evidence_mode: ""' in queries
        assert "rigor:" not in queries


def test_empty_query_allowlist_materializes_no_defaults() -> None:
    lines = ["# Queries", "", "## Notes"]
    assert _materialize_missing_query_defaults(
        lines,
        {"draft_profile": "survey"},
        allowed_fields=set(),
    ) == lines


def test_default_survey_profile_is_not_downgraded() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        queries = _kickoff(
            workspace=workspace,
            topic="A literature survey of retrieval-augmented generation",
            pipeline="arxiv-survey",
        )

        assert '- max_results: "1800"' in queries
        assert '- core_size: "300"' in queries
        assert '- per_subsection: "28"' in queries
        assert '- global_citation_min_subsections: "4"' in queries
        assert '- draft_profile: "survey"' in queries
        assert '- citation_target: "recommended"' in queries


def test_course_paper_policy_is_coherent_across_contract_and_quality_gate() -> None:
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "arxiv-survey.pipeline.md")
    policy = spec.quality_contract
    course_citations = policy["citation_policy"]["by_profile"]["course_paper"]
    assert course_citations["global_budget_per_h3"] == 3
    assert "per_h3" not in course_citations
    assert policy["structure_policy"]["max_h3_by_profile"]["course_paper"] == 6
    assert policy["subsection_policy"]["course_paper"] == {
        "min_unique_citations": 4,
        "min_chars": 1600,
    }

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        _kickoff(workspace=workspace, topic="写一篇关于检索增强生成的课程论文", pipeline="arxiv-survey")
        assert _draft_profile(workspace) == "course_paper"
        citation_policy = survey_citation_policy(workspace, bibliography_size=48, h3_count=6)
        assert citation_policy["hard"] == 24
        assert citation_policy["recommended"] == 32


def test_default_survey_citation_policy_stays_at_a150_plus_plus() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        _kickoff(workspace=workspace, topic="A literature survey of agent evaluation", pipeline="arxiv-survey")
        citation_policy = survey_citation_policy(workspace, bibliography_size=300, h3_count=10)
        assert citation_policy["hard"] == 150
        assert citation_policy["recommended"] == 165


def test_course_paper_binding_gate_accepts_compact_but_traceable_evidence() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        _kickoff(workspace=workspace, topic="Write a course paper on agent evaluation", pipeline="arxiv-survey")
        (workspace / "outline").mkdir(parents=True, exist_ok=True)
        (workspace / "papers").mkdir(parents=True, exist_ok=True)
        (workspace / "outline" / "outline.yml").write_text(
            "- id: '3'\n  title: Core\n  subsections:\n    - id: '3.1'\n      title: Evaluation\n",
            encoding="utf-8",
        )
        evidence_ids = [f"E-P{index:03d}-x" for index in range(1, 7)]
        (workspace / "papers" / "evidence_bank.jsonl").write_text(
            "\n".join(
                json.dumps({"evidence_id": evidence_id})
                for evidence_id in evidence_ids
            )
            + "\n",
            encoding="utf-8",
        )
        binding = {
            "sub_id": "3.1",
            "title": "Evaluation",
            "paper_ids": ["P001", "P002", "P003", "P004"],
            "mapped_bibkeys": [f"k{index}" for index in range(1, 7)],
            "bibkeys": [f"k{index}" for index in range(1, 7)],
            "evidence_ids": evidence_ids,
        }
        (workspace / "outline" / "evidence_bindings.jsonl").write_text(
            json.dumps(binding) + "\n",
            encoding="utf-8",
        )

        assert _check_evidence_bindings(workspace, ["outline/evidence_bindings.jsonl"]) == []

        queries_path = workspace / "queries.md"
        queries_path.write_text(
            queries_path.read_text(encoding="utf-8")
            .replace('draft_profile: "course_paper"', 'draft_profile: "survey"')
            .replace('per_subsection: "6"', 'per_subsection: "28"'),
            encoding="utf-8",
        )
        issues = _check_evidence_bindings(workspace, ["outline/evidence_bindings.jsonl"])
        assert {issue.code for issue in issues} == {"evidence_bindings_incomplete"}


def test_abstract_evidence_index_covers_complete_core_set_without_download_limit() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "papers").mkdir(parents=True)
        (workspace / "queries.md").write_text(
            '# Evidence strength\n- evidence_mode: "abstract"\n- fulltext_max_papers: ""\n',
            encoding="utf-8",
        )
        core_rows = [
            f"P{index:04d},RAG Evaluation Paper {index},2024,https://example.com/{index},"
            for index in range(1, 49)
        ]
        (workspace / "papers" / "core_set.csv").write_text(
            "paper_id,title,year,url,arxiv_id\n" + "\n".join(core_rows) + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                ".codex/skills/pdf-text-extractor/scripts/run.py",
                "--workspace",
                str(workspace),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        index_path = workspace / "papers" / "fulltext_index.jsonl"
        records = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 48
        assert {record["status"] for record in records} == {"skip_mode_abstract"}
        assert _check_pdf_text_extractor(workspace, ["papers/fulltext_index.jsonl"]) == []

        index_path.write_text(
            "\n".join(json.dumps(record) for record in records[:40]) + "\n",
            encoding="utf-8",
        )
        issues = _check_pdf_text_extractor(workspace, ["papers/fulltext_index.jsonl"])
        assert {issue.code for issue in issues} == {"abstract_index_incomplete"}


def test_course_paper_subsection_plan_is_six_moves_instead_of_ten() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    kwargs = {
        "sub_id": "3.1",
        "sub_title": "Evaluation",
        "rq": "How do evaluation protocols affect conclusions?",
        "axes": ["task", "metric", "budget"],
        "clusters": [{"label": "A"}, {"label": "B"}],
        "evidence_summary": {"abstract": 8},
    }

    assert len(module._paragraph_plan(**kwargs, draft_profile="course_paper")) == 6
    assert len(module._paragraph_plan(**kwargs, draft_profile="survey")) == 10


def test_chapter_h3_budget_respects_global_profile_limit() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "chapter-skeleton" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("chapter_skeleton_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module._chapter_h3_budgets(
        chapter_count=3,
        total_limit=6,
        preferred_per_chapter=3,
    ) == [2, 2, 2]
    assert module._chapter_h3_budgets(
        chapter_count=4,
        total_limit=10,
        preferred_per_chapter=3,
    ) == [3, 3, 2, 2]


def test_outline_builder_uses_rag_evaluation_axes_before_generic_agent_axes() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "outline-builder" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("outline_builder_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    defaults = load_yaml(module.DEFAULTS_PATH)

    retrieval = module._comparison_axes_bullet(
        parent="Evaluation Targets and Failure Decomposition",
        title="Retrieval Quality and Evidence Coverage",
        hint="Compare recall, ranking quality, and context coverage.",
        defaults=defaults,
    )
    attribution = module._comparison_axes_bullet(
        parent="Evaluation Targets and Failure Decomposition",
        title="Generation Faithfulness and Source Attribution",
        hint="Measure claim support, citation correctness, and attribution failure.",
        defaults=defaults,
    )

    assert "retrieval recall and rank quality" in retrieval
    assert "memory type" not in retrieval
    assert "claim-level support and answer faithfulness" in attribution


def test_rag_subsection_pack_produces_specific_axes_and_two_comparison_clusters() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_rag_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    goal = "Evaluate retrieval-augmented generation systems"
    title = "Generation Faithfulness and Source Attribution"
    axes = module._choose_axes(
        sub_title=title,
        goal=goal,
        evidence_needs=["evaluation protocol", "failure modes and limitations"],
        outline_axes=[],
    )
    refs = [
        module.PaperRef("P001", "Source2025", "Source Attribution in Retrieval-Augmented Generation", 2025, "abstract"),
        module.PaperRef("P002", "Ground2026", "Deceptive Grounding and Attribution Failure", 2026, "abstract"),
        module.PaperRef("P003", "Metric2026", "Do Attribution Metrics Transfer?", 2026, "abstract"),
        module.PaperRef("P004", "Ares2024", "ARES: An Automated Evaluation Framework for RAG", 2024, "abstract"),
        module.PaperRef("P005", "Query2025", "Cross-Query Consistency for Robust RAG", 2025, "abstract"),
        module.PaperRef("P006", "Fresco2026", "FRESCO: Evaluating Semantic Conflict in RAG", 2026, "abstract"),
    ]
    clusters = module._build_clusters(paper_refs=refs, goal=goal, sub_title=title, want=2)

    assert axes[:2] == [
        "claim-level support and answer faithfulness",
        "source-attribution correctness",
    ]
    assert [cluster["label"] for cluster in clusters] == [
        "Attribution and grounding diagnostics",
        "Automated faithfulness evaluators",
    ]
    assert all(len(cluster["paper_ids"]) >= 2 for cluster in clusters)


def test_rag_retrieval_brief_separates_diagnostics_from_coverage_optimization() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_retrieval_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    refs = [
        module.PaperRef("P001", "Quality2024", "Evaluating Retrieval Quality in RAG", 2024, "abstract"),
        module.PaperRef("P002", "Chunk2026", "Evaluating Chunking Strategies for RAG", 2026, "abstract"),
        module.PaperRef("P003", "Utility2026", "Predicting Retrieval Utility and Answer Quality", 2026, "abstract"),
        module.PaperRef("P004", "Coverage2024", "Coverage-Conditioned Retrieval-Augmented Generation", 2024, "abstract"),
        module.PaperRef("P005", "Query2026", "Cross-Query Consistency for Robust RAG", 2026, "abstract"),
        module.PaperRef("P006", "Domain2026", "Domain-Oriented RAG Design", 2026, "abstract"),
    ]

    clusters = module._build_clusters(
        paper_refs=refs,
        goal="Evaluate retrieval-augmented generation systems",
        sub_title="Retrieval quality and evidence coverage",
        want=2,
    )

    assert [cluster["label"] for cluster in clusters] == [
        "Retrieval diagnostic studies",
        "Retrieval utility and coverage optimization",
    ]
    assert all(len(cluster["paper_ids"]) >= 2 for cluster in clusters)


def test_rag_protocol_brief_separates_frameworks_from_stress_test_benchmarks() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_protocol_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    refs = [
        module.PaperRef("P001", "Rage2026", "RAGe: A Retrieval-Augmented Generation Evaluation Framework", 2026, "abstract"),
        module.PaperRef("P002", "Ares2023", "ARES: An Automated Evaluation Framework for RAG", 2023, "abstract"),
        module.PaperRef("P003", "Trec2025", "Overview of the TREC 2025 RAG Track", 2025, "abstract"),
        module.PaperRef("P004", "Authority2026", "AuthorityBench: Benchmarking Reliable RAG", 2026, "abstract"),
        module.PaperRef("P005", "Fresco2026", "FRESCO: Benchmarking Semantic Conflict in RAG", 2026, "abstract"),
        module.PaperRef("P006", "Mrag2026", "MRAG: Benchmarking RAG for Bio-medicine", 2026, "abstract"),
    ]

    clusters = module._build_clusters(
        paper_refs=refs,
        goal="Evaluate retrieval-augmented generation systems",
        sub_title="Dataset, task, and metric design",
        want=2,
    )

    assert [cluster["label"] for cluster in clusters] == [
        "Evaluation frameworks and shared tracks",
        "Domain and stress-test benchmarks",
    ]
    assert all(len(cluster["paper_ids"]) >= 2 for cluster in clusters)


def test_rag_deployment_brief_can_explicitly_include_meta_evidence() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_deployment_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    refs = [
        module.PaperRef("P001", "Trust2026", "Trustworthiness in RAG Systems: A Survey", 2026, "abstract"),
        module.PaperRef("P002", "Transfer2026", "Do Attribution Metrics Transfer?", 2026, "abstract"),
        module.PaperRef("P003", "Domain2025", "Domain-Oriented RAG Design", 2025, "abstract"),
        module.PaperRef("P004", "Open2024", "Open-Domain Evaluation of RAG", 2024, "abstract"),
    ]

    clusters = module._build_clusters(
        paper_refs=refs,
        goal="Evaluate retrieval-augmented generation systems",
        sub_title="Domain transfer, trustworthiness, and deployment",
        want=2,
    )

    assert [cluster["label"] for cluster in clusters] == [
        "Trust and evaluator-transfer studies",
        "Domain and deployment studies",
    ]
    assert "P001" in clusters[0]["paper_ids"]
    assert set(clusters[0]["paper_ids"]).isdisjoint(clusters[1]["paper_ids"])


def test_evidence_draft_recognizes_domain_neutral_evaluation_claims_and_axes() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "evidence-draft" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("evidence_draft_rag_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    axes = [
        "corpus and query provenance",
        "task coverage and difficulty",
        "retrieval and generation metric decomposition",
    ]
    snippets = [
        {
            "paper_id": "P001",
            "text": "Query and corpus provenance changes retrieval relevance and answer accuracy across evaluation datasets.",
            "citations": ["Key1"],
        },
        {
            "paper_id": "P002",
            "text": "Task coverage exposes a measurable gap between retrieval recall and downstream answer faithfulness.",
            "citations": ["Key2"],
        },
        {
            "paper_id": "P003",
            "text": "Metric decomposition separates context relevance from answer faithfulness and source attribution.",
            "citations": ["Key3"],
        },
        {
            "paper_id": "P004",
            "text": "Corpus provenance and task difficulty alter evaluator calibration and metric agreement.",
            "citations": ["Key4"],
        },
    ]

    claims = module._claim_candidates(
        title="Dataset, Task, and Metric Design",
        axes=axes,
        evidence_snippets=snippets,
        cite_keys=["Key1", "Key2", "Key3", "Key4"],
        has_fulltext=False,
    )
    comparisons = module._comparisons(
        title="Dataset, Task, and Metric Design",
        axes=axes,
        clusters=[
            {"label": "Protocol studies", "paper_ids": ["P001", "P002"]},
            {"label": "Evaluator studies", "paper_ids": ["P003", "P004"]},
        ],
        cite_keys=["Key1", "Key2", "Key3", "Key4"],
        evidence_snippets=snippets,
        policy=module._runtime_policy(),
    )

    assert len(claims) >= 3
    assert len(comparisons) == 3
    assert all(item["A_highlights"] and item["B_highlights"] for item in comparisons)
    assert module._comparison_eligible(
        "Structure-aware chunking yields higher retrieval effectiveness on top-K metrics and lower computational costs than baseline strategies."
    )


def test_evidence_comparison_highlights_preserve_long_complete_sentences() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "evidence-draft" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("evidence_draft_complete_sentence_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    long_result = (
        "Experiments on four open-domain question answering benchmarks show that CQC-RAG "
        "outperforms the strongest previous multi-query baseline by +4.76 pp EM on TriviaQA "
        "and +9.12 pp EM on MuSiQue, validating the effectiveness of cross-query consistency "
        "for filtering noise-induced hallucinations."
    )
    snippets = [
        {"paper_id": "P001", "text": long_result, "citations": ["Key1"]},
        {
            "paper_id": "P002",
            "text": "Structure-aware chunking yields higher retrieval effectiveness on top-K metrics than baseline strategies.",
            "citations": ["Key2"],
        },
        {
            "paper_id": "P003",
            "text": "Retrieval utility predicts downstream answer quality across three evaluation datasets.",
            "citations": ["Key3"],
        },
        {
            "paper_id": "P004",
            "text": "Coverage-conditioned retrieval improves evidence recall under a fixed context budget.",
            "citations": ["Key4"],
        },
    ]

    comparisons = module._comparisons(
        title="Retrieval quality and evidence coverage",
        axes=["retrieval quality"],
        clusters=[
            {"label": "Diagnostics", "paper_ids": ["P001", "P002"]},
            {"label": "Optimization", "paper_ids": ["P003", "P004"]},
        ],
        cite_keys=["Key1", "Key2", "Key3", "Key4"],
        evidence_snippets=snippets,
        policy=module._runtime_policy(),
    )

    assert comparisons
    excerpts = [
        item["excerpt"]
        for comparison in comparisons
        for side in ("A_highlights", "B_highlights")
        for item in comparison[side]
    ]
    assert long_result in excerpts
    assert all(not excerpt.endswith("noise-induced") for excerpt in excerpts)


def test_writer_evidence_normalizer_keeps_complete_coordinated_list() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_writer_evidence_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    sentence = (
        "ARES is an Automated RAG Evaluation System for evaluating RAG systems along the dimensions "
        "of context relevance, answer faithfulness, and answer relevance."
    )

    assert module._normalize_evidence_text(sentence, limit=240) == sentence

    long_sentence = (
        "Experiments on four open-domain question answering benchmarks show that CQC-RAG "
        "outperforms the strongest previous multi-query baseline by +4.76 pp EM on TriviaQA "
        "and +9.12 pp EM on MuSiQue, validating the effectiveness of cross-query consistency "
        "for filtering noise-induced hallucinations."
    )
    normalized_once = module._support_text(long_sentence, kind="fact")
    assert normalized_once
    assert module._support_text(normalized_once, kind="fact") == normalized_once

    assert module._neutralize_author_voice(
        "We term this deceptive grounding (DG): a failure invisible to ordinary citation checks."
    ) == "deceptive grounding (DG) describes a failure invisible to ordinary citation checks."

    assert module._normalize_evidence_text(
        "Existing metrics are unable to distinguish retrieval,reasoning, or grounding failures."
    ) == "Existing metrics are unable to distinguish retrieval, reasoning, or grounding failures."
    assert module._support_text(
        "This year's challenge introduces long narrative queries for the shared track.",
        kind="limit",
    ) == ""
    assert module._support_text(
        "ListJudge offers optimal cost-effectiveness across the reported benchmark.",
        kind="limit",
    ) == ""
    assert module._support_text(
        "Structure-aware chunking incurs lower computational costs than semantic baselines.",
        kind="limit",
    ) == ""
    assert module._support_text(
        "This document is a practical framework for resilient RAG deployment.",
        kind="fact",
    ) == ""
    assert module._support_text(
        "Existing benchmarks fail under temporal corpus shift.",
        kind="limit",
    ) == "Existing benchmarks fail under temporal corpus shift."
    assert module._inline_proposition(
        "A prompt-based evaluator is not uniformly reliable across datasets.",
        kind="limit",
    ).startswith("a prompt-based evaluator")


def test_evidence_draft_rejects_named_challenges_and_positive_cost_results_as_limits() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "evidence-draft" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("evidence_draft_limit_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    named_challenge = (
        "Building on the inaugural track, this year's challenge introduces long narrative queries."
    )
    positive_cost = (
        "Results show that ListJudge offers optimal cost-effectiveness on the benchmark."
    )
    lower_cost = "Structure-aware chunking incurs lower computational costs than semantic baselines."
    recommendation = (
        "These findings suggest that RAG evaluation should include multi-stage failure analysis."
    )
    genuine_limit = "Existing benchmarks fail under temporal corpus shift."
    contradiction_limit = (
        "This approach can introduce errors when sources contain outdated or contradictory information."
    )
    reduced_errors = (
        "The proposed reranker reduces retrieval errors by 37% on three benchmarks."
    )
    corrected_sources = (
        "The model corrects outdated information and reduces contradictory answers."
    )
    rows = module._limitations_from_notes(
        ["P001"],
        notes_by_pid={
            "P001": {
                "paper_id": "P001",
                "title": "Authority Estimation for Retrieval-Augmented Generation",
                "bibkey": "Authority2026",
                "evidence_level": "fulltext",
                "limitations": [
                    named_challenge,
                    positive_cost,
                    lower_cost,
                    recommendation,
                    genuine_limit,
                    contradiction_limit,
                    reduced_errors,
                    corrected_sources,
                ],
            }
        },
        cite_keys=["Authority2026"],
    )
    bullets = [str(row.get("bullet") or "") for row in rows]
    assert genuine_limit in bullets
    assert contradiction_limit in bullets
    assert named_challenge not in bullets
    assert positive_cost not in bullets
    assert lower_cost not in bullets
    assert recommendation not in bullets
    assert reduced_errors not in bullets
    assert corrected_sources not in bullets
    assert module._sanitize_source_text(
        "Existing metrics are unable to distinguish retrieval,reasoning, or grounding failures."
    ) == "Existing metrics are unable to distinguish retrieval, reasoning, or grounding failures."


def test_evidence_draft_does_not_turn_improvements_into_limitations() -> None:
    module = _load_skill_script("evidence-draft")
    positive_results = [
        "The proposed reranker reduces retrieval errors by 37% on three benchmarks.",
        "The model corrects outdated information and reduces contradictory answers.",
        "Error rates drop by 37% after reranking.",
        "The method detects contradictory information before generation.",
        "The system achieves 20% fewer hallucinations on NQ.",
        "The method is robust to domain shift.",
        "The system improves security against attacks.",
        "The model achieves strong performance on out-of-distribution inputs.",
        "The guard prevents attacks before they reach the model.",
        "The scheduler eliminates latency bottlenecks in the serving path.",
        "The system is secure against attacks.",
        "Attack success rate drops by 40% after hardening.",
        "The method improves robustness under domain shift.",
        "The system has low latency.",
    ]

    rows = module._limitations_from_notes(
        ["P001"],
        notes_by_pid={
            "P001": {
                "paper_id": "P001",
                "title": "Repairing Retrieval Failures",
                "bibkey": "Repair2026",
                "evidence_level": "fulltext",
                "limitations": positive_results,
            }
        },
        cite_keys=["Repair2026"],
    )

    assert rows == []


def test_evidence_draft_keeps_negated_failures_without_metric_false_positives() -> None:
    module = _load_skill_script("evidence-draft")
    unresolved = "The reranker does not reduce hallucinations under temporal corpus shift."

    rows = module._limitations_from_notes(
        ["P001"],
        notes_by_pid={
            "P001": {
                "paper_id": "P001",
                "title": "Retrieval Under Shift",
                "bibkey": "Shift2026",
                "evidence_level": "fulltext",
                "limitations": [
                    "The evaluation reports an error rate of 2.1% on NQ.",
                    unresolved,
                ],
            }
        },
        cite_keys=["Shift2026"],
    )

    assert [str(row.get("bullet") or "") for row in rows] == [unresolved]


def test_paper_notes_extracts_concrete_failure_sentence_from_abstract() -> None:
    module = _load_skill_script("paper-notes")
    abstract = (
        "Retrieval grounding can improve answers in high-stakes domains. "
        "Yet, this approach can introduce errors when source documents contain outdated or "
        "contradictory information. "
        "The study compares five models on medical queries."
    )

    limitations = module._infer_limitations(
        evidence_level="abstract",
        mapped_sections=["5.2"],
        abstract=abstract,
    )

    assert limitations == [
        "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence.",
        "Yet, this approach can introduce errors when source documents contain outdated or contradictory information.",
    ]


def test_paper_notes_does_not_extract_resolved_failures_as_limitations() -> None:
    module = _load_skill_script("paper-notes")
    abstract = (
        "The proposed reranker reduces retrieval errors by 37% on three benchmarks. "
        "The model also corrects outdated information and reduces contradictory answers. "
        "Error rates drop by 37% after reranking. "
        "The verifier detects contradictory information before generation. "
        "The system achieves 20% fewer hallucinations on NQ. "
        "The method is robust to domain shift. "
        "The system improves security against attacks. "
        "The model achieves strong performance on out-of-distribution inputs. "
        "The guard prevents attacks before they reach the model. "
        "The scheduler eliminates latency bottlenecks in the serving path. "
        "The system is secure against attacks. "
        "Attack success rate drops by 40% after hardening. "
        "The method improves robustness under domain shift. "
        "The system has low latency."
    )

    limitations = module._infer_limitations(
        evidence_level="abstract",
        mapped_sections=["4.1"],
        abstract=abstract,
    )

    assert limitations == [
        "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence."
    ]


def test_paper_notes_prefers_unresolved_negation_over_neutral_error_metrics() -> None:
    module = _load_skill_script("paper-notes")
    unresolved = "The method does not address the generalization gap under domain shift."
    abstract = (
        "The evaluation reports an error rate of 2.1% on NQ. "
        f"{unresolved}"
    )

    limitations = module._infer_limitations(
        evidence_level="abstract",
        mapped_sections=["4.1"],
        abstract=abstract,
    )

    assert limitations == [
        "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence.",
        unresolved,
    ]


def test_paper_notes_keeps_negated_detection_after_positive_clause_cleanup() -> None:
    module = _load_skill_script("paper-notes")
    unresolved = "The method does not detect contradictory information before generation."
    abstract = (
        "The verifier detects contradictory information in the main benchmark. "
        f"{unresolved}"
    )

    limitations = module._infer_limitations(
        evidence_level="abstract",
        mapped_sections=["4.1"],
        abstract=abstract,
    )

    assert limitations == [
        "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence.",
        unresolved,
    ]


def test_paper_notes_prefers_persistent_attack_risk_over_positive_security_results() -> None:
    module = _load_skill_script("paper-notes")
    unresolved = "Attack success rate remains high under adaptive prompting."
    abstract = (
        "The system is secure against attacks in the base evaluation. "
        "Attack success rate drops by 40% after hardening. "
        "The method improves robustness under domain shift. "
        "The system has low latency. "
        f"{unresolved}"
    )

    limitations = module._infer_limitations(
        evidence_level="abstract",
        mapped_sections=["4.1"],
        abstract=abstract,
    )

    assert limitations == [
        "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence.",
        unresolved,
    ]


def test_writer_context_pack_uses_polarity_aware_limitation_signals() -> None:
    module = _load_skill_script("writer-context-pack")

    assert module._has_negative_limit_signal(
        "This approach can introduce errors when sources contain outdated information."
    )
    assert not module._has_negative_limit_signal(
        "The proposed reranker reduces retrieval errors by 37% on three benchmarks."
    )
    assert not module._has_negative_limit_signal(
        "The model corrects outdated information and reduces contradictory answers."
    )
    assert not module._has_negative_limit_signal(
        "The evaluation reports an error rate of 2.1% on NQ."
    )
    assert not module._has_negative_limit_signal(
        "The verifier detects errors caused by stale evidence before generation."
    )
    assert not module._has_negative_limit_signal(
        "Error rates drop by 37% after reranking."
    )
    assert not module._has_negative_limit_signal(
        "The method detects contradictory information before generation."
    )
    assert not module._has_negative_limit_signal(
        "The system achieves 20% fewer hallucinations on NQ."
    )
    assert not module._has_negative_limit_signal(
        "The method is robust to domain shift."
    )
    assert not module._has_negative_limit_signal(
        "The system improves security against attacks."
    )
    assert not module._has_negative_limit_signal(
        "The model achieves strong performance on out-of-distribution inputs."
    )
    assert not module._has_negative_limit_signal(
        "The guard prevents attacks before they reach the model."
    )
    assert not module._has_negative_limit_signal(
        "The scheduler eliminates latency bottlenecks in the serving path."
    )
    assert not module._has_negative_limit_signal(
        "The system is secure against attacks."
    )
    assert not module._has_negative_limit_signal(
        "Attack success rate drops by 40% after hardening."
    )
    assert not module._has_negative_limit_signal(
        "The method improves robustness under domain shift."
    )
    assert not module._has_negative_limit_signal(
        "The system has low latency."
    )
    assert module._has_negative_limit_signal(
        "The reranker does not reduce hallucinations under temporal corpus shift."
    )
    assert module._has_negative_limit_signal(
        "The method does not address the generalization gap under domain shift."
    )
    assert module._has_negative_limit_signal(
        "Error rates remain high under domain shift."
    )
    assert module._has_negative_limit_signal(
        "Hallucinations persist after retrieval."
    )
    assert module._has_negative_limit_signal(
        "Error rates do not drop under temporal shift."
    )
    assert module._has_negative_limit_signal(
        "The system does not achieve fewer hallucinations on adversarial prompts."
    )
    assert module._has_negative_limit_signal(
        "The method is not robust to domain shift."
    )
    assert module._has_negative_limit_signal(
        "The system does not improve security against attacks."
    )
    assert module._has_negative_limit_signal(
        "The model fails to maintain strong performance on out-of-distribution inputs."
    )
    assert module._has_negative_limit_signal(
        "The method does not detect contradictory information before generation."
    )
    assert module._has_negative_limit_signal(
        "The guard does not prevent attacks against the model."
    )
    assert module._has_negative_limit_signal(
        "The system is not secure against attacks."
    )
    assert module._has_negative_limit_signal(
        "The method does not improve robustness under domain shift."
    )
    assert module._has_negative_limit_signal(
        "Attack success rate remains high under adaptive prompting."
    )
    assert module._has_negative_limit_signal(
        "The system does not have low latency under load."
    )


def test_shared_limitation_policy_scripts_keep_standalone_help_portable(
    tmp_path: Path,
) -> None:
    for skill_name in ("evidence-draft", "paper-notes", "writer-context-pack"):
        script = REPO_ROOT / ".codex" / "skills" / skill_name / "scripts" / "run.py"
        result = subprocess.run(
            [sys.executable, "-S", str(script), "--help"],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"{skill_name}: {result.stderr or result.stdout}"


def test_writer_does_not_repeat_the_same_evidence_as_fact_and_limit() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_writer_dedupe_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    evidence = "Existing benchmarks fail under temporal corpus shift."
    record = {"text": evidence, "citations": ["Shift2026"]}
    paragraph = module._compose_cluster_paragraph(
        title="Robustness evaluation",
        plan_item={
            "argument_role": "evaluation_cluster_A",
            "focus": ["temporal shift"],
        },
        profile={"label": "stability studies", "axes": ["temporal shift"]},
        other_label="adaptation studies",
        kind="evaluation",
        facts=[],
        anchors=[record],
        claims=[],
        limits=[record],
        benchmarks=[],
        protocol_citations=[],
    )
    assert paragraph.count("Existing benchmarks fail under temporal corpus shift") == 1

    repeated = (
        "A prompt-based evaluator is not uniformly reliable across datasets, so metric choice must "
        "be validated on the target protocol before results are compared."
    )
    deduped = module._dedupe_evidence_sentences_in_paragraphs(
        [
            f"{repeated.rstrip('.')} [@Judge2026].",
            f"A separate limitation follows. {repeated.rstrip('.')} [@Judge2026].",
        ]
    )
    assert " ".join(deduped).count(repeated.rstrip(".")) == 1
    assert deduped[1] == "A separate limitation follows."

    wrapped = module._dedupe_evidence_sentences_in_paragraphs(
        [
            f"{repeated.rstrip('.')} [@Judge2026].",
            f"A narrower reading is warranted because {repeated.lower().rstrip('.')} [@Judge2026].",
        ]
    )
    assert len(wrapped) == 1


def test_anchor_sheet_rejects_inventory_and_author_meta_text() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "anchor-sheet" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("anchor_sheet_hygiene_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert not module._is_usable_anchor_text("Evaluation mentions include: RAG, ARES, and KILT.")
    assert not module._is_usable_anchor_text("Our contributions are three-fold: benchmark, metric, and analysis.")
    assert not module._is_usable_anchor_text(
        "Prefer head-to-head comparisons only when benchmark and metric are shared."
    )
    assert not module._is_usable_anchor_text(
        "When comparing results, anchor the paragraph with task, metric, and constraint."
    )
    assert module._is_usable_anchor_text("ARES evaluates answer faithfulness on KILT tasks.")


def test_writer_selfloop_detects_duplicate_evidence_sized_sentences() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "writer-selfloop" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("writer_selfloop_duplicate_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    repeated = (
        "A prompt-based evaluator is not uniformly reliable across datasets, so metric choice must "
        "be validated on the target protocol before results are compared."
    )
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        section = workspace / "sections" / "S4_2.md"
        section.parent.mkdir(parents=True)
        section.write_text(f"{repeated}\n\n{repeated}\n", encoding="utf-8")
        duplicates = module._duplicate_long_sentences_for_h3(
            workspace=workspace,
            h3_paths=["sections/S4_2.md"],
        )

    assert duplicates == [("sections/S4_2.md", repeated, 2)]


def test_evidence_draft_keeps_specific_survey_evidence_but_not_landscape_prose() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "evidence-draft" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("evidence_draft_meta_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    notes = {
        "P001": {
            "paper_id": "P001",
            "title": "Trustworthiness in RAG Systems: A Survey",
            "bibkey": "Trust2026",
            "evidence_level": "abstract",
            "key_results": [
                "TRC Bench evaluates factuality, robustness, fairness, transparency, accountability, and privacy across proprietary and open-source models."
            ],
        },
        "P002": {
            "paper_id": "P002",
            "title": "A Survey of Retrieval-Augmented Generation",
            "bibkey": "Survey2025",
            "evidence_level": "abstract",
            "summary_bullets": ["This survey reviews the rapidly growing RAG landscape."],
        },
    }

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        snippets = module._evidence_snippets(
            workspace=Path(tmp),
            pids=["P001", "P002"],
            notes_by_pid=notes,
            bibkeys={"Trust2026", "Survey2025"},
            limit=10,
        )

    assert [snippet["paper_id"] for snippet in snippets] == ["P001"]
    assert "TRC Bench" in snippets[0]["text"]


def test_course_writer_context_policy_can_preserve_required_comparison_cards() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "writer-context-pack" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("writer_context_course_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    limits = module._profile_limits("course_paper")

    assert limits["comparison_keep_limit"] >= 3
    assert limits["comparison_pair_limit"] >= 3


def test_subsection_refinement_marker_must_be_newer_than_writer_inputs() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_writer_marker_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        prerequisite = workspace / "writer_context_packs.jsonl"
        marker = workspace / "h3_bodies.refined.ok"
        prerequisite.write_text("{}\n", encoding="utf-8")
        marker.write_text("reviewed\n", encoding="utf-8")
        marker_ns = marker.stat().st_mtime_ns
        os.utime(marker, ns=(marker_ns + 2, marker_ns + 2))
        assert module._refinement_marker_is_current(marker, [prerequisite])

        os.utime(prerequisite, ns=(marker_ns + 3, marker_ns + 3))
        assert not module._refinement_marker_is_current(marker, [prerequisite])


def test_subsection_writer_normalizes_scoped_tension_and_uses_domain_neutral_defaults() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_writer_language_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    title = "Generation faithfulness and source attribution"
    tension = (
        "A central tension in Generation faithfulness and source attribution is the trade-off between "
        "claim-level support and answer faithfulness, source-attribution correctness and reliable evaluation."
    )

    assert module._normalize_tension(tension, title) == (
        "claim-level support and answer faithfulness, source-attribution correctness and reliable evaluation"
    )

    generic_assets = [
        REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "assets" / "paragraph_job_templates.json",
        REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "assets" / "bootstrap_paragraph_templates.json",
        REPO_ROOT / ".codex" / "skills" / "front-matter-writer" / "assets" / "front_matter_templates.json",
    ]
    generic_text = "\n".join(path.read_text(encoding="utf-8") for path in generic_assets).lower()
    assert "embodiment" not in generic_text
    assert "sensor access" not in generic_text


def test_subsection_writer_drops_cluster_paragraph_without_usable_evidence() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_writer_support_gate_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    paragraph = module._compose_cluster_paragraph(
        title="Retrieval quality and evidence coverage",
        plan_item={"argument_role": "evaluation_cluster_A", "focus": ["evaluation anchor"]},
        profile={"label": "Retrieval diagnostics", "axes": ["retrieval quality"]},
        other_label="Coverage optimization",
        kind="evaluation",
        facts=[],
        anchors=[],
        claims=[],
        limits=[],
        benchmarks=[],
        protocol_citations=["Key1"],
    )

    assert paragraph == ""


def test_shared_refinement_marker_becomes_stale_after_upstream_change() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        output = workspace / "artifact.yml"
        upstream = workspace / "upstream.yml"
        marker = workspace / "artifact.refined.ok"
        output.write_text("artifact\n", encoding="utf-8")
        upstream.write_text("upstream\n", encoding="utf-8")
        marker.write_text("reviewed\n", encoding="utf-8")
        marker_ns = marker.stat().st_mtime_ns
        os.utime(marker, ns=(marker_ns + 2, marker_ns + 2))

        assert refinement_marker_is_current(marker, [output, upstream])

        os.utime(upstream, ns=(marker_ns + 3, marker_ns + 3))
        assert not refinement_marker_is_current(marker, [output, upstream])


def test_subsection_cluster_fallback_repartitions_one_dominant_tag() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "subsection-briefs" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("subsection_briefs_cluster_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    refs = [
        module.PaperRef(
            f"P{index:03d}",
            f"Memory{index}",
            f"Long-term Memory Architecture {index}",
            2025,
            "abstract",
        )
        for index in range(1, 9)
    ]

    clusters = module._build_clusters(
        paper_refs=refs,
        goal="Survey long-term memory for LLM agents",
        sub_title="Memory Architectures",
        want=2,
    )

    assert len(clusters) == 2
    assert all(len(cluster["paper_ids"]) >= 2 for cluster in clusters)
    assert set(clusters[0]["paper_ids"]).isdisjoint(clusters[1]["paper_ids"])


def test_compact_mapping_limits_prevent_one_paper_from_covering_every_h3() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "section-mapper" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("section_mapper_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module._compute_limits(
        soft_limit=0,
        hard_limit=0,
        subsections=6,
        papers=48,
        per_subsection=6,
    ) == (2, 4)


def test_section_mapping_rejects_generic_single_term_and_cross_domain_matches() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "section-mapper" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("section_mapper_semantic_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    faithfulness_terms = {"faithfulness", "source", "attribution"}
    relevant_score, _ = module._score_candidate(
        title_tokens=faithfulness_terms,
        context_tokens=faithfulness_terms | {"automated", "calibration"},
        paper_title_tokens={"source", "attribution"},
        paper_abstract_tokens={"faithfulness", "documents", "calibration"},
        high_signal_tokens=faithfulness_terms | {"automated", "calibration"},
    )
    catalyst_score, _ = module._score_candidate(
        title_tokens=faithfulness_terms,
        context_tokens=faithfulness_terms | {"cost", "stability"},
        paper_title_tokens={"catalysts", "generation"},
        paper_abstract_tokens={"materials", "cost", "stability"},
        high_signal_tokens=faithfulness_terms | {"cost", "stability"},
    )
    generic_model_score, _ = module._score_candidate(
        title_tokens={"automated", "model", "human"},
        context_tokens={"automated", "model", "human", "agreement"},
        paper_title_tokens={"clinical", "reasoning"},
        paper_abstract_tokens={"model"},
        high_signal_tokens={"automated", "human", "agreement"},
    )

    assert relevant_score > 0
    assert catalyst_score == 0
    assert generic_model_score == 0


def test_rag_mapping_pack_rejects_generic_task_match_and_boosts_evaluation_titles() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "section-mapper" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("section_mapper_domain_pack_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    pack_path = (
        REPO_ROOT
        / ".codex"
        / "skills"
        / "section-mapper"
        / "assets"
        / "domain_packs"
        / "rag_evaluation.json"
    )
    rules = module._domain_section_rules(
        workspace_text="Write a course paper to evaluate retrieval-augmented generation systems.",
        section_title="Dataset, task, and metric design",
        packs=module._load_domain_packs([pack_path]),
    )

    rejected_score, rejected_terms = module._apply_domain_section_rules(
        score=8,
        matched_terms=["task"],
        paper_title="Multi-Task Agentic RAG for Cold-Start Recommendations",
        paper_abstract="The system uses a task router and evaluates recommendation quality.",
        rules=rules,
    )
    accepted_score, accepted_terms = module._apply_domain_section_rules(
        score=0,
        matched_terms=[],
        paper_title="RAGe: A Retrieval-Augmented Generation Evaluation Framework",
        paper_abstract="The framework decomposes retrieval and answer metrics.",
        rules=rules,
    )

    assert rules
    assert (rejected_score, rejected_terms) == (0, [])
    assert accepted_score >= 8
    assert "evaluation framework" in accepted_terms


def test_mapping_gate_rejects_low_confidence_filler_rows() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "outline" / "outline.yml").write_text(
            "- id: '3'\n"
            "  title: Evidence\n"
            "  subsections:\n"
            "    - id: '3.1'\n"
            "      title: Source Attribution\n",
            encoding="utf-8",
        )
        (workspace / "outline" / "mapping.tsv").write_text(
            "section_id\tsection_title\tpaper_id\twhy\n"
            "3.1\tSource Attribution\tP001\tLow-confidence candidate for Source Attribution; manual review is required.\n"
            "3.1\tSource Attribution\tP002\tSection-specific evidence for Source Attribution; discriminative concepts: source.\n"
            "3.1\tSource Attribution\tP003\tSection-specific evidence for Source Attribution; discriminative concepts: attribution.\n",
            encoding="utf-8",
        )

        issues = _check_mapping(workspace, ["outline/mapping.tsv"])

    assert "mapping_low_confidence" in {issue.code for issue in issues}


def test_mapping_gap_candidates_are_read_only_and_section_specific() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "section-mapper" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("section_mapper_gap_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    rows = module._build_gap_candidate_rows(
        subsections=[{"id": "4.2", "title": "Automated and Human Evaluation"}],
        picks_by_subsection={"4.2": []},
        query_token_sets_by_subsection={
            "4.2": (
                {"automated", "human"},
                {"automated", "human", "agreement", "calibration"},
            )
        },
        candidate_records=[
            {
                "title": "Automated Evaluation with Human Agreement",
                "abstract": "The evaluator measures calibration against human judgments.",
                "year": 2025,
                "url": "https://example.test/relevant",
            },
            {
                "title": "High-Entropy Catalyst Discovery",
                "abstract": "A model predicts material stability.",
                "year": 2026,
                "url": "https://example.test/irrelevant",
            },
        ],
        core_keys=set(),
        per_subsection=3,
        minimum_score=3,
        high_signal_tokens={"automated", "human", "agreement", "calibration"},
        tokenize=tokenize,
        normalize_title=normalize_title_for_dedupe,
    )

    assert [row["candidate_title"] for row in rows] == ["Automated Evaluation with Human Agreement"]
    assert rows[0]["missing_slots"] == 3


def test_course_paper_table_contract_accepts_one_index_and_one_appendix_table() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        _kickoff(workspace=workspace, topic="Write a course paper on agent evaluation", pipeline="arxiv-survey")
        (workspace / "outline").mkdir(parents=True, exist_ok=True)
        (workspace / "outline" / "table_schema.md").write_text(
            "# Table schema\n\n## Table I1: Index\n\nEvidence map.\n\n## Table A1: Reader table\n\nComparison map.\n",
            encoding="utf-8",
        )
        one_table = "| Topic | Evidence |\n|---|---|\n| Evaluation | [@KeyA] |\n"
        (workspace / "outline" / "tables_index.md").write_text(one_table, encoding="utf-8")
        (workspace / "outline" / "tables_appendix.md").write_text(one_table, encoding="utf-8")

        assert _check_table_schema(workspace, ["outline/table_schema.md"]) == []
        assert _check_tables_index_md(workspace, ["outline/tables_index.md"]) == []
        assert _check_tables_appendix_md(workspace, ["outline/tables_appendix.md"]) == []

        queries_path = workspace / "queries.md"
        queries_path.write_text(
            queries_path.read_text(encoding="utf-8").replace(
                'draft_profile: "course_paper"',
                'draft_profile: "survey"',
            ),
            encoding="utf-8",
        )
        assert {issue.code for issue in _check_table_schema(workspace, ["outline/table_schema.md"])} == {"table_schema_too_few"}
        assert {issue.code for issue in _check_tables_index_md(workspace, ["outline/tables_index.md"])} == {"tables_missing"}
        assert {issue.code for issue in _check_tables_appendix_md(workspace, ["outline/tables_appendix.md"])} == {"tables_appendix_missing"}


def test_appendix_table_cells_never_clip_mid_sentence() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "appendix-table-writer" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("appendix_table_writer_complete_text_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first = "Retrieval recall is measured against relevance labels."
    second = " This second sentence is intentionally much longer than the preferred cell budget."
    assert module._sanitize_cell_text(first + second, limit=60) == first

    incomplete = "Evaluation of the retrieval model based on query-document relevance labels " * 4
    assert module._sanitize_cell_text(incomplete, limit=60) == ""


def test_course_paper_latex_keeps_compact_table_whole_without_forced_pages() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "latex-scaffold" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("latex_scaffold_compact_table_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = "\n".join(f"| Area {index} | concise contrast | [@Key{index}] |" for index in range(1, 7))
    markdown = (
        "**Appendix Table A1. Comparison map.**\n\n"
        "| Area | Evidence contrast | Key refs |\n"
        "|---|---|---|\n"
        f"{rows}\n"
    )
    compact = module._markdown_to_latex(markdown, split_large_tables=False)

    assert "(continued)" not in compact
    assert r"\clearpage" not in compact
    assert compact.count(r"\begin{table}[H]") == 1


def test_course_paper_latex_scaffold_uses_compact_page_geometry(tmp_path: Path) -> None:
    script = REPO_ROOT / ".codex" / "skills" / "latex-scaffold" / "scripts" / "run.py"
    asset = (
        REPO_ROOT
        / ".codex"
        / "skills"
        / "latex-scaffold"
        / "assets"
        / "layout_profiles.json"
    )
    policy = json.loads(asset.read_text(encoding="utf-8"))
    course_layout = policy["profiles"]["course_paper"]
    skill_text = (
        REPO_ROOT / ".codex" / "skills" / "latex-scaffold" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert course_layout["margin"] == "0.9in"
    assert "assets/layout_profiles.json" in skill_text
    assert "0.9in" in skill_text
    output = tmp_path / "output"
    output.mkdir(parents=True)
    (output / "DRAFT.md").write_text(
        "# Compact Report\n\n## Introduction\n\nA concise evidence-backed report.\n",
        encoding="utf-8",
    )
    (tmp_path / "queries.md").write_text(
        "- draft_profile: course_paper\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(script), "--workspace", str(tmp_path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    tex = (tmp_path / "latex" / "main.tex").read_text(encoding="utf-8")
    assert rf"\usepackage[a4paper,margin={course_layout['margin']}]{{geometry}}" in tex


def test_numeric_hygiene_rewrites_to_standalone_caveat() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "evaluation-anchor-checker" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("evaluation_anchor_standalone_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    paragraph = "Method A improves by 17% [@BenchStudy]."
    pack = {
        "sub_id": "4.2",
        "title": "Automated evaluators and human validation",
        "evaluation_anchor_minimal": {
            "task": "benchmark tasks",
            "metric": "accuracy",
            "constraint": "annotation budget",
        },
    }
    rewritten, changed = module._polish_paragraph(paragraph, pack)

    assert changed == 1
    assert "17%" not in rewritten
    assert "[@BenchStudy]" in rewritten
    assert not re.search(r"(?i)\b(?:that number|the cited number|numeric margin)\b", rewritten)

    migrated, changed = module._polish_paragraph(
        "The cited number only holds under the stated setup in benchmark tasks [@BenchStudy].",
        pack,
    )
    assert changed == 1
    assert "[@BenchStudy]" in migrated
    assert "the cited number" not in migrated.lower()


def test_draft_gate_rejects_dangling_numeric_caveat() -> None:
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        _kickoff(workspace=workspace, topic="Write a course paper on agent evaluation", pipeline="arxiv-survey")
        (workspace / "output").mkdir(parents=True, exist_ok=True)
        (workspace / "output" / "DRAFT.md").write_text(
            "# Agent Evaluation\n\n## Introduction\n\n"
            "That number belongs to the cited setup and should not travel [@RealKey].\n",
            encoding="utf-8",
        )

        issues = _check_draft(workspace, ["output/DRAFT.md"])

        assert "draft_dangling_numeric_caveat" in {issue.code for issue in issues}


def test_survey_c5_dependencies_snapshot_only_after_all_section_mutators() -> None:
    for template_name in ["UNITS.arxiv-survey.csv", "UNITS.arxiv-survey-latex.csv"]:
        with (REPO_ROOT / "templates" / template_name).open(encoding="utf-8", newline="") as handle:
            rows = {row["unit_id"]: row for row in csv.DictReader(handle)}

        assert rows["U1006"]["depends_on"] == "U1005"
        assert rows["U1007"]["depends_on"] == "U1006"
        assert rows["U102"]["depends_on"] == "U1007"
        assert rows["U1026"]["depends_on"] == "U102"
        assert rows["U1008"]["depends_on"] == "U1026"
        assert rows["U1025"]["depends_on"] == "U1008"
        assert rows["U098"]["depends_on"] == "U1025"
        assert "U1025" in rows["U101"]["depends_on"].split(";")


def test_argument_snapshot_refreshes_and_then_detects_stale_section_manifest() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "argument-selfloop" / "scripts" / "run.py"
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "sections").mkdir(parents=True)
        (workspace / "outline" / "outline.yml").write_text(
            '- id: "3"\n  title: Evaluation\n  subsections:\n    - id: "3.1"\n      title: Retrieval quality\n',
            encoding="utf-8",
        )
        section_path = workspace / "sections" / "S3_1.md"
        section_path.write_text(
            "Retrieval evaluation needs an explicit metric contract [@StudyA].\n\n"
            "Benchmark evidence remains conditional on corpus shift [@StudyB].\n",
            encoding="utf-8",
        )
        (workspace / "sections" / "sections_manifest.jsonl").write_text(
            json.dumps({"kind": "h3", "id": "3.1", "path": "sections/S3_1.md", "sha256": "stale"}) + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(script), "--workspace", str(workspace)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        manifest = json.loads((workspace / "sections" / "sections_manifest.jsonl").read_text(encoding="utf-8"))
        assert manifest["sha256"] == hashlib.sha256(section_path.read_bytes()).hexdigest()
        assert manifest["bytes"] == section_path.stat().st_size
        assert _check_argument_snapshot(workspace, []) == []

        section_path.write_text(section_path.read_text(encoding="utf-8") + "\nA later edit changes the snapshot.\n", encoding="utf-8")
        issues = _check_argument_snapshot(workspace, [])
        assert "sections_manifest_stale" in {issue.code for issue in issues}


def test_paragraph_curator_only_compacts_h3_and_preserves_citation_blocks() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "paragraph-curator" / "scripts" / "run.py"
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "sections").mkdir(parents=True)
        (workspace / "queries.md").write_text('- draft_profile: "course_paper"\n', encoding="utf-8")
        (workspace / "outline" / "outline.yml").write_text(
            '- id: "1"\n  title: Introduction\n'
            '- id: "3"\n  title: Evaluation\n  subsections:\n    - id: "3.1"\n      title: Retrieval quality\n',
            encoding="utf-8",
        )
        intro = "Front matter must remain untouched even when it has many short paragraphs.\n\n" * 8
        (workspace / "sections" / "S1.md").write_text(intro, encoding="utf-8")
        paragraphs = [
            f"Paragraph {index} provides a distinct evidence-backed comparison for retrieval evaluation [@Study{index}]."
            for index in range(1, 9)
        ]
        h3_path = workspace / "sections" / "S3_1.md"
        h3_path.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
        citations_before = re.findall(r"\[@([^\]]+)\]", h3_path.read_text(encoding="utf-8"))

        result = subprocess.run(
            [sys.executable, str(script), "--workspace", str(workspace)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert (workspace / "sections" / "S1.md").read_text(encoding="utf-8") == intro
        curated = h3_path.read_text(encoding="utf-8")
        assert 5 <= len([part for part in re.split(r"\n\s*\n", curated.strip()) if part.strip()]) <= 7
        assert re.findall(r"\[@([^\]]+)\]", curated) == citations_before


def test_paragraph_curator_never_drops_middle_prose_when_over_budget() -> None:
    module = _load_skill_script("paragraph-curator")
    paragraphs = [
        f"Distinct move {index} keeps its full evidence statement [@Study{index}]."
        for index in range(1, 16)
    ]

    curated = module._curate(
        "\n\n".join(paragraphs),
        max_paragraphs=7,
        min_paragraphs=5,
        tail_keep=2,
        min_chars=1600,
    )

    paragraph_count = len([part for part in re.split(r"\n\s*\n", curated.strip()) if part.strip()])
    assert 5 <= paragraph_count <= 7
    for index in range(1, 16):
        assert f"Distinct move {index} " in curated
    assert re.findall(r"\[@([^\]]+)\]", curated) == [f"Study{index}" for index in range(1, 16)]


def test_section_merger_detects_stale_section_fingerprint() -> None:
    module = _load_skill_script("section-merger")
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "sections").mkdir(parents=True)
        section = workspace / "sections" / "S3_1.md"
        section.write_text("Current section content [@StudyA].\n", encoding="utf-8")
        manifest = workspace / "sections" / "sections_manifest.jsonl"
        manifest.write_text(
            json.dumps(
                {
                    "path": "sections/S3_1.md",
                    "bytes": section.stat().st_size,
                    "sha256": hashlib.sha256(section.read_bytes()).hexdigest(),
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert module._stale_manifest_paths(
            workspace,
            "sections/sections_manifest.jsonl",
            ["sections/S3_1.md"],
        ) == []

        section.write_text("Changed after the snapshot [@StudyA].\n", encoding="utf-8")
        assert module._stale_manifest_paths(
            workspace,
            "sections/sections_manifest.jsonl",
            ["sections/S3_1.md"],
        ) == ["sections/S3_1.md"]

        manifest.write_text(
            json.dumps(
                {
                    "path": "sections/S3_1.md",
                    "bytes": "not-a-number",
                    "sha256": hashlib.sha256(section.read_bytes()).hexdigest(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert module._stale_manifest_paths(
            workspace,
            "sections/sections_manifest.jsonl",
            ["sections/S3_1.md"],
        ) == ["sections/S3_1.md"]


def test_post_merge_voice_gate_ignores_uninjected_transition_suggestions() -> None:
    script = REPO_ROOT / ".codex" / "skills" / "post-merge-voice-gate" / "scripts" / "run.py"
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "workspaces") as tmp:
        workspace = Path(tmp)
        (workspace / "output").mkdir(parents=True)
        (workspace / "outline").mkdir(parents=True)
        (workspace / "output" / "DRAFT.md").write_text(
            "# Evaluation\n\n## Results\n\nEvidence remains bounded by the stated protocol.\n",
            encoding="utf-8",
        )
        (workspace / "outline" / "transitions.md").write_text(
            "- 3.1 -> 3.2: To keep the chapter's comparison lens explicit, we now turn to cost.\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(script), "--workspace", str(workspace)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        report = (workspace / "output" / "POST_MERGE_VOICE_REPORT.md").read_text(encoding="utf-8")
        assert "- Status: PASS" in report
        assert "- Transition injection: disabled" in report
