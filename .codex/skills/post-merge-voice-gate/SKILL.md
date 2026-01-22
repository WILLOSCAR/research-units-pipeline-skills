---
name: post-merge-voice-gate
description: |
  Post-merge paper-voice gate: detect planner-talk / axis-label artifacts introduced during merge (especially from `outline/transitions.md`), then route fixes back to the earliest source.
  **Trigger**: post-merge voice gate, merge voice gate, transition leakage, planner talk, 合并后口吻门, 过渡句污染.
  **Use when**: `section-merger` has produced `output/DRAFT.md` and you want to ensure merge-injected text won't drag the draft into generator voice before polishing.
  **Skip if**: you are still pre-merge (no `output/DRAFT.md`) or you plan to rework structure upstream first.
  **Network**: none.
  **Guardrail**: analysis-only; do not edit `output/DRAFT.md`; do not invent facts/citations; write only the report + routing.
---

# Post-merge Voice Gate (treat transitions as injected prose)

Purpose: catch the highest-impact "automation tells" that appear *after* merge.

Why this exists:
- `outline/transitions.md` is injected verbatim into `output/DRAFT.md`.
- Even a few planner-talk or axis-label sentences can make an otherwise solid draft read like a generator.
- Fixes should land at the *earliest responsible artifact* (usually `outline/transitions.md`), not as ad-hoc edits in the merged draft.

This skill is a gate:
- It writes a report (`output/POST_MERGE_VOICE_REPORT.md`).
- If FAIL, it also appends to `output/QUALITY_GATE.md` so the workspace remains debuggable.

## Role prompt: Voice Gatekeeper (paper voice, no new facts)

```text
You are the post-merge voice gatekeeper for a survey draft.

Your job is to detect high-signal generator voice that entered the draft via merge injection:
- planner-talk transitions ("To keep the chapter...", "The remaining uncertainty is...")
- slide/navigation narration ("Next, we move...", "We now turn...")
- axis-label slash lists (A / B / C; planning/memory) used as prose

Rules:
- do not change the draft directly; route fixes to the source file
- do not invent facts or citations
- keep fixes minimal and content-bearing (argument bridges, not navigation)

Output:
- a short PASS/FAIL report with a routing plan
```

## Inputs

- `output/DRAFT.md`
- `outline/transitions.md`


## Output

- `output/POST_MERGE_VOICE_REPORT.md` (always written)

## What this gate checks (high-signal only)

- Planner-talk transition stems (construction notes that read like comments in the paper body)
- Slash-list axis markers in injected transitions (A / B / C)
- Slide/navigation narration that should be argument bridges

## Rewrite triggers (if you see these, FAIL and route)

These stems are high-signal generator voice once injected into the draft body:
- "To keep ..." / "To keep the chapter..."
- "The remaining uncertainty is ..."
- "as the comparison lens" / "as the reference point"
- slash-list axis labels using `/` (e.g., "retrieval / index / write policy")

## Routing rules (earliest responsible artifact)

- If the offending phrase appears in `outline/transitions.md`:
  - Fix: rerun `transition-weaver` (or hand-edit `outline/transitions.md`), then rerun `section-merger`.
- Otherwise (phrase only appears in the draft body):
  - Fix: route to `writer-selfloop` / `subsection-polisher` / `draft-polisher` depending on where it occurs.

## Mini rewrite examples (do not copy verbatim)

Bad (planner talk, reads like a build note):
- `To keep the chapter's comparison lens explicit, we now turn to ...`

Better (argument bridge, content-bearing):
- `Once interface contracts fix what actions are executable, the next bottleneck is how agents choose among those actions under uncertainty and budget constraints.`

Bad (axis-label slash list):
- `... under mechanism/architecture/data trade-offs ...`

Better (natural prose):
- `... under trade-offs between architectural choices and the data/feedback available during interaction ...`

## Script (optional; deterministic gate)

### Quick Start

- `python .codex/skills/post-merge-voice-gate/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; default: `output/DRAFT.md;outline/transitions.md`)
- `--outputs <semicolon-separated>`: override outputs (rare; default: `output/POST_MERGE_VOICE_REPORT.md`)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Run right after `section-merger` (recommended):
  - `python .codex/skills/post-merge-voice-gate/scripts/run.py --workspace workspaces/<ws>`

### Notes

- The script is analysis-only; it never edits content.
- On FAIL it writes `output/POST_MERGE_VOICE_REPORT.md` and appends a short record to `output/QUALITY_GATE.md`.
