from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "examples" / "course-paper-pilot"
BRIEF_SNAPSHOT = REPO_ROOT / "examples" / "research-brief-harness-proof"
REAL_BRIEF_SNAPSHOT = REPO_ROOT / "examples" / "research-brief-real-source-proof"
RESIDUE_PASS_SNAPSHOT = REPO_ROOT / "examples" / "course-paper-residue-pass"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_course_paper_snapshot_is_complete_and_hash_consistent() -> None:
    summary = json.loads((SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "arxiv-survey-latex"
    assert summary["run_state"] == "COMPLETED"
    assert summary["units"] == {"total": 49, "done": 49, "active": 0}
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["target_artifacts_missing"] == 0
    assert summary["delivery"]["pages"] == 10
    assert summary["writing_provenance"] == {
        "schema": "template-residue-measurement.v1",
        "measurement_scope": "examples/course-paper-pilot/DRAFT.md",
        "measurement_scope_description": "Entire reader-facing draft",
        "template_asset_scope": (
            "Five current candidate writer-template banks; the historical Run did not "
            "retain its optional domain-overlay selection."
        ),
        "template_assets": [
            ".codex/skills/front-matter-writer/assets/front_matter_templates.json",
            ".codex/skills/front-matter-writer/assets/domain_templates/llm_agents.json",
            ".codex/skills/chapter-lead-writer/assets/lead_block_compatibility_defaults.json",
            ".codex/skills/subsection-writer/assets/paragraph_job_templates.json",
            ".codex/skills/subsection-writer/assets/bootstrap_paragraph_templates.json",
        ],
        "template_asset_sha256": {
            ".codex/skills/front-matter-writer/assets/front_matter_templates.json": (
                "f14ff99f69d233ca825dbe2fb41aebbb191c67d387882abde13350631b271f02"
            ),
            ".codex/skills/front-matter-writer/assets/domain_templates/llm_agents.json": (
                "6081aac7bf7cb10734eaf8d4001b3e110a1f4194e4f894777de8cc7bd129f212"
            ),
            ".codex/skills/chapter-lead-writer/assets/lead_block_compatibility_defaults.json": (
                "85ea675a7d1cad3471187cbe71b9aea90a01b4cfe1a56146f0561c79ec370963"
            ),
            ".codex/skills/subsection-writer/assets/paragraph_job_templates.json": (
                "859c546d1b99960e7ab665281f2468fc2d556b5ccc1153e6cd194c8f9070170f"
            ),
            ".codex/skills/subsection-writer/assets/bootstrap_paragraph_templates.json": (
                "0143a81c1d58f6aaf7f725ceb330bd3b1c66c73fa5e008ff7ac75a0d4e7bd1b4"
            ),
        },
        "min_literal_chars": 24,
        "sentence_count": 140,
        "matched_sentence_count": 96,
        "matched_sentence_ratio": 0.685714,
        "scope_breakdown": {
            "h3_early_check": {
                "sentence_count": 90,
                "matched_sentence_count": 49,
                "matched_sentence_ratio": 0.544444,
            },
            "front_matter": {
                "sentence_count": 41,
                "matched_sentence_count": 41,
                "matched_sentence_ratio": 1.0,
            },
        },
        "current_gate_scope": "Entire merged reader-facing draft",
        "current_workflow_limit": 0.1,
        "current_gate_verdict": "FAIL",
        "threshold_validation": "No completed passing Run has yet validated the 10% policy target.",
        "interpretation": (
            "Lower bound on literal deterministic bootstrap-template residue; "
            "not an authorship classifier."
        ),
        "asset_lock_trace": "not retained",
        "actor_revision_trace": "not retained",
    }
    for relpath, digest in summary["writing_provenance"]["template_asset_sha256"].items():
        assert _sha256(REPO_ROOT / relpath) == digest

    for relative_path, metadata in summary["files"].items():
        artifact = SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path

    assert (SNAPSHOT / "paper.pdf").read_bytes().startswith(b"%PDF-")


def test_course_paper_snapshot_exposes_the_completed_unit_plan() -> None:
    with (SNAPSHOT / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 49
    assert {row["status"] for row in rows} == {"DONE"}
    assert rows[0]["skill"] == "workspace-init"
    assert rows[-1]["skill"] == "artifact-contract-auditor"


def test_course_paper_residue_pass_snapshot_is_complete_and_hash_consistent() -> None:
    from tooling.quality_checks.template_residue import measure_template_residue

    summary = json.loads((RESIDUE_PASS_SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))
    scorecard = json.loads(
        (RESIDUE_PASS_SNAPSHOT / "TEMPLATE_RESIDUE_SCORECARD.json").read_text(encoding="utf-8")
    )

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "arxiv-survey-latex"
    assert summary["source_mode"] == "retained_online_arxiv_artifact_revalidation"
    assert summary["run_state"] == "COMPLETED"
    assert summary["completion_protocol"] == "recoverable-provenance.v2"
    assert summary["repository"] == {
        "revision": "8c0cf7ddb71617e66d6583a4438a8f457c99191a",
        "dirty": True,
    }
    assert summary["units"] == {"total": 49, "done": 49, "active": 0}
    assert summary["kernel_lock"] == {
        "verdict": "PASS",
        "locked_files": 35,
        "current_files": 35,
        "matched_files": 35,
        "drifted_files": 0,
    }
    assert summary["workflow_acceptance"]["verdict"] == "PASS"
    assert summary["workflow_acceptance"]["locked_required_checks"] == 31
    assert summary["workflow_acceptance"]["covered_required_checks"] == 31
    assert summary["workflow_acceptance"]["verified_required_units"] == 31
    assert summary["workflow_acceptance"]["done_without_acceptance_evidence"] == 0
    assert summary["attempts"] == {
        "started": 49,
        "finished": 49,
        "open": 0,
        "succeeded": 49,
        "failed_retryable": 0,
        "waiting_human": 0,
        "extra_attempts": 0,
        "retry_units": 0,
        "process_mode": 1,
        "manual_mode": 48,
    }
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["target_artifacts_present"] == 75
    assert summary["artifact_audit"]["target_artifacts_missing"] == 0
    assert summary["artifact_audit"]["ledger_integrity_issues"] == 0
    assert summary["delivery"]["pages"] == 10
    assert summary["delivery"]["page_size"] == "A4"

    provenance = summary["writing_provenance"]
    assert provenance["schema"] == "template-residue-measurement.v1"
    assert provenance["sentence_count"] == 226
    assert provenance["matched_sentence_count"] == 0
    assert provenance["matched_sentence_ratio"] == 0.0
    assert provenance["workflow_limit"] == 0.1
    assert provenance["gate_verdict"] == "PASS"
    assert provenance["asset_selection_verdict"] == "PASS"
    assert provenance["implementation_lock_verdict"] == "PASS"

    assert scorecard["schema"] == "template-residue-scorecard.v1"
    assert scorecard["verdict"] == "PASS"
    assert scorecard["score"] == 100
    assert scorecard["measurement"]["sentence_count"] == 226
    assert scorecard["measurement"]["matched_sentence_count"] == 0
    assert scorecard["measurement"]["matched_sentence_ratio"] == 0.0
    assert scorecard["policy"]["max_ratio"] == 0.1
    assert scorecard["asset_selection"]["status"] == "PASS"
    assert scorecard["implementation_lock"]["status"] == "PASS"

    asset_paths = tuple(REPO_ROOT / relpath for relpath in scorecard["measurement"]["template_assets"])
    measurement = measure_template_residue(
        documents=[("DRAFT.md", (RESIDUE_PASS_SNAPSHOT / "DRAFT.md").read_text(encoding="utf-8"))],
        asset_paths=asset_paths,
        min_literal_chars=scorecard["measurement"]["min_literal_chars"],
    )
    assert measurement["sentence_count"] == 226
    assert measurement["matched_sentence_count"] == 0
    assert measurement["matched_sentence_ratio"] == 0.0

    draft = (RESIDUE_PASS_SNAPSHOT / "DRAFT.md").read_text(encoding="utf-8")
    assert not re.search(
        r"(?i)\b(?:this run|this workspace|quality gate)\b|\bthis\s+(?:pipeline|stage)\b",
        draft,
    )

    for relpath, digest in provenance["template_asset_sha256"].items():
        assert _sha256(REPO_ROOT / relpath) == digest
    for relative_path, metadata in summary["files"].items():
        artifact = RESIDUE_PASS_SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path

    assert (RESIDUE_PASS_SNAPSHOT / "paper.pdf").read_bytes().startswith(b"%PDF-")


def test_course_paper_residue_pass_snapshot_exposes_done_plan_without_private_ids() -> None:
    with (RESIDUE_PASS_SNAPSHOT / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 49
    assert {row["status"] for row in rows} == {"DONE"}
    assert rows[0]["skill"] == "workspace-init"
    assert rows[-1]["skill"] == "artifact-contract-auditor"

    for path in RESIDUE_PASS_SNAPSHOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".csv", ".tex", ".bib"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "/Users/" not in text, path
        assert not re.search(r"\b(?:run|goal|attempt)_[0-9a-f]{8,}\b", text), path


def test_research_brief_harness_proof_is_complete_and_hash_consistent() -> None:
    summary = json.loads((BRIEF_SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "research-brief"
    assert summary["source_mode"] == "deterministic_synthetic_fixture"
    assert summary["run_state"] == "COMPLETED"
    assert summary["completion_protocol"] == "recoverable-provenance.v1"
    assert summary["repository"]["dirty"] is False
    assert len(summary["repository"]["revision"]) == 40
    assert summary["repository"]["locked_kernel_files"] > 0
    assert summary["repository"]["locked_skills"] > 0
    assert summary["units"] == {"total": 11, "done": 11, "active": 0}
    assert summary["attempts"]["succeeded"] == 11
    assert summary["attempts"]["extra_attempts"] == 0
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["target_artifacts_missing"] == 0
    assert summary["artifact_audit"]["ledger_integrity_issues"] == 0
    assert summary["evaluation"]["verdict"] == "PASS"
    assert summary["evaluation"]["score"] == 100
    assert summary["historical_comparison"]["harness_issue_delta"] == -8

    for relative_path, metadata in summary["files"].items():
        artifact = BRIEF_SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path


def test_research_brief_harness_proof_exposes_plan_sources_and_scorecard() -> None:
    with (BRIEF_SNAPSHOT / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (BRIEF_SNAPSHOT / "papers" / "core_set.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        core_papers = list(csv.DictReader(handle))
    scorecard = json.loads((BRIEF_SNAPSHOT / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))

    assert len(rows) == 11
    assert {row["status"] for row in rows} == {"DONE"}
    assert rows[0]["skill"] == "workspace-init"
    assert rows[-1]["skill"] == "artifact-contract-auditor"
    assert len(core_papers) == 12
    assert all(record["url"].startswith("https://example.org/") for record in core_papers)
    assert scorecard["schema"] == "research-brief-scorecard.v1"
    assert scorecard["verdict"] == "PASS"
    assert scorecard["failures"] == []


def test_real_source_research_brief_proof_is_complete_and_hash_consistent() -> None:
    summary = json.loads((REAL_BRIEF_SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "research-brief"
    assert summary["source_mode"] == "online_arxiv_api"
    assert summary["strict_quality_gates"] is True
    assert summary["run_state"] == "COMPLETED"
    assert summary["completion_protocol"] == "recoverable-provenance.v1"
    assert summary["repository"]["dirty"] is False
    assert len(summary["repository"]["revision"]) == 40
    assert summary["units"] == {"total": 11, "done": 11, "active": 0}
    assert summary["attempts"]["succeeded"] == 11
    assert summary["attempts"]["extra_attempts"] == 0
    assert summary["retrieval"] == {
        "provider": "arxiv_api",
        "raw_records": 80,
        "deduplicated_records": 80,
        "core_papers": 12,
        "minimum_records_gate": 15,
    }
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["ledger_integrity_issues"] == 0
    assert summary["evaluation"]["verdict"] == "PASS"
    assert summary["evaluation"]["score"] == 100
    assert summary["evaluation"]["words"] == 539
    assert summary["product_loop"]["required_evidence"] == "complete"
    assert summary["baseline_comparison"]["verdict"] == "PASS"

    for relative_path, metadata in summary["files"].items():
        artifact = REAL_BRIEF_SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path


def test_real_source_research_brief_proof_exposes_arxiv_sources_without_private_run_ids() -> None:
    with (REAL_BRIEF_SNAPSHOT / "papers" / "core_set.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        core_papers = list(csv.DictReader(handle))
    scorecard = json.loads((REAL_BRIEF_SNAPSHOT / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))

    assert len(core_papers) == 12
    assert all("arxiv.org/abs/" in record["url"] for record in core_papers)
    assert all(record["arxiv_id"] for record in core_papers)
    assert scorecard["schema"] == "research-brief-scorecard.v1"
    assert scorecard["verdict"] == "PASS"
    assert scorecard["counts"]["words"] == 539

    for path in REAL_BRIEF_SNAPSHOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "/Users/" not in text, path
        assert not re.search(r"\b(?:run|attempt)_[0-9a-f]{8,}\b", text), path
