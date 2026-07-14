from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import ensure_dir, load_workspace_goal_constraints, parse_semicolon_list

    workspace = Path(args.workspace).resolve()
    constraints = load_workspace_goal_constraints(workspace)
    page_range = constraints.get("page_range") if isinstance(constraints.get("page_range"), dict) else {}
    page_target = (
        f"{int(page_range.get('min'))}-{int(page_range.get('max'))} total PDF pages"
        if page_range.get("min") and page_range.get("max")
        else ""
    )
    outputs = parse_semicolon_list(args.outputs) or ["latex/main.pdf", "output/LATEX_BUILD_REPORT.md"]

    pdf_rel = outputs[0]
    report_rel = outputs[1] if len(outputs) > 1 else "output/LATEX_BUILD_REPORT.md"
    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel

    tex_path = workspace / "latex" / "main.tex"
    if not tex_path.exists():
        _write_report(report_path, ok=False, message=f"Missing input: {tex_path}")
        return 2

    ensure_dir(pdf_path.parent)
    ensure_dir(report_path.parent)
    _remove_stale_pdf(pdf_path)

    proc, engine = _compile_latex(tex_path)

    built_pdf = tex_path.parent / "main.pdf"
    ok = proc.returncode == 0 and built_pdf.exists()

    if ok and pdf_path != built_pdf:
        shutil.copy2(built_pdf, pdf_path)

    page_count = _pdf_page_count(pdf_path if pdf_path.exists() else built_pdf)
    warnings = _collect_warnings(tex_dir=tex_path.parent, stdout=proc.stdout, stderr=proc.stderr)

    if ok:
        _write_report(
            report_path,
            ok=True,
            message="SUCCESS",
            stdout=proc.stdout,
            stderr=proc.stderr,
            engine=engine,
            page_count=page_count,
            page_target=page_target,
            warnings=warnings,
        )
        return 0

    _remove_stale_pdf(pdf_path)
    if built_pdf != pdf_path:
        _remove_stale_pdf(built_pdf)
    _write_report(
        report_path,
        ok=False,
        message=f"{engine} failed (exit {proc.returncode})",
        stdout=proc.stdout,
        stderr=proc.stderr,
        engine=engine,
        page_count=page_count,
        page_target=page_target,
        warnings=warnings,
    )
    return 2


def _remove_stale_pdf(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _compile_latex(tex_path: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    latexmk = shutil.which("latexmk")
    if latexmk:
        cmd = [
            latexmk,
            "-xelatex",
            "-bibtex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            tex_path.name,
        ]
        proc = subprocess.run(cmd, cwd=str(tex_path.parent), capture_output=True, text=True)
        return proc, "latexmk -xelatex -bibtex"

    xelatex = shutil.which("xelatex")
    bibtex = shutil.which("bibtex")
    if xelatex and bibtex:
        runs: list[subprocess.CompletedProcess[str]] = []
        steps = [
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
            [bibtex, tex_path.stem],
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_path.name],
        ]
        for cmd in steps:
            proc = subprocess.run(cmd, cwd=str(tex_path.parent), capture_output=True, text=True)
            runs.append(proc)
            if proc.returncode != 0:
                break
        stdout = "\n".join([p.stdout for p in runs if p.stdout])
        stderr = "\n".join([p.stderr for p in runs if p.stderr])
        final = runs[-1] if runs else subprocess.CompletedProcess([], 1, "", "")
        merged = subprocess.CompletedProcess(
            args=steps[: len(runs)],
            returncode=final.returncode,
            stdout=stdout,
            stderr=stderr,
        )
        return merged, "xelatex + bibtex"

    missing = []
    if not latexmk:
        missing.append("latexmk")
    if not xelatex:
        missing.append("xelatex")
    if not bibtex:
        missing.append("bibtex")
    proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=f"Missing tools: {', '.join(missing)}")
    return proc, "unavailable toolchain"


def _pdf_page_count(path: Path) -> int | None:
    if not path or not path.exists():
        return None
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        n = int(len(doc))
        doc.close()
        return n
    except Exception:
        pass

    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return None
    try:
        proc = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return None
        m = re.search(r"(?im)^Pages:\s+(\d+)\b", proc.stdout or "")
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _collect_warnings(*, tex_dir: Path, stdout: str, stderr: str) -> dict[str, int]:
    # Prefer the final LaTeX log; latexmk stdout/stderr can include warnings from
    # intermediate runs (e.g., before bibtex is applied), which would create
    # false positives for resolved citations.

    log_path = tex_dir / "main.log"
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    aux_text = "\n".join([stdout or "", stderr or ""]).strip()

    log_patterns: list[tuple[str, str]] = [
        ("citation_undefined", r"(?im)^Package\s+natbib\s+Warning: Citation.+undefined"),
        ("citation_undefined", r"(?im)There were undefined citations"),
        ("reference_undefined", r"(?im)there were undefined references"),
        ("missing_character", r"(?im)^Missing character:"),
        ("float_too_large", r"(?im)^LaTeX Warning: Float too large for page"),
        ("overfull_hbox", r"(?im)^Overfull \\hbox"),
        ("overfull_vbox", r"(?im)^Overfull \\vbox"),
        ("underfull_hbox", r"(?im)^Underfull \\hbox"),
        ("rerun_references", r"(?im)Rerun to get cross-references right"),
    ]
    aux_patterns: list[tuple[str, str]] = [
        ("annotation_out_of_page", r"(?im)^xdvipdfmx:warning:\s+Annotation out of page boundary"),
    ]

    counts: dict[str, int] = {}
    for name, pat in log_patterns:
        counts[name] = counts.get(name, 0) + len(re.findall(pat, log_text))
    for name, pat in aux_patterns:
        counts[name] = counts.get(name, 0) + len(re.findall(pat, aux_text))

    latex_warns = 0
    for ln in log_text.splitlines():
        if "LaTeX Warning:" in ln and "hbox" not in ln.lower():
            latex_warns += 1
    if latex_warns:
        counts["latex_warnings"] = latex_warns

    return {k: v for k, v in counts.items() if v}



def _write_report(
    path: Path,
    *,
    ok: bool,
    message: str,
    stdout: str = "",
    stderr: str = "",
    engine: str = "",
    page_count: int | None = None,
    page_target: str = "",
    warnings: dict[str, int] | None = None,
) -> None:
    from datetime import datetime

    from tooling.common import atomic_write_text

    def _tail(s: str, n: int = 120) -> str:
        lines = (s or "").splitlines()
        if len(lines) <= n:
            return "\n".join(lines)
        return "\n".join(lines[-n:])

    ts = datetime.now().replace(microsecond=0).isoformat()
    warn = warnings or {}

    header_lines = [
        "# LaTeX build report",
        "",
        f"- Timestamp: `{ts}`",
        "- Entry: `latex/main.tex`",
        "- Output: `latex/main.pdf`",
        f"- Engine: `{engine or 'unknown'}`",
    ]
    if page_count is not None:
        header_lines.append(f"- Page count: `{page_count}`")
    if page_target:
        header_lines.append(f"- Goal page target: `{page_target}`")

    content_lines: list[str] = []
    content_lines.extend(header_lines)
    content_lines.extend(
        [
            "",
            "## Result",
            "",
            f"- Status: {'SUCCESS' if ok else 'FAILED'}",
            f"- Message: {message}",
            "",
        ]
    )

    if warn:
        content_lines.extend(["## Warning summary", ""])
        for k in sorted(warn):
            content_lines.append(f"- {k}: {warn[k]}")
        content_lines.append("")

    content_lines.extend(
        [
            "## Stdout (tail)",
            "",
            "```",
            _tail(stdout),
            "```",
            "",
            "## Stderr (tail)",
            "",
            "```",
            _tail(stderr),
            "```",
            "",
        ]
    )

    atomic_write_text(path, "\n".join(content_lines).rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
