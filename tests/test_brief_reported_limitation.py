"""Regression: brief 'Reported limitation' bullet is a real limitation, not motivation.

A read of a generated SNAPSHOT (real clinical-summarization corpus via the full engine)
found the "Open problems / risks" section's "Reported limitation to weigh:" bullet
quoting a motivation sentence — "Deploying MLLMs ... demands not only fluent
generation but also transparency ..." — rather than a limitation the cited paper
reports.

Cause: `_LIMITATION_CUE`'s bare "not" branch matched "demands **not** only", a
rhetorical "not only ... but also" motivation construction. Fix: add "not only" /
"not just" / "not merely" / "not simply" to `_POSITIVE_FRAMING`, which already
excludes motivation sentences from the limitation selection. Genuine "do not / does
not / cannot / still struggling" limitations are unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _LIMITATION_CUE, _POSITIVE_FRAMING


def _is_reported_limitation(sentence: str) -> bool:
    # Mirrors the selection guard in _brief_risk_bullets.
    return bool(_LIMITATION_CUE.search(sentence)) and not _POSITIVE_FRAMING.search(sentence)


def test_not_only_motivation_is_not_a_limitation() -> None:
    s = (
        "Deploying multimodal large language models for clinical summarization demands "
        "not only fluent generation but also transparency about where each statement originates."
    )
    assert not _is_reported_limitation(s), s


def test_not_just_and_not_merely_excluded() -> None:
    for s in (
        "The system needs not just accuracy but also calibrated confidence.",
        "This is not merely a benchmark win; it changes how results are interpreted.",
    ):
        assert not _is_reported_limitation(s), s


def test_genuine_limitations_still_detected() -> None:
    for s in (
        "Long context windows do not consistently enhance clinical reasoning.",
        "The method cannot handle rare disease prediction.",
        "The evaluation is limited to four benchmarks; this is a limitation of the study.",
    ):
        assert _is_reported_limitation(s), s


def test_positive_framing_still_excludes_advantages() -> None:
    assert not _is_reported_limitation(
        "The approach is promising and outperforms strong baselines, though limited to one dataset."
    )
