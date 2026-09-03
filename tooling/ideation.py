from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable

from tooling.common import (
    atomic_write_text,
    ensure_dir,
    load_workspace_pipeline_spec,
    pipeline_overridable_query_fields,
    read_jsonl,
)


DEFAULT_IDEA_RUBRIC: list[tuple[str, float, str]] = [
    ("discussion_worthiness", 0.24, "is this direction worth a serious PI/PhD discussion right now?"),
    ("academic_value", 0.22, "could it open a meaningful paper/thesis-worthy research angle?"),
    ("evidence_grounding", 0.18, "can we point to concrete literature tensions rather than pure speculation?"),
    ("direction_distinctness", 0.16, "is it genuinely different from neighboring directions, not just a wording variant?"),
    ("first_probe_clarity", 0.10, "is there a plausible low-cost first probe that would teach us something?"),
    ("thesis_potential", 0.10, "does it plausibly grow beyond a one-off note into a stronger line of work?"),
]

STOPWORDS = {
    "a", "an", "and", "the", "of", "to", "for", "in", "on", "with", "via", "by", "from", "or",
    "work", "works", "study", "studies", "survey", "review", "benchmarks", "benchmark", "evaluation",
    "agents", "agent", "model", "models", "llm", "large", "language", "using", "based",
}

CLUSTER_AXIS_HINTS: list[tuple[list[str], list[str], str, str]] = [
    (["agent loop", "action"], ["observability granularity", "action-space design", "tool/environment boundary"], "mechanism", "Could sharpen how we think about the basic agent loop rather than adding yet another full stack."),
    (["tool", "orchestration", "interface"], ["tool routing", "permission model", "API reliability assumptions"], "systems", "Could clarify whether interface design is the real bottleneck behind seemingly agent-level gains."),
    (["planning", "reasoning"], ["search depth", "verification loop", "partial-observability handling"], "mechanism", "Could turn vague talk about reasoning quality into a sharper research question about what actually drives robust planning."),
    (["memory", "retrieval", "rag"], ["retrieval policy", "state summarization cadence", "memory horizon"], "mechanism", "Could reveal when memory is a genuine capability lever versus a reporting convenience."),
    (["self-improvement", "adaptation"], ["feedback type", "adaptation horizon", "evaluation signal quality"], "adaptation", "Could distinguish genuine improvement from evaluation-sensitive self-optimization."),
    (["multi-agent", "coordination"], ["role specialization", "communication budget", "aggregation rule"], "coordination", "Could separate coordination benefits from simple redundancy or verification effects."),
    (["benchmark", "evaluation"], ["metric choice", "task slice design", "failure-analysis lens"], "evaluation", "Could make evaluation choices themselves a research object instead of hidden background assumptions."),
    (["safety", "security", "governance"], ["threat model", "monitoring granularity", "permission boundary"], "governance", "Could connect technical agent behaviors to deployment-relevant risk questions in a more principled way."),
]

GENERIC_LIMITATION_PATTERNS = [
    "abstract-level evidence only",
    "validate assumptions",
    "full paper",
    "before relying on this as key evidence",
]

BENCHMARK_HINTS = [
    "HotpotQA", "FEVER", "ALFWorld", "WebShop", "HumanEval", "WebArena", "AgentBench",
    "GSM8K", "MATH", "Wikipedia", "wiki", "API", "question answering", "fact verification",
]

AXIS_INSIGHT_LIBRARY: dict[str, dict[str, str]] = {
    "observability granularity": {
        "question": "whether several agent-loop gains are really planner gains, or whether they mostly come from changing what the planner gets to observe and when",
        "confound": "planner quality and broader agent competence",
        "thesis": "Several agent-loop gains remain hard to interpret because papers often improve observation access at the same time they improve the planner; before crediting planner depth, we should ask what the system was allowed to see.",
        "insight": "A convincing result would not just move aggregate score. It would show which published gains survive once observation access is fixed, ideally producing a regime map of when observability—not planner depth—changes the failure story.",
        "contribution_shape": "Could yield a causal-attribution result plus a reporting rule for agent-loop papers: claims about planning quality should specify and control observation access.",
        "demotion": "This direction weakens sharply if the strongest prior work already holds observation access fixed while planner quality changes and still reports the same gain pattern.",
        "kill_signal": "an anchor paper already fixes observation access while varying planner quality and the main conclusion still survives",
        "missing_piece": "What is missing is a fixed-interface, fixed-budget comparison that varies only observation access and tracks whether the failure taxonomy—not just average score—changes.",
        "program_kind": "causal attribution",
        "time_to_clarity": "fast",
        "priority_note": "Fastest to falsify on public tasks, and the answer would immediately change how several agent-loop results are interpreted.",
        "reading_extract": "what the agent sees at each step, which ablations vary planner depth, and whether the action interface stays fixed",
        "title": "Observability granularity vs planner depth",
    },
    "action-space design": {
        "question": "whether robustness comes from better reasoning or from giving the agent a cleaner action interface",
        "confound": "the shape of the action vocabulary and interface design",
        "thesis": "Some agent-loop gains may be interface gains in disguise: when action vocabularies become cleaner or narrower, papers can attribute robustness to reasoning improvements that partly come from action-space design.",
        "insight": "A useful result would show whether the same nominal planner still behaves very differently once the action space is widened, normalized, or made less ergonomic.",
        "contribution_shape": "Could produce an action-space normalization protocol and a clearer account of which agent claims survive once interface ergonomics are controlled.",
        "demotion": "This direction weakens if current papers already compare equivalent action spaces and still obtain the same ranking.",
        "kill_signal": "the key anchor papers already normalize action vocabularies or API surfaces and still see the same ordering",
        "missing_piece": "What is missing is an action-space-normalized comparison that keeps planner prompts fixed while changing only interface granularity and affordances.",
        "program_kind": "interface normalization",
        "time_to_clarity": "medium",
        "priority_note": "Interesting and still thesis-relevant, but less immediate than observability because interface normalization usually requires more careful task redesign.",
        "reading_extract": "how many actions are available, how semantically aligned the actions are, and whether interface cleanup happens together with reasoning changes",
        "title": "Action-space design or agent competence?",
    },
    "tool/environment boundary": {
        "question": "whether reliability depends more on boundary design between tool and environment than on the nominal reasoning loop",
        "confound": "tool abstraction and environment modeling",
        "thesis": "A number of agent results may really be about boundary design: where the system stops reasoning internally and starts delegating to tools can change reliability without changing the nominal planner much.",
        "insight": "A strong result would show that several agent-level conclusions are actually boundary-design conclusions once tool abstraction is normalized.",
        "contribution_shape": "Could yield a boundary-design taxonomy and a cleaner experimental recipe for separating planner quality from tool/interface scaffolding.",
        "demotion": "This direction weakens if changing the boundary carefully barely affects the failure story.",
        "kill_signal": "careful tool-boundary changes leave both the metric and the qualitative failure modes essentially unchanged",
        "missing_piece": "What is missing is a comparison that keeps task semantics fixed while moving the tool/environment boundary in a controlled way.",
        "program_kind": "systems boundary",
        "time_to_clarity": "medium",
        "priority_note": "Valuable as a systems-facing thesis line, but slower to turn into a decisive first readout than the lead mechanism questions.",
        "reading_extract": "where tool calls begin, what state is exposed to the planner, and whether environment modeling changes together with the tool boundary",
        "title": "Where the tool boundary really matters",
    },
    "search depth": {
        "question": "whether apparent planning gains reflect deeper search or simply more inference-time budget to recover from weak initial choices",
        "confound": "inference-time compute budget",
        "thesis": "Many planning results still bundle depth with budget: deeper search often spends more tokens, branches, or retries, so it remains unclear whether depth changes reasoning quality or just buys more recovery opportunities.",
        "insight": "A convincing result would show whether depth changes the nature of planning failures under a matched budget, rather than merely delaying failure by spending more compute.",
        "contribution_shape": "Could produce a compute-normalized planning benchmark slice and a regime map for when search depth matters beyond extra inference budget.",
        "demotion": "This direction weakens if prior work already equalizes budget and still finds depth-specific gains.",
        "kill_signal": "the anchor papers already normalize token or wall-clock budget and the depth advantage remains intact",
        "missing_piece": "What is missing is a compute-normalized study that holds token or wall-clock budget fixed while varying depth or branching, then checks whether failure modes actually change.",
        "program_kind": "budget-normalized mechanism",
        "time_to_clarity": "medium",
        "priority_note": "Still thesis-sized, but it ranks behind observability because compute normalization is harder to defend and easier for prior work to have addressed already.",
        "reading_extract": "the reported depth or branching settings, the effective compute budget, and whether shallow baselines were budget-matched",
        "title": "Search depth or compute budget?",
    },
    "verification loop": {
        "question": "whether verification contributes a distinct reasoning mechanism or mostly acts as expensive redundancy",
        "confound": "extra compute and repeated checking",
        "thesis": "Verification-heavy pipelines may look stronger because they retry, re-check, or filter more often, not necessarily because they add a distinct reasoning mechanism.",
        "insight": "A useful result would separate verification as a mechanism from verification as a compute-expensive retry policy.",
        "contribution_shape": "Could produce a cleaner protocol for comparing verification loops under matched retry or compute budgets.",
        "demotion": "This direction weakens if verification can be replaced by simple repetition with little change in behavior.",
        "kill_signal": "repeat-sampling or retry baselines already match the reported verification gain",
        "missing_piece": "What is missing is a matched-budget comparison between explicit verification and simple repetition or reranking baselines.",
        "program_kind": "verification audit",
        "time_to_clarity": "medium",
        "priority_note": "Decision-relevant when the group suspects redundancy masquerading as reasoning, though the probe is less clean than the top two directions.",
        "reading_extract": "how many extra passes are spent on checking, whether retry baselines exist, and which errors verification actually fixes",
        "title": "Verification or just expensive redundancy?",
    },
    "partial-observability handling": {
        "question": "whether planning systems fail because they reason badly or because they are brittle under missing state information",
        "confound": "state visibility",
        "thesis": "Some planning failures may be epistemic before they are algorithmic: systems can look like weak planners when they are actually brittle under missing state information.",
        "insight": "A strong result would show whether improved visibility changes the failure taxonomy more than planner changes do.",
        "contribution_shape": "Could produce a planning-under-partial-observability benchmark slice and a clearer division between epistemic and algorithmic failure modes.",
        "demotion": "This direction weakens if stronger visibility barely changes the failure pattern.",
        "kill_signal": "improved visibility leaves both success rates and error types almost unchanged",
        "missing_piece": "What is missing is a task slice that varies only state visibility while keeping planner scaffolding steady.",
        "program_kind": "epistemic failure analysis",
        "time_to_clarity": "medium",
        "priority_note": "Useful if the group wants a deeper failure-analysis program, but it is currently less concrete than the lead directions.",
        "reading_extract": "what information is hidden, which observations are restored by tools, and whether planner quality is tested separately from visibility",
        "title": "Is planning failure really an observability problem?",
    },
    "retrieval policy": {
        "question": "whether memory gains come from better stored knowledge or from better decisions about when and how retrieval is triggered",
        "confound": "memory content versus retrieval timing",
        "thesis": "Reported memory gains are often hard to interpret because memory content and retrieval triggers move together; some improvements may be protocol effects about when retrieval happens, not capability effects about what memory stores.",
        "insight": "A convincing result would separate memory-content effects from retrieval-trigger effects and show whether the interpretation of current RAG-style gains changes once trigger policy is normalized.",
        "contribution_shape": "Could yield a cleaner memory-evaluation protocol and a reusable result on when retrieval policy, rather than memory content, is the true hidden variable.",
        "demotion": "This direction weakens if current work already varies retrieval policy independently of memory content and sees the same story.",
        "kill_signal": "the main memory papers already keep the memory store fixed while varying retrieval triggers or timing and the conclusion does not move",
        "missing_piece": "What is missing is a fixed-memory comparison that varies retrieval trigger and timing only, then checks whether the gain survives and which errors it actually removes.",
        "program_kind": "protocol sensitivity",
        "time_to_clarity": "medium",
        "priority_note": "Different enough from the planning directions to stay in the lead set, but it ranks lower because the current evidence is thinner and more protocol-sensitive.",
        "reading_extract": "what is stored in memory, when retrieval fires, what retrieval budget is allowed, and whether trigger policy is ever ablated independently",
        "title": "Retrieval policy or memory content?",
    },
    "state summarization cadence": {
        "question": "whether summarization helps because it improves reasoning or because it selectively compresses away troublesome state information",
        "confound": "what gets forgotten versus what gets highlighted",
        "thesis": "Summarization may help less because the agent reasons better and more because the system filters state in a favorable way; cadence choices can quietly redefine what information survives.",
        "insight": "A useful result would show whether different summarization cadences preserve the same conclusions and failure taxonomy once memory content is held steady.",
        "contribution_shape": "Could produce a summarization-control protocol for long-horizon agents and a clearer account of how state compression alters conclusions.",
        "demotion": "This direction weakens if different summarization cadences preserve the same conclusions and failure taxonomy.",
        "kill_signal": "changing summarization cadence leaves both retrieval behavior and downstream errors largely unchanged",
        "missing_piece": "What is missing is a fixed-memory, fixed-task comparison that varies only summarization cadence and records what state is lost or amplified.",
        "program_kind": "state compression",
        "time_to_clarity": "medium",
        "priority_note": "Promising but currently less mature than retrieval-policy framing because the concrete prior-work hooks are thinner.",
        "reading_extract": "what gets summarized away, how often summaries are rewritten, and whether failure cases correlate with state compression choices",
        "title": "What summarization cadence is really changing",
    },
    "memory horizon": {
        "question": "whether longer memory helps because more context is useful or because evaluations reward persistence over selectivity",
        "confound": "context length and evaluation design",
        "thesis": "Longer memory can look like better capability even when the benchmark mainly rewards persistence or repeated access to earlier state, so horizon effects may partly be evaluation-design effects.",
        "insight": "A convincing result would show whether extending horizon changes task framing and error patterns, not just aggregate score.",
        "contribution_shape": "Could produce a regime map for when horizon length matters, versus when selective retrieval or better task design explains the gain.",
        "demotion": "This direction weakens if memory horizon has little effect once retrieval policy is controlled.",
        "kill_signal": "memory-length changes stop mattering once retrieval triggers or evaluation design are normalized",
        "missing_piece": "What is missing is a horizon study that matches retrieval policy and benchmark framing while varying how much state is retained.",
        "program_kind": "regime mapping",
        "time_to_clarity": "medium",
        "priority_note": "Conceptually useful, but currently less decisive than retrieval-policy framing for a first discussion round.",
        "reading_extract": "whether longer context actually changes retrieval choices, and whether the benchmark rewards persistence more than selective recall",
        "title": "Does longer memory really help?",
    },
}


@dataclass(frozen=True)
class IdeaSignal:
    signal_id: str
    cluster: str
    direction_type: str
    theme: str
    claim_or_observation: str
    tension: str
    missing_piece: str
    possible_axis: str
    academic_value: str
    evidence_confidence: str
    paper_ids: list[str]


@dataclass(frozen=True)
class DirectionCard:
    direction_id: str
    cluster: str
    direction_type: str
    title: str
    focus_axis: str
    main_confound: str
    program_kind: str
    contribution_shape: str
    time_to_clarity: str
    one_line_thesis: str
    why_interesting: str
    literature_suggests: list[str]
    closest_prior_gap: list[str]
    missing_piece: str
    possible_variants: list[str]
    academic_value: str
    first_probes: list[str]
    what_counts_as_insight: str
    weakness_conditions: list[str]
    kill_criteria: list[str]
    what_would_change_mind: list[str]
    best_fit: str
    why_this_ranks_here: str
    evidence_confidence: str
    paper_ids: list[str]
    signal_ids: list[str]
    anchor_reading_notes: list[dict[str, str]]


@dataclass(frozen=True)
class ScreenedDirection:
    direction_id: str
    cluster: str
    direction_type: str
    title: str
    total_score: float
    discussion_worthiness: int
    academic_value_score: int
    evidence_grounding: int
    direction_distinctness: int
    first_probe_clarity: int
    thesis_potential: int
    recommendation: str
    rationale: str


def read_core_set(path: Path) -> list[dict[str, str]]:
    import csv
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any] | Any]) -> None:
    ensure_dir(path.parent)
    encoded: list[str] = []
    for row in rows:
        value = asdict(row) if is_dataclass(row) else row
        encoded.append(json.dumps(value, ensure_ascii=False))
    atomic_write_text(path, "\n".join(encoded).rstrip() + ("\n" if encoded else ""))


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2).rstrip() + "\n")


def uniq_keep_order(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def slugify(text: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "-", str(text or "").strip().lower())
    return raw.strip("-") or "x"


def clean_text(text: str, *, limit: int = 220) -> str:
    s = str(text or "").strip()
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("|", ", ")
    # Unescape LaTeX-escaped punctuation that leaks from source notes/abstracts
    # ("attains a 35\% success rate" -> "35%"). These backslash escapes are a
    # LaTeX artifact and must never reach reader-facing Markdown/plain text.
    s = re.sub(r"\\([%&#_$])", r"\1", s)
    s = s.strip(" \"'`")
    if len(s) <= limit:
        return s
    clipped = s[:limit].rsplit(" ", 1)[0].strip()
    return clipped if clipped else s[:limit].strip()


# Words a clipped PAPER TITLE must not end on — a "read <title>" instruction that
# ends on a dangling article/preposition ("... Learning: A") is unsearchable and
# reads broken. Used by clean_title to drop such a trailing word after clipping.
_TITLE_DANGLING = frozenset({
    "a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "with", "via",
    "from", "into", "at", "by", "as", "vs", "vs.",
})


def clean_title(text: str, *, limit: int = 140) -> str:
    """Clean a paper title for reader-facing "read <title>" prose.

    Uses a generous cap (most arXiv titles fit) so a title is not chopped, and —
    when a clip is unavoidable — drops a trailing dangling article/preposition so
    the title never ends on "... Learning: A".
    """
    s = clean_text(text, limit=limit)
    words = s.split()
    while words and words[-1].lower().strip(":,;-") in _TITLE_DANGLING:
        words.pop()
    return " ".join(words).rstrip(" :,;-") or s


def clean_sentence(text: str, *, limit: int = 180) -> str:
    s = clean_text(text, limit=max(limit * 2, limit))
    if len(s) <= limit:
        return s
    window = s[:limit + 40]
    pieces = re.split(r'(?<=[.!?;])\s+', window)
    acc: list[str] = []
    total = 0
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        nxt = total + len(piece) + (1 if acc else 0)
        if nxt > limit and acc:
            break
        acc.append(piece)
        total = nxt
        if total >= int(limit * 0.65):
            break
    result = " ".join(acc).strip() if acc else s
    # Guarantee no mid-word cut: if still over the limit (e.g. a single long
    # sentence with no internal terminator), back up to the last clause boundary
    # within the limit, then to the last whole word. Never emit a partial word
    # like "... survives, de".
    if len(result) > limit:
        head = result[:limit]
        boundary = max(head.rfind(", "), head.rfind("; "))
        if boundary >= int(limit * 0.5):
            result = head[:boundary]
        else:
            cut = head.rfind(" ")
            result = head[:cut] if cut > 0 else head
    return result.rstrip(" ,;:-").strip()


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(cell).replace("\n", " ").strip() for cell in row) + " |" for row in rows]
    return "\n".join([head, sep] + body)


def write_markdown(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    atomic_write_text(path, text.rstrip() + "\n")


def extract_goal_from_goal_md(path: Path) -> str:
    if not path.exists():
        return "research ideas"
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip() and not ln.startswith("#")]
    return lines[0] if lines else "research ideas"


def _idea_workspace_from_brief(path: Path) -> Path | None:
    try:
        return path.resolve().parents[2]
    except Exception:
        return None


def _require_positive_float(value: Any, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}") from exc
    if parsed <= 0:
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
    return parsed


def _query_int_override(workspace: Path, key: str, default: int) -> int:
    queries_path = workspace / "queries.md"
    normalized = str(key or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not normalized:
        return int(default)
    if normalized not in pipeline_overridable_query_fields(workspace):
        return int(default)
    if not queries_path.exists():
        return int(default)
    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_").replace("-", "_")
            if key != normalized:
                continue
            cleaned = value.split("#", 1)[0].strip().strip('"').strip("'")
            if not cleaned:
                raise ValueError(f"Invalid ideation override: `{normalized}` is empty in queries.md.")
            try:
                parsed = int(cleaned)
            except Exception as exc:
                raise ValueError(f"Invalid ideation override: `{normalized}` must be an integer in queries.md.") from exc
            if parsed <= 0:
                raise ValueError(f"Invalid ideation override: `{normalized}` must be a positive integer in queries.md.")
            return parsed
    except Exception:
        raise
    return int(default)


def _validate_score_weights(value: Any, *, field_name: str) -> dict[str, float]:
    required = {
        "discussion_worthiness": 0.24,
        "academic_value": 0.22,
        "evidence_grounding": 0.18,
        "direction_distinctness": 0.16,
        "first_probe_clarity": 0.10,
        "thesis_potential": 0.10,
    }
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
    weights: dict[str, float] = {}
    for key in required:
        if key not in value:
            raise ValueError(f"Missing or invalid ideation contract field: {field_name}.{key}")
        weights[key] = _require_positive_float(value.get(key), field_name=f"{field_name}.{key}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
    return {key: round(weight / total, 6) for key, weight in weights.items()}


def _validate_diversity_axes(value: Any, *, field_name: str) -> list[str]:
    allowed = {"cluster", "direction_type", "program_kind"}
    if not isinstance(value, list):
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
    axes: list[str] = []
    seen: set[str] = set()
    for item in value:
        axis = str(item or "").strip().lower().replace("-", "_")
        if not axis:
            continue
        if axis not in allowed:
            raise ValueError(f"Missing or invalid ideation contract field: {field_name}.{axis}")
        if axis in seen:
            continue
        seen.add(axis)
        axes.append(axis)
    if not axes:
        raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
    return axes


def parse_idea_focus_decision(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    match = re.search(
        r"<!-- BEGIN CHECKPOINT:C2 -->(.*?)<!-- END CHECKPOINT:C2 -->",
        text,
        flags=re.DOTALL,
    )
    block = match.group(1) if match else ""

    def values(label: str) -> list[str]:
        selected = re.search(rf"(?im)^-\s*{re.escape(label)}:\s*(.*)$", block)
        if selected is None:
            return []
        raw = selected.group(1).strip()
        if not raw or raw.startswith("("):
            return []
        return [item.strip() for item in raw.split(";") if item.strip()]

    return {
        "focus_clusters": values("Focus clusters"),
        "hard_exclusions": values("Hard exclusions"),
    }


def write_idea_focus_decision(
    path: Path,
    *,
    focus_clusters: Iterable[str],
    hard_exclusions: Iterable[str] = (),
) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    begin = "<!-- BEGIN CHECKPOINT:C2 -->"
    end = "<!-- END CHECKPOINT:C2 -->"
    if begin not in text or end not in text:
        raise ValueError("C2 review block is missing; run checkpoint-brief before approval.")
    focus = [str(item or "").strip() for item in focus_clusters if str(item or "").strip()]
    exclusions = [str(item or "").strip() for item in hard_exclusions if str(item or "").strip()]
    if not focus:
        raise ValueError("At least one C2 focus cluster is required.")

    prefix, remainder = text.split(begin, 1)
    block, suffix = remainder.split(end, 1)
    replacements = {
        "Focus clusters": "; ".join(focus),
        "Hard exclusions": "; ".join(exclusions) if exclusions else "(none recorded)",
    }
    for label, value in replacements.items():
        pattern = re.compile(rf"(?im)^-\s*{re.escape(label)}:\s*.*$")
        if not pattern.search(block):
            raise ValueError(f"C2 review block is missing `{label}`.")
        block = pattern.sub(f"- {label}: {value}", block, count=1)
    atomic_write_text(path, prefix + begin + block + end + suffix)


def resolve_idea_contract(workspace: Path) -> dict[str, Any]:
    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        raise ValueError("Missing active pipeline contract.")
    query_defaults = dict(spec.query_defaults)
    quality_contract = dict(spec.quality_contract)

    def _require_positive_int(value: Any, *, field_name: str) -> int:
        try:
            parsed = int(value)
        except Exception as exc:
            raise ValueError(f"Missing or invalid ideation contract field: {field_name}") from exc
        if parsed <= 0:
            raise ValueError(f"Missing or invalid ideation contract field: {field_name}")
        return parsed

    signal_policy = quality_contract.get("signal_policy") or {}
    direction_policy = quality_contract.get("direction_policy") or {}
    screening_policy = quality_contract.get("screening_policy") or {}
    brief = parse_idea_brief(workspace / "output" / "trace" / "IDEA_BRIEF.md")
    focus_decision = parse_idea_focus_decision(workspace / "DECISIONS.md")
    selected_focus = focus_decision.get("focus_clusters") or []
    focus_clusters = [str(x).strip() for x in selected_focus if str(x).strip()]
    if not focus_clusters:
        raise ValueError(
            "Missing explicit C2 focus selection in DECISIONS.md; "
            "the pre-retrieval Idea Brief cannot authorize post-retrieval synthesis."
        )
    direction_pool_min_default = _require_positive_int(query_defaults.get("direction_pool_min"), field_name="query_defaults.direction_pool_min")
    direction_pool_max_default = _require_positive_int(query_defaults.get("direction_pool_max"), field_name="query_defaults.direction_pool_max")
    shortlist_size_default = _require_positive_int(query_defaults.get("idea_shortlist_size"), field_name="query_defaults.idea_shortlist_size")
    report_top_n_default = _require_positive_int(query_defaults.get("report_top_n"), field_name="query_defaults.report_top_n")
    idea_screen_top_n_default = _require_positive_int(query_defaults.get("idea_screen_top_n"), field_name="query_defaults.idea_screen_top_n")
    shortlist_min = _require_positive_int(direction_policy.get("shortlist_min"), field_name="quality_contract.direction_policy.shortlist_min")
    shortlist_max = _require_positive_int(direction_policy.get("shortlist_max"), field_name="quality_contract.direction_policy.shortlist_max")
    keep_min = _require_positive_int(direction_policy.get("keep_min"), field_name="quality_contract.direction_policy.keep_min")
    cluster_diversity_min = _require_positive_int(direction_policy.get("cluster_diversity_min"), field_name="quality_contract.direction_policy.cluster_diversity_min")
    lead_diversity_target = _require_positive_int(direction_policy.get("lead_diversity_target"), field_name="quality_contract.direction_policy.lead_diversity_target")
    lead_diversity_axes = _validate_diversity_axes(
        direction_policy.get("lead_diversity_axes"),
        field_name="quality_contract.direction_policy.lead_diversity_axes",
    )
    signal_table_min = _require_positive_int(signal_policy.get("min_rows"), field_name="quality_contract.signal_policy.min_rows")
    keep_rank_max = _require_positive_int(screening_policy.get("keep_rank_max"), field_name="quality_contract.screening_policy.keep_rank_max")
    maybe_rank_max = _require_positive_int(screening_policy.get("maybe_rank_max"), field_name="quality_contract.screening_policy.maybe_rank_max")
    score_weights = _validate_score_weights(
        screening_policy.get("score_weights"),
        field_name="quality_contract.screening_policy.score_weights",
    )
    direction_pool_min = _query_int_override(workspace, "direction_pool_min", direction_pool_min_default)
    direction_pool_max = _query_int_override(workspace, "direction_pool_max", direction_pool_max_default)
    shortlist_size = _query_int_override(workspace, "idea_shortlist_size", shortlist_size_default)
    report_top_n = _query_int_override(workspace, "report_top_n", report_top_n_default)
    idea_screen_top_n = _query_int_override(workspace, "idea_screen_top_n", idea_screen_top_n_default)
    if direction_pool_min > direction_pool_max:
        raise ValueError(f"Invalid ideation contract: direction_pool_min ({direction_pool_min}) exceeds direction_pool_max ({direction_pool_max}).")
    if shortlist_size < shortlist_min or shortlist_size > shortlist_max:
        raise ValueError(
            f"Invalid ideation contract: idea_shortlist_size ({shortlist_size}) must stay within "
            f"[{shortlist_min}, {shortlist_max}]."
        )
    if report_top_n > shortlist_size:
        raise ValueError(f"Invalid ideation contract: report_top_n ({report_top_n}) exceeds idea_shortlist_size ({shortlist_size}).")
    if maybe_rank_max < keep_rank_max:
        raise ValueError(
            f"Invalid ideation contract: maybe_rank_max ({maybe_rank_max}) must be >= keep_rank_max ({keep_rank_max})."
        )
    if idea_screen_top_n > direction_pool_max:
        raise ValueError(f"Invalid ideation contract: idea_screen_top_n ({idea_screen_top_n}) exceeds direction_pool_max ({direction_pool_max}).")
    return {
        "focus_clusters": focus_clusters,
        "hard_exclusions": list(focus_decision.get("hard_exclusions") or []),
        "direction_pool_min": direction_pool_min,
        "direction_pool_max": direction_pool_max,
        "idea_screen_top_n": idea_screen_top_n,
        "shortlist_size": shortlist_size,
        "report_top_n": report_top_n,
        "shortlist_min": shortlist_min,
        "shortlist_max": shortlist_max,
        "signal_table_min": signal_table_min,
        "keep_min": keep_min,
        "cluster_diversity_min": cluster_diversity_min,
        "lead_diversity_target": lead_diversity_target,
        "lead_diversity_axes": lead_diversity_axes,
        "keep_rank_max": keep_rank_max,
        "maybe_rank_max": maybe_rank_max,
        "score_weights": score_weights,
    }


def parse_idea_brief(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    out: dict[str, Any] = {
        "goal": extract_goal_from_goal_md(path),
        "focus_clusters": [],
        "query_buckets": [],
        "exclusions": [],
        "constraints": [],
        "targets": {},
    }
    cur = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            continue
        if cur == "goal" and line.startswith("- Topic:"):
            out["goal"] = line.split(":", 1)[1].strip()
        if cur in {"focus after c2", "focus lenses after c2"} and line.startswith("- Focus clusters:"):
            clusters = [x.strip() for x in line.split(":", 1)[1].split(";") if x.strip()]
            cleaned: list[str] = []
            for item in clusters:
                low = item.lower()
                if "to be filled" in low or "fill after c2" in low or "placeholder" in low:
                    continue
                cleaned.append(item)
            out["focus_clusters"] = cleaned
        if cur == "query buckets" and re.match(r"^\d+\.\s+", line):
            out["query_buckets"].append(re.sub(r"^\d+\.\s+", "", line).strip())
        if cur in {"exclude terms", "exclusions"} and line.startswith("- "):
            value = line[2:].strip()
            if value and not value.lower().startswith("none"):
                out["exclusions"].append(value)
        if cur == "constraints" and line.startswith("- "):
            out["constraints"].append(line[2:].strip())
        if cur == "targets" and line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            out["targets"][key.strip().lower().replace(" ", "_")] = value.strip()

    return out


def collect_note_index(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in read_jsonl(path):
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("paper_id") or "").strip()
        if pid:
            out[pid] = rec
    return out


def keywords_from_cluster(name: str) -> list[str]:
    toks = [t for t in re.findall(r"[A-Za-z0-9]+", str(name or "").lower()) if t not in STOPWORDS and len(t) > 2]
    return uniq_keep_order(toks)


def score_note_to_cluster(cluster_name: str, note: dict[str, Any]) -> int:
    keys = keywords_from_cluster(cluster_name)
    blob_parts = [str(note.get("title") or "")]
    for field in ["summary_bullets", "limitations", "key_results", "method", "abstract"]:
        val = note.get(field)
        if isinstance(val, list):
            blob_parts.extend([str(x) for x in val])
        elif isinstance(val, str):
            blob_parts.append(val)
    blob = " ".join(blob_parts).lower()
    return sum(1 for key in keys if key in blob)


def map_notes_to_clusters(taxonomy_path: Path, notes_path: Path) -> dict[str, list[dict[str, Any]]]:
    import yaml

    taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8", errors="ignore")) if taxonomy_path.exists() else []
    notes = [r for r in read_jsonl(notes_path) if isinstance(r, dict)]
    out: dict[str, list[dict[str, Any]]] = {}
    for top in taxonomy or []:
        if not isinstance(top, dict):
            continue
        parent_name = str(top.get("name") or "").strip()
        for child in top.get("children") or []:
            if not isinstance(child, dict):
                continue
            child_name = str(child.get("name") or "").strip()
            if not child_name:
                continue
            name = f"{parent_name} / {child_name}" if parent_name else child_name
            scored: list[tuple[int, dict[str, Any]]] = []
            for note in notes:
                s = score_note_to_cluster(name, note)
                if s > 0:
                    scored.append((s, note))
            scored.sort(key=lambda x: (-x[0], str(x[1].get("paper_id") or "")))
            out[name] = [n for _, n in scored[:8]]
    return out


def _cluster_axis_terms(cluster: str) -> list[str]:
    """Distinctive content tokens of a cluster label, most-specific first.

    A cluster label is "Parent / Child"; the CHILD segment is the distinguishing
    part (parents repeat across clusters, e.g. two "Interatomic Potential / …"
    clusters). Take the child tokens first, then the parent tokens, dropping
    stopwords/duplicates, so clusters that share a parent still lead with a
    distinct child token and therefore get distinct axes.
    """
    raw = str(cluster or "")
    if "/" in raw:
        parent, _, child = raw.rpartition("/")
        ordered_segments = [child, parent]
    else:
        ordered_segments = [raw]
    seen: list[str] = []
    for segment in ordered_segments:
        for tok in re.findall(r"[A-Za-z0-9]+", segment):
            low = tok.lower()
            if low in STOPWORDS or len(low) < 3:
                continue
            if low not in [t.lower() for t in seen]:
                seen.append(tok)
    return seen


def _cluster_profile(cluster: str) -> tuple[str, list[str], str]:
    low = cluster.lower()
    for keys, axes, direction_type, academic_value in CLUSTER_AXIS_HINTS:
        if any(key in low for key in keys):
            return direction_type, axes, academic_value
    # No domain hint matched (non-agent topic, or a keyword-derived cluster).
    # Derive axes from THIS cluster's own distinctive terms so different clusters
    # explore different axes, rather than collapsing every cluster onto the same
    # fixed triple. The analytical lenses (sensitivity / failure modes / scope)
    # are kept but grounded in the cluster's leading term.
    terms = _cluster_axis_terms(cluster)
    if terms:
        lead = terms[0].lower()
        second = terms[1].lower() if len(terms) > 1 else lead
        axes = [
            f"{lead} sensitivity",
            f"{second} failure modes" if second != lead else f"{lead} failure modes",
            f"{lead} scope boundary",
        ]
        # de-duplicate while preserving order (guards lead == second)
        axes = list(dict.fromkeys(axes))
        if len(axes) < 3:
            axes += [a for a in ("assumption sensitivity", "failure analysis", "scope boundary") if a not in axes]
        return "research", axes[:3], f"Could sharpen how {lead} is framed and compared within this sub-area."
    return "research", ["assumption sensitivity", "failure analysis", "scope boundary"], "Could sharpen the way this sub-area is framed and compared."


def _note_bullets(note: dict[str, Any], field: str) -> list[str]:
    val = note.get(field)
    if isinstance(val, list):
        return [clean_text(x, limit=220) for x in val if clean_text(x, limit=220)]
    if isinstance(val, str) and clean_text(val, limit=220):
        return [clean_text(val, limit=220)]
    return []


def _specific_limitations(note: dict[str, Any]) -> list[str]:
    items = _note_bullets(note, "limitations")
    specific = []
    for item in items:
        low = item.lower()
        if any(pat in low for pat in GENERIC_LIMITATION_PATTERNS):
            continue
        specific.append(item)
    return specific or items


def _evidence_confidence(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return "low"
    if any(str(n.get("evidence_level") or "").strip() == "fulltext" for n in notes):
        return "medium-high"
    specific = sum(
        1
        for n in notes
        if _specific_limitations(n) and not any(p in (_specific_limitations(n)[0].lower()) for p in GENERIC_LIMITATION_PATTERNS)
    )
    if len(notes) >= 3 and specific >= 2:
        return "medium"
    return "low-medium"


def _axis_profile(axis: str, cluster: str) -> dict[str, str]:
    base = AXIS_INSIGHT_LIBRARY.get(axis, {})
    confound = base.get("confound", "nearby design choices and evaluation framing")
    return {
        "question": base.get("question", f"whether {axis} is doing more conceptual work in {cluster.lower()} than current papers make explicit"),
        "confound": confound,
        "thesis": base.get("thesis", f"Current results in {cluster.lower()} may be hard to interpret because {axis} still moves together with {confound}."),
        "insight": base.get("insight", f"A meaningful result would show whether {axis} changes how we interpret the current literature rather than merely how we narrate it."),
        "contribution_shape": base.get("contribution_shape", f"Could turn {axis} into a cleaner explanatory variable for {cluster.lower()} rather than a background convenience."),
        "demotion": base.get("demotion", f"This direction would weaken if the strongest prior work already isolates {axis} cleanly."),
        "kill_signal": base.get("kill_signal", f"the strongest prior work already isolates {axis} against {confound}"),
        "missing_piece": base.get("missing_piece", f"What is missing is a cleaner comparison that varies {axis} while keeping {confound} fixed enough to change interpretation, not just presentation."),
        "program_kind": base.get("program_kind", "mechanism clarification"),
        "time_to_clarity": base.get("time_to_clarity", "medium"),
        "priority_note": base.get("priority_note", f"Worth discussion because it could turn {axis} into a sharper explanatory wedge for {cluster.lower()}."),
        "reading_extract": base.get("reading_extract", f"which variables change together with {axis}, what comparator is used, and whether any ablation already fixes {confound}"),
        # Fall back to a cluster-qualified title so different topics (and
        # repeated axes across clusters) do not collapse to an identical stem
        # like "What <axis> is really doing"; every other fallback field in this
        # profile is already cluster-qualified.
        "title": base.get("title", f"What {axis} is really doing in {cluster}"),
    }


def _result_fact(note: dict[str, Any]) -> str:
    candidates = _note_bullets(note, "key_results") + _note_bullets(note, "summary_bullets")
    scored: list[str] = []
    for cand in candidates:
        low = cand.lower()
        if any(token in low for token in ["pass@1", "accuracy", "success rate", "exact match", "f1", "outperform", "achiev", "%"]) or any(ch.isdigit() for ch in cand):
            scored.append(cand)
    chosen = scored[0] if scored else _claim_text(note)
    chosen = re.sub(r"^(for instance|for example|e\.g\.)[:,]?\s*", "", chosen, flags=re.IGNORECASE)
    low = chosen.lower()
    tasks = _extract_task_mentions(note)
    task_text = "/".join(tasks[:2]) if tasks else "reported setting"
    percents = re.findall(r"\d+(?:\.\d+)?%", chosen)
    if "pass@1" in low and percents:
        if len(percents) >= 2:
            return clean_text(f"{task_text}: {percents[0]} pass@1 vs {percents[1]} in the reported comparison.", limit=95)
        return clean_text(f"{task_text}: {percents[0]} pass@1 in the reported comparison.", limit=95)
    if "success rate" in low and len(percents) >= 2:
        baseline = " over imitation/RL baselines" if "imitation" in low or "reinforcement learning" in low else " in the reported comparison"
        return clean_text(f"{task_text}: {percents[0]}/{percents[1]} success-rate gains{baseline}.", limit=95)
    if len(percents) >= 2:
        return clean_text(f"{task_text}: {percents[0]} vs {percents[1]} in the reported comparison.", limit=95)
    if len(percents) == 1:
        return clean_text(f"{task_text}: reported result reaches {percents[0]} in the abstract.", limit=95)
    return clean_text(chosen, limit=95)


def _metric_phrase(notes: list[dict[str, Any]]) -> str:
    blob = " ".join(_result_fact(note) for note in notes)
    low = blob.lower()
    if "pass@1" in low:
        return "pass@1 plus failure-type shifts"
    if "success rate" in low:
        return "success rate plus failure-type shifts"
    if "accuracy" in low:
        return "accuracy plus failure-type shifts"
    if "exact match" in low:
        return "exact match plus failure-type shifts"
    if "f1" in low:
        return "F1 plus failure-type shifts"
    if "%" in blob:
        return "the reported benchmark metric plus failure-type shifts"
    return "task success plus failure-type shifts"


def _sentence_has_concrete_hook(text: str) -> bool:
    low = str(text or "").lower()
    if any(ch.isdigit() for ch in str(text or "")):
        return True
    if any(token in low for token in ["pass@1", "accuracy", "success rate", "exact match", "f1", "alfworld", "webshop", "hotpotqa", "fever", "humaneval", "webarena", "agentbench"]):
        return True
    return False


def _extract_task_mentions(note: dict[str, Any]) -> list[str]:
    blob_parts = []
    for field in ["key_results", "summary_bullets", "method", "abstract", "title"]:
        val = note.get(field)
        if isinstance(val, list):
            blob_parts.extend([str(x) for x in val])
        elif isinstance(val, str):
            blob_parts.append(val)
    blob = " ".join(blob_parts)
    low = blob.lower()
    positions: list[tuple[int, str]] = []
    for hint in BENCHMARK_HINTS:
        pos = low.find(hint.lower())
        if pos >= 0:
            positions.append((pos, hint))
    for match in re.finditer(r"\b(?:HumanEval|ALFWorld|WebShop|HotpotQA|FEVER|WebArena|AgentBench|GSM8K|MATH)\b", blob):
        positions.append((match.start(), match.group(0)))
    positions.sort(key=lambda item: (item[0], item[1]))
    return uniq_keep_order(name for _, name in positions)


def _task_phrase(notes: list[dict[str, Any]]) -> str:
    tasks: list[str] = []
    for note in notes:
        tasks.extend(_extract_task_mentions(note))
    uniq = uniq_keep_order(tasks)
    if not uniq:
        return "a small public task slice"
    if len(uniq) == 1:
        return uniq[0]
    return "/".join(uniq[:2])


def _claim_text(note: dict[str, Any]) -> str:
    candidates = _note_bullets(note, "key_results") + _note_bullets(note, "summary_bullets")
    long_cands = [c for c in candidates if len(c.split()) >= 8]
    # Prefer a candidate that is a COMPLETE sentence (ends in terminal
    # punctuation) over a truncated abstract fragment ending mid-list
    # ("... ImageNet-C, DomainNet,"). Fall back to the first long candidate.
    chosen = ""
    for cand in long_cands:
        if cand.rstrip().endswith((".", "!", "?")):
            chosen = cand
            break
    if not chosen and long_cands:
        chosen = long_cands[0]
    if not chosen:
        return clean_text(note.get("method") or note.get("title") or "", limit=220)
    # clean_sentence trims to a clause/word boundary when over the limit; also
    # drop any trailing list punctuation so a mid-list fragment never ends on a
    # dangling comma/semicolon/colon.
    return clean_sentence(chosen, limit=240).rstrip(" ,;:")


def _limitation_text(note: dict[str, Any], axis: str, cluster: str) -> str:
    limitations = _specific_limitations(note)
    if limitations and not any(pat in limitations[0].lower() for pat in GENERIC_LIMITATION_PATTERNS):
        return limitations[0]
    profile = _axis_profile(axis, cluster)
    return f"The paper still leaves unclear whether {axis} is genuinely responsible for the reported story in {cluster.lower()}, or whether that story is really driven by {profile['confound']}."


def _anchor_notes(note_index: dict[str, dict[str, Any]], paper_ids: list[str]) -> list[dict[str, Any]]:
    return [note_index[pid] for pid in paper_ids if pid in note_index]


def _ensure_sentence_end(text: str) -> str:
    """Guarantee a text excerpt ends with terminal punctuation.

    `_paper_annotation` appends ' Open gap: ...' after a result excerpt. When the
    excerpt is a clipped fragment ('... to Crazyflie 2.1', '... reports of
    MIMIC-CXR,'), the appended clause runs onto it as one sentence. Append a
    period so 'Open gap:' reads as a separate clause; a trailing comma/semicolon/
    colon is replaced by a period, and an existing .!? is left as is.
    """
    s = str(text or "").rstrip()
    if not s:
        return s
    if s[-1] in ".!?":
        return s
    if s[-1] in ",;:":
        return s[:-1] + "."
    return s + "."


def _paper_annotation(note: dict[str, Any], axis: str, cluster: str) -> str:
    title = clean_text(note.get("title") or note.get("paper_id") or "paper", limit=110)
    profile = _axis_profile(axis, cluster)
    result = _ensure_sentence_end(_result_fact(note))
    return clean_sentence(
        f"{title}: {result} Open gap: {axis} still moves with {profile['confound']}.",
        limit=300,
    )



def _synthesis_annotation(notes: list[dict[str, Any]], axis: str, cluster: str) -> str:
    profile = _axis_profile(axis, cluster)
    task_phrase = _task_phrase(notes)
    return clean_sentence(
        f"Across the anchor papers, the live question is whether {axis} changes interpretation itself or merely rides along with {profile['confound']}, especially on {task_phrase}.",
        limit=260,
    )



def _signal_theme(title: str, cluster: str) -> str:
    """Signal Theme = the axis-profile title, cluster-qualified exactly once.

    The default profile title already ends with "... in {cluster}", so blindly
    appending " in {cluster}" doubled it ("... in X in X"). A custom short title
    from the axis-profile table (e.g. "Observability granularity vs planner
    depth") carries no cluster, so it still needs the qualifier. Append only when
    the title does not already reference the cluster.
    """
    title = str(title or "").strip()
    cl = str(cluster or "").strip()
    if not cl or cl.lower() in title.lower():
        return title
    return f"{title} in {cl}"


def build_signal_rows(
    *, cluster: str, notes: list[dict[str, Any]], cluster_index: int = 0
) -> list[IdeaSignal]:
    if not notes:
        return []
    direction_type, axes, academic_value = _cluster_profile(cluster)
    evidence_confidence = _evidence_confidence(notes)
    anchors = notes[:3]
    paper_ids = uniq_keep_order(str(n.get("paper_id") or "").strip() for n in anchors)
    signals: list[IdeaSignal] = []
    for idx, axis in enumerate(axes[:3], start=1):
        anchor = anchors[(idx - 1) % len(anchors)]
        claim = _claim_text(anchor)
        tension = _limitation_text(anchor, axis, cluster)
        profile = _axis_profile(axis, cluster)
        missing_piece = clean_sentence(
            f"What is still missing is a direction that isolates whether {axis} is the real explanatory variable in {cluster.lower()}, rather than leaving it entangled with {profile['confound']}.",
            limit=240,
        )
        signals.append(IdeaSignal(
            # cluster_index keeps signal_id globally unique even when two
            # clusters share the same truncated slug prefix (e.g. two
            # "Clinical Summarization ..." clusters both slugify to
            # "clinical-summari"); without it the per-cluster idx collides and
            # the duplicate-id gate blocks the run.
            signal_id=f"SIG-{cluster_index:02d}-{slugify(cluster)[:16]}-{idx}",
            cluster=cluster,
            direction_type=direction_type,
            theme=_signal_theme(profile["title"], cluster),
            claim_or_observation=claim,
            tension=clean_text(tension, limit=220),
            missing_piece=missing_piece,
            possible_axis=axis,
            academic_value=academic_value,
            evidence_confidence=evidence_confidence,
            paper_ids=paper_ids,
        ))
    return signals


def signal_table_markdown(rows: list[IdeaSignal]) -> str:
    table_rows = []
    for row in rows:
        table_rows.append([
            row.signal_id,
            row.cluster,
            row.theme,
            row.claim_or_observation,
            row.tension,
            row.missing_piece,
            row.possible_axis,
            row.academic_value,
            row.evidence_confidence,
            ", ".join(row.paper_ids),
        ])
    return "\n".join([
        "# IDEA_SIGNAL_TABLE",
        "",
        "## Research signals",
        "",
        markdown_table(["Signal ID", "Cluster", "Theme", "Claim / observation", "Tension", "Missing piece", "Possible axis", "Academic value", "Confidence", "Paper IDs"], table_rows),
        "",
    ])


def _title_from_signal(signal: IdeaSignal) -> str:
    profile = _axis_profile(signal.possible_axis, signal.cluster)
    return clean_sentence(profile["title"], limit=72)


def _best_fit(direction_type: str, axis: str) -> str:
    if direction_type == "governance":
        return "Best fit when the group wants a deployment-relevant reading of agent behavior rather than another internal benchmark story."
    if direction_type == "evaluation":
        return "Best fit when the discussion is really about what counts as convincing evidence, not just how to raise scores."
    if axis in {"search depth", "verification loop", "retrieval policy"}:
        return "Best fit for a PhD discussion that wants one sharper mechanism/confound question rather than a broad systems buildout."
    return "Best fit for PI/PhD discussions that want a thesis-worthy mechanism question rather than a generic benchmark wrapper."


def _cluster_matches_focus(cluster: str, focus: set[str]) -> bool:
    value = str(cluster or "").strip()
    return value in focus or any(value.startswith(f"{item} /") for item in focus)


def _signal_matches_hard_exclusion(signal: IdeaSignal, exclusions: Iterable[str]) -> bool:
    haystack = " ".join(
        (
            signal.cluster,
            signal.direction_type,
            signal.theme,
            signal.claim_or_observation,
            signal.tension,
            signal.missing_piece,
            signal.possible_axis,
            signal.academic_value,
        )
    ).casefold()
    normalized_haystack = " ".join(haystack.split())
    return any(
        " ".join(str(exclusion or "").casefold().split()) in normalized_haystack
        for exclusion in exclusions
        if str(exclusion or "").strip()
    )


def signals_to_direction_cards(
    signals: list[IdeaSignal],
    *,
    note_index: dict[str, dict[str, Any]],
    focus_clusters: list[str],
    pool_min: int,
    pool_max: int,
    hard_exclusions: list[str] | None = None,
) -> list[DirectionCard]:
    focus = {x.strip() for x in focus_clusters if str(x).strip()}
    eligible_signals = [
        signal
        for signal in signals
        if not _signal_matches_hard_exclusion(signal, hard_exclusions or [])
    ]
    cards: list[DirectionCard] = []
    for idx, signal in enumerate(eligible_signals, start=1):
        profile = _axis_profile(signal.possible_axis, signal.cluster)
        anchors = _anchor_notes(note_index, signal.paper_ids)
        task_phrase = _task_phrase(anchors)
        metric_phrase = _metric_phrase(anchors)
        nearest = anchors[0] if anchors else {}
        nearest_title = clean_title((nearest.get("title") if isinstance(nearest, dict) else "") or (signal.paper_ids[0] if signal.paper_ids else signal.cluster))
        nearest_task_phrase = _task_phrase([nearest]) if nearest else task_phrase
        literature_suggests = [_paper_annotation(note, signal.possible_axis, signal.cluster) for note in anchors[:2]]
        literature_suggests.append(_synthesis_annotation(anchors, signal.possible_axis, signal.cluster))
        closest_prior_gap = [
            clean_sentence(
                f"{nearest_title} is the closest prior anchor because it already reports concrete behavior on {nearest_task_phrase}. The unresolved point is whether those gains survive once {profile['confound']} is held fixed while {signal.possible_axis} is varied.",
                limit=220,
            ),
            clean_sentence(
                "The novelty test here is narrow, not rhetorical: if a strong anchor paper already runs that single-variable control, this direction should collapse quickly rather than stay alive as a vague confound story.",
                limit=220,
            ),
        ]
        one_line_thesis = clean_sentence(profile["thesis"], limit=230)
        why_interesting = clean_sentence(
            f"This is not just another benchmark wedge. It opens a {profile['program_kind']} line around {signal.possible_axis}: {profile['question']}.",
            limit=220,
        )
        missing_piece = clean_sentence(profile["missing_piece"], limit=230)
        possible_variants = [
            clean_sentence(f"Single-variable control on {task_phrase}: vary {signal.possible_axis} while holding {profile['confound']} fixed as far as the setup allows.", limit=210),
            clean_sentence("Replace score-only reporting with a failure-type comparison after the same intervention, so the result says more than whether the average went up.", limit=210),
            clean_sentence("Check whether the conclusion survives on one simple public task slice and one more tool- or environment-heavy setting before treating it as a general claim.", limit=210),
        ]
        first_probes = [
            # These are complete instructional directives whose only variable-length
            # input is the (already-capped) anchor title, so the limit must be high
            # enough to never clip the actionable clause — a mid-sentence cut like
            # "...already fixes planner quality and broader" drops the "if the
            # conclusion survives, demote this direction" instruction the reader acts on.
            clean_sentence(
                f"Intervention: vary {signal.possible_axis} while holding {profile['confound']} as fixed as possible on {task_phrase}. Readout: {metric_phrase}. Decisive if the interpretation changes even after the control.",
                limit=280,
            ),
            clean_sentence(
                f"Prior-work audit: inspect {nearest_title} for any ablation that already fixes {profile['confound']}, and if the conclusion survives, demote this direction.",
                limit=260,
            ),
        ]
        what_counts_as_insight = clean_sentence(profile['insight'], limit=190)
        kill_criteria = [
            clean_sentence(f"Kill quickly if {profile['kill_signal']}.", limit=170),
            clean_sentence(f"Kill if the first controlled probe leaves both {metric_phrase} and the failure taxonomy essentially unchanged.", limit=170),
        ]
        weakness_conditions = [
            clean_sentence(f"This direction is weaker if changing {signal.possible_axis} mostly rescales the aggregate metric without changing which failure modes appear or disappear.", limit=175),
            clean_sentence(profile['demotion'], limit=170),
        ]
        anchor_reading_notes: list[dict[str, str]] = []
        for note in anchors[:3]:
            title = clean_text(note.get("title") or note.get("paper_id") or "paper", limit=110)
            result = _result_fact(note)
            anchor_reading_notes.append({
                "paper_title": title,
                "why_read": clean_sentence(f"Closest {signal.cluster.lower()} anchor with a concrete result hook on {task_phrase}: {result}", limit=180),
                "what_to_extract": clean_sentence(f"Extract the metric and comparator, then check whether {profile['reading_extract']}.", limit=180),
                "current_hook": clean_sentence(result, limit=180),
                "kill_signal": clean_sentence(f"Weaken this direction if the paper already shows {profile['kill_signal']}.", limit=180),
            })
        why_this_ranks_here = clean_sentence(profile['priority_note'], limit=170)
        cards.append(DirectionCard(
            direction_id=f"DIR-{idx:03d}",
            cluster=signal.cluster,
            direction_type=signal.direction_type,
            title=_title_from_signal(signal),
            focus_axis=signal.possible_axis,
            main_confound=profile['confound'],
            program_kind=profile['program_kind'],
            contribution_shape=profile['contribution_shape'],
            time_to_clarity=profile['time_to_clarity'],
            one_line_thesis=one_line_thesis,
            why_interesting=why_interesting,
            literature_suggests=literature_suggests,
            closest_prior_gap=closest_prior_gap,
            missing_piece=missing_piece,
            possible_variants=possible_variants,
            academic_value=profile['contribution_shape'],
            first_probes=first_probes,
            what_counts_as_insight=what_counts_as_insight,
            weakness_conditions=weakness_conditions,
            kill_criteria=kill_criteria,
            what_would_change_mind=kill_criteria,
            best_fit=_best_fit(signal.direction_type, signal.possible_axis),
            why_this_ranks_here=why_this_ranks_here,
            evidence_confidence=signal.evidence_confidence,
            paper_ids=signal.paper_ids,
            signal_ids=[signal.signal_id],
            anchor_reading_notes=anchor_reading_notes,
        ))
    # Distinctness guard: two signals whose (axis, cluster) collapse to the same
    # normalized phrase — e.g. "... Distribution Shifts" vs "... Distribution
    # Shift" — otherwise produce near-identical direction cards ("What feedback
    # type is really doing in ...") that read as one confound template repeated.
    # Drop the later near-duplicate, keeping the first (higher-ranked) card.
    deduped: list[DirectionCard] = []
    seen_keys: set[str] = set()
    for card in cards:
        key = _direction_distinctness_key(card)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(card)
    cards = deduped
    cards.sort(key=lambda c: (0 if _cluster_matches_focus(c.cluster, focus) else 1, c.cluster, c.program_kind, c.title))
    target = max(pool_min, min(pool_max, len(cards)))
    return cards[:target]


def _direction_distinctness_key(card: "DirectionCard") -> str:
    """Normalized THESIS identity for near-duplicate direction detection.

    A direction's thesis line is defined by its program kind + the axis it
    isolates + the confound it controls for — NOT by which domain cluster it is
    filed under. Two cards sharing (program_kind, focus_axis, main_confound) are
    the same thesis restated on a different application domain (e.g. "feedback
    type ... in Distribution Shifts" vs "... in Time Series") and read as one
    confound template repeated. Keying on the thesis identity collapses those;
    genuinely different mechanisms or confounds stay distinct. Falls back to the
    cluster when axis/confound are absent (older cards).

    The axis/confound fold is order-insensitive and strips generic filler words
    (articles, prepositions, wh-words) so pure wording variants of the SAME axis
    also collapse: "feedback type", "the type of feedback" -> one key. Variants
    that add a real content token ("feedback signal type", "feedback modality")
    stay distinct, since treating those as identical needs synonymy (LLM-bound).
    """

    def _fold(text: str) -> str:
        # Order-insensitive content-token set: lowercased, plural-folded, generic
        # fillers dropped. Collapses word-order and filler-word wording variants.
        tokens = re.findall(r"[a-z0-9]+", str(text or "").casefold())
        content = [
            (tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok)
            for tok in tokens
            if tok not in _AXIS_FILLER_WORDS
        ]
        return " ".join(sorted(set(content)))

    axis = _fold(card.focus_axis)
    confound = _fold(getattr(card, "main_confound", ""))
    identity = f"{axis}|{confound}".strip("|")
    if not identity:
        identity = _fold(card.cluster)
    return f"{card.program_kind.casefold()}|{identity}"


# Generic filler words dropped from a direction's axis/confound fold so pure
# wording variants ("feedback type" vs "the type of feedback") collapse to one
# distinctness key. Domain/content words (e.g. "type", "signal", "modality") are
# deliberately NOT here — collapsing those needs synonymy, which is out of scope.
_AXIS_FILLER_WORDS = frozenset(
    {
        "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "that",
        "this", "is", "are", "its", "by", "with", "how", "what", "whether",
        "when", "where", "which", "as", "at", "from", "into", "under", "over",
    }
)



def direction_pool_markdown(cards: list[DirectionCard]) -> str:
    rows: list[list[str]] = []
    for card in cards:
        rows.append([
            card.direction_id,
            card.cluster,
            card.direction_type,
            card.program_kind,
            card.title,
            clean_sentence(card.one_line_thesis, limit=100),
            clean_sentence(card.why_interesting, limit=100),
            clean_sentence(card.missing_piece, limit=100),
            clean_sentence(" / ".join(card.possible_variants), limit=120),
            clean_sentence(card.academic_value, limit=90),
            clean_sentence(" / ".join(card.first_probes), limit=120),
            card.evidence_confidence,
            ", ".join(card.paper_ids),
        ])
    return "\n".join([
        "# IDEA_DIRECTION_POOL",
        "",
        "## Candidate research directions",
        "",
        markdown_table(["Direction ID", "Cluster", "Type", "Program", "Title", "One-line thesis", "Why interesting", "Missing piece", "Possible variants", "Academic value", "First probes", "Confidence", "Paper IDs"], rows),
        "",
    ])


def _thesis_potential(direction_type: str, cluster: str) -> int:
    if direction_type in {"mechanism", "coordination", "adaptation"}:
        return 5
    if direction_type in {"systems", "governance"}:
        return 4
    if "benchmark" in cluster.lower() or direction_type == "evaluation":
        return 3
    return 4


def score_direction_cards(
    cards: list[DirectionCard],
    *,
    focus_clusters: list[str],
    keep_rank_max: int,
    maybe_rank_max: int,
    score_weights: dict[str, float] | None = None,
) -> list[ScreenedDirection]:
    focus = {x.strip() for x in focus_clusters if str(x).strip()}
    keep_rank_max = int(keep_rank_max)
    maybe_rank_max = int(maybe_rank_max)
    if keep_rank_max <= 0:
        raise ValueError("Invalid ideation scoring contract: keep_rank_max must be positive.")
    if maybe_rank_max < keep_rank_max:
        raise ValueError("Invalid ideation scoring contract: maybe_rank_max must be >= keep_rank_max.")
    weights = _validate_score_weights(score_weights or {}, field_name="score_direction_cards.score_weights")
    cluster_counts: dict[str, int] = {}
    program_counts: dict[str, int] = {}
    for card in cards:
        cluster_counts[card.cluster] = cluster_counts.get(card.cluster, 0) + 1
        program_counts[card.program_kind] = program_counts.get(card.program_kind, 0) + 1

    provisional: list[tuple[DirectionCard, float, int, int, int, int, int, int]] = []
    for card in cards:
        discussion_worthiness = 5 if _cluster_matches_focus(card.cluster, focus) or card.time_to_clarity == "fast" else 4
        academic_value_score = 5 if any(token in card.contribution_shape.lower() for token in ["rule", "protocol", "regime map", "causal"]) else 4
        concrete_hooks = sum(1 for item in card.literature_suggests if _sentence_has_concrete_hook(item))
        evidence_grounding = 5 if len(card.paper_ids) >= 3 and concrete_hooks >= 2 else 4 if len(card.paper_ids) >= 2 and concrete_hooks >= 1 else 3
        if program_counts.get(card.program_kind, 0) == 1 and cluster_counts.get(card.cluster, 0) == 1:
            direction_distinctness = 5
        elif program_counts.get(card.program_kind, 0) == 1 or cluster_counts.get(card.cluster, 0) == 1:
            direction_distinctness = 4
        else:
            direction_distinctness = 3
        probe_blob = " ".join(card.first_probes).lower()
        first_probe_clarity = 5 if all(token in probe_blob for token in ["intervention:", "readout:", "decisive if"]) else 4 if "intervention:" in probe_blob else 3
        thesis_potential = _thesis_potential(card.direction_type, card.cluster)
        total = round(
            discussion_worthiness * weights["discussion_worthiness"]
            + academic_value_score * weights["academic_value"]
            + evidence_grounding * weights["evidence_grounding"]
            + direction_distinctness * weights["direction_distinctness"]
            + first_probe_clarity * weights["first_probe_clarity"]
            + thesis_potential * weights["thesis_potential"],
            2,
        )
        provisional.append((card, total, discussion_worthiness, academic_value_score, evidence_grounding, direction_distinctness, first_probe_clarity, thesis_potential))
    provisional.sort(key=lambda row: (-row[1], 0 if row[0].time_to_clarity == "fast" else 1, row[0].cluster, row[0].title))
    rows: list[ScreenedDirection] = []
    for idx, (card, total, dw, av, eg, dd, fp, tp) in enumerate(provisional, start=1):
        recommendation = "keep" if idx <= keep_rank_max else "maybe" if idx <= maybe_rank_max else "drop"
        strengths: list[str] = []
        if eg >= 5:
            strengths.append("concrete anchor evidence")
        if dd >= 5:
            strengths.append(f"distinct {card.program_kind} wedge")
        if fp >= 5:
            strengths.append("clean first probe")
        if av >= 5:
            strengths.append("thesis-sized payoff")
        if not strengths:
            strengths.append("discussion value")
        risk = "still abstract-first" if str(card.evidence_confidence).startswith("low") else f"main risk is controlling {card.main_confound} cleanly"
        # Make the rationale DIRECTION-SPECIFIC (name this direction's own focus
        # axis) and DECISION-CONSISTENT (a "maybe"/"drop" must not read identically
        # to a "keep"): score-flag boilerplate alone gave sibling directions the
        # same rationale, and even paired the same text with different decisions.
        axis = str(getattr(card, "focus_axis", "") or "").strip() or str(card.title or "").strip()
        if recommendation == "keep":
            decision_frame = f"Keep — {axis} is strongest on"
        elif recommendation == "maybe":
            decision_frame = f"Maybe — {axis} rests on"
        else:
            decision_frame = f"Drop — {axis} offers only"
        rationale = clean_sentence(
            f"{decision_frame} {' + '.join(strengths[:2])}; {risk}.", limit=180
        )
        rows.append(ScreenedDirection(
            direction_id=card.direction_id,
            cluster=card.cluster,
            direction_type=card.direction_type,
            title=card.title,
            total_score=total,
            discussion_worthiness=dw,
            academic_value_score=av,
            evidence_grounding=eg,
            direction_distinctness=dd,
            first_probe_clarity=fp,
            thesis_potential=tp,
            recommendation=recommendation,
            rationale=rationale,
        ))
    return rows



def screening_table_markdown(rows: list[ScreenedDirection]) -> str:
    data: list[list[str]] = []
    for row in rows:
        data.append([
            row.direction_id,
            row.cluster,
            row.direction_type,
            row.title,
            f"{row.total_score:.2f}",
            str(row.discussion_worthiness),
            str(row.academic_value_score),
            str(row.evidence_grounding),
            str(row.direction_distinctness),
            str(row.first_probe_clarity),
            str(row.thesis_potential),
            row.recommendation,
            row.rationale,
        ])
    return "\n".join([
        "# IDEA_SCREENING_TABLE",
        "",
        "## Discussion-first screening",
        "",
        markdown_table(["Direction ID", "Cluster", "Type", "Title", "Total", "Discussion", "Academic value", "Evidence", "Distinctness", "First probe", "Thesis potential", "Decision", "Rationale"], data),
        "",
    ])


def shortlist_markdown(records: list[dict[str, Any]]) -> str:
    lines = ["# IDEA_SHORTLIST", "", "## Prioritized directions", ""]
    for record in records:
        lines.extend([
            f"### Direction {record['rank']}. {record['title']}",
            f"- Cluster: {record['cluster']}",
            f"- Type: {record['direction_type']}",
            f"- Focus axis: {record.get('focus_axis')}",
            f"- Program kind: {record.get('program_kind')}",
            f"- Main confound: {record.get('main_confound')}",
            f"- Time to clarity: {record.get('time_to_clarity')}",
            f"- One-line thesis: {record['one_line_thesis']}",
            f"- Why this is interesting: {record['why_interesting']}",
            f"- Why this ranks here: {record['why_this_ranks_here']}",
            f"- Contribution shape: {record.get('contribution_shape')}",
            "- What the literature already suggests:",
        ])
        for item in record.get("literature_suggests") or []:
            lines.append(f"  - {item}")
        lines.extend([
            "- Closest prior work and why it does not settle the question:",
        ])
        for item in record.get("closest_prior_gap") or []:
            lines.append(f"  - {item}")
        lines.extend([
            f"- What is still missing: {record['missing_piece']}",
            "- Possible variants:",
        ])
        for item in record.get("possible_variants") or []:
            lines.append(f"  - {item}")
        lines.extend([
            f"- Why this could matter academically: {record['academic_value']}",
            "- First probes:",
        ])
        for item in record.get("first_probes") or []:
            lines.append(f"  - {item}")
        lines.extend([
            f"- What would count as actual insight: {record['what_counts_as_insight']}",
            "- What would make this weak or unconvincing:",
        ])
        for item in record.get("weakness_conditions") or []:
            lines.append(f"  - {item}")
        lines.extend([
            "- Quick kill criteria:",
        ])
        for item in record.get("kill_criteria") or record.get("what_would_change_mind") or []:
            lines.append(f"  - {item}")
        lines.extend([
            f"- Best fit: {record['best_fit']}",
            f"- Evidence confidence: {record['evidence_confidence']}",
            "- Anchor papers: " + ", ".join(f"`{pid}`" for pid in record.get("paper_ids") or []),
            f"- Why prioritized now: {record['why_prioritized']}",
            "",
        ])
    return "\n".join(lines)



def shortlist_snapshot_table(records: list[dict[str, Any]]) -> str:
    rows = []
    for rec in records:
        rows.append([
            str(rec.get("rank") or ""),
            rec.get("title", ""),
            _glance_cell(rec.get("why_this_ranks_here", "")),
            _glance_cell(rec.get("contribution_shape", rec.get("academic_value", ""))),
            _glance_cell((rec.get("kill_criteria") or rec.get("what_would_change_mind") or [""])[0]),
        ])
    # The middle column is fed `why_this_ranks_here` — a rank-placement rationale
    # ("Leads because ...", "Ranks behind X ...", "Stays in the lead set ..."), NOT
    # a timeliness statement. Heading it "Why now" promised a timeliness reason the
    # cells never give; "Why this rank" matches what the column actually says.
    return markdown_table(["Rank", "Direction", "Why this rank", "If it survives", "Fast kill signal"], rows)


# Trailing function words that must not END a glance-table cell — a cell cut on
# "...to a" / "...vs" / "...already fixes the" reads as a broken fragment. This
# also includes object-requiring prepositions ("isolates X against", "varies Y
# into") whose object is lost when the cell is cut just after them, so the cell
# must back off to the last content word rather than dangle on the preposition.
_GLANCE_DANGLING = frozenset({
    "a", "an", "the", "to", "of", "and", "or", "but", "plus", "vs", "with", "for",
    "in", "on", "at", "by", "from", "into", "than", "as", "that", "which", "while",
    "because", "if", "it", "its", "their", "this", "these", "so", "up", "over",
    "against", "between", "among", "across", "toward", "towards", "onto", "off",
    "about", "via", "per", "versus", "vs.", "isolating", "holding", "varying",
})


def _glance_cell(text: str, *, max_len: int = 90) -> str:
    """A self-contained short phrase for the 'at a glance' table.

    The source rationales are full sentences, so a hard character truncation left
    cells dangling mid-clause ("Leads because it offers the fastest path to a").
    Instead, cut at the first clause boundary (sentence terminator or a coordinating
    ", and/but/because/..."), then to the last whole word within ``max_len``, then
    drop any trailing function word / object-requiring preposition so the cell ends
    on content, not on "to a" or "isolates X against".
    """
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return ""
    match = re.search(r"[.;]|,\s+(?:and|but|because|so|while|which|which,)\b", s)
    clause = s[: match.start()].strip() if match else s
    if len(clause) > max_len:
        head = clause[:max_len]
        cut = head.rfind(" ")
        clause = head[:cut] if cut > 0 else head
    words = clause.split()
    # Drop trailing dangling words AND any orphaned punctuation token (a bare "/"
    # or "-" left when a slash-joined scope like "large / adapted" is cut after
    # the slash), so the cell never ends on "for large /" or "isolates X against".
    while words and (
        words[-1].lower().strip(",;:-") in _GLANCE_DANGLING
        or not re.search(r"[A-Za-z0-9]", words[-1])
    ):
        words.pop()
    return " ".join(words).rstrip(" ,;:-/")



def build_report_payload(*, topic: str, shortlist: list[dict[str, Any]], deferred: list[dict[str, Any]], trace_paths: dict[str, str]) -> dict[str, Any]:
    top = list(shortlist)
    takeaways: list[str] = []
    if top:
        takeaways.append("The strongest directions are the ones most likely to change how existing results are interpreted, not just add another benchmark win.")
        takeaways.append("The current rank order reflects a tradeoff between time-to-clarity, thesis-sized payoff, and how concrete the nearest prior-work gap already looks.")
        program_kinds = uniq_keep_order(str(rec.get("program_kind") or "").strip() for rec in top)
        if len(program_kinds) >= 2:
            takeaways.append(f"The lead set is intentionally not one confound template repeated three times: it spans {', '.join(program_kinds[:3])} rather than a single explanatory mold.")
        else:
            takeaways.append("The lead set still sits in one tight neighborhood, so the next reading pass should stress-test whether those directions are genuinely distinct thesis lines.")
        if any(str(rec.get("evidence_confidence") or "").startswith("low") for rec in top):
            takeaways.append("Most anchors are still abstract-first, so the memo is best used to decide the next reading and falsification pass rather than to lock a project immediately.")
        else:
            takeaways.append("The evidence is already concrete enough for a serious PI/PhD discussion, though one deeper paper pass could still reshuffle the exact order.")
    lead = top[0] if top else {}
    lead_anchor = (lead.get("anchor_reading_notes") or [{}])[0] if top else {}
    # Cap the (variable-length) anchor paper title so it does not push the §9
    # next-step directive past its limit and clip the actionable clause.
    _lead_anchor_title_raw = lead_anchor.get("paper_title") if isinstance(lead_anchor, dict) else "the first anchor paper"
    lead_anchor_title = clean_title(_lead_anchor_title_raw or "the first anchor paper")
    discussion_questions = [
        "Which direction still survives once we ask for a single-variable control rather than a suggestive confound story?",
        "Which lead direction would still matter if the nearest prior work already addressed the obvious control we are worried about?",
        "Which candidate could plausibly turn into a thesis line with a reusable method, protocol, or regime map rather than a one-off empirical note?",
        "Which ranking would change most after one full-paper reading pass on the anchor set?",
    ]
    uncertainties = [
        "The main remaining risk is novelty risk, not idea scarcity: closer reading may reveal that one lead direction is already settled by an existing control or ablation.",
        "Evidence confidence is still bounded by abstract-first notes for part of the lead set, so paper-specific details could either strengthen or kill a direction quickly.",
        "The memo is more reliable as a discussion and triage artifact than as a final commitment on exact project order.",
    ]
    next_steps = []
    if top:
        next_steps.append(clean_sentence(f"Start with {lead.get('title')}: read {lead_anchor_title or 'the first anchor paper'} looking specifically for whether {lead.get('focus_axis')} is already isolated against {lead.get('main_confound')}.", limit=300))
        first_probe = (lead.get("first_probes") or [""])[0]
        if first_probe:
            next_steps.append(clean_sentence(first_probe, limit=220))
        next_steps.append(clean_sentence(f"Re-rank only after checking the quick kill criteria for {lead.get('title')} and at least one competing direction in the lead set.", limit=220))
    else:
        next_steps.extend([
            "Read the anchor papers for the current top direction in full and test whether the memo's stated hidden variable still looks unresolved.",
            "In the next PI/PhD discussion, use the ranking arguments and kill criteria to decide whether any direction deserves promotion into a sharper thesis candidate.",
        ])
    return {
        "topic": topic,
        "takeaways": takeaways,
        "top_directions": top,
        "deferred_directions": deferred,
        "discussion_questions": discussion_questions,
        "uncertainties": uncertainties,
        "next_steps": next_steps,
        "trace_artifacts": trace_paths,
    }



def report_markdown(payload: dict[str, Any]) -> str:
    top_dirs = payload.get("top_directions") or []
    deferred_idx = 3 + len(top_dirs)
    discussion_idx = deferred_idx + 1
    uncertainty_idx = deferred_idx + 2
    next_idx = deferred_idx + 3
    appendix_idx = deferred_idx + 4
    lines = [
        "# Research Idea Brainstorm Memo",
        "",
        "## 0. Scope and framing",
        "",
        f"- Topic: {payload.get('topic') or 'research ideas'}",
        "- Intended readers: PI / PhD",
        "- Goal: surface a small number of discussion-worthy research directions rather than force a final project choice.",
        "- Current evidence basis: abstract-first notes unless otherwise stated.",
        "- What this memo is not: not a final project spec, not a survey draft, and not a symmetric top-3 proposal pack.",
        "",
        "## 1. Big-picture takeaways",
        "",
    ]
    for item in payload.get("takeaways") or []:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## 2. Top directions at a glance",
        "",
        shortlist_snapshot_table(payload.get("top_directions") or []),
        "",
    ])
    for idx, record in enumerate(top_dirs, start=1):
        lines.extend([
            f"## {idx + 2}. Direction {idx} — {record.get('title')}",
            "",
            "### One-line thesis",
            f"- {record.get('one_line_thesis')}",
            "",
            "### Why it belongs in the lead set",
            f"- {record.get('why_this_ranks_here')}",
            f"- Time to clarity: {record.get('time_to_clarity')}",
            "",
            "### What the current literature actually shows",
        ])
        for item in record.get("literature_suggests") or []:
            lines.append(f"- {item}")
        lines.extend([
            "",
            "### Closest prior work and remaining gap",
        ])
        for item in record.get("closest_prior_gap") or []:
            lines.append(f"- {item}")
        lines.extend([
            f"- Missing piece: {record.get('missing_piece')}",
            "",
            "### If this direction is right, what contribution emerges",
            f"- {record.get('contribution_shape') or record.get('academic_value')}",
            f"- {record.get('what_counts_as_insight')}",
            "",
            "### Smallest decisive probe",
        ])
        for item in record.get("first_probes") or []:
            lines.append(f"- {item}")
        lines.extend([
            "",
            "### Quick kill criteria",
        ])
        for item in record.get("kill_criteria") or record.get("what_would_change_mind") or []:
            lines.append(f"- {item}")
        lines.extend(["",])
    lines.extend([
        f"## {deferred_idx}. Other promising but not prioritized directions",
        "",
    ])
    deferred = payload.get("deferred_directions") or []
    if deferred:
        for record in deferred:
            lines.append(f"- **{record.get('title')}** — {record.get('one_line_thesis')} (why not prioritized now: {record.get('why_not_prioritized')})")
    else:
        lines.append("- No additional deferred directions were retained in the current memo.")
    lines.extend([
        "",
        f"## {discussion_idx}. Cross-cutting discussion questions",
        "",
    ])
    for item in payload.get("discussion_questions") or []:
        lines.append(f"- {item}")
    lines.extend([
        "",
        f"## {uncertainty_idx}. Uncertainty and disagreement",
        "",
    ])
    for item in payload.get("uncertainties") or []:
        lines.append(f"- {item}")
    lines.extend([
        "",
        f"## {next_idx}. Suggested next reading / next discussion step",
        "",
    ])
    for item in payload.get("next_steps") or []:
        lines.append(f"- {item}")
    lines.extend([
        "",
        f"## {appendix_idx}. Appendix guide",
        "",
        "- `output/APPENDIX.md` for anchor-paper reading notes and deferred directions.",
        "- `output/REPORT.json` for the structured version of this memo.",
    ])
    return "\n".join(lines)



def appendix_markdown(payload: dict[str, Any], *, core_titles: dict[str, str]) -> str:
    lines = [
        "# Appendix to the Research Idea Brainstorm Memo",
        "",
        "## A. Deferred but still promising directions",
        "",
    ]
    deferred = payload.get("deferred_directions") or []
    if deferred:
        for rec in deferred:
            lines.extend([
                f"### {rec.get('title')}",
                f"- One-line thesis: {rec.get('one_line_thesis')}",
                f"- Program kind: {rec.get('program_kind')}",
                f"- Why interesting: {rec.get('why_interesting')}",
                f"- Why not prioritized now: {rec.get('why_not_prioritized')}",
                "",
            ])
    else:
        lines.append("- (none)")
    lines.extend([
        "## B. Anchor papers and what to extract",
        "",
    ])
    for rec in payload.get("top_directions") or []:
        lines.append(f"### {rec.get('title')}")
        lines.append(f"- Program kind: {rec.get('program_kind')}")
        lines.append(f"- Lead-set reason: {rec.get('why_this_ranks_here')}")
        notes = rec.get("anchor_reading_notes") or []
        if notes:
            rows: list[list[str]] = []
            for item in notes:
                if not isinstance(item, dict):
                    continue
                rows.append([
                    item.get("paper_title", "paper"),
                    item.get("why_read", ""),
                    item.get("what_to_extract", ""),
                    item.get("current_hook", ""),
                    item.get("kill_signal", ""),
                ])
            if rows:
                lines.append(markdown_table(["Anchor paper", "Why read now", "What to extract", "Current evidence hook", "Kill signal"], rows))
            else:
                for pid in rec.get("paper_ids") or []:
                    title = core_titles.get(pid, pid)
                    lines.append(f"- {title}")
        else:
            for pid in rec.get("paper_ids") or []:
                title = core_titles.get(pid, pid)
                lines.append(f"- {title}")
        lines.append("")
    return "\n".join(lines)
