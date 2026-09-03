"""Regression: sibling taxonomy children are not overlapping fragments of one title.

On a TITLES-ONLY corpus (empty abstracts), the builder produced sibling
children that were overlapping fragments sliced from a single title
phrase: "Fine Grained" + "Grained Expert" (both from "Fine-Grained Expert
Segmentation") and "Laws Language" + "Scaling Laws" (both from "Scaling Laws for
Language Models").

The child-selection loop now skips a child that shares a content token with an
already-kept SIBLING beyond the parent cluster's own token — those are the same
title fragment, not distinct sub-areas. Sharing only the parent/domain token (as
on a single-topic corpus, where sibling children legitimately share the dominant
term) is still allowed, so the idea-brainstorm direction floors are unaffected.
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

_TITLES = [
    "Sparse Mixture-of-Experts Scaling Laws for Language Models",
    "Routing Stability in Mixture-of-Experts Transformers",
    "Expert Load Balancing via Auxiliary Losses",
    "Compute-Optimal Mixture-of-Experts Pretraining",
    "Fine-Grained Expert Segmentation for Efficient Inference",
    "Dropless Mixture-of-Experts with Token Choice Routing",
    "Memory-Efficient Expert Parallelism for Large MoE Models",
    "Scaling Vision Transformers with Sparse Experts",
]


def _content_tokens(label: str) -> frozenset[str]:
    import re

    words = [w for w in re.findall(r"[a-z0-9]+", str(label or "").lower()) if len(w) >= 3]
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _build_taxonomy(tmp_path: Path) -> list[dict]:
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outline").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "abstract"])
        writer.writeheader()
        for idx, title in enumerate(_TITLES, start=1):
            writer.writerow({"paper_id": f"P{idx:04d}", "title": title, "abstract": ""})
    with (tmp_path / "papers" / "papers_dedup.jsonl").open("w", encoding="utf-8") as handle:
        for title in _TITLES:
            handle.write(json.dumps({"title": title, "abstract": ""}) + "\n")
    (tmp_path / "queries.md").write_text("- draft_profile: idea_brainstorm\n", encoding="utf-8")
    (tmp_path / "GOAL.md").write_text("goal: mixture of experts scaling\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path), "--min-freq", "2",
         "--outputs", "outline/taxonomy.yml"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load((tmp_path / "outline" / "taxonomy.yml").read_text(encoding="utf-8")) or []


def test_sibling_children_do_not_overlap_beyond_parent_token(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    assert taxonomy, "expected a non-empty taxonomy"
    for node in taxonomy:
        parent_fold = _content_tokens(str(node.get("name") or ""))
        kept: list[frozenset[str]] = []
        for child in node.get("children") or []:
            fold = _content_tokens(str(child.get("name") or ""))
            for prev in kept:
                extra = (fold & prev) - parent_fold
                assert not extra, (
                    f"siblings under {node.get('name')!r} share non-parent token(s) {set(extra)}: "
                    f"{child.get('name')!r}"
                )
            kept.append(fold)


def test_specific_overlapping_fragment_siblings_removed(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    by_parent = {str(n.get("name") or ""): [str(c.get("name") or "") for c in (n.get("children") or [])] for n in taxonomy}
    # "Grained Expert" must not co-occur with "Fine Grained" under one parent.
    for parent, kids in by_parent.items():
        assert not ("Fine Grained" in kids and "Grained Expert" in kids), (parent, kids)
        assert not ("Laws Language" in kids and "Scaling Laws" in kids), (parent, kids)
