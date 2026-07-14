from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PACKAGE_ROOT / "assets"
POLICY_PATH = ASSETS_DIR / "evidence_policy.json"
SCHEMA_PATH = ASSETS_DIR / "evidence_pack_schema.json"
SOURCE_HYGIENE_PATH = ASSETS_DIR / "source_text_hygiene.json"


def _load_optional_json_asset(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


_SOURCE_HYGIENE = _load_optional_json_asset(SOURCE_HYGIENE_PATH)


def _compile_hygiene_pattern(key: str, default: str) -> re.Pattern[str]:
    pattern = str(_SOURCE_HYGIENE.get(key) or default).strip()
    return re.compile(pattern)


def _compile_hygiene_pattern_list(key: str, default: list[str]) -> list[re.Pattern[str]]:
    raw = _SOURCE_HYGIENE.get(key)
    if not isinstance(raw, list):
        raw = default
    out: list[re.Pattern[str]] = []
    for item in raw:
        pattern = str(item or "").strip()
        if pattern:
            out.append(re.compile(pattern))
    return out


_EVAL_STOP = {
    "ai",
    "ml",
    "llm",
    "nlp",
    "cv",
    "arxiv",
    "dataset",
    "datasets",
    "benchmark",
    "benchmarks",
    "metric",
    "metrics",
    "diffusion",
    "transformer",
}
_TOPIC_STOPWORDS = {
    "and",
    "the",
    "with",
    "from",
    "into",
    "across",
    "under",
    "over",
    "between",
    "task",
    "tasks",
    "study",
    "studies",
    "design",
    "system",
    "systems",
    "model",
    "models",
    "method",
    "methods",
    "paper",
    "papers",
    "evaluation",
    "protocol",
}

_URL_RE = re.compile(r"https?://\S+")
_AVAILABILITY_VERB_RE = re.compile(
    r"(?i)\b(?:is|are|was|were|will\s+be|can\s+be|has\s+been)?\s*(?:publicly\s+)?(?:available|released|open-?sourced|shared)\b"
)
_LEADING_SELF_REF_RE = re.compile(
    r"(?i)^(?:to (?:address|overcome|tackle|mitigate|study|investigate|examine|understand|analyze|explore|bridge|enhance|improve)[^,]{0,180},\s*)?"
    r"(?:(?:in|throughout)\s+(?:this|our)\s+(?:survey|paper|work|study|article),?\s*)?"
)
_LEADING_CONTEXT_RE = _compile_hygiene_pattern(
    "leading_context_pattern",
    r"(?i)^(?:building on this foundation|against this backdrop|in this context|to this end|towards this end|specifically|for example|based on this proposition|throughout [^,]{1,120}|moreover|furthermore|additionally),?\s*",
)
_LEADING_AUTHOR_FINDING_RE = _compile_hygiene_pattern(
    "leading_author_finding_pattern",
    r"(?i)^(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:(?:also|further|furthermore|empirically|experimentally)\s+)?(?:show|shows|find|finds|observe|observes|demonstrate|demonstrates|quantify|quantifies|reveal|reveals|indicate|indicates)\s+that\s+",
)
_LEADING_AUTHOR_PREDICATE_RE = _compile_hygiene_pattern(
    "leading_author_predicate_pattern",
    r"(?i)^(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:(?:also|further|furthermore|empirically|experimentally)\s+)?(?:show|shows|find|finds|observe|observes|demonstrate|demonstrates|reveal|reveals|indicate|indicates)\s+",
)
_LEADING_AUTHOR_ACTION_RE = _compile_hygiene_pattern(
    "leading_author_action_pattern",
    r"(?i)^(?:here,\s*)?(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:(?:also|broadly|comprehensively)\s+)?(?:introduce|present|propose|develop|describe|compare|conduct|discuss|summarize|review|explore|analyze|evaluate|quantify|study|design|build|construct|divide)\b[^,]{0,160},\s*",
)
_LEADING_PARTICIPLE_RE = re.compile(
    r"(?i)^(?:demonstrating|showing|finding|observing|revealing|indicating|suggesting)\s+that\s+"
)
_FRAGMENT_PARTICIPLE_RE = re.compile(r"(?i)^(?:demonstrating|showing|revealing|highlighting|indicating)\b")
_PROMISSORY_SELF_NARRATION_RE = re.compile(
    r"(?i)^(?:we\s+hope|we\s+aim|our\s+(?:survey|paper|work|study)\s+aims?|this\s+(?:survey|paper|work|study)\s+aims?)\b"
)
_LEADING_DISCOURSE_RE = re.compile(r"(?i)^(?:moreover|furthermore|additionally|in addition),\s*")
_POST_ACTION_ARTIFACT_RE = re.compile(r"^([A-Z][A-Za-z0-9._-]{1,80}),\s+(.*)$")
_NAMED_ARTIFACT_RE = re.compile(
    r"(?i)^(?:here,\s*)?(?:we|the authors)\s+(?:introduce|present|propose|develop|describe)\s+([A-Z][A-Za-z0-9][^,.;:]{0,120}),\s+(.*)$"
)
_GENERIC_SELF_NARRATION_RE = re.compile(
    r"(?i)^(?:(?:here,\s*)?(?:we|our)\s+(?:(?:also|broadly|comprehensively)\s+)?"
    r"(?:introduce|present|propose|develop|describe|compare|conduct|discuss|summarize|review|explore|analyze|evaluate|study|design|build|construct|divide)|"
    r"our\s+(?:approach|method|framework|pipeline|system|model)\s+(?:facilitates?|enables?|allows?|uses?))\b"
)
_STUDY_SELF_NARRATION_RE = re.compile(r"(?i)^(?:this|our)\s+(?:survey|paper|work|study|article|thesis|manuscript|dissertation)\b")
_LEADING_CONCESSION_RE = re.compile(r"(?i)^(?:while|but|yet|however|nevertheless|in contrast)\s+")
_LEADING_WHERE_ARTIFACT_RE = _compile_hygiene_pattern(
    "leading_where_artifact_pattern",
    r"(?i)^where\s+([A-Z][A-Za-z0-9._-]{1,80})\s+",
)
_RELATIVE_CLAUSE_ARTIFACT_RE = _compile_hygiene_pattern(
    "relative_clause_artifact_pattern",
    r"^([A-Z][A-Za-z0-9._-]{1,80}),\s+(?:which|that)\s+",
)
_FINITE_VERB_RE = re.compile(
    r"(?i)\b(?:is|are|was|were|has|have|had|can|may|might|does|do|did|remains?|becomes?|"
    r"shows?|finds?|demonstrates?|reports?|reveals?|suggests?|indicates?|outperforms?|improves?|"
    r"reduces?|increases?|enables?|supports?|validates?|requires?|limits?|fails?|lacks?|degrades?|bridges?|prevents?|yields?|"
    r"evaluates?|assesses?|compares?|measures?|introduces?|proposes?|conducts?|captures?|distinguishes?|examines?)\b"
)
_SURVEY_META_SENTENCE_RE = re.compile(
    r"(?i)\b(?:survey|review)\b.*\b(?:categoriz|summariz|overview|taxonomy|landscape|scope|history|promising directions?)\b|"
    r"\bmain contribution\b|\bsynthesis of\b|\bidentification of promising directions\b|\btrace the history\b|"
    r"\bthree key findings mapped to these axes\b"
)
_META_PAPER_TITLE_RE = re.compile(r"(?i)\b(?:survey|review|overview|taxonomy)\b")
_GENERIC_EVIDENCE_RE = re.compile(
    r"(?i)^(?:"
    r"recent advances? in|"
    r"evaluations?\s+are\s+critical\s+to|"
    r"generalist robot policies?,\s+trained on|"
    r"vision-language-action\s+\(vla\)\s+models\s+have\s+advanced|"
    r"this field is exploding|"
    r"offering great potential|"
    r"in this thesis\b|"
    r"the results demonstrate that\b|"
    r"one key challenge in this context is\b|"
    r"large real-world robot datasets hold great potential\b|"
    r"internet-scale data has enabled broad reasoning capabilities\b|"
    r"language models are often used to interact with human beings through dialogue\b|"
    r"three key findings mapped to these axes\b|"
    r"it comprises [A-Z][A-Za-z0-9-]+(?:-[A-Za-z0-9-]+)*\b|"
    r"to support this, we present [A-Z][A-Za-z0-9.-]+\b"
    r")"
)
_EMBODIED_CONTEXT_RE = re.compile(
    r"(?i)\b(?:robot|robotic|embod|manipulation|navigation|policy|action|control|real-world|simulation|benchmark|dataset|"
    r"task|transfer|generalization|latency|failure|robust|deployment|safety|LIBERO|Bridge|RT-2|OpenVLA|ManiSkill|RoboCasa|MOTIF)\b"
)
_CONCRETE_CLAIM_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b|\b[A-Z]{2,}(?:-[A-Z0-9]+)*\b|\b[A-Z][a-z]+[A-Z][A-Za-z0-9-]*\b")
_WRITER_UNSAFE_SNIPPET_RE = re.compile(
    r"(?i)^molmospaces-bench\s+exhibits\s+strong\s+sim-to-real\s+correlation\b.*\bconfirm\b.*\bidentify\b|"
    r"^these\s+models\s+can\s+simulate\s+realistic\s+visual\s+outcomes\b|"
    r"^general\s+visual\s+representations\s+learned\s+from\s+web-scale\s+datasets\b|"
    r"^vision-language-action\s*\(vla\)\s+models?\s+achieve\s+strong\s+generalization\b|"
    r"^robot\s+learning\s+from\s+interacting\s+with\s+the\s+physical\s+world\s+is\s+fundamentally\s+bottlenecked\b|"
    r"^language-guided\s+long-horizon\s+mobile\s+manipulation\s+has\s+long\s+been\s+a\s+grand\s+challenge\b|"
    r"^simulation\s+has\s+great\s+potential\s+in\s+supplementing\s+large-scale\s+data\b|"
    r"^a\s+robotic\s+foundation\s+model\s+built\s+upon\b|"
    r"^agentworld\s+is\s+an\s+interactive\s+simulation\s+platform\b|"
    r"^it\s+typically\s+relies\s+on\s+large\s+amounts\s+of\s+human\s+demonstration\s+data\b|"
    r"^recent\s+approaches\s+attempt\s+to\s+mitigate\s+these\s+limitations\b|"
    r"^existing\s+manipulation\s+datasets\s+remain\s+costly\s+to\s+curate\b|"
    r"^learning\s+visuomotor\s+policy\s+for\s+multi-task\s+robotic\s+manipulation\s+has\s+been\s+a\s+long-standing\s+challenge\b|"
    r"^training\s+vision-language-action\s*\(vla\)\s+models\s+for\s+generalist\s+robots\s+typically\s+requires\b|"
    r"^robot\s+learning\s+is\s+witnessing\s+a\s+significant\s+increase\b|"
    r"^the\s+acquisition\s+of\s+large-scale\s+physical\s+interaction\s+data\b|"
    r"^despite\s+rapid\s+advances\s+in\s+learning-based\s+planning\s+and\s+control\b|"
    r"^three\s+fundamental\s+limitations\s+hinder\s+progress\b|"
    r"^while\s+vlm\s+backbones\s+endow\s+vlas\s+with\s+robust\s+perceptual\s+understanding\b|"
    r"^video\s+models\s+enable\s+photorealistic,\s+physically\s+consistent\s+deformable-body\s+simulation\b|"
    r"^prior\s+works\s+have\s+explored\s+leveraging\s+human\s+demonstrations\b|"
    r"^building\s+a\s+generalist\s+robot\s+that\s+can\s+perceive,\s+reason,\s+and\s+act\s+across\s+diverse\s+tasks\s+remains\s+an\s+open\s+challenge\b|"
    r"^offering\s+great\s+potential\s+in\s+robotic\s+manipulation\b|"
    r"^i\s+will\s+discuss\s+selected\s+works\s+on\s+two\s+domains\b|"
    r"^to\s+support\s+systematic\s+training\s+and\s+evaluation,\s+we\s+curate\s+two\s+benchmarks\b|"
    r"^all\s+demonstrations\s+are\s+gathered\s+using\s+a\s+consistent\s+robotic\s+embodiment\b"
)
_CLAIM_PORTABILITY_RE = re.compile(
    r"(?i)\b(?:\d+(?:\.\d+)?%?|outperform\w*|improv\w*|success\s+rate|correlation|transfer|generaliz\w*|"
    r"robust\w*|failure\w*|limit\w*|bottleneck|costs?|latenc\w*|benchmarks?|metrics?|datasets?|sim-to-real|ood|"
    r"accuracy|precision|recall|relevance|faithful\w*|attribution|grounded\w*|agreement|calibrat\w*|"
    r"valid\w*|stability|variance|degrad\w*|reliab\w*|sensitiv\w*|coverage|"
    r"effectiv\w*|utility|ranking|rerank\w*|chunk\w*|top-k|"
    r"real-world|novel\s+(?:task|object|scene|environment)|cross-embodiment)\b"
)
_GENERIC_SUMMARY_PATTERNS = _compile_hygiene_pattern_list(
    "generic_summary_patterns",
    [
        r"(?i)^benchmarks? are crucial for evaluating progress\b",
        r"(?i)^evaluations? are critical to assess progress\b",
        r"(?i)^recent work has advanced such general robot policies\b",
        r"(?i)^in this machine learning-focused workflow\b",
        r"(?i)^we benchmark our method against\b",
        r"(?i)^the experiments also provide an extensive evaluation\b",
    ],
)


def _load_json_asset(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        raise SystemExit(f"Missing required asset: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON asset {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid JSON asset root (need object): {path}")
    return data


def _runtime_policy() -> dict[str, Any]:
    return _load_json_asset(POLICY_PATH)


def _profile_thresholds(*, policy: dict[str, Any], profile: str, draft_profile: str) -> dict[str, int]:
    thresholds = policy.get("profile_thresholds") or {}
    default_cfg = thresholds.get("default") or {}
    profile_key = str(draft_profile or "").strip().lower().replace("-", "_")
    cfg = thresholds.get(profile_key) or default_cfg
    return {
        "min_snippets": int(cfg.get("min_snippets") or 12),
        "min_comparisons": int(cfg.get("min_comparisons") or 8),
        "min_limitations": int(cfg.get("min_limitations") or 5),
    }


def _block_message(policy: dict[str, Any], key: str, **kwargs: Any) -> str:
    template = str(((policy.get("block_messages") or {}).get(key) or "")).strip()
    if not template:
        return key
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def _downgrade_message(policy: dict[str, Any], key: str) -> str:
    return str(((policy.get("downgrade_messages") or {}).get(key) or key)).strip()


def _validate_pack_shape(pack: dict[str, Any], schema: dict[str, Any]) -> None:
    required = schema.get("required") or []
    if not isinstance(required, list):
        return
    missing = [str(k) for k in required if str(k) and k not in pack]
    if missing:
        raise SystemExit(f"Evidence pack missing required fields: {', '.join(missing)}")


def _has_numeric_evidence(evidence_snippets: list[dict[str, Any]]) -> bool:
    for item in evidence_snippets or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        if re.search(r"\b\d+(?:\.\d+)?%?\b", text):
            return True
    return False


def _snippet_specificity_score(text: str) -> int:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return -10
    low = s.lower()
    score = 0
    if _CONCRETE_CLAIM_RE.search(s):
        score += 3
    if re.search(r"(?i)\b(?:outperform\w*|baseline|versus|vs\.?|compared with|few-shot|zero-shot|real-world|simulation|ood|stress)\b", s):
        score += 2
    if _EMBODIED_CONTEXT_RE.search(s):
        score += 2
    if re.search(r"(?i)\b(?:benchmarks?|datasets?|metrics?|success|accuracy|latenc\w*|costs?|failure|robust|generaliz|transfer|effectiv\w*|utility|ranking|rerank\w*|chunk\w*)\b", s):
        score += 2
    if len(s) >= 120:
        score += 1
    if _GENERIC_EVIDENCE_RE.search(s):
        score -= 4
    if _SURVEY_META_SENTENCE_RE.search(s):
        score -= 5
    if re.search(r"(?i)\b(?:survey|review|history|taxonomy|landscape)\b", low):
        score -= 2
    return score


def _append_unique(items: list[str], value: str) -> None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if text and text not in items:
        items.append(text)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _topic_tokens(*, title: str, axes: list[str]) -> set[str]:
    raw = " ".join([str(title or "")] + [str(a or "") for a in (axes or [])])
    return {
        tok
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", raw.lower())
        if tok not in _TOPIC_STOPWORDS and len(tok) >= 4
    }


def _text_relevant_to_topic(text: str, *, title: str, axes: list[str]) -> bool:
    tokens = _topic_tokens(title=title, axes=axes)
    if not tokens:
        return True
    low = re.sub(r"\s+", " ", str(text or "").lower())
    return any(tok in low for tok in tokens)


def _claim_eligible(text: str) -> bool:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return False
    if _SURVEY_META_SENTENCE_RE.search(s) or _GENERIC_EVIDENCE_RE.search(s):
        return False
    if _WRITER_UNSAFE_SNIPPET_RE.search(s):
        return False
    return bool(_CLAIM_PORTABILITY_RE.search(s))


def _comparison_eligible(text: str) -> bool:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return False
    if _WRITER_UNSAFE_SNIPPET_RE.search(s):
        return False
    specificity = _snippet_specificity_score(s)
    if specificity < 2:
        return False
    return bool(_CLAIM_PORTABILITY_RE.search(s) or _EMBODIED_CONTEXT_RE.search(s))


def _assert_h3_cutover_ready(*, workspace: Path, consumer: str) -> None:
    from tooling.common import read_jsonl

    state_path = workspace / "outline" / "outline_state.jsonl"
    if not state_path.exists() or state_path.stat().st_size <= 0:
        return

    records = [rec for rec in read_jsonl(state_path) if isinstance(rec, dict)]
    if not records:
        return

    latest = records[-1]
    cutover_keys = {"structure_phase", "h3_status", "approval_status", "reroute_target", "retry_budget_remaining"}
    if not any(key in latest for key in cutover_keys):
        return

    h3_status = str(latest.get("h3_status") or "").strip().lower()
    if h3_status == "stable":
        return

    structure_phase = str(latest.get("structure_phase") or "").strip() or "unknown"
    reroute_target = str(latest.get("reroute_target") or "").strip() or "none"
    raise SystemExit(
        f"{consumer} is blocked until stable H3 ids exist: "
        f"`outline/outline_state.jsonl` reports h3_status={h3_status or 'missing'} "
        f"(structure_phase={structure_phase}, reroute_target={reroute_target})."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import ensure_dir, latest_outline_state, load_workspace_pipeline_spec, now_iso_seconds, parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()
    spec = load_workspace_pipeline_spec(workspace)
    if spec is not None and str(spec.structure_mode or "").strip() == "section_first":
        state = latest_outline_state(workspace)
        if not state:
            raise SystemExit("Missing outline_state.jsonl; run the section-first C2 planner pass before evidence-draft.")
        if str(state.get("structure_phase") or "").strip() != "decomposed" or str(state.get("h3_status") or "").strip() != "stable":
            raise SystemExit("Section-first cutover not ready: `outline_state.jsonl` must report `structure_phase: decomposed` and `h3_status: stable` before evidence-draft.")

    from tooling.quality_gate import _draft_profile, _pipeline_profile

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    policy = _runtime_policy()
    schema = _load_json_asset(SCHEMA_PATH)
    thresholds = _profile_thresholds(policy=policy, profile=profile, draft_profile=draft_profile)

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/subsection_briefs.jsonl",
        "papers/paper_notes.jsonl",
        "citations/ref.bib",
        "papers/evidence_bank.jsonl",
        "outline/evidence_bindings.jsonl",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/evidence_drafts.jsonl"]

    def _first(suffixes: tuple[str, ...], default: str) -> str:
        for raw in inputs:
            rel = str(raw or '').strip()
            if not rel:
                continue
            for suf in suffixes:
                if rel.endswith(suf):
                    return rel
        return default

    briefs_rel = _first(("outline/subsection_briefs.jsonl", "subsection_briefs.jsonl"), "outline/subsection_briefs.jsonl")
    notes_rel = _first(("papers/paper_notes.jsonl", "paper_notes.jsonl"), "papers/paper_notes.jsonl")
    bib_rel = _first(("citations/ref.bib", "ref.bib"), "citations/ref.bib")
    bank_rel = _first(("papers/evidence_bank.jsonl", "evidence_bank.jsonl"), "papers/evidence_bank.jsonl")
    bindings_rel = _first(("outline/evidence_bindings.jsonl", "evidence_bindings.jsonl"), "outline/evidence_bindings.jsonl")

    briefs_path = workspace / briefs_rel
    notes_path = workspace / notes_rel
    bib_path = workspace / bib_rel
    bank_path = workspace / bank_rel
    bindings_path = workspace / bindings_rel
    out_path = workspace / outputs[0]

    # Explicit freeze policy: only skip regeneration if the user creates `outline/evidence_drafts.refined.ok`.
    freeze_marker = out_path.parent / "evidence_drafts.refined.ok"
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

    _assert_h3_cutover_ready(workspace=workspace, consumer="evidence-draft")

    briefs = read_jsonl(briefs_path)
    if not briefs:
        raise SystemExit(f"Missing or empty briefs: {briefs_path}")

    notes = read_jsonl(notes_path)
    if not notes:
        raise SystemExit(f"Missing or empty notes: {notes_path}")

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    bibkeys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    notes_by_pid: dict[str, dict[str, Any]] = {}
    for rec in notes:
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("paper_id") or "").strip()
        if pid:
            notes_by_pid[pid] = rec

    # Optional: evidence bank + binder output (WebWeaver-style addressable memory).
    bank_by_eid: dict[str, dict[str, Any]] = {}
    if bank_path.exists() and bank_path.stat().st_size > 0:
        for rec in read_jsonl(bank_path):
            if not isinstance(rec, dict):
                continue
            eid = str(rec.get("evidence_id") or "").strip()
            if eid:
                bank_by_eid[eid] = rec

    bindings_by_sub: dict[str, dict[str, Any]] = {}
    if bindings_path.exists() and bindings_path.stat().st_size > 0:
        for rec in read_jsonl(bindings_path):
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            if sid:
                bindings_by_sub[sid] = rec

    records: list[dict[str, Any]] = []
    md_dir = workspace / "outline" / "evidence_drafts"
    ensure_dir(md_dir)

    for brief in briefs:
        if not isinstance(brief, dict):
            continue
        sub_id = str(brief.get("sub_id") or "").strip()
        title = str(brief.get("title") or "").strip()
        if not sub_id or not title:
            continue

        rq = str(brief.get("rq") or "").strip()
        scope_rule = brief.get("scope_rule") or {}

        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        clusters = brief.get("clusters") or []
        evidence_summary = brief.get("evidence_level_summary") or {}

        cited_pids = _pids_from_clusters(clusters)
        bound = bindings_by_sub.get(sub_id) or {}
        bound_eids = bound.get("evidence_ids") or []
        bound_pids = _pids_from_bound_evidence(bound_eids, bank_by_eid=bank_by_eid) if bank_by_eid else []
        support_pids = _dedupe_preserve_order(cited_pids + bound_pids)
        cite_keys = _cite_keys_for_pids(support_pids, notes_by_pid=notes_by_pid, bibkeys=bibkeys)

        evidence_snippets: list[dict[str, Any]] = []
        if isinstance(bound_eids, list) and bound_eids and bank_by_eid:
            for eid in bound_eids:
                eid = str(eid or '').strip()
                if not eid:
                    continue
                it = bank_by_eid.get(eid) or {}
                pid = str(it.get('paper_id') or '').strip()
                note = notes_by_pid.get(pid) or {}
                if _is_meta_paper_title(str(note.get('title') or '')):
                    continue
                bibkey = str(it.get('bibkey') or '').strip()
                if not bibkey or (bibkeys and bibkey not in bibkeys):
                    continue
                snippet = _sanitize_source_text(it.get('snippet') or '', sentence_limit=2)
                if not snippet:
                    continue
                lvl = str(it.get('evidence_level') or '').strip().lower() or 'unknown'
                locator = it.get('locator') or {}
                prov = {
                    'evidence_level': lvl,
                    'source': str((locator or {}).get('source') or '').strip() or 'evidence_bank',
                    'pointer': str((locator or {}).get('pointer') or '').strip() or f"papers/evidence_bank.jsonl:evidence_id={eid}",
                }
                evidence_snippets.append(
                    {
                        'evidence_id': eid,
                        'text': snippet,
                        'paper_id': pid,
                        'citations': [bibkey],
                        'provenance': prov,
                    }
                )
                if len(evidence_snippets) >= 18:
                    break
            represented = {str(item.get("paper_id") or "").strip() for item in evidence_snippets if isinstance(item, dict)}
            supplemental = _evidence_snippets(
                workspace=workspace,
                pids=[pid for pid in support_pids if pid not in represented],
                notes_by_pid=notes_by_pid,
                bibkeys=bibkeys,
                limit=max(0, 22 - len(evidence_snippets)),
                clusters=clusters,
            )
            seen_keys = {
                (
                    str(item.get("paper_id") or "").strip(),
                    re.sub(r"\s+", " ", str(item.get("text") or "").strip().lower()),
                )
                for item in evidence_snippets
                if isinstance(item, dict)
            }
            for item in supplemental:
                key = (
                    str(item.get("paper_id") or "").strip(),
                    re.sub(r"\s+", " ", str(item.get("text") or "").strip().lower()),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                evidence_snippets.append(item)
                if len(evidence_snippets) >= 22:
                    break
        else:
            evidence_snippets = _evidence_snippets(
                workspace=workspace,
                pids=support_pids,
                notes_by_pid=notes_by_pid,
                bibkeys=bibkeys,
                limit=22,
                clusters=clusters,
            )

        fulltext_n = int(evidence_summary.get("fulltext", 0) or 0) if isinstance(evidence_summary, dict) else 0
        abstract_n = int(evidence_summary.get("abstract", 0) or 0) if isinstance(evidence_summary, dict) else 0
        title_n = int(evidence_summary.get("title", 0) or 0) if isinstance(evidence_summary, dict) else 0

        verify_fields = _verify_fields(
            axes=axes,
            evidence_summary={"fulltext": fulltext_n, "abstract": abstract_n},
            policy=policy,
        )

        blocking_missing: list[str] = []
        downgrade_signals: list[str] = []
        if not cite_keys:
            _append_unique(blocking_missing, _block_message(policy, "no_citations"))
        if (fulltext_n + abstract_n) == 0 and title_n > 0:
            _append_unique(blocking_missing, _block_message(policy, "title_only_evidence"))
        if not evidence_snippets:
            _append_unique(blocking_missing, _block_message(policy, "no_snippets"))

        snip_ok = (
            len([s for s in evidence_snippets if isinstance(s, dict) and str(s.get("text") or "").strip()])
            if isinstance(evidence_snippets, list)
            else 0
        )
        if snip_ok < int(thresholds.get("min_snippets") or 12):
            _append_unique(
                blocking_missing,
                _block_message(policy, "too_few_snippets", min_needed=int(thresholds.get("min_snippets") or 12), actual=snip_ok),
            )

        eval_tokens = _extract_eval_tokens(pids=support_pids, notes_by_pid=notes_by_pid)
        wants_eval = any(t in " ".join(axes).lower() for t in ["evaluation", "benchmark", "metric", "dataset"])
        if wants_eval and not eval_tokens:
            _append_unique(blocking_missing, _block_message(policy, "missing_eval_tokens"))
        if fulltext_n == 0 and abstract_n > 0:
            _append_unique(downgrade_signals, _downgrade_message(policy, "abstract_only"))
        if _has_numeric_evidence(evidence_snippets) and not eval_tokens:
            _append_unique(downgrade_signals, _downgrade_message(policy, "numeric_without_protocol"))

        definitions_setup = _definitions_setup(
            rq=rq,
            scope_rule=scope_rule,
            axes=axes,
            cite_keys=cite_keys,
        )

        claim_candidates = _claim_candidates(
            title=title,
            axes=axes,
            evidence_snippets=evidence_snippets,
            cite_keys=cite_keys,
            has_fulltext=(fulltext_n > 0),
        )
        claim_n = len([c for c in claim_candidates if isinstance(c, dict) and str(c.get('claim') or '').strip()])
        if claim_n < 3:
            _append_unique(blocking_missing, _block_message(policy, 'too_few_claim_candidates', min_needed=3))

        concrete_comparisons = _comparisons(
            title=title,
            axes=axes,
            clusters=clusters,
            cite_keys=cite_keys,
            evidence_snippets=evidence_snippets,
            policy=policy,
        )
        comp_n = len([c for c in concrete_comparisons if isinstance(c, dict)])
        if comp_n < int(thresholds.get('min_comparisons') or 8):
            _append_unique(
                blocking_missing,
                _block_message(policy, 'too_few_comparisons', min_needed=int(thresholds.get('min_comparisons') or 8)),
            )

        evaluation_protocol = _evaluation_protocol(
            tokens=eval_tokens,
            cite_keys=cite_keys,
            policy=policy,
        )

        failures_limitations = _limitations_from_notes(
            support_pids,
            notes_by_pid=notes_by_pid,
            cite_keys=cite_keys,
            evidence_snippets=evidence_snippets,
        )
        if len([item for item in failures_limitations if isinstance(item, dict) and str(item.get('bullet') or '').strip()]) < int(thresholds.get('min_limitations') or 5):
            _append_unique(downgrade_signals, _downgrade_message(policy, 'insufficient_limitations'))
            _append_unique(verify_fields, 'failure modes / known limitations')

        pack = {
            "sub_id": sub_id,
            "title": title,
            "evidence_ids": [str(e or "").strip() for e in ((bound_eids if isinstance(bound_eids, list) and bound_eids else [s.get("evidence_id") for s in evidence_snippets]) or []) if str(e or "").strip()],
            "evidence_level_summary": {
                "fulltext": fulltext_n,
                "abstract": abstract_n,
                "title": title_n,
            },
            "evidence_snippets": evidence_snippets,
            "definitions_setup": definitions_setup,
            "claim_candidates": claim_candidates,
            "concrete_comparisons": concrete_comparisons,
            "evaluation_protocol": evaluation_protocol,
            "failures_limitations": failures_limitations,
            "blocking_missing": blocking_missing,
            "downgrade_signals": downgrade_signals,
            "verify_fields": verify_fields,
            "generated_at": now_iso_seconds(),
        }
        _validate_pack_shape(pack, schema)

        records.append(pack)
        _write_md_pack(md_dir / f"{sub_id}.md", pack)

    write_jsonl(out_path, records)
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
    if "<!-- scaffold" in low:
        return False
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", text):
        return False
    if "(placeholder)" in low:
        return False
    if path.stat().st_size < 800:
        return False
    try:
        for line in text.splitlines()[:3]:
            if line.strip():
                json.loads(line)
    except Exception:
        return False
    return True


def _pids_from_clusters(clusters: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(clusters, list):
        return out
    for c in clusters:
        if not isinstance(c, dict):
            continue
        for pid in c.get("paper_ids") or []:
            pid = str(pid).strip()
            if pid and pid not in out:
                out.append(pid)
    return out


def _cluster_ordered_pids(pids: list[str], clusters: Any) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    cluster_lists: list[list[str]] = []
    if isinstance(clusters, list):
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            cluster_pids = [str(pid).strip() for pid in (cluster.get("paper_ids") or []) if str(pid).strip() and str(pid).strip() in pids]
            if cluster_pids:
                cluster_lists.append(cluster_pids)
    idx = 0
    while True:
        added = False
        for cluster_pids in cluster_lists:
            if idx >= len(cluster_pids):
                continue
            pid = cluster_pids[idx]
            if pid not in seen:
                seen.add(pid)
                ordered.append(pid)
            added = True
        if not added:
            break
        idx += 1
    for pid in pids:
        if pid not in seen:
            ordered.append(pid)
            seen.add(pid)
    return ordered


def _pids_from_bound_evidence(evidence_ids: Any, *, bank_by_eid: dict[str, dict[str, Any]]) -> list[str]:
    out: list[str] = []
    if not isinstance(evidence_ids, list):
        return out
    for eid in evidence_ids:
        eid = str(eid or "").strip()
        if not eid:
            continue
        pid = str((bank_by_eid.get(eid) or {}).get("paper_id") or "").strip()
        if pid and pid not in out:
            out.append(pid)
    return out


def _cite_keys_for_pids(pids: list[str], *, notes_by_pid: dict[str, dict[str, Any]], bibkeys: set[str]) -> list[str]:
    out: list[str] = []
    for pid in pids:
        bibkey = str((notes_by_pid.get(pid) or {}).get("bibkey") or "").strip()
        if not bibkey or (bibkeys and bibkey not in bibkeys):
            continue
        key = bibkey
        if key not in out:
            out.append(key)
        if len(out) >= 12:
            break
    return out


def _split_sentences(text: str) -> list[str]:
    from tooling.common import split_sentences

    return split_sentences(text)


def _is_availability_boilerplate(text: str) -> bool:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return True
    low = s.lower()
    has_link = bool(_URL_RE.search(s))
    mentions_artifact = bool(
        re.search(
            r"(?i)\b(?:project\s+(?:website|site|web\s*page|page)|website|site|web\s*page|repository|repo|code|dataset|data|collection|resources?)\b",
            s,
        )
    )
    if has_link and mentions_artifact:
        return True
    if re.search(r"(?i)\b(?:encourage|invite)\s+readers?\b", s) and mentions_artifact:
        return True
    if re.search(r"(?i)\b(?:view|visit|see|consult|check)\b", s) and re.search(r"(?i)\b(?:github|repository|repo|website|project\s+site)\b", s):
        return True
    if re.search(r"(?i)\bour\s+(?:living\s+)?(?:github\s+)?repository\b", s):
        return True
    if "available at" in low or "can be found at" in low:
        return mentions_artifact or has_link
    if re.search(r"(?i)\b(?:our|the)\s+(?:code|project|repository|repo|dataset|data|collection|resources?)\b", s):
        return has_link or bool(_AVAILABILITY_VERB_RE.search(s))
    if re.search(r"(?i)\b(?:code|dataset|data|collection|resources?)\b", s) and _AVAILABILITY_VERB_RE.search(s):
        return True
    return False


def _sanitize_source_sentence(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return ""
    if _is_availability_boilerplate(s):
        return ""
    if any(pattern.search(s) for pattern in _GENERIC_SUMMARY_PATTERNS):
        return ""

    s = _URL_RE.sub("", s)
    s = re.sub(r"([,;:])(?=[A-Za-z(])", r"\1 ", s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;:")
    s = _LEADING_CONTEXT_RE.sub("", s)
    s = _LEADING_DISCOURSE_RE.sub("", s)
    s = _LEADING_CONCESSION_RE.sub("", s)
    s = re.sub(r"(?i)^is a significant gap exists\b", "A significant gap exists", s)
    s = _LEADING_SELF_REF_RE.sub("", s)
    s = _LEADING_AUTHOR_FINDING_RE.sub("", s)
    s = _LEADING_AUTHOR_PREDICATE_RE.sub("", s)
    s = _LEADING_AUTHOR_ACTION_RE.sub("", s)
    s = _LEADING_PARTICIPLE_RE.sub("", s)
    s = _LEADING_WHERE_ARTIFACT_RE.sub(r"\1 ", s)

    if _PROMISSORY_SELF_NARRATION_RE.match(s) or _FRAGMENT_PARTICIPLE_RE.match(s):
        return ""
    if _SURVEY_META_SENTENCE_RE.search(s):
        return ""

    m = _NAMED_ARTIFACT_RE.match(s)
    if m:
        name = re.sub(r"\s+", " ", m.group(1).strip(" ,;:"))
        rest = re.sub(r"\s+", " ", m.group(2).strip(" ,;:"))
        if rest and re.match(r"(?i)^(?:which|that)\b", rest):
            rest = re.sub(r"(?i)^(?:which|that)\s+", "", rest).strip()
            s = f"{name} {rest}"
        elif rest and re.match(r"(?i)^(?:a|an|the|one|\d+)\b", rest):
            s = f"{name} is {rest}"
        elif rest:
            s = f"{name}: {rest}"
        else:
            s = name
    elif _STUDY_SELF_NARRATION_RE.match(s) or _GENERIC_SELF_NARRATION_RE.match(s):
        return ""

    rel_clause = _RELATIVE_CLAUSE_ARTIFACT_RE.match(s)
    if rel_clause:
        name = rel_clause.group(1).strip()
        rest = _RELATIVE_CLAUSE_ARTIFACT_RE.sub("", s, count=1).strip(" ,;:")
        if rest:
            s = f"{name} {rest}"
        else:
            s = name

    artifact_match = _POST_ACTION_ARTIFACT_RE.match(s)
    if artifact_match:
        name = artifact_match.group(1).strip()
        rest = artifact_match.group(2).strip()
        if rest and re.match(r"(?i)^(?:which|that)\b", rest):
            rest = re.sub(r"(?i)^(?:which|that)\s+", "", rest).strip()
            s = f"{name} {rest}"
        elif rest and re.match(r"(?i)^(?:a|an|the|one|\d+)\b", rest):
            s = f"{name} is {rest}"
        elif rest:
            s = f"{name}: {rest}"

    if s:
        s = s[:1].upper() + s[1:]
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;:")
    if re.match(r"(?i)^abstract-level evidence only\b", s):
        return ""
    if re.match(r"(?i)^title-only evidence\b", s):
        return ""
    if any(pattern.search(s) for pattern in _GENERIC_SUMMARY_PATTERNS):
        return ""
    if len(s) < 16:
        return ""
    if not _FINITE_VERB_RE.search(s):
        return ""
    if s[-1] not in ".!?":
        s = f"{s}."
    return s


def _sanitize_source_text(text: str, *, sentence_limit: int | None = None) -> str:
    raw_sentences = _split_sentences(text)
    if not raw_sentences:
        raw_sentences = [str(text or "")]

    out: list[str] = []
    seen: set[str] = set()
    for sentence in raw_sentences:
        cleaned = _sanitize_source_sentence(sentence)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if sentence_limit is not None and len(out) >= int(sentence_limit):
            break
    return " ".join(out).strip()


def _is_meta_paper_title(title: str) -> bool:
    t = re.sub(r"\s+", " ", str(title or "").strip())
    return bool(t and _META_PAPER_TITLE_RE.search(t))


def _note_snippet_candidates(*, workspace: Path, pid: str, note: dict[str, Any], bibkeys: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    bibkey = str(note.get("bibkey") or "").strip()
    if not bibkey or (bibkeys and bibkey not in bibkeys):
        return candidates

    def add_candidate(text: str, *, source: str, pointer: str, base_score: int) -> None:
        cleaned = _sanitize_source_text(text, sentence_limit=1)
        if not cleaned:
            return
        if re.match(r"(?i)^abstract-level evidence only\b", cleaned):
            return
        if re.match(r"(?i)^title-only evidence\b", cleaned):
            return
        if _SURVEY_META_SENTENCE_RE.search(cleaned):
            return
        score = _snippet_specificity_score(cleaned) + int(base_score)
        if score < 1:
            return
        candidates.append(
            {
                "text": cleaned,
                "paper_id": pid,
                "citations": [bibkey],
                "provenance": {
                    "evidence_level": str(note.get("evidence_level") or "").strip().lower() or "unknown",
                    "source": source,
                    "pointer": pointer,
                },
                "score": score,
            }
        )

    key_results = note.get("key_results")
    if isinstance(key_results, list):
        for idx, kr in enumerate(key_results):
            raw_kr = str(kr).strip()
            if not raw_kr:
                continue
            low = raw_kr.lower()
            if low.startswith("key quantitative results") or low.startswith("evidence level"):
                continue
            add_candidate(raw_kr, source="paper_notes", pointer=f"papers/paper_notes.jsonl:paper_id={pid}#key_results[{idx}]", base_score=3)

    limitations = note.get("limitations") or []
    if isinstance(limitations, list):
        for idx, lim in enumerate(limitations[:6]):
            add_candidate(str(lim or ""), source="paper_notes", pointer=f"papers/paper_notes.jsonl:paper_id={pid}#limitations[{idx}]", base_score=2)

    method = str(note.get("method") or "").strip()
    if method:
        add_candidate(method, source="paper_notes", pointer=f"papers/paper_notes.jsonl:paper_id={pid}#method", base_score=1)

    abstract = str(note.get("abstract") or "").strip()
    if abstract:
        for idx, sent in enumerate(_split_sentences(abstract)[:4]):
            add_candidate(sent, source="abstract", pointer=f"papers/paper_notes.jsonl:paper_id={pid}#abstract[{idx}]", base_score=1)

    bullets = note.get("summary_bullets") or []
    if isinstance(bullets, list):
        for idx, bullet in enumerate(bullets[:8]):
            raw_b = str(bullet).strip()
            if len(raw_b) < 24:
                continue
            low = raw_b.lower()
            if low.startswith("evidence level") or low.startswith("main idea (from title)"):
                continue
            add_candidate(raw_b, source="paper_notes", pointer=f"papers/paper_notes.jsonl:paper_id={pid}#summary_bullets[{idx}]", base_score=0)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cand in sorted(candidates, key=lambda item: (-int(item.get("score") or 0), -len(str(item.get("text") or "")), str(item.get("text") or "").lower())):
        key = str(cand.get("text") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(cand)
    return deduped


def _evidence_snippets(
    *,
    workspace: Path,
    pids: list[str],
    notes_by_pid: dict[str, dict[str, Any]],
    bibkeys: set[str],
    limit: int,
    clusters: Any | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ordered_pids = _cluster_ordered_pids(pids, clusters)

    for pid in ordered_pids:
        note = notes_by_pid.get(pid) or {}
        note_candidates = _note_snippet_candidates(workspace=workspace, pid=pid, note=note, bibkeys=bibkeys)
        if _is_meta_paper_title(str(note.get("title") or "")):
            # Survey/review papers are secondary evidence, but they may still
            # contain concrete benchmark or framework facts. Keep only those
            # portable claims; generic landscape prose remains filtered out.
            note_candidates = [
                candidate
                for candidate in note_candidates
                if _claim_eligible(str(candidate.get("text") or ""))
                or _snippet_specificity_score(str(candidate.get("text") or "")) >= 4
            ]

        if not note_candidates:
            evidence_level = str(note.get("evidence_level") or "").strip().lower() or "unknown"
            fulltext_rel = str(note.get("fulltext_path") or "").strip()
            fulltext_path = (workspace / fulltext_rel) if fulltext_rel else None
            if evidence_level == "fulltext" and fulltext_path and fulltext_path.exists() and fulltext_path.stat().st_size > 800:
                raw = fulltext_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                cleaned = _sanitize_source_text(raw, sentence_limit=2)
                bibkey = str(note.get("bibkey") or "").strip()
                if cleaned and bibkey:
                    note_candidates = [
                        {
                            "text": cleaned,
                            "paper_id": pid,
                            "citations": [bibkey],
                            "provenance": {
                                "evidence_level": evidence_level,
                                "source": "fulltext",
                                "pointer": str(fulltext_rel),
                            },
                            "score": _snippet_specificity_score(cleaned) + 1,
                        }
                    ]

        if note_candidates:
            chosen = note_candidates[0]
            out.append(
                {
                    "text": _sanitize_source_text(chosen.get("text") or "", sentence_limit=2),
                    "paper_id": pid,
                    "citations": chosen.get("citations") or [],
                    "provenance": chosen.get("provenance") or {},
                }
            )

        if len(out) >= int(limit):
            break

    return out


def _verify_fields(*, axes: list[str], evidence_summary: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    fields: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if x and x not in fields:
            fields.append(x)

    joined = " ".join([a.lower() for a in axes])

    for item in (policy.get("verify_field_defaults") or []):
        add(str(item or ""))

    for rule in (policy.get("verify_field_rules") or []):
        if not isinstance(rule, dict):
            continue
        keywords = [str(k).strip().lower() for k in (rule.get("keywords") or []) if str(k).strip()]
        field = str(rule.get("field") or "").strip()
        if field and any(k in joined for k in keywords):
            add(field)

    if int((evidence_summary or {}).get("fulltext", 0) or 0) == 0:
        add("paper-local protocol details from full text")

    return fields[:12]


def _definitions_setup(*, rq: str, scope_rule: Any, axes: list[str], cite_keys: list[str]) -> list[dict[str, Any]]:
    include = []
    exclude = []
    if isinstance(scope_rule, dict):
        include = [str(x).strip() for x in (scope_rule.get("include") or []) if str(x).strip()]
        exclude = [str(x).strip() for x in (scope_rule.get("exclude") or []) if str(x).strip()]

    rq_text = rq or "What is the subsection-specific question this section must answer?"
    scope_bits = []
    if include:
        scope_bits.append(f"in-scope: {include[0]}")
    if exclude:
        scope_bits.append(f"out-of-scope: {exclude[0]}")
    scope_txt = "; ".join(scope_bits)

    axis_txt = "; ".join([a for a in axes[:5] if a])
    bullet = f"Setup: {rq_text}"
    if scope_txt:
        bullet += f" Scope: {scope_txt}."
    if axis_txt:
        bullet += f" Axes: {axis_txt}."

    return [{"bullet": bullet.strip(), "citations": cite_keys[:3]}]


def _claim_candidates(
    *,
    title: str,
    axes: list[str],
    evidence_snippets: list[dict[str, Any]],
    cite_keys: list[str],
    has_fulltext: bool,
) -> list[dict[str, Any]]:
    from tooling.common import bounded_complete_text

    out: list[dict[str, Any]] = []

    # Non-negotiable: claim candidates must be snippet-derived (traceable), even in abstract-only mode.
    for snip in evidence_snippets[:8]:
        if not isinstance(snip, dict):
            continue
        text = str(snip.get("text") or "").strip()
        if not text:
            continue
        if _snippet_specificity_score(text) < 1:
            continue
        low = text.lower()
        if low.startswith("abstract-level evidence") or low.startswith("title-only evidence"):
            continue
        if low.startswith("this work is mapped to:") or low.startswith("mapped to outline subsections:"):
            continue

        sents = _split_sentences(text)
        claim = (sents[0] if sents else text).strip()
        claim = re.sub(r"\s+", " ", claim).strip()
        if len(claim) < 24:
            continue
        if not _claim_eligible(claim):
            continue
        if not _text_relevant_to_topic(claim, title=title, axes=axes) and _snippet_specificity_score(claim) < 4:
            continue
        claim = bounded_complete_text(claim, max_chars=400, overflow_factor=2.0)
        if not claim:
            continue

        out.append(
            {
                "claim": claim,
                "evidence_field": "evidence_snippet",
                "citations": snip.get("citations") if isinstance(snip.get("citations"), list) else cite_keys[:2],
            }
        )
        if len(out) >= 5:
            break

    return out


def _comparisons(
    *,
    title: str,
    axes: list[str],
    clusters: Any,
    cite_keys: list[str],
    evidence_snippets: Any,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    # Build multiple A-vs-B comparison cards (NO PROSE).
    # A150++ requires a larger pool of concrete comparisons (survey>=8, deep>=10)
    # so subsection writing does not collapse into per-paper summaries.

    axes = [str(a).strip() for a in (axes or []) if str(a).strip()]
    if not axes:
        axes = [str(a).strip() for a in (policy.get("default_axes") or []) if str(a).strip()]

    # Build cluster groups.
    groups: list[dict[str, Any]] = []
    if isinstance(clusters, list):
        for c in clusters:
            if not isinstance(c, dict):
                continue
            label = str(c.get("label") or "").strip()
            pids = [str(x).strip() for x in (c.get("paper_ids") or []) if str(x).strip()]
            if not pids:
                continue
            if not label:
                label = f"Cluster {len(groups) + 1}"
            groups.append({"label": label, "pids": pids})

    if len(groups) < 2 and isinstance(evidence_snippets, list):
        seen: set[str] = set()
        pids: list[str] = []
        for sn in evidence_snippets:
            if not isinstance(sn, dict):
                continue
            pid = str(sn.get("paper_id") or "").strip()
            if pid and pid not in seen:
                seen.add(pid)
                pids.append(pid)
        if len(pids) >= 6:
            mid = max(3, len(pids) // 2)
            groups = [
                {"label": "Group A", "pids": pids[:mid]},
                {"label": "Group B", "pids": pids[mid : mid + mid]},
            ]

    # No usable cluster grouping: return explicit failure state to the caller instead of fabricating A/B cards.
    if len(groups) < 2:
        return []

    # Pair ordering: prioritize earlier clusters.
    pairs: list[tuple[int, int]] = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            pairs.append((i, j))

    def axis_keywords(axis: str) -> list[str]:
        low = (axis or "").lower()
        kws: list[str] = []
        if any(k in low for k in ["embod", "manipulation", "navigation", "robot"]):
            kws += ["robot", "manipulation", "navigation", "embodiment", "task", "policy"]
        if any(k in low for k in ["policy", "action", "control", "interface", "sensor", "observation"]):
            kws += ["policy", "action", "control", "interface", "sensor", "observation", "latency"]
        if any(k in low for k in ["transfer", "generalization", "cross-embodiment", "sim-to-real", "deployment"]):
            kws += ["transfer", "generalization", "cross-embodiment", "sim-to-real", "real-world", "deployment"]
        if any(k in low for k in ["data", "supervision", "pretraining", "post-training", "demonstration"]):
            kws += ["data", "dataset", "supervision", "pretraining", "post-training", "demonstration"]
        if any(k in low for k in ["failure", "robust", "stress", "safety", "reliability"]):
            kws += ["failure", "robust", "stress", "safety", "reliability", "recovery"]
        if any(k in low for k in ["tool", "function", "schema", "protocol", "api", "mcp", "router", "interface"]):
            kws += ["tool", "function", "schema", "protocol", "api", "mcp", "router", "interface"]
        if any(k in low for k in ["plan", "reason", "search", "mcts", "cot", "tot"]):
            kws += ["plan", "planner", "reason", "search", "mcts", "chain-of-thought", "tree"]
        if any(k in low for k in ["memory", "retriev", "rag", "index"]):
            kws += ["memory", "retrieval", "rag", "index", "vector", "embedding"]
        if any(k in low for k in ["eval", "benchmark", "dataset", "metric", "human"]):
            kws += ["benchmark", "dataset", "metric", "evaluation", "human"]
        if any(k in low for k in ["compute", "latency", "cost", "efficien", "budget"]):
            kws += ["compute", "latency", "cost", "efficient", "speed", "budget"]
        if any(k in low for k in ["train", "supervision", "preference", "rl", "sft"]):
            kws += ["train", "training", "supervision", "preference", "rl", "sft"]
        if any(
            k in low
            for k in ["security", "safety", "threat", "attack", "sandbox", "permission", "injection", "jailbreak"]
        ):
            kws += ["security", "safety", "threat", "attack", "sandbox", "permission", "injection", "jailbreak"]

        # Preserve domain terms from the actual axis instead of relying only on
        # built-in domain synonym lists. This keeps new research topics usable
        # without weakening evidence traceability.
        for token in re.findall(r"[a-z][a-z0-9-]{3,}", low):
            if token in _TOPIC_STOPWORDS or token in {"versus", "under", "across", "between"}:
                continue
            kws.append(token)

        seen: set[str] = set()
        out: list[str] = []
        for k in kws:
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out[:10]

    def pick_highlights(pids: list[str], axis: str, *, limit: int = 2) -> list[dict[str, Any]]:
        from tooling.common import bounded_complete_text

        if not isinstance(evidence_snippets, list) or not pids:
            return []

        kws = axis_keywords(axis)
        scored: list[tuple[int, int, str, dict[str, Any]]] = []
        for snip in evidence_snippets:
            if not isinstance(snip, dict):
                continue
            pid = str(snip.get("paper_id") or "").strip()
            if pid not in pids:
                continue
            text = str(snip.get("text") or "").strip()
            if not text:
                continue
            low = text.lower()
            topic_fit = _text_relevant_to_topic(text, title=title, axes=axes)
            specificity = _snippet_specificity_score(text)
            if specificity < 1:
                continue
            if not _comparison_eligible(text):
                continue
            score = 0
            score += min(3, max(0, specificity - 1))
            for kw in kws:
                if kw and kw in low:
                    score += 1
            if any(kw and kw in low for kw in kws[:4]):
                score += 1
            if topic_fit:
                score += 1
            if re.search(r"\b\d+(?:\.\d+)?%?\b", text):
                score += 1
            prov = snip.get("provenance")
            if isinstance(prov, dict) and str(prov.get("evidence_level") or "").strip().lower() == "fulltext":
                score += 1
            if not topic_fit:
                score -= 2
                if specificity < 3:
                    continue
            scored.append((score, len(text), low[:80], snip))

        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))

        out: list[dict[str, Any]] = []
        for score, _, _, snip in scored:
            if score <= 0:
                continue
            pid = str(snip.get("paper_id") or "").strip()
            eid = str(snip.get("evidence_id") or "").strip()
            cites = [str(c).strip() for c in (snip.get("citations") or []) if str(c).strip()]
            prov = snip.get("provenance") or {}
            ptr = str((prov.get("pointer") if isinstance(prov, dict) else "") or "").strip()

            raw = str(snip.get("text") or "").strip()
            sents = _split_sentences(raw)
            excerpt = (sents[0] if sents else raw).strip()
            excerpt = re.sub(r"\s+", " ", excerpt)
            excerpt = bounded_complete_text(excerpt, max_chars=280, overflow_factor=3.0)
            if not excerpt:
                continue

            out.append(
                {
                    "paper_id": pid,
                    "evidence_id": eid,
                    "excerpt": excerpt,
                    "citations": cites,
                    "pointer": ptr,
                    "score": int(score),
                }
            )
            if len(out) >= int(limit):
                break
        return out

    out: list[dict[str, Any]] = []
    target = 10

    for ax in axes[:10]:
        for i, j in pairs:
            if len(out) >= target:
                break

            a = groups[i]
            b = groups[j]
            a_pids = [str(pid).strip() for pid in (a.get("pids") or []) if str(pid).strip()]
            b_pids = [str(pid).strip() for pid in (b.get("pids") or []) if str(pid).strip()]
            shared = set(a_pids) & set(b_pids)
            if shared:
                a_unique = [pid for pid in a_pids if pid not in shared]
                b_unique = [pid for pid in b_pids if pid not in shared]
                if len(a_unique) >= 2:
                    a_pids = a_unique
                if len(b_unique) >= 2:
                    b_pids = b_unique
            a_label = str(a.get("label") or "Cluster A").strip()
            b_label = str(b.get("label") or "Cluster B").strip()

            a_hl = pick_highlights(a_pids, ax)
            b_hl = pick_highlights(b_pids, ax)
            if not a_hl or not b_hl:
                continue

            cits: list[str] = []
            for h in a_hl + b_hl:
                if isinstance(h, dict):
                    for c in (h.get("citations") or []):
                        c = str(c).strip()
                        if c and c not in cits:
                            cits.append(c)
            if not cits:
                cits = cite_keys[:6]

            a_txt = a_label
            if a_pids:
                a_txt += ": " + ", ".join([f"`{p}`" for p in a_pids[:3]])
            b_txt = b_label
            if b_pids:
                b_txt += ": " + ", ".join([f"`{p}`" for p in b_pids[:3]])

            out.append(
                {
                    "axis": ax,
                    "A_label": a_label,
                    "B_label": b_label,
                    "A_papers": a_txt,
                    "B_papers": b_txt,
                    "A_highlights": a_hl,
                    "B_highlights": b_hl,
                    "write_prompt": (
                        f"Contrast {a_label} vs {b_label} along \"{ax}\". "
                        "Ground A and B using the highlight snippets; do not introduce new claims beyond the cited evidence."
                    ),
                    "evidence_field": ax,
                    "citations": cits,
                }
            )

        if len(out) >= target:
            break

    return out[:target]


def _extract_eval_tokens(*, pids: list[str], notes_by_pid: dict[str, dict[str, Any]]) -> list[str]:
    tokens: list[str] = []

    def add(tok: str) -> None:
        t = (tok or "").strip()
        if not t:
            return
        low = t.lower()
        if low in _EVAL_STOP:
            return
        if len(t) < 3:
            return
        if t not in tokens:
            tokens.append(t)

    def scan(text: str) -> None:
        text = text or ""
        # Uppercase acronyms and CamelCase tokens are common for benchmarks/metrics.
        for m in re.findall(r"\b[A-Z]{2,}[A-Za-z0-9-]{0,18}\b", text):
            add(m)
        for m in re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9-]{1,24}\b", text):
            add(m)

    for pid in pids[:30]:
        note = notes_by_pid.get(pid) or {}
        scan(str(note.get("abstract") or ""))
        for b in (note.get("key_results") or []):
            scan(str(b or ""))
        for b in (note.get("limitations") or []):
            scan(str(b or ""))

    # Prefer a small list.
    return tokens[:12]


def _evaluation_protocol(*, tokens: list[str], cite_keys: list[str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Produce protocol-context bullets (NO PROSE) from explicit policy, not filler."""

    out: list[dict[str, Any]] = []
    cites_strong = cite_keys[:4] if isinstance(cite_keys, list) else []
    cites_light = cite_keys[:2] if isinstance(cite_keys, list) else []

    tok_list = ", ".join([t for t in (tokens or []) if str(t).strip()][:10]).strip()
    if not tok_list or not (cites_strong or cites_light):
        return []

    out.append(
        {
            "kind": "benchmark_inventory",
            "bullet": "Evaluation mentions include: " + tok_list + ".",
            "citations": cites_strong or cites_light,
        }
    )

    for bullet in (policy.get("evaluation_protocol_defaults") or []):
        bullet = str(bullet or "").strip()
        if bullet:
            out.append({"kind": "protocol_guardrail", "bullet": bullet, "citations": cites_light})

    return out[:8]


def _limitations_from_notes(
    pids: list[str],
    *,
    notes_by_pid: dict[str, dict[str, Any]],
    cite_keys: list[str],
    evidence_snippets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Extract cite-backed limitations/failure-mode bullets (NO PROSE).

    Prefer explicit `limitations` fields from notes, but fall back to scanning note fields
    for concrete caveat language. The extractor should surface real constraints from abstracts
    and summaries, not pad sparse packs with generic caution bullets.
    """

    limit_re = re.compile(
        r"(?i)\b(?:"
        r"limit\w*|challeng\w*|risk\w*|unsafe|secur\w*|attack\w*|threat\w*|fail\w*|fragil\w*|uncertain\w*|"
        r"open\s+problem\w*|future\s+work|caveat\w*|downside\w*|obstacle\w*|bottleneck\w*|gap\w*|disconnect\w*|"
        r"domain\s+shift|sim-?to-?real|generalization\s+(?:gap|challenge)|hinder\w*|cost\w*|complexit\w*|"
        r"partial\s+observability|manual\s+annotation|latency|hallucinat\w*|restrict\w*|out-of-distribution|ood|"
        r"cascading\s+error\w*|poor\s+instruction\s+following"
        r")\b|受限|局限|风险|挑战|失败|安全"
    )
    strong_negative_re = re.compile(
        r"(?i)\b(?:"
        r"limit\w*|risk\w*|unsafe|fail\w*|fragil\w*|gap\w*|disconnect\w*|bottleneck\w*|"
        r"latency|cost\w*|complexit\w*|hallucinat\w*|domain\s+shift|manual\s+annotation|restrict\w*|"
        r"out-of-distribution|ood|partial\s+observability|poor\s+instruction\s+following|cascading\s+error\w*"
        r")\b|受限|局限|风险|失败|安全"
    )
    solution_re = re.compile(
        r"(?i)^(?:to address|addressing|to overcome|we address|we mitigate|we solve|to tackle|"
        r"we introduce|we present|we propose|towards this end|in this work,\s+we(?:\s+close)?|"
        r"to unify these observations|to facilitate this|we close this gap|motivated by these limitations|"
        r"(?:these|the)\s+findings\s+(?:suggest|indicate)\s+that\b.*\bshould\b)"
    )
    remedy_phrase_re = re.compile(
        r"(?i)\b(?:we introduce|we present|we propose|we close this gap|bridges?\s+(?:a|the)\s+key\s+gap)\b"
    )
    positive_result_re = re.compile(
        r"(?i)\b(?:outperform\w*|surpass\w*|superior\w*|state-of-the-art|sota|achiev\w*|excelling?|strong\s+results?)\b"
    )
    positive_gap_re = re.compile(r"(?i)\b(?:narrowing|closing|bridging)\s+the\s+gap\b")
    positive_challenge_re = re.compile(
        r"(?i)\bchalleng\w*\s+(?:task|tasks|benchmark|benchmarks|environment|environments|setting|settings)\b"
    )
    event_challenge_re = re.compile(
        r"(?i)\b(?:this|the)\s+(?:year(?:'s)?\s+)?challenge\s+"
        r"(?:introduces?|includes?|features?|uses?|asks?|invites?|requires?)\b|"
        r"\b(?:shared|benchmark|competition|track)\s+challenge\b"
    )
    positive_cost_re = re.compile(
        r"(?i)\bcost[-\s]?effectiv(?:e|eness|ely)\b|"
        r"\b(?:lower|reduced?|decreased?|minimal|optimal)\s+(?:computational\s+)?costs?\b"
    )
    solution_tail_re = re.compile(
        r"(?i)[,;:]\s*(?:we|the authors)\s+(?:introduce|present|propose|develop|devise|design)\b"
    )

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(bullet: str, citations: list[str]) -> None:
        b = re.sub(r"\s+", " ", str(bullet or "").strip())
        if not b:
            return
        key = b.lower()
        if key in seen:
            return
        seen.add(key)
        out.append({"bullet": b, "citations": citations})

    def trim_solution_tail(text: str) -> str:
        s = re.sub(r"\s+", " ", str(text or "").strip())
        if not s:
            return ""
        m = solution_tail_re.search(s)
        if not m:
            return s
        head = s[: m.start()].strip(" ,;:")
        if not head or not strong_negative_re.search(head):
            return s
        if head.lower().startswith("because "):
            head = head[8:].strip()
            if head:
                head = head[:1].upper() + head[1:]
        if head[-1] not in ".!?":
            head += "."
        return head

    def is_caveat_sentence(text: str) -> bool:
        s = re.sub(r"\s+", " ", str(text or "").strip())
        signal_text = positive_cost_re.sub("", s)
        signal_text = event_challenge_re.sub("", signal_text)
        if not s or not limit_re.search(signal_text):
            return False
        if _GENERIC_EVIDENCE_RE.search(s) and _snippet_specificity_score(s) < 2:
            return False
        if solution_re.search(s):
            return False
        if remedy_phrase_re.search(s) and not strong_negative_re.search(signal_text):
            return False
        if positive_challenge_re.search(s) and not strong_negative_re.search(signal_text):
            return False
        if positive_gap_re.search(s):
            return False
        if positive_result_re.search(s) and not strong_negative_re.search(signal_text):
            return False
        if not strong_negative_re.search(signal_text) and _snippet_specificity_score(s) < 2:
            return False
        return True

    for pid in pids[:40]:
        note = notes_by_pid.get(pid) or {}
        if _is_meta_paper_title(str(note.get("title") or "")):
            continue
        bibkey = str(note.get("bibkey") or "").strip()
        cite = [bibkey] if bibkey else (cite_keys[:2] if isinstance(cite_keys, list) else [])

        limitations = note.get("limitations") or []
        if isinstance(limitations, list):
            for lim in limitations[:6]:
                lim = str(lim or "").strip()
                if not lim:
                    continue
                lim = _sanitize_source_text(lim, sentence_limit=2)
                if not lim:
                    continue
                lim = trim_solution_tail(lim)
                low = lim.lower()
                if low.startswith("evidence level"):
                    continue
                if low.startswith("abstract-level evidence") or low.startswith("title-only evidence"):
                    continue
                if low.startswith("this work is mapped to:") or low.startswith("mapped to outline subsections:"):
                    continue
                if not is_caveat_sentence(lim):
                    continue
                add(lim, cite)

        scan_fields: list[Any] = [note.get("abstract") or "", note.get("method") or ""]
        summary_bullets = note.get("summary_bullets") or []
        if isinstance(summary_bullets, list):
            scan_fields.extend(summary_bullets[:8])
        key_results = note.get("key_results") or []
        if isinstance(key_results, list):
            scan_fields.extend(key_results[:8])

        for raw in scan_fields:
            for s in _split_sentences(str(raw)):
                s = _sanitize_source_sentence(s)
                s = trim_solution_tail(s)
                if not is_caveat_sentence(s):
                    continue
                add(s, cite)

        if len(out) >= 10:
            break

    snippet_items = evidence_snippets or []
    for item in snippet_items[:24]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        cites = [str(x).strip() for x in (item.get("citations") or []) if str(x).strip()]
        if not cites:
            cites = cite_keys[:2] if isinstance(cite_keys, list) else []
        for s in _split_sentences(text):
            s = _sanitize_source_sentence(s)
            s = trim_solution_tail(s)
            if not is_caveat_sentence(s):
                continue
            add(s, cites)
            if len(out) >= 10:
                break
        if len(out) >= 10:
            break

    minimum_target = 5
    if len(out) < minimum_target:
        for pid in pids[:40]:
            note = notes_by_pid.get(pid) or {}
            bibkey = str(note.get("bibkey") or "").strip()
            cite = [bibkey] if bibkey else (cite_keys[:2] if isinstance(cite_keys, list) else [])
            if not cite:
                continue
            title = re.sub(r"\s+", " ", str(note.get("title") or "").strip())
            level = str(note.get("evidence_level") or "").strip().lower()
            if level not in {"abstract", "title"}:
                continue
            level_label = "abstract-level" if level == "abstract" else "title-only"
            if title:
                add(
                    f"{title}: only {level_label} evidence is available here; verify evaluation protocol, baselines, and failure cases in the full paper before using it for strong cross-paper claims.",
                    cite,
                )
            if len(out) >= minimum_target:
                break

    return out[:8]


def _write_md_pack(path: Path, pack: dict[str, Any]) -> None:
    from tooling.common import atomic_write_text

    sub_id = str(pack.get("sub_id") or "").strip()
    title = str(pack.get("title") or "").strip()

    lines: list[str] = [
        f"# Evidence draft: {sub_id} {title}",
        "",
        "## Evidence snippets (with provenance)",
    ]

    for s in pack.get("evidence_snippets") or []:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text") or "").strip()
        eid = str(s.get("evidence_id") or "").strip()
        cites = " ".join([c for c in (s.get("citations") or []) if str(c).strip()])
        prov = s.get("provenance")
        prov_s = ""
        if isinstance(prov, dict):
            prov_s = " | ".join([str(prov.get("source") or "").strip(), str(prov.get("pointer") or "").strip()]).strip(" |")
        if text:
            prefix = f"({eid}) " if eid else ""
            line = f"- {prefix}{text} {cites}".rstrip()
            if prov_s:
                line += f" (provenance: {prov_s})"
            lines.append(line)

    lines.extend(["", "## Definitions / setup", ""])
    for item in pack.get("definitions_setup") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    lines.extend(["", "## Claim candidates", ""])
    for item in pack.get("claim_candidates") or []:
        claim = str((item or {}).get("claim") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if claim:
            lines.append(f"- {claim} {cites}".rstrip())

    lines.extend(["", "## Concrete comparisons", ""])
    for item in pack.get("concrete_comparisons") or []:
        axis = str((item or {}).get("axis") or "").strip()
        a = str((item or {}).get("A_papers") or "").strip()
        b = str((item or {}).get("B_papers") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        lines.append(f"- Axis: {axis}; A: {a}; B: {b}. {cites}".rstrip())

        for side, hs in [("A", (item or {}).get("A_highlights") or []), ("B", (item or {}).get("B_highlights") or [])]:
            if not isinstance(hs, list):
                continue
            for h in hs[:2]:
                if not isinstance(h, dict):
                    continue
                ref = str(h.get("evidence_id") or h.get("paper_id") or "").strip()
                excerpt = str(h.get("excerpt") or "").strip()
                hcites = " ".join([c for c in (h.get("citations") or []) if str(c).strip()])
                ptr = str(h.get("pointer") or "").strip()
                if excerpt:
                    prefix = f"({ref}) " if ref else ""
                    suffix = f" (pointer: {ptr})" if ptr else ""
                    lines.append(f"  - {side} highlight: {prefix}{excerpt} {hcites}".rstrip() + suffix)

    lines.extend(["", "## Evaluation protocol", ""])
    for item in pack.get("evaluation_protocol") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    lines.extend(["", "## Failures / limitations", ""])
    for item in pack.get("failures_limitations") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    blocking = pack.get("blocking_missing") or []
    if blocking:
        lines.extend(["", "## Blocking missing (stop drafting)", ""])
        for m in blocking:
            m = str(m).strip()
            if m:
                lines.append(f"- {m}")

    downgrade = pack.get("downgrade_signals") or []
    if downgrade:
        lines.extend(["", "## Downgrade signals (keep claims conservative)", ""])
        for m in downgrade:
            m = str(m).strip()
            if m:
                lines.append(f"- {m}")

    verify = pack.get("verify_fields") or []
    if verify:
        lines.extend(["", "## Verify fields (non-blocking)", ""])
        for m in verify:
            m = str(m).strip()
            if m:
                lines.append(f"- {m}")

    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
