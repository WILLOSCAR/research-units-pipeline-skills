"""Regression: claim extraction consolidates near-duplicate claims.

A review (a manuscript restating the SAME empirical
result in the abstract and experiments) found claim extraction listed the same
2.3-point accuracy assertion as three separate claims (C01/C02/C04), inflating
the claim count and downstream gaps.

`pick_claim_candidates` already deduped EXACT normalized strings; it now also
drops NEAR-duplicates whose significant content-token sets are >= 0.8 Jaccard,
keeping the highest-scored variant. A high threshold avoids merging genuinely
distinct claims that merely share vocabulary.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import pick_claim_candidates, _token_set_near_duplicate


_MANUSCRIPT = """# GAD

## Abstract
On ImageNet-scale evaluation GAD improves top-1 accuracy by 2.3 points over the strongest KD baseline.
GAD improves top-1 accuracy by 2.3 points over the strongest KD baseline on the same evaluation.

## 3. Experiments
GAD improves top-1 accuracy by 2.3 points over the strongest KD baseline.
Ablations remove the projection (-1.8) and the temperature scaling (-1.1).

## 6. Conclusion
Gradient-aligned distillation improves compact vision transformers.
"""


def test_near_duplicate_result_claims_are_consolidated() -> None:
    claims = pick_claim_candidates(_MANUSCRIPT, limit=8)
    sentences = [c["sentence"] for c in claims]
    # The 2.3-point improvement over the strongest KD baseline appears only ONCE.
    dup = [s for s in sentences if "2.3 points over the strongest kd baseline" in s.lower()]
    assert len(dup) == 1, dup
    # Genuinely distinct claims survive (ablations, conclusion).
    assert any("ablations remove the projection" in s.lower() for s in sentences), sentences


def test_token_set_near_duplicate_threshold() -> None:
    a = frozenset({"gad", "improves", "accuracy", "points", "strongest", "baseline"})
    # Same tokens plus one -> Jaccard high -> duplicate.
    b = frozenset(a | {"imagenet"})
    assert _token_set_near_duplicate(a, b) is True
    # Half-different -> below threshold -> distinct.
    c = frozenset({"gad", "improves", "latency", "memory", "footprint", "device"})
    assert _token_set_near_duplicate(a, c) is False
