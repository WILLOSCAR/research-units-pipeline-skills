from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_TABLE_SEP = re.compile(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")


def _is_placeholder(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    if "<!-- scaffold" in low:
        return True
    if "(placeholder)" in low:
        return True
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", low):
        return True
    if "…" in (text or ""):
        return True
    if re.search(r"(?m)\.\.\.+", text or ""):
        return True
    return False


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
    outputs = parse_semicolon_list(args.outputs) or ["outline/tables_appendix.md"]
    out_rel = outputs[0]

    out_path = workspace / out_rel
    report_path = workspace / "output" / "TABLES_APPENDIX_REPORT.md"
    ensure_dir(report_path.parent)

    if not out_path.exists() or out_path.stat().st_size <= 0:
        atomic_write_text(
            report_path,
            "# Appendix tables report\n\n- Status: FAIL\n- Missing: `" + out_rel + "`\n",
        )
        return 2

    text = out_path.read_text(encoding="utf-8", errors="ignore")
    issues: list[str] = []

    if _is_placeholder(text):
        issues.append("contains placeholders/ellipsis")

    if any(ln.lstrip().startswith("#") for ln in text.splitlines()):
        issues.append("contains Markdown headings (#/##/###); keep appendix tables heading-free (merger adds Appendix heading)")

    n_tables = len(re.findall(_TABLE_SEP, text))
    if n_tables < 2:
        issues.append(f"too few Markdown tables ({n_tables}; expected >= 2)")

    if "[@" not in text:
        issues.append("missing citation markers like [@BibKey]")

    # Heuristic: avoid dumping index-style subsection maps into the paper.
    if re.search(r"(?im)^\|\s*subsection\s*\|", text) and re.search(r"(?im)\|\s*axes\s*\|", text):
        issues.append("looks like an internal subsection/axes index table; curate reader-facing Appendix tables instead")

    # Heuristic: <br> is fine, but a dense dump often means an index table.
    br_n = len(re.findall(r"(?i)<br\s*/?>", text))
    if br_n >= 60:
        issues.append(f"high <br> density ({br_n}); tables likely read like internal lists")

    status = "PASS" if not issues else "FAIL"

    rep_lines: list[str] = [
        "# Appendix tables report",
        "",
        f"- Status: {status}",
        f"- Tables detected: {n_tables}",
        f"- <br> count: {br_n}",
    ]

    if issues:
        rep_lines.extend(["", "## Issues"])
        rep_lines.extend(["- " + it for it in issues])

    atomic_write_text(report_path, "\n".join(rep_lines).rstrip() + "\n")
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
