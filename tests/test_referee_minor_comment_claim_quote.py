"""Regression: Minor Comments identify their target claim by quoting its text.

A read of a generated referee report (real ml-interatomic-potentials
abstract via the paper-review engine) found the Minor Comments listed bare
"Claim C02:" / "Claim C03:" prefixes with no claim text anywhere in the report —
so an author could not tell which manuscript statement each comment targeted.

The claim text is already available to the renderer via `claim_text_by_id`
(Clarity/Soundness already quote it). `render_rubric_review_markdown` now quotes
a clipped claim after each Minor-Comment claim id so the comment is actionable.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _clip_claim, render_rubric_review_markdown


def _minor_section(review: str) -> str:
    return review.split("### Minor Comments", 1)[1].split("### Recommendation", 1)[0]


def _claims() -> list[dict]:
    return [
        {"claim_id": "C01", "text": "The model attains a mean absolute error of 5.06 meV/atom for energy on the held-out test set."},
        {"claim_id": "C02", "text": "The interatomic potential enables access to the atomic structures of amorphous alloys across compositions."},
        {"claim_id": "C03", "text": "We develop a general-purpose machine-learning interatomic potential trained on density-functional data."},
    ]


def _minor_gaps() -> list[dict]:
    return [
        {"claim_id": "C02", "gap": "The conceptual claim needs a clearer boundary and stronger relation to prior work.",
         "minimal_fix": "Clarify what the claim excludes and tie it to the closest prior work."},
        {"claim_id": "C03", "gap": "The methods/dataset claim needs provenance and coverage.",
         "minimal_fix": "State dataset provenance, exact size, coverage, and evaluation protocol."},
    ]


def test_minor_comments_quote_their_claim_text() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=2, claims=_claims(), major_gaps=[], minor_gaps=_minor_gaps(),
        novelty_available=True, novelty_row={"work": "Thong et al.", "related_work": "Thong et al.", "claim_id": "C01"},
    )
    minor = _minor_section(review)
    # Each minor comment names its claim id AND quotes the underlying claim text.
    assert "Claim C02:" in minor, minor
    assert "amorphous alloys" in minor, minor  # from C02's claim text
    assert "Claim C03:" in minor, minor
    assert "general-purpose machine-learning interatomic potential" in minor, minor
    # No ellipsis residue from clipping.
    assert "..." not in minor, minor


def test_minor_comment_without_claim_text_has_no_empty_quote() -> None:
    # A minor gap whose claim id has no matching claim text must not print `("")`.
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, claims=[{"claim_id": "C01", "text": "A concrete measured result."}],
        major_gaps=[], minor_gaps=[{"claim_id": "C99", "gap": "Orphan minor concern with no claim text."}],
        novelty_available=True, novelty_row={"work": "Smith et al.", "related_work": "Smith et al.", "claim_id": "C01"},
    )
    minor = _minor_section(review)
    assert '("")' not in minor, minor
    assert "Claim C99:" in minor, minor
    assert "Orphan minor concern" in minor, minor


def test_clip_claim_is_word_bounded_and_ellipsis_free() -> None:
    long = "The model demonstrates excellent predictive performance on an independent test set with a mean absolute error of 5.06 meV per atom for energy"
    clipped = _clip_claim(long)
    assert len(clipped) <= 110
    assert "..." not in clipped
    # Word-bounded: the clip is a prefix ending on a whole word.
    assert long.startswith(clipped)
    assert not clipped.endswith(" ")
    assert _clip_claim("") == ""
    assert _clip_claim("short one") == "short one"
