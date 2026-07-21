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
    survey_citation_policy,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_skill_script(skill_name: str):
    script = REPO_ROOT / ".codex" / "skills" / skill_name / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location(f"{skill_name.replace('-', '_')}_run", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
                ],
            }
        },
        cite_keys=["Authority2026"],
    )
    bullets = [str(row.get("bullet") or "") for row in rows]
    assert genuine_limit in bullets
    assert named_challenge not in bullets
    assert positive_cost not in bullets
    assert lower_cost not in bullets
    assert recommendation not in bullets
    assert module._sanitize_source_text(
        "Existing metrics are unable to distinguish retrieval,reasoning, or grounding failures."
    ) == "Existing metrics are unable to distinguish retrieval, reasoning, or grounding failures."


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
