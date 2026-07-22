from __future__ import annotations

import json
import math
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from tooling.common import decisions_has_approval, load_yaml, read_jsonl, tokenize


_GENERIC_TITLE_WORDS = {
    "tutorial",
    "guide",
    "lecture",
    "video",
    "primer",
    "intro",
    "introduction",
    "repo",
    "repository",
    "docs",
    "documentation",
    "source",
    "sources",
    "reader",
    "readers",
}

_PHRASE_FILLERS = {
    "a",
    "an",
    "and",
    "for",
    "how",
    "if",
    "in",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "when",
    "why",
    "with",
}

_ACTION_PATTERNS = [
    r"\b(?:should|can)\s+explain\s+(.+)",
    r"\b(?:should|can)\s+teach\s+(.+)",
    r"\b(?:should|can)\s+cover\s+(.+)",
    r"\b(?:should|can)\s+show\s+(.+)",
    r"\bdocuments?\s+(.+)",
    r"\bexplains?\s+(.+)",
    r"\bdemonstrates?\s+(.+)",
    r"\bshows?\s+(.+)",
    r"\blearn(?:ers)?\s+should\s+learn\s+how\s+to\s+(.+)",
    r"\blearn\s+how\s+to\s+(.+)",
]

_BUCKET_ORDER = ["foundation", "data", "build", "evaluate", "iterate"]
_BUCKET_KEYWORDS = {
    "foundation": {
        "basics",
        "behavior",
        "cloning",
        "concept",
        "concepts",
        "foundation",
        "observations",
        "observation",
        "actions",
        "action",
        "policy",
        "policies",
        "task",
        "tasks",
        "interface",
        "interfaces",
        "schema",
        "format",
    },
    "data": {
        "data",
        "dataset",
        "datasets",
        "demonstration",
        "demonstrations",
        "trajectory",
        "trajectories",
        "collection",
        "records",
        "samples",
    },
    "build": {
        "training",
        "train",
        "configuration",
        "configs",
        "pipeline",
        "checkpoint",
        "checkpointing",
        "implementation",
        "workflow",
        "scripts",
        "launch",
    },
    "evaluate": {
        "evaluation",
        "evaluate",
        "metrics",
        "metric",
        "validation",
        "rollout",
        "rollouts",
        "benchmark",
        "benchmarks",
        "inspection",
        "inspect",
        "testing",
        "test",
    },
    "iterate": {
        "debugging",
        "debug",
        "failure",
        "failures",
        "analysis",
        "limitations",
        "limitation",
        "revisit",
        "iteration",
        "troubleshooting",
        "deploy",
        "deployment",
    },
}
_OBJECTIVE_VERBS = {
    "foundation": "Explain",
    "data": "Organize",
    "build": "Run",
    "evaluate": "Compare",
    "iterate": "Diagnose",
}


def read_goal_summary(path: Path) -> str:
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", ">", "<!--")):
            continue
        low = line.lower()
        if "replace" in low or "todo" in low:
            continue
        return line
    return ""


def load_source_bundle(workspace: Path) -> list[dict[str, Any]]:
    index_records = read_jsonl(workspace / "sources" / "index.jsonl")
    prov_records = read_jsonl(workspace / "sources" / "provenance.jsonl")
    prov_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in prov_records:
        source_id = str(rec.get("source_id") or "").strip()
        if source_id:
            prov_by_source[source_id].append(rec)

    bundle: list[dict[str, Any]] = []
    for rec in index_records:
        if str(rec.get("status") or "").strip() != "success":
            continue
        source_id = str(rec.get("source_id") or "").strip()
        if not source_id:
            continue
        provenance = prov_by_source.get(source_id, [])
        text_parts: list[str] = []
        pointers: list[dict[str, str]] = []
        if provenance:
            for prov in provenance:
                local_path = str(prov.get("local_path") or "").strip()
                text = _read_workspace_path(workspace, local_path)
                if text:
                    text_parts.append(text)
                pointers.append(
                    {
                        "pointer": str(prov.get("pointer") or local_path).strip(),
                        "local_path": local_path,
                        "note": str(prov.get("note") or "").strip(),
                        "origin": str(prov.get("origin_url_or_path") or "").strip(),
                        "text": text,
                    }
                )
        else:
            local_path = str(rec.get("local_path") or "").strip()
            text = _read_workspace_path(workspace, local_path)
            if text:
                text_parts.append(text)
            if local_path:
                pointers.append(
                    {
                        "pointer": local_path,
                        "local_path": local_path,
                        "note": "",
                        "origin": str(rec.get("canonical_url") or "").strip(),
                        "text": text,
                    }
                )

        title = str(rec.get("title") or source_id).strip()
        text = "\n\n".join(part for part in text_parts if part.strip()).strip()
        low_tokens = set(tokenize(title + "\n" + text))
        bundle.append(
            {
                "source_id": source_id,
                "kind": str(rec.get("kind") or "").strip(),
                "title": title,
                "canonical_url": str(rec.get("canonical_url") or "").strip(),
                "required": bool(rec.get("required", False)),
                "text": text,
                "tokens": low_tokens,
                "pointers": pointers,
            }
        )
    return bundle


def build_source_tutorial_spec(workspace: Path) -> dict[str, Any]:
    goal = read_goal_summary(workspace / "GOAL.md")
    bundle = load_source_bundle(workspace)
    if not bundle:
        raise ValueError("source-tutorial-spec requires non-empty `sources/index.jsonl` and `sources/provenance.jsonl`.")

    candidates = _collect_phrase_candidates(bundle)
    concepts = _select_concepts(candidates)
    if not concepts:
        concepts = _fallback_concepts(bundle)

    learning_objectives = [_objective_from_concept(concept) for concept in concepts[:5]]
    primary_phrase = concepts[0]["title"] if concepts else "the source-backed workflow"
    running_example = _pick_running_example(bundle)
    audience = [
        f"Readers who want a guided path through {primary_phrase.lower()} without reading every source end-to-end.",
        _audience_support_line(bundle),
    ]
    prerequisites = [
        "Comfort reading structured technical material and following a multi-step example.",
        _prerequisite_from_concepts(concepts),
    ]
    non_goals = [
        "This tutorial is not an exhaustive survey of every adjacent branch or benchmark.",
        "It does not replace the original repo/docs/video; it restructures them into one teaching sequence.",
        "It stays within the concepts and examples that the current source set can support explicitly.",
    ]
    source_scope = [_source_scope_entry(source, concepts) for source in bundle]
    delivery_shape = [
        "Primary deliverable: article-first tutorial (`output/TUTORIAL.md`).",
        "Derived deliverables: article PDF (`latex/main.pdf`) and Beamer slides (`latex/slides/main.pdf`).",
        "Source notes stay visible in each module instead of being collapsed into a hidden appendix.",
    ]

    return {
        "title": _spec_title(goal, concepts),
        "goal": goal,
        "audience": audience,
        "prerequisites": prerequisites,
        "learning_objectives": learning_objectives,
        "non_goals": non_goals,
        "source_scope": source_scope,
        "running_example_policy": running_example,
        "delivery_shape": delivery_shape,
        "core_concepts": concepts,
    }


def render_source_tutorial_spec_markdown(spec: dict[str, Any]) -> str:
    title = str(spec.get("title") or "Source-grounded Tutorial Spec").strip()
    lines = [
        f"# {title}",
        "",
        "## Audience",
    ]
    lines.extend([f"- {item}" for item in spec.get("audience") or []])
    lines.extend(
        [
            "",
            "## Prerequisites",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("prerequisites") or []])
    lines.extend(
        [
            "",
            "## Learning objectives",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("learning_objectives") or []])
    lines.extend(
        [
            "",
            "## Non-goals",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("non_goals") or []])
    lines.extend(
        [
            "",
            "## Source scope",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("source_scope") or []])
    running = dict(spec.get("running_example_policy") or {})
    lines.extend(
        [
            "",
            "## Running example policy",
            f"- Mode: `{str(running.get('mode') or 'none').strip()}`",
            f"- Summary: {str(running.get('summary') or 'No single running example is stable enough across the current sources.').strip()}",
            f"- Reason: {str(running.get('reason') or 'No strong source-supported example was found.').strip()}",
        ]
    )
    lines.extend(
        [
            "",
            "## Delivery shape",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("delivery_shape") or []])
    lines.extend(
        [
            "",
            "## Core concepts",
        ]
    )
    for concept in spec.get("core_concepts") or []:
        if not isinstance(concept, dict):
            continue
        source_ids = ", ".join(concept.get("source_ids") or [])
        lines.append(f"- `{concept['id']}` {concept['title']} - {concept['summary']} (sources: {source_ids})")
    lines.extend(
        [
            "",
            "## Structured data",
            "```json",
            json.dumps(spec, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def load_source_tutorial_spec_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"## Structured data\s+```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        payload = json.loads(match.group(1))
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"Could not read structured spec data from {path}")


def build_concept_graph(spec_data: dict[str, Any]) -> dict[str, Any]:
    concepts = spec_data.get("core_concepts") or []
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("Structured tutorial spec has no `core_concepts`.")
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for concept in concepts:
        if not isinstance(concept, dict):
            continue
        concept_id = str(concept.get("id") or "").strip()
        if not concept_id or concept_id in seen_ids:
            continue
        seen_ids.add(concept_id)
        nodes.append(
            {
                "id": concept_id,
                "title": str(concept.get("title") or concept_id).strip(),
                "summary": str(concept.get("summary") or "").strip(),
                "source_ids": list(concept.get("source_ids") or []),
                "objective_refs": list(concept.get("objective_refs") or []),
                "bucket": str(concept.get("bucket") or "").strip(),
            }
        )
        for prereq in concept.get("prerequisites") or []:
            prereq_id = str(prereq or "").strip()
            if prereq_id:
                edges.append({"from": prereq_id, "to": concept_id})
    return {"nodes": nodes, "edges": _dedupe_edge_dicts(edges)}


def build_module_plan(graph: dict[str, Any], *, spec_data: dict[str, Any] | None = None) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes") or [] if isinstance(node, dict) and str(node.get("id") or "").strip()]
    if not nodes:
        raise ValueError("module-planner requires non-empty concept graph nodes.")
    spec = spec_data or {}
    objectives = list(spec.get("learning_objectives") or [])
    running = dict(spec.get("running_example_policy") or {})

    node_map = {str(node["id"]).strip(): node for node in nodes}
    ordered_ids = topological_order(graph)
    ordered_nodes = [node_map[node_id] for node_id in ordered_ids if node_id in node_map]
    chunk_size = max(1, math.ceil(len(ordered_nodes) / max(2, min(5, math.ceil(len(ordered_nodes) / 2)))))
    chunks = [ordered_nodes[idx: idx + chunk_size] for idx in range(0, len(ordered_nodes), chunk_size)]

    modules: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        concept_ids = [str(node["id"]).strip() for node in chunk]
        concept_titles = [str(node.get("title") or "").strip() for node in chunk if str(node.get("title") or "").strip()]
        module_title = _compose_module_title(concept_titles, index=idx)
        module_objectives = _module_objectives(chunk, objectives)
        outputs = [
            f"Produce a short explanation or checklist that makes `{concept_titles[0]}` concrete in the tutorial flow.",
            f"Update the running example or module notes so `{module_title}` can be reused by the next module.",
        ]
        modules.append(
            {
                "id": f"M{idx:02d}",
                "title": module_title,
                "objectives": module_objectives,
                "concepts": concept_ids,
                "outputs": outputs,
                "running_example_steps": _running_example_steps(module_title, running, idx),
                "source_ids": _ordered_unique([source_id for node in chunk for source_id in node.get("source_ids") or []]),
            }
        )
    return {"modules": modules}


def add_module_exercises(plan: dict[str, Any]) -> dict[str, Any]:
    modules = [module for module in plan.get("modules") or [] if isinstance(module, dict)]
    if not modules:
        raise ValueError("exercise-builder requires non-empty `outline/module_plan.yml`.")
    for module in modules:
        if module.get("exercises"):
            continue
        title = str(module.get("title") or "the module").strip()
        outputs = list(module.get("outputs") or [])
        step = "; ".join(module.get("running_example_steps") or [])
        module["exercises"] = [
            {
                "prompt": f"Use this module to explain or reproduce `{title}` on the running example.",
                "expected_output": outputs[0] if outputs else f"A concise artifact showing `{title}`.",
                "verification_steps": [
                    f"Check that the result names the core concepts behind `{title}`.",
                    "Check that the result can be traced back to at least one source note or snippet.",
                    f"Check that the result connects cleanly to the running example step: {step or 'summarize the current example state.'}",
                ],
            }
        ]
    return {"modules": modules}


def build_module_source_coverage(workspace: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    modules = [module for module in plan.get("modules") or [] if isinstance(module, dict)]
    if not modules:
        raise ValueError("module-source-coverage requires non-empty `outline/module_plan.yml`.")
    bundle = load_source_bundle(workspace)
    records: list[dict[str, Any]] = []
    for module in modules:
        title = str(module.get("title") or "").strip()
        query = "\n".join(
            [title]
            + [str(item) for item in module.get("objectives") or []]
            + [str(item) for item in module.get("running_example_steps") or []]
            + [str(item) for item in module.get("outputs") or []]
        )
        ranked = sorted(
            (
                {
                    "source": source,
                    "score": _match_score(query, source),
                }
                for source in bundle
            ),
            key=lambda item: (-item["score"], item["source"]["source_id"]),
        )
        selected = [item["source"] for item in ranked if item["score"] > 0][:2]
        gaps: list[str] = []
        if not selected and ranked:
            selected = [ranked[0]["source"]]
            gaps.append("Weak lexical grounding; keep the module scoped tightly to the selected source notes.")
        records.append(
            {
                "module_id": str(module.get("id") or "").strip(),
                "module_title": title,
                "source_ids": [source["source_id"] for source in selected],
                "matched_pointers": [
                    pointer["pointer"]
                    for source in selected
                    for pointer in source.get("pointers") or []
                    if str(pointer.get("pointer") or "").strip()
                ],
                "gaps": gaps,
            }
        )
    return records


def build_tutorial_context_packs(workspace: Path, plan: dict[str, Any], coverage_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modules = [module for module in plan.get("modules") or [] if isinstance(module, dict)]
    coverage_by_id = {str(record.get("module_id") or "").strip(): record for record in coverage_records if str(record.get("module_id") or "").strip()}
    bundle = load_source_bundle(workspace)
    bundle_by_id = {source["source_id"]: source for source in bundle}

    packs: list[dict[str, Any]] = []
    for module in modules:
        module_id = str(module.get("id") or "").strip()
        coverage = coverage_by_id.get(module_id) or {}
        source_ids = [str(source_id or "").strip() for source_id in coverage.get("source_ids") or [] if str(source_id or "").strip()]
        selected_sources = [bundle_by_id[source_id] for source_id in source_ids if source_id in bundle_by_id]
        snippets = _source_snippets_for_module(module, selected_sources)
        exercise = {}
        exercises = module.get("exercises") or []
        if exercises and isinstance(exercises[0], dict):
            exercise = dict(exercises[0])
        packs.append(
            {
                "module_id": module_id,
                "title": str(module.get("title") or "").strip(),
                "objective": str((module.get("objectives") or [""])[0]).strip(),
                "objectives": list(module.get("objectives") or []),
                "core_concepts": list(module.get("concepts") or []),
                "outputs": list(module.get("outputs") or []),
                "running_example_steps": list(module.get("running_example_steps") or []),
                "worked_example_candidates": _worked_example_candidates(module, snippets),
                "pitfalls": _pack_pitfalls(module, coverage),
                "exercise_seed": exercise,
                "source_ids": source_ids,
                "source_snippets": snippets,
            }
        )
    return packs


def render_source_tutorial_markdown(workspace: Path, *, spec_data: dict[str, Any] | None = None) -> str:
    decisions_path = workspace / "DECISIONS.md"
    if not decisions_has_approval(decisions_path, "C2"):
        raise PermissionError("Approve C2 is required before writing `output/TUTORIAL.md`.")

    plan = _load_module_plan(workspace)
    packs = _load_context_packs(workspace)
    pack_by_id = {str(pack.get("module_id") or "").strip(): pack for pack in packs if str(pack.get("module_id") or "").strip()}
    spec = spec_data or _maybe_load_spec(workspace)

    title = str(spec.get("title") or "Source-grounded Tutorial").strip()
    lines = [
        f"# {title}",
        "",
        "## Who This Is For",
    ]
    lines.extend([f"- {item}" for item in spec.get("audience") or []])
    lines.extend(
        [
            "",
            "## Prerequisites",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("prerequisites") or []])
    lines.extend(
        [
            "",
            "## What You Will Learn",
        ]
    )
    lines.extend([f"- {item}" for item in spec.get("learning_objectives") or []])
    lines.extend(
        [
            "",
            "## How To Use This Tutorial",
            "- Move module by module; each one advances the same source-backed story rather than starting from scratch.",
            "- Keep the source notes visible so you can jump back to the original material when you need more detail.",
            "- Treat the check-yourself block as the module exit criterion before you continue.",
        ]
    )

    for index, module in enumerate(plan.get("modules") or [], start=1):
        if not isinstance(module, dict):
            continue
        module_id = str(module.get("id") or "").strip()
        pack = pack_by_id.get(module_id) or {}
        lines.extend(
            [
                "",
                f"## Module {index}: {str(module.get('title') or module_id).strip()}",
                "",
                "### Why it matters",
                _render_why_it_matters(spec, module, pack),
                "",
                "### Key idea",
            ]
        )
        lines.extend(_render_key_idea(module, pack))
        lines.extend(
            [
                "",
                "### Worked example",
            ]
        )
        lines.extend(_render_worked_example(pack))
        lines.extend(
            [
                "",
                "### Check yourself",
            ]
        )
        lines.extend(_render_check_yourself(pack))
        lines.extend(
            [
                "",
                "### Source notes",
            ]
        )
        lines.extend(_render_source_notes(pack))

    return "\n".join(lines).rstrip() + "\n"


def topological_order(graph: dict[str, Any]) -> list[str]:
    nodes = [str(node.get("id") or "").strip() for node in graph.get("nodes") or [] if isinstance(node, dict)]
    edges = [edge for edge in graph.get("edges") or [] if isinstance(edge, dict)]
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        src = str(edge.get("from") or "").strip()
        dst = str(edge.get("to") or "").strip()
        if src not in indegree or dst not in indegree:
            continue
        outgoing[src].append(dst)
        indegree[dst] += 1
    queue = deque(sorted(node_id for node_id, deg in indegree.items() if deg == 0))
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for nxt in sorted(outgoing[node_id]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        raise ValueError("concept graph is cyclic")
    return order


def _maybe_load_spec(workspace: Path) -> dict[str, Any]:
    spec_path = workspace / "output" / "TUTORIAL_SPEC.md"
    if spec_path.exists():
        return load_source_tutorial_spec_data(spec_path)
    return {
        "title": "Source-grounded Tutorial",
        "audience": ["Readers who need a cleaner path through the current source set."],
        "prerequisites": ["Comfort reading structured technical material."],
        "learning_objectives": [],
    }


def _load_module_plan(workspace: Path) -> dict[str, Any]:
    path = workspace / "outline" / "module_plan.yml"
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid module plan: {path}")
    return data


def _load_context_packs(workspace: Path) -> list[dict[str, Any]]:
    return [dict(record) for record in read_jsonl(workspace / "outline" / "tutorial_context_packs.jsonl") if isinstance(record, dict)]


def _spec_title(goal: str, concepts: list[dict[str, Any]]) -> str:
    if goal:
        goal_line = goal.rstrip(".")
        if len(goal_line) <= 80:
            return goal_line
    if concepts:
        return f"{concepts[0]['title']} Tutorial"
    return "Source-grounded Tutorial Spec"


def _audience_support_line(bundle: list[dict[str, Any]]) -> str:
    kinds = {source["kind"] for source in bundle}
    parts: list[str] = []
    if "repo" in kinds or "docs_site" in kinds:
        parts.append("willing to inspect repo/docs snippets")
    if "video" in kinds:
        parts.append("happy to learn from transcript-backed demonstrations")
    if "pdf" in kinds or "webpage" in kinds:
        parts.append("comfortable cross-checking short textual explanations")
    if not parts:
        return "Readers who want one coherent explanation stitched from multiple materials."
    return "Best for readers " + ", ".join(parts) + "."


def _prerequisite_from_concepts(concepts: list[dict[str, Any]]) -> str:
    focus = ", ".join(concept["title"].lower() for concept in concepts[:2])
    return f"Basic familiarity with the terms behind {focus} is enough; the rest is taught in sequence."


def _source_scope_entry(source: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    relevant = [concept["title"] for concept in concepts if source["source_id"] in (concept.get("source_ids") or [])]
    coverage = ", ".join(relevant[:3]) if relevant else "general context"
    return f"`{source['source_id']}` ({source['kind']}) - {source['title']} - used for {coverage}."


def _pick_running_example(bundle: list[dict[str, Any]]) -> dict[str, str]:
    patterns = [
        r"(?:running example|example)\s+(?:around|for|using)\s+(?:an?|the)?\s*([^.]+)",
        r"demonstrates?\s+(?:a|an|the)?\s*([^.]+)",
    ]
    for source in bundle:
        text = source["text"]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            phrase = _clean_phrase(match.group(1))
            if phrase:
                return {
                    "mode": "supported",
                    "summary": f"Use `{phrase}` as the running example that accumulates across modules.",
                    "reason": f"The source set names `{phrase}` explicitly in `{source['source_id']}`.",
                    "label": phrase,
                }
    return {
        "mode": "none",
        "summary": "No single running example is strong enough across the current source set.",
        "reason": "The sources cover the workflow, but none of them provides one stable example that survives every module.",
        "label": "",
    }


def _collect_phrase_candidates(bundle: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source_index, source in enumerate(bundle):
        title_phrase = _clean_title_phrase(source["title"])
        if title_phrase:
            candidates.append(
                {
                    "display": title_phrase,
                    "norm": _normalize_phrase(title_phrase),
                    "source_ids": [source["source_id"]],
                    "bucket": _bucket_for_text(title_phrase),
                    "summary": f"Anchor the tutorial with `{title_phrase}` from `{source['source_id']}`.",
                    "source_index": source_index,
                    "candidate_index": 0,
                }
            )
        sentence_index = 1
        for sentence in _split_sentences(source["text"]):
            fragments = _sentence_fragments(sentence)
            for fragment in fragments:
                phrase = _clean_phrase(fragment)
                if not phrase:
                    continue
                candidates.append(
                    {
                        "display": phrase,
                        "norm": _normalize_phrase(phrase),
                        "source_ids": [source["source_id"]],
                        "bucket": _bucket_for_text(phrase),
                        "summary": f"Ground `{phrase}` in `{source['source_id']}`: {sentence.strip()}",
                        "source_index": source_index,
                        "candidate_index": sentence_index,
                    }
                )
                sentence_index += 1
    return [candidate for candidate in candidates if candidate["norm"]]


def _select_concepts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        norm = candidate["norm"]
        if norm in merged:
            merged[norm]["source_ids"] = _ordered_unique(list(merged[norm]["source_ids"]) + list(candidate["source_ids"]))
            continue
        merged[norm] = dict(candidate)
    ranked = sorted(
        merged.values(),
        key=lambda item: (
            _BUCKET_ORDER.index(item["bucket"]) if item["bucket"] in _BUCKET_ORDER else len(_BUCKET_ORDER),
            item["source_index"],
            item["candidate_index"],
            -len(item["source_ids"]),
            len(item["display"]),
        ),
    )
    chosen: list[dict[str, Any]] = []
    for item in ranked:
        if len(chosen) >= 6:
            break
        if any(_phrase_too_similar(item["norm"], existing["norm"]) for existing in chosen):
            continue
        chosen.append(item)

    previous_id = ""
    concepts: list[dict[str, Any]] = []
    for idx, item in enumerate(chosen, start=1):
        concept_id = _slugged_id(item["display"], prefix=f"c{idx:02d}")
        concept = {
            "id": concept_id,
            "title": item["display"],
            "summary": item["summary"],
            "source_ids": list(item["source_ids"]),
            "objective_refs": [idx - 1],
            "bucket": item["bucket"],
            "prerequisites": [previous_id] if previous_id else [],
        }
        concepts.append(concept)
        previous_id = concept_id
    return concepts


def _fallback_concepts(bundle: list[dict[str, Any]]) -> list[dict[str, Any]]:
    concepts: list[dict[str, Any]] = []
    previous_id = ""
    for idx, source in enumerate(bundle[:4], start=1):
        title = _clean_title_phrase(source["title"]) or f"Source {idx}"
        concept_id = _slugged_id(title, prefix=f"c{idx:02d}")
        concepts.append(
            {
                "id": concept_id,
                "title": title,
                "summary": f"Use `{source['source_id']}` to teach `{title}`.",
                "source_ids": [source["source_id"]],
                "objective_refs": [idx - 1],
                "bucket": _bucket_for_text(title),
                "prerequisites": [previous_id] if previous_id else [],
            }
        )
        previous_id = concept_id
    return concepts


def _objective_from_concept(concept: dict[str, Any]) -> str:
    bucket = str(concept.get("bucket") or "").strip()
    verb = _OBJECTIVE_VERBS.get(bucket, "Explain")
    return f"{verb} how `{concept['title']}` fits into the end-to-end tutorial flow."


def _compose_module_title(concept_titles: list[str], *, index: int) -> str:
    if not concept_titles:
        return f"Module {index}"
    if len(concept_titles) == 1:
        return concept_titles[0]
    return f"{concept_titles[0]} and {concept_titles[1]}"


def _module_objectives(chunk: list[dict[str, Any]], objectives: list[str]) -> list[str]:
    by_ref = {idx: objective for idx, objective in enumerate(objectives)}
    out: list[str] = []
    for node in chunk:
        refs = node.get("objective_refs") or []
        for ref in refs:
            if isinstance(ref, int) and ref in by_ref and by_ref[ref] not in out:
                out.append(by_ref[ref])
    if out:
        return out[:3]
    return [f"Explain how `{node.get('title')}` supports the tutorial." for node in chunk[:3]]


def _running_example_steps(module_title: str, running: dict[str, Any], index: int) -> list[str]:
    mode = str(running.get("mode") or "").strip()
    label = str(running.get("label") or "").strip()
    if mode == "supported" and label:
        return [f"Advance `{label}` through the decisions introduced in module {index}: {module_title}."]
    return [f"Use the strongest source-backed example available to illustrate `{module_title}` without inventing new context."]


def _source_snippets_for_module(module: dict[str, Any], selected_sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    query = "\n".join(
        [str(module.get("title") or "")]
        + [str(item) for item in module.get("objectives") or []]
        + [str(item) for item in module.get("running_example_steps") or []]
    )
    snippets: list[dict[str, str]] = []
    for source in selected_sources:
        candidates: list[tuple[int, str, str]] = []
        query_tokens = set(tokenize(query))
        for pointer_record in source.get("pointers") or []:
            pointer_text = str(pointer_record.get("text") or "").strip()
            pointer = str(pointer_record.get("pointer") or "").strip()
            if not pointer_text or not pointer:
                continue
            candidate = _best_snippet(pointer_text, query)
            overlap = len(query_tokens.intersection(tokenize(candidate)))
            candidates.append((overlap, pointer, candidate))
        if candidates:
            _, pointer, snippet = max(candidates, key=lambda item: (item[0], len(item[2])))
        else:
            snippet = _best_snippet(source["text"], query)
            pointer = ""
        snippets.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "pointer": pointer,
                "snippet": snippet,
            }
        )
    return snippets


def _worked_example_candidates(module: dict[str, Any], snippets: list[dict[str, str]]) -> list[str]:
    steps = [str(step or "").strip() for step in module.get("running_example_steps") or [] if str(step or "").strip()]
    if steps:
        return steps
    if snippets:
        return [f"Rebuild the module story from: {snippets[0]['snippet']}"]
    return [f"Create a compact worked example for `{str(module.get('title') or '').strip()}` from the approved sources."]


def _pack_pitfalls(module: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    pitfalls = [str(item or "").strip() for item in coverage.get("gaps") or [] if str(item or "").strip()]
    if not pitfalls:
        pitfalls.append(f"Do not collapse `{str(module.get('title') or '').strip()}` into a generic summary; keep the explanation tied to the cited source snippets.")
    if module.get("running_example_steps"):
        pitfalls.append("Keep the worked example synchronized with the current module instead of jumping ahead to later material.")
    return pitfalls[:3]


def _render_why_it_matters(spec: dict[str, Any], module: dict[str, Any], pack: dict[str, Any]) -> str:
    objective = str(pack.get("objective") or (module.get("objectives") or [""])[0]).strip()
    outputs = ", ".join(module.get("outputs") or [])
    primary_goal = str(spec.get("goal") or "").strip()
    if primary_goal:
        return f"{objective} This matters because the tutorial goal is to {primary_goal.rstrip('.')}. The module output is: {outputs}"
    return f"{objective} The module output is: {outputs}"


def _render_key_idea(module: dict[str, Any], pack: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for snippet in pack.get("source_snippets") or []:
        if not isinstance(snippet, dict):
            continue
        title = str(snippet.get("title") or snippet.get("source_id") or "source").strip()
        body = str(snippet.get("snippet") or "").strip()
        if body:
            lines.append(f"- **{title}**: {body}")
    if not lines:
        lines.append(f"- Build the module around `{str(module.get('title') or '').strip()}` and keep the explanation scoped to the approved source set.")
    return lines


def _render_worked_example(pack: dict[str, Any]) -> list[str]:
    candidates = [str(item or "").strip() for item in pack.get("worked_example_candidates") or [] if str(item or "").strip()]
    if not candidates:
        return ["- Reconstruct the module example directly from the source notes."]
    return [f"- {item}" for item in candidates[:2]]


def _render_check_yourself(pack: dict[str, Any]) -> list[str]:
    exercise = dict(pack.get("exercise_seed") or {})
    prompt = str(exercise.get("prompt") or "").strip()
    expected = str(exercise.get("expected_output") or "").strip()
    checks = [str(item or "").strip() for item in exercise.get("verification_steps") or [] if str(item or "").strip()]
    lines: list[str] = []
    if prompt:
        lines.append(f"- Prompt: {prompt}")
    if expected:
        lines.append(f"- Expected output: {expected}")
    for check in checks[:3]:
        lines.append(f"- Verify: {check}")
    if not lines:
        lines.append("- Rephrase the core concept in your own words and verify it against the source notes.")
    return lines


def _render_source_notes(pack: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for snippet in pack.get("source_snippets") or []:
        if not isinstance(snippet, dict):
            continue
        source_id = str(snippet.get("source_id") or "").strip()
        title = str(snippet.get("title") or source_id).strip()
        pointer = str(snippet.get("pointer") or "").strip()
        label = f"`{source_id}` - {title}"
        if pointer:
            label += f" ({pointer})"
        lines.append(f"- {label}")
    if not lines:
        lines.append("- Keep this module tied to the approved source set.")
    return lines


def _read_workspace_path(workspace: Path, rel_or_abs: str) -> str:
    if not rel_or_abs:
        return ""
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = (workspace / path).resolve()
    if not path.exists():
        return ""
    if path.is_dir():
        texts: list[str] = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                texts.append(child.read_text(encoding="utf-8", errors="ignore"))
        return "\n\n".join(texts).strip()
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _sentence_fragments(sentence: str) -> list[str]:
    for pattern in _ACTION_PATTERNS:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if match:
            return _split_phrase_list(match.group(1))
    if "," in sentence:
        return _split_phrase_list(sentence)
    return []


def _split_phrase_list(text: str) -> list[str]:
    fragments = re.split(r",| and | / |;", text)
    return [fragment.strip() for fragment in fragments if fragment.strip()]


def _clean_title_phrase(title: str) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", title or "")]
    filtered = [token for token in tokens if token.lower() not in _GENERIC_TITLE_WORDS]
    return _clean_phrase(" ".join(filtered))


def _clean_phrase(text: str) -> str:
    raw = str(text or "").strip(" .,:;!?-")
    if not raw:
        return ""
    raw = re.sub(r"^\b(?:how to|when to|why|the|a|an)\b\s+", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\([^)]*\)", "", raw)
    tokens = [token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", raw)]
    while tokens and tokens[0].lower() in _PHRASE_FILLERS:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in (_PHRASE_FILLERS | _GENERIC_TITLE_WORDS):
        tokens.pop()
    if not tokens:
        return ""
    if len(tokens) > 5:
        tokens = tokens[:5]
    low_tokens = [token.lower() for token in tokens]
    if all(token in _GENERIC_TITLE_WORDS for token in low_tokens):
        return ""
    return " ".join(_smart_title_case(token) for token in tokens)


def _smart_title_case(token: str) -> str:
    if "-" in token:
        return "-".join(part.capitalize() for part in token.split("-"))
    if token.isupper():
        return token
    return token.capitalize()


def _normalize_phrase(text: str) -> str:
    return " ".join(tokenize(text))


def _bucket_for_text(text: str) -> str:
    words = set(tokenize(text))
    best_bucket = "foundation"
    best_score = -1
    for bucket in _BUCKET_ORDER:
        score = len(words & _BUCKET_KEYWORDS[bucket])
        if score > best_score:
            best_bucket = bucket
            best_score = score
    return best_bucket


def _phrase_too_similar(left: str, right: str) -> bool:
    left_set = set(left.split())
    right_set = set(right.split())
    if not left_set or not right_set:
        return False
    overlap = len(left_set & right_set)
    return overlap >= min(len(left_set), len(right_set))


def _slugged_id(text: str, *, prefix: str) -> str:
    slug = "-".join(tokenize(text)[:4]) or "concept"
    return f"{prefix}-{slug}"


def _ordered_unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _dedupe_edge_dicts(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        key = (str(edge.get("from") or "").strip(), str(edge.get("to") or "").strip())
        if not all(key) or key in seen:
            continue
        seen.add(key)
        out.append({"from": key[0], "to": key[1]})
    return out


def _match_score(query: str, source: dict[str, Any]) -> int:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0
    source_tokens = set(source.get("tokens") or [])
    overlap = len(query_tokens & source_tokens)
    title_overlap = len(query_tokens & set(tokenize(source.get("title") or "")))
    return overlap + (title_overlap * 2)


def _best_snippet(text: str, query: str) -> str:
    candidates = _split_sentences(text)
    if not candidates:
        return ""
    ranked = sorted(
        candidates,
        key=lambda sentence: (-_sentence_score(sentence, query), len(sentence)),
    )
    best = ranked[0].strip()
    return best if len(best) <= 240 else best[:240].rstrip()


def _sentence_score(sentence: str, query: str) -> int:
    return len(set(tokenize(sentence)) & set(tokenize(query)))
