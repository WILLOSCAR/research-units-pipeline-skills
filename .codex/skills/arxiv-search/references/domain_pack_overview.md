# Domain packs for retrieval

A domain pack is curated knowledge about one research area: arXiv ids of
classic papers and surveys that a reader of that area expects to see, and
query clauses that retrieve the area precisely. Packs live under
`../literature-engineer/assets/domain_packs/<domain>.json` relative to the
`arxiv-search` Skill directory. That directory is the single owner;
retrieval records classifications in `origin` for curation to consume.

## Fields

- `topic_triggers` — `trigger_group_a` and `trigger_group_b`: the pack applies
  when the Success Spec's `scope` (or `goal.text`) contains a term from each
  group; `name_triggers` are system names that alone indicate the area.
- `pinned_classics`, `pinned_surveys` — `{arxiv_id, label}` entries to
  retrieve by id when the pack applies.
- `query_rewrite.core_clause`, `query_rewrite.signal_clause` — fielded arXiv
  query fragments; the first query is `core_clause AND signal_clause`.
- Legacy `survey_detection` entries may be present; curation uses its own
  title rule and the recorded `pinned_survey` classification.

## Rule of use

The Success Spec decides scope; a pack only helps reach it. If `scope` names
a narrower question than the pack's area, keep the spec's terms in every
query and treat the pinned ids as candidates that `dedupe-rank` may drop. If
no pack matches, build queries from the spec alone; there is no penalty for
having no pack.

## Adding a pack

Create `../literature-engineer/assets/domain_packs/<domain>.json` with the fields above. Keep only
ids you have checked resolve to the paper the label names.
