from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tooling.quality_checks.common import QualityIssue


def write_quality_report(*, workspace: Path, unit_id: str, skill: str, issues: list[QualityIssue]) -> Path:
    from tooling.common import atomic_write_text, ensure_dir

    ensure_dir(workspace / "output")
    report_path = workspace / "output" / "QUALITY_GATE.md"

    now = datetime.now().replace(microsecond=0).isoformat()
    status = "PASS" if not issues else "FAIL"
    lines: list[str] = [
        "# Quality gate report",
        "",
        f"- Timestamp: `{now}`",
        f"- Unit: `{unit_id}`",
        f"- Skill: `{skill}`",
        "",
        "## Status",
        "",
        f"- {status}",
        "",
        "## Issues",
        "",
    ]
    if issues:
        for issue in issues:
            lines.append(f"- `{issue.code}`: {issue.message}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Next action")
    lines.append("")
    if issues:
        for ln in next_action_lines(skill=skill, unit_id=unit_id):
            lines.append(ln)
    else:
        lines.append("- Proceed to the next unit.")
    lines.append("")

    entry = "\n".join(lines).rstrip() + "\n"

    # Append-only by default: keep a history of quality-gate outcomes in the workspace.
    # This makes failures debuggable without rerunning (and preserves context across retries).
    if report_path.exists() and report_path.stat().st_size > 0:
        prev = report_path.read_text(encoding="utf-8", errors="ignore").rstrip() + "\n\n---\n\n"
        atomic_write_text(report_path, prev + entry)
    else:
        atomic_write_text(report_path, entry)
    return report_path


def next_action_lines(*, skill: str, unit_id: str) -> list[str]:
    skill_md = f".codex/skills/{skill}/SKILL.md"
    common = [
        "- Treat the current outputs as a starting point (often a scaffold).",
        f"- Follow `{skill_md}` to refine the required artifacts until the issues above no longer apply.",
        f"- Then commit `{unit_id}` through `uv run python scripts/pipeline.py mark --workspace <workspace> --unit-id {unit_id} --status DONE --note \"LLM refined\"`, replacing `<workspace>` with the Run directory; do not edit the `DONE` cell directly.",
    ]

    by_skill: dict[str, list[str]] = {
        "literature-engineer": [
            "- Provide multiple offline exports under `papers/imports/` (different queries/routes) to reach a large candidate pool (survey target: >=200).",
            "- Ensure most records contain stable IDs (`arxiv_id`/`doi`) and non-empty `url`; prefer arXiv/OpenReview/ACL exports with IDs.",
            "- If network is available, rerun with `--online` (and optionally `--snowball`) to expand coverage via arXiv API and citation graph.",
        ],
        "dedupe-rank": [
            "- Inspect `papers/papers_raw.jsonl`: ensure `title/year/url/authors` are present and not empty; fix/replace the offline export if needed.",
            "- Rerun dedupe with an appropriate `--core-size` to get a usable `papers/core_set.csv` (with stable `paper_id`).",
        ],
        "taxonomy-builder": [
            "- Edit `outline/taxonomy.yml`: replace all `TODO` / placeholder text with domain-meaningful node names and 1–2 sentence descriptions.",
            "- Ensure taxonomy has ≥2 levels (uses `children`) and avoids generic buckets like “Overview/Benchmarks/Open Problems”.",
        ],
        "outline-builder": [
            "- Edit `outline/outline.yml`: rewrite every `TODO` bullet into topic-specific, checkable bullets (axes, comparisons, evaluation setups, failure modes).",
            "- Keep it bullets-only (no prose paragraphs).",
        ],
        "section-mapper": [
            "- Edit `outline/mapping.tsv`: diversify mapped papers per subsection and reduce over-reuse of a few papers across unrelated sections.",
            "- Replace generic `why` (e.g., `matched_terms=...`) with a short semantic rationale (mechanism/task/benchmark/safety angle).",
            "- Use `outline/mapping_report.md` to find hotspots and weak-signal subsections.",
            "- Use `outline/mapping_gap_candidates.tsv` to identify in-scope candidates from the deduplicated pool before changing the frozen core set or expanding retrieval.",
        ],
        "paper-notes": [
            "- Edit `papers/paper_notes.jsonl`: fully enrich `priority=high` papers (method, key_results, concrete limitations) and remove all `TODO`s.",
            "- Long-tail papers can remain abstract-level, but avoid copy-pasted limitation boilerplate across many records.",
        ],
        "claim-evidence-matrix": [
            "- Edit `outline/claim_evidence_matrix.md`: rewrite template-y claims into specific, falsifiable claims per subsection.",
            "- For each claim, keep ≥2 evidence sources (paper IDs) and add caveats when evidence is abstract-only.",
        ],
        "pdf-text-extractor": [
            "- If you want to avoid downloads, keep `evidence_mode: \"abstract\"` in `queries.md` (it will emit skip records).",
            "- For full-text evidence: set `evidence_mode: \"fulltext\"`, ensure `papers/core_set.csv` has `pdf_url`/`arxiv_id`, or provide PDFs under `papers/pdfs/`.",
            "- Consider `--local-pdfs-only` and add a small set of PDFs manually to unblock strict mode.",
        ],
        "citation-verifier": [
            "- Ensure every `papers/paper_notes.jsonl` record has a stable `bibkey`, `title`, and canonical `url`.",
            "- Regenerate `citations/ref.bib` + `citations/verified.jsonl` and ensure every bibkey has a verification record with `url/date/title`.",
            "- If offline, use `verification_status=offline_generated` and plan a later `--verify-only` pass when network is available.",
        ],
        "survey-visuals": [
            "- Tables are handled by table skills: `table-schema` (schema) → `table-filler` (index: `outline/tables_index.md`) → `appendix-table-writer` (reader tables: `outline/tables_appendix.md`).",
            "- Fill `outline/timeline.md` with ≥8 milestone bullets (year + cited works).",
            "- Fill `outline/figures.md` with ≥2 figure specs (purpose, elements, supporting citations).",
        ],
        "subsection-writer": [
            "- Write per-unit prose files under `sections/` (small, verifiable units):",
            "  - `sections/abstract.md` (`## Abstract`), `sections/discussion.md`, `sections/conclusion.md`.",
            "  - `sections/S<section_id>.md` for H2 sections without H3 (body only).",
            "  - `sections/S<sub_id>.md` for each H3 (body only; no headings).",
            "- Each H3 file should have >=3 unique citations and avoid ellipsis/TODO/template boilerplate.",
            "- Keep H3 citations subsection-first: cite keys mapped in `outline/evidence_bindings.jsonl` for that H3; limited reuse from sibling H3s in the same H2 chapter is allowed; avoid cross-chapter “free cite”.",
            "- After files exist, run `writer-selfloop` to enforce draft-profile depth/scope and to generate an actionable fix plan (`output/WRITER_SELFLOOP_TODO.md`).",
        ],
        "writer-selfloop": [
            "- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).",
            "- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).",
            "- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.",
            "- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.",
        ],
        "evaluation-anchor-checker": [
            "- Open `output/EVAL_ANCHOR_REPORT.md` and confirm it reports a non-zero `Files checked` count.",
            "- Keep numbers only when the same sentence carries enough task/metric/constraint context; otherwise weaken the claim without changing citation keys.",
            "- If later section-level rewrites touch the same H3 files, rerun `evaluation-anchor-checker` before merge instead of waiting for `pipeline-auditor`.",
        ],
        "section-merger": [
            "- Ensure all required `sections/*.md` exist (see `output/MERGE_REPORT.md` for missing paths), then rerun merge.",
            "- After merge, polish/review the combined `output/DRAFT.md` (then run `pipeline-auditor` before LaTeX).",
        ],
        "post-merge-voice-gate": [
            "- Open `output/POST_MERGE_VOICE_REPORT.md` and fix the earliest responsible artifact it points to.",
            "- If the report says `source: transitions`: rewrite `outline/transitions.md` as content-bearing argument bridges (no planner talk, no A/B/C slash labels), then rerun `section-merger` and this gate.",
            "- If the report says `source: draft`: route to `writer-selfloop` / `subsection-polisher` / `draft-polisher` for the flagged section, then rerun `section-merger` and this gate.",
        ],
        "prose-writer": [
            "- Treat any leaked scaffold text (`…`, `enumerate 2-4 ...`, 'Scope and definitions ...') as a HARD FAIL: fix outline/claims first, then draft.",
            "- For each subsection, write a unique thesis + 2 contrast sentences (A vs B) + 1 failure mode, each backed by citations.",
            "- Use concrete axes (datasets/metrics/compute/training/sampling/failure modes), not generic \"design space\" prose.",
            "- Keep citations evidence-first: paragraph-level cites; keys must exist in `citations/ref.bib`.",
            "- Ensure paper-like structure exists: Introduction, (optional) Related Work, 3–4 core chapters, Discussion/Future Work, Conclusion.",
        ],
        "latex-scaffold": [
            "- Edit `latex/main.tex`: remove any leaked markdown (`##`, `**`, `[@...]`) and ensure bibliography points to `../citations/ref.bib`.",
        ],
        "latex-compile-qa": [
            "- Open `output/LATEX_BUILD_REPORT.md` and fix the first compile error (missing package, missing bib, bad cite key).",
            "- Ensure `latexmk` is installed and `latex/main.tex` references `../citations/ref.bib`.",
        ],
        "arxiv-search": [
            "- Ensure `papers/papers_raw.jsonl` contains real records (not placeholders) and rerun the unit if needed.",
        ],
    }

    out: list[str] = []
    out.extend(by_skill.get(skill, []))
    out.extend(common)
    return out
