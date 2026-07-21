---
name: idea-memo-writer
description: |
  Synthesize the shortlist into a discussion-ready research idea brainstorm memo, writing `output/REPORT.md`, `output/APPENDIX.md`, and `output/REPORT.json`.
  **Trigger**: idea memo, brainstorm memo, research direction memo, report md, 研究备忘录, brainstorm report.
  **Use when**: the shortlist exists and you want the final reader-facing brainstorm deliverable for PI / PhD discussion.
---

# Idea Memo Writer

Goal: turn the shortlist into a discussion-ready memo.

## Load Order

Always read:
- `references/overview.md`
- `references/report_structure.md`

## Script Boundary

Use `scripts/run.py` only for:
- deterministic assembly of the report from trace artifacts
- calling `tooling/ideation.py` library functions for rendering

Do not treat `run.py` as the place for:
- ideation heuristics or scoring logic
- hardcoded report prose templates

The final memo should feel like:
- an advisor-ready discussion memo rather than workflow notes,
- paper-specific in its evidence hooks and appendix reading guide,
- explicit about rank logic and quick kill criteria,

and still feel like:
- a strong brainstorming artifact,
- grounded in the literature,
- rich enough for PI/PhD discussion,
- but not frozen into a rigid project execution spec.

## Script

### Quick Start

- `uv run python .codex/skills/idea-memo-writer/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Assemble the brainstorm memo for a workspace:
  - `uv run python .codex/skills/idea-memo-writer/scripts/run.py --workspace workspaces/brainstorm-llm-agents`
