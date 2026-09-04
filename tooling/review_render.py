from __future__ import annotations

from collections import Counter
import re


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    def clean(value: object) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ").strip()

    lines = [
        "| " + " | ".join(clean(header) for header in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_claims_markdown(claims: list[dict[str, str]]) -> str:
    empirical = [c for c in claims if (c.get("claim_type") or c.get("type")) == "empirical"]
    conceptual = [c for c in claims if (c.get("claim_type") or c.get("type")) == "conceptual"]
    lines = ["# Claims", ""]
    for title, bucket in (("Empirical claims", empirical), ("Conceptual claims", conceptual)):
        lines.extend([f"## {title}", ""])
        if not bucket:
            lines.append("- (none)")
            lines.append("")
            continue
        for claim in bucket:
            claim_id = claim.get("claim_id") or claim.get("id", "")
            claim_text = claim.get("text") or claim.get("claim", "")
            claim_type = claim.get("claim_type") or claim.get("type", "")
            source = claim.get("source_pointer") or claim.get("source", "")
            lines.extend(
                [
                    f"### {claim_id}",
                    f"- Claim: {claim_text}",
                    f"- Type: {claim_type}",
                    f"- Scope: {claim['scope']}",
                    f"- Source: {source}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_gap_report_markdown(gaps: list[dict[str, str]]) -> str:
    lines = ["# Missing Evidence", ""]
    for gap in gaps:
        lines.extend(
            [
                f"### {gap.get('gap_id') or gap.get('id', '')}",
                f"- Claim ID: {gap['claim_id']}",
                f"- Claim: {gap['claim']}",
                f"- Evidence present: {gap['evidence_present']}",
                f"- Gap / concern: {gap['gap']}",
                f"- Minimal fix: {gap['minimal_fix']}",
                f"- Severity: {gap['severity']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_novelty_matrix_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Novelty Matrix",
        "",
        "| Claim ID | Claim | Closest related work | Overlap | Delta | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['claim_id']} | {row['claim']} | {row['related_work']} | {row['overlap']} | {row['delta']} | {row['evidence']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _summary_claim_sentence(claims: list[dict[str, str]] | None) -> str:
    """Pick the most informative real claim to anchor the referee Summary.

    Prefers an empirical claim from the Abstract/Introduction that carries a
    number (a concrete result), falling back to any empirical claim, then any
    claim. Returns a trimmed claim string, or "" when no usable claim exists.
    Deterministic (first match in claim order); no NL generation.
    """
    records = [c for c in (claims or []) if isinstance(c, dict)]

    def _text(c: dict) -> str:
        return str(c.get("text") or c.get("claim") or "").strip()

    def _type(c: dict) -> str:
        return str(c.get("claim_type") or c.get("type") or "").strip().lower()

    def _scope(c: dict) -> str:
        return str(c.get("scope") or "").strip().lower()

    def _has_number(c: dict) -> bool:
        return bool(re.search(r"[0-9]", _text(c)))

    front = ("abstract", "introduction")

    # A sentence opening with a refinement connective ("To further reduce ...",
    # "Additionally, we ...", "We also ...") describes a SECONDARY contribution,
    # not the paper's main one; deprioritize it when picking a headline.
    def _is_refinement(text: str) -> bool:
        return bool(
            re.match(
                r"(?i)^\s*(?:to further\b|additionally\b|moreover\b|furthermore\b|"
                r"we also\b|also,|in addition\b|beyond (?:this|that)\b)",
                text,
            )
        )

    # A primary-contribution sentence introduces the work itself: "we
    # develop/propose/present/introduce <X>", "we present <X>". Prefer one that is
    # NOT a refinement so the Summary anchors on the main contribution rather than
    # the first-listed claim (which may be a secondary detail).
    _CONTRIB = re.compile(
        r"(?i)\bwe\s+(?:develop|propose|present|introduce|design|build|construct)\b"
    )

    def _is_primary_contribution(c: dict) -> bool:
        t = _text(c)
        return bool(t) and bool(_CONTRIB.search(t)) and not _is_refinement(t)

    for pred in (
        lambda c: _type(c) == "empirical" and any(f in _scope(c) for f in front) and _has_number(c),
        lambda c: _type(c) == "empirical" and _has_number(c),
        lambda c: _type(c) == "empirical",
        # No empirical result: prefer the primary-contribution sentence over the
        # first-listed claim, and never anchor on a refinement sentence.
        _is_primary_contribution,
        lambda c: bool(_text(c)) and not _is_refinement(_text(c)),
        lambda c: bool(_text(c)),
    ):
        for c in records:
            if pred(c) and _text(c):
                return _text(c)
    return ""


def _clip_claim(text: str, *, limit: int = 110) -> str:
    """Clip a claim to a short reader-facing quote on a word boundary.

    Minor-Comment bullets identify their claim with a short quote; a full
    sentence would bloat the list. Cut at the last word boundary within `limit`
    (no mid-word cut, no ellipsis leak, matching the project's residue rules).
    """
    text = " ".join(str(text or "").split()).strip()
    if len(text) <= limit:
        return text
    head = text[:limit].rstrip()
    if " " in head:
        head = head[: head.rfind(" ")].rstrip()
    return head.rstrip(".,;:") or text[:limit].rstrip()


def _minor_gap_priority(gap: dict[str, str]) -> int:
    """Execution-priority rank for a Minor Comment (lower = act first).

    An author works the Minor Comments in order, so they must be sorted by how
    load-bearing / concrete the fix is, not by raw manuscript claim-id order.
    Ranking (most actionable first):
      0  a concrete result that only needs a baseline/protocol check (cheap, high-value)
      1  a dataset/method claim missing provenance/coverage (specific, checkable)
      2  a qualitative finding with no concrete evidence (needs new numbers)
      3  a conceptual claim needing a clearer boundary / relation to prior work (vaguest)
      4  anything else
    """
    body = (str(gap.get("gap") or gap.get("gap_concern") or "") + " " + str(gap.get("minimal_fix") or "")).lower()
    if "baseline/protocol check" in body or ("concrete result" in body and "baseline" in body):
        return 0
    if "provenance" in body or "dataset provenance" in body or ("coverage" in body and "protocol" in body):
        return 1
    if "no concrete evidence" in body or "qualitative finding" in body:
        return 2
    if "clearer boundary" in body or "relation to prior work" in body or "conceptual claim" in body:
        return 3
    return 4



def _related_work_label(work: str) -> str:
    """Reduce a related-work entry to a clean author phrase for reader-facing prose.

    The novelty matrix stores the FULL reference string for audit
    ("Behler and Parrinello. Generalized neural-network representation of
    potential energy surfaces. 2007."). Pasted verbatim into a referee sentence,
    its internal periods create false sentence breaks — the prose appears to end
    at "Behler and Parrinello." with the title and year dangling as a fragment
    (flagged in review). Reduce it to just the author phrase:
    the leading "<Surname> et al." / two-author "<Surname> and <Surname>" /
    single "<Surname>" token, dropping the title and year. Falls back to the
    original text when no author phrase is parseable.
    """
    w = " ".join(str(work or "").split()).strip()
    if not w:
        return ""
    # Strip a leading list marker ("- ", "* ", "1. ").
    w = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", w)
    m = re.match(
        r"([A-Z][A-Za-z\-']+)"
        r"(?:\s+et\s+al\.?"  # "Behler et al."
        r"|\s+and\s+([A-Z][A-Za-z\-']+))?",  # "Behler and Parrinello"
        w,
    )
    if not m:
        return w.rstrip(".")
    if m.group(1) and w[m.start():].lower().startswith(m.group(1).lower() + " et al"):
        return f"{m.group(1)} et al."
    if m.group(2):
        return f"{m.group(1)} and {m.group(2)}"
    return m.group(1)


def _trim_overlap_author_echo(overlap: str, related: str) -> str:
    """Drop a restatement of the related work's author phrase from the overlap.

    The overlap clause is rendered in parentheses immediately after the work's
    author phrase ("... positions itself against Behler and Parrinello (<overlap>)").
    The overlap prose, taken from the manuscript's Related Work, frequently names
    the same authors again ("The neural-network potential framework of Behler and
    Parrinello introduced ..."), so the name appears twice in one sentence. Reduce the overlap to what the work DOES: drop the
    author phrase (and a leading "The <noun> of" / "framework of" scaffold), so the
    parenthetical reads as a description, not a second citation.
    """
    text = " ".join(str(overlap or "").split()).strip()
    if not text or not related:
        return text
    surname = related.split()[0]
    if surname.lower() not in text.lower():
        return text
    # "<lead-in> of Behler and Parrinello introduced X" -> "introduced X".
    escaped = re.escape(related)
    m = re.search(rf"(?i)\b(?:of\s+)?{escaped}\s+(.+)$", text)
    if m and m.group(1).strip():
        return m.group(1).strip()
    # "Behler and Parrinello introduced X" at the very start -> "introduced X".
    m = re.match(rf"(?i)\s*{escaped}\s+(.+)$", text)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return text


# Verbs a description can START with — then "which <text>" is already grammatical.
_OVERLAP_LEADING_VERBS = frozenset(
    {
        "introduced",
        "introduces",
        "proposed",
        "proposes",
        "studied",
        "studies",
        "study",
        "addressed",
        "addresses",
        "address",
        "developed",
        "develops",
        "updated",
        "updates",
        "models",
        "modeled",
        "modelled",
        "benchmarked",
        "presents",
        "presented",
        "extends",
        "extended",
        "combines",
        "combined",
        "targets",
        "targeted",
        "uses",
        "used",
        "applies",
        "applied",
    }
)


def _as_relative_clause(overlap: str) -> str:
    """Make `overlap` grammatical after a leading "which".

    A trimmed overlap that already starts with a verb ("introduced atom-centered
    symmetry functions") reads correctly as "which introduced ...". A noun-phrase
    overlap ("adjacent setting", "neural-network potentials for energy surfaces")
    does not, so prefix a neutral verb -> "which addresses <noun phrase>".
    """
    text = " ".join(str(overlap or "").split()).strip()
    if not text:
        return text
    first = re.sub(r"[^A-Za-z]", "", text.split()[0]).lower()
    if first in _OVERLAP_LEADING_VERBS:
        return text
    return f"addresses {text}"


def render_rubric_review_markdown(
    *,
    claim_count: int,
    gap_count: int,
    major_gaps: list[dict[str, str]],
    novelty_available: bool,
    claims: list[dict[str, str]] | None = None,
    novelty_row: dict[str, str] | None = None,
    minor_gaps: list[dict[str, str]] | None = None,
) -> str:
    # Recommendation must be coherent with the concern severity the report itself
    # states: a report with 0 major concerns is an accept-with-minor-revisions
    # situation and must lean positive; major concerns lean negative. (An overclaim
    # or other genuine soundness problem is surfaced as a MAJOR gap upstream —
    # so it correctly lands in the weak-reject branch rather than a bland
    # borderline.) The verdict is rendered as reader-facing prose near the end of
    # the report (see the Recommendation section), not a bare enum label here.
    # Ground novelty in a concrete matrix row (closest related work + delta) when
    # one is available, rather than only stating that a matrix exists.
    _nov_related = str(novelty_row.get("related_work") or "").strip() if isinstance(novelty_row, dict) else ""
    if _nov_related and "unavailable" in _nov_related.lower():
        # The manuscript has no related-work / references section, so novelty
        # cannot be positioned. Say so honestly rather than printing the sentinel
        # ("Closest related work is related works unavailable ...").
        novelty_note = (
            "Novelty could not be positioned: the manuscript provides no related-work or "
            "references section to compare against."
        )
    elif isinstance(novelty_row, dict) and _nov_related:
        related = _related_work_label(_nov_related)
        delta = str(novelty_row.get("delta") or "").strip() or "the claimed delta needs verification"
        overlap = _trim_overlap_author_echo(str(novelty_row.get("overlap") or "").strip(), related)
        # Render the overlap as a relative clause on "the work of <authors>", so the
        # description reads as prose rather than a bare-verb parenthetical dangling
        # after the author names ("... against Behler and Parrinello (introduced ...)").
        if overlap:
            work_phrase = f"the work of {related}, which {_as_relative_clause(overlap)}"
        else:
            work_phrase = f"the work of {related}"
        novelty_note = (
            f"The manuscript positions itself against {work_phrase}; "
            f"the stated advance over it is {delta}. This is one of the prior works the "
            "manuscript cites, and may not be the most directly comparable."
        )
    elif novelty_available:
        novelty_note = "Novelty was assessed conservatively from the available novelty matrix."
    else:
        novelty_note = "Novelty matrix was unavailable; novelty is therefore conservative."
    # Anchor the Summary in the paper's own strongest claim, so a referee sees
    # what the manuscript actually asserts. The Summary states the paper's
    # headline claim ONLY — no parenthetical about how many claims the review
    # examined or how it examined them; that is review-process meta-commentary
    # (and, worse, exposed pipeline machinery). The claim/concern counts already
    # surface in the Soundness line for a reader who wants them.
    headline = _summary_claim_sentence(claims)
    if headline:
        summary_line = f"- The paper's headline claim is: \"{headline}\""
    else:
        summary_line = (
            f"- The paper advances {claim_count} main contribution(s), assessed here "
            "against the evidence the manuscript provides."
        )
    # Ground the Clarity note in the specific claim behind the first concern,
    # rather than a generic sentence, so a referee sees WHICH claim is at risk.
    claim_text_by_id: dict[str, str] = {}
    for c in claims or []:
        if isinstance(c, dict):
            cid = str(c.get("claim_id") or c.get("id") or "").strip()
            ctext = str(c.get("text") or c.get("claim") or "").strip()
            if cid and ctext:
                claim_text_by_id[cid] = ctext
    # A purely-conceptual / position paper (no empirical claim) must not be
    # framed with empirical-paper language ("result", "reproduce", "protocol,
    # metric"). Detect it so Summary/Clarity/Impact adapt.
    _types = [
        str(c.get("claim_type") or c.get("type") or "").strip().lower()
        for c in (claims or []) if isinstance(c, dict)
    ]
    paper_is_conceptual = bool(_types) and not any(t == "empirical" for t in _types)
    # The word for the paper's headline: a conceptual paper contributes a
    # framework/argument, not a measured "result".
    headline_noun = "headline contribution" if paper_is_conceptual else "headline result"
    focus_gap = major_gaps[0] if major_gaps else None
    # When there is no MAJOR gap, fall back to the first MINOR gap so the Clarity
    # dimension can still ground in a specific claim (the Soundness line already
    # surfaces this same claim via its own minor-gap branch). Otherwise Clarity
    # drops to a generic "each top claim should state its protocol..." template
    # that reads identically for any paper while Soundness names claim C01 —
    # an inconsistent, partly-ungrounded report.
    if focus_gap is None:
        focus_gap = next(
            (g for g in (minor_gaps or []) if isinstance(g, dict) and str(g.get("claim_id") or "").strip()),
            None,
        )
    focus_claim_id = str(focus_gap.get("claim_id", "")).strip() if focus_gap else ""
    focus_claim_text = claim_text_by_id.get(focus_claim_id, "")
    # A conceptual paper's claims are judged on boundary + relation to prior
    # work, not on empirical protocol/metric.
    clarity_expectation = (
        "state its scope boundary and relation to prior work explicitly"
        if paper_is_conceptual
        else "state its protocol, metric, and boundary explicitly"
    )
    clarity_expectation_present = (
        "states its scope boundary and relation to prior work explicitly"
        if paper_is_conceptual
        else "states its protocol, metric, and boundary explicitly"
    )
    if focus_claim_text:
        clarity_line = (
            f"- The sharpest clarity risk is claim {focus_claim_id}: "
            f"\"{focus_claim_text}\" — it should {clarity_expectation}."
        )
    elif focus_claim_id:
        clarity_line = (
            f"- The sharpest clarity risk is claim {focus_claim_id}: it should {clarity_expectation}."
        )
    else:
        clarity_line = f"- The main clarity risk is whether each top claim {clarity_expectation_present}."
    # Ground Soundness in the load-bearing concern — WHICH claim's evidence is
    # weakest and why — not just a count, so a referee learns what is unsound.
    n_major = len(major_gaps)
    n_minor_raw = max(0, gap_count - n_major)
    # The Minor Comments section lists DEDUPLICATED distinct minor concerns, so
    # the Soundness count must match what the reader will actually see there,
    # not the raw gap total (a whole-report coherence defect otherwise: "5 minor"
    # in Soundness vs 2 listed in Minor Comments).
    _distinct_minor_keys: set[str] = set()
    for _g in minor_gaps or []:
        if not isinstance(_g, dict):
            continue
        _body = str(_g.get("gap") or _g.get("gap_concern") or _g.get("minimal_fix") or "").strip().lower()
        if _body:
            _distinct_minor_keys.add(_body)
    n_minor = len(_distinct_minor_keys) if minor_gaps else n_minor_raw
    # Report the count the reader will actually see in Minor Comments (the distinct
    # count), in referee language. Do NOT expose the raw pre-dedup total via a
    # "(from N minor gap(s))" parenthetical — "gap" is the pipeline's internal
    # extraction term and "8 deduplicated to 2" is process bookkeeping the
    # manuscript's authors/editor do not need (same process-residue class as the
    # Summary "extracted claim(s)").
    if n_major == 1:
        _major_phrase = "1 major concern"
    else:
        _major_phrase = f"{n_major} major concerns"
    if n_minor == 1:
        _minor_phrase = "1 minor concern"
    else:
        _minor_phrase = f"{n_minor} minor concerns"
    count_clause = f"The review surfaced {_major_phrase} and {_minor_phrase}"
    focus_concern = str(focus_gap.get("gap") or "").strip() if focus_gap else ""
    concern_tail = focus_concern.rstrip(".") if focus_concern else "its evidence chain is not yet strong enough for acceptance"
    if focus_claim_id and focus_claim_text:
        soundness_line = (
            f"- {count_clause}; the load-bearing soundness gap is on claim {focus_claim_id} "
            f"(\"{focus_claim_text}\"): {concern_tail}."
        )
    elif focus_claim_id:
        soundness_line = (
            f"- {count_clause}; the load-bearing soundness gap is on claim {focus_claim_id}: {concern_tail}."
        )
    elif minor_gaps:
        first_minor = next((g for g in minor_gaps if isinstance(g, dict) and str(g.get("gap") or "").strip()), None)
        if first_minor:
            minor_concern = str(first_minor.get("gap") or "").strip().rstrip(".")
            minor_id = str(first_minor.get("claim_id") or "").strip()
            minor_anchor = f"claim {minor_id}: {minor_concern}" if minor_id else minor_concern
            soundness_line = f"- {count_clause}; no major concern, but {minor_anchor}."
        else:
            soundness_line = f"- {count_clause}; no major concern blocks acceptance."
    else:
        soundness_line = f"- {count_clause}; no evidence issue blocks soundness."
    # Ground Impact in THIS manuscript's headline result and closest related
    # work, so the "if fixed" statement is about the paper's actual contribution
    # rather than a sentence identical across every manuscript.
    related = _related_work_label(str(novelty_row.get("related_work") or "").strip()) if isinstance(novelty_row, dict) else ""
    if paper_is_conceptual:
        # A position/framework paper is not "reproduced"; its impact is whether
        # the argument is sharpened and clearly positioned against prior work.
        if headline and related:
            impact_line = (
                f"- The {headline_noun} (\"{headline}\") is positioned relative to a cited prior work ({related}); "
                "sharpening its boundaries and testable predictions would strengthen the argument."
            )
        elif headline:
            impact_line = (
                f"- The {headline_noun} (\"{headline}\") would have more impact if its scope "
                "and testable predictions were made explicit and tied to prior work."
            )
        else:
            impact_line = (
                "- The contribution would have more impact with sharper boundaries and explicit "
                "positioning against prior work."
            )
    elif major_gaps and headline and related:
        impact_line = (
            f"- If the {n_major} major issue(s) are resolved, the {headline_noun} "
            f"(\"{headline}\") could be verified against {related.rstrip('.')} and its claimed "
            "delta confirmed rather than asserted."
        )
    elif major_gaps and headline:
        impact_line = (
            f"- If the {n_major} major issue(s) are resolved, the {headline_noun} "
            f"(\"{headline}\") could be confirmed rather than asserted, making the "
            "contribution easier to compare and reproduce."
        )
    elif major_gaps:
        impact_line = (
            f"- If the {n_major} major issue(s) are resolved, the contribution's {headline_noun} "
            "could be confirmed rather than asserted and made easier to compare and reproduce."
        )
    elif headline and related:
        impact_line = (
            f"- The {headline_noun} (\"{headline}\") is positioned relative to a cited prior work ({related}); "
            "with the remaining minor gaps closed it would be straightforward to compare and reproduce."
        )
    elif headline:
        impact_line = (
            f"- With the remaining evidence gaps closed, the {headline_noun} "
            f"(\"{headline}\") would be easier to compare and reproduce."
        )
    else:
        impact_line = (
            "- With the remaining evidence gaps closed, the contribution would be easier to compare and reproduce."
        )
    lines = [
        "# Review",
        "",
        "### Summary",
        summary_line,
        "",
        "### Novelty",
        f"- {novelty_note}",
        "",
        "### Soundness",
        soundness_line,
        "",
        "### Clarity",
        clarity_line,
        "",
        "### Impact",
        impact_line,
        "",
        "### Major Concerns",
    ]
    if major_gaps:
        for gap in major_gaps:
            lines.extend(
                [
                    f"- Claim {gap.get('claim_id', 'unknown')} / Gap {gap.get('gap_id', 'unknown')}: {gap['gap']}",
                    "- Why it matters: the current evidence chain is not strong enough for a confident acceptance decision.",
                    f"- Minimal fix: {gap['minimal_fix']}",
                ]
            )
    else:
        lines.append("- (none)")
    lines.extend(["", "### Minor Comments"])
    # Surface the ACTUAL minor gaps (deduplicated, tied to their claim), not a
    # repeat of the major concerns' fixes. Fall back to the prior generic note
    # only when no structured minor gaps are available.
    rendered_minor = False
    if minor_gaps:
        # Order by execution priority (not raw manuscript claim-id order): an author
        # acts on the list top-down, so the most actionable/load-bearing fixes lead.
        # Stable within a rank by original position.
        ordered_minor = sorted(
            enumerate(minor_gaps),
            key=lambda iv: (_minor_gap_priority(iv[1]) if isinstance(iv[1], dict) else 99, iv[0]),
        )
        # When there is NO major gap, the focus (load-bearing) claim is already
        # surfaced verbatim in BOTH Soundness and Clarity. Repeating its full concern
        # as a Minor Comment tells the author the same thing a third time. Render that
        # one bullet as a back-reference ("already detailed under Soundness/Clarity
        # above") instead of a verbatim repeat — this keeps the Soundness<->Minor
        # count coherent while removing the triple-repeat. Only when
        # OTHER distinct minor concerns exist to lead the list; if the focus claim is
        # the only minor, show its concern normally (a back-reference would be circular
        # and would drop the sole concern's text).
        _distinct_bodies = {
            str(g.get("gap") or g.get("gap_concern") or g.get("minimal_fix") or "").strip().lower()
            for g in minor_gaps if isinstance(g, dict)
            and str(g.get("gap") or g.get("gap_concern") or g.get("minimal_fix") or "").strip()
        }
        crossref_focus = (not major_gaps) and bool(focus_claim_id) and len(_distinct_bodies) > 1
        seen_minor: set[str] = set()
        for _idx, gap in ordered_minor:
            concern = str(gap.get("gap") or gap.get("gap_concern") or "").strip()
            fix = str(gap.get("minimal_fix") or "").strip()
            claim_id = str(gap.get("claim_id") or "").strip()
            body = concern or fix
            if not body:
                continue
            key = body.lower()
            if key in seen_minor:
                continue
            seen_minor.add(key)
            prefix = f"Claim {claim_id}: " if claim_id else ""
            # Identify WHICH manuscript statement the comment targets. A bare
            # "Claim C02:" is unactionable — the reader cannot tell which claim
            # it refers to (the claim text is not otherwise shown in this
            # section). The claim text is already in hand via claim_text_by_id;
            # quote a clipped form so each bullet stays readable.
            claim_quote = _clip_claim(claim_text_by_id.get(claim_id, "")) if claim_id else ""
            quote = f'("{claim_quote}") ' if claim_quote else ""
            if crossref_focus and claim_id and claim_id == focus_claim_id:
                # The load-bearing concern is spelled out in Soundness + Clarity; here
                # just point to it so the action list is not a verbatim third copy.
                lines.append(
                    f"- {prefix}{quote}addressed under Soundness and Clarity above — "
                    "resolve that load-bearing concern first."
                )
            else:
                suffix = f" Fix: {fix}" if fix and fix.lower() != body.lower() else ""
                lines.append(f"- {prefix}{quote}{body}{suffix}")
            rendered_minor = True
    if not rendered_minor:
        if gap_count and major_gaps:
            # No structured minor gaps: echo the distinct major fixes as guidance.
            seen_fix: set[str] = set()
            for gap in major_gaps[:3]:
                fix = str(gap.get("minimal_fix") or "").strip()
                if fix and fix.lower() not in seen_fix:
                    seen_fix.add(fix.lower())
                    lines.append(f"- {fix}")
            if not seen_fix:
                lines.append("- Clarify the strongest remaining evidence gaps and manuscript boundaries.")
        elif gap_count:
            lines.append("- Clarify the strongest remaining evidence gaps and manuscript boundaries.")
        else:
            lines.append("- (none)")
    # Render the recommendation as reader-facing referee prose tied to the report's
    # own concern profile, not a bare machine enum label ("weak_accept") that an
    # author/editor reads as pipeline output. The verdict phrase leads the sentence
    # so the decision is still unambiguous (and greppable).
    if major_gaps:
        _n_major = len(major_gaps)
        _major_word = "major concern" if _n_major == 1 else "major concerns"
        recommendation_line = (
            f"Weak reject: {_n_major} {_major_word} must be resolved before the "
            f"manuscript can be accepted."
        )
    else:
        if n_minor == 0:
            _minor_clause = "no outstanding concerns"
        elif n_minor == 1:
            _minor_clause = "1 minor concern to address in revision"
        else:
            _minor_clause = f"{n_minor} minor concerns to address in revision"
        recommendation_line = (
            f"Weak accept: no major concerns, {_minor_clause}."
        )
    lines.extend(["", "### Recommendation", f"- {recommendation_line}"])
    return "\n".join(lines).rstrip() + "\n"


_LENS_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "with", "under", "in", "on", "to",
    "using", "via", "based", "study", "studies", "survey", "review", "analysis",
    "approach", "approaches", "method", "methods",
}


def _depluralize(token: str) -> str:
    """Crude singular form so "shifts" matches the goal's "shift"."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _lens_content_tokens(title: str) -> set[str]:
    """Significant, singular word tokens of a candidate lens/goal (drops function words)."""
    return {
        _depluralize(t) for t in re.findall(r"[a-z0-9]+", str(title or "").lower())
        if len(t) >= 3 and t not in _LENS_STOPWORDS
    }


def _brief_comparison_lenses(sections: list[str], goal: str) -> list[str]:
    """Genuine differentiating comparison lenses from the outline sections.

    A comparison lens must be an AXIS the reader can compare papers along — not a
    restatement of the whole topic. On a corpus where every paper shares the topic
    (e.g. all "test-time adaptation"), the outline can surface a section titled with
    the topic itself ("Test Time Adaptation") plus a fragment of it ("Shifts" from
    "distribution shift"); listing those as "Comparison lenses" tells the reader
    nothing. Keep a section title only when it has at least one significant content
    token NOT already in the goal topic (i.e. it adds a dimension). Singular/plural
    is normalized so "Shifts" is recognized as the topic's "shift". Returns up to 3;
    the caller falls back to a generic lens phrase when none qualify.
    """
    goal_tokens = _lens_content_tokens(goal)
    kept: list[str] = []
    for title in sections:
        if title.strip().lower() in {"introduction", "related work", "conclusion"}:
            continue
        toks = _lens_content_tokens(title)
        if not toks:
            continue  # nothing significant (all function words)
        if toks <= goal_tokens:
            continue  # restates the topic / a fragment of it — not a comparison axis
        kept.append(title)
        if len(kept) >= 3:
            break
    return kept


# Verbs/openers that already make a goal read as a stated OUTCOME the brief
# delivers ("Produce a brief on X", "Survey X", "Orient the reader to X").
_OUTCOME_OPENERS = (
    "produce", "provide", "deliver", "orient", "summarize", "summarise", "survey",
    "review", "map", "compare", "assess", "characterize", "characterise", "outline",
    "identify", "synthesize", "synthesise", "trace", "give", "build", "compile",
    "catalogue", "catalog", "explain",
)


def _normalize_requested_outcome(goal: str) -> str:
    """Turn the raw goal into a declarative 'Requested outcome' statement.

    Echoing the raw goal verbatim leaks prompt residue into the finished brief: a question to the assistant ("Can you find me the key papers ...?"),
    first-person chatter ("I need ... help me get oriented"), or a bare keyword
    fragment ("test-time adaptation distribution shift") all read as the original
    prompt, not an outcome. A clean declarative request ("Produce a compact brief
    on X ...") is left untouched. Otherwise recast into "Orient the reader to
    <topic>." on the goal's own topic words.
    """
    text = " ".join(str(goal or "").replace("# Goal", "").split()).strip()
    if not text:
        return "Orient the reader to the target topic."
    low = text.lower()
    first = re.sub(r"[^a-z]", "", low.split(" ", 1)[0]) if low else ""

    # Already a declarative request that opens with an outcome verb -> keep as-is.
    is_question = text.rstrip().endswith("?") or bool(
        re.match(r"(?i)^(?:can|could|would|will|please|help|how|what|which|do|does)\b", text)
    )
    is_first_person = bool(re.match(r"(?i)^(?:i|we|my|our)\b", text)) or bool(
        re.search(r"(?i)\b(?:help me|for my|i need|i want|i'?m|orient me)\b", text)
    )
    if first in _OUTCOME_OPENERS and not is_question and not is_first_person:
        return text if text.endswith((".", "!")) else text + "."

    # Prompt residue (question / first-person / bare fragment): recast to a
    # neutral declarative outcome on the goal's topic. Strip a leading
    # conversational wrapper and trailing chatter, keep the topical remainder.
    topic = text
    topic = re.sub(
        r"(?i)^(?:can you|could you|would you|will you|please|help me(?:\s+to)?|"
        r"i(?:'|\s)?(?:d like|would like|need|want|'m looking) to|i need|i want|"
        r"i'?m trying to|we (?:need|want) to)\s+",
        "",
        topic,
    ).strip()
    topic = re.sub(
        r"(?i)^(?:find (?:me )?|get (?:me )?|give (?:me )?|show (?:me )?|understand |"
        r"learn about |look into |orient me (?:on|to|about) )",
        "",
        topic,
    ).strip()
    # Drop trailing meta-chatter clauses ("..., help me get oriented", "for my thesis").
    topic = re.split(
        r"(?i),?\s+(?:help me\b|for my\b|so (?:i|we)\b|because (?:i|we)\b)", topic, maxsplit=1
    )[0].strip()
    topic = topic.rstrip(" .?!,")
    if not topic:
        return "Orient the reader to the target topic."
    # Lowercase the leading letter only when it is an ordinary capitalized word,
    # NOT an acronym/all-caps token ("TTA" must stay "TTA", not "tTA").
    first_word = topic.split(" ", 1)[0]
    if first_word.isupper() or (len(first_word) > 1 and first_word[1:].lower() != first_word[1:]):
        lead = topic
    else:
        lead = topic[0].lower() + topic[1:]
    return f"Orient the reader to {lead}."


def render_research_brief_markdown(*, goal: str, papers: list[dict[str, str]], sections: list[str]) -> str:
    chosen = papers[: min(8, len(papers))]
    n_themes = min(6, len(chosen))
    lenses = _brief_comparison_lenses(sections, goal)
    lens_text = ", ".join(lenses) if lenses else "methods, evaluation, and deployment risks"
    request = _normalize_requested_outcome(goal)
    # chosen[0] is the FIRST core-set paper (core-set order), not a topically-chosen
    # anchor for the whole area — presenting it as "the boundary is anchored by X"
    # overclaims a representativeness judgment the tool never made (a narrow first
    # paper then reads as anchoring a broad topic). Describe it accurately as the
    # entry-point/first listed core paper the reader can start from.
    scope_anchor = f" The first listed paper is [{_brief_pointer(chosen[0])}]." if chosen else ""
    # Disclose both the selected core-set size AND how many are highlighted
    # below, so the stated count is consistent with the visible citations (a
    # whole-document coherence defect otherwise: "12 selected" but only 6 shown).
    if len(papers) > n_themes:
        boundary_line = (
            f"- Evidence boundary: a focused orientation over {len(papers)} selected "
            f"papers, with the {n_themes} most representative highlighted below (not an "
            f"exhaustive literature claim).{scope_anchor}"
        )
    else:
        boundary_line = (
            f"- Evidence boundary: this is a focused orientation based on {len(papers)} selected "
            f"papers, not an exhaustive literature claim.{scope_anchor}"
        )

    lines = [
        "# Research Brief",
        "",
        "## Scope",
        f"- Requested outcome: {request}",
        boundary_line,
        f"- Comparison lenses: {lens_text}.",
        "",
        "## Key themes",
    ]
    for paper in chosen[:6]:
        pointer = _brief_pointer(paper)
        abstract = str(paper.get("abstract") or "").strip()
        insight = _brief_summary(abstract, max_words=45) or f"Use this paper to understand {paper.get('title') or 'the topic'}"
        lines.append(f"- {insight.rstrip('.')} [{pointer}].")

    lines.extend(["", "## What to read first"])
    # A READING PATH, not a repeat of Key themes: give each entry a sequencing
    # reason (where it sits in the order + what to take from it) rather than
    # re-printing the same _brief_summary sentence the Key-themes bullet already
    # shows. Reciting the summary twice makes the two sections redundant.
    read_first = chosen[: min(4, len(chosen))]
    _ORDINALS = ("Start here", "Read next", "Then", "Finally")
    # Distinct sequencing notes for the MIDDLE steps: reusing one static reason for
    # every non-first/non-last entry made adjacent steps ("Read next" and "Then")
    # read as verbatim boilerplate. Advance each middle step through the
    # comparison lenses when they exist, else give a position-distinct role.
    _MIDDLE_FALLBACKS = (
        "compare its approach against the entry point before moving on",
        "contrast it with the earlier papers to see where the approaches diverge",
        "round out the middle of the path before the closing risks",
    )

    def _middle_reason(pos: int) -> str:
        # pos is 0-based among middle steps. Prefer a lens not already used by the
        # "Start here" entry (lenses[0]); fall back to a position-distinct note.
        rest_lenses = lenses[1:] if len(lenses) > 1 else []
        if pos < len(rest_lenses):
            return f"read it through the {rest_lenses[pos]} lens to compare approaches across the selected set"
        return _MIDDLE_FALLBACKS[min(pos, len(_MIDDLE_FALLBACKS) - 1)]

    for index, paper in enumerate(read_first):
        pointer = _brief_pointer(paper)
        ordinal = _ORDINALS[index] if index < len(_ORDINALS) else f"Item {index + 1}"
        if index == 0:
            reason = (
                f"it is the entry point for the topic and frames the "
                f"{lenses[0] if lenses else 'methods'} lens the rest build on"
            )
        elif index == len(read_first) - 1:
            reason = "read last to see where the open problems and risks concentrate"
        else:
            reason = _middle_reason(index - 1)
        lines.append(f"- {ordinal} — {pointer}: {reason}.")

    lines.extend(["", "## Open problems / risks"])
    for bullet in _brief_risk_bullets(lenses=lenses, papers=chosen, highlighted=n_themes):
        lines.append(f"- {bullet}")
    return "\n".join(lines).rstrip() + "\n"


# Genuinely topic-independent methodological caveats: they describe the briefing
# METHOD (compact core set, abstract-level orientation), not the subject matter,
# so they honestly apply to every brief.
_BRIEF_UNIVERSAL_RISKS = (
    "The selected set is deliberately compact; missing terminology or adjacent communities can still change the topic boundary.",
    "Abstract-level descriptions are useful for orientation but cannot support strong causal, comparative, or reproducibility claims without full-text checking.",
)

_LIMITATION_CUE = re.compile(
    r"(?i)\b(?:limitation|limitations|caveat|confound(?:s|ing)?|does not|do not|"
    r"cannot|can't|fails? to|struggles? (?:to|with)|unclear|restricted to|"
    r"constrained to|assumes?|remains? (?:an? )?(?:open|challenge|unresolved)|"
    r"still (?:struggl|fail|lack)|not (?:yet |consistently )?)\b"
)

# A sentence that reads as motivation / a positive property is NOT a limitation,
# even if it happens to contain a weak cue word like "only". The "not only ... but
# also" / "not just" / "not merely" constructions are rhetorical motivation ("X
# demands not only fluency but also transparency"), NOT a reported limitation — the
# bare "not" cue in _LIMITATION_CUE would otherwise mislabel them.
_POSITIVE_FRAMING = re.compile(
    r"(?i)\b(?:promising|making it|advantage|advantages|benefit|benefits|enables?|"
    r"strength|well[- ]suited|effective(?:ly)?|state[- ]of[- ]the[- ]art|"
    r"outperform|not only|not just|not merely|not simply)\b"
)


def _brief_risk_bullets(*, lenses: list[str], papers: list[dict[str, str]], highlighted: int = 0) -> list[str]:
    """Build the Open-problems bullets from THIS brief's lenses + evidence.

    The two universal caveats describe the briefing method and always apply. The
    remaining bullets are derived from the run's own comparison lenses and the
    in-scope papers' stated limitations (NO NEW FACTS), so the section varies
    with the topic instead of repeating hardcoded, domain-mislabeled boilerplate.

    ``highlighted`` is how many papers are already surfaced in "Key themes"
    (chosen[:highlighted]); the limitation bullet prefers a paper OUTSIDE that set
    so Open-problems adds a NEW paper's risk instead of repeating a Key-themes
    sentence verbatim. It falls back to the highlighted papers only when no
    non-highlighted paper states a limitation.
    """

    bullets = list(_BRIEF_UNIVERSAL_RISKS)

    if lenses:
        lens_phrase = _join_human(lenses[:3])
        bullets.append(
            f"Findings across {lens_phrase} should be compared on common ground "
            "before turning this briefing into a larger evidence synthesis."
        )

    # Surface one concrete limitation the selected papers themselves state,
    # rather than a generic risk sentence. Deterministic: first cued sentence in
    # core-set order, but preferring a paper NOT already highlighted in Key themes
    # (so this bullet is not a verbatim repeat of a Key-themes sentence), then
    # falling back to the highlighted papers.
    tail = papers[highlighted:] if highlighted else []
    for group in (tail, papers):
        limitation_bullet = _first_limitation_bullet(group)
        if limitation_bullet:
            bullets.append(limitation_bullet)
            break

    return bullets


def _first_limitation_bullet(papers: list[dict[str, str]]) -> str:
    """First stated limitation (cued, non-positive) in core-set order, as a bullet."""
    for paper in papers:
        abstract = str(paper.get("abstract") or "").strip()
        for sentence in re.split(r"(?<=[.!?])\s+", abstract):
            sentence = sentence.strip()
            if (
                sentence
                and _LIMITATION_CUE.search(sentence)
                and not _POSITIVE_FRAMING.search(sentence)
            ):
                pointer = _brief_pointer(paper)
                limitation = _brief_summary(sentence, max_words=32) or sentence
                return f"Reported limitation to weigh: {limitation.rstrip('.')} [{pointer}]."
    return ""


def _join_human(items: list[str]) -> str:
    items = [item.strip() for item in items if item.strip()]
    if not items:
        return "the comparison lenses"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _brief_pointer(paper: dict[str, str]) -> str:
    paper_id = str(paper.get("paper_id") or "unknown").strip()
    title = str(paper.get("title") or "Untitled paper").strip()
    url = str(paper.get("url") or "").strip()
    return f"{paper_id} - {title}" + (f" ({url})" if url else "")


def _brief_summary(text: str, *, max_words: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ""

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", clean)
        if sentence.strip()
    ]
    action_pattern = re.compile(
        r"(?i)\b(?:we|the authors?|this (?:paper|work|study|survey|review)|our (?:research|approach|method|work))\s+"
        r"(?:propose|present|introduce|develop|demonstrate|evaluate|show|find|review|"
        r"construct|build|design|derive|create|train|formulate|describe|report|"
        r"provide|establish|extend|achieve|achieved|use|objective|"
        r"benchmark|assess|quantify|measure|compare|analyze|analyse|investigate|explore)s?\b"
    )
    result_pattern = re.compile(
        r"(?i)\b(?:results?|experiments?|evaluation|findings?)\b.*\b"
        r"(?:show|demonstrate|improve|outperform|reveal|indicate)s?\b"
    )
    focus_pattern = re.compile(
        r"(?i)\b(?:adaptation|distribution shift|out-of-distribution|sim-to-real|"
        r"continual learning|deployment|transfer)\b"
    )
    # A leading field-background / motivation opener ("X has been applied for
    # decades", "X is widely used", "X plays a key role") is NOT a contribution —
    # it could precede any paper on the topic. Penalize it so the summary picks
    # the paper's actual contribution sentence instead. Also covers two openers a
    # real abstract often leads with before its contribution: "X have (recently)
    # emerged as ..." and a problem-statement ("Y is generally not well known",
    # "Z remains challenging", "traditional methods are costly").
    background_pattern = re.compile(
        r"(?i)\b(?:has|have) been (?:widely |ubiquitously |extensively |commonly )?"
        r"(?:applied|used|studied|explored|adopted|investigated|demonstrated)\b"
        r"|\b(?:is|are) (?:a |an )?(?:widely|ubiquitous|central|fundamental|popular|"
        r"versatile|key|crucial|essential|important|promising)\b"
        r"|\bfor decades\b|\bin recent years\b|\bhas attracted\b|\bhas emerged\b"
        r"|\b(?:has|have) (?:recently |long )?emerged\b"
        r"|\b(?:is|are) (?:generally |often |still |typically )?not (?:well[- ])?"
        r"(?:known|understood|characterized|established)\b"
        r"|\bremains? (?:experimentally |computationally )?(?:challenging|difficult|"
        r"elusive|unclear|an open)\b"
        r"|\b(?:is|are) (?:costly|inefficient|expensive|time-consuming)\b"
        r"|\bin the era of\b|\bwith the (?:rise|advent|proliferation|growth) of\b"
        r"|\bplays? an? (?:key|central|important|crucial) role\b"
    )

    def sentence_score(sentence: str) -> int:
        return (
            6 * bool(action_pattern.search(sentence))
            + 5 * bool(result_pattern.search(sentence))
            + 2 * bool(focus_pattern.search(sentence))
            - 4 * bool(re.search(r"(?i)\b(?:to do so|this approach|this method)\b", sentence))
            - 5 * bool(background_pattern.search(sentence))
        )

    summary = max(
        enumerate(sentences),
        key=lambda item: (sentence_score(item[1]), -item[0]),
    )[1]
    summary = re.sub(r"(?i)\bthis\s+(?:survey|review|paper|work|study)\b", "The study", summary)
    summary = re.sub(
        r"(?i)\bwe\s+(propose|present|introduce|develop|show|demonstrate|evaluate|find|review|"
        r"construct|build|design|derive|create|train|formulate|describe|report|provide|establish|extend)\b",
        lambda match: f"The authors {match.group(1).lower()}",
        summary,
    )
    summary = re.sub(r"(?i)\bour\b", "the study's", summary)
    summary = re.sub(r"(?<=, )The\s+", "the ", summary)
    # "The study" is only sentence-initial; after a lowercase word (e.g. "In The
    # study") it must be lowercase. Fix the capitalization artifact.
    summary = re.sub(r"(?<=[a-z] )The study\b", "the study", summary)
    summary = re.sub(r"https?://\S+", "", summary).strip()

    words = summary.split()
    if len(words) > max_words:
        # A single sentence that only slightly exceeds the cap is kept whole (end
        # on its natural terminator) rather than cut mid-phrase into a dangling
        # ellipsis ("... and ternary amorphous"). Only when it is well over the cap
        # do we hard-truncate.
        is_one_sentence = len(re.findall(r"[.!?]\s", summary)) == 0
        if is_one_sentence and len(words) <= int(max_words * 1.25) + 2:
            return summary.strip()
        clipped = " ".join(words[:max_words])
        # Prefer to end at the last clause boundary within the cap rather than
        # after a dangling word/preposition ("... and adapts to"). Only back up
        # if the boundary keeps most of the clipped text (avoid over-trimming).
        boundary = max(clipped.rfind(","), clipped.rfind(";"))
        if boundary >= int(len(clipped) * 0.6):
            clipped = clipped[:boundary]
        else:
            # No clause boundary in the cap: drop trailing connective/preposition
            # words so the annotation does not end on a dangling function word.
            tail = clipped.split()
            while tail and tail[-1].lower().strip(",;:-") in _BRIEF_TRAILING_DROP:
                tail.pop()
            if len(tail) >= int(max_words * 0.6):
                clipped = " ".join(tail)
        summary = clipped.rstrip(" ,;:-") + "..."
    return summary.strip()


# Trailing words that must not end a truncated brief annotation before the "...":
# structural connectives, prepositions, and articles (a content word before the
# ellipsis is an acceptable truncation signal; a dangling function word is not).
_BRIEF_TRAILING_DROP = {
    "and", "or", "of", "for", "to", "with", "across", "the", "a", "an", "in",
    "on", "at", "by", "from", "into", "over", "under", "as", "that", "which",
    "using", "via", "such", "between", "among", "through", "while", "when",
}


def render_evidence_synthesis_markdown(rows: list[dict[str, str]]) -> str:
    years = [int(row["year"]) for row in rows if str(row.get("year") or "").isdigit()]
    tasks = [str(row.get("task") or "").strip() for row in rows if str(row.get("task") or "").strip()]
    rob_counts = Counter(str(row.get("rob_overall") or "unclear").strip() or "unclear" for row in rows)
    year_span = f"{min(years)}-{max(years)}" if years else "unknown"
    task_summary = ", ".join(sorted(set(tasks))) if tasks else "mixed tasks with sparse deterministic labels"
    paper_ids = [str(row.get("paper_id") or "").strip() for row in rows if str(row.get("paper_id") or "").strip()]
    evidence_rows = []
    for row in rows:
        evidence_rows.append(
            [
                str(row.get("paper_id") or ""),
                str(row.get("title") or ""),
                str(row.get("population_or_setting") or "not reported"),
                str(row.get("task") or "not reported"),
                str(row.get("metric") or "not reported"),
                str(row.get("study_type") or "not reported"),
                str(row.get("rob_overall") or "unclear"),
                str(row.get("evidence_pointer") or row.get("url") or ""),
            ]
        )

    lines = [
        "# Evidence Review Synthesis",
        "",
        "## Research questions + scope",
        "- This synthesis reports only conclusions the included studies directly support.",
        "",
        "## Included studies summary",
        f"- Included studies: {len(rows)}",
        f"- Year span: {year_span}",
        f"- Task coverage: {task_summary}",
        "",
        "## Extracted evidence table",
        _markdown_table(
            ["Paper ID", "Study", "Population / setting", "Task", "Metric", "Study type", "Overall RoB", "Evidence pointer"],
            evidence_rows,
        ),
        "",
        "## Findings by theme",
        f"- The included studies cluster around {task_summary} ({', '.join(paper_ids)}).",
        "- Findings are kept conservative: no effect is claimed beyond what the included studies report.",
        "",
        "## Risk of bias",
        f"- Overall RoB counts: low={rob_counts.get('low', 0)}, unclear={rob_counts.get('unclear', 0)}, high={rob_counts.get('high', 0)}.",
        "- Protocol detail and confounding control remain the main reasons to keep conclusions bounded.",
        "",
        "## Supported conclusions",
        f"- Across {len(rows)} included studies ({', '.join(paper_ids)}), the evidence supports descriptive conclusions about the reported tasks, settings, and metrics.",
        "",
        "## Needs more evidence",
        "- Strong comparative or causal claims still need studies that report richer outcome data, stronger protocol detail, and more complete results.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
