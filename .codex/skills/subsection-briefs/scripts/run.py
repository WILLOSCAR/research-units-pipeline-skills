from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperRef:
    paper_id: str
    bibkey: str
    title: str
    year: int
    evidence_level: str


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

    from tooling.common import ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, read_jsonl, read_tsv, write_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/outline.yml",
        "outline/mapping.tsv",
        "papers/paper_notes.jsonl",
        "GOAL.md",
        "outline/claim_evidence_matrix.md",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/subsection_briefs.jsonl"]

    outline_path = workspace / inputs[0]
    mapping_path = workspace / inputs[1]
    notes_path = workspace / inputs[2]
    goal_path = workspace / (inputs[3] if len(inputs) >= 4 else "GOAL.md")
    out_path = workspace / outputs[0]

    if _looks_refined_jsonl(out_path):
        return 0

    outline = load_yaml(outline_path) if outline_path.exists() else None
    if not isinstance(outline, list) or not outline:
        raise SystemExit(f"Invalid outline: {outline_path}")

    mappings = read_tsv(mapping_path) if mapping_path.exists() else []
    if not mappings:
        raise SystemExit(f"Missing or empty mapping: {mapping_path}")

    notes = read_jsonl(notes_path)
    if not notes:
        raise SystemExit(f"Missing or empty paper notes: {notes_path}")

    notes_by_id: dict[str, dict[str, Any]] = {}
    for rec in notes:
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("paper_id") or "").strip()
        if pid:
            notes_by_id[pid] = rec

    mapped_by_sub: dict[str, list[str]] = {}
    for row in mappings:
        sid = str(row.get("section_id") or "").strip()
        pid = str(row.get("paper_id") or "").strip()
        if not sid or not pid:
            continue
        mapped_by_sub.setdefault(sid, []).append(pid)

    goal = _read_goal(goal_path)

    briefs: list[dict[str, Any]] = []
    for sec_id, sec_title, sub_id, sub_title, bullets in _iter_subsections(outline):
        rq = _extract_prefixed(bullets, "rq") or f"What are the main approaches and comparisons in {sub_title}?"

        evidence_needs = _extract_list_prefixed(bullets, "evidence needs")
        outline_axes = _extract_list_prefixed(bullets, "comparison axes")

        pids = [pid for pid in mapped_by_sub.get(sub_id, []) if pid in notes_by_id]
        pids = _dedupe_preserve_order(pids)

        paper_refs = [_paper_ref(pid, notes_by_id=notes_by_id) for pid in pids]
        evidence_summary = Counter([p.evidence_level or "unknown" for p in paper_refs])

        axes = _choose_axes(
            sub_title=sub_title,
            goal=goal,
            evidence_needs=evidence_needs,
            outline_axes=outline_axes,
        )

        clusters = _build_clusters(
            paper_refs=paper_refs,
            goal=goal,
            want=3,
        )

        paragraph_plan = _paragraph_plan(
            sub_title=sub_title,
            rq=rq,
            axes=axes,
            clusters=clusters,
            evidence_summary=dict(evidence_summary),
        )

        scope_rule = _scope_rule(goal=goal, sub_title=sub_title)

        briefs.append(
            {
                "sub_id": sub_id,
                "title": sub_title,
                "section_id": sec_id,
                "section_title": sec_title,
                "rq": rq,
                "scope_rule": scope_rule,
                "axes": axes,
                "clusters": clusters,
                "paragraph_plan": paragraph_plan,
                "evidence_level_summary": {
                    "fulltext": int(evidence_summary.get("fulltext", 0)),
                    "abstract": int(evidence_summary.get("abstract", 0)),
                    "title": int(evidence_summary.get("title", 0)),
                },
                "generated_at": now_iso_seconds(),
            }
        )

    ensure_dir(out_path.parent)
    write_jsonl(out_path, briefs)
    return 0


def _looks_refined_jsonl(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    if "…" in text:
        return False
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", text):
        return False
    if "(placeholder)" in low:
        return False
    if "generated_at" not in low:
        return False
    try:
        for line in text.splitlines()[:3]:
            if line.strip():
                json.loads(line)
    except Exception:
        return False
    return path.stat().st_size > 800


def _iter_subsections(outline: list[dict[str, Any]]):
    for section in outline:
        if not isinstance(section, dict):
            continue
        sec_id = str(section.get("id") or "").strip()
        sec_title = str(section.get("title") or "").strip()
        for sub in section.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sub_id = str(sub.get("id") or "").strip()
            sub_title = str(sub.get("title") or "").strip()
            bullets = [str(b).strip() for b in (sub.get("bullets") or []) if str(b).strip()]
            if sec_id and sec_title and sub_id and sub_title:
                yield sec_id, sec_title, sub_id, sub_title, bullets


def _extract_prefixed(bullets: list[str], key: str) -> str:
    key = (key or "").strip().lower()
    for b in bullets:
        m = re.match(r"^([A-Za-z ]+)\s*[:：]\s*(.+)$", b)
        if not m:
            continue
        head = (m.group(1) or "").strip().lower()
        if head == key:
            return (m.group(2) or "").strip()
    return ""


def _extract_list_prefixed(bullets: list[str], key: str) -> list[str]:
    raw = _extract_prefixed(bullets, key)
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"[;,；]", raw) if p.strip()]
    out: list[str] = []
    for p in parts:
        p = re.sub(r"\s+", " ", p)
        if p and p not in out:
            out.append(p)
    return out


def _read_goal(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", ">", "<!--")):
            continue
        low = line.lower()
        if "写一句话" in line or "fill" in low:
            continue
        return line
    return ""


def _paper_ref(pid: str, *, notes_by_id: dict[str, dict[str, Any]]) -> PaperRef:
    note = notes_by_id.get(pid) or {}
    bibkey = str(note.get("bibkey") or "").strip()
    title = str(note.get("title") or "").strip()
    year = int(note.get("year") or 0) if str(note.get("year") or "").isdigit() else 0
    evidence_level = str(note.get("evidence_level") or "").strip().lower() or "unknown"
    return PaperRef(paper_id=pid, bibkey=bibkey, title=title, year=year, evidence_level=evidence_level)


def _choose_axes(*, sub_title: str, goal: str, evidence_needs: list[str], outline_axes: list[str]) -> list[str]:
    axes: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if not x:
            return
        low = x.lower()
        if "refine" in low and "evidence" in low:
            return
        if x not in axes:
            axes.append(x)

    # Prefer evidence_needs / outline axes.
    for a in evidence_needs:
        add(a)
    for a in outline_axes:
        add(a)

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()

    if any(t in title_low for t in ["representation", "latent", "token", "pixel", "tokenizer", "codebook"]):
        add("representation (pixel/latent/token)")
    if any(t in title_low for t in ["sampling", "solver", "distillation", "speed", "efficiency", "steps"]):
        add("sampling/solver (steps, solver, distillation)")
    if any(t in title_low for t in ["guidance", "cfg", "classifier-free"]):
        add("guidance strategy (CFG, conditioning)")
    if any(t in title_low for t in ["control", "editing", "personalization", "inversion", "lora", "dreambooth"]):
        add("control/personalization interface")
    if any(t in title_low for t in ["evaluation", "benchmark", "metrics"]):
        add("evaluation protocol (benchmarks/metrics/human)")

    if "text-to-image" in goal_low or "t2i" in goal_low or "image generation" in goal_low:
        add("datasets/benchmarks (COCO, DrawBench, GenEval, etc.)")

    # Final fallback: stable 5-axis set.
    for a in [
        "mechanism/architecture",
        "data/training setup",
        "evaluation protocol",
        "compute/efficiency",
        "failure modes/limitations",
    ]:
        add(a)

    return axes[:5]


def _paper_tags(p: PaperRef) -> set[str]:
    text = f"{p.title}".lower()
    tags: set[str] = set()
    if "diffusion" in text:
        tags.add("diffusion")
    if "transformer" in text or "dit" in text:
        tags.add("transformer")
    if "control" in text or "controll" in text:
        tags.add("control")
    if "edit" in text or "inversion" in text or "personal" in text:
        tags.add("editing")
    if "benchmark" in text or "evaluation" in text or "metric" in text:
        tags.add("evaluation")
    if "video" in text or "temporal" in text:
        tags.add("video")
    if "distill" in text or "consistency" in text:
        tags.add("distillation")
    if "guidance" in text or "classifier-free" in text or "cfg" in text:
        tags.add("guidance")
    return tags


def _build_clusters(*, paper_refs: list[PaperRef], goal: str, want: int) -> list[dict[str, Any]]:
    goal_low = (goal or "").lower()
    forbid_video = ("text-to-image" in goal_low or "t2i" in goal_low) and ("video" not in goal_low and "t2v" not in goal_low)

    tag_to_papers: dict[str, list[PaperRef]] = {}
    for p in paper_refs:
        tags = _paper_tags(p)
        if forbid_video:
            tags.discard("video")
        for tag in tags:
            tag_to_papers.setdefault(tag, []).append(p)

    candidates = [(tag, ps) for tag, ps in tag_to_papers.items() if len(ps) >= 2]
    candidates.sort(key=lambda t: (-len(t[1]), t[0]))

    clusters: list[dict[str, Any]] = []
    used: set[str] = set()

    def add_cluster(label: str, rationale: str, ps: list[PaperRef]) -> None:
        pids = []
        bibs = []
        for p in sorted(ps, key=lambda x: (-x.year, x.paper_id)):
            if p.paper_id in used:
                continue
            used.add(p.paper_id)
            pids.append(p.paper_id)
            if p.bibkey:
                bibs.append(p.bibkey)
            if len(pids) >= 5:
                break
        if len(pids) < 2:
            return
        clusters.append({"label": label, "rationale": rationale, "paper_ids": pids, "bibkeys": bibs})

    for tag, ps in candidates[: max(1, want)]:
        label = {
            "diffusion": "Diffusion-family methods",
            "transformer": "Transformer-based generators",
            "control": "Control / conditioning interfaces",
            "editing": "Editing / personalization methods",
            "evaluation": "Evaluation / benchmark-focused works",
            "distillation": "Distillation / acceleration",
            "guidance": "Guidance strategies",
        }.get(tag, f"{tag} cluster")
        add_cluster(label, f"Grouped by keyword tag `{tag}` from titles (bootstrap).", ps)
        if len(clusters) >= want:
            break

    # Fallback: recency split.
    if len(clusters) < 2 and paper_refs:
        recent = [p for p in paper_refs if p.year and p.year >= max(0, max([pp.year for pp in paper_refs] or [0]) - 2)]
        classic = [p for p in paper_refs if p not in recent]
        add_cluster("Recent representative works", "Grouped by recency (bootstrap).", recent)
        add_cluster("Earlier / seminal works", "Grouped by older years (bootstrap).", classic)

    return clusters[:want]


def _paragraph_plan(*, sub_title: str, rq: str, axes: list[str], clusters: list[dict[str, Any]], evidence_summary: dict[str, int]) -> list[dict[str, Any]]:
    has_fulltext = int(evidence_summary.get("fulltext", 0) or 0) > 0
    mode = "grounded" if has_fulltext else "provisional"

    cluster_labels = [c.get("label") for c in clusters if c.get("label")]
    c1 = cluster_labels[0] if cluster_labels else "Cluster A"
    c2 = cluster_labels[1] if len(cluster_labels) > 1 else "Cluster B"

    axes_hint = ", ".join(axes[:4])

    plan = [
        {
            "para": 1,
            "intent": "Define scope, setup, and the subsection thesis (no pipeline jargon).",
            "focus": ["scope boundary", "key definitions"],
            "use_clusters": [c1],
        },
        {
            "para": 2,
            "intent": "Make the main comparison: contrast clusters along concrete axes.",
            "focus": [f"compare {c1} vs {c2}", f"axes: {axes_hint}"],
            "use_clusters": [c1, c2],
        },
        {
            "para": 3,
            "intent": "Discuss evaluation protocols + limitations; end with open questions if evidence is weak.",
            "focus": ["evaluation protocol", "failure modes", f"evidence mode: {mode}"],
            "use_clusters": [c2] if len(cluster_labels) > 1 else [c1],
        },
    ]

    if not has_fulltext:
        plan[2]["policy"] = "Use conservative language; avoid 'dominant trade-offs' claims; prefer questions-to-answer + evidence TODO fields."
    else:
        plan[2]["policy"] = "Claims must remain traceable to citations; summarize limitations without adding new facts."

    plan[0]["rq"] = rq

    return plan[:3]


def _scope_rule(*, goal: str, sub_title: str) -> dict[str, Any]:
    goal_low = (goal or "").lower()
    is_t2i = ("text-to-image" in goal_low or "t2i" in goal_low or "image generation" in goal_low) and ("video" not in goal_low and "t2v" not in goal_low)

    include = [f"Core topics directly relevant to '{sub_title}'."]
    exclude: list[str] = []

    if is_t2i:
        exclude.extend(
            [
                "Text-to-video / audio-video generation unless explicitly used as a bridging reference.",
                "Modalities outside text-to-image (unless the subsection is explicitly about evaluation/architecture shared across modalities).",
            ]
        )

    notes = "If you include an out-of-scope paper as a bridge, state the reason in 1 sentence and keep it secondary."
    return {"include": include, "exclude": exclude, "notes": notes}


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
