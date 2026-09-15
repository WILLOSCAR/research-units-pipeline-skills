# Taxonomy principles

## 1) Optimise for reader questions, not keyword buckets

Good top-level nodes read like chapter titles in a survey. Bad top-level
nodes read like bag-of-words clusters.

## 2) Prefer fewer, thicker top-level categories

A paper-like survey wants a small number of chapter-driving categories. If
every recurring term becomes a top-level node, the outline and the prose
fragment with it.

## 3) Make leaves mappable

A leaf should plausibly absorb several papers. A one-paper leaf usually
belongs as a comparison axis inside a sibling subsection, not as a node.

## 4) Encode scope in the definition

A good definition says what belongs in the node and what comparison it
supports. It is what lets `outline-builder` and the writer avoid drift.

## 5) Separate mechanism, evaluation, and risk when the corpus supports it

If a topic mixes system design, benchmarking, and safety in one node,
placement becomes ambiguous. Split only when the split is meaningful to
readers and populated by sources.

## 6) Avoid generic placeholders

Not as node names: `Overview`, `Representative Approaches`, `Benchmarks`,
`Open Problems`, `Misc`, `Other`. They signal that the tree is dodging the
real organising question.

## 7) Keep definitions concrete

Mention the design or evaluation question the node covers, the assumptions
or constraints that matter there, and — via `source_ids` — the papers that
populate it. Do not paste ids into the definition text.

## 8) Serve the Success Spec first

Every aspect an `answers` or `coverage` criterion names has a node the
outline can point at. A pack or archetype that lacks such a node is
extended; a pack node the core set does not populate is dropped.

## 9) Treat domain packs as explicit support, not hidden bias

If an area needs a curated starting tree, put it in
`../assets/domain_packs/<domain>.yaml` (`profile`, `display_name`,
`detect.all_of_groups`, `taxonomy` of `name` / `definition` / `children`).
Nothing about a domain lives outside that file; the pack is a starting
shape the core set and the Success Spec reshape, never a fixed answer.
