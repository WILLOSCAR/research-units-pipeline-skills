---
name: paper-notes
description: Write paper_notes.jsonl — one checkable note per line (source_id, kind, claim, verbatim evidence_span, locator) for every core-set paper, drawn only from the retrieved source files.
role: producer
reads: [success_spec.yaml, core_set.csv, sources/]
outputs: [paper_notes.jsonl]
---

# Paper Notes

The `notes` step of the `survey` kind. For every core-set paper it records
what the source file says — setting, mechanism, results, limitations — as
one-sentence claims, each tied to a verbatim span and a locator in that file.
`survey-writer` takes its pointers from these notes: a note's `locator`
becomes a statement's `locator`, and the `source-support` prover opens the
same file at that locator. A note whose span is not in the file, or whose
claim adds what the span lacks, becomes an unsupported statement downstream.

## Inputs

- `core_set.csv` — `source_id,title,year,venue,score,reason`; every
  `source_id` gets notes. `score` and `reason` (`survey`, `pinned-*`,
  `coverage:*`) mark the high-priority papers.
- `sources/<source_id>.md` — front matter, `## Abstract`, and
  `## Retrieved text` when present. The only ground: what is not in the file
  is not in the notes. Ignore files whose stem is not in `core_set.csv`.
- `success_spec.yaml` — always in the packet; `scope` and the `coverage`
  criteria say which aspects to note first.

## Outputs

`paper_notes.jsonl`, UTF-8, one JSON object per line, no blank lines, papers
in `core_set.csv` order:

```json
{"note_id": "2210.03629-n1", "source_id": "2210.03629", "kind": "summary", "claim": "ReAct prompts a language model to interleave reasoning traces with task actions so that reasoning updates the plan and actions fetch external information.", "evidence_span": "generate both reasoning traces and task-specific actions in an interleaved manner", "locator": "abstract"}
{"note_id": "2210.03629-n2", "source_id": "2210.03629", "kind": "result", "claim": "On ALFWorld and WebShop, ReAct beats imitation and reinforcement learning baselines by 34 and 10 absolute points of success rate with one or two in-context examples.", "evidence_span": "outperforms imitation and reinforcement learning methods by an absolute success rate of 34% and 10% respectively", "locator": "abstract"}
{"note_id": "2210.03629-n3", "source_id": "2210.03629", "kind": "limitation", "claim": "The abstract evaluates on four tasks and reports no cost or latency for the longer interleaved trajectories.", "evidence_span": "on two interactive decision making benchmarks (ALFWorld and WebShop)", "locator": "abstract"}
```

- `note_id` is `<source_id>-n<k>`, `k` from 1 per paper; `source_id` is the
  source file's stem. All six keys are present in every line.
- `kind` is one of `summary`, `setting`, `method`, `result`, `limitation`.
- `claim` is one neutral sentence in your words, specific to this paper.
- `evidence_span` is a contiguous verbatim quote of at most 40 words from the
  source file; `locator` says where it sits: `abstract`, `title`, `§3.2` (a
  `###` heading under `## Retrieved text`), `L40-L46` (line numbers of the
  file), or `p.5`.
- Kernel gates on this step: `schema-valid` (every non-blank line parses as
  JSON, at least one line) and `scaffold-absent` (no `<!-- scaffold -->`, no
  whole-word `TODO`, `TBD`, `FIXME`, or `XXX`).

## Method

1. **Minimums.** Every core paper: at least two notes, one `summary` and one
   `limitation` or `setting`. High-priority papers (top third by `score`, or
   `reason` containing `survey`, `pinned-`, or `coverage:`): at least four —
   `summary`, `method`, one or more `result`, one or more `limitation`. A
   file whose `## Abstract` is `(no abstract in record)`: exactly one
   `summary` restating the title, `locator: title`.
2. **Depth follows the file.** With only an abstract every locator is
   `abstract`; with `## Retrieved text`, prefer spans from the body and give
   `§` or `L` locators.
3. **Results** carry task or benchmark, metric, number, and baseline as far
   as the span gives them and no further
   (`references/result_extraction_examples.md`).
4. **Limitations** are paper-specific and checkable against the file
   (`references/limitation_taxonomy.md`). An absence claim ("the abstract
   reports no cost figure") requires reading the whole file, is phrased
   about the file, and points at the span that lists what is reported. At
   most one evidence-depth caveat per paper, never the same sentence twice.
5. **Hygiene.** Strip author narration ("we show that", "in this work"),
   roadmap lines, and availability lines from `claim`; never alter
   `evidence_span` (`references/source_text_hygiene.md`).
6. **Check** before writing: every `core_set.csv` `source_id` meets its
   minimum; every `evidence_span` is found verbatim in its file at its
   `locator`; no two papers share a `claim` sentence.

## Repair

A Fault routed here comes from the kernel (file missing or empty, a line that
does not parse, a placeholder token) or from a prover finding that cites
`paper_notes.jsonl` (a note's span was not in the file at its locator; a core
paper had no notes to write from). Reread the source files and write the
whole `paper_notes.jsonl` again; for a cited note, quote the passage exactly
as the file has it, or drop the note when the file does not contain it.

## Do not

- Do not write prose, synthesis across papers, or rankings.
- Do not put a number, benchmark, or baseline in `claim` that the
  `evidence_span` does not contain.
- Do not draw on memory of the paper, other papers, or the title alone for a
  `method` or `result` note.
- Do not paraphrase, stitch, or trim inside `evidence_span`.
- Do not write the same limitation sentence for more than one paper.
