# Subsection bullet contract (survey)

Every survey subsection in `outline.yml` stays bullets-only and checkable
against the sources it names. Its `bullets` carry these fields, in this
order, each a single line starting with the field label:

- `Intent:` — what belongs in this subsection and how it differs from its
  neighbours (name the sibling ids).
- `RQ:` — the decision-relevant trade-off the subsection answers; tie it to
  the `question` (a Success Spec criterion or scope question).
- `Scope cues:` — the taxonomy leaf's definition, condensed; omit when the
  definition already appears in `Intent`.
- `Evidence needs:` — mechanism, training or data setup, evaluation
  protocol, failure modes — whichever the named sources actually report,
  with their ids in brackets.
- `Expected cites:` — how many of the subsection's `source_ids` the writer
  should cite and which one is canonical; at least two ids per subsection,
  or the leaf should have been merged upstream.
- `Concrete comparisons:` — at least two explicit A-versus-B contrasts
  (mechanism or protocol) between named sources.
- `Evaluation anchors:` — one to three benchmarks, datasets, metrics, or
  protocols the sources use, by name.
- `Comparison axes:` — short atomic phrases separated by semicolons; derive
  them from comparable mechanisms, settings, metrics and failure modes
  that the subsection's named sources actually report.

## Quality bar

- specific to the subsection: two subsections must not share a bullet
- phrased as coverage requirements for the writer, not as narration
- conservative when evidence is thin: say what the sources leave open
- every bullet that asserts something about a paper ends with its
  `source_id`s in brackets

## Avoid

- stems like "This subsection discusses the topic."
- placeholder tokens (`TODO`, `TBD`, `FIXME`, `XXX`) or the scaffold marker;
  the `scaffold-absent` gate fails the step on any of them
- generic bullets with no topic terms
- bullets no source in `core_set.csv` could support
