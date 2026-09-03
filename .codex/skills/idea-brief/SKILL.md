---
name: idea-brief
description: "Lock an ideation run into a single-source-of-truth brainstorm brief (`output/trace/IDEA_BRIEF.md`) and a replayable multi-query plan (`queries.md`)."
---

# Idea Brief

## Triggers & routing

- **Trigger**: idea brief, ideation brief, research ideas, brainstorm, 找 idea, 选题, 点子, 找方向.
- **Use when**: the user wants research ideas and their input is long / multi-turn; you need to clarify topic + constraints before retrieval.


Turn a fuzzy ideation request into an auditable brainstorm contract for the later ideation stack.

This skill does **not** retrieve papers.
It only locks topic, audience, constraints, exclusions, rubric, query buckets, and target artifact shape into:

- `output/trace/IDEA_BRIEF.md`
- `queries.md`
- `DECISIONS.md`

## Inputs
- `GOAL.md`
- `DECISIONS.md`
- `queries.md`

## Outputs
- `output/trace/IDEA_BRIEF.md`
- `queries.md`
- `DECISIONS.md`

## Execution notes

This skill starts from `GOAL.md`, then refines the topic/constraints into `output/trace/IDEA_BRIEF.md`, updates `queries.md`, and records blockers or approvals in `DECISIONS.md`.

Read `references/overview.md` before changing the package shape or the brief contract.
`assets/brief_contract.json` is the machine-readable source for:

- required brief sections
- goal / audience framing
- rubric rows
- query bucket templates
- default exclusions
- focus placeholder
- shared table/open-question text
- decisions bootstrap text

## Script

### Quick Start

- `uv run python .codex/skills/idea-brief/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`
- `--unit-id <id>`
- `--inputs <a;b;...>`
- `--outputs <a;b;...>`
- `--checkpoint <C*>`

### Examples

- `uv run python .codex/skills/idea-brief/scripts/run.py --workspace <workspace>`
