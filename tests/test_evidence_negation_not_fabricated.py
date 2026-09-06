"""Held-out set for the evidence-auditor negation defect.

Frozen BEFORE the repair so the repair cannot be tuned to it. Four groups:

1. NEGATED — the manuscript explicitly denies the signal. Reporting it as
   provided writes fabricated support into a reader-facing referee artifact.
   This is the release blocker.
2. POSITIVE — the manuscript really does provide the signal. The repair must
   not suppress these; a negation fix that silences real evidence is worse
   than the defect.
3. SCOPED — a negation that governs ONE signal while another is genuinely
   present. Only the negated one may drop out.
4. CROSS-SECTION — the negation and the signal sit in different sentences or
   different sections, which is where a naive "any 'not' nearby" rule fails.

Run against the shipped module, not a copy.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "evidence_auditor_run",
    REPO_ROOT / ".codex" / "skills" / "evidence-auditor" / "scripts" / "run.py",
)
assert _SPEC and _SPEC.loader
_ea = importlib.util.module_from_spec(_SPEC)
sys.modules["evidence_auditor_run"] = _ea
_SPEC.loader.exec_module(_ea)

CLAIM = "Our method improves accuracy on the target task."


# ---------------------------------------------------------------- 1. NEGATED

NEGATED = (
    ("We do not report any ablation study for this component.", "ablation study"),
    ("No baseline comparison is provided in this work.", "baseline comparison"),
    ("We did not run an ablation for the fusion module.", "ablation study"),
    ("We do not report confidence intervals for these numbers.", "confidence intervals"),
    ("No dataset beyond the toy example was used.", "a named dataset"),
    ("We provide no baselines and leave that to future work.", "baseline comparison"),
    ("Ablations are not included in this version.", "ablation study"),
    ("Confidence intervals were not computed.", "confidence intervals"),
)


def test_negated_signal_is_not_reported_as_provided() -> None:
    for context, label in NEGATED:
        out = _ea._evidence_present(CLAIM, context)
        assert not (out.startswith("The manuscript provides") and label in out), (
            f"fabricated evidence: context denies {label!r} but audit says: {out}"
        )


# --------------------------------------------------------------- 2. POSITIVE

POSITIVE = (
    ("We run an ablation study over all three components.", "ablation study"),
    ("We compare against four strong baselines.", "baseline comparison"),
    ("All numbers are means over 5 seeds.", "multiple seeds"),
    ("We report 95% CI for every cell.", "confidence intervals"),
    ("Evaluated on the TCGA dataset.", "a named dataset"),
    ("The ablation study isolates each contribution.", "ablation study"),
)


def test_real_evidence_is_still_reported() -> None:
    for context, label in POSITIVE:
        out = _ea._evidence_present(CLAIM, context)
        assert label in out, f"real {label!r} was suppressed: {out}"


# ----------------------------------------------------------------- 3. SCOPED

def test_scoped_negation_drops_only_the_negated_signal() -> None:
    context = (
        "We compare against four strong baselines. "
        "We do not report any ablation study for this component."
    )
    out = _ea._evidence_present(CLAIM, context)
    assert "baseline comparison" in out, out
    assert not (out.startswith("The manuscript provides") and "ablation study" in out), out


def test_scoped_negation_other_order() -> None:
    context = (
        "No ablation study is included. "
        "We evaluate on the TCGA dataset with 95% confidence intervals."
    )
    out = _ea._evidence_present(CLAIM, context)
    assert "a named dataset" in out, out
    assert "confidence intervals" in out, out
    assert not (out.startswith("The manuscript provides") and "ablation study" in out), out


# ---------------------------------------------------------- 4. CROSS-SECTION

def test_negation_in_one_sentence_does_not_suppress_a_later_positive() -> None:
    # The negation governs its own sentence only. A different sentence that
    # genuinely provides the signal must still count.
    context = (
        "We do not report an ablation study in the main text. "
        "An ablation study over all components appears in Appendix B."
    )
    out = _ea._evidence_present(CLAIM, context)
    assert "ablation study" in out, out


def test_negated_source_context_does_not_borrow_a_results_signal_falsely() -> None:
    # Cross-section merge must obey the same rule: a signal denied in the
    # results context is not "additionally reported" there.
    source_context = "We compare against four strong baselines."
    results_context = "We do not report any ablation study."
    out = _ea._evidence_present(CLAIM, source_context, results_context)
    assert "baseline comparison" in out, out
    assert "ablation study" not in out, out


def test_cross_section_positive_still_merges() -> None:
    source_context = "The method improves accuracy."
    results_context = "We run an ablation study and report 95% confidence intervals."
    out = _ea._evidence_present(CLAIM, source_context, results_context)
    assert "ablation study" in out, out
    assert "results" in out.lower(), out


def test_hyphenated_compound_is_not_a_denial() -> None:
    # "a no-retrieval controller" NAMES a baseline; it does not deny one. An
    # over-broad negation cue silences the affirming sentence it sits in, which
    # is the opposite failure from the one this module guards.
    context = "Baselines include Salemi, Lin, and a no-retrieval controller."
    out = _ea._evidence_present(CLAIM, context)
    assert "baseline comparison" in out, out


def test_affirming_idioms_are_not_denials() -> None:
    # These carry a negation token but AFFIRM. Treating them as denials would
    # suppress evidence the manuscript really states.
    for context, label in (
        ("We evaluate against no fewer than three baselines.", "baseline comparison"),
        ("Not only do we run an ablation study, we also report 95% CI.", "ablation study"),
        ("Without loss of generality we report 95% confidence intervals.", "confidence intervals"),
    ):
        out = _ea._evidence_present(CLAIM, context)
        assert label in out, f"affirming idiom read as denial: {out}"


def test_known_limit_mixed_clause_under_reports_rather_than_fabricates() -> None:
    # A single sentence that denies one signal while affirming another is dropped
    # whole. This UNDER-reports the affirmed signal — a real limitation, pinned
    # here so it is a known contract rather than a surprise. The direction is what
    # matters: the artifact says less than the manuscript shows, never more.
    context = "Although we do not ablate the gate, we compare against four baselines."
    out = _ea._evidence_present(CLAIM, context)
    assert "baseline comparison" not in out, out
    assert not out.startswith("The manuscript provides"), out


# ------------------------------------------------- 5. FLATTENED SECTION BODIES

def test_one_denial_bullet_does_not_erase_its_sibling_bullets() -> None:
    # _results_context and _source_context flatten a section with " ".join, so a
    # markdown list arrives as ONE line. Without list-aware splitting the whole
    # section becomes a single pseudo-sentence and one denial bullet wipes every
    # genuine sibling — turning four real supports into "no concrete support".
    context = (
        "- Datasets: TCGA and CIFAR "
        "- Baselines: Salemi, Lin, Chen "
        "- Seeds: 5 seeds per configuration "
        "- Uncertainty: 95% confidence intervals "
        "- Ablation study: not performed"
    )
    out = _ea._evidence_present(CLAIM, context)
    for label in ("a named dataset", "baseline comparison", "multiple seeds", "confidence intervals"):
        assert label in out, f"{label} erased by an unrelated denial bullet: {out}"
    assert "ablation study" not in out, out


def test_abbreviation_does_not_sever_a_denial_from_its_signal() -> None:
    # An abbreviation period is not a sentence end. Splitting there strands the
    # signal in a fragment with no negation, so the denial is lost and the audit
    # fabricates support — the exact harm this module exists to prevent.
    for context, label in (
        ("We did not evaluate on the TCGA cohort used by Smith et al. 2021 or the CIFAR benchmark.", "a named dataset"),
        ("We do not report an ablation, cf. Table 4, nor a baseline comparison.", "baseline comparison"),
    ):
        out = _ea._evidence_present(CLAIM, context)
        assert not (out.startswith("The manuscript provides") and label in out), (
            f"abbreviation split fabricated {label!r}: {out}"
        )


def test_ordinary_sentence_boundaries_still_split() -> None:
    # The abbreviation guard must not stop real sentence splitting, or a denial
    # would swallow the affirming sentence that follows it.
    out = _ea._evidence_present(
        CLAIM, "We do not ablate the gate. We compare against four baselines."
    )
    assert "baseline comparison" in out, out


def test_denials_that_use_no_negation_verb() -> None:
    # A manuscript can decline to provide a signal without ever saying "not":
    # unable to, outside the scope, neither/nor, deferred, left for future work.
    # These are the same fabrication harm as an explicit denial.
    for context, label in (
        ("We were unable to run ablations within the compute budget.", "ablation study"),
        ("Ablation studies remain outside the scope of this paper.", "ablation study"),
        ("Neither ablations nor confidence intervals accompany the main table.", "ablation study"),
        ("A full ablation study is deferred to future work.", "ablation study"),
        ("The ablation study is left for future work.", "ablation study"),
    ):
        out = _ea._evidence_present(CLAIM, context)
        assert not (out.startswith("The manuscript provides") and label in out), (
            f"fabricated {label!r} from a soft denial: {out}"
        )
