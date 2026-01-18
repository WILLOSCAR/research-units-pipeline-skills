from __future__ import annotations

import argparse
import hashlib
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

    # Explicit freeze policy: only skip regeneration if the user creates `outline/subsection_briefs.refined.ok`.
    freeze_marker = out_path.parent / "subsection_briefs.refined.ok"
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

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
        rq = _extract_prefixed(bullets, "rq") or f"Which design choices in {sub_title} drive the major trade-offs, and how are those trade-offs measured?"
        rq_norm = str(rq or "").strip()
        if re.match(r"(?i)^what\s+are\s+the\s+main\s+approaches", rq_norm):
            rq = f"Which design choices in {sub_title} drive the major trade-offs, and how are those trade-offs measured?"

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

        thesis = _thesis_statement(
            sub_title=sub_title,
            axes=axes,
            evidence_summary=dict(evidence_summary),
        )

        paragraph_plan = _paragraph_plan(
            sub_id=sub_id,
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
                "thesis": thesis,
                "scope_rule": scope_rule,
                "axes": axes,
                "bridge_terms": _bridge_terms(sub_title=sub_title, axes=axes, goal=goal),
                "contrast_hook": _contrast_hook(sub_title=sub_title, axes=axes, goal=goal),
                "required_evidence_fields": _required_evidence_fields(sub_title=sub_title, axes=axes, goal=goal),
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



def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

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

def _pick(seed: str, options: list[str]) -> str:
    """Deterministic picker to avoid repeating the same connector phrasing everywhere."""
    if not options:
        return ""
    h = int(hashlib.md5(seed.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)
    return options[h % len(options)]


def _thesis_statement(*, sub_title: str, axes: list[str], evidence_summary: dict[str, int]) -> str:
    """Return a 1-sentence, execution-oriented thesis (NO NEW FACTS)."""
    title = re.sub(r"\s+", " ", (sub_title or "").strip())
    a1 = axes[0] if axes else "mechanism and evaluation"
    a2 = axes[1] if len(axes) > 1 else ""
    axes_phrase = a1 if not a2 else f"{a1} and {a2}"

    has_fulltext = int(evidence_summary.get("fulltext", 0) or 0) > 0
    seed = f"thesis:{title}:{axes_phrase}:{'fulltext' if has_fulltext else 'abstract'}"

    # The thesis is an internal execution hint for C5 writers; avoid "This subsection ..." meta-prose
    # because it creates repetitive, generator-like openers in the final draft.
    if has_fulltext:
        options = [
            f"Design choices in {title} create decision-relevant trade-offs—especially in {axes_phrase}—and meaningful comparisons depend on consistent evaluation protocols.",
            f"The core tension in {title} lies in {axes_phrase}, and the literature is most informative when methods are compared under shared evaluation settings.",
            f"Work on {title} suggests that {axes_phrase} drives many downstream trade-offs, making protocol-aligned evaluation a first-class design constraint.",
            f"In {title}, decisions about {axes_phrase} often dominate practical outcomes, so synthesis should stay grounded in protocol-consistent comparisons.",
        ]
        return _pick(seed, options)

    options = [
        f"{title} methods emphasize {axes_phrase} trade-offs, but synthesis is clearest when claims are tied to explicit evaluation settings and reporting conventions.",
        f"For {title}, {axes_phrase} is a recurring axis of variation, so comparisons should foreground evaluation protocol choices and failure-mode assumptions.",
        f"{title} highlights a tension around {axes_phrase}, motivating a protocol-aware synthesis rather than per-paper summaries.",
        f"In {title}, differences in {axes_phrase} frequently imply different evaluation setups, so the key is to compare under consistent protocols where possible.",
    ]
    return _pick(seed, options)


def _choose_axes(*, sub_title: str, goal: str, evidence_needs: list[str], outline_axes: list[str]) -> list[str]:
    axes: list[str] = []

    def norm(x: str) -> str:
        x = re.sub(r"\s+", " ", (x or "").strip().lower())
        x = x.rstrip(" .;:，；。")
        x = re.sub(r"\s*/\s*", " / ", x)
        return x

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        x = x.rstrip(" .;:，；。")
        x = re.sub(r"\s*/\s*", " / ", x)
        if not x:
            return
        low = x.lower()
        if "refine" in low and "evidence" in low:
            return
        # Drop ultra-generic axis tokens that are almost always scaffold leakage.
        if norm(x) in {"mechanism", "data", "evaluation", "efficiency", "limitation", "limitations"}:
            return
        if x not in axes:
            axes.append(x)

    # Prefer evidence_needs / outline axes as seeds, but treat generic "scaffold" axes as low priority.
    for a in evidence_needs:
        add(a)
    for a in outline_axes:
        add(a)

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()

    # Domain-specific axes for LLM-agent surveys (cheap heuristics; should become evidence-driven with richer notes).
    is_agent_domain = any(k in goal_low for k in ["agent", "agents", "llm agent", "tool use", "tool-use", "memory", "planning"]) or any(
        k in title_low for k in ["agent", "tool", "memory", "rag", "planning", "reasoning", "multi-agent", "evaluation", "safety", "security"]
    )

    if is_agent_domain:
        if any(t in title_low for t in ["plan", "planning", "reason", "reasoning", "deliberation", "search", "tree", "thought"]):
            add("control loop design (planner / executor, search)")
            add("deliberation method (CoT / ToT / MCTS)")
            add("action grounding (tool calls vs environment actions)")
        if any(t in title_low for t in ["tool", "orchestration", "mcp", "api", "function", "protocol"]):
            add("tool interface (function calling, schemas, protocols)")
            add("tool selection / routing policy")
            add("sandboxing / permissions / observability")
        if any(t in title_low for t in ["memory", "retrieval", "rag", "cache", "long-horizon"]):
            add("memory type (episodic / semantic / scratchpad)")
            add("retrieval source + index (docs / web / logs)")
            add("write / update / forgetting policy")
        if any(t in title_low for t in ["multi-agent", "coordination", "debate", "collaboration", "swarm"]):
            add("communication protocol + role assignment")
            add("aggregation (vote / debate / referee)")
            add("stability (collusion, mode collapse, incentives)")
        if any(t in title_low for t in ["train", "alignment", "preference", "rl", "reinforcement", "self-improvement", "reflection"]):
            add("training signal (SFT / preference / RL)")
            add("data synthesis + evaluator / reward")
            add("generalization + regression control")
        if any(t in title_low for t in ["evaluation", "benchmark", "suite", "deploy", "deployment"]):
            add("task suites (web / code / embodied / tools)")
            add("metrics (success, cost, reliability, safety)")
            add("contamination + reproducibility controls")
        if any(t in title_low for t in ["safety", "security", "attack", "guardrail", "defense", "vulnerab"]):
            add("threat model (prompt/tool injection, exfiltration)")
            add("defense surface (policy, sandbox, monitoring)")
            add("security evaluation protocol")

    # Existing T2I-specific heuristics (kept for backward compatibility).
    if any(t in title_low for t in ["representation", "latent", "token", "pixel", "tokenizer", "codebook"]):
        add("representation (pixel / latent / token)")
    if any(t in title_low for t in ["sampling", "solver", "distillation", "speed", "efficiency", "steps"]):
        add("sampling / solver (steps, solver, distillation)")
    if any(t in title_low for t in ["guidance", "cfg", "classifier-free"]):
        add("guidance strategy (CFG, conditioning)")
    if any(t in title_low for t in ["control", "editing", "personalization", "inversion", "lora", "dreambooth"]):
        add("control / personalization interface")
    if any(t in title_low for t in ["evaluation", "benchmark", "metrics"]):
        add("evaluation protocol (benchmarks / metrics / human)")

    if "text-to-image" in goal_low or "t2i" in goal_low or "image generation" in goal_low:
        add("datasets / benchmarks (COCO, DrawBench, GenEval, etc.)")

    # Final fallback: stable generic set.
    for a in [
        "mechanism / architecture",
        "data / training setup",
        "evaluation protocol",
        "compute / efficiency",
        "failure modes / limitations",
    ]:
        add(a)

    generic = {
        "mechanism / architecture",
        "data / training setup",
        "evaluation protocol",
        "evaluation protocol (benchmarks / metrics / human)",
        "evaluation protocol (datasets / metrics / human)",
        "compute / efficiency",
        "efficiency / compute",
        "failure modes / limitations",
        "failure modes/limitations",
        "failure modes / limitations.",
    }

    # Reorder: keep non-generic axes first so heuristics aren't crowded out by scaffold-y outline axes.
    ordered: list[str] = []
    for a in axes:
        if norm(a) not in generic and a not in ordered:
            ordered.append(a)
    for a in axes:
        if norm(a) in generic and a not in ordered:
            ordered.append(a)

    specific = [a for a in ordered if norm(a) not in generic]
    generic_axes = [a for a in ordered if norm(a) in generic]

    # Avoid repeating the same generic axis list in every subsection, but keep enough axes
    # so later evidence packs can generate multiple concrete comparison cards.
    out: list[str] = list(specific)
    target = 5
    if len(out) < target:
        for a in generic_axes:
            if a not in out:
                out.append(a)
            if len(out) >= target:
                break

    return out[:target]




def _bridge_terms(*, sub_title: str, axes: list[str], goal: str) -> list[str]:
    """Return 3–6 bridge terms for transition-weaver (NO NEW FACTS)."""

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()

    terms: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if not x:
            return
        if x.lower() in {"mechanism", "data", "evaluation", "efficiency", "limitations"}:
            return
        if x not in terms:
            terms.append(x)

    # Agent-domain heuristics (cheap but useful for coherence).
    if any(k in goal_low for k in ["agent", "agents", "tool use", "tool-use", "memory", "planning"]) or any(
        k in title_low for k in ["agent", "tool", "memory", "rag", "planning", "reasoning", "multi-agent", "evaluation", "safety", "security"]
    ):
        if any(t in title_low for t in ["plan", "planning", "reason", "reasoning", "deliberation", "search", "tree", "thought"]):
            for t in ["planner/executor", "search", "deliberation", "action grounding"]:
                add(t)
        if any(t in title_low for t in ["tool", "orchestration", "mcp", "api", "function", "protocol"]):
            for t in ["function calling", "tool schema", "routing", "sandbox", "observability"]:
                add(t)
        if any(t in title_low for t in ["memory", "retrieval", "rag", "cache", "long-horizon"]):
            for t in ["retrieval", "index", "write policy", "long-term memory"]:
                add(t)
        if any(t in title_low for t in ["multi-agent", "coordination", "debate", "collaboration", "swarm"]):
            for t in ["roles", "communication", "debate", "aggregation", "stability"]:
                add(t)
        if any(t in title_low for t in ["train", "alignment", "preference", "rl", "reinforcement", "self-improvement", "reflection"]):
            for t in ["preference", "reward", "feedback", "self-improvement"]:
                add(t)
        if any(t in title_low for t in ["evaluation", "benchmark", "suite", "deploy", "deployment"]):
            for t in ["benchmarks", "metrics", "reproducibility", "contamination"]:
                add(t)
        if any(t in title_low for t in ["safety", "security", "attack", "guardrail", "defense", "vulnerab"]):
            for t in ["threat model", "prompt/tool injection", "monitoring", "guardrails"]:
                add(t)

    # Add lightweight terms from axes.
    for a in axes[:5]:
        low = str(a or "").lower()
        if "benchmark" in low or "metric" in low or "dataset" in low:
            add("benchmarks/metrics")
        if "compute" in low or "efficien" in low or "cost" in low:
            add("compute")
        if "threat" in low or "security" in low or "attack" in low:
            add("threat model")

    return terms[:6]


def _contrast_hook(*, sub_title: str, axes: list[str], goal: str) -> str:
    """Return a short hook label for transitions (NO NEW FACTS)."""

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()
    axes_low = " ".join([str(a or "").lower() for a in axes])

    if any(k in goal_low for k in ["agent", "agents"]) or "agent" in title_low:
        if any(t in title_low for t in ["plan", "planning", "reason", "reasoning", "deliberation", "search", "thought"]):
            return "planning/control loop"
        if any(t in title_low for t in ["tool", "orchestration", "mcp", "api", "function", "protocol"]):
            return "tool interfaces"
        if any(t in title_low for t in ["memory", "retrieval", "rag", "cache"]):
            return "memory/retrieval"
        if any(t in title_low for t in ["multi-agent", "coordination", "debate", "collaboration", "swarm"]):
            return "coordination"
        if any(t in title_low for t in ["train", "alignment", "preference", "rl", "self-improvement", "reflection"]):
            return "learning/feedback"
        if any(t in title_low for t in ["evaluation", "benchmark", "suite", "deploy", "deployment"]):
            return "evaluation"
        if any(t in title_low for t in ["safety", "security", "attack", "guardrail", "defense", "vulnerab"]):
            return "security"

    if any(t in axes_low for t in ["benchmark", "metric", "dataset", "evaluation"]):
        return "evaluation"
    if any(t in axes_low for t in ["compute", "efficien", "cost"]):
        return "compute"
    if any(t in axes_low for t in ["failure", "limit"]):
        return "limitations"

    # Fallback: first axis phrase.
    return (axes[0] if axes else "").strip()[:48]


def _required_evidence_fields(*, sub_title: str, axes: list[str], goal: str) -> list[str]:
    """Return a short checklist of evidence fields this subsection should eventually support."""

    joined = " ".join([str(a or "").lower() for a in axes] + [(sub_title or "").lower(), (goal or "").lower()])

    out: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if x and x not in out:
            out.append(x)

    # Defaults for survey-quality comparisons.
    add("benchmarks/datasets")
    add("metrics / human-eval protocol")

    if any(t in joined for t in ["compute", "efficien", "cost", "latency", "speed"]):
        add("compute / cost (train/infer)")
    if any(t in joined for t in ["data", "training", "supervision", "sft", "rl", "preference"]):
        add("training signal / supervision")
    if any(t in joined for t in ["failure", "limit", "robust", "error"]):
        add("failure modes / limitations")
    if any(t in joined for t in ["security", "attack", "threat", "guardrail", "sandbox", "injection"]):
        add("threat model")
        add("defense surface")

    return out[:8]


def _paper_tags(p: PaperRef) -> set[str]:
    """Lightweight keyword tags for clustering (bootstrap only).

    These tags are intentionally heuristic and title-only so the pipeline remains
    deterministic without needing an LLM in the planner pass.
    """

    text = f"{p.title}".lower()
    tags: set[str] = set()

    # Vision / generative (legacy tags kept for other topics).
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

    # Agentic / LLM systems (bootstrap from titles).
    if re.search(r"\bagent(?:s|ic)?\b", text) or any(k in text for k in ["autogpt", "react", "toolformer", "mrkl"]):
        tags.add("agents")
    if any(
        k in text
        for k in [
            "tool",
            "function call",
            "function-call",
            "function calling",
            "api",
            "schema",
            "protocol",
            "mcp",
            "orchestrat",
            "router",
        ]
    ):
        tags.add("tool-use")
    if any(k in text for k in ["plan", "planner", "planning", "reason", "tree of thought", "tot", "mcts", "search"]):
        tags.add("planning")
    if any(k in text for k in ["memory", "retriev", "rag", "vector", "embedding", "index", "cache"]):
        tags.add("memory")
    if any(k in text for k in ["multi-agent", "multiagent", "society", "debate", "swarm", "coordination", "collaborat"]):
        tags.add("multi-agent")
    if any(k in text for k in ["safety", "secure", "security", "guard", "jailbreak", "injection", "threat", "sandbox", "permission"]):
        tags.add("security")
    if any(k in text for k in ["code", "coding", "program", "software", "debug", "bug", "repo", "github"]):
        tags.add("code")
    if any(k in text for k in ["web", "browser", "search", "crawl", "scrape"]):
        tags.add("web")
    if any(k in text for k in ["workflow", "orchestration", "pipeline"]):
        tags.add("orchestration")
    if any(k in text for k in ["reflection", "self-refine", "self improve", "self-improve"]):
        tags.add("reflection")

    return tags


def _build_clusters(*, paper_refs: list[PaperRef], goal: str, want: int) -> list[dict[str, Any]]:
    """Return 2–3 paper clusters for comparison.

    Quality-gate requirement: at least **two** clusters, each with >=2 papers.
    When a subsection has only ~3 mapped papers, we allow overlap across clusters
    (e.g., [A,B] vs [B,C]) to keep the drafting plan executable.
    """

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

    def add_cluster(label: str, rationale: str, ps: list[PaperRef]) -> None:
        pids: list[str] = []
        bibs: list[str] = []
        for p in sorted(ps, key=lambda x: (-x.year, x.paper_id)):
            pids.append(p.paper_id)
            if p.bibkey:
                bibs.append(p.bibkey)
            if len(pids) >= 8:
                break
        # Dedupe while preserving order.
        seen: set[str] = set()
        pids = [pid for pid in pids if not (pid in seen or seen.add(pid))]
        bibs = [b for b in bibs if b]
        if len(pids) < 2:
            return
        clusters.append({"label": label, "rationale": rationale, "paper_ids": pids, "bibkeys": bibs})

    # Tag-based clusters (bootstrap).
    for tag, ps in candidates[: max(1, want)]:
        label = {
            "diffusion": "Diffusion-family methods",
            "transformer": "Transformer-based generators",
            "control": "Control / conditioning interfaces",
            "editing": "Editing / personalization methods",
            "evaluation": "Evaluation / benchmark-focused works",
            "distillation": "Distillation / acceleration",
            "guidance": "Guidance strategies",
            "agents": "Agent frameworks / architectures",
            "tool-use": "Tool-use and function calling",
            "planning": "Planning / reasoning loops",
            "memory": "Memory / retrieval augmentation",
            "multi-agent": "Multi-agent coordination",
            "security": "Safety / security / guardrails",
            "code": "Code agents / software tasks",
            "web": "Web navigation / search",
            "orchestration": "Orchestration / workflows",
            "reflection": "Self-improvement / reflection",
            "video": "Video / temporal generation",
        }.get(tag, f"{tag} cluster")
        add_cluster(label, f"Grouped by keyword tag `{tag}` from titles (bootstrap).", ps)
        if len(clusters) >= want:
            break

    # Fallback 1: recency split.
    if len(clusters) < 2 and paper_refs:
        years = [p.year for p in paper_refs if p.year]
        cutoff = (max(years) - 2) if years else 0
        recent = [p for p in paper_refs if p.year and p.year >= cutoff]
        classic = [p for p in paper_refs if p not in recent]
        add_cluster("Recent representative works", "Grouped by recency (bootstrap).", recent)
        add_cluster("Earlier / related works", "Grouped by older years (bootstrap).", classic)

    # Fallback 2: ensure at least two clusters via overlapping split.
    if len(clusters) < 2:
        ranked = sorted(paper_refs, key=lambda x: (-x.year, x.paper_id))
        if len(ranked) >= 3:
            add_cluster(
                "Mapped subset A",
                "Overlap-allowed split to ensure two comparable clusters when the mapped set is small.",
                ranked[:2],
            )
            add_cluster(
                "Mapped subset B",
                "Overlap-allowed split to ensure two comparable clusters when the mapped set is small.",
                ranked[1:3],
            )
        elif len(ranked) >= 2:
            add_cluster(
                "Mapped subset",
                "Small mapped set; use the same pair for both paragraphs, focusing on axis-by-axis contrasts.",
                ranked[:2],
            )
            add_cluster(
                "Mapped subset (alt)",
                "Small mapped set; duplicate cluster (writer should compare within the pair along different axes).",
                ranked[:2],
            )



    # Coverage bucket: if mappings are dense, keep a third cluster to increase citation diversity.
    used: set[str] = set()
    for c in clusters:
        if isinstance(c, dict):
            for pid in c.get("paper_ids") or []:
                used.add(str(pid).strip())

    remaining = [p for p in paper_refs if p.paper_id and p.paper_id not in used]
    if len(clusters) < 3 and len(remaining) >= 2:
        add_cluster(
            "Additional mapped works",
            "Coverage bucket to increase citation diversity (use cautiously; avoid over-claiming beyond available evidence).",
            remaining,
        )
    # Keep at most 3 clusters to avoid over-structuring.
    return clusters[: max(2, min(3, int(want) if int(want) > 0 else 3))]




def _paragraph_plan(
    *,
    sub_id: str,
    sub_title: str,
    rq: str,
    axes: list[str],
    clusters: list[dict[str, Any]],
    evidence_summary: dict[str, int],
) -> list[dict[str, Any]]:
    """Return a paragraph-by-paragraph writing plan (NO PROSE).

    Survey default: prefer fewer, thicker paragraphs with explicit contrasts and an evaluation anchor.
    """

    has_fulltext = int(evidence_summary.get("fulltext", 0) or 0) > 0
    mode = "grounded" if has_fulltext else "provisional"

    cluster_labels = [c.get("label") for c in clusters if c.get("label")]
    c1 = cluster_labels[0] if cluster_labels else "Cluster A"
    c2 = cluster_labels[1] if len(cluster_labels) > 1 else "Cluster B"
    c3 = cluster_labels[2] if len(cluster_labels) > 2 else ""

    axes_hint = ", ".join(axes[:5])

    contrast_prefix = _pick(
        f"{sub_id}:contrast",
        ["In contrast,", "However,", "By contrast,", "Unlike this route,"],
    )
    extend_prefix = _pick(
        f"{sub_id}:extend",
        ["Building on this,", "More concretely,", "At the implementation level,", "Following this design,"],
    )
    eval_prefix = _pick(
        f"{sub_id}:eval",
        ["To evaluate these trade-offs,", "Empirically,", "In evaluations,", "Under standard benchmarks,"],
    )
    synth_prefix = _pick(
        f"{sub_id}:synth",
        ["Collectively,", "Stepping back,", "Overall,", "Taken together,"],
    )
    causal_prefix = _pick(
        f"{sub_id}:causal",
        ["Therefore,", "As a result,", "Consequently,", "This suggests that"],
    )
    lim_prefix = _pick(
        f"{sub_id}:lim",
        ["Despite these advances,", "However, these routes remain limited in practice, since", "A key limitation is that", "This raises the question of whether"],
    )

    plan = [
        {
            "para": 1,
            "argument_role": "setup_thesis",
            "intent": "Define scope, setup, and the subsection thesis (no pipeline jargon).",
            "focus": ["scope boundary", "key definitions", "thesis vs neighboring subsections"],
            "connector_to_prev": "",
            "connector_phrase": "",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 2,
            "argument_role": "mechanism_cluster_A",
            "intent": "Explain cluster A: core mechanism/architecture and what decision it makes in the agent loop.",
            "focus": [f"cluster: {c1}", "mechanism / architecture", "assumptions"],
            "connector_to_prev": "grounding",
            "connector_phrase": f"{_pick(f'{sub_id}:p2', ['To ground this thesis,', 'To make this concrete,'])} {c1} approaches provide a natural starting point because they make the agent-loop decision explicit.",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 3,
            "argument_role": "implementation_cluster_A",
            "intent": "Cluster A implementation details: data/training signals and interface contract (tools/memory) that constrain behavior.",
            "focus": [f"cluster: {c1}", "data / training setup", "interface contract", f"axes: {axes_hint}"],
            "connector_to_prev": "elaboration",
            "connector_phrase": f"{extend_prefix} these designs imply concrete interface/data assumptions that shape behavior.",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 4,
            "argument_role": "evaluation_cluster_A",
            "intent": "Cluster A evaluation/trade-offs: where it works, costs (compute/latency), and typical failure modes.",
            "focus": [f"cluster: {c1}", "evaluation anchor", "efficiency", "failure modes"],
            "connector_to_prev": "evaluation",
            "connector_phrase": f"{eval_prefix} protocols and metrics clarify where {c1} works, and where it fails or becomes costly.",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 5,
            "argument_role": "contrast_cluster_B",
            "intent": "Explain cluster B (contrast with A): core mechanism/architecture and what it optimizes for.",
            "focus": [f"cluster: {c2}", f"contrast with {c1}", "mechanism / architecture"],
            "connector_to_prev": "contrast",
            "connector_phrase": f"{contrast_prefix} {c2} approaches shift the emphasis and optimize for a different point in the trade-off space.",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 6,
            "argument_role": "implementation_cluster_B",
            "intent": "Cluster B implementation details: data/training and interface assumptions (mirror A for comparability).",
            "focus": [f"cluster: {c2}", "data / training setup", "interface contract", f"axes: {axes_hint}"],
            "connector_to_prev": "elaboration",
            "connector_phrase": f"{extend_prefix} the B-route relies on different interface/training assumptions, which changes failure modes and costs.",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 7,
            "argument_role": "evaluation_cluster_B",
            "intent": "Cluster B evaluation/trade-offs: where it works, costs, and failure modes (mirror A).",
            "focus": [f"cluster: {c2}", "evaluation anchor", "efficiency", "failure modes"],
            "connector_to_prev": "evaluation",
            "connector_phrase": f"{eval_prefix} when comparable settings exist, evaluation evidence for B can be contrasted against A to surface the trade-offs.",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 8,
            "argument_role": "cross_paper_synthesis",
            "intent": "Cross-paper synthesis: compare clusters along the main axes (include >=2 citations in one paragraph).",
            "focus": [f"compare {c1} vs {c2}", "multiple citations in one paragraph", f"axes: {axes_hint}"],
            "connector_to_prev": "synthesis",
            "connector_phrase": f"{synth_prefix} the key distinction between {c1} and {c2} is how they trade off {axes_hint} under evaluation constraints.",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
        {
            "para": 9,
            "argument_role": "decision_guidance",
            "intent": "Decision guidance: when to choose which route (criteria + evaluation signals + engineering constraints).",
            "focus": ["decision checklist", "evaluation protocol", "practical constraints"],
            "connector_to_prev": "consequence",
            "connector_phrase": f"{causal_prefix} a decision checklist can map evaluation signals and constraints to route selection.",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
        {
            "para": 10,
            "argument_role": "limitations_open_questions",
            "intent": "Limitations + verification targets; end with a concrete open question to hand off.",
            "focus": ["limitations", f"evidence mode: {mode}", "what needs verification", "open question"],
            "connector_to_prev": "limitations",
            "connector_phrase": f"{lim_prefix} key claims hinge on assumptions that merit stress-testing, which motivates concrete verification targets.",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
    ]

    if not has_fulltext:
        plan[-1]["policy"] = "Use conservative language; avoid strong conclusions; prefer questions-to-answer + explicit evidence gaps list."
    else:
        plan[-1]["policy"] = "Claims must remain traceable to citations; summarize limitations without adding new facts."

    plan[0]["rq"] = rq
    return plan



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
