---
name: latex-scaffold
description: |
  Scaffold a LaTeX project (`latex/main.tex`, optional bibliography wiring, structure) from an existing Markdown draft.
  **Trigger**: latex scaffold, md→tex, LaTeX 项目骨架, 生成 main.tex.
  **Use when**: 需要 LaTeX/PDF 交付（例如 arxiv-survey-latex pipeline），且 draft 已生成/已进入写作阶段。
---

# LaTeX Scaffold

Convert the approved Markdown draft into a minimal, buildable LaTeX project.

This is a deterministic conversion step; prose quality should already be addressed in `output/DRAFT.md`.

## Inputs

- `output/DRAFT.md` or `output/TUTORIAL.md`
- optional: `citations/ref.bib`

## Outputs

- `latex/main.tex` (and any required LaTeX support files)

## Workflow

1. Create `latex/` directory if missing.
2. Create `latex/main.tex` with sections matching the outline.
3. Wire bibliography to `citations/ref.bib` when that file exists.

## Quality checklist

- [ ] `latex/main.tex` exists.
- [ ] If `citations/ref.bib` exists, `latex/main.tex` references it.

## Script

### Quick Start

- `uv run python .codex/skills/latex-scaffold/scripts/run.py --help`
- `uv run python .codex/skills/latex-scaffold/scripts/run.py --workspace <workspace>`

### All Options

- See `--help` (inputs/outputs are taken from the unit runner when used via pipeline)

### Examples

- Build `latex/main.tex` from `output/DRAFT.md` or `output/TUTORIAL.md`:
  - `uv run python .codex/skills/latex-scaffold/scripts/run.py --workspace <workspace>`

### Notes

- The generated `latex/main.tex` includes a table of contents (tocdepth=2) for readability.
- Language default: the scaffold uses `article` (English-looking front matter). If the draft contains CJK characters, it switches to `ctexart` so the PDF renders correctly.
- Conversion rules (high level):
  - Headings `##/###/####` → `\section/\subsection/\subsubsection` (strips leading numeric prefixes like `1.2`).
  - Headings starting with `Appendix` / `附录` trigger `\appendix` once, then render as appendix sections.
  - Bold caption lines like `**Table 1. ...**` / `**Appendix Table A1. ...**` immediately before a Markdown table become a LaTeX `table` float with `\caption{...}` and a stable `\label{tab:...}`.
  - `## Abstract` → `abstract` environment.
  - `[@Key]` or `[@Key1; @Key2]` → `\citep{Key}` / `\citep{Key1,Key2}`.
  - Inline markdown `**bold**` / `*italic*` / `` `code` `` → `\textbf{}` / `\emph{}` / `\texttt{}`.

## Troubleshooting

### Issue: the generated `latex/main.tex` still contains Markdown markers

**Fix**:
- Re-run `latex-scaffold` and ensure the input `output/DRAFT.md` is clean (no `##`, no `**`, no `[@...]` syntax that isn""t handled).

### Issue: citations are missing in LaTeX

**Fix**:
- Ensure `citations/ref.bib` exists and the scaffold points bibliography to it; then compile with `latex-compile-qa`.
