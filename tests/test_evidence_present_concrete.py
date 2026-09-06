"""Regression: evidence-auditor 'Evidence present' states concrete support.

An INDEPENDENT L1 review of MISSING_EVIDENCE.md found every row's "Evidence
present" field was the generic "The extracted claim has a locatable manuscript
source pointer.", discarding the concrete evidence the manuscript actually gives
(seeds, confidence intervals, benchmarks, baselines, ablations).

The auditor now reads the claim's manuscript source-section context and lists
the concrete evidence signals present; it falls back to an honest "no concrete
empirical support stated" only when none is found (no fabrication).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".codex" / "skills" / "evidence-auditor" / "scripts" / "run.py"

_PAPER = """# Confidence-Gated Retrieval

## 4. Experiments
On four benchmarks, CGC-RAG improves task success by 6.4 points over retrieval.
Baselines include Salemi, Lin, and a no-retrieval controller. We report over
five seeds with 95% confidence intervals. Ablations remove the gate (-4.1) and
the cache (-2.3).

## 6. Conclusion
A confidence-gated retrieval policy improves adaptation without weight updates.
"""

_CLAIMS = [
    {"schema": "review-claim.v1", "claim_id": "C01",
     "text": "On four benchmarks, CGC-RAG improves task success by 6.4 points over retrieval.",
     "claim_type": "empirical", "scope": "experiments", "source_pointer": "4. Experiments | x"},
    {"schema": "review-claim.v1", "claim_id": "C02",
     "text": "A confidence-gated retrieval policy improves adaptation without weight updates.",
     "claim_type": "conceptual", "scope": "conclusion", "source_pointer": "6. Conclusion | x"},
]


def _run(tmp_path: Path):
    (tmp_path / "output").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "PAPER.md").write_text(_PAPER, encoding="utf-8")
    (tmp_path / "output" / "CLAIMS.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in _CLAIMS), encoding="utf-8"
    )
    (tmp_path / "output" / "CLAIMS.md").write_text("# Claims\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    with (tmp_path / "output" / "EVIDENCE_AUDIT.jsonl").open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_experiments_claim_lists_concrete_evidence(tmp_path: Path) -> None:
    rows = _run(tmp_path)
    c01 = next(r for r in rows if r["claim_id"] == "C01")
    ev = c01["evidence_present"].lower()
    assert "manuscript provides" in ev, ev
    # Concrete signals from the Experiments section context.
    assert "confidence intervals" in ev, ev
    assert "ablation study" in ev, ev
    assert "baseline comparison" in ev, ev
    assert "locatable manuscript source pointer" not in ev, ev


def test_unsupported_conceptual_claim_is_honest(tmp_path: Path) -> None:
    rows = _run(tmp_path)
    c02 = next(r for r in rows if r["claim_id"] == "C02")
    ev = c02["evidence_present"].lower()
    # The Conclusion context has no concrete empirical signal -> honest note.
    assert "no concrete empirical support stated" in ev, ev
