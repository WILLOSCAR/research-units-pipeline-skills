"""Regression: idea-brainstorm directions — distinct + no mid-word truncation.

A read of a generated idea-brainstorm §3 directions section found two
deterministic defects that the surface checks did not catch:

1. `clean_sentence` returned a mid-word cut ("... and if the conclusion
   survives, de") when a single long sentence had no internal terminator within
   the limit — it appended the whole over-long window. It now always ends on a
   clause-or-word boundary.
2. `signals_to_direction_cards` emitted two near-identical direction cards whose
   clusters differed only by plural/singular ("... Distribution Shifts" vs "...
   Distribution Shift"), so Directions 2 and 3 were duplicates. A distinctness
   guard now collapses such twins.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import clean_sentence


_LONG = (
    "Prior-work audit: inspect Label Distribution Shift-Aware Prediction "
    "Refinement for Test-Time Adaptation for any ablation that already fixes "
    "nearby design choices and evaluation framing, and if the conclusion "
    "survives, demote this direction."
)


def test_clean_sentence_never_ends_mid_word() -> None:
    for limit in (54, 100, 120, 180):
        out = clean_sentence(_LONG, limit=limit)
        assert len(out) <= limit, (limit, len(out), out)
        # The last token must be a whole word from the source.
        last = out.rstrip(".").split()[-1] if out.strip() else ""
        source_words = set(_LONG.replace(",", "").replace(".", "").split())
        assert last in source_words, (limit, last, out)
        # Specifically not the known bad fragments.
        assert not out.rstrip().endswith((" de", " surv", " dem", " survi")), out


def test_clean_sentence_short_input_verbatim() -> None:
    s = "Vary the feedback type and read out task success."
    assert clean_sentence(s, limit=180) == s


def _make_card(cluster: str, *, axis: str = "feedback type", confound: str = "nearby design choices"):
    from tooling.ideation import DirectionCard
    import dataclasses

    kwargs: dict = {}
    for f in dataclasses.fields(DirectionCard):
        kwargs[f.name] = "" if (f.type == "str" or f.type is str) else []
    kwargs["cluster"] = cluster
    kwargs["focus_axis"] = axis
    kwargs["main_confound"] = confound
    kwargs["program_kind"] = "mechanism-clarification"
    kwargs["evidence_confidence"] = "medium"
    return DirectionCard(**kwargs)


def test_same_thesis_identity_collapses_across_domains() -> None:
    from tooling.ideation import _direction_distinctness_key

    # Same axis + confound, DIFFERENT domain cluster (incl. plural/singular) ->
    # same thesis line -> collapses (the near-duplicate case: "feedback
    # type ... Distribution Shifts" vs "... Time Series").
    a = _direction_distinctness_key(_make_card("Test Time Adaptation / Distribution Shifts"))
    b = _direction_distinctness_key(_make_card("Test Time Adaptation / Distribution Shift"))
    c = _direction_distinctness_key(_make_card("Test Time Adaptation / Time Series"))
    assert a == b == c, (a, b, c)


def test_different_axis_or_confound_stays_distinct() -> None:
    from tooling.ideation import _direction_distinctness_key

    base = _direction_distinctness_key(_make_card("X / Y", axis="feedback type", confound="design choices"))
    diff_axis = _direction_distinctness_key(_make_card("X / Y", axis="accurate sensitivity", confound="design choices"))
    diff_confound = _direction_distinctness_key(_make_card("X / Y", axis="feedback type", confound="evaluation budget"))
    assert diff_axis != base, (diff_axis, base)
    assert diff_confound != base, (diff_confound, base)


def test_axis_wording_variants_collapse_but_content_variants_stay() -> None:
    """A generated direction set contained four cards that were wording variants
    of the same axis ("feedback type" / "the type of feedback" / "feedback
    signal type" / "feedback modality"), all surviving as distinct. The key
    now folds order + generic filler words, so pure wording variants collapse;
    variants that add a real content token stay distinct (synonymy is LLM-bound).
    """
    from tooling.ideation import _direction_distinctness_key

    # Word-order + filler-word variants of the SAME axis collapse to one key.
    k_type = _direction_distinctness_key(_make_card("X / Y", axis="feedback type", confound="design choices"))
    k_of = _direction_distinctness_key(_make_card("X / Y", axis="the type of feedback", confound="design choices"))
    assert k_type == k_of, (k_type, k_of)

    # A variant that adds a real content token is NOT collapsed (needs synonymy).
    k_signal = _direction_distinctness_key(_make_card("X / Y", axis="feedback signal type", confound="design choices"))
    k_modality = _direction_distinctness_key(_make_card("X / Y", axis="feedback modality", confound="design choices"))
    assert k_signal != k_type, (k_signal, k_type)
    assert k_modality != k_type, (k_modality, k_type)

    # Confound wording variants collapse the same way (order + filler).
    k_c1 = _direction_distinctness_key(_make_card("X / Y", axis="feedback type", confound="nearby design choices and evaluation framing"))
    k_c2 = _direction_distinctness_key(_make_card("X / Y", axis="feedback type", confound="evaluation framing and the nearby design choices"))
    assert k_c1 == k_c2, (k_c1, k_c2)


def test_axis_wording_variants_deduped_in_pool() -> None:
    from tooling.ideation import IdeaSignal, signals_to_direction_cards

    note_index = {"P1": {"title": "Anchor Paper One"}}
    axes = ["feedback type", "the type of feedback", "feedback signal type", "feedback modality"]
    signals = [
        IdeaSignal(
            signal_id=f"S{i}", cluster="Test-Time Adaptation", direction_type="confound_control",
            theme="feedback", claim_or_observation="c", tension="t", missing_piece="m",
            possible_axis=ax, academic_value="a", evidence_confidence="medium", paper_ids=["P1"],
        )
        for i, ax in enumerate(axes, start=1)
    ]
    cards = signals_to_direction_cards(
        signals, note_index=note_index, focus_clusters=["Test-Time Adaptation"], pool_min=1, pool_max=20
    )
    # "feedback type" and "the type of feedback" collapse; the two that add a
    # content token survive: 3 of 4, no pure wording twin.
    axes_out = sorted(c.focus_axis for c in cards)
    assert len(cards) == 3, axes_out
    assert not ("feedback type" in axes_out and "the type of feedback" in axes_out), axes_out
