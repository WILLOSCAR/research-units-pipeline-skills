# Overview

`outline-builder` turns the Success Spec plus the curated sources (or the
taxonomy) into `outline.yml`: the plan the writer follows and the first
place a coverage gap can be seen.

## What this skill owns

- deciding which section answers which Success Spec criterion or scope
  question, so that every criterion is reachable before writing starts
- naming, per section, the `source_ids` from `core_set.csv` that will carry
  its claims
- assigning `budget_words` within the `length` criterion's bound
- for a survey, translating taxonomy nodes into chapters and subsections
  and giving each subsection the bullet fields in `bullet_contract.md`
- emitting bullets a reader of the sources could check, never paragraphs

## Read in this order

1. `bullet_contract.md` — the fields every survey subsection carries
2. `intro_related_patterns.md` — the `introduction` block and how to
   position a survey against existing surveys without a fixed domain
3. `examples_good.md`, then `examples_bad.md` — bullet calibration

## Non-goals

- prose of any kind
- changing the taxonomy or the core set
- naming a source that is not in `core_set.csv`
