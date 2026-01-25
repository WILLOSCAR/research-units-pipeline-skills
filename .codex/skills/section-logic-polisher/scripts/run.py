from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Counts:
    causal: int
    contrast: int
    extension: int
    implication: int


def _draft_profile(workspace: Path) -> str:
    path = workspace / "queries.md"
    if not path.exists():
        return "survey"
    keys = {"draft_profile", "writing_profile", "quality_profile"}
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key not in keys:
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"survey", "deep"}:
                return value
            return "survey"
    except Exception:
        return "survey"
    return "survey"


def _h3_files(workspace: Path) -> list[Path]:
    sec_dir = workspace / "sections"
    if not sec_dir.exists():
        return []
    out: list[Path] = []
    for p in sorted(sec_dir.glob("S*.md")):
        name = p.name
        if name in {"abstract.md", "discussion.md", "conclusion.md"}:
            continue
        if name.endswith("_lead.md"):
            continue
        # H3 IDs are rendered as S<sec>_<sub>.md (underscore).
        if "_" not in name:
            continue
        out.append(p)
    return out


def _first_paragraph(text: str) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    return paras[0] if paras else ""


def _has_thesis(paragraph: str) -> bool:
    if not paragraph:
        return False
    p = re.sub(r"\[@[^\]]+\]", "", paragraph)
    p = re.sub(r"\s+", " ", p).strip()
    if not p:
        return False

    thesis_patterns = [
        # Conclusion-first / takeaway markers (avoid repetitive "This subsection ..." meta-prose).
        r"(?i)\b(key\s+takeaway|main\s+takeaway|takeaway)\b\s*[:\-]",
        r"(?i)\b(a|an|one)\s+(?:central|core|key)\s+(?:tension|challenge|trade[-\s]?off|bottleneck|constraint)\s+is\b",
        r"(?i)\bthe\s+(?:central|core|key)\s+(?:claim|point|tension|idea)\s+is\b",
        r"(?i)\bthe\s+key\s+point\s+is\b",
        r"(?i)\bour\s+(?:synthesis|review|survey)\s+(?:suggests|shows|finds|indicates)\s+that\b",
        r"(?i)\bwe\s+(?:argue|show|find|suggest|observe|contend)\s+that\b",
        r"(?i)\bthis\s+(?:section|subsection)\s+(?:shows|argues|concludes|highlights)\s+that\b",
        # Content-claim verbs (more natural than explicit "takeaway:" labels).
        r"(?i)\bdetermin(?:e|es|ed|ing)\b|\bdriv(?:e|es|en|ing)\b|\bshap(?:e|es|ed|ing)\b|\bconstrain(?:s|ed|ing)?\b|\bgovern(?:s|ed|ing)?\b|\bset(?:s)?\s+the\s+ceiling\b",
        # Chinese thesis/takeaway cues.
        r"(?:本小节|本节)(?:结论|核心观点|要点|认为|指出|主张|表明|决定|驱动|影响|约束|塑造|主导)",
        r"(?:一个|一项|一個)(?:关键|核心)(?:挑战|矛盾|张力|權衡|权衡|瓶颈|约束|約束)是",
    ]
    return any(re.search(pat, p) for pat in thesis_patterns)


def _has_template_subsection_opener(paragraph: str) -> bool:
    """Detect generator-like openers that hurt "paper feel"."""

    p = re.sub(r"\[@[^\]]+\]", "", paragraph or "")
    p = re.sub(r"\s+", " ", p).strip()
    if not p:
        return False
    return bool(re.search(r"(?i)\bthis\s+subsection\s+(?:argues|shows|surveys|suggests|demonstrates|contends)\b", p))


def _connector_counts(text: str) -> Counts:
    blob = re.sub(r"\[@[^\]]+\]", "", text or "")
    blob = blob.lower()

    causal = r"\b(therefore|thus|hence|as a result|consequently|accordingly|because|since|this leads to|which means|which makes)\b|因此|所以|从而|因而|由此"
    contrast = r"\b(however|nevertheless|nonetheless|yet|whereas|unlike|in contrast|by contrast|although|while|but)\b|然而|相比之下|相较|不同于"
    extension = r"\b(moreover|furthermore|additionally|in addition|similarly|likewise|building on|following|also|another|a second|at the same time|in turn)\b|此外|并且|同时|进一步|另外"
    implication = r"\b(this raises|this suggests|this implies|this motivates|this highlights|this means|this indicates|this points to|a practical implication is|one implication is)\b|这(?:提示|表明|意味着|引出)"

    return Counts(
        causal=len(re.findall(causal, blob)),
        contrast=len(re.findall(contrast, blob)),
        extension=len(re.findall(extension, blob)),
        implication=len(re.findall(implication, blob)),
    )


def _thresholds(profile: str) -> Counts:
    profile = (profile or "").strip().lower()
    if profile == "deep":
        return Counts(causal=3, contrast=2, extension=2, implication=1)
    return Counts(causal=2, contrast=2, extension=2, implication=1)


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

    from tooling.common import ensure_dir, now_iso_seconds, parse_semicolon_list

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["output/SECTION_LOGIC_REPORT.md"]
    out_rel = outputs[0] if outputs else "output/SECTION_LOGIC_REPORT.md"
    out_path = workspace / out_rel
    ensure_dir(out_path.parent)

    prof = _draft_profile(workspace)
    thresh = _thresholds(prof)

    # rows: (rel, thesis_ok, connectors_ok, template_ok, counts)
    rows: list[tuple[str, bool, bool, bool, Counts]] = []
    for p in _h3_files(workspace):
        text = p.read_text(encoding="utf-8", errors="ignore")
        first_p = _first_paragraph(text)
        thesis_ok = _has_thesis(first_p)
        template_ok = not _has_template_subsection_opener(first_p)
        counts = _connector_counts(text)
        connectors_ok = (
            counts.causal >= thresh.causal
            and counts.contrast >= thresh.contrast
            and counts.extension >= thresh.extension
            and counts.implication >= thresh.implication
        )
        rows.append((p.relative_to(workspace).as_posix(), thesis_ok, connectors_ok, template_ok, counts))

    fail = [r for r in rows if not r[1]]
    status = "PASS" if (rows and not fail) else "FAIL"

    lines: list[str] = [
        "# Section Logic Report",
        "",
        f"- Generated at: {now_iso_seconds()}",
        f"- Draft profile: `{prof}`",
        f"- Status: {status}",
        "",
        "## Thresholds",
        "",
        "| Type | Min |",
        "|---|---:|",
        f"| causal | {thresh.causal} |",
        f"| contrast | {thresh.contrast} |",
        f"| extension | {thresh.extension} |",
        f"| implication | {thresh.implication} |",
        "",
        "## Per-section (H3)",
        "",
        "| File | Thesis | Connectors | Template opener | causal | contrast | extension | implication | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for rel, thesis_ok, connectors_ok, template_ok, c in rows:
        ok = thesis_ok
        lines.append(
            f"| `{rel}` | {'Y' if thesis_ok else 'N'} | {'Y' if connectors_ok else 'N'} | {'Y' if template_ok else 'N'} | {c.causal} | {c.contrast} | {c.extension} | {c.implication} | {'PASS' if ok else 'FAIL'} |"
        )

    if not rows:
        lines.extend(["", "- No H3 section files found under `sections/` (expected `S<sec>_<sub>.md`)."])

    template_bad = [r[0] for r in rows if not r[3]]
    if template_bad:
        lines.extend(
            [
                "",
                "## Paper voice warnings (non-blocking)",
                "",
                "- Some H3 files start with generator-like meta openers (e.g., `This subsection ...`). Rewrite the first sentence into a content claim (no narration).",
                *[f"- `{rel}`" for rel in template_bad],
            ]
        )

    if fail:
        lines.extend(
            [
                "",
                "## How to fix (blocking)",
                "",
                "- Make paragraph 1 conclusion-first with a clear thesis sentence (keep signposting light; avoid repeated opener labels).",
                "- Express logical relations, but prefer subject-first sentences and mid-sentence glue (because/while/which) instead of repeating paragraph-starter adverbs (Overall/In addition).",
                "- Do not add new citation keys; keep scope within the subsection.",
            ]
        )

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
