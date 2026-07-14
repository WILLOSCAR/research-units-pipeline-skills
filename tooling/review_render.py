from __future__ import annotations

from collections import Counter


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

    lines = [
        "# Research Brief",
        "",
        "## Scope",
        f"- Requested outcome: {request}",
        f"- Evidence boundary: this is a focused orientation based on {len(papers)} selected papers, not an exhaustive literature claim.",
        f"- Comparison lenses: {lens_text}.",
        "",
        "## Key themes",
    ]
    for paper in chosen[:6]:
        pointer = _brief_pointer(paper)
        abstract = str(paper.get("abstract") or "").strip()
        insight = abstract or f"Use this paper to understand {paper.get('title') or 'the topic'}"
        lines.append(f"- {insight.rstrip('.')} [{pointer}].")

    lines.extend(["", "## What to read first"])
    for paper in chosen[:6]:
        pointer = _brief_pointer(paper)
        abstract = str(paper.get("abstract") or "").strip()
        reason = abstract or "Representative item from the ranked core set."
        lines.append(f"- {pointer}: {reason.rstrip('.')}.")

    lines.extend(
        [
            "",
            "## Open problems / risks",
            "- The core set is deliberately compact; missing terminology or adjacent communities can still change the topic boundary.",
            "- Abstract-level descriptions are useful for orientation but cannot support strong causal, comparative, or reproducibility claims without full-text checking.",
            "- Evaluation settings, safety constraints, and transfer conditions should be compared before turning this briefing into a larger evidence synthesis.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _brief_pointer(paper: dict[str, str]) -> str:
    paper_id = str(paper.get("paper_id") or "unknown").strip()
    title = str(paper.get("title") or "Untitled paper").strip()
    url = str(paper.get("url") or "").strip()
    return f"{paper_id} - {title}" + (f" ({url})" if url else "")


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
