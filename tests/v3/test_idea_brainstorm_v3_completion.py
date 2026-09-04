"""Regression: idea-brainstorm completes through the v3 engine via the human C2 flow.

idea-brainstorm's C2 requires an explicit focus-cluster selection recorded in
DECISIONS.md. U042 (checkpoint-brief) rewrites DECISIONS.md to add that focus
block and genuinely reads the existing file, but the UNITS template previously
declared DECISIONS.md only as an OUTPUT of U042, not an INPUT. The v3 engine's
in-place-lineage guard (`_artifact_lineage_is_current`) then treats U042 as a
non-consuming producer, so the C2 focus edit made the earlier idea-brief (U003,
which bound DECISIONS.md at C0) go stale and the run BLOCKED — even though the
legacy scripts/pipeline.py runner completes the same workflow.

Declaring DECISIONS.md as a U042 input (truthful: checkpoint-brief reads+merges
it) restores a valid consuming-producer lineage. This test drives the real
idea-brainstorm workflow through compose_repository_engine on a bounded
deterministic offline corpus and asserts it reaches COMPLETED via the intended
human C2 focus flow (BLOCKED at the C2 staleness before the fix).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from research_harness._local_runtime import (
    compose_repository_engine,
    initialize_repository_run,
)
from research_harness.engine import (
    AdvanceRun,
    AdvanceUntil,
    ApproveLocalCheckpoint,
    EngineOutcome,
)
from tooling.ideation import write_idea_focus_decision

REPO_ROOT = Path(__file__).resolve().parents[2]

_COMMON = (
    "We study LLM agent loops and action spaces for tool interfaces and orchestration, "
    "planning and reasoning, memory and retrieval RAG, self-improvement and adaptation, "
    "multi-agent coordination, benchmark evaluation protocols, and safety security governance. "
    "The controlled evaluation reports a 12% reduction in unsupported citations, while the main "
    "limitation is that retrieval policy, verifier access, and context budget still vary together."
)


def _copy_repository(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", ".pytest_cache", "__pycache__", "workspaces", ".scratch",
        ),
    )
    return destination


def _corpus_jsonl() -> str:
    records = []
    for index in range(1, 19):
        records.append(
            {
                "paper_id": f"P{index:04d}",
                "title": f"Evidence-Grounded LLM Research Agents: Controlled Study {index}",
                "year": 2020 + (index % 6),
                "url": f"https://example.org/agent-evidence-{index}",
                "arxiv_id": f"25{index:02d}.{index:05d}",
                "authors": [f"Author {index}", "Researcher B"],
                "abstract": _COMMON + f" Study {index} isolates one evaluation slice.",
                "source": "fixture",
                "provenance": [{"route": "fixture", "source": "fixture"}],
            }
        )
    return "\n".join(json.dumps(r) for r in records) + "\n"


def _approve(engine, *, workspace: Path) -> None:
    """Approve the pending HUMAN checkpoint; record a real C2 focus first."""
    run = engine.inspect().run
    pending = next(
        u.plan.checkpoint
        for u in run.units
        if u.status.value in {"TODO", "READY", "PENDING"}
        and (u.plan.owner.value == "HUMAN" or u.plan.skill == "human-checkpoint")
    )
    if pending == "C2":
        tax_path = workspace / "outline" / "taxonomy.yml"
        clusters = []
        if tax_path.is_file():
            tax = yaml.safe_load(tax_path.read_text(encoding="utf-8")) or []
            clusters = [
                str(n.get("name")).strip()
                for n in tax
                if isinstance(n, dict) and str(n.get("name") or "").strip()
            ][:2]
        write_idea_focus_decision(
            workspace / "DECISIONS.md", focus_clusters=clusters or ["Core methods"]
        )
    # tick the Approve box in-place, then issue the engine approval
    import re

    decisions = workspace / "DECISIONS.md"
    text = decisions.read_text(encoding="utf-8")
    ticked, n = re.subn(
        rf"(?im)^(\s*-\s*)\[ \](\s*(?:Approve\s+)?{re.escape(pending)}\b.*)$",
        r"\1[x]\2",
        text,
    )
    assert n == 1, f"expected one Approve {pending} box, found {n}"
    decisions.write_text(ticked, encoding="utf-8")
    engine.execute(ApproveLocalCheckpoint(checkpoint=pending))


def test_idea_brainstorm_completes_through_v3_engine_human_c2_flow(tmp_path: Path) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="idea-brainstorm",
        request=(
            "Brainstorm discussion-worthy research directions on evidence-grounded "
            "autonomous literature-review agents."
        ),
        run_id="idea-brainstorm-v3-c2",
    )
    (workspace / "papers").mkdir(parents=True, exist_ok=True)
    (workspace / "papers" / "import.jsonl").write_text(_corpus_jsonl(), encoding="utf-8")

    engine = compose_repository_engine(workspace=workspace, repo_root=repo_copy)
    outcome = None
    for _ in range(96):
        result = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))
        outcome = result.outcome
        if outcome is EngineOutcome.COMPLETED:
            break
        if outcome is EngineOutcome.WAITING_FOR_CHECKPOINT:
            _approve(engine, workspace=workspace)
            continue
        # Any BLOCKED/SKILL_FAILED (including the pre-fix C2 staleness) fails here.
        raise AssertionError(f"idea-brainstorm did not complete on v3: {outcome} :: {result.issues}")
    assert outcome is EngineOutcome.COMPLETED
    # The reader-facing memo exists and the focus lineage held.
    assert (workspace / "output" / "REPORT.md").is_file()
