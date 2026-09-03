"""Regression: no child label restates another top-level cluster's topic.

On a near-synonym corpus, the generic taxonomy-builder let a CHILD label
duplicate another top-level cluster: "Domain
Shift" appeared as a child of "Distribution Shift" while "Domain" was its own
top-level cluster, and "Test Time" appeared as a child while "Test Time
Adaptation" was a top-level cluster. A reader saw the same topic area at two
levels.

The child-selection loop deduped children against sibling/earlier-claimed labels
and spine tokens, but not against the set of top-level cluster labels. It now
skips a child whose folded content tokens are a subset of / near-duplicate to
ANY other top-level cluster label (overlap with the child's own parent is still
allowed). Pure semantic synonymy with no shared token ("Domain Shift" vs
"Distribution Shift" as two clusters) stays out of scope — that is LLM-bound.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".codex" / "skills" / "taxonomy-builder" / "scripts" / "run.py"

# Titles engineered so a cluster's children would include topics that are
# themselves other top-level clusters (domain / test-time-adaptation).
_TITLES = [
    "Robust Adaptation under Distribution Shift for Vision Models",
    "Handling Domain Shift with Test-Time Adaptation",
    "Test Time Adaptation for Continual Distribution Shift",
    "Domain Shift Robustness via Feature Alignment",
    "A Survey of Distribution Shift Detection Methods",
    "Test-Time Adaptation Benchmarks under Domain Shift",
    "Continual Test Time Adaptation for Streaming Data",
    "Distribution Shift Estimation with Confidence Bounds",
]


def _content_tokens(label: str) -> frozenset[str]:
    import re

    words = [w for w in re.findall(r"[a-z0-9]+", str(label or "").lower()) if len(w) >= 3]
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _near_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    if a <= b or b <= a:
        return True
    inter = len(a & b)
    return inter / max(1, len(a | b)) >= 0.5


def _build_taxonomy(tmp_path: Path) -> list[dict]:
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outline").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_id", "title"])
        writer.writeheader()
        for idx, title in enumerate(_TITLES, start=1):
            writer.writerow({"paper_id": f"P{idx:04d}", "title": title})
    with (tmp_path / "papers" / "papers_dedup.jsonl").open("w", encoding="utf-8") as handle:
        for title in _TITLES:
            handle.write(json.dumps({"title": title, "abstract": title}) + "\n")
    (tmp_path / "queries.md").write_text("- draft_profile: idea_brainstorm\n", encoding="utf-8")
    (tmp_path / "GOAL.md").write_text("goal: adaptation under shift\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path), "--min-freq", "2",
         "--outputs", "outline/taxonomy.yml"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load((tmp_path / "outline" / "taxonomy.yml").read_text(encoding="utf-8")) or []


def test_no_child_restates_another_top_level_cluster(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    assert taxonomy, "expected a non-empty taxonomy"

    cluster_folds = {str(n.get("name") or ""): _content_tokens(str(n.get("name") or "")) for n in taxonomy}
    for node in taxonomy:
        parent = str(node.get("name") or "")
        parent_fold = cluster_folds[parent]
        for child in node.get("children") or []:
            child_name = str(child.get("name") or "")
            child_fold = _content_tokens(child_name)
            for other_name, other_fold in cluster_folds.items():
                if other_fold == parent_fold:
                    continue
                assert not _near_duplicate(child_fold, other_fold), (
                    f"child {child_name!r} under {parent!r} restates top-level cluster {other_name!r}"
                )


def test_specific_cross_level_duplicates_removed(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    children = {str(c.get("name") or "") for n in taxonomy for c in (n.get("children") or [])}
    # The offending children the reviewers flagged must not appear.
    assert "Domain Shift" not in children, children
    assert "Test Time" not in children, children
    assert "Handling Domain" not in children, children
