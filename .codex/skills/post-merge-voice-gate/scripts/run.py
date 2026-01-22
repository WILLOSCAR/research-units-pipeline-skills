from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _examples(text: str, pattern: str, *, max_examples: int = 3, window: int = 90) -> list[str]:
    out: list[str] = []
    if not text:
        return out
    for m in re.finditer(pattern, text):
        start = max(0, m.start() - int(window))
        end = min(len(text), m.end() + int(window))
        snippet = text[start:end].replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if snippet and snippet not in out:
            out.append(snippet[:220])
        if len(out) >= int(max_examples):
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list
    from tooling.quality_gate import QualityIssue, write_quality_report

    unit_id = str(args.unit_id or "U103").strip() or "U103"

    inputs = parse_semicolon_list(args.inputs) or ["output/DRAFT.md", "outline/transitions.md"]
    outputs = parse_semicolon_list(args.outputs) or ["output/POST_MERGE_VOICE_REPORT.md"]

    draft_rel = next((p for p in inputs if p.endswith("DRAFT.md")), "output/DRAFT.md")
    trans_rel = next((p for p in inputs if p.endswith("transitions.md")), "outline/transitions.md")
    out_rel = outputs[0] if outputs else "output/POST_MERGE_VOICE_REPORT.md"

    draft_path = workspace / draft_rel
    trans_path = workspace / trans_rel
    out_path = workspace / out_rel
    ensure_dir(out_path.parent)

    issues: list[QualityIssue] = []

    if not draft_path.exists() or draft_path.stat().st_size <= 0:
        issues.append(QualityIssue(code="post_merge_missing_draft", message=f"Missing `{draft_rel}`"))
        draft = ""
    else:
        draft = _read(draft_path)

    transitions = _read(trans_path) if trans_path.exists() else ""
    if not trans_path.exists() or trans_path.stat().st_size <= 0:
        issues.append(QualityIssue(code="post_merge_missing_transitions", message=f"Missing `{trans_rel}`"))

    # High-signal planner talk and narration stems.
    patterns: list[tuple[str, str, str]] = [
        ("post_merge_planner_talk_keep_chapter", r"(?i)\bto\s+keep\s+the\s+chapter(?:'|\u2019)?s\b", "planner-talk transition stem ('to keep the chapter...')"),
        ("post_merge_planner_talk_remaining_uncertainty", r"(?i)\bthe\s+remaining\s+uncertainty\s+is\b", "planner-talk transition stem ('the remaining uncertainty is...')"),
        ("post_merge_planner_talk_bridge_via", r"(?i)\bmakes\s+the\s+bridge\s+explicit\s+via\b", "planner-talk transition stem ('makes the bridge explicit via...')"),
        ("post_merge_planner_talk_turning", r"(?i)\bfollows\s+naturally\s+by\s+turning\b", "planner-talk transition stem ('follows naturally by turning...')"),
        ("post_merge_planner_talk_comparison_lens", r"(?i)\bcomparison\s+lens\b", "meta phrase 'comparison lens' (often reads like planning)"),
        ("post_merge_slide_navigation", r"(?i)\b(?:next,\s+we\s+move\s+from|we\s+now\s+(?:turn|move)\s+to|in\s+the\s+next\s+(?:section|subsection))\b", "slide/navigation narration"),
    ]

    # Slash-list axis markers (A / B / C) are high-signal generator voice in injected transitions.
    slash_list = r"\b[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\b"

    findings: list[dict[str, object]] = []

    for code, pat, label in patterns:
        if not draft or not re.search(pat, draft):
            continue
        source = "transitions" if transitions and re.search(pat, transitions) else "draft"
        findings.append(
            {
                "code": code,
                "label": label,
                "source": source,
                "examples": _examples(draft, pat),
            }
        )
        issues.append(QualityIssue(code=code, message=f"{label} (source: {source})"))

    if draft and re.search(slash_list, draft):
        source = "transitions" if transitions and re.search(slash_list, transitions) else "draft"
        findings.append(
            {
                "code": "post_merge_slash_list_axes",
                "label": "slash-list axis markers (A/B/C)",
                "source": source,
                "examples": _examples(draft, slash_list),
            }
        )
        issues.append(QualityIssue(code="post_merge_slash_list_axes", message=f"slash-list axis markers (source: {source})"))

    status = "PASS" if not issues else "FAIL"
    now = datetime.now().replace(microsecond=0).isoformat()

    lines: list[str] = [
        "# Post-merge voice report",
        "",
        f"- Timestamp: `{now}`",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}`",
        f"- Transitions: `{trans_rel}`",
        "",
    ]

    if status == "PASS":
        lines.extend(
            [
                "## Summary",
                "",
                "- No high-signal planner-talk / axis-label artifacts detected after merge.",
                "- Proceed to citation budget/injection and polishing.",
                "",
            ]
        )
        atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
        return 0

    lines.extend(
        [
            "## Findings (high-signal only)",
            "",
        ]
    )

    for f in findings:
        code = str(f.get("code") or "")
        label = str(f.get("label") or "")
        source = str(f.get("source") or "")
        lines.append(f"- `{code}`: {label} (source: `{source}`)")
        exs = f.get("examples") or []
        if isinstance(exs, list) and exs:
            for ex in exs[:3]:
                lines.append(f"  - e.g., {ex}")

    lines.extend(
        [
            "",
            "## Routing (fix the earliest responsible artifact)",
            "",
            "- If `source: transitions`: fix `outline/transitions.md` via `transition-weaver`, then rerun `section-merger` and this gate.",
            "- If `source: draft`: fix the owning unit via `writer-selfloop` (or `subsection-polisher` / `draft-polisher`), then rerun merge + this gate.",
            "",
            "## Notes",
            "",
            "- This gate is intentionally narrow: it blocks only high-signal generator-voice patterns that reliably spoil paper feel.",
            "- Fixes should be semantic rewrites (argument bridges), not template substitutions.",
            "",
        ]
    )

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")

    # Persist as a quality-gate record so the workspace is debuggable without reruns.
    write_quality_report(workspace=workspace, unit_id=unit_id, skill="post-merge-voice-gate", issues=issues)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
