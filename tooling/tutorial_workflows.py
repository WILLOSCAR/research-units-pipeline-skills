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

# Prepositions that must never begin OR end a concept title: a title that starts
# with one ("Into Passages Before Indexing") or ends with one ("Retriever Selects
# Candidate Passages From") is a mid-clause sentence fragment, not a teachable
# noun-phrase concept.
_PREPOSITIONS = {
    "into",
    "onto",
    "from",
    "before",
    "after",
    "over",
    "under",
    "between",
    "among",
    "amongst",
    "about",
    "against",
    "toward",
    "towards",
    "upon",
    "within",
    "across",
    "behind",
    "beyond",
    "per",
    "during",
    "than",
    "around",
    "via",
    "through",
    "without",
    "throughout",
    "beneath",
    "besides",
    "as",
    "at",
    "by",
    "but",
}

# Tokens trimmed from the START/END of a cleaned concept title. Includes
# prepositions so truncation can never re-expose a dangling function word.
_TRAILING_TRIM = _PHRASE_FILLERS | _GENERIC_TITLE_WORDS | _PREPOSITIONS

# Words that mark a candidate running-example phrase as an authors' RESULTS /
# QUALITY claim rather than a concrete artifact/task/system a reader could carry
# across modules. A "running example" must be a thing the reader works through
# (a dataset, task, system, scenario) — not "the effectiveness of our method" or
# "significant performance improvements". If the extracted phrase is dominated by
# these claim words (or names no concrete noun beyond them), it is rejected and
# the policy falls through to the honest mode: none.
_CLAIM_PHRASE_WORDS = frozenset(
    {
        "effectiveness",
        "efficiency",
        "efficacy",
        "performance",
        "improvement",
        "improvements",
        "improves",
        "accuracy",
        "ability",
        "capability",
        "capabilities",
        "superiority",
        "robustness",
        "stability",
        "scalability",
        "generalization",
        "generalizability",
        "usefulness",
        "benefit",
        "benefits",
        "advantage",
        "advantages",
        "significance",
        "significantly",
        "reliability",
        "reliable",
        "feasibility",
        "successful",
        "greater",
        "methodology",
        "our",
        "their",
        "its",
        "method",
        "methods",
        "approach",
        "approaches",
        "framework",
        "results",
        "showing",
        "showcasing",
        "yielding",
        "achieving",
    }
)

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

    # One learning objective per core concept. Capping below the concept count
    # (previously concepts[:5] for up to 6 concepts) left the last concept with no
    # stated objective in TUTORIAL_SPEC.md — a scope under-coverage the C2 review
    # surfaces. Concepts are already bounded (<=6 in _select_concepts), so this
    # stays a short, per-concept list.
    learning_objectives = [_objective_from_concept(concept, i) for i, concept in enumerate(concepts)]
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
    lines.extend([f"- {_reader_facing_objective(item)}" for item in spec.get("learning_objectives") or []])
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
    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        concept_ids = [str(node["id"]).strip() for node in chunk]
        concept_titles = [str(node.get("title") or "").strip() for node in chunk if str(node.get("title") or "").strip()]
        module_title = _compose_module_title(concept_titles, index=idx)
        module_objectives = _module_objectives(chunk, objectives)
        # One concrete-artifact output PER concept in the module, so a multi-concept
        # module does not leave its second (or later) concept unassessed — the
        # objectives cover every concept, so the outputs must too. Then a linkage
        # output: "reuse by the next module" only when a next module exists; the
        # FINAL module gets a synthesis line instead (there is no next module to
        # feed, and "reusable by the next module" on the last module reads as a
        # template artifact).
        outputs = [
            f"Produce a short explanation or checklist that makes `{title}` concrete in the tutorial flow."
            for title in (concept_titles or [module_title])
        ]
        if idx < total_chunks:
            outputs.append(
                f"Update the running example or module notes so `{module_title}` can be reused by the next module."
            )
        else:
            outputs.append(
                f"Synthesize the running example and module notes into a final summary that ties `{module_title}` back to the tutorial's overall goal."
            )
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
        # The third verify step must state a CONDITION the learner confirms, not
        # paste a fresh DO-THIS instruction. `running_example_steps` holds a
        # learner task ("Work through X on a concrete case: state the inputs,
        # apply the concept ..."); pasting it after "connects cleanly to the
        # running example step:" produced an incoherent verify item — a check
        # should be something you confirm, not a new multi-step task. Turn
        # it into a verification condition instead.
        steps = [str(s or "").strip() for s in module.get("running_example_steps") or [] if str(s or "").strip()]
        # A supported running example emits "Advance `<label>` through ..."; pull
        # the label so the check names it. Otherwise (mode: none) state a generic
        # concrete-case condition without a fabricated example.
        label = ""
        for s in steps:
            m = re.match(r"Advance `([^`]+)`", s)
            if m:
                label = m.group(1).strip()
                break
        if label:
            example_check = (
                f"Check that the result advances the running example `{label}`: it identifies "
                "the case inputs, applies the concept step by step, and validates the outcome "
                "against a cited source snippet."
            )
        else:
            example_check = (
                "Check that the result works the concept on a concrete case from the source "
                "notes: it identifies the case inputs, applies the concept step by step, and "
                "validates the outcome against a cited source snippet."
            )
        # The expected output must describe a LEARNER'S answer, not the module's
        # authoring output ("Produce a short explanation or checklist..." is a
        # directive to the tutorial author, not a model answer the learner checks
        # against). Frame it as the substance a correct learner response contains.
        expected = (
            f"A short learner explanation (or checklist) that correctly describes "
            f"`{title}`: what it is, how the module's concepts fit together, and how "
            f"it applies to the running example — traceable to the cited source notes."
        )
        module["exercises"] = [
            {
                "prompt": f"Use this module to explain or reproduce `{title}` on the running example.",
                "expected_output": expected,
                "verification_steps": [
                    f"Check that the result names the core concepts behind `{title}`.",
                    "Check that the result can be traced back to at least one source note or snippet.",
                    example_check,
                ],
            }
        ]
    return {"modules": modules}


def build_module_source_coverage(workspace: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    modules = [module for module in plan.get("modules") or [] if isinstance(module, dict)]
    if not modules:
        raise ValueError("module-source-coverage requires non-empty `outline/module_plan.yml`.")
    bundle = load_source_bundle(workspace)
    bundle_by_id = {source["source_id"]: source for source in bundle}
    records: list[dict[str, Any]] = []
    for module in modules:
        title = str(module.get("title") or "").strip()
        # Authoritative grounding: the sources that actually contributed this
        # module's concepts (from the module plan). Lexical matching against the
        # full bundle over-attributes — it adds any source that weakly matches
        # the generic module text even if it contributed no concept.
        concept_source_ids = _ordered_unique(
            [str(sid).strip() for sid in module.get("source_ids") or [] if str(sid).strip()]
        )
        query = "\n".join(
            [title]
            + [str(item) for item in module.get("objectives") or []]
            + [str(item) for item in module.get("running_example_steps") or []]
            + [str(item) for item in module.get("outputs") or []]
        )
        gaps: list[str] = []
        if concept_source_ids:
            selected = [bundle_by_id[sid] for sid in concept_source_ids if sid in bundle_by_id]
        else:
            # No concept-level grounding recorded: fall back to lexical match.
            ranked = sorted(
                ({"source": source, "score": _match_score(query, source)} for source in bundle),
                key=lambda item: (-item["score"], item["source"]["source_id"]),
            )
            selected = [item["source"] for item in ranked if item["score"] > 0][:2]
            if not selected and ranked:
                selected = [ranked[0]["source"]]
            gaps.append("No concept-level source grounding; attributed by lexical match — scope the module tightly to these notes.")
        if not selected:
            gaps.append("No source could be attributed to this module.")
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

    # Corpus-level reconciliation: a per-module audit cannot express a source that
    # contributed to ZERO modules — it simply never appears, so every module row
    # reads `gaps: []` and a C2 reviewer wrongly concludes the whole ingested set
    # is covered. Append one non-module reconciliation record that names every
    # ingested source and flags any that no module used, so an unused source is
    # explicit instead of silent (U070: "or explicitly records a gap").
    ingested_source_ids = _ordered_unique([str(source["source_id"]) for source in bundle])
    attributed_source_ids = _ordered_unique(
        [sid for record in records for sid in record.get("source_ids") or []]
    )
    attributed_set = set(attributed_source_ids)
    unused_source_ids = [sid for sid in ingested_source_ids if sid not in attributed_set]
    reconciliation_gaps: list[str] = []
    if unused_source_ids:
        reconciliation_gaps.append(
            "Ingested but unused by any module: "
            + ", ".join(f"`{sid}`" for sid in unused_source_ids)
            + ". Confirm these sources are intentionally out of scope, or widen a "
            "module to ground in them before approving the tutorial."
        )
    records.append(
        {
            "record_type": "corpus_reconciliation",
            "ingested_source_ids": ingested_source_ids,
            "attributed_source_ids": attributed_source_ids,
            "unused_source_ids": unused_source_ids,
            "gaps": reconciliation_gaps,
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
    # Frame each objective as a learner OUTCOME ("By the end you should be able to
    # explain X: ..."), not the raw "Explain X:" authoring imperative — the same
    # reframe applied to module "Why it matters" prose. Otherwise this list
    # reads as instructions to the tutorial's author, not to the learner.
    lines.extend([f"- {_reader_facing_objective(item)}" for item in spec.get("learning_objectives") or []])
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
    # Join the first two concept titles with a grammatical conjunction, not a bare
    # comma ("current recipes, exporter migration" reads as a comma-splice
    # mid-sentence). With no concepts, fall back to a generic prerequisite rather
    # than emit the broken "behind  is enough".
    titles = [str(c.get("title") or "").strip().lower() for c in concepts[:2] if str(c.get("title") or "").strip()]
    if not titles:
        return "No specific background is assumed; each concept is taught in sequence."
    focus = titles[0] if len(titles) == 1 else f"{titles[0]} and {titles[1]}"
    return f"Basic familiarity with the terms behind {focus} is enough; the rest is taught in sequence."


def _source_scope_entry(source: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    # A source's contributed concepts. Drop any concept whose title just repeats
    # the source's own title (the title-candidate concept) — the source title is
    # already printed as the label, so echoing it in "used for" adds nothing and
    # reads as a redundant repeat.
    source_title_norm = str(source.get("title") or "").strip().casefold()
    relevant = [
        concept["title"]
        for concept in concepts
        if source["source_id"] in (concept.get("source_ids") or [])
        and str(concept.get("title") or "").strip().casefold() != source_title_norm
    ]
    coverage = ", ".join(relevant[:3]) if relevant else "general context"
    return f"`{source['source_id']}` ({source['kind']}) - {source['title']} - used for {coverage}."


def _is_reusable_example_phrase(phrase: str) -> bool:
    """A running example must name a concrete artifact/task/system/scenario a
    reader can carry across modules — not an authors' results/quality claim.

    The `demonstrates?` extractor happily lifts the object of academic
    results-claim sentences ("demonstrate the effectiveness of our method,
    showing ...") and dresses it up as a running example. Those phrases lead
    with a claim word ("effectiveness", "our method"), are dominated by claim
    words, or carry a bare possessive residue ("DART's" -> "DART S"); reject
    them so the policy falls through to the honest mode: none.
    """
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", phrase)]
    content = [t for t in tokens if t not in _PHRASE_FILLERS and t not in _PREPOSITIONS]
    if not content:
        return False
    concrete = [t for t in content if t not in _CLAIM_PHRASE_WORDS and t != "s"]
    if not concrete:
        return False
    claim = [t for t in content if t in _CLAIM_PHRASE_WORDS or t == "s"]
    # Leads with a claim word (the object of the claim, not a named thing) ...
    if content[0] in _CLAIM_PHRASE_WORDS:
        return False
    # ... or claim words are at least as numerous as concrete nouns.
    if len(claim) >= len(concrete):
        return False
    return True


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
            if phrase and _is_reusable_example_phrase(phrase):
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
                    "kind": "title",
                }
            )
        # A source's own section headings are the author's concept
        # decomposition — far better teachable concepts than sentence fragments.
        # Prefer them: give them a low candidate_index so they rank first.
        heading_index = 0
        for heading in _source_headings(source["text"]):
            phrase = _heading_concept(heading)
            if not phrase or not _looks_like_concept(phrase):
                continue
            heading_index += 1
            context = _heading_context(source["text"], heading)
            summary = (
                f"`{phrase}` covers: {context}"
                if context
                else f"Teach `{phrase}` as a section of `{source['source_id']}`."
            )
            candidates.append(
                {
                    "display": phrase,
                    "norm": _normalize_phrase(phrase),
                    "source_ids": [source["source_id"]],
                    "bucket": _bucket_for_text(f"{phrase} {context}"),
                    "summary": summary,
                    "source_index": source_index,
                    "candidate_index": heading_index,
                    "kind": "heading",
                }
            )
        # The sentence-fragment fallback exists for sources with FEW/NO headings
        # (prose notes, FAQs). A heading-rich doc (e.g. a dense design/reference
        # doc with many `##` sections) already exposes the author's own concept
        # decomposition as headings; mining its prose sentences on top only adds
        # noisy clause fragments. Suppress the sentence fallback once enough clean
        # heading concepts exist.
        sentence_index = 1000
        sentences = [] if heading_index >= 4 else _split_sentences(source["text"])
        for sentence in sentences:
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
                        "kind": "sentence",
                    }
                )
                sentence_index += 1
        # A markdown comparison/reference TABLE lists its entities in the first
        # column — the author's own concept decomposition, like headings. Mine
        # each row's subject cell as a concept (ranked just after headings), so a
        # table-only source is not reduced to a garbled cross-cell fragment.
        table_index = 500
        for subject, row_context in _table_row_subjects(source["text"]):
            phrase = _clean_phrase(subject)
            if not phrase or not _looks_like_concept(subject):
                continue
            table_index += 1
            summary = (
                f"`{phrase}` is a row of `{source['source_id']}`: {row_context}"
                if row_context
                else f"Teach `{phrase}` as an entry of `{source['source_id']}`."
            )
            candidates.append(
                {
                    "display": phrase,
                    "norm": _normalize_phrase(phrase),
                    "source_ids": [source["source_id"]],
                    "bucket": _bucket_for_text(f"{phrase} {row_context}"),
                    "summary": summary,
                    "source_index": source_index,
                    "candidate_index": table_index,
                    "kind": "table",
                }
            )
        # A markdown BULLET LIST enumerates entities too, often as "Term:
        # definition" entries — the author's own concept decomposition. Mine each
        # bullet's teachable term (ranked just after headings/tables), so a
        # bullet-only source is not reduced to garbled mid-bullet fragments.
        list_index = 700
        for subject, item_context in _list_item_subjects(source["text"]):
            phrase = _clean_phrase(subject)
            if not phrase or not _looks_like_concept(subject):
                continue
            list_index += 1
            summary = (
                f"`{phrase}` is a list entry of `{source['source_id']}`: {item_context}"
                if item_context
                else f"Teach `{phrase}` as an entry of `{source['source_id']}`."
            )
            candidates.append(
                {
                    "display": phrase,
                    "norm": _normalize_phrase(phrase),
                    "source_ids": [source["source_id"]],
                    "bucket": _bucket_for_text(f"{phrase} {item_context}"),
                    "summary": summary,
                    "source_index": source_index,
                    "candidate_index": list_index,
                    "kind": "list",
                }
            )
    return [candidate for candidate in candidates if candidate["norm"]]


_BULLET_LINE = re.compile(r"^\s*[-*+]\s+(.*\S)\s*$")
# A numbered/ordered list line ("1. Export ...", "2) Build ..."). The marker is
# NOT a concept; its content is a step handled like a bullet.
_NUMBERED_LINE = re.compile(r"^\s*\(?\d{1,3}[.)]\s+(.*\S)\s*$")


def _list_line_body(raw_line: str) -> str | None:
    """The content of a bullet or numbered/ordered list line, marker stripped, or
    None when the line is not a list item."""
    for pattern in (_BULLET_LINE, _NUMBERED_LINE):
        match = pattern.match(raw_line)
        if match:
            return match.group(1).strip()
    return None


def _list_item_subjects(text: str) -> list[tuple[str, str]]:
    """Teachable subject + definition for each bullet / numbered step of a list.

    A list often reads as "Term: definition" entries — the author's own concept
    decomposition. For each item, the concept is the term before the first colon
    ("Pod: the smallest ..." -> "Pod"); when there is no colon, the leading phrase
    up to the first sentence terminator is used. Numbered-step markers ("1.", "2)")
    are stripped so the step content — not the bare number — becomes the concept.
    Returns (subject, definition_context).
    """

    items: list[tuple[str, str]] = []
    for raw_line in (text or "").splitlines():
        body = _list_line_body(raw_line)
        if body is None:
            continue
        # Skip a checkbox/task marker or empty body.
        body = re.sub(r"^\[[ xX]\]\s*", "", body).strip()
        if not body:
            continue
        colon = body.find(":")
        if 0 < colon <= 40:
            subject = body[:colon].strip()
            context = body[colon + 1 :].strip()
        else:
            # No leading "Term:" — reduce the item to its teachable concept: an
            # imperative step ("Export the trained checkpoint ...") yields its
            # object NP ("trained checkpoint") via _fragment_concept; otherwise the
            # first clause. Full item text is kept as the definition context.
            first_clause = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0].strip()
            subject = _fragment_concept(first_clause) or first_clause
            context = body
        if subject:
            items.append((subject, context))
    return items


def _table_row_subjects(text: str) -> list[tuple[str, str]]:
    """First-column subject + row context for each data row of a markdown table.

    A markdown table's first column is its list of entities (e.g. optimizer names
    in an "Optimizer | Update rule | ..." table). The header row and the
    `---|---` separator are skipped. Returns (subject_cell, rest_of_row_joined).
    """

    rows: list[tuple[str, str]] = []
    seen_header = False
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        # A table row starts and ends with a pipe and has >=2 cells.
        if not (line.startswith("|") and line.count("|") >= 2):
            seen_header = False
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Separator row (---|:--:|---): all cells are dashes/colons.
        if all(set(c) <= {"-", ":"} and c for c in cells):
            seen_header = True
            continue
        if not seen_header:
            # The first data-looking row before a separator is the header — skip it
            # but keep scanning; a separator will flip seen_header on for the body.
            # If no separator ever appears this is not a real table (left as prose).
            continue
        subject = cells[0] if cells else ""
        rest = " ".join(c for c in cells[1:] if c)
        if subject:
            rows.append((subject, rest))
    return rows


def _source_headings(text: str) -> list[str]:
    """Return a source's markdown section headings (## / ###), numbering stripped.

    These are the author's own concept decomposition. Skips the H1 title (kept
    separately as the title candidate) and drops generic scaffolding headings.
    """

    headings: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        match = re.match(r"^(#{2,4})\s+(.*\S)\s*$", line)
        if not match:
            continue
        heading = match.group(2).strip()
        # Strip leading section numbering ("1. ", "2.3 ", "Phase 1: ").
        heading = re.sub(r"^(?:phase\s+)?\d+(?:\.\d+)*[.:]?\s+", "", heading, flags=re.IGNORECASE)
        heading = heading.strip()
        if heading:
            headings.append(heading)
    return headings


# Leading question / discourse words that a heading may open with but that are
# not part of the teachable concept ("How the harness acts ...", "Why external
# ..."). Stripped before reducing a heading to its noun-phrase topic.
_HEADING_LEAD_STRIP = re.compile(
    r"(?i)^\s*(?:how|why|what|when|where|which|who|whether|understanding|introducing|"
    r"about|on|towards?|toward)\b[\s:,-]*"
)


def _heading_concept(heading: str) -> str:
    """Reduce a `##` section heading to a teachable noun-phrase concept.

    Handles the heading shapes the plain _clean_phrase mangles:
    - a comma / "and" LIST heading ("The Loop, the graph, and the Skills") keeps
      its enumerated items ("Loop, Graph and Skills") instead of a garbled bigram;
    - a QUESTION / discourse-led heading ("How the harness acts as referee",
      "Why external and why bounded") drops the lead word, then reduces a residual
      subject-verb clause to its subject noun-phrase via _fragment_concept.
    Falls back to _clean_phrase for a plain noun-phrase heading.
    """

    raw = str(heading or "").strip()
    # Comma/"and" enumeration heading -> keep the content items as one phrase.
    parts = [p.strip() for p in re.split(r",|\band\b|/|;", raw) if p.strip()]
    if len(parts) >= 2:
        items: list[str] = []
        for part in parts:
            cleaned = _clean_phrase(part)
            if cleaned and cleaned.lower() not in {i.lower() for i in items}:
                items.append(cleaned)
        if len(items) >= 2:
            joined = ", ".join(items[:-1]) + " and " + items[-1]
            # Cap length; a very long list still reads as its first items.
            return joined if len(joined.split()) <= 8 else ", ".join(items[:3])
    # Drop a leading question / discourse word, then reduce a residual clause.
    stripped = _HEADING_LEAD_STRIP.sub("", raw)
    if stripped != raw and stripped:
        reduced = _fragment_concept(stripped)
        if reduced:
            return _clean_phrase(reduced)
    return _clean_phrase(raw)


def _heading_context(text: str, heading: str) -> str:
    """First prose sentence under a given section heading (empty if none).

    Used to make a heading-concept's summary specific ("`X` covers ...")
    instead of a generic "Teach `X` as a section". Reuses _prose_blocks so the
    sentence is real prose (no table rows / code / markup).
    """
    lines = (text or "").splitlines()
    capturing = False
    body: list[str] = []
    heading_low = re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()
    for raw_line in lines:
        line = raw_line.strip()
        h = re.match(r"^(#{2,4})\s+(.*\S)\s*$", line)
        if h:
            htxt = re.sub(r"^(?:phase\s+)?\d+(?:\.\d+)*[.:]?\s+", "", h.group(2).strip(), flags=re.IGNORECASE)
            htxt_low = re.sub(r"[^a-z0-9]+", " ", htxt.lower()).strip()
            if capturing:
                break
            if htxt_low == heading_low:
                capturing = True
            continue
        if capturing:
            body.append(raw_line)
    block = "\n".join(body)
    for prose in _prose_blocks(block):
        for sentence in _split_sentences(prose):
            if _looks_like_prose(sentence):
                return _trim_snippet(sentence, cap=180)
    return ""


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


def _objective_from_concept(concept: dict[str, Any], index: int = 0) -> str:
    bucket = str(concept.get("bucket") or "").strip()
    verb = _OBJECTIVE_VERBS.get(bucket, "Explain")
    # Vary the action clause by position so consecutive objectives do not all read
    # as one repeated template ("Explain how X fits into the end-to-end flow").
    # Each concept then states a distinct learner performance.
    clause = _OBJECTIVE_CLAUSES[index % len(_OBJECTIVE_CLAUSES)]
    return f"{verb} `{concept['title']}`: {clause}"


# Distinct learner-performance clauses cycled across a tutorial's objectives so
# they read as different things to DO with each concept, not one template.
_OBJECTIVE_CLAUSES = (
    "how it fits into the end-to-end flow and why it comes at this point.",
    "what problem it solves and what it takes as input and produces as output.",
    "how it connects to the concept before it and sets up the one after.",
    "the key decision or trade-off it introduces for the reader.",
    "how you would recognize it working correctly versus failing in practice.",
    "what it does NOT cover, and where to go next when it is not enough.",
)


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
        # Resolve the concept's referenced learning objective; if none resolves
        # (e.g. the concept is beyond the spec's top-N objectives), synthesize
        # one from its title so EVERY module concept is covered — otherwise a
        # module can list a concept with no matching objective.
        resolved = False
        for ref in node.get("objective_refs") or []:
            if isinstance(ref, int) and ref in by_ref and by_ref[ref] not in out:
                out.append(by_ref[ref])
                resolved = True
        if not resolved:
            title = str(node.get("title") or "").strip()
            if title:
                synthesized = f"Explain how `{title}` fits into the end-to-end tutorial flow."
                if synthesized not in out:
                    out.append(synthesized)
    if out:
        return out
    return [f"Explain how `{node.get('title')}` supports the tutorial." for node in chunk[:3]]


def _running_example_steps(module_title: str, running: dict[str, Any], index: int) -> list[str]:
    mode = str(running.get("mode") or "").strip()
    label = str(running.get("label") or "").strip()
    if mode == "supported" and label:
        return [f"Advance `{label}` through the decisions introduced in module {index}: {module_title}."]
    # No single running example is supported across the source set. Emit a
    # READER-facing worked step (what the learner should do with this concept),
    # not a writer instruction. The old fallback printed "Use the strongest
    # source-backed example ... without inventing new context." verbatim into
    # the tutorial's Worked-example and Check-yourself sections — an instruction
    # to the generator, not guidance for the learner.
    return [
        f"Work through `{module_title}` on a concrete case from the source notes: "
        "state the inputs, apply the concept step by step, and check the result against the cited snippet."
    ]


def _source_snippets_for_module(module: dict[str, Any], selected_sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    # Build the snippet-selection query from the module's CONCEPT-bearing fields
    # (title, concepts, objectives) — NOT running_example_steps. Those steps are
    # boilerplate scaffolding ("Work through X on a concrete case from the source
    # notes: state the inputs, apply the concept step by step ...") whose generic
    # words ("work", "case", "notes", "inputs", "result") are IDENTICAL across
    # modules, so including them inflated a generic sentence to the top for every
    # module and collapsed distinct per-module snippets onto one shared quote.
    query = "\n".join(
        [str(module.get("title") or "")]
        + [str(item) for item in module.get("concepts") or []]
        + [str(item) for item in module.get("objectives") or []]
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


def _goal_topic(goal: str) -> str:
    """A clean learner-facing TOPIC phrase from the raw teaching goal.

    The raw goal is an authoring imperative ("Teach a new engineer the harness
    pipeline taxonomy (what each research Workflow is and when to use it) from the
    fixed source doc.") that must NOT be recited verbatim in reader prose. Strip the
    "teach <audience>" lead and the "from the (fixed) source ..." trailer, leaving
    the subject ("the harness pipeline taxonomy ...").
    """
    text = re.sub(r"\s+", " ", str(goal or "")).strip().rstrip(".")
    if not text:
        return ""
    # Drop a leading teaching-imperative + audience phrase up to the topic. The
    # audience is any short article+adjective+role phrase ("a new contributor",
    # "a scientist", "readers") — NOT just a fixed noun list, so an unusual role
    # ("contributor", "practitioner") does not leak the whole raw goal into reader
    # prose ("...understanding of Teach a new contributor the pipeline taxonomy").
    # Consume an optional "through"/"to" connector but KEEP the topic lead-in word
    # (the/how/about/why/what/when) that begins the subject.
    text = re.sub(
        r"(?i)^(?:teach|help|guide|show|walk|introduce|explain to)\b"
        r"(?:\s+(?:a|an|the))?"
        r"(?:\s+[a-z]+){0,3}?"
        r"(?:\s+(?:through|to))?"
        r"\s+(?=(?:the|how|about|why|what|when)\b)",
        "",
        text,
        count=1,
    )
    # Drop a trailing "from the (fixed) source doc/material/repo/video ...".
    text = re.sub(
        r"(?i)\s*(?:,\s*)?from the (?:fixed )?(?:source|repo|documentation|docs?|video|"
        r"material|paper)s?\b.*$",
        "",
        text,
    )
    return text.strip(" ,;:-")


def _reader_facing_objective(objective: str) -> str:
    """Turn an authoring objective ("Explain `X`: ...") into a reader outcome.

    The spec's objectives are phrased as authoring imperatives ("Explain `X`:
    how it fits ..."), which read as a directive to the tutorial author, not as
    motivation addressed to the learner. Reframe as a learner outcome ("By the
    end you should be able to explain `X`: ..."). Non-matching text is returned
    unchanged.
    """
    verbs = (
        "Explain", "Compare", "Describe", "Identify", "Apply", "Analyze",
        "Evaluate", "Distinguish", "Trace", "Assess", "Outline", "Summarize",
    )
    match = re.match(r"(?i)^\s*(%s)\b\s+(.*)$" % "|".join(verbs), str(objective or ""))
    if not match:
        return str(objective or "").strip()
    verb, rest = match.group(1).lower(), match.group(2).strip()
    return f"By the end you should be able to {verb} {rest}"


def _render_why_it_matters(spec: dict[str, Any], module: dict[str, Any], pack: dict[str, Any]) -> str:
    objective = str(pack.get("objective") or (module.get("objectives") or [""])[0]).strip()
    outcome = _reader_facing_objective(objective)
    topic = _goal_topic(str(spec.get("goal") or ""))
    title = str(module.get("title") or "").strip()
    # Learner-facing motivation: state the learner OUTCOME (not the raw authoring
    # "Explain X:" imperative), then tie this module to the tutorial's TOPIC (not
    # the raw authoring goal) and to the reading flow. Do NOT recite the raw goal
    # verbatim or dump the internal module-output list — those are planner artifacts.
    if topic and title:
        return (
            f"{outcome} Working through `{title}` here builds your understanding of "
            f"{topic} and sets up the module that follows."
        )
    if topic:
        return f"{outcome} This module builds your understanding of {topic}."
    return outcome


def _render_key_idea(module: dict[str, Any], pack: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for snippet in pack.get("source_snippets") or []:
        if not isinstance(snippet, dict):
            continue
        title = str(snippet.get("title") or snippet.get("source_id") or "source").strip()
        body = str(snippet.get("snippet") or "").strip()
        if body:
            # The stored snippet is a contiguous source substring (grounding
            # contract) and can be clipped without its terminal period, so the
            # rendered Key-idea line reads as a sentence that just stops.
            # Add a terminal period for DISPLAY only when the body is sentence-like
            # and lacks end punctuation; the stored snippet is untouched, so the
            # grounding check (which compares snippet['snippet']) is unaffected.
            if body[-1] not in ".!?:;" and not body.endswith("`"):
                body = body + "."
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
    # Drop markdown heading lines, TABLE rows, and BULLET-list lines first: none
    # has a sentence terminator, so collapsing whitespace would glue a heading to
    # the next body sentence, fuse a table into one pseudo-sentence, or merge all
    # bullets into one run mined into garbled mid-item fragments. Headings feed
    # heading candidates; table rows feed table-subject candidates; bullets feed
    # list-item candidates (see _table_row_subjects / _list_item_subjects).
    body_lines = [
        line
        for line in (text or "").splitlines()
        if not re.match(r"^\s*#{1,6}\s", line)
        and not (line.strip().startswith("|") and line.strip().count("|") >= 2)
        and _list_line_body(line) is None
    ]
    cleaned = re.sub(r"\s+", " ", "\n".join(body_lines)).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _sentence_fragments(sentence: str) -> list[str]:
    for pattern in _ACTION_PATTERNS:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if not match:
            continue
        # Object-noun misfire: some action words ("documents", "shows") are also
        # common nouns. If a finite verb already precedes the matched word, the
        # word is this clause's OBJECT ("Chunking splits documents into ..."),
        # not its governing verb ("The repo documents X, Y, Z") — skip the match
        # rather than mine the post-object tail into a fragment concept.
        pre = sentence[: match.start(1)]
        pre_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", pre)
        if len(pre_tokens) >= 2 and _finite_verb_index(pre_tokens[:-1]) != -1:
            continue
        # The object list AFTER an action verb ("documents X, Y, Z") is a genuine
        # enumeration of concepts; keep it as-is.
        return _split_phrase_list(match.group(1))
    if "," in sentence:
        # No governing action verb: splitting the WHOLE sentence on commas slices
        # subject + verb clauses ("correctable while the Goal", "human Decisions
        # change") into fake concepts. Reduce each fragment to its concept form:
        # for an SVO clause keep just the SUBJECT noun-phrase ("A retriever selects
        # candidate passages" -> "A retriever"), never the verb clause.
        results: list[str] = []
        for fragment in _split_phrase_list(sentence):
            reduced = _fragment_concept(fragment)
            if reduced:
                results.append(reduced)
        return results
    # A single comma-free declarative sentence ("Graph indexes connect each vector
    # to ...") still has a teachable SUBJECT concept ("Graph indexes"). Extract it
    # so a no-heading prose source is not silently reduced to near-zero coverage.
    reduced = _fragment_concept(sentence)
    return [reduced] if reduced else []


def _fragment_concept(fragment: str) -> str | None:
    """Reduce one clause/fragment to a teachable concept phrase, or None.

    An SVO clause is reduced to its SUBJECT noun-phrase ("Graph indexes connect
    each vector ..." -> "Graph indexes"); an IMPERATIVE clause is reduced to its
    OBJECT noun-phrase ("Configure the time-to-live ..." -> "the time-to-live");
    a plain noun phrase is kept as-is; a fragment that is not concept-like
    (leading connective, no subject) is dropped.
    """

    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", fragment or "")
    if not tokens:
        return None
    # Imperative clause ("Configure the time-to-live ...", "Measure the cache hit
    # rate ..."): the teachable concept is the verb's OBJECT noun-phrase, taken up
    # to the first clause boundary (a subordinator / preposition / conjunction).
    if tokens[0].lower() in _IMPERATIVE_VERBS:
        return _imperative_object(tokens)
    # A fragment that LEADS with a 3rd-person-singular finite verb ("names the
    # concepts", "does not repeat that glossary", "maps those terms") is a
    # subjectless predicate clause, not a concept — it commonly arises when a
    # compound sentence is split on ";"/" and ". Reject it. Only the unambiguous
    # "-s" verb form triggers this (NOT a base-form verb like "approximate" that
    # is also an adjective/modifier leading a real noun phrase).
    if _is_present_verb(tokens[0].lower()):
        return None
    verb_index = _finite_verb_index(tokens)
    if verb_index > 0:
        subject = " ".join(tokens[:verb_index])
        # Salvage the subject NP only when it is itself a clean concept; otherwise
        # drop the clause (a verb clause is not a concept name).
        return subject if _looks_like_concept(subject) else None
    if verb_index == 0:
        # Leads with a verb ("connect each vector ...") — a predicate, no subject.
        return None
    # No unambiguous finite verb. Look for an ambiguous verb+noun ("map", "act")
    # immediately followed by a preposition ("map to", "act as"): that is a
    # verb+complement, so tokens before it are the subject noun-phrase.
    for index in range(1, len(tokens) - 1):
        if (
            tokens[index].lower() in _AMBIGUOUS_VERBS
            and tokens[index + 1].lower() in _COMPLEMENT_MARKERS
        ):
            subject = " ".join(tokens[:index])
            return subject if _looks_like_concept(subject) else None
    # Otherwise keep only if it already reads like a concept.
    return fragment if _looks_like_concept(fragment) else None


# Instructional verbs that head an IMPERATIVE tutorial sentence ("Configure the
# TTL", "Measure the hit rate", "Avoid caching ..."). The teachable concept is
# the verb's OBJECT noun-phrase, not the instruction itself.
_IMPERATIVE_VERBS = {
    "mark", "reuse", "avoid", "configure", "measure", "set", "use", "add",
    "define", "compute", "compare", "choose", "select", "pick", "enable",
    "disable", "apply", "prefer", "keep", "ensure", "check", "verify",
    "monitor", "track", "record", "store", "load", "build", "create", "run",
    "split", "batch", "tune", "adjust", "increase", "decrease", "limit",
    "cache", "index", "train", "evaluate", "validate", "test", "review",
    "export", "import", "deploy", "promote", "launch", "package", "publish",
    "release", "install", "provision", "roll", "collect", "annotate",
    "normalize", "preprocess", "fine-tune", "benchmark", "profile", "instrument",
}

# Words that end an imperative's object noun-phrase: a clause boundary follows
# ("Configure the time-to-live SO THAT ...", "Measure the cache hit rate BEFORE
# ..."). Object collection stops at the first of these.
_OBJECT_BOUNDARY = _PREPOSITIONS | {
    "so", "that", "which", "when", "where", "while", "because", "if", "and",
    "or", "but", "then", "to", "as", "on", "in", "of", "with", "for", "at",
    "once", "until", "unless", "whether", "after", "before",
}

# Verb particles/prepositions that can immediately follow an imperative verb
# before its object ("roll OUT to a canary", "set UP the cluster"). Skipped along
# with articles so the object noun-phrase is not mistaken for the particle.
_LEADING_PARTICLES = {
    "out", "up", "down", "in", "on", "off", "over", "through", "to", "into",
    "onto", "across", "back", "away",
}


def _imperative_object(tokens: list[str]) -> str | None:
    """Object noun-phrase of an imperative clause, or None.

    Skips the leading imperative verb, any verb particle/preposition ("roll OUT
    to ..."), and articles, then collects the object head up to the first clause
    boundary: "Configure the time-to-live so that ..." -> "time-to-live";
    "Roll out to a canary that ..." -> "canary". Returns None when no substantive
    object survives.
    """

    index = 1  # skip the imperative verb itself
    while index < len(tokens) and tokens[index].lower() in (_PHRASE_FILLERS | _LEADING_PARTICLES):
        index += 1
    object_tokens: list[str] = []
    while index < len(tokens) and tokens[index].lower() not in _OBJECT_BOUNDARY:
        object_tokens.append(tokens[index])
        index += 1
    if not object_tokens:
        return None
    phrase = " ".join(object_tokens)
    return phrase if _looks_like_concept(phrase) else None


# Common technical plural nouns that end in "s" but are NOT finite verbs. Without
# this stoplist the verb detector would split a noun phrase ("dense bi-encoder
# embeddings") at its trailing plural head.
_PLURAL_NOUN_STOP = {
    "passages", "documents", "candidates", "encoders", "embeddings", "chunks",
    "notes", "tokens", "pairs", "scores", "boundaries", "models", "datasets",
    "methods", "features", "results", "metrics", "systems", "networks", "layers",
    "weights", "gradients", "samples", "labels", "classes", "outputs", "inputs",
    "downsides", "drawbacks", "baselines", "benchmarks", "seeds", "values",
    "parameters", "representations", "applications", "tasks", "settings",
    "trees", "rows", "columns", "learners", "trajectories", "policies", "nodes",
    "edges", "clusters", "sources", "readers", "authors", "queries", "answers",
    "passwords", "vectors", "matrices", "epochs", "batches", "signals",
    "indexes", "indices", "filters", "matches", "codes", "cells", "neighbors",
    "predicates", "keywords", "similarities", "points", "corpora", "graphs",
    "queries", "databases", "notes", "steps", "stages", "phases", "modules",
    "concepts", "objectives", "exercises", "examples", "sections", "headings",
}

# Noun-forming "-s" suffixes ("analysis", "faithfulness", "corpus", "physics")
# that must not be mistaken for a 3rd-person-singular present verb.
_VERB_S_EXCLUDE_SUFFIX = ("ss", "us", "ous", "is", "sis", "xis", "ics", "ness", "ess")

# High-frequency BASE-FORM verbs common as the main verb of a technical
# declarative sentence with a plural/mass subject ("Graph indexes CONNECT ...",
# "Embeddings ENCODE ..."). Used to find the subject/predicate boundary so the
# subject noun-phrase can be salvaged as a concept. Tokens that are just as often
# a noun ("search", "map", "index", "trade", "scan", "cluster", "sample") are
# deliberately EXCLUDED: they would fire on the subject head noun itself.
_BASE_FORM_VERBS = {
    "encode", "decode", "connect", "partition", "compress", "restrict",
    "combine", "trade", "walk", "store", "produce", "generate", "require",
    "enable", "support", "allow", "reduce", "improve", "compute", "measure",
    "apply", "define", "describe", "represent", "contain", "include", "predict",
    "capture", "provide", "compare", "optimize", "estimate", "transform",
    "retrieve", "summarize", "classify", "detect", "mitigate", "leverage",
    "aggregate", "propagate", "approximate", "quantize", "normalize",
    "concatenate", "encode", "embed", "traverse", "prune",
}

# Verbs that are ALSO common nouns ("a feature map", "an act", "a search").
# They must NOT be treated as finite verbs in general (they routinely head a
# subject noun-phrase), but when one appears mid-fragment FOLLOWED BY A
# PREPOSITION ("documents map TO ...", "trees act AS ...") the structure is
# unambiguously verb+complement, so the tokens before it are the subject NP.
_AMBIGUOUS_VERBS = {
    "map", "maps", "act", "acts", "search", "searches", "index", "indexes",
    "scale", "scales", "trade", "trades", "cluster", "clusters", "sample",
    "samples", "score", "scores", "point", "points", "scan", "scans",
    "return", "returns", "run", "runs", "fit", "fits", "form", "forms",
}

# Words that mark the start of a verb's complement ("map TO", "act AS",
# "conditions ON"): if one directly follows an ambiguous verb, that verb is
# functioning as a predicate, so the tokens before it are the subject NP. Wider
# than _PREPOSITIONS because it includes "to"/"as", which are fillers/conjunctions
# elsewhere but are complement markers here.
_COMPLEMENT_MARKERS = _PREPOSITIONS | {"to", "as", "on", "in", "of", "with", "for"}


def _is_present_verb(token: str) -> bool:
    """True when a token looks like a 3rd-person-singular present verb ("selects",
    "conditions", "separates") rather than a plural/derived noun."""

    low = token.lower()
    if len(low) < 4 or not low.endswith("s") or low.endswith("'s"):
        return False
    if any(low.endswith(suffix) for suffix in _VERB_S_EXCLUDE_SUFFIX):
        return False
    return low not in _PLURAL_NOUN_STOP


def _is_finite_verb(token: str) -> bool:
    """True when a token is a finite present verb: a 3rd-person-singular ``-s``
    verb, or an unambiguous base-form technical verb ("connect", "encode")."""

    low = token.lower()
    return _is_present_verb(low) or low in _BASE_FORM_VERBS


def _finite_verb_index(tokens: list[str]) -> int:
    """Index of the first finite present verb that has a substantive subject token
    before it, else -1.

    Used to split an SVO clause into its subject noun-phrase: "A retriever selects
    candidate passages" -> subject "A retriever"; "Graph indexes connect each
    vector ..." -> "Graph indexes". A leading plural-noun subject ("Cross-encoders
    ...") is not treated as a verb because nothing substantive precedes it.
    """

    seen_subject = False
    for index, token in enumerate(tokens):
        low = token.lower()
        if seen_subject and _is_finite_verb(low):
            return index
        if (
            low not in _PHRASE_FILLERS
            and low not in _PREPOSITIONS
            and not _is_finite_verb(low)
        ):
            seen_subject = True
    return -1


# Finite/relational verbs and connectives whose presence marks a fragment as a
# CLAUSE ("the unit of trust is the Loop", "human Decisions change") rather than
# a teachable concept phrase. Concept phrases are noun-led ("dataset schema",
# "training configuration"); clauses assert something and are not reusable names.
_CLAUSE_MARKERS = {
    "is", "are", "was", "were", "be", "been", "being",
    "keeps", "keep", "kept", "change", "changes", "changed", "changing",
    "describe", "describes", "described", "report", "reports", "reported",
    "has", "have", "had", "do", "does", "did", "make", "makes", "made",
    "supersedes", "supersede", "superseded", "letting", "grade", "grades",
    "proves", "prove", "proved", "claims", "claim", "claimed", "produced",
    "while", "because", "although", "though", "unless", "whereas", "so",
    "not", "they", "it", "we", "you", "he", "she",
}

# Words that, when they LEAD a fragment, mark it as a trailing/subordinate
# clause rather than a concept name (relative pronouns, conjunctions, and
# clause-heading prepositions).
_LEADING_CONNECTIVES = {
    "and", "or", "but", "so", "while", "because", "although", "though",
    "whereas", "if", "when", "which", "who", "whom", "whose", "that",
    "without", "with", "via", "through", "despite", "unless", "until",
}

# Bare ordinal / list-enumerator words that are stray inline list markers, not
# teachable concepts (they leak from fragments like "avoid `first: ...`,
# `second: ...`, `third: ...`").
_ORDINAL_ENUMERATORS = {
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
    "ninth", "tenth", "next", "last", "final", "step", "point", "item", "part",
    "one", "two", "three", "four", "five",
}


def _looks_like_concept(fragment: str) -> bool:
    """True when a sentence-derived fragment reads like a concept, not a clause.

    Rejects fragments that begin with a connective/subordinator/relative
    pronoun ("and ...", "while ...", "which ..."), that contain a
    finite/relational verb or clause marker ("... is the Loop", "... Decisions
    change"), that are a single bare adverb ("reproducibly"), or that carry no
    substantive (non-stopword) noun token. Enumeration items after an action
    verb bypass this guard entirely (see `_sentence_fragments`).
    """

    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", fragment or "")]
    if not tokens:
        return False
    # A leading connective/subordinator/relative pronoun means this is a
    # trailing or subordinate clause, not a name.
    if tokens[0] in _LEADING_CONNECTIVES:
        return False
    # Any clause marker (finite/relational verb, subordinator, pronoun) makes it
    # a clause, not a name.
    if any(token in _CLAUSE_MARKERS for token in tokens):
        return False
    # A single bare adverb ("reproducibly", "correctly") is not a concept.
    if len(tokens) == 1 and tokens[0].endswith("ly"):
        return False
    # A lone ordinal / list-enumerator word ("first", "second", "third", "step",
    # "point") is a stray inline list marker, not a teachable concept. These leak
    # from sentence fragments like "avoid `first: ...`, `second: ...`".
    if len(tokens) == 1 and (
        tokens[0] in _ORDINAL_ENUMERATORS or re.fullmatch(r"\d+(st|nd|rd|th)", tokens[0])
    ):
        return False
    # Must carry at least one substantive token (a candidate noun): not a
    # stopword, not a generic title word.
    substantive = [
        token
        for token in tokens
        if token not in _PHRASE_FILLERS and token not in _GENERIC_TITLE_WORDS
    ]
    return bool(substantive)


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
    while tokens and tokens[0].lower() in (_PHRASE_FILLERS | _PREPOSITIONS):
        tokens.pop(0)
    while tokens and tokens[-1].lower() in _TRAILING_TRIM:
        tokens.pop()
    if not tokens:
        return ""
    if len(tokens) > 5:
        tokens = tokens[:5]
        # Truncation can re-expose a dangling function word ("... Passages From"):
        # re-trim the (now) trailing/leading fillers and prepositions.
        while tokens and tokens[-1].lower() in _TRAILING_TRIM:
            tokens.pop()
        while tokens and tokens[0].lower() in (_PHRASE_FILLERS | _PREPOSITIONS):
            tokens.pop(0)
    if not tokens:
        return ""
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


def _trim_snippet(best: str, *, cap: int = 240) -> str:
    """Trim a snippet to <= cap chars, ending on a complete-enough phrase.

    The old `best[:cap]` cut mid-word ("... and `workflow"); a later fix stopped
    at a word boundary but still left mid-sentence fragments dangling on a
    conjunction ("... produced correctly, reproducibly, and"). The snippet must
    stay a contiguous substring of the raw provenance (the context-pack grounding
    check compares whitespace-normalized substrings) and carry NO ellipsis, so we
    only ever DROP trailing tokens: prefer to end at the last sentence terminator
    within the cap; else cut at the last whole word and drop a trailing dangling
    conjunction/connector so the phrase does not end on "and"/"to"/"the".
    """
    best = best.strip()
    if len(best) <= cap:
        trimmed = best
    else:
        window = best[:cap]
        # Prefer ending at a real sentence terminator within the cap (a complete
        # sentence is still a contiguous prefix substring of the provenance).
        terminators = list(re.finditer(r"[.!?](?=\s|$)", window))
        if terminators and terminators[-1].end() >= int(cap * 0.5):
            trimmed = window[: terminators[-1].end()]
        else:
            cut = window.rfind(" ")
            trimmed = window[:cut] if cut > 0 else window
    trimmed = trimmed.rstrip()
    # Drop a dangling unmatched backtick span ("`workflow" with no closing `).
    if trimmed.count("`") % 2 == 1:
        trimmed = trimmed[: trimmed.rfind("`")].rstrip()
    # Drop a trailing opening bracket / stray connector punctuation.
    trimmed = trimmed.rstrip(" ,;:-([{")
    # Drop a trailing dangling conjunction/connector word so a mid-sentence cut
    # does not end on "and"/"or"/"to"/"the" (only when the snippet was truncated,
    # i.e. it does not already end on a sentence terminator).
    if not trimmed.endswith((".", "!", "?")):
        trimmed = re.sub(
            r"(?i)[\s,;:]+(?:and|or|but|nor|yet|so|because|which|while|that|with|"
            r"to|of|the|a|an|for|in|on|at|by|from|into|than|as)$",
            "",
            trimmed,
        ).rstrip(" ,;:-")
    return trimmed


def _best_snippet(text: str, query: str) -> str:
    # Prefer a readable prose teaching sentence (no table rows / code / markup).
    # Sentence-split WITHIN each contiguous prose block so no candidate bridges
    # a removed block — that keeps every candidate a contiguous substring of the
    # raw provenance (the grounding check requires it).
    prose: list[str] = []
    for block in _prose_blocks(text):
        prose.extend(
            sentence for sentence in _split_sentences(block) if _looks_like_prose(sentence)
        )
    if prose:
        return _strip_leading_connective(_trim_snippet(_rank_snippet_candidates(prose, query)))
    # Graceful fallback: no prose sentence available for this source. Keep the
    # prior behavior (best raw sentence) so the module still gets a non-empty,
    # source-backed snippet rather than dropping to empty (a hard contract
    # failure at module-source-coverage / tutorial-context-pack). _split_sentences
    # drops table rows, so for an all-table source fall back to raw non-empty
    # lines (a table row is still source-backed grounding of last resort).
    candidates = _split_sentences(text)
    if not candidates:
        candidates = [
            line.strip()
            for line in (text or "").splitlines()
            if line.strip() and not re.match(r"^\s*#{1,6}\s", line) and set(line.strip()) - set("|-: ")
        ]
    if not candidates:
        return ""
    return _strip_leading_connective(_trim_snippet(_rank_snippet_candidates(candidates, query)))


def _rank_snippet_candidates(candidates: list[str], query: str) -> str:
    """Pick the best snippet, preferring self-contained sentences.

    A sentence that opens with a dangling connective/pronoun ("So this ...",
    "Its ...") is not self-contained: a learner reading the snippet alone cannot
    resolve the opener, so it is a poor teaching quote even when it packs one more
    query token than a coherent alternative. We model that as a small relevance
    PENALTY on a dangling opener rather than a hard reorder — so a dangling
    sentence still wins when it is clearly more on-topic than any alternative
    (a source whose only relevant sentence opens with a pronoun still yields a
    snippet), but a near-equally-relevant self-contained sentence overtakes it.
    Ranking only REORDERS candidates — never rewrites them — so each emitted
    snippet stays a contiguous substring of the raw provenance (the grounding
    check requires it) and stays driven by per-module relevance.
    """

    def effective_score(sentence: str) -> int:
        score = _sentence_score(sentence, query)
        if not _snippet_is_self_contained(sentence):
            score -= 1
        return score

    return sorted(
        candidates,
        key=lambda sentence: (
            -effective_score(sentence),
            # at equal effective score, a self-contained sentence beats a dangling
            # one before falling back to the shorter-sentence tiebreak
            not _snippet_is_self_contained(sentence),
            len(sentence),
        ),
    )[0]


def _prose_blocks(text: str) -> list[str]:
    """Return contiguous prose blocks with non-prose markdown removed.

    The Key-idea snippet must be a readable teaching sentence, not a raw table
    row or a code/mermaid block (table rows pack many topic tokens onto one
    line, so token-overlap scoring would otherwise always pick them). Each
    removed line (fenced code, table row, heading) BREAKS the current block, so
    a later sentence-split never bridges a gap — every emitted sentence stays a
    contiguous substring of the raw provenance, which the grounding check needs.
    """

    blocks: list[str] = []
    current: list[str] = []
    in_fence = False

    def flush() -> None:
        if current:
            blocks.append("\n".join(current))
            current.clear()

    for raw_line in (text or "").splitlines():
        stripped = raw_line.strip()
        # Toggle fenced code / mermaid / text blocks and drop their contents.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        # Drop markdown table rows and their separator lines.
        if stripped.startswith("|") or re.fullmatch(r"[\s|:-]+", stripped):
            flush()
            continue
        # Drop heading lines (their text is captured separately as concepts).
        if stripped.startswith("#"):
            flush()
            continue
        # A blank line also ends the current block.
        if not stripped:
            flush()
            continue
        # Keep prose/list/quote lines verbatim: the grounding check matches
        # snippets against the raw provenance, so leading markers are preserved.
        current.append(raw_line)
    flush()
    return blocks


def _looks_like_prose(sentence: str) -> bool:
    """True when a candidate reads like a teaching sentence, not table/markup."""

    text = str(sentence or "").strip()
    if not text:
        return False
    # Residual table cells or heavy pipe use → not prose.
    if "|" in text:
        return False
    # Require enough alphabetic word tokens to be a real sentence.
    words = re.findall(r"[A-Za-z]{2,}", text)
    return len(words) >= 5


def _sentence_score(sentence: str, query: str) -> int:
    return len(set(tokenize(sentence)) & set(tokenize(query)))


# Openers that make a snippet non-self-contained. Two kinds, handled differently:
#  - STRIPPABLE discourse connectives ("So this catalog ...", "Therefore ..."):
#    the leading word only signals missing prior reasoning; dropping it leaves a
#    clean, still-grounded sentence ("This catalog ..."), so we strip it.
#  - Bare pronouns / demonstrative subjects ("Its exporter target ...", "They
#    ...") have no antecedent inside the quote and cannot be repaired by
#    stripping, so a sentence opening with one is deprioritized in ranking.
# Ranking only REORDERS candidates and stripping only removes a leading connective
# — both keep the snippet a contiguous substring of the raw provenance (modulo
# case/whitespace, which the grounding check normalizes away).
_STRIPPABLE_CONNECTIVES = {
    "so", "thus", "therefore", "hence", "then", "and", "but", "or", "yet",
    "however", "moreover", "furthermore", "besides", "also", "still", "instead",
    "otherwise", "consequently", "accordingly", "meanwhile", "nonetheless",
    "nevertheless",
}
_PRONOUN_OPENERS = {
    "it", "its", "they", "them", "their", "this", "these", "that", "those",
    "he", "she", "his", "her", "him", "such",
}


def _first_word(sentence: str) -> str:
    match = re.search(r"[A-Za-z][A-Za-z'-]*", str(sentence or ""))
    return match.group(0).lower() if match else ""


def _strip_leading_connective(sentence: str) -> str:
    """Drop a single leading discourse connective ("So this ..." -> "this ...").

    Only strips a pure connective (never a pronoun, which carries meaning). The
    remainder stays a contiguous substring of the source, and the first surviving
    letter is upper-cased for a clean reader-facing opener.
    """
    text = str(sentence or "").strip()
    match = re.match(r"([A-Za-z][A-Za-z'-]*)\b[\s,]*(.*)", text, flags=re.DOTALL)
    if not match:
        return text
    lead, rest = match.group(1), match.group(2)
    if lead.lower() in _STRIPPABLE_CONNECTIVES and rest:
        return rest[:1].upper() + rest[1:]
    return text


def _snippet_is_self_contained(sentence: str) -> bool:
    """False when a snippet opens with an UNRESOLVABLE pronoun/demonstrative.

    Leading discourse connectives are handled by stripping (see
    `_strip_leading_connective`), so only a bare pronoun opener — whose antecedent
    is absent from the quote — marks a sentence as not self-contained here, used
    to rank it below an equally-relevant alternative.
    """
    return _first_word(sentence) not in _PRONOUN_OPENERS
