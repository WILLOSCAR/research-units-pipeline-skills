"""Real-skill vertical through the v3 LocalRunEngine.

Every other tests/v3 test drives the engine with in-memory STUB skill adapters
(see tests/v3/support/factories.py). This test closes that gap: it runs the
*real* repository skills for the smallest pipeline (paper-review, 9 CODEX units,
no human checkpoint) end to end through compose_repository_engine, so the same
subprocess seam a user hits is exercised at least once.

Scope note: the v3 engine tracks unit status in .harness-v3/state.json and
projects committed status back into UNITS.csv as the Run advances. UNITS.csv is
recorded as a committed artifact but exempt from the post-Completion drift
comparison (case._MUTABLE_PROJECTION_PATHS), so the projection does not trip the
immutable-output check. Because the artifact-contract-auditor skill reads
UNITS.csv status, the final unit observes the pipeline as complete and the run
reaches COMPLETED. This test drives the real repository skills end to end.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from research_harness._local_runtime import (
    compose_repository_engine,
    initialize_repository_run,
)
from research_harness.engine import AdvanceRun, AdvanceUntil, EngineOutcome


REPO_ROOT = Path(__file__).resolve().parents[2]

# A manuscript rich enough to pass the paper-review semantic acceptance gates:
# an explicit contributions list (claims-extractor), baselines + protocol
# (evidence-auditor), and a `## References` list with `- ` entries so
# novelty-matrix can position claims against unique related works.
_MANUSCRIPT = """# Confidence-Gated Retrieval for Robotic Test-Time Adaptation

## Abstract
We present CQC-RAG, a retrieval-augmented method for test-time adaptation in
robotic manipulation. On four manipulation benchmarks it improves task success
by 6.4 points over the strongest retrieval baseline while halving adaptation
latency. We claim a confidence-gated retrieval policy, a cache-coherent memory,
and an evaluation protocol separating retrieval quality from control quality.

## 1. Introduction
Test-time adaptation lets a deployed policy adjust to distribution shift without
new labels. We argue retrieval, not fine-tuning, is the right adaptation
primitive at deployment.

## 2. Related Work
Retrieval-augmented control has been studied by Salemi et al. and by Lin et al.,
who retrieve demonstrations at inference. Model-based adaptation by Chen
fine-tunes dynamics online. CQC-RAG gates retrieval on calibrated confidence and
never updates weights at test time; the delta over Salemi is the confidence gate
and the cache-coherent memory.

## 3. Method
The confidence-gated retrieval policy triggers a lookup only when calibrated
confidence falls below a threshold. Retrieved trajectories merge through a
cache-coherent memory that deduplicates by content hash.

## 4. Experiments
We evaluate on four manipulation benchmarks. Baselines include Salemi, Lin, and
a no-retrieval controller. We report task success and adaptation latency over
five seeds with 95% confidence intervals.

## 5. Results
CQC-RAG reaches 71.2% success versus 64.8% for the strongest baseline, a 6.4
point gain, while reducing adaptation latency from 180ms to 96ms.

## 6. Limitations
Our evaluation is limited to simulation and four benchmarks; real-robot transfer
and cross-embodiment generalization remain untested.

## 7. Conclusion
Confidence-gated retrieval is an effective test-time adaptation primitive.

## References
- Salemi et al. Retrieval-augmented control for manipulation. 2024.
- Lin et al. Demonstration retrieval at inference time. 2023.
- Chen. Model-based online dynamics adaptation. 2022.
- Kumar et al. Calibrated confidence for policies. 2023.
- Zhao et al. Cache-coherent episodic memory. 2024.
"""


def _copy_repository(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            "workspaces",
            ".scratch",
        ),
    )
    return destination


def test_paper_review_real_skills_run_end_to_end_through_v3_engine(
    tmp_path: Path,
) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="paper-review",
        request="Review the supplied manuscript with real skills",
        run_id="real-skill-vertical",
    )
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "manuscript.md").write_text(
        _MANUSCRIPT, encoding="utf-8"
    )

    engine = compose_repository_engine(workspace=workspace, repo_root=repo_copy)
    result = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))

    # Every real skill up to the final contract auditor executed and committed:
    # the run advanced through all nine units, not just the first.
    assert result.unit_ids == (
        "U001",
        "U002",
        "U005",
        "U010",
        "U020",
        "U025",
        "U030",
        "U035",
        "U040",
    ), result.issues

    # The real semantic artifacts produced by real skills exist on disk.
    for produced in (
        "output/PAPER.md",
        "output/CLAIMS.jsonl",
        "output/EVIDENCE_AUDIT.jsonl",
        "output/NOVELTY_MATRIX.tsv",
        "output/REVIEW.md",
        "output/REVIEW_SCORECARD.json",
    ):
        assert (workspace / produced).exists(), f"missing real artifact {produced}"

    # novelty-matrix positioned claims against the reference list rather than
    # emitting the "related works unavailable" fallback — proving the real skill
    # parsed the manuscript, not a stub.
    novelty = (workspace / "output" / "NOVELTY_MATRIX.tsv").read_text(
        encoding="utf-8"
    )
    assert "related works unavailable" not in novelty

    # The v3 engine projects committed Unit status from its canonical authority
    # back into UNITS.csv as the Run advances, so the final
    # artifact-contract-auditor observes the pipeline as complete and the run
    # reaches COMPLETED.
    inspection = engine.inspect().run
    assert inspection is not None
    status_by_unit = {unit.plan.id: unit.status.value for unit in inspection.units}
    for done_unit in ("U001", "U010", "U025", "U035", "U040"):
        assert status_by_unit[done_unit] == "DONE", status_by_unit

    assert result.outcome is EngineOutcome.COMPLETED, result.issues
