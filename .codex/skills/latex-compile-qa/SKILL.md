---
name: latex-compile-qa
description: "Compile a LaTeX project and run basic QA (missing refs, bib errors, broken citations), producing `latex/main.pdf` and a build report."
---

# LaTeX Compile + QA

## Triggers & routing

- **Trigger**: latex compile, build PDF, LaTeX errors, missing refs, 编译PDF, 引用错误.
- **Use when**: 已有 `latex/main.tex`（通常来自 `latex-scaffold`），需要确认可编译并输出失败原因报告。


Compile the LaTeX project and produce a PDF (when the toolchain is available), plus a short build report.

This step is deterministic; if compilation fails, record actionable diagnostics rather than guessing.

## Inputs

- `latex/main.tex`
- `citations/ref.bib`

## Outputs

- `latex/main.pdf` (if compilation succeeds)
- `output/LATEX_BUILD_REPORT.md` (recommended)

## Workflow

1. Run a LaTeX build (e.g., `latexmk`) if available.
2. Fix missing packages, missing bib entries, and unresolved references.
3. Record remaining issues in a build report.

## Quality checklist

- [ ] `latex/main.pdf` exists only when compilation succeeds; failed builds must remove stale PDFs and explain the failure in `output/LATEX_BUILD_REPORT.md`.
- [ ] For `arxiv-survey-latex` deliverables: `latex/main.pdf` is >= 8 pages and has no undefined citations/references (strict gate).

## Script

### Quick Start

- `uv run python .codex/skills/latex-compile-qa/scripts/run.py --help`
- `uv run python .codex/skills/latex-compile-qa/scripts/run.py --workspace <workspace>`

### All Options

- See `--help` (inputs/outputs are taken from the unit runner when used via pipeline)

### Examples

- Compile + produce report:
  - `uv run python .codex/skills/latex-compile-qa/scripts/run.py --workspace <workspace>`

### Notes

- Uses `latexmk -xelatex -bibtex` when available.
- Always writes `output/LATEX_BUILD_REPORT.md` (success or failure).
- Report includes page count + warning summary when available.

## Troubleshooting

### Common Issues

#### Issue: `latexmk` not found

**Symptom**:
- Build report says “latexmk not found in PATH”.

**Causes**:
- LaTeX toolchain is not installed.

**Solutions**:
- Install a TeX distribution that includes `latexmk`.
- If you can’t install tools, still use `latex-scaffold` to generate `latex/main.tex` and compile elsewhere.

#### Issue: Build fails with bib/ref errors

**Symptom**:
- Report shows missing citations/refs or BibTeX errors.

**Causes**:
- `citations/ref.bib` missing/miswired, or draft contains invalid cite keys.

**Solutions**:
- Ensure `latex/main.tex` points to `../citations/ref.bib` (or the correct relative path).
- Ensure all citation keys exist in `citations/ref.bib`.

### Recovery Checklist

- [ ] Read `output/LATEX_BUILD_REPORT.md` tail for the first actionable error.
- [ ] Confirm `latex/main.tex` exists and bibliography path is correct.
