from __future__ import annotations

import argparse
import re
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

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["latex/main.tex"]
    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    draft_path = workspace / "output" / "DRAFT.md"
    if not draft_path.exists():
        raise SystemExit(f"Missing input: {draft_path}")

    md = draft_path.read_text(encoding="utf-8", errors="ignore")
    title = _read_first_h1(md) or _read_goal(workspace) or "Survey"
    body = _markdown_to_latex(md)
    use_ctex = _has_cjk(md)

    tex = "\n".join(
        [
            (r"\documentclass[UTF8,a4paper,11pt]{ctexart}" if use_ctex else r"\documentclass[a4paper,11pt]{article}"),
            "",
            # xelatex-friendly defaults; keep English-looking front matter unless CJK is present.
            ("" if use_ctex else r"\usepackage{fontspec}"),
            r"\usepackage[a4paper,margin=1in]{geometry}",
            r"\usepackage{hyperref}",
            r"\hypersetup{colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue}",
            r"\usepackage{enumitem}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{array}",
            r"\newcolumntype{Y}{>{\raggedright\arraybackslash}X}",
            r"\usepackage[numbers]{natbib}",
            r"\usepackage{url}",
            "",
            rf"\title{{{_escape_latex(title)}}}",
            r"\author{}",
            r"\date{\today}",
            "",
            r"\setlist[itemize]{noitemsep,topsep=0.25em,leftmargin=*}",
            r"\setcounter{tocdepth}{2}",
            "",
            r"\begin{document}",
            r"\maketitle",
            "",
            r"\tableofcontents",
            r"\newpage",
            "",
            body.strip(),
            "",
            r"\bibliographystyle{plainnat}",
            r"\bibliography{../citations/ref}",
            "",
            r"\end{document}",
            "",
        ]
    )

    atomic_write_text(out_path, tex)
    return 0


def _read_goal(workspace: Path) -> str:
    goal_path = workspace / "GOAL.md"
    if not goal_path.exists():
        return ""
    for line in goal_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", ">", "<!--")):
            continue
        low = line.lower()
        if "写一句话描述" in line or "fill" in low:
            continue
        return line
    return ""


def _has_cjk(text: str) -> bool:
    # If the draft contains CJK characters, prefer ctex so the PDF renders correctly.
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _read_first_h1(md: str) -> str:
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = []
    for ch in text:
        out.append(replacements.get(ch, ch))
    return "".join(out)


_CITE_SINGLE = re.compile(r"\[@([A-Za-z0-9:_-]+)\]")
_BR = re.compile(r"(?i)<br\s*/?>")
_CITE_BLOCK = re.compile(r"\[@([^\]]+)\]")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def _convert_inline(text: str) -> str:
    placeholders: dict[str, str] = {}
    idx = 0

    def _ph(repl: str) -> str:
        nonlocal idx
        token = f"__LATEX_PH_{idx}__"
        idx += 1
        placeholders[token] = repl
        return token

    def _cite(m: re.Match[str]) -> str:
        inside = (m.group(1) or "").strip()
        keys = re.findall(r"[A-Za-z0-9:_-]+", inside)
        if not keys:
            return ""
        uniq: list[str] = []
        for k in keys:
            if k not in uniq:
                uniq.append(k)
        return _ph(rf"\citep{{{','.join(uniq)}}}")

    def _br(m: re.Match[str]) -> str:
        return _ph(r"\newline ")

    text = _BR.sub(_br, text)

    # Multi-cite first, then fall back to single-cite.
    text = _CITE_BLOCK.sub(_cite, text)
    text = _CITE_SINGLE.sub(_cite, text)

    def _code(m: re.Match[str]) -> str:
        return _ph(r"\texttt{" + _escape_latex(m.group(1)) + "}")

    text = _INLINE_CODE.sub(_code, text)

    def _bold(m: re.Match[str]) -> str:
        inner = m.group(1)
        return _ph(r"\textbf{" + _escape_latex(inner) + "}")

    def _italic(m: re.Match[str]) -> str:
        inner = m.group(1)
        return _ph(r"\emph{" + _escape_latex(inner) + "}")

    text = _BOLD.sub(_bold, text)
    text = _ITALIC.sub(_italic, text)

    escaped = _escape_latex(text)
    for token, repl in placeholders.items():
        escaped = escaped.replace(_escape_latex(token), repl)
    return escaped


def _markdown_to_latex(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []

    in_itemize = False
    in_abstract = False

    def _close_itemize() -> None:
        nonlocal in_itemize
        if in_itemize:
            out.append(r"\end{itemize}")
            out.append("")
            in_itemize = False

    def _close_abstract() -> None:
        nonlocal in_abstract
        if in_abstract:
            _close_itemize()
            out.append(r"\end{abstract}")
            out.append("")
            in_abstract = False

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped:
            _close_itemize()
            out.append("")
            i += 1
            continue

        if stripped.startswith("<!--") and stripped.endswith("-->"):
            # Drop HTML comments (often used as scaffold markers).
            _close_itemize()
            i += 1
            continue

        if stripped.startswith("# "):
            # Title handled in preamble.
            i += 1
            continue

        if stripped.startswith("## "):
            _close_itemize()
            heading = _strip_heading_prefix(stripped[3:].strip())
            heading_low = heading.lower()
            if heading_low in {"abstract", "摘要"}:
                _close_abstract()
                out.append(r"\begin{abstract}")
                out.append("")
                in_abstract = True
                i += 1
                continue
            if heading_low in {"references", "bibliography"}:
                # Bibliography is injected after the body.
                _close_abstract()
                i += 1
                continue
            _close_abstract()
            out.append(rf"\section{{{_escape_latex(heading)}}}")
            out.append("")
            i += 1
            continue

        if stripped.startswith("### "):
            _close_itemize()
            _close_abstract()
            heading = _strip_heading_prefix(stripped[4:].strip())
            out.append(rf"\subsection{{{_escape_latex(heading)}}}")
            out.append("")
            i += 1
            continue

        if stripped.startswith("#### "):
            _close_itemize()
            _close_abstract()
            heading = _strip_heading_prefix(stripped[5:].strip())
            out.append(rf"\subsubsection{{{_escape_latex(heading)}}}")
            out.append("")
            i += 1
            continue

        if _is_table_header(stripped) and i + 1 < len(lines) and _is_table_separator(lines[i + 1].strip()):
            _close_itemize()
            _close_abstract()
            table_lines = [stripped, lines[i + 1].strip()]
            j = i + 2
            while j < len(lines):
                nxt = lines[j].rstrip("\n")
                if not nxt.strip():
                    break
                if "|" not in nxt:
                    break
                table_lines.append(nxt.strip())
                j += 1
            out.extend(_render_table(table_lines, convert_inline=_convert_inline))
            out.append("")
            i = j
            continue

        if stripped.startswith("- "):
            if not in_itemize:
                out.append(r"\begin{itemize}")
                in_itemize = True
            out.append(r"\item " + _convert_inline(stripped[2:].strip()))
            i += 1
            continue

        _close_itemize()
        out.append(_convert_inline(stripped))
        i += 1

    _close_itemize()
    _close_abstract()
    return "\n".join(out).strip() + "\n"


def _is_table_header(line: str) -> bool:
    line = (line or "").strip()
    if "|" not in line:
        return False
    # Avoid treating single "a | b" sentences as tables.
    cells = _split_md_row(line)
    return len(cells) >= 2


def _is_table_separator(line: str) -> bool:
    line = (line or "").strip()
    if "|" not in line and "-" not in line:
        return False
    # Examples: |---|---| ; ---|--- ; |:---|---:|
    return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", line))


def _split_md_row(line: str) -> list[str]:
    line = (line or "").strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _render_table(lines: list[str], *, convert_inline) -> list[str]:
    # lines: header, separator, row...
    header = _split_md_row(lines[0]) if lines else []
    rows = [_split_md_row(ln) for ln in lines[2:]] if len(lines) > 2 else []
    ncols = max([len(header)] + [len(r) for r in rows] + [0])
    if ncols <= 0:
        return []
    header = (header + [""] * ncols)[:ncols]
    rows = [(r + [""] * ncols)[:ncols] for r in rows]

    colspec = "l" + ("".join(["Y" for _ in range(ncols - 1)]) if ncols > 1 else "")
    out: list[str] = []
    out.append(r"\begin{center}")
    out.append(rf"\begin{{tabularx}}{{\linewidth}}{{{colspec}}}")
    out.append(r"\toprule")
    out.append(" & ".join([convert_inline(c) for c in header]) + r" \\")
    out.append(r"\midrule")
    for r in rows:
        out.append(" & ".join([convert_inline(c) for c in r]) + r" \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabularx}")
    out.append(r"\end{center}")
    return out


def _strip_heading_prefix(text: str) -> str:
    # Avoid duplicated numbering like "\section{1 Introduction}".
    text = (text or "").strip()
    return re.sub(r"^\d+(?:\.\d+)*\s+", "", text)


if __name__ == "__main__":
    raise SystemExit(main())
