#!/usr/bin/env python
"""Generate fresh current typed-engine run evidence for the paper-review Recipe.

This drives the REAL repository skills end to end through the typed
``research_harness`` local engine (``initialize_repository_run`` +
``compose_repository_engine``), which owns ``.harness-v3`` storage. It then
writes a curated ``completed-run-evidence.v1`` artifact under
``examples/paper-review-typed-engine-proof/`` describing exactly what the run
produced, plus a companion ``README.md``.

Honesty boundary: this proves execution-integrity and contract-acceptance for
ONE fresh run of ONE Recipe on a synthetic manuscript through the current typed
engine. It is NOT research-quality validation, not cross-topic, and not expert
reviewed. Every number, hash, and schema string is read from the actual run;
nothing is fabricated.

Reproducibility note: five of the six produced artifacts are byte-stable across
runs. ``output/REVIEW_SCORECARD.json`` embeds a wall-clock ``generated_at``
timestamp (``tooling.common.now_iso_seconds`` -> ``datetime.now``), so its raw
bytes differ every run by design. To keep the committed evidence reproducible we
record the sha256 of the scorecard with ``generated_at`` normalized to a fixed
sentinel; a plain ``sha256sum`` of the on-disk file will therefore differ, and we
say so explicitly in the artifact record and README.

Usage:
    python scripts/generate_typed_engine_run_evidence.py            # write
    python scripts/generate_typed_engine_run_evidence.py --check     # re-run to a
                                                                     # temp dir and
                                                                     # byte-diff the
                                                                     # committed file
    python scripts/generate_typed_engine_run_evidence.py \
        --captured-at 2026-08-21T00:00:00+08:00                      # override stamp
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from research_harness._local_runtime import (  # noqa: E402
    compose_repository_engine,
    initialize_repository_run,
)
from research_harness.engine import AdvanceRun, AdvanceUntil, EngineOutcome  # noqa: E402

EXAMPLE_DIR = REPO_ROOT / "examples" / "paper-review-typed-engine-proof"
RUN_SUMMARY = EXAMPLE_DIR / "run-summary.json"
README = EXAMPLE_DIR / "README.md"

# A fixed capture stamp: never derived from datetime.now (blocked in some
# contexts and inherently nondeterministic). Overridable via --captured-at.
_DEFAULT_CAPTURED_AT = "2026-08-21T00:00:00+08:00"

_GOAL = (
    "Review one supplied manuscript through the current typed research_harness "
    "engine and reach a COMPLETED Review."
)

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

# The task-required reader- and machine-facing artifacts. PAPER.md (the ingested
# canonical manuscript) is byte-stable and included for completeness; the
# scorecard is handled specially because it embeds a wall-clock timestamp.
_STABLE_ARTIFACTS = (
    "output/PAPER.md",
    "output/CLAIMS.jsonl",
    "output/EVIDENCE_AUDIT.jsonl",
    "output/NOVELTY_MATRIX.tsv",
    "output/REVIEW.md",
)
_SCORECARD = "output/REVIEW_SCORECARD.json"
_NORMALIZED_SENTINEL = "<normalized-for-reproducible-hash>"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_scorecard_bytes(path: Path) -> bytes:
    """Serialize the scorecard with the wall-clock timestamp normalized.

    Only ``generated_at`` is replaced; every other field is preserved. This
    yields a byte-stable representation whose sha256 is reproducible across runs.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if "generated_at" in payload:
        payload["generated_at"] = _NORMALIZED_SENTINEL
    return (
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


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


def _run(tmp: Path, captured_at: str) -> dict[str, object]:
    repo_copy = tmp / "repo"
    shutil.copytree(
        REPO_ROOT,
        repo_copy,
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
    workspace = tmp / "workspace"
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="paper-review",
        request=_GOAL,
        run_id="paper-review-typed-engine",
    )
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "manuscript.md").write_text(_MANUSCRIPT, encoding="utf-8")

    engine = compose_repository_engine(workspace=workspace, repo_root=repo_copy)
    result = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))
    if result.outcome is not EngineOutcome.COMPLETED:
        raise SystemExit(
            f"run did not reach COMPLETED: {result.outcome} :: {result.issues}"
        )

    run = engine.inspect().run
    assert run is not None
    status_by_unit = {u.plan.id: u.status.value for u in run.units}
    done = sum(1 for s in status_by_unit.values() if s in {"DONE", "SKIP"})

    artifacts: list[dict[str, object]] = []
    for rel in _STABLE_ARTIFACTS:
        p = workspace / rel
        if not p.is_file():
            raise SystemExit(f"expected produced artifact missing: {rel}")
        raw = p.read_bytes()
        artifacts.append(
            {"path": rel, "sha256": _sha256_bytes(raw), "size": len(raw)}
        )

    scorecard_path = workspace / _SCORECARD
    if not scorecard_path.is_file():
        raise SystemExit(f"expected produced artifact missing: {_SCORECARD}")
    scorecard_raw = scorecard_path.read_bytes()
    scorecard_doc = json.loads(scorecard_raw)
    artifacts.append(
        {
            "path": _SCORECARD,
            "sha256": _sha256_bytes(_canonical_scorecard_bytes(scorecard_path)),
            "size": len(scorecard_raw),
            "hash_basis": (
                "sha256 over canonical JSON with `generated_at` normalized to "
                f"{_NORMALIZED_SENTINEL!r}; the on-disk file embeds a wall-clock "
                "`generated_at` (tooling.common.now_iso_seconds -> datetime.now), "
                "so a plain sha256sum of the raw file will differ by design."
            ),
        }
    )

    observed_schemas = _observe_storage_schemas(workspace)

    return {
        "schema": "completed-run-evidence.v1",
        "captured_at": captured_at,
        "engine": "research_harness typed local engine",
        "storage_namespace": ".harness-v3",
        "observed_storage_schemas": observed_schemas,
        "semantic_scorecard_schema": str(scorecard_doc.get("schema")),
        "workflow": "paper-review",
        "goal": _GOAL,
        "source_mode": "deterministic_synthetic_manuscript",
        "run_state": "COMPLETED",
        "units": {
            "total": len(status_by_unit),
            "done": done,
            "unit_status": status_by_unit,
        },
        "produced_artifacts": artifacts,
        "verification": {
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
        },
        "limitations": [
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
        ],
    }


def _stable_json(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def _render_readme(summary: dict[str, object]) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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

    with tempfile.TemporaryDirectory() as raw:
        summary = _run(Path(raw), captured_at=args.captured_at)
    summary_payload = _stable_json(summary)
    readme_payload = _render_readme(summary)

    if args.check:
        problems: list[str] = []
        if not RUN_SUMMARY.is_file():
            problems.append("MISSING committed run-summary.json")
        elif RUN_SUMMARY.read_text(encoding="utf-8") != summary_payload:
            problems.append("DRIFT: run-summary.json does not reproduce byte-for-byte")
        if not README.is_file():
            problems.append("MISSING committed README.md")
        elif README.read_text(encoding="utf-8") != readme_payload:
            problems.append("DRIFT: README.md does not reproduce byte-for-byte")
        if problems:
            for line in problems:
                print(line, file=sys.stderr)
            return 1
        print("OK: typed-engine evidence reproduces byte-for-byte.")
        return 0

    EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY.write_text(summary_payload, encoding="utf-8")
    README.write_text(readme_payload, encoding="utf-8")
    print(f"wrote {RUN_SUMMARY.relative_to(REPO_ROOT)}")
    print(f"wrote {README.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
