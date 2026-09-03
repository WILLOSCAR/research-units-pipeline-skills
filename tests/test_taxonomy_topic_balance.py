"""Regression: top-level taxonomy clusters are distinct topics, not fragments.

On a two-topic corpus (test-time adaptation + clinical text summarization), the
top-level clusters were "Clinical Text Summarization", "Text Summarization",
"Clinical Text", "Test
Time Adaptation" — three overlapping fragments of the SAME clinical topic
consuming top-level slots and crowding out the second topic.

The builder now draws from a larger token pool but keeps only clusters whose
labels are distinct topic areas: a cluster whose content tokens are a subset of,
or >= 0.5 Jaccard with, an already-emitted cluster label is skipped
(`_cluster_labels_near_duplicate`), freeing the slot for a distinct topic.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".codex" / "skills" / "taxonomy-builder" / "scripts" / "run.py"
sys.path.insert(0, str(SKILL.parent))
from run import _cluster_labels_near_duplicate, _label_content_tokens  # noqa: E402

# 2-topic titles: clinical summarization + test-time adaptation.
_TITLES = [
    "Clinical Text Summarization with Large Language Models",
    "Faithful Clinical Text Summarization via Agentic Inference",
    "Adapted Large Language Models for Clinical Summarization",
    "Abstractive Clinical Text Summarization Benchmarks",
    "Test-Time Adaptation under Distribution Shift",
    "Robust Test-Time Adaptation against Distribution Shifts",
    "Benchmarking Test-Time Adaptation in Image Classification",
    "Continual Test-Time Adaptation for Time Series",
]


def test_cluster_labels_near_duplicate_detects_fragments() -> None:
    a = _label_content_tokens("Clinical Text Summarization")
    b = _label_content_tokens("Clinical Text")  # subset
    c = _label_content_tokens("Text Summarization")  # heavy overlap
    d = _label_content_tokens("Test Time Adaptation")  # distinct
    assert _cluster_labels_near_duplicate(a, b) is True
    assert _cluster_labels_near_duplicate(a, c) is True
    assert _cluster_labels_near_duplicate(a, d) is False


def test_two_topic_taxonomy_has_both_topics_no_fragment_dups(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outline").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "reason"])
        writer.writeheader()
        for idx, title in enumerate(_TITLES, start=1):
            writer.writerow({"paper_id": f"P{idx:04d}", "title": title, "year": 2024, "url": f"https://x/{idx}", "reason": "fixture"})
    (tmp_path / "queries.md").write_text("- draft_profile: idea_brainstorm\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path), "--outputs", "outline/taxonomy.yml"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    tax = yaml.safe_load((tmp_path / "outline" / "taxonomy.yml").read_text(encoding="utf-8")) or []
    names = [str(n.get("name") or "") for n in tax]
    # No two top-level clusters are near-duplicate fragments of each other.
    folds = [_label_content_tokens(n) for n in names]
    for i in range(len(folds)):
        for j in range(i + 1, len(folds)):
            assert not _cluster_labels_near_duplicate(folds[i], folds[j]), (names[i], names[j])
    # Both topics are represented.
    joined = " ".join(names).lower()
    assert any(w in joined for w in ("clinical", "summar")), names
    assert any(w in joined for w in ("test", "adaptation", "distribution")), names
