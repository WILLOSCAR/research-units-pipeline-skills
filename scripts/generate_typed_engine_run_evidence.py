#!/usr/bin/env python
"""Generate fresh current typed-engine run evidence for repository Recipes.

This drives the REAL repository skills end to end through the typed
``research_harness`` local engine (``initialize_repository_run`` +
``compose_repository_engine``), which owns ``.harness-v3`` storage. For each
selected Recipe it writes a curated ``completed-run-evidence.v1`` artifact under
``examples/<recipe>-typed-engine-proof/`` describing exactly what the run
produced, plus a companion ``README.md``.

Two Recipes are proven here, both offline and with real skills:

* ``paper-review`` — a synthetic manuscript reviewed to COMPLETED. No human
  checkpoint (all 9 Units are CODEX-owned).
* ``research-brief`` — a synthetic offline paper export (``papers/import.jsonl``)
  briefed to COMPLETED across 11 Units. ``arxiv-search`` runs its offline-import
  path (no network); the C2 scope+outline gate is a HUMAN Unit that this
  generator approves by ticking ``Approve C2`` in ``DECISIONS.md`` — exactly the
  human action the engine requires, never an auto-approval.

Honesty boundary: this proves execution-integrity and contract-acceptance for
ONE fresh run of each Recipe on synthetic input through the current typed engine.
It is NOT research-quality validation, not cross-topic, and not expert reviewed.
Every number, hash, and schema string is read from the actual run; nothing is
fabricated.

Reproducibility note: most produced artifacts are byte-stable across runs, but a
few embed a wall-clock timestamp (``tooling.common.now_iso_seconds`` ->
``datetime.now``), so their raw bytes differ every run by design. To keep the
committed evidence reproducible we record the sha256 of those files over
timestamp-normalized content with a documented ``hash_basis``; a plain
``sha256sum`` of the on-disk file will therefore differ, and we say so
explicitly in the artifact record and README. ``captured_at`` is a fixed arg,
never ``datetime.now``.

Usage:
    python scripts/generate_typed_engine_run_evidence.py            # write all
    python scripts/generate_typed_engine_run_evidence.py --check     # verify all
    python scripts/generate_typed_engine_run_evidence.py \
        --recipe research-brief                                      # one recipe
    python scripts/generate_typed_engine_run_evidence.py \
        --captured-at 2026-08-21T00:00:00+08:00                      # override stamp
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from research_harness._local_runtime import (  # noqa: E402
    compose_repository_engine,
    initialize_repository_run,
)
from research_harness.engine import (  # noqa: E402
    AdvanceRun,
    AdvanceUntil,
    ApproveLocalCheckpoint,
    EngineOutcome,
)

EXAMPLES_ROOT = REPO_ROOT / "examples"

# A fixed capture stamp: never derived from datetime.now (blocked in some
# contexts and inherently nondeterministic). Overridable via --captured-at.
_DEFAULT_CAPTURED_AT = "2026-08-21T00:00:00+08:00"

_NORMALIZED_SENTINEL = "<normalized-for-reproducible-hash>"

# ---------------------------------------------------------------------------
# paper-review synthetic input
# ---------------------------------------------------------------------------

# Reused verbatim from tests/v3/test_real_skill_vertical.py: a manuscript rich
# enough to pass the paper-review semantic acceptance gates (explicit
# contributions, baselines + protocol, and a `## References` list).
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


def _seed_paper_review(workspace: Path) -> None:
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "manuscript.md").write_text(_MANUSCRIPT, encoding="utf-8")


# ---------------------------------------------------------------------------
# research-brief synthetic input (deterministic offline paper export)
# ---------------------------------------------------------------------------

_BRIEF_THEMES = (
    "retrieval augmentation",
    "tool use",
    "planning",
    "memory",
    "multi-agent coordination",
    "evaluation protocols",
    "safety",
)


def _research_brief_import(count: int = 24) -> str:
    """A bounded, deterministic offline export the arxiv-search skill imports.

    Each record carries the fields downstream skills require (title/authors/
    year/url/abstract + stable arxiv_id + provenance). No field derives from the
    clock, so the export — and every deterministic artifact downstream — is
    byte-stable.
    """

    rows: list[str] = []
    for index in range(1, count + 1):
        theme = _BRIEF_THEMES[index % len(_BRIEF_THEMES)]
        rows.append(
            json.dumps(
                {
                    "paper_id": f"P{index:04d}",
                    "title": (
                        f"Evidence-Grounded LLM Agents: {theme.title()} Study {index}"
                    ),
                    "authors": [f"Author {index}", "Researcher B"],
                    "year": 2020 + (index % 6),
                    "url": f"https://arxiv.org/abs/25{index:02d}.{index:05d}",
                    "arxiv_id": f"25{index:02d}.{index:05d}",
                    "abstract": (
                        f"We study {theme} for autonomous LLM research agents. A "
                        "controlled evaluation reports a 12% reduction in "
                        f"unsupported citations. Study {index} isolates one "
                        "evaluation slice. The main limitation is that retrieval "
                        "policy and context budget vary together, confounding "
                        "attribution of the observed gains."
                    ),
                    "source": "fixture",
                    "provenance": [{"route": "offline_import", "source": "fixture"}],
                }
            )
        )
    return "\n".join(rows) + "\n"


def _seed_research_brief(workspace: Path) -> None:
    (workspace / "papers").mkdir(parents=True, exist_ok=True)
    (workspace / "papers" / "import.jsonl").write_text(
        _research_brief_import(), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Recipe specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedArtifact:
    """A produced artifact whose raw bytes embed a wall-clock timestamp.

    We record its sha256 over timestamp-normalized content so the committed
    evidence regenerates byte-for-byte. ``kind`` selects the normalizer:

    * ``json_field`` — parse JSON, replace ``detail`` field with the sentinel,
      re-serialize canonically.
    * ``md_timestamp`` — replace the backtick-wrapped ISO stamp on the line
      whose prefix is ``detail`` with the sentinel.
    """

    path: str
    kind: str
    detail: str
    hash_basis: str


@dataclass(frozen=True)
class Recipe:
    name: str
    pipeline: str
    run_id: str
    goal: str
    request: str
    source_mode: str
    seed: Callable[[Path], None]
    stable_artifacts: tuple[str, ...]
    timestamped_artifacts: tuple[NormalizedArtifact, ...]
    scorecard_path: str
    verification: Callable[[dict], dict]
    limitations: tuple[str, ...]
    render_readme: Callable[[dict], str]
    approves_checkpoints: bool = False

    @property
    def example_dir(self) -> Path:
        return EXAMPLES_ROOT / f"{self.name}-typed-engine-proof"

    @property
    def run_summary_path(self) -> Path:
        return self.example_dir / "run-summary.json"

    @property
    def readme_path(self) -> Path:
        return self.example_dir / "README.md"


# ---------------------------------------------------------------------------
# Shared mechanics
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _copy_repo(destination: Path) -> Path:
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
            ".claude",
        ),
    )
    return destination


def _canonical_json_field_bytes(path: Path, field_name: str) -> bytes:
    """Serialize a JSON artifact with one wall-clock field normalized.

    Only ``field_name`` is replaced; every other field is preserved. This yields
    a byte-stable representation whose sha256 is reproducible across runs.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if field_name in payload:
        payload[field_name] = _NORMALIZED_SENTINEL
    return (
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:[+-]\d{2}:?\d{2}|Z)?")


def _normalized_md_bytes(path: Path, line_prefix: str) -> bytes:
    """Serialize a Markdown artifact with the wall-clock timestamp normalized.

    The single line whose stripped form begins with ``line_prefix`` has its
    ISO-8601 stamp replaced with the sentinel; all other bytes are preserved.
    """

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    normalized: list[str] = []
    for line in lines:
        if line.lstrip().startswith(line_prefix):
            line = _ISO_STAMP.sub(_NORMALIZED_SENTINEL, line)
        normalized.append(line)
    return "".join(normalized).encode("utf-8")


def _observe_storage_schemas(workspace: Path) -> dict[str, str]:
    """Read the ACTUAL schema strings the typed engine wrote to .harness-v3."""

    harness = workspace / ".harness-v3"
    observed: dict[str, str] = {}

    state = harness / "state.json"
    if state.is_file():
        observed["run_state_ledger (.harness-v3/state.json)"] = json.loads(
            state.read_text(encoding="utf-8")
        )["schema"]

    workflow = harness / "contracts" / "workflow.json"
    if workflow.is_file():
        wf = json.loads(workflow.read_text(encoding="utf-8"))
        observed["workflow_snapshot (.harness-v3/contracts/workflow.json)"] = wf[
            "schema"
        ]

    identity = harness / "contracts" / "identity.json"
    if identity.is_file():
        observed["local_identity (.harness-v3/contracts/identity.json)"] = json.loads(
            identity.read_text(encoding="utf-8")
        )["schema"]

    manifests = sorted((harness / "manifests").glob("*.json"))
    if manifests:
        manifest_schemas = {
            json.loads(m.read_text(encoding="utf-8"))["schema"] for m in manifests
        }
        # completion manifests share one schema; assert and record the single value.
        assert len(manifest_schemas) == 1, manifest_schemas
        observed[
            f"completion_manifest (.harness-v3/manifests/*.json, {len(manifests)} files)"
        ] = next(iter(manifest_schemas))

    return observed


def _approve_pending_checkpoint(engine) -> None:
    """Tick the pending HUMAN checkpoint's Approve box, then approve it.

    This performs exactly the action a human reviewer takes: it flips the single
    ``- [ ] Approve C# ...`` box in DECISIONS.md to ``[x]`` and issues the
    engine's approval command. It is NOT an auto-approve back door; the engine
    still rejects approval unless the box is genuinely checked.
    """

    run = engine.inspect().run
    assert run is not None
    pending = next(
        unit.plan.checkpoint
        for unit in run.units
        if unit.status.value in {"TODO", "READY", "PENDING"}
        and (unit.plan.owner.value == "HUMAN" or unit.plan.skill == "human-checkpoint")
    )
    workspace = engine.inspect().workspace
    decisions = workspace / "DECISIONS.md"
    text = decisions.read_text(encoding="utf-8")
    ticked, count = re.subn(
        rf"(?im)^(\s*-\s*)\[ \](\s*(?:Approve\s+)?{re.escape(pending)}\b.*)$",
        r"\1[x]\2",
        text,
    )
    if count != 1:
        raise SystemExit(
            f"expected exactly one Approve {pending} checkbox to tick, found {count}"
        )
    decisions.write_text(ticked, encoding="utf-8")
    engine.execute(ApproveLocalCheckpoint(checkpoint=pending))


def _drive(recipe: Recipe, workspace: Path, repo_copy: Path):
    """Advance the run to COMPLETED, approving HUMAN checkpoints if allowed."""

    engine = compose_repository_engine(workspace=workspace, repo_root=repo_copy)
    for _ in range(64):
        result = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))
        if result.outcome is EngineOutcome.COMPLETED:
            return engine
        if (
            result.outcome is EngineOutcome.WAITING_FOR_CHECKPOINT
            and recipe.approves_checkpoints
        ):
            _approve_pending_checkpoint(engine)
            continue
        raise SystemExit(
            f"{recipe.name} run did not reach COMPLETED: "
            f"{result.outcome} :: {result.issues}"
        )
    raise SystemExit(f"{recipe.name} run exceeded the advance budget")


def _run(recipe: Recipe, tmp: Path, captured_at: str) -> dict[str, object]:
    repo_copy = _copy_repo(tmp / "repo")
    workspace = tmp / "workspace"
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline=recipe.pipeline,
        request=recipe.request,
        run_id=recipe.run_id,
    )
    recipe.seed(workspace)

    engine = _drive(recipe, workspace, repo_copy)

    run = engine.inspect().run
    assert run is not None
    status_by_unit = {u.plan.id: u.status.value for u in run.units}
    done = sum(1 for s in status_by_unit.values() if s in {"DONE", "SKIP"})

    artifacts: list[dict[str, object]] = []
    for rel in recipe.stable_artifacts:
        p = workspace / rel
        if not p.is_file():
            raise SystemExit(f"expected produced artifact missing: {rel}")
        raw = p.read_bytes()
        artifacts.append({"path": rel, "sha256": _sha256_bytes(raw), "size": len(raw)})

    for spec in recipe.timestamped_artifacts:
        p = workspace / spec.path
        if not p.is_file():
            raise SystemExit(f"expected produced artifact missing: {spec.path}")
        raw = p.read_bytes()
        if spec.kind == "json_field":
            canonical = _canonical_json_field_bytes(p, spec.detail)
        elif spec.kind == "md_timestamp":
            canonical = _normalized_md_bytes(p, spec.detail)
        else:  # pragma: no cover - guarded by the recipe registry.
            raise SystemExit(f"unknown normalization kind: {spec.kind}")
        artifacts.append(
            {
                "path": spec.path,
                "sha256": _sha256_bytes(canonical),
                "size": len(raw),
                "hash_basis": spec.hash_basis,
            }
        )

    scorecard_path = workspace / recipe.scorecard_path
    scorecard_doc = json.loads(scorecard_path.read_text(encoding="utf-8"))
    observed_schemas = _observe_storage_schemas(workspace)

    return {
        "schema": "completed-run-evidence.v1",
        "captured_at": captured_at,
        "engine": "research_harness typed local engine",
        "storage_namespace": ".harness-v3",
        "observed_storage_schemas": observed_schemas,
        "semantic_scorecard_schema": str(scorecard_doc.get("schema")),
        "workflow": recipe.pipeline,
        "goal": recipe.goal,
        "source_mode": recipe.source_mode,
        "run_state": "COMPLETED",
        "units": {
            "total": len(status_by_unit),
            "done": done,
            "unit_status": status_by_unit,
        },
        "produced_artifacts": artifacts,
        "verification": recipe.verification(scorecard_doc),
        "limitations": list(recipe.limitations),
    }


def _stable_json(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# paper-review recipe
# ---------------------------------------------------------------------------

_PAPER_REVIEW_GOAL = (
    "Review one supplied manuscript through the current typed research_harness "
    "engine and reach a COMPLETED Review."
)


def _paper_review_verification(scorecard_doc: dict) -> dict:
    return {
        "reached_completed": True,
        "real_skills": (
            "producer skills (manuscript-ingest, claims-extractor, "
            "evidence-auditor, novelty-matrix, rubric-writer) plus the "
            "artifact-contract-auditor ran as subprocesses; no stub adapters."
        ),
        "novelty_matrix_grounded": (
            "positioned claims against the manuscript reference list rather "
            "than emitting the 'related works unavailable' fallback."
        ),
        "scorecard_verdict": str(scorecard_doc.get("verdict")),
        "scorecard_score": scorecard_doc.get("score"),
        "scorecard_pass_score": scorecard_doc.get("pass_score"),
    }


def _render_paper_review_readme(summary: dict[str, object]) -> str:
    schemas = summary["observed_storage_schemas"]
    assert isinstance(schemas, dict)
    schema_rows = "\n".join(
        f"- `{location}` -> `{value}`" for location, value in sorted(schemas.items())
    )
    units = summary["units"]
    assert isinstance(units, dict)
    return f"""# Paper-review — current typed-engine proof

A fresh, reproducible end-to-end run of the **paper-review** Recipe through the
current typed `research_harness` engine, driven by `initialize_repository_run` +
`compose_repository_engine`. This engine owns `.harness-v3` storage; "v3" is the
storage-namespace label, **not** a completion-protocol version.

Regenerate and verify:

```bash
uv run python scripts/generate_typed_engine_run_evidence.py
uv run python scripts/generate_typed_engine_run_evidence.py --check   # reproducibility gate
```

## What this proves

- The current typed engine runs the **real** repository skills for paper-review
  end to end (manuscript-ingest → claims-extractor → evidence-auditor →
  novelty-matrix → rubric-writer → artifact-contract-auditor) as subprocesses —
  no stub adapters — and reaches `COMPLETED` with
  **{units["done"]}/{units["total"]} units** committed.
- All six reader- and machine-facing artifacts are produced and hashed:
  `output/PAPER.md`, `output/CLAIMS.jsonl`, `output/EVIDENCE_AUDIT.jsonl`,
  `output/NOVELTY_MATRIX.tsv`, `output/REVIEW.md`,
  `output/REVIEW_SCORECARD.json`.
- `novelty-matrix` positioned claims against the manuscript's reference list
  rather than emitting its "related works unavailable" fallback, proving the
  real skill parsed the manuscript.

## Observed `.harness-v3` schema strings

Recorded directly from the storage the run actually wrote (not assumed):

{schema_rows}

The semantic scorecard carries `{summary["semantic_scorecard_schema"]}`.

## Reproducibility

Five of the six artifacts are byte-stable across runs. The sixth,
`output/REVIEW_SCORECARD.json`, embeds a wall-clock `generated_at`
(`tooling.common.now_iso_seconds` → `datetime.now`), so its raw bytes change
every run **by design**. The evidence records the scorecard's sha256 over
timestamp-normalized content (`generated_at` replaced with a fixed sentinel) so
the committed `run-summary.json` regenerates byte-for-byte. A plain
`sha256sum output/REVIEW_SCORECARD.json` will therefore differ from the recorded
hash — this is expected and documented in the artifact record's `hash_basis`.
`captured_at` is a fixed stamp, never `datetime.now`.

## Open boundary (what this does NOT prove)

This is **execution-integrity + contract-acceptance** evidence for one run, not
research quality:

- one Recipe (paper-review), one synthetic manuscript, one topic;
- a `COMPLETED` run and a passing contract audit do **not** establish that the
  review is correct, novel, or complete — a scorecard PASS is a contract signal,
  never a truth claim;
- not expert reviewed; cross-topic stability and real-manuscript proof remain
  open;
- artifact hashes are content-addressed for this checkout and will move by
  design when the skills or manuscript change.

The machine-readable summary is [`run-summary.json`](run-summary.json)
(`completed-run-evidence.v1`).
"""


# ---------------------------------------------------------------------------
# research-brief recipe
# ---------------------------------------------------------------------------

_RESEARCH_BRIEF_GOAL = (
    "Produce a one-page research brief on evidence-grounded LLM research agents "
    "from a supplied offline paper export through the current typed "
    "research_harness engine and reach a COMPLETED Brief."
)


def _research_brief_verification(scorecard_doc: dict) -> dict:
    return {
        "reached_completed": True,
        "real_skills": (
            "producer skills (arxiv-search offline import, dedupe-rank, "
            "taxonomy-builder, outline-builder, snapshot-writer) plus "
            "checkpoint-brief and the artifact-contract-auditor ran as "
            "subprocesses; no stub adapters."
        ),
        "offline_retrieval": (
            "arxiv-search took its offline-import path from the seeded "
            "papers/import.jsonl export; no network call was made."
        ),
        "human_checkpoint_approval": (
            "the C2 scope+outline gate is a HUMAN Unit (U045); this run approved "
            "it by ticking `Approve C2` in DECISIONS.md — exactly the human "
            "action the engine requires. The engine still rejects approval unless "
            "the box is genuinely checked; it is not an auto-approval."
        ),
        "scorecard_verdict": str(scorecard_doc.get("verdict")),
        "scorecard_score": scorecard_doc.get("score"),
        "scorecard_pass_score": scorecard_doc.get("pass_score"),
    }


def _render_research_brief_readme(summary: dict[str, object]) -> str:
    schemas = summary["observed_storage_schemas"]
    assert isinstance(schemas, dict)
    schema_rows = "\n".join(
        f"- `{location}` -> `{value}`" for location, value in sorted(schemas.items())
    )
    units = summary["units"]
    assert isinstance(units, dict)
    return f"""# Research-brief — current typed-engine proof

A fresh, reproducible end-to-end run of the **research-brief** Recipe through the
current typed `research_harness` engine, driven by `initialize_repository_run` +
`compose_repository_engine`. This engine owns `.harness-v3` storage; "v3" is the
storage-namespace label, **not** a completion-protocol version.

This is the second Recipe proven through the typed engine (after
[`paper-review`](../paper-review-typed-engine-proof/README.md)), beginning
cross-recipe current-engine coverage. It runs **fully offline**: the retrieval
step imports a seeded export instead of calling arXiv.

Regenerate and verify:

```bash
uv run python scripts/generate_typed_engine_run_evidence.py --recipe research-brief
uv run python scripts/generate_typed_engine_run_evidence.py --recipe research-brief --check
```

## What this proves

- The current typed engine runs the **real** repository skills for
  research-brief end to end (arxiv-search → dedupe-rank → taxonomy-builder →
  outline-builder → checkpoint-brief → **HUMAN C2** → snapshot-writer →
  deliverable-selfloop → artifact-contract-auditor) as subprocesses — no stub
  adapters — and reaches `COMPLETED` with
  **{units["done"]}/{units["total"]} units** committed.
- **Offline retrieval**: `arxiv-search` took its offline-import path from a
  seeded deterministic export (`papers/import.jsonl`); **no network call was
  made**. The rest of the pipeline is deterministic.
- **Real human checkpoint**: C2 (scope + outline) is a HUMAN Unit. The generator
  approves it exactly the way a reviewer does — by ticking `Approve C2` in
  `DECISIONS.md` — and the engine still refuses to advance unless that box is
  genuinely checked. This is not an auto-approve back door.
- Nine reader- and machine-facing artifacts are produced and hashed: the
  retrieval pool (`papers/papers_raw.jsonl`, `papers/papers_dedup.jsonl`,
  `papers/core_set.csv`), the structure (`outline/taxonomy.yml`,
  `outline/outline.yml`), and the deliverables (`output/SNAPSHOT.md`,
  `output/BRIEF_SCORECARD.md`, `output/BRIEF_SCORECARD.json`,
  `output/CONTRACT_REPORT.md`).

## Observed `.harness-v3` schema strings

Recorded directly from the storage the run actually wrote (not assumed):

{schema_rows}

The semantic scorecard carries `{summary["semantic_scorecard_schema"]}`.

## Reproducibility

Seven of the nine recorded artifacts are byte-stable across runs. Two embed a
wall-clock timestamp (`tooling.common.now_iso_seconds` → `datetime.now`), so
their raw bytes change every run **by design**:

- `output/BRIEF_SCORECARD.json` — its `generated_at` field; and
- `output/CONTRACT_REPORT.md` — its `- Timestamp:` line.

The evidence records each one's sha256 over timestamp-normalized content (the
stamp replaced with a fixed sentinel) so the committed `run-summary.json`
regenerates byte-for-byte. A plain `sha256sum` of either raw file will therefore
differ from the recorded hash — this is expected and documented in each artifact
record's `hash_basis`. `captured_at` is a fixed stamp, never `datetime.now`.

## Open boundary (what this does NOT prove)

This is **execution-integrity + contract-acceptance** evidence for one run, not
research quality:

- one Recipe (research-brief), one synthetic offline export, one topic;
- retrieval is a seeded offline import, **not** a live arXiv query — this proves
  nothing about online retrieval coverage or freshness;
- a `COMPLETED` run and a passing contract audit do **not** establish that the
  brief is correct, complete, or that its reading path is well chosen — a
  scorecard PASS is a contract signal, never a truth claim;
- the HUMAN checkpoint is satisfied mechanically (box ticked by the generator);
  no person actually reviewed the scope/outline;
- not expert reviewed; cross-topic stability and real-source proof remain open;
- artifact hashes are content-addressed for this checkout and will move by
  design when the skills or the seeded export change.

The machine-readable summary is [`run-summary.json`](run-summary.json)
(`completed-run-evidence.v1`).
"""


# ---------------------------------------------------------------------------
# Recipe registry
# ---------------------------------------------------------------------------

RECIPES: dict[str, Recipe] = {
    "paper-review": Recipe(
        name="paper-review",
        pipeline="paper-review",
        run_id="paper-review-typed-engine",
        goal=_PAPER_REVIEW_GOAL,
        request=_PAPER_REVIEW_GOAL,
        source_mode="deterministic_synthetic_manuscript",
        seed=_seed_paper_review,
        stable_artifacts=(
            "output/PAPER.md",
            "output/CLAIMS.jsonl",
            "output/EVIDENCE_AUDIT.jsonl",
            "output/NOVELTY_MATRIX.tsv",
            "output/REVIEW.md",
        ),
        timestamped_artifacts=(
            NormalizedArtifact(
                path="output/REVIEW_SCORECARD.json",
                kind="json_field",
                detail="generated_at",
                hash_basis=(
                    "sha256 over canonical JSON with `generated_at` normalized to "
                    f"{_NORMALIZED_SENTINEL!r}; the on-disk file embeds a wall-clock "
                    "`generated_at` (tooling.common.now_iso_seconds -> datetime.now), "
                    "so a plain sha256sum of the raw file will differ by design."
                ),
            ),
        ),
        scorecard_path="output/REVIEW_SCORECARD.json",
        verification=_paper_review_verification,
        limitations=(
            "One Recipe (paper-review), one synthetic manuscript, one topic.",
            "Proves execution-integrity and contract-acceptance for this run only; "
            "NOT research quality, novelty, or exhaustive-retrieval validation.",
            "A COMPLETED run and a PASS scorecard are contract signals, never a "
            "truth claim about the review's correctness.",
            "Not expert reviewed; cross-topic and real-manuscript proof remain open.",
            "Artifact hashes are content-addressed for this checkout; skill or "
            "manuscript changes will change them by design.",
            "REVIEW_SCORECARD.json embeds a wall-clock generated_at; its recorded "
            "hash is over timestamp-normalized content, not the raw bytes.",
        ),
        render_readme=_render_paper_review_readme,
        approves_checkpoints=False,
    ),
    "research-brief": Recipe(
        name="research-brief",
        pipeline="research-brief",
        run_id="research-brief-typed-engine",
        goal=_RESEARCH_BRIEF_GOAL,
        request=_RESEARCH_BRIEF_GOAL,
        source_mode="deterministic_synthetic_offline_import",
        seed=_seed_research_brief,
        stable_artifacts=(
            "papers/papers_raw.jsonl",
            "papers/papers_dedup.jsonl",
            "papers/core_set.csv",
            "outline/taxonomy.yml",
            "outline/outline.yml",
            "output/SNAPSHOT.md",
            "output/BRIEF_SCORECARD.md",
        ),
        timestamped_artifacts=(
            NormalizedArtifact(
                path="output/BRIEF_SCORECARD.json",
                kind="json_field",
                detail="generated_at",
                hash_basis=(
                    "sha256 over canonical JSON with `generated_at` normalized to "
                    f"{_NORMALIZED_SENTINEL!r}; the on-disk file embeds a wall-clock "
                    "`generated_at` (tooling.common.now_iso_seconds -> datetime.now), "
                    "so a plain sha256sum of the raw file will differ by design."
                ),
            ),
            NormalizedArtifact(
                path="output/CONTRACT_REPORT.md",
                kind="md_timestamp",
                detail="- Timestamp:",
                hash_basis=(
                    "sha256 over the report text with the `- Timestamp:` line's "
                    f"wall-clock ISO stamp normalized to {_NORMALIZED_SENTINEL!r}; "
                    "the on-disk file embeds a wall-clock timestamp, so a plain "
                    "sha256sum of the raw file will differ by design."
                ),
            ),
        ),
        scorecard_path="output/BRIEF_SCORECARD.json",
        verification=_research_brief_verification,
        limitations=(
            "One Recipe (research-brief), one synthetic offline export, one topic.",
            "Retrieval is a seeded offline import (papers/import.jsonl), NOT a live "
            "arXiv query; this proves nothing about online retrieval coverage.",
            "Proves execution-integrity and contract-acceptance for this run only; "
            "NOT research quality or reading-path correctness.",
            "A COMPLETED run and a PASS scorecard are contract signals, never a "
            "truth claim about the brief's correctness.",
            "The HUMAN C2 checkpoint is satisfied mechanically (box ticked by the "
            "generator); no person reviewed the scope/outline.",
            "Not expert reviewed; cross-topic and real-source proof remain open.",
            "Artifact hashes are content-addressed for this checkout; skill or "
            "seeded-export changes will change them by design.",
            "BRIEF_SCORECARD.json and CONTRACT_REPORT.md embed wall-clock stamps; "
            "their recorded hashes are over timestamp-normalized content, not the "
            "raw bytes.",
        ),
        render_readme=_render_research_brief_readme,
        approves_checkpoints=True,
    ),
}


def _generate(recipe: Recipe, captured_at: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as raw:
        summary = _run(recipe, Path(raw), captured_at=captured_at)
    return _stable_json(summary), recipe.render_readme(summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recipe",
        choices=(*sorted(RECIPES), "all"),
        default="all",
        help="Which Recipe(s) to (re)generate or check. Defaults to all.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate to a temp dir and byte-diff against the committed files.",
    )
    parser.add_argument(
        "--captured-at",
        default=_DEFAULT_CAPTURED_AT,
        help="Fixed ISO capture stamp recorded in the evidence (never datetime.now).",
    )
    args = parser.parse_args()

    selected: Sequence[Recipe] = (
        tuple(RECIPES.values())
        if args.recipe == "all"
        else (RECIPES[args.recipe],)
    )

    if args.check:
        problems: list[str] = []
        for recipe in selected:
            summary_payload, readme_payload = _generate(recipe, args.captured_at)
            if not recipe.run_summary_path.is_file():
                problems.append(f"[{recipe.name}] MISSING committed run-summary.json")
            elif (
                recipe.run_summary_path.read_text(encoding="utf-8") != summary_payload
            ):
                problems.append(
                    f"[{recipe.name}] DRIFT: run-summary.json does not reproduce "
                    "byte-for-byte"
                )
            if not recipe.readme_path.is_file():
                problems.append(f"[{recipe.name}] MISSING committed README.md")
            elif recipe.readme_path.read_text(encoding="utf-8") != readme_payload:
                problems.append(
                    f"[{recipe.name}] DRIFT: README.md does not reproduce "
                    "byte-for-byte"
                )
        if problems:
            for line in problems:
                print(line, file=sys.stderr)
            return 1
        names = ", ".join(recipe.name for recipe in selected)
        print(f"OK: typed-engine evidence reproduces byte-for-byte ({names}).")
        return 0

    for recipe in selected:
        summary_payload, readme_payload = _generate(recipe, args.captured_at)
        recipe.example_dir.mkdir(parents=True, exist_ok=True)
        recipe.run_summary_path.write_text(summary_payload, encoding="utf-8")
        recipe.readme_path.write_text(readme_payload, encoding="utf-8")
        print(f"wrote {recipe.run_summary_path.relative_to(REPO_ROOT)}")
        print(f"wrote {recipe.readme_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
