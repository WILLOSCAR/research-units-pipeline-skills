from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--min-freq", type=int, default=3)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import candidate_keywords, dump_yaml, parse_semicolon_list, read_jsonl, tokenize

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["papers/core_set.csv"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/taxonomy.yml"]

    core_path = workspace / inputs[0]
    out_path = workspace / outputs[0]

    if not core_path.exists():
        raise SystemExit(f"Missing core set: {core_path}")

    # Never overwrite non-placeholder user work.
    if out_path.exists() and out_path.stat().st_size > 0:
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if not _is_placeholder(existing):
            return 0

    titles: list[str] = []
    core_rows: list[dict[str, str]] = []
    with core_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row = row or {}
            title = str(row.get("title") or "").strip()
            if title:
                titles.append(title)
            core_rows.append({k: str(v or "").strip() for k, v in row.items()})

    # Optional: leverage papers_dedup.jsonl for richer keyword signals (abstracts/categories).
    dedup_path = workspace / "papers" / "papers_dedup.jsonl"
    dedup = read_jsonl(dedup_path) if dedup_path.exists() else []

    text_blob = "\n".join([_safe_lower(t) for t in titles])
    for rec in dedup:
        if not isinstance(rec, dict):
            continue
        text_blob += "\n" + _safe_lower(str(rec.get("title") or ""))
        text_blob += "\n" + _safe_lower(str(rec.get("abstract") or ""))

    profile = _detect_profile(workspace=workspace, text_blob=text_blob)

    if profile == "llm_agents":
        dump_yaml(out_path, _llm_agent_taxonomy(core_rows=core_rows))
        return 0

    if profile == "gen_image":
        dump_yaml(out_path, _gen_image_taxonomy(core_rows=core_rows))
        return 0

    # Generic fallback: build a two-level taxonomy from frequent terms, but with non-placeholder descriptions.
    top_topics = candidate_keywords(titles, top_k=int(args.top_k), min_freq=int(args.min_freq))
    if not top_topics:
        top_topics = ["methods", "evaluation", "applications"]

    taxonomy: list[dict[str, Any]] = []
    for token in top_topics[:4]:
        subset = [t for t in titles if token in set(tokenize(t))]
        sub = candidate_keywords(subset, top_k=6, min_freq=1)
        sub = [s for s in sub if s not in {"overview", "benchmarks", "open", "problems"}]
        if not sub:
            sub = ["problem", "mechanisms", "evaluation", "limitations"]

        rep = _representative_papers(core_rows=core_rows, terms=[token] + list(sub))
        rep_str = ", ".join(rep[:4]) if rep else ""
        desc_terms = ", ".join([_pretty(s) for s in sub[:4]])
        desc_parts = [
            f"Cluster capturing work where '{token}' is a salient term in titles/abstracts.",
            f"Common related terms include: {desc_terms}." if desc_terms else "",
            f"Representative paper_id(s): {rep_str}." if rep_str else "",
        ]
        desc = " ".join([p for p in desc_parts if p]).strip()

        taxonomy.append(
            {
                "name": _pretty(token),
                "description": desc,
                "children": [
                    {
                        "name": _pretty(st),
                        "description": _child_description(
                            parent=_pretty(token),
                            child=_pretty(st),
                            core_rows=core_rows,
                            seed_terms=[token, st],
                        ),
                    }
                    for st in sub[:3]
                ],
            }
        )

    if all(not item.get("children") for item in taxonomy):
        raise SystemExit("Failed to build a 2-level taxonomy")

    dump_yaml(out_path, taxonomy)
    return 0


def _pretty(token: str) -> str:
    token = token.replace("_", " ").replace("-", " ").strip()
    return " ".join([w[:1].upper() + w[1:] for w in token.split() if w])


def _safe_lower(text: str) -> str:
    return (text or "").strip().lower()


def _detect_profile(*, workspace: Path, text_blob: str) -> str:
    queries_path = workspace / "queries.md"
    goal_path = workspace / "GOAL.md"
    low = (text_blob or "").lower()
    if queries_path.exists():
        low += "\n" + _safe_lower(queries_path.read_text(encoding="utf-8", errors="ignore"))
    if goal_path.exists():
        low += "\n" + _safe_lower(goal_path.read_text(encoding="utf-8", errors="ignore"))

    if ("agent" in low or "agents" in low) and (
        "llm" in low or "language model" in low or "gpt" in low or "chatgpt" in low
    ):
        return "llm_agents"

    gen_signals = [
        "diffusion",
        "text-to-image",
        "text to image",
        "image generation",
        "stable diffusion",
        "sdxl",
        "dit",
        "pixart",
        "imagen",
        "maskgit",
        "vqgan",
        "vqvae",
        "gan",
        "autoregressive",
    ]
    if any(sig in low for sig in gen_signals):
        return "gen_image"

    return "generic"


def _llm_agent_taxonomy(*, core_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Domain-aware, paper-like taxonomy for tool-using LLM agents.

    Design goal: avoid fragmentation (too many tiny H3s). Prefer fewer, thicker buckets
    that can each sustain evidence-first writing.
    """

    def rep_str(terms: list[str]) -> str:
        rep = _representative_papers(core_rows=core_rows, terms=terms)
        return ", ".join(rep[:4]) if rep else ""

    def with_rep(base: str, terms: list[str]) -> str:
        rep = rep_str(terms)
        return base + (f" Representative paper_id(s): {rep}." if rep else "")

    return [
        {
            "name": "Foundations & Interfaces",
            "description": with_rep(
                "Problem formulation and interface design for tool-using LLM agents: the agent loop, action spaces, and the tool/environment boundary that constrains reliability.",
                ["agent", "tool", "environment", "api", "interface", "function"],
            ),
            "children": [
                {
                    "name": "Agent loop and action spaces",
                    "description": "Agent loop abstractions (state → decide → act → observe), action representations, environment/tool modeling, and failure recovery assumptions.",
                },
                {
                    "name": "Tool interfaces and orchestration",
                    "description": "Calling tools/APIs (function calling), tool selection/routing, permissions/sandboxing, and orchestration patterns that affect correctness and safety.",
                },
            ],
        },
        {
            "name": "Core Components (Planning + Memory)",
            "description": with_rep(
                "Core capability levers for long-horizon agents: planning/reasoning for action selection and memory/retrieval for grounded state.",
                ["planning", "reasoning", "memory", "retrieval", "rag"],
            ),
            "children": [
                {
                    "name": "Planning and reasoning loops",
                    "description": "Decomposition, plan search/verification, and robustness under partial observability and tool failures; how planning interleaves with tool calls.",
                },
                {
                    "name": "Memory and retrieval (RAG)",
                    "description": "Working vs long-term memory, retrieval policies, state summarization, grounding strategies, and how memory interacts with planning and tool use.",
                },
            ],
        },
        {
            "name": "Learning, Adaptation & Coordination",
            "description": with_rep(
                "How agents improve with experience (reflection/RL/prompt/program optimization) and how multiple agents coordinate to divide labor or verify outputs.",
                ["reflection", "self", "improve", "rl", "multi-agent", "coordination", "communication"],
            ),
            "children": [
                {
                    "name": "Self-improvement and adaptation",
                    "description": "Reflection/critique/revision loops, preference optimization, and evaluation-driven prompt/program tuning; stability and reward hacking risks.",
                },
                {
                    "name": "Multi-agent coordination",
                    "description": "Role specialization, communication protocols, debate/verification patterns, aggregation, and coordination failure modes.",
                },
            ],
        },
        {
            "name": "Evaluation & Risks",
            "description": with_rep(
                "What we measure and why it is hard: benchmarks/protocols for tool-use and long-horizon tasks, plus risk surfaces and governance constraints for deployed agents.",
                ["benchmark", "evaluation", "tool", "safety", "security", "attack", "governance"],
            ),
            "children": [
                {
                    "name": "Benchmarks and evaluation protocols",
                    "description": "Task suites, datasets, metrics, human evaluation, leakage/reproducibility concerns, and how evaluation choices bias conclusions.",
                },
                {
                    "name": "Safety, security, and governance",
                    "description": "Threat models (prompt injection, data exfiltration, tool abuse), guardrails/monitoring, and governance controls for deployed agents.",
                },
            ],
        },
    ]


def _gen_image_taxonomy(*, core_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Paper-like taxonomy for generative image models (<=12 subsections)."""

    rep = _representative_papers(core_rows=core_rows, terms=["diffusion", "text", "image", "token", "gan", "edit"])
    rep_str = ", ".join(rep[:4]) if rep else ""

    return [
        {
            "name": "Foundations & Formulations",
            "description": (
                "Core objectives, representations, and sampling/inference formulations for modern generative image models."
                + (f" Representative paper_id(s): {rep_str}." if rep_str else "")
            ),
            "children": [
                {
                    "name": "Objectives and likelihood views",
                    "description": "Training objectives (denoising/score matching, autoregressive factorization, adversarial training) and what they optimize.",
                },
                {
                    "name": "Representations (pixel/latent/token)",
                    "description": "How representations (pixel space, continuous latents, discrete tokens) shape compute, fidelity, and controllability.",
                },
                {
                    "name": "Sampling and efficiency",
                    "description": "Samplers/solvers, guidance, distillation/consistency, and other techniques that reduce inference steps and cost.",
                },
            ],
        },
        {
            "name": "Model Families (Diffusion & Token-based)",
            "description": "Major model families for text-to-image generation and editing, and the trade-offs they induce (quality, speed, controllability).",
            "children": [
                {
                    "name": "Diffusion and latent diffusion",
                    "description": "Diffusion-style pipelines, latent diffusion, and conditioning mechanisms (cross-attention) with implications for compute and controllability.",
                },
                {
                    "name": "Diffusion transformers and scaling",
                    "description": "Transformer backbones (DiT-style) and scaling/architecture choices that affect sample quality, training stability, and inference speed.",
                },
                {
                    "name": "Token-based / AR / masked generation",
                    "description": "Discrete tokenization, autoregressive or masked token predictors, and decoding strategies; comparisons versus diffusion pipelines.",
                },
            ],
        },
        {
            "name": "Control, Editing & Conditioning",
            "description": "Mechanisms to steer generation: structured conditioning, layout/geometry signals, inpainting/editing, and personalization.",
            "children": [
                {
                    "name": "Structured controls",
                    "description": "Conditioning with geometry/layout/depth/pose/segmentation and how control signals propagate through the backbone.",
                },
                {
                    "name": "Instruction-guided editing",
                    "description": "Editing/inversion methods, text-based editing, and failure modes such as identity drift or over-editing.",
                },
                {
                    "name": "Personalization and tuning",
                    "description": "Fine-tuning and parameter-efficient adaptation (e.g., LoRA-like) for subject-driven personalization with limited examples.",
                },
            ],
        },
        {
            "name": "Evaluation, Safety & Provenance",
            "description": "How models are evaluated, common benchmark pitfalls, and concerns around bias, misuse, and provenance/watermarking.",
            "children": [
                {
                    "name": "Metrics and human evaluation",
                    "description": "Automatic metrics (distribution/semantic alignment) and human evaluation protocols; gaps between metrics and perception.",
                },
                {
                    "name": "Robustness and failure modes",
                    "description": "Prompt sensitivity, compositional failures, bias/toxicity, and reliability issues under distribution shift.",
                },
                {
                    "name": "Provenance and safeguards",
                    "description": "Watermarking/provenance, dataset governance, and mitigation strategies for misuse and deepfakes.",
                },
            ],
        },
    ]


def _representative_papers(*, core_rows: list[dict[str, str]], terms: list[str]) -> list[str]:
    terms_low = {t.strip().lower() for t in terms if str(t).strip()}
    hits: list[tuple[int, str]] = []
    for row in core_rows:
        pid = str(row.get("paper_id") or "").strip()
        title = _safe_lower(str(row.get("title") or ""))
        if not pid or not title:
            continue
        score = sum(1 for t in terms_low if t and t in title)
        if score:
            hits.append((score, pid))
    hits.sort(key=lambda t: (-t[0], t[1]))
    return [pid for _, pid in hits[:8]]


def _child_description(*, parent: str, child: str, core_rows: list[dict[str, str]], seed_terms: list[str]) -> str:
    rep = _representative_papers(core_rows=core_rows, terms=seed_terms)
    rep_str = ", ".join(rep[:3]) if rep else ""
    parts = [
        f"Subtopic under '{parent}' focusing on '{child}' as a recurrent theme in the core set.",
        f"Representative paper_id(s): {rep_str}." if rep_str else "",
        "Use this bucket when the paper explicitly emphasizes this mechanism/setting in its title or abstract.",
    ]
    return " ".join([p for p in parts if p]).strip()


def _is_placeholder(text: str) -> bool:
    text = (text or "").strip().lower()
    if not text:
        return True
    if "(placeholder)" in text:
        return True
    if "<!-- scaffold" in text:
        return True
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", text):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
