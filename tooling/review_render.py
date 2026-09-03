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


def render_rubric_review_markdown(*, claim_count: int, gap_count: int, major_gaps: list[dict[str, str]], novelty_available: bool) -> str:
    recommendation = "weak_reject" if major_gaps else ("borderline" if gap_count else "weak_accept")
    novelty_note = (
        "Novelty was assessed conservatively from the available novelty matrix."
        if novelty_available
        else "Novelty matrix was unavailable; novelty is therefore conservative."
    )
    lines = [
        "# Review",
        "",
        "### Summary",
        f"- The paper claims {claim_count} main contribution(s) and is reviewed through explicit claim and gap extraction.",
        "",
        "### Novelty",
        f"- {novelty_note}",
        "",
        "### Soundness",
        f"- The review surfaced {len(major_gaps)} major and {max(0, gap_count - len(major_gaps))} minor evidence issues.",
        "",
        "### Clarity",
        "- The main clarity risk is whether each top claim states its protocol, metric, and boundary explicitly.",
        "",
        "### Impact",
        "- If the major issues are fixed, the work could become easier to compare and reproduce.",
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
    if gap_count:
        for gap in major_gaps[:3]:
            lines.append(f"- {gap['minimal_fix']}")
        if not major_gaps:
            lines.append("- Clarify the strongest remaining evidence gaps and manuscript boundaries.")
    else:
        lines.append("- (none)")
    lines.extend(["", "### Recommendation", f"- {recommendation}"])
    return "\n".join(lines).rstrip() + "\n"


def render_research_brief_markdown(*, goal: str, papers: list[dict[str, str]], sections: list[str]) -> str:
    chosen = papers[: min(8, len(papers))]
    lenses = [
        title
        for title in sections
        if title.strip().lower() not in {"introduction", "related work", "conclusion"}
    ][:4]
    lens_text = ", ".join(lenses) if lenses else "methods, evaluation, and deployment risks"
    request = " ".join(goal.replace("# Goal", "").split()) or "Orient the reader to the target topic."
    scope_anchor = f" The boundary is anchored by [{_brief_pointer(chosen[0])}]." if chosen else ""

    lines = [
        "# Research Brief",
        "",
        "## Scope",
        f"- Requested outcome: {request}",
        (
            f"- Evidence boundary: this is a focused orientation based on {len(papers)} selected papers, "
            f"not an exhaustive literature claim.{scope_anchor}"
        ),
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
    for paper in chosen[:4]:
        pointer = _brief_pointer(paper)
        abstract = str(paper.get("abstract") or "").strip()
        reason = _brief_summary(abstract, max_words=28) or "Representative item from the ranked core set."
        lines.append(f"- {pointer}: {reason.rstrip('.')}.")

    lines.extend(["", "## Open problems / risks"])
    for bullet in _brief_risk_bullets(lenses=lenses, papers=chosen):
        lines.append(f"- {bullet}")
    return "\n".join(lines).rstrip() + "\n"


# Genuinely topic-independent methodological caveats: they describe the briefing
# METHOD (compact core set, abstract-level orientation), not the subject matter,
# so they honestly apply to every brief.
_BRIEF_UNIVERSAL_RISKS = (
    "The core set is deliberately compact; missing terminology or adjacent communities can still change the topic boundary.",
    "Abstract-level descriptions are useful for orientation but cannot support strong causal, comparative, or reproducibility claims without full-text checking.",
)

_LIMITATION_CUE = re.compile(
    r"(?i)\b(?:limitation|caveat|confound|does not|cannot|fails? to|"
    r"unclear|only|restricted to|assumes?)\b"
)


def _brief_risk_bullets(*, lenses: list[str], papers: list[dict[str, str]]) -> list[str]:
    """Build the Open-problems bullets from THIS brief's lenses + evidence.

    The two universal caveats describe the briefing method and always apply. The
    remaining bullets are derived from the run's own comparison lenses and the
    in-scope papers' stated limitations (NO NEW FACTS), so the section varies
    with the topic instead of repeating hardcoded, domain-mislabeled boilerplate.
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
    # core-set order.
    for paper in papers:
        abstract = str(paper.get("abstract") or "").strip()
        for sentence in re.split(r"(?<=[.!?])\s+", abstract):
            sentence = sentence.strip()
            if sentence and _LIMITATION_CUE.search(sentence):
                pointer = _brief_pointer(paper)
                limitation = _brief_summary(sentence, max_words=32) or sentence
                bullets.append(
                    f"Reported limitation to weigh: {limitation.rstrip('.')} "
                    f"[{pointer}]."
                )
                break
        else:
            continue
        break

    return bullets


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
        r"(?i)\b(?:we|the authors?|this (?:paper|work|study|survey|review))\s+"
        r"(?:propose|present|introduce|develop|demonstrate|evaluate|show|find|review)s?\b"
    )
    result_pattern = re.compile(
        r"(?i)\b(?:results?|experiments?|evaluation|findings?)\b.*\b"
        r"(?:show|demonstrate|improve|outperform|reveal|indicate)s?\b"
    )
    focus_pattern = re.compile(
        r"(?i)\b(?:adaptation|distribution shift|out-of-distribution|sim-to-real|"
        r"continual learning|deployment|transfer)\b"
    )

    def sentence_score(sentence: str) -> int:
        return (
            6 * bool(action_pattern.search(sentence))
            + 5 * bool(result_pattern.search(sentence))
            + 2 * bool(focus_pattern.search(sentence))
            - 4 * bool(re.search(r"(?i)\b(?:to do so|this approach|this method)\b", sentence))
        )

    summary = max(
        enumerate(sentences),
        key=lambda item: (sentence_score(item[1]), -item[0]),
    )[1]
    summary = re.sub(r"(?i)\bthis\s+(?:survey|review|paper|work|study)\b", "The study", summary)
    summary = re.sub(
        r"(?i)\bwe\s+(propose|present|introduce|develop|show|demonstrate|evaluate|find|review)\b",
        lambda match: f"The authors {match.group(1).lower()}",
        summary,
    )
    summary = re.sub(r"(?i)\bour\b", "the study's", summary)
    summary = re.sub(r"(?<=, )The\s+", "the ", summary)
    summary = re.sub(r"https?://\S+", "", summary).strip()

    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]).rstrip(" ,;:-") + "..."
    return summary.strip()


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
        "- This synthesis follows the current protocol and only reports what the extraction table supports.",
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
        f"- The current extracted evidence clusters around {task_summary} ({', '.join(paper_ids)}).",
        "- The deterministic pass keeps findings conservative and avoids claiming effects not present in the table.",
        "",
        "## Risk of bias",
        f"- Overall RoB counts: low={rob_counts.get('low', 0)}, unclear={rob_counts.get('unclear', 0)}, high={rob_counts.get('high', 0)}.",
        "- Protocol detail and confounding control remain the main reasons to keep conclusions bounded.",
        "",
        "## Supported conclusions",
        f"- Across {len(rows)} included studies ({', '.join(paper_ids)}), the extracted evidence supports descriptive conclusions about the reported tasks, settings, and metrics.",
        "",
        "## Needs more evidence",
        "- Strong comparative or causal claims still need richer extraction fields, stronger protocol detail, or more complete reporting.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
