---
name: manuscript-ingest
description: Turn the manuscript the Goal points at (a URL or path to a PDF, arXiv HTML, LaTeX, or text file) into manuscript.md, a faithful full text with stable paragraph, table, figure, and reference anchors that every later step of the review kind cites as locators.
role: producer
reads: [goal.md, success_spec.yaml]
outputs: [manuscript.md]
---

# Manuscript Ingest

The `ingest` step of the `review` kind. It produces the Source ground of the
Run: `manuscript.md` is the only text `claims-extractor`, `evidence-auditor`,
`novelty-matrix`, and `review-writer` may cite for what the paper says, and
the text the `source-support` prover opens when it checks a review statement.
The job is faithful transcription with addressable anchors, not a summary.

## Inputs

- `goal.md` — names the manuscript (URL or path) and the review's focus. The
  manuscript itself is not an input object; fetch or open it from there.
- `success_spec.yaml` — `scope`, and any `coverage` criterion that names
  sections, tables, appendices, or experiments; those parts must survive
  ingestion under their own anchors.

## Outputs

`manuscript.md`: YAML front matter, then the full text in manuscript order,
each addressable unit preceded by an HTML-comment anchor on its own line.

```markdown
---
title: <title as printed>
authors: [<author>, <author>]
source: <URL or path the text was taken from, with version and date>
ingested_at: <ISO 8601>
anchors: "p: 47 paragraph anchors; t: 6 table anchors; f: 11 figure anchors; ref: 31 reference entries"
---

# <Title>

## Abstract

<!-- p:abs.1 -->
First paragraph of the abstract, verbatim.

<!-- t:1 -->
**Table 1: Pass@1 accuracy for various model-strategy-language combinations.**
| Benchmark + Language | Prev SOTA Pass@1 | SOTA Pass@1 | Reflexion Pass@1 |
| --- | --- | --- | --- |
| HumanEval (PY) | 65.8 (CodeT [5] + GPT-3.5) | 80.1 (GPT-4) | **91.0** |

## References

<!-- ref:15 -->
[15] Madaan, A., ... (2023). Self-refine: Iterative refinement with self-feedback. arXiv:2303.17651.
```

Anchor scheme; downstream ledgers and the review use these labels verbatim as
`locator`:

- `p:<section>.<k>` — the k-th body paragraph of the (sub)section whose
  printed number is `<section>` (`p:4.1.3`; appendix `p:B.1.1`); `abs` for
  the abstract. Counting restarts in every numbered (sub)section and skips
  headings, captions, tables, figures, and code blocks. A run-in heading
  (`\paragraph{Results}`) does not start a new count: keep it inline in bold
  at the start of its paragraph. A bullet or numbered list is one paragraph.
- `t:<n>` / `f:<n>` — captioned Table n / Figure n; the caption follows the
  anchor in bold, then the table as a Markdown table (or verbatim text when
  cells did not survive extraction). An uncaptioned table or figure is
  `t:<section>.<k>` / `f:<section>.<k>` (`t:2.1`).
- `ref:<n>` — the n-th reference entry, kept in full; `ref:<citekey>` when
  the manuscript uses author–year keys.
- Headings keep their printed number and title (`## 4 Experiments`,
  `### 4.1 ...`, `## A <appendix title>`); depth follows the manuscript.

No kernel gate reads this file; integrity verify only requires that it
exists and is non-empty. Its quality is checked indirectly when the
`source-support` prover follows a locator here and fails a statement whose
passage it cannot find.

## Method

1. Locate the manuscript in `goal.md`. Prefer a structured source (arXiv
   HTML, LaTeX) over a PDF; convert a PDF with a local extractor
   (`pdftotext -layout`, `pypdf`). Record source, version, and date in the
   front matter; cross-check at least two tables against a second rendering
   when one exists.
2. Preserve every body paragraph, heading, caption, footnote (inlined as
   `[fn 3]`), table, algorithm or code listing (fenced block), equation
   (`$...$` TeX), and reference entry. Text panels inside a figure (example
   trajectories, prompts) go under the figure anchor as quoted lines.
3. Repair only extraction damage: rejoin hyphenated line breaks, drop running
   headers, page numbers, and column artefacts, restore paragraph breaks.
   Keep the manuscript's own wording, including broken cross-references and
   typos; they are facts about the manuscript.
4. Where content is lost (a chart, an unreadable table) write one line
   `[extraction: <what was lost>]` at the anchor: a stated loss, not a
   placeholder.
5. Number paragraphs once, after normalization; confirm every (sub)section's
   paragraph count against the source and that no reference entry is missing.
6. Check `success_spec.yaml`: every section, table, appendix, or experiment
   a `coverage` criterion names is present under its own anchor.

## Repair

A Fault reaches this step when a prover cites `manuscript.md` and implicates
`ingest`: a locator that leads to no passage, a truncated section, a table
whose cells were lost, the wrong document or version. Obtain the text again
from the source named in `goal.md`, fix the named defect, and keep every
other anchor label unchanged; the ledgers downstream cite them.

## Do not

- Do not paraphrase, reorder, shorten, or smooth wording; a polished text
  makes `quotes` and `condenses` statements about the manuscript unverifiable.
- Do not summarise, critique, or grade the manuscript.
- Do not extract claims, audit evidence, position or retrieve related work;
  those are the `claims`, `audit`, and `novelty` steps, and the `review`
  kind retrieves nothing.
- Do not leave `TODO`, `TBD`, `FIXME`, `XXX`, or `<!-- scaffold -->` in the file.
