"""Regression: novelty matrix uses the manuscript's stated per-work deltas.

A review of NOVELTY_MATRIX.md found every row carried identical
boilerplate ("adjacent problem setting" / "claimed method delta requires
verification"), discarding the manuscript's own Related-Work distinctions ("the
delta over Salemi is that gate, and the delta over Lin is the cache-coherent
memory").

`related_work_delta` now extracts the manuscript-stated overlap/delta per cited
work, and the novelty-matrix builder uses it, falling back to a conservative
"no explicit delta stated" only when the manuscript says nothing specific.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import related_work_delta


_PAPER = """# Confidence-Gated Retrieval for Robotic Test-Time Adaptation

## 2. Related Work
Prior work by Salemi et al. and Lin et al. addresses test-time adaptation in
robotic manipulation. Model-based adaptation by Chen updates parameters online.
CGC-RAG differs by adding a confidence-gated retrieval policy; the delta over
Salemi is that gate, and the delta over Lin is the cache-coherent memory. Kumar
et al. study calibrated confidence and Zhao et al. study cache-coherent episodic
memory, both of which CGC-RAG combines.

## 3. Method
Weights are never updated at test time.

## References
- Salemi et al. Retrieval-augmented methods. 2024.
- Lin et al. Inference-time retrieval. 2023.
"""


def test_related_work_delta_extracts_explicit_deltas() -> None:
    _, salemi = related_work_delta(_PAPER, "Salemi et al. Retrieval-augmented methods. 2024.")
    _, lin = related_work_delta(_PAPER, "Lin et al. Inference-time retrieval. 2023.")
    assert "gate" in salemi.lower(), salemi
    assert "cache-coherent memory" in lin.lower(), lin


def test_related_work_delta_marks_combined_works() -> None:
    # Kumar/Zhao are "both of which CGC-RAG combines" -> not a differentiating delta.
    _, kumar = related_work_delta(_PAPER, "Kumar et al. Calibrated confidence. 2023.")
    assert "combined" in kumar.lower(), kumar


def test_related_work_delta_empty_when_unmentioned() -> None:
    o, d = related_work_delta(_PAPER, "Nonexistent et al. Unrelated topic. 2020.")
    assert o == "" and d == "", (o, d)


def test_novelty_matrix_rows_are_differentiated() -> None:
    # End-to-end: the builder should produce >1 distinct delta across rows for a
    # manuscript that states per-work deltas.
    import csv
    import subprocess
    import tempfile

    script = REPO_ROOT / ".codex" / "skills" / "novelty-matrix" / "scripts" / "run.py"
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "output").mkdir(parents=True, exist_ok=True)
        (ws / "output" / "PAPER.md").write_text(_PAPER, encoding="utf-8")
        (ws / "output" / "CLAIMS.md").write_text(
            "# Claims\n\n## Empirical claims\n\n### C01\n- Claim: CGC-RAG improves task success by 6.4 points.\n- Type: empirical\n- Scope: Abstract\n- Source: Abstract | x\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(script), "--workspace", str(ws)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        rows = list(csv.DictReader((ws / "output" / "NOVELTY_MATRIX.tsv").open(), delimiter="\t"))
        deltas = {r["delta"] for r in rows}
        # Salemi -> "that gate", Lin -> "the cache-coherent memory": >1 distinct.
        assert len(deltas) >= 2, deltas
        assert any("gate" in d.lower() for d in deltas), deltas
        # No row carries the old boilerplate.
        assert "claimed method delta requires verification" not in deltas, deltas
