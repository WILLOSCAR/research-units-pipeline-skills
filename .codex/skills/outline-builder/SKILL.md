---
name: outline-builder
description: |
  Convert a taxonomy (`outline/taxonomy.yml`) into a bullet-only outline (`outline/outline.yml`) with sections/subsections.
  **Trigger**: outline builder, bullet outline, outline.yml, 大纲生成, bullets-only.
  **Use when**: structure 阶段（NO PROSE），已有 taxonomy，需要生成可映射/可写作的章节与小节骨架（每小节≥3 bullets）。
  **Skip if**: 已经有批准过且可映射的 outline（避免无意义 churn）。
  **Network**: none.
  **Guardrail**: bullets-only；移除 TODO/模板语句；每小节至少 3 个可检查 bullets。
---

# Outline Builder

Convert a taxonomy into a **checkable, mappable outline** (bullets only).

Bullets should describe *what the section must cover*, not draft prose.

## When to use

- You have a taxonomy and need an outline for mapping papers and building evidence.
- You want each subsection to have concrete “coverage requirements” (axes, comparisons, evaluation).

## When not to use

- You already have an approved outline (don’t rewrite for style).

## Input

- `outline/taxonomy.yml`
- Optional style references (paper-like section sizing):
  - `ref/agent-surveys/STYLE_REPORT.md`
  - `ref/agent-surveys/text/`

## Output

- `outline/outline.yml`

## Workflow (heuristic)
Uses: `outline/taxonomy.yml`.

Optional style calibration (recommended for paper-like structure):
- Read `ref/agent-surveys/STYLE_REPORT.md` to sanity-check top-level section counts and typical subsection sizing.
- Skim 1–2 examples under `ref/agent-surveys/text/` to imitate *structure* (not wording), keeping your outline at ~6–8 H2 sections with fewer, thicker H3s.

1. Translate taxonomy nodes into section headings that read like a survey structure.
2. For each subsection, write **≥3 bullets** that are:
   - topic-specific (names of mechanisms, tasks, benchmarks, failure modes)
   - checkable (someone can verify whether the subsection covered it)
   - useful for mapping (papers can be assigned to each bullet/axis)
3. Prefer bullets that force synthesis later:
   - “Compare X vs Y along axes A/B/C”
   - “What evaluation setups are standard, and what they miss”
   - “Where methods fail (latency, tool errors, jailbreaks, reward hacking…)”

## Quality checklist

- [ ] `outline/outline.yml` exists and is bullets-only (no paragraphs).
- [ ] Every subsection has ≥3 non-generic bullets.
- [ ] Bullets are not copy-pasted templates across subsections.

## Common failure modes (and fixes)

- **Template bullets everywhere** → replace with domain terms + evaluation axes specific to that subsection.
- **Bullets too vague** (“Discuss limitations”) → name *which* limitations and *how to test* them.
- **Outline too flat/too deep** → aim for sections a reader can navigate (usually 6–10 sections, 2–5 subsections each).

## Helper script (optional)

### Quick Start

- `python .codex/skills/outline-builder/scripts/run.py --help`
- `python .codex/skills/outline-builder/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help` (this helper is intentionally minimal)

### Examples

- Generate a baseline bullets-only outline, then refine bullets:
  - Run the helper once, then replace every generic bullet / `TODO` with topic-specific, checkable bullets.

### Notes

- The script generates a baseline bullets-only outline and never overwrites non-placeholder work.
- Paper-like default: it inserts `Introduction` and `Related Work` as fixed H2 sections before taxonomy-driven chapters.
- In `pipeline.py --strict` it will be blocked only if placeholder markers (TODO/TBD/FIXME/(placeholder)) remain.

## Troubleshooting

### Common Issues

#### Issue: Outline still has `TODO` / scaffold bullets

**Symptom**:
- Quality gate blocks `outline_scaffold`.

**Causes**:
- Helper script generated a scaffold; bullets were not rewritten.

**Solutions**:
- Replace every generic bullet with topic-specific, checkable bullets (axes, comparisons, evaluation setups, failure modes).
- Keep bullets-only (no prose paragraphs).

#### Issue: Outline bullets are mostly generic templates

**Symptom**:
- Quality gate blocks `outline_template_bullets`.

**Causes**:
- Too many “Define problem…/Benchmarks…/Open problems…” template bullets.

**Solutions**:
- Add concrete terms, datasets, evaluation metrics, and known failure modes per subsection.

### Recovery Checklist

- [ ] Every subsection has ≥3 non-template bullets.
- [ ] No `TODO`/`(placeholder)` remains.
