from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable

from tooling.common import load_workspace_goal_constraints, pipeline_profile
from tooling.quality_checks.common import QualityIssue, has_placeholder_markers


def check_deliverable_selfloop_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next(
        (path for path in outputs if path.endswith("DELIVERABLE_SELFLOOP_TODO.md")),
        "output/DELIVERABLE_SELFLOOP_TODO.md",
    )
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            QualityIssue(
                code="missing_deliverable_selfloop_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [
            QualityIssue(
                code="deliverable_selfloop_placeholders",
                message=f"`{report_rel}` contains placeholders/ellipsis.",
            )
        ]
    if "- Status: PASS" not in text:
        return [
            QualityIssue(
                code="deliverable_selfloop_not_pass",
                message=f"`{report_rel}` is not PASS.",
            )
        ]
    return []


def check_latex_scaffold(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "latex/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_main_tex", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    profile = pipeline_profile(workspace)

    issues: list[QualityIssue] = []
    if profile not in {"source-tutorial"} and "\\begin{abstract}" not in text:
        issues.append(QualityIssue(code="latex_missing_abstract", message="LaTeX output has no `\\begin{abstract}` block."))
    if profile not in {"source-tutorial"} and "\\bibliography{../citations/ref}" not in text:
        issues.append(QualityIssue(code="latex_missing_bib", message="LaTeX output does not reference `../citations/ref.bib`."))
    # Heuristics: markdown artifacts should not leak into TeX.
    if "[@" in text:
        issues.append(QualityIssue(code="latex_markdown_cites", message="LaTeX still contains markdown cite markers like `[@...]`."))
    if "**" in text:
        issues.append(QualityIssue(code="latex_markdown_bold", message="LaTeX still contains markdown bold markers `**...**`."))
    if "## " in text or "### " in text:
        issues.append(QualityIssue(code="latex_markdown_headings", message="LaTeX still contains markdown headings like `##`/`###`."))
    return issues


def check_latex_compile_qa(
    workspace: Path,
    outputs: list[str],
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> list[QualityIssue]:
    pdf_rel = outputs[0] if outputs else "latex/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/LATEX_BUILD_REPORT.md"

    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    log_path = workspace / "latex" / "main.log"

    if not pdf_path.exists():
        return [QualityIssue(code="missing_main_pdf", message=f"`{pdf_rel}` does not exist.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_build_report", message=f"`{report_rel}` does not exist.")]

    report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    issues: list[QualityIssue] = []
    profile = pipeline_profile(workspace)

    if "Status: SUCCESS" not in report_text and "- Status: SUCCESS" not in report_text:
        issues.append(
            QualityIssue(
                code="latex_build_not_success",
                message=f"`{report_rel}` does not report SUCCESS; fix LaTeX build errors and re-run compile.",
            )
        )

    # Prefer the final LaTeX log for undefined-citation checks. The build report may
    # include warning counters (e.g., `citation_undefined: N`) which are not proof
    # that the final PDF still contains unresolved cites.
    undefined_text = ""
    if log_path.exists():
        undefined_text = log_path.read_text(encoding="utf-8", errors="ignore")
    else:
        undefined_text = report_text

    if re.search(r"(?im)^Package\s+natbib\s+Warning: Citation.+undefined", undefined_text) or re.search(
        r"(?im)There were undefined citations", undefined_text
    ) or re.search(r"(?im)There were undefined references", undefined_text) or re.search(
        r"(?im)^LaTeX\s+Warning: Reference.+undefined", undefined_text
    ):
        issues.append(
            QualityIssue(
                code="latex_undefined_citations",
                message="LaTeX build reports undefined citations/references; ensure all cited keys exist in `citations/ref.bib` and rerun until warnings disappear.",
            )
        )

    if re.search(r"(?im)^LaTeX Warning: Float too large for page", undefined_text):
        issues.append(
            QualityIssue(
                code="latex_float_too_large",
                message="LaTeX build still has `Float too large for page` warnings; shrink or split oversized tables/figures and recompile.",
            )
        )

    if re.search(r"(?im)^Missing character:", undefined_text):
        issues.append(
            QualityIssue(
                code="latex_missing_character",
                message="LaTeX build still reports missing Unicode glyphs; add an explicit mapping or sanitize the generated TeX before recompiling.",
            )
        )

    sample_text = ""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = int(len(doc))
        sample_pages = min(pages, 4)
        for i in range(sample_pages):
            try:
                sample_text += doc.load_page(i).get_text("text") + "\n"
            except Exception:
                continue
        doc.close()
    except Exception as exc:
        try:
            import subprocess

            pdfinfo = which("pdfinfo")
            if not pdfinfo:
                raise exc
            proc = subprocess.run([pdfinfo, str(pdf_path)], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pdfinfo failed")
            m = re.search(r"(?im)^Pages:\s+(\d+)\b", proc.stdout or "")
            if not m:
                raise RuntimeError("pdfinfo output missing page count")
            pages = int(m.group(1))
        except Exception as inner_exc:
            issues.append(
                QualityIssue(
                    code="pdf_page_count_unavailable",
                    message=f"Could not compute PDF page count for `{pdf_rel}` ({type(inner_exc).__name__}: {inner_exc}).",
                )
            )
            return issues

    constraints = load_workspace_goal_constraints(workspace)
    page_range = constraints.get("page_range") if isinstance(constraints.get("page_range"), dict) else {}
    min_pages = int(page_range.get("min") or (4 if profile == "source-tutorial" else 8))
    max_pages = int(page_range.get("max") or 0)
    if pages < min_pages:
        issues.append(
            QualityIssue(
                code="pdf_too_short",
                message=f"`{pdf_rel}` is too short ({pages} pages); expand the draft until the compiled PDF has >= {min_pages} pages.",
            )
        )
    if max_pages and pages > max_pages:
        issues.append(
            QualityIssue(
                code="pdf_too_long",
                message=(
                    f"`{pdf_rel}` exceeds the Goal page limit ({pages} pages; target {min_pages}-{max_pages} total PDF pages). "
                    "Compress layout or prose without dropping required evidence, then recompile."
                ),
            )
        )

    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", sample_text) or "(placeholder)" in sample_text.lower() or "<!-- SCAFFOLD" in sample_text:
        issues.append(
            QualityIssue(
                code="pdf_contains_placeholders",
                message="PDF still contains placeholder text (TODO/TBD/FIXME/SCAFFOLD); rewrite the draft and recompile.",
            )
        )

    return issues


def check_beamer_scaffold(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "latex/slides/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_beamer_tex", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[QualityIssue] = []
    if "\\documentclass" not in text or "beamer" not in text:
        issues.append(QualityIssue(code="beamer_missing_class", message=f"`{out_rel}` is not a Beamer document."))
    if "\\begin{frame}" not in text:
        issues.append(QualityIssue(code="beamer_missing_frames", message=f"`{out_rel}` has no frame structure."))
    if "## " in text or "### " in text:
        issues.append(QualityIssue(code="beamer_markdown_headings", message=f"`{out_rel}` still contains markdown headings."))
    return issues


def check_beamer_compile_qa(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    pdf_rel = outputs[0] if outputs else "latex/slides/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/SLIDES_BUILD_REPORT.md"
    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    if not pdf_path.exists():
        return [QualityIssue(code="missing_beamer_pdf", message=f"`{pdf_rel}` does not exist.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_slides_build_report", message=f"`{report_rel}` does not exist.")]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if "- Status: PASS" not in text and "Status: PASS" not in text:
        return [QualityIssue(code="beamer_build_not_pass", message=f"`{report_rel}` is not PASS.")]
    return []


def check_contract_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith('CONTRACT_REPORT.md')), 'output/CONTRACT_REPORT.md')
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code='missing_contract_report', message=f'`{out_rel}` is missing or empty.')]

    text = path.read_text(encoding='utf-8', errors='ignore').strip()
    if not text:
        return [QualityIssue(code='empty_contract_report', message=f'`{out_rel}` is empty.')]
    if has_placeholder_markers(text) or '…' in text:
        return [QualityIssue(code='contract_report_placeholders', message=f'`{out_rel}` contains placeholders/ellipsis; regenerate after fixing missing artifacts.')]

    ok_status = bool(re.search(r'(?im)^-\s*Status:\s*PASS\b', text))
    ok_complete = bool(re.search(r'(?im)^-\s*Pipeline complete \(units\):\s*yes\b', text))
    if ok_status and ok_complete:
        return []

    return [
        QualityIssue(
            code='contract_report_not_pass',
            message=(
                f'`{out_rel}` is not PASS (or pipeline not complete). '
                'Fix missing artifacts / unit statuses and rerun `artifact-contract-auditor`.'
            ),
        )
    ]
