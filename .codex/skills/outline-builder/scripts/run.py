from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


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

    from tooling.common import dump_yaml, load_yaml, parse_semicolon_list

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["outline/taxonomy.yml"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/outline.yml"]

    taxonomy_path = workspace / inputs[0]
    out_path = workspace / outputs[0]

    taxonomy = load_yaml(taxonomy_path) if taxonomy_path.exists() else None
    if not isinstance(taxonomy, list) or not taxonomy:
        raise SystemExit(f"Invalid taxonomy in {taxonomy_path}")

    # Never overwrite non-placeholder user work.
    if out_path.exists() and out_path.stat().st_size > 0:
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if not _is_placeholder(existing):
            return 0

    outline: list[dict[str, Any]] = [
        {
            "id": "1",
            "title": "Introduction",
            "bullets": [
                "Intent: motivate the topic, set scope boundaries, and explain why the survey is needed now.",
                "RQ: What is the survey scope and what reader questions will the taxonomy answer?",
                "Evidence needs: define key terms; position vs prior surveys; summarize what evidence is collected (datasets/metrics/benchmarks).",
                "Expected cites: >=10 across intro + background (surveys, seminal works, widely-used benchmarks).",
                "Structure: preview the taxonomy and how later sections map to evidence and comparisons.",
            ],
        },
        {
            "id": "2",
            "title": "Related Work & Prior Surveys",
            "bullets": [
                "Intent: position this survey relative to prior surveys/reviews and adjacent lines of work (agents, tool use, RAG, evaluation, security).",
                "RQ: What does this survey add beyond prior surveys (taxonomy choices, evidence-first criteria, evaluation focus)?",
                "Evidence needs: cite 3–6 prior surveys/reviews and 3–6 foundational works; clarify scope boundaries and terminology.",
                "Expected cites: >=10 (prior surveys + seminal works + widely-used benchmarks).",
                "Structure: explain how the taxonomy differs from prior organization schemes and why it supports deeper comparisons.",
            ],
        },
    ]

    section_no = 3
    for topic in taxonomy:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("name") or "").strip() or f"Topic {section_no}"
        topic_desc = str(topic.get("description") or "").strip()
        children = topic.get("children") or []
        section_id = str(section_no)

        section: dict[str, Any] = {
            "id": section_id,
            "title": name,
            "bullets": _section_meta_bullets(title=name, hint=topic_desc),
            "subsections": [],
        }

        subsection_no = 1
        for child in children if isinstance(children, list) else []:
            if not isinstance(child, dict):
                continue
            child_name = str(child.get("name") or "").strip() or f"Subtopic {section_id}.{subsection_no}"
            child_desc = str(child.get("description") or "").strip()
            subsection_id = f"{section_id}.{subsection_no}"
            section["subsections"].append(
                {
                    "id": subsection_id,
                    "title": child_name,
                    "bullets": _subsection_bullets(parent=name, title=child_name, hint=child_desc),
                }
            )
            subsection_no += 1

        outline.append(section)
        section_no += 1

    dump_yaml(out_path, outline)
    return 0


def _hint_sentence(text: str, *, max_len: int = 220) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\s+", " ", raw).strip()

    # Try to extract a short first sentence.
    best = raw
    for sep in [".", "。", ";"]:
        idx = raw.find(sep)
        if idx > 40:  # avoid tiny fragments
            best = raw[: idx + 1].strip()
            break

    if len(best) > int(max_len):
        best = best[: int(max_len)].rstrip()
    return best


def _section_meta_bullets(*, title: str, hint: str = "") -> list[str]:
    title = (title or "").strip() or "this chapter"
    hint_short = _hint_sentence(hint)

    bullets = [
        f"Intent: define the design space for {title} and provide cross-subsection comparisons.",
        f"RQ: What is the organizing logic of {title}, and which comparisons are most decision-relevant?",
    ]
    if hint_short:
        bullets.append(f"Scope cues: {hint_short}")
    bullets.extend(
        [
            "Evidence needs: representative methods; evaluation protocols; known failure modes; connections to adjacent chapters.",
            "Expected cites: each subsection >=3; chapter total should be high enough to support evidence-first synthesis.",
        ]
    )
    return bullets


def _subsection_bullets(*, parent: str, title: str, hint: str = "") -> list[str]:
    title = (title or "").strip() or "this subtopic"
    parent = (parent or "").strip() or "this chapter"
    hint_short = _hint_sentence(hint)

    # Stage A contract: each H3 must be verifiable with intent/RQ/evidence needs/expected cite density.
    # Keep bullets checkable; do not leave instruction-like scaffold text (e.g., "enumerate 2-4 ...").
    bullets = [
        f"Intent: explain what belongs in {title} (within {parent}) and how it differs from neighboring subtopics.",
        f"RQ: Which design choices in {title} drive the major trade-offs, and how are those trade-offs measured?",
    ]
    if hint_short:
        bullets.append(f"Scope cues: {hint_short}")
    bullets.extend(
        [
            "Evidence needs: mechanism/architecture; data/training setup; evaluation protocol (datasets/metrics/human); efficiency/compute; failure modes/limitations.",
            "Expected cites: >=3 (H3); include >=1 canonical/seminal work and >=1 recent representative work when possible.",
            "Comparison axes: mechanism; data; evaluation; efficiency; limitations (refine with evidence in later stages).",
        ]
    )
    return bullets


def _is_placeholder(text: str) -> bool:
    text = (text or "").strip().lower()
    if not text:
        return True
    if "(placeholder)" in text:
        return True
    if "<!-- scaffold" in text:
        return True
    if re.search(r"(?:todo|tbd|fixme)", text, flags=re.IGNORECASE):
        return True
    if re.search(r"(?m)^\s*#\s*outline\s*\(placeholder\)", text):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
