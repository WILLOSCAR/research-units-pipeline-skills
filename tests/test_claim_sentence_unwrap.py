"""Regression: manuscript sentences are not truncated at soft line wraps.

`heading_context_sentences` split sentences PER LINE, so a sentence
soft-wrapped across markdown lines (as in a typical abstract, or PDF-extracted
text) was cut at each line break. That produced fragment "claims" like
"...improves F1 by 5.1 points (accuracy 0.914) over the" — which the downstream
gap classifier then mislabels as "underspecified: no concrete metric", turning a
metric-bearing claim into a false major concern in the referee report. Surfaced
while reading a generated REVIEW.md.

The extractor now joins a paragraph's wrapped lines before sentence-splitting.
This test pins that a wrapped sentence is recovered whole and that claim
candidates carry their trailing metric context.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import heading_context_sentences, pick_claim_candidates

_WRAPPED = """# Title

## Abstract
We present CE-VarNet for somatic variant calling under coverage shift. On the
TCGA benchmark dataset it improves F1 by 5.1 points (accuracy 0.914) over the
strongest ensemble baseline, measured across five sequencing depths.

## 4. Experiments
Ablation removing the filter drops F1 by 4.1 on
the same benchmark.
"""


def test_wrapped_sentence_is_recovered_whole() -> None:
    sentences = [s["sentence"] for s in heading_context_sentences(_WRAPPED)]
    # The abstract's wrapped result sentence must appear whole, not cut at "over the".
    whole = [s for s in sentences if "strongest ensemble baseline" in s and "F1 by 5.1 points" in s]
    assert whole, f"wrapped sentence was truncated: {sentences}"
    # No extracted sentence ends on a dangling function word (the tell-tale of a
    # mid-sentence line-break cut).
    for s in sentences:
        assert not s.rstrip().endswith((" the", " over", " by", " on", " a", " of", " to")), s


def test_claim_candidates_keep_metric_context() -> None:
    candidates = [c["sentence"] for c in pick_claim_candidates(_WRAPPED)]
    joined = " || ".join(candidates)
    # The metric-bearing claim retains its baseline + depth context.
    assert "strongest ensemble baseline" in joined, candidates
    # The ablation claim retains its object ("the same benchmark"), not "...4.1 on".
    assert any("drops F1 by 4.1 on the same benchmark" in c for c in candidates), candidates
