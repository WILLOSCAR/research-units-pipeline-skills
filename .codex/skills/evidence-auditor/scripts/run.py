from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Concrete evidence signals a manuscript can supply for a claim. Each maps a
# detection regex to a short human-readable phrase for the "Evidence present"
# field, so the audit records WHAT support exists rather than a generic pointer.
_EVIDENCE_SIGNALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\b(\d+)\s+seeds?\b"), "multiple seeds"),
    (re.compile(r"(?i)confidence intervals?|95%\s*ci|std(?:ard)?\s*dev"), "confidence intervals"),
    (re.compile(r"(?i)\bablation(s)?\b"), "ablation study"),
    (re.compile(r"(?i)\b(\d+)\s+benchmarks?\b|benchmark datasets?"), "benchmark coverage"),
    (re.compile(r"(?i)\bbaseline(s)?\b"), "baseline comparison"),
    (re.compile(r"(?i)\b\d+(\.\d+)?\s*(points?|%|f1|accuracy)\b"), "a reported metric value"),
    (re.compile(r"(?i)\bdataset(s)?\b|TCGA|CIFAR|ImageNet"), "a named dataset"),
]

# A signal word inside a sentence that DENIES it is not evidence. Reporting it
# would write support into the referee artifact that the manuscript explicitly
# disclaims. Scope is the sentence: a denial governs its own clause, not the
# whole section, so a later sentence that genuinely supplies the signal counts.
#
# `no` must be followed by whitespace: a hyphenated compound like "a no-retrieval
# controller" or "zero-shot" names a THING, it does not deny one, and treating it
# as a denial would silence the affirming sentence it sits in.
_NEGATION_CUE = re.compile(
    r"(?i)(?:\bno\s|\bnot\b|\bnever\b|\bwithout\b|\blacks?\b|\babsent\b|"
    r"\bomits?\b|\bomitted\b|\bcannot\b|\bfailed to\b|"
    r"\bneither\b|\bnor\b|\bunable to\b|\boutside the scope\b|"
    r"\bbeyond the scope\b|\bdefer(?:s|red)?\b|\bleft for\b|\bpostponed?\b|"
    r"\bleave[sd]?\b.{0,20}\bto future work\b)"
)
# Phrases that contain a negation token but AFFIRM. Checked first, so they are
# never mistaken for denials. This list is deliberately short: each entry is a
# fixed idiom, not an attempt to parse English.
_AFFIRMING_IDIOM = re.compile(
    r"(?i)(?:\bno fewer than\b|\bno less than\b|\bnot only\b|"
    r"\bwithout loss of generality\b)"
)
# Sentence boundary. Section bodies reach us already flattened with " ".join
# (see _results_context / _source_context), so a newline split is not enough:
# a markdown bullet list arrives as one long line and would collapse into a
# single pseudo-sentence, letting one denial bullet erase every sibling bullet.
# Split on list-item markers too, so each bullet is its own unit.
#
# The negative lookbehind keeps common abbreviations from ending a sentence.
# "Smith et al. 2021" or "cf. Table 4" would otherwise sever a denial from the
# signal it governs, and the surviving fragment would be read as affirming
# support the manuscript explicitly denies.
_ABBREV = r"(?<!\bal\.)(?<!\bcf\.)(?<!\bFig\.)(?<!\bTab\.)(?<!\bEq\.)(?<!\bSec\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\bNo\.)"
_SENTENCE_SPLIT = re.compile(
    _ABBREV + r"(?<=[.!?;])\s+"  # ordinary sentence end, not an abbreviation
    r"|\n+"                      # explicit newline
    r"|\s+(?=[-*•]\s)"      # start of a "- ", "* " or bullet item
    r"|\s+(?=\d+[.)]\s)"         # start of a "1. " or "1) " item
)


def _affirming_sentences(text: str) -> str:
    """Drop sentences that deny a signal, keep the rest.

    Sentence-scoped on purpose. A section-wide rule would let one "we do not
    report X" erase a genuine X stated two sentences later; a phrase-level rule
    would need a parser. The sentence is the unit a denial actually governs.

    Known limit: a sentence that denies one signal while affirming another
    ("although we do not ablate the gate, we compare against four baselines")
    is dropped whole, so the affirmed signal is under-reported. That errs toward
    saying LESS than the manuscript shows, which is the safe direction for a
    referee artifact; the alternative is claiming support the manuscript denies.
    """
    kept = [
        s
        for s in _SENTENCE_SPLIT.split(text)
        if s and (_AFFIRMING_IDIOM.search(s) or not _NEGATION_CUE.search(s))
    ]
    return "\n".join(kept)


def _evidence_present(claim_text: str, source_context: str, results_context: str = "") -> str:
    """Concrete evidence the manuscript states for this claim (context + text).

    Scans the claim's source-section context (and the claim text) for concrete
    empirical signals and lists the ones found, instead of a generic "has a
    locatable source pointer". Falls back to the locatable-pointer note only when
    no concrete signal is present.

    When the claim sentence sits in a non-results section (e.g. a headline claim
    in the Introduction) whose own context lacks concrete numbers, ``results_context``
    supplies the manuscript's Results/Experiments text so cross-section evidence
    for the SAME claim is not under-reported. Evidence found only there is labelled
    as reported in the results section.
    """
    haystack = _affirming_sentences(f"{claim_text}\n{source_context}")
    found: list[str] = []
    for pattern, label in _EVIDENCE_SIGNALS:
        if pattern.search(haystack) and label not in found:
            found.append(label)
    # For an empirical headline claim, evidence for the SAME claim often lives in
    # the results section, not the sentence's own section. Merge those signals so
    # the audit does not under-report support just because of where the sentence
    # sits. Signals found ONLY in the results section are noted as such.
    cross_only: list[str] = []
    if results_context:
        affirming_results = _affirming_sentences(results_context)
        for pattern, label in _EVIDENCE_SIGNALS:
            if label in found:
                continue
            if pattern.search(affirming_results) and label not in cross_only:
                cross_only.append(label)
    if found and cross_only:
        return (
            "The manuscript provides " + ", ".join(found[:5]) + " for this claim, "
            "with additional " + ", ".join(cross_only[:5]) + " reported in the "
            "results/experiments section (a different section than the claim sentence)."
        )
    if found:
        return "The manuscript provides " + ", ".join(found[:5]) + " for this claim."
    if cross_only:
        return (
            "The manuscript provides " + ", ".join(cross_only[:5]) + " for this claim "
            "in its results/experiments section (reported in a different section "
            "than the claim sentence)."
        )
    return "The extracted claim has a locatable manuscript source pointer but no concrete empirical support stated."


# Section headings whose body reports empirical results. Evidence for a headline
# claim frequently lives here rather than in the section that states the claim.
_RESULTS_SECTION_CUE = re.compile(r"(?i)\b(experiment|experiments|results|evaluation|empirical|ablation)s?\b")


def _results_context(paper_text: str) -> str:
    """Concatenated body text of the manuscript's results/experiments sections."""
    if not paper_text:
        return ""
    buf: list[str] = []
    capturing = False
    for raw in paper_text.splitlines():
        line = raw.strip()
        h = re.match(r"^#{1,4}\s+(.*\S)\s*$", line)
        if h:
            head = re.sub(r"^\d+(?:\.\d+)*[.:]?\s+", "", h.group(1)).strip()
            capturing = bool(_RESULTS_SECTION_CUE.search(head))
            continue
        if capturing and line:
            buf.append(line)
    return " ".join(buf).strip()


def _source_context(claim: dict[str, str], paper_text: str) -> str:
    """The manuscript section text tied to this claim (via its source pointer)."""
    pointer = str(claim.get("source_pointer") or claim.get("source") or "")
    # Source pointers look like "4. Experiments | \"...\"" — take the section name.
    section = pointer.split("|", 1)[0].strip()
    if not section or not paper_text:
        return ""
    lines = paper_text.splitlines()
    # Find the heading whose text contains the section name, collect until next heading.
    buf: list[str] = []
    capturing = False
    sec_low = re.sub(r"[^a-z0-9]+", " ", section.lower()).strip()
    for raw in lines:
        line = raw.strip()
        h = re.match(r"^#{1,4}\s+(.*\S)\s*$", line)
        if h:
            head_low = re.sub(r"[^a-z0-9]+", " ", h.group(1).lower()).strip()
            if capturing:
                break
            if sec_low and (sec_low in head_low or head_low in sec_low):
                capturing = True
            continue
        if capturing:
            buf.append(line)
    return " ".join(b for b in buf if b).strip()


def _gap_for_claim(claim: dict[str, str], evidence_present: str) -> tuple[str, str, str]:
    text = str(claim.get("claim") or "")
    low = text.lower()
    if claim.get("type") == "empirical":
        if "%" in text or _HAS_CONCRETE_METRIC.search(low) or any(
            token in low for token in ("benchmark", "dataset", "accuracy", "success rate", "metric")
        ):
            # The claim already states a concrete metric/value — the honest gap is
            # missing PROTOCOL context (dataset identity, baseline, budget), NOT an
            # absence of any metric (which would contradict the claim's own text).
            return (
                evidence_present,
                "The claim reports a concrete result but still needs an explicit "
                "baseline/protocol check (dataset identity, comparator, budget) "
                "before it can support a strong review judgment.",
                "Add a comparison table that states dataset, metric, baseline, and evaluation budget for this claim.",
            )
        return (
            evidence_present,
            "The empirical claim is underspecified: no concrete metric, dataset, or benchmark detail appears in the extracted claim text.",
            "State the task, metric, baseline, and result in the manuscript section tied to this claim.",
        )
    return _conceptual_gap(text, evidence_present)


# A conceptual claim is not one uniform thing: the audit gap a referee needs
# differs by the claim's ROLE. A results-reporting sentence ("the results reveal
# that some models achieve high accuracy") needs the underlying per-model numbers;
# a methods/dataset sentence ("using ~10,000 calculations we evaluate ...") needs
# provenance/coverage/protocol; a background/motivation sentence needs citations
# and scoping. Emitting one identical "clearer boundary + prior work" gap for all
# three (the old behaviour) gives the referee no per-claim signal.
_RESULTS_REPORT_CUE = re.compile(
    r"(?i)\b(?:results? (?:reveal|show|indicate|demonstrate)|we (?:find|observe|show|"
    r"demonstrate|report)\b|these findings?|our (?:results|findings|experiments?) (?:show|reveal|indicate)|"
    r"achieve[sd]? (?:high|substantial|state-of-the-art)|exhibit[s]? (?:substantial|significant))"
)
_METHOD_DATASET_CUE = re.compile(
    r"(?i)\b(?:using (?:around |about |~)?\d|we (?:evaluate|benchmark|construct|train|build|"
    r"assemble|collect|curate)|dataset (?:of|comprising|containing)|\d[\d,\s]*\s*(?:calculations?|"
    r"samples?|structures?|configurations?|examples?|data\s?points?))"
)


def _conceptual_gap(text: str, evidence_present: str) -> tuple[str, str, str]:
    """Role-specific gap for a conceptual claim (results / methods / background)."""
    low = text.lower()
    if _RESULTS_REPORT_CUE.search(low):
        # A findings/results sentence that carries no concrete number: the gap is
        # the MISSING quantitative backing, not a boundary/prior-work issue.
        return (
            evidence_present,
            "The claim reports a qualitative finding but states no concrete evidence: "
            "the specific systems/models, the metric, and the magnitude that justify "
            "the outcome (e.g. what counts as 'high accuracy' vs 'substantial inaccuracy') are not given.",
            "State the per-result numbers behind the finding — which items, on what "
            "metric, at what magnitude and threshold — and where they are reported.",
        )
    if _METHOD_DATASET_CUE.search(low):
        # A methods/dataset sentence: the gap is provenance/coverage/protocol.
        return (
            evidence_present,
            "The methods/dataset claim needs provenance and coverage: the exact count, "
            "how the data was generated/sourced, what is covered, and the evaluation protocol.",
            "State the dataset provenance, exact size, coverage, and evaluation "
            "protocol (settings, splits) so the design can be checked and reproduced.",
        )
    # Default: a background / motivation / interpretation claim.
    return (
        evidence_present,
        "The conceptual claim needs a clearer boundary and stronger relation to prior work.",
        "Clarify what the claim excludes and tie it to the closest prior work in the related-work section.",
    )


# A concrete measured metric stated in the claim text: a named error/accuracy
# metric, or a numeric value with a recognizable unit (%, meV/atom, eV, ms, FPS,
# GPU-hours, points). Its presence means the claim is NOT "missing all metrics".
_HAS_CONCRETE_METRIC = re.compile(
    r"(?i)\b(?:mean absolute error|mean squared error|root mean squared? error|"
    r"\bm[as]e\b|\brmse\b|\bmape\b|absolute error|error of|error rate|accuracy of|"
    r"\bf1\b|\bauc\b|\bbleu\b|\brouge\b|\bmiou\b|perplexity|test set|held-out)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:%|mev|ev|kcal|ms|fps|gpu-hours?|points?|x)\b"
    r"|\b\d+(?:\.\d+)?\s*mev\s*/\s*(?:atom|[a-zÅ]+)\b"
)


# Unqualified superiority / absoluteness language that, without hedging or a
# stated scope, is an overclaim a referee must flag as a MAJOR soundness issue.
_OVERCLAIM_CUE = re.compile(
    r"(?i)(?:\bno downsides?\b|\bno drawbacks?\b|without any (?:downsides?|drawbacks?|cost)|"
    r"\balways wins?\b|\bnever regress\w*|\bnever loses?\b|"
    r"\bstrictly better\b|\boutperforms? all\b|\bbest (?:possible|in all)\b|"
    r"\bsuperior in every\b|\buniversally (?:better|superior|outperforms?)\b)"
)
# Hedging that legitimately qualifies a strong claim (then it is not an overclaim).
_HEDGE_CUE = re.compile(
    r"(?i)\b(?:may|might|can|could|often|typically|in our (?:tests|experiments|setting)|"
    r"on (?:these|the|three|four|five) (?:workloads?|benchmarks?|datasets?)|"
    r"under (?:the|these) (?:conditions?|assumptions?)|we observe|suggests?)\b"
)


def _overclaim_gap(claim_text: str, evidence_present: str) -> tuple[str, str, str] | None:
    """Return a MAJOR overclaim gap when a claim asserts unqualified superiority.

    A superiority/absoluteness assertion ("no downsides", "never regresses",
    "strictly better") with no scoping qualifier is an overclaim: the referee
    should require the authors to bound it or provide supporting evidence.
    Hedged/scoped versions ("improves throughput on three workloads") are NOT overclaims.
    """
    text = str(claim_text or "")
    if not _OVERCLAIM_CUE.search(text):
        return None
    # A cue that sits next to a scope qualifier is acceptable, not an overclaim.
    if _HEDGE_CUE.search(text):
        return None
    return (
        evidence_present,
        "Overclaim: the claim asserts unqualified superiority / absence of downsides "
        "without a stated scope or supporting evidence.",
        "Bound the claim to the tested settings and report where it does NOT hold "
        "(counterexamples, regressions, or limitations), or provide evidence for the "
        "absolute assertion.",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import read_jsonl, write_jsonl
    from tooling.review_artifacts import write_text
    from tooling.review_render import render_gap_report_markdown
    from tooling.review_text import parse_item_blocks

    workspace = Path(args.workspace).resolve()
    claims_path = workspace / "output" / "CLAIMS.md"
    if not claims_path.exists():
        raise SystemExit("evidence-auditor requires `output/CLAIMS.md`.")

    claims_jsonl = workspace / "output" / "CLAIMS.jsonl"
    if claims_jsonl.exists():
        claims = read_jsonl(claims_jsonl)
    else:
        claims = parse_item_blocks(claims_path.read_text(encoding="utf-8", errors="ignore"))
    if not claims:
        raise SystemExit("No claim blocks found in `output/CLAIMS.md`.")

    paper_path = workspace / "output" / "PAPER.md"
    paper_text = paper_path.read_text(encoding="utf-8", errors="ignore") if paper_path.exists() else ""
    results_context = _results_context(paper_text)

    gaps: list[dict[str, str]] = []
    for idx, claim in enumerate(claims, start=1):
        normalized_claim = {
            "id": str(claim.get("claim_id") or claim.get("id") or ""),
            "claim": str(claim.get("text") or claim.get("claim") or ""),
            "type": str(claim.get("claim_type") or claim.get("type") or ""),
            "source_pointer": str(claim.get("source_pointer") or claim.get("source") or ""),
        }
        context = _source_context(normalized_claim, paper_text)
        # For an EMPIRICAL claim whose own section lacks concrete numbers (e.g. a
        # headline claim in the Introduction), the substantiating evidence often
        # lives in the results/experiments section. Supply it so cross-section
        # evidence is not under-reported. Conceptual/method claims are NOT given
        # results context — they must not inherit unrelated result numbers.
        # Match the section NAME only. A pointer is '<section> | "<claim quote>"',
        # and the quote often contains a results word, which would otherwise read
        # as "already in the results section" and suppress the cross-section
        # evidence this lookup exists to supply. `_source_context` splits the same way.
        pointer_section = normalized_claim["source_pointer"].split("|", 1)[0]
        pointer_is_results = bool(_RESULTS_SECTION_CUE.search(pointer_section))
        cross_context = (
            results_context
            if normalized_claim["type"] == "empirical" and not pointer_is_results
            else ""
        )
        evidence_present = _evidence_present(normalized_claim["claim"], context, cross_context)
        overclaim = _overclaim_gap(normalized_claim["claim"], evidence_present)
        if overclaim is not None:
            _, gap, fix = overclaim
            severity = "major"
        else:
            _, gap, fix = _gap_for_claim(normalized_claim, evidence_present)
            severity = "major" if "underspecified" in gap.lower() else "minor"
        gaps.append(
            {
                "schema": "review-evidence-gap.v1",
                "gap_id": f"G{idx:02d}",
                "claim_id": normalized_claim["id"],
                "claim": normalized_claim["claim"],
                "evidence_present": evidence_present,
                "gap": gap,
                "minimal_fix": fix,
                "severity": severity,
            }
        )
    write_jsonl(workspace / "output" / "EVIDENCE_AUDIT.jsonl", gaps)
    write_text(workspace / "output" / "MISSING_EVIDENCE.md", render_gap_report_markdown(gaps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
