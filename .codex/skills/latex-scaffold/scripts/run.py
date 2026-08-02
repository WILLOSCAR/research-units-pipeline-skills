from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


LAYOUT_POLICY_PATH = Path(__file__).resolve().parents[1] / "assets" / "layout_profiles.json"


def _layout_profile(profile: str) -> dict[str, object]:
    payload = json.loads(LAYOUT_POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "latex-layout-profiles.v1":
        raise ValueError(f"Unsupported LaTeX layout policy: {payload.get('schema')!r}")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not isinstance(profiles.get("default"), dict):
        raise ValueError("LaTeX layout policy is missing the default profile")
    selected = dict(profiles["default"])
    override = profiles.get(str(profile or "").strip())
    if isinstance(override, dict):
        selected.update(override)
    if not str(selected.get("margin") or "").strip():
        raise ValueError("LaTeX layout profile is missing margin")
    return selected


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

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list, research_title_from_request
    from tooling.quality_gate import _draft_profile

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["latex/main.tex"]
    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    draft_path = workspace / "output" / "DRAFT.md"
    tutorial_path = workspace / "output" / "TUTORIAL.md"
    profile = ""
    try:
        from tooling.common import load_workspace_pipeline_spec

        spec = load_workspace_pipeline_spec(workspace)
        profile = str(spec.profile or "").strip() if spec is not None else ""
    except Exception:
        profile = ""

    if profile == "source-tutorial" and tutorial_path.exists():
        draft_path = tutorial_path
    elif draft_path.exists() and tutorial_path.exists():
        preview = draft_path.read_text(encoding="utf-8", errors="ignore")
        low_preview = preview.lower()
        if "(placeholder)" in low_preview or "<!-- scaffold" in low_preview or "draft (placeholder)" in low_preview:
            draft_path = tutorial_path
    elif not draft_path.exists():
        draft_path = tutorial_path
    if not draft_path.exists():
        raise SystemExit(f"Missing input: {workspace / 'output' / 'DRAFT.md'} or {workspace / 'output' / 'TUTORIAL.md'}")

    md = draft_path.read_text(encoding="utf-8", errors="ignore")
    draft_profile = _draft_profile(workspace)
    layout = _layout_profile(draft_profile)
    title = _read_first_h1(md) or research_title_from_request(_read_goal(workspace)) or "Survey"
    body = _markdown_to_latex(
        md,
        split_large_tables=bool(layout.get("split_large_tables", True)),
    )
    use_ctex = _has_cjk(md)
    bib_path = workspace / "citations" / "ref.bib"
    include_bibliography = bib_path.exists() and _has_real_bib_entries(bib_path)

    tex = "\n".join(
        [
            (
                r"\documentclass[UTF8,a4paper,11pt]{ctexart}"
                if use_ctex
                else r"\documentclass[a4paper,11pt]{article}"
            ),
            "",
            # xelatex-friendly defaults; keep English-looking front matter unless CJK is present.
            ("" if use_ctex else r"\usepackage{fontspec}"),
            r"\usepackage{newunicodechar}",
            r"\newunicodechar{π}{\ensuremath{\pi}}",
            rf"\usepackage[a4paper,margin={layout['margin']}]{{geometry}}",
            r"\usepackage{hyperref}",
            r"\hypersetup{colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue}",
            r"\usepackage{enumitem}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{array}",
            r"\usepackage{float}",
            r"\newcolumntype{Y}{>{\raggedright\arraybackslash}X}",
            r"\usepackage[numbers]{natbib}",
            r"\usepackage{url}",
            r"\emergencystretch=2em",
            r"\sloppy",
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
            *(
                [r"\tableofcontents", r"\newpage", ""]
                if bool(layout.get("show_table_of_contents", True))
                else []
            ),
            body.strip(),
            "",
            *(
                [
                    *([r"{\small"] if bool(layout.get("compact_bibliography")) else []),
                    r"\bibliographystyle{plainnat}",
                    r"\bibliography{../citations/ref}",
                    *([r"}"] if bool(layout.get("compact_bibliography")) else []),
                ]
                if include_bibliography
                else []
            ),
            "",
            r"\end{document}",
            "",
        ]
    )

    _assert_no_placeholder_residue(tex, context=str(out_path))
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


def _has_real_bib_entries(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return bool(re.search(r"(?m)^@\w+\s*\{", text))


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
_PLACEHOLDER_RESIDUE = re.compile(r"(?:@@LATEXPH\d+@@|(?:__|\\_\\_)LATEX(?:_|\\_)PH(?:_|\\_)\d+(?:__|\\_\\_))")


def _assert_no_placeholder_residue(text: str, *, context: str) -> None:
    match = _PLACEHOLDER_RESIDUE.search(text or "")
    if not match:
        return
    start, end = match.span()
    excerpt = (text or "")[max(0, start - 80):min(len(text or ""), end + 80)].replace("\n", " ")
    raise ValueError(f"Unresolved LaTeX placeholder residue in {context}: {match.group(0)} | excerpt: {excerpt}")


def _restore_placeholders(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for _ in range(len(placeholders) + 1):
        changed = False
        for token, repl in placeholders.items():
            if token in restored:
                restored = restored.replace(token, repl)
                changed = True
        if not changed:
            break
    _assert_no_placeholder_residue(restored, context="inline conversion")
    return restored


def _convert_inline(text: str) -> str:
    placeholders: dict[str, str] = {}
    idx = 0

    def _ph(repl: str) -> str:
        nonlocal idx
        token = f"@@LATEXPH{idx}@@"
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
    return _restore_placeholders(escaped, placeholders)


def _markdown_to_latex(md: str, *, split_large_tables: bool = True) -> str:
    lines = md.splitlines()
    out: list[str] = []

    in_itemize = False
    in_abstract = False

    in_appendix = False
    pending_table_caption: tuple[str, str] | None = None

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
            # Appendix handling: emit \appendix once, and strip the prefix from the heading.
            if heading_low.startswith("appendix") or heading.startswith("Appendix") or heading.startswith("APPENDIX") or heading.startswith("附录"):
                if not in_appendix:
                    out.append(r"\appendix")
                    out.append("")
                    in_appendix = True
                heading = re.sub(r"(?i)^appendix(?:es)?\s*[:\-]?\s*", "", heading).strip()
                heading = re.sub(r"^附录\s*[:：\-]?\s*", "", heading).strip()
                if not heading:
                    heading = "Appendix"

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

        m = re.match(r"^\*\*(?:Appendix\s+)?Table\s+([A-Za-z0-9]+)[\.:]\s+(.+?)\*\*\.?$", stripped)
        if m:
            pending_table_caption = (m.group(1), m.group(2))
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
            cap_id = ""
            cap_text = ""
            if pending_table_caption:
                cap_id, cap_text = pending_table_caption
                pending_table_caption = None
            out.extend(
                _render_table(
                    table_lines,
                    convert_inline=_convert_inline,
                    caption=cap_text,
                    label=cap_id,
                    split_large_tables=split_large_tables,
                )
            )
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
    body = "\n".join(out).strip() + "\n"
    _assert_no_placeholder_residue(body, context="markdown body conversion")
    return body


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


def _render_table(
    lines: list[str],
    *,
    convert_inline,
    caption: str | None = None,
    label: str | None = None,
    split_large_tables: bool = True,
) -> list[str]:
    # lines: header, separator, row...
    header = _split_md_row(lines[0]) if lines else []
    rows = [_split_md_row(ln) for ln in lines[2:]] if len(lines) > 2 else []
    ncols = max([len(header)] + [len(r) for r in rows] + [0])
    if ncols <= 0:
        return []
    header = (header + [""] * ncols)[:ncols]
    rows = [(r + [""] * ncols)[:ncols] for r in rows]

    header_join = " ".join(header).lower()
    colspec = "Y" * ncols
    if ncols >= 3 and re.search(r"\b(refs?|citations?)\b", header_join):
        # Keep the refs column compact; let the other columns share the remaining width.
        colspec = ("Y" * (ncols - 1)) + "l"
    in_table_env = bool(caption)
    lab = re.sub(r"[^a-z0-9]+", "", str(label or "").lower()) if label else ""

    row_text_budget = max(len(" ".join(row)) for row in rows) if rows else 0
    chunk_size = 0
    if in_table_env and split_large_tables:
        if row_text_budget >= 260:
            chunk_size = 2
        elif row_text_budget >= 180 and len(rows) >= 5:
            chunk_size = 3
        elif len(rows) >= 7:
            chunk_size = 4 if row_text_budget >= 120 else 5

    if not chunk_size:
        return _render_table_chunk(
            header=header,
            rows=rows,
            colspec=colspec,
            convert_inline=convert_inline,
            caption=caption,
            label=lab,
            in_table_env=in_table_env,
            table_position="H" if not split_large_tables else "t",
        )

    out: list[str] = []
    chunks = [rows[i:i + chunk_size] for i in range(0, len(rows), chunk_size)]
    for idx, chunk in enumerate(chunks, start=1):
        chunk_caption = caption if idx == 1 else f"{caption} (continued)"
        chunk_label = lab if idx == 1 else ""
        out.extend(
            _render_table_chunk(
                header=header,
                rows=chunk,
                colspec=colspec,
                convert_inline=convert_inline,
                caption=chunk_caption,
                label=chunk_label,
                in_table_env=in_table_env,
                table_position="t",
            )
        )
        if idx != len(chunks):
            out.extend(["", r"\clearpage", ""])
    return out


def _render_table_chunk(
    *,
    header: list[str],
    rows: list[list[str]],
    colspec: str,
    convert_inline,
    caption: str | None,
    label: str,
    in_table_env: bool,
    table_position: str,
) -> list[str]:
    out: list[str] = []
    if in_table_env:
        out.append(rf"\begin{{table}}[{table_position}]")
        out.append(r"\centering")
        out.append(r"\scriptsize")
        out.append(r"\setlength{\tabcolsep}{2.5pt}")
        out.append(r"\renewcommand{\arraystretch}{1.0}")
        out.append(r"\caption{" + convert_inline(caption or "") + "}")
        if label:
            out.append(r"\label{tab:" + label + "}")
    else:
        out.append(r"\begin{center}")

    out.append(rf"\begin{{tabularx}}{{\linewidth}}{{{colspec}}}")
    out.append(r"\toprule")
    out.append(" & ".join([convert_inline(c) for c in header]) + r" \\")
    out.append(r"\midrule")
    for r in rows:
        out.append(" & ".join([convert_inline(c) for c in r]) + r" \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabularx}")
    if in_table_env:
        out.append(r"\end{table}")
    else:
        out.append(r"\end{center}")
    return out


def _strip_heading_prefix(text: str) -> str:
    # Avoid duplicated numbering like "\section{1 Introduction}".
    text = (text or "").strip()
    text = re.sub(r"^\d+(?:\.\d+)*\s+", "", text)
    return re.sub(r"\.+$", "", text).strip()


if __name__ == "__main__":
    raise SystemExit(main())
