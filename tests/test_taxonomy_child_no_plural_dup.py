"""Regression: taxonomy children have no plural/singular sibling duplicates.

The L1 (intermediate-artifact) review of a research-brief taxonomy found sibling
children that differed only by plural/singular — "Distribution Shifts" and
"Distribution Shift" under the same parent. The earlier dedup used a case-only
`used_labels` set, which does not fold plural/singular.

The builder now folds child labels with `_label_fold` (plural/singular- and
whitespace-insensitive) and skips a child whose folded key was already used.
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
from run import _label_fold  # noqa: E402

# Titles engineered so the top cluster's children include both "Distribution
# Shifts" and "Distribution Shift" candidates.
_TITLES = [
    "Test-Time Adaptation under Distribution Shifts in Vision",
    "Robust Test-Time Adaptation against Distribution Shift",
    "Benchmarking Test-Time Adaptation under Distribution Shifts",
    "Continual Test-Time Adaptation and Distribution Shift Detection",
    "Label Distribution Shift-Aware Test-Time Adaptation",
    "Test-Time Adaptation for Distribution Shifts in Time Series",
    "Confidence-Gated Test-Time Adaptation under Distribution Shift",
    "Source-Free Test-Time Adaptation against Distribution Shifts",
]


def test_label_fold_collapses_plural_singular() -> None:
    assert _label_fold("Distribution Shifts") == _label_fold("Distribution Shift")
    assert _label_fold("Series Anomaly") != _label_fold("Distribution Shift")


def test_taxonomy_children_have_no_plural_singular_siblings(tmp_path: Path) -> None:
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
    for node in tax:
        folds = [_label_fold(c.get("name", "")) for c in (node.get("children") or [])]
        assert len(folds) == len(set(folds)), (node.get("name"), [c.get("name") for c in node.get("children") or []])
