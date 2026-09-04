"""Regression: figure-caption / table-reference claims are clean and typed right.

A review on a manuscript whose results live in FIGURE CAPTIONS and TABLE
references found two defects:

1. raw markdown image markup ("![](fig3.png)") leaked into an extracted claim,
   and a standalone "![alt](fig4.png)" line was extracted as a bogus claim; and
2. a measured comparison in non-canonical units ("trains in 8 GPU-hours versus
   31 GPU-hours") was misclassified conceptual.

`heading_context_sentences` now strips markdown image markup (dropping
image-only lines, stripping inline "![...](...)" from caption text), and
`classify_claim` treats a quantified comparison (>=2 numbers + a comparison cue)
as empirical even without a canonical result verb.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import classify_claim, heading_context_sentences, pick_claim_candidates


_PAPER = """# FastSeg: Real-Time Segmentation

## Results

![](fig3.png)
Figure 3: FastSeg reaches 79.2 mIoU on Cityscapes at 60 FPS, versus 74.1 mIoU at 22 FPS for DeepLab.

![architecture diagram](fig4.png)

Table 2 shows FastSeg trains in 8 GPU-hours versus 31 GPU-hours for the baseline.
"""


def test_no_raw_markdown_image_in_claims() -> None:
    claims = [c["sentence"] for c in pick_claim_candidates(_PAPER)]
    for claim in claims:
        assert "![" not in claim, claim
        assert "](" not in claim, claim


def test_image_only_line_not_extracted_as_claim() -> None:
    sentences = [it["sentence"] for it in heading_context_sentences(_PAPER)]
    # The standalone architecture image ref must not appear as a claim.
    assert not any("architecture diagram" in s and "fig4" in s for s in sentences), sentences
    # The caption assertion survives (markup stripped).
    assert any("79.2 mIoU" in s for s in sentences), sentences
    assert all("![" not in s for s in sentences), sentences


def test_quantified_comparison_classified_empirical() -> None:
    assert classify_claim("Table 2 shows FastSeg trains in 8 GPU-hours versus 31 GPU-hours for the baseline.") == "empirical"
    assert classify_claim("FastSeg runs at 60 FPS versus 22 FPS for the baseline.") == "empirical"


def test_single_number_no_comparison_still_conceptual() -> None:
    # A lone quantity with no comparison cue and no result verb / hint stays conceptual.
    assert classify_claim("The approach uses a 2 kb context window around each site.") == "conceptual"
    assert classify_claim("We propose a compact architecture for segmentation.") == "conceptual"


def test_caption_claims_flow_through_pool() -> None:
    claims = pick_claim_candidates(_PAPER)
    joined = " ".join(c["sentence"] for c in claims)
    assert "79.2 mIoU" in joined
    assert "8 GPU-hours" in joined
    # And the metric claims are typed empirical.
    for c in claims:
        if "GPU-hours" in c["sentence"] or "mIoU" in c["sentence"]:
            assert classify_claim(c["sentence"]) == "empirical", c["sentence"]
