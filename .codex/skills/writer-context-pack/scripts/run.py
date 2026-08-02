from __future__ import annotations

import argparse
import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


_SOURCE_HYGIENE = _load_json(_ASSET_ROOT / "source_text_hygiene.json")
_CONTEXT_PACK_POLICY = _load_json(_ASSET_ROOT / "context_pack_policy.json")


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
        if not pattern:
            continue
        out.append(re.compile(pattern))
    return out


_URL_RE = _compile_hygiene_pattern("url_pattern", r"https?://\S+")
_AVAILABILITY_VERB_RE = _compile_hygiene_pattern(
    "availability_verb_pattern",
    r"(?i)\b(?:is|are|was|were|will\s+be|can\s+be|has\s+been)?\s*(?:publicly\s+)?(?:available|released|open-?sourced|shared)\b",
)
_AVAILABILITY_ARTIFACT_RE = _compile_hygiene_pattern(
    "availability_artifact_pattern",
    r"(?i)\b(?:project\s+(?:website|site|web\s*page|page)|website|site|web\s*page|repository|repo|code|dataset|data|collection|resources?)\b",
)
_INVITE_READERS_RE = _compile_hygiene_pattern("invite_readers_pattern", r"(?i)\b(?:encourage|invite)\s+readers?\b")
_AVAILABILITY_ACTION_RE = _compile_hygiene_pattern("availability_action_pattern", r"(?i)\b(?:view|visit|see|consult|check)\b")
_AVAILABILITY_LOCATION_RE = _compile_hygiene_pattern("availability_location_pattern", r"(?i)\b(?:github|repository|repo|website|project\s+site)\b")
_OUR_ARTIFACT_RE = _compile_hygiene_pattern("our_artifact_pattern", r"(?i)\bour\s+(?:living\s+)?(?:github\s+)?repository\b")
_AVAILABILITY_PHRASE_RE = _compile_hygiene_pattern("availability_phrase_pattern", r"(?i)\b(?:available at|can be found at)\b")
_AVAILABILITY_GENERIC_ARTIFACT_RE = _compile_hygiene_pattern("availability_generic_artifact_pattern", r"(?i)\b(?:code|dataset|data|collection|resources?)\b")
_LEADING_SELF_REF_RE = _compile_hygiene_pattern(
    "leading_self_reference_pattern",
    r"(?i)^(?:to (?:address|overcome|tackle|mitigate|study|investigate|examine|understand|analyze|explore|bridge)[^,]{0,180},\s*)?(?:(?:in|throughout)\s+(?:this|our)\s+(?:survey|paper|work|study|article),?\s*)?",
)
_LEADING_CONTEXT_RE = _compile_hygiene_pattern(
    "leading_context_pattern",
    r"(?i)^(?:building on this foundation|against this backdrop|in this context|to this end|towards this end|specifically|for example|for instance|based on this proposition|throughout [^,]{1,120}|moreover|furthermore|additionally|recently|further|notably),?\s*",
)
_LEADING_AUTHOR_FINDING_RE = _compile_hygiene_pattern(
    "leading_author_finding_pattern",
    r"(?i)^(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:show|shows|find|finds|observe|observes|demonstrate|demonstrates|quantify|quantifies|reveal|reveals|indicate|indicates)\s+that\s+",
)
_LEADING_AUTHOR_PREDICATE_RE = _compile_hygiene_pattern(
    "leading_author_predicate_pattern",
    r"(?i)^(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:show|shows|find|finds|observe|observes|demonstrate|demonstrates|reveal|reveals|indicate|indicates)\s+",
)
_LEADING_AUTHOR_ACTION_RE = _compile_hygiene_pattern(
    "leading_author_action_pattern",
    r"(?i)^(?:here,\s*)?(?:we|our\s+(?:results|analysis|study|evaluations?|experiments?))\s+(?:(?:also|broadly|comprehensively)\s+)?(?:introduce|present|propose|develop|describe|compare|conduct|discuss|summarize|review|explore|analyze|evaluate|quantify|study|design|build|construct|divide)\b[^,]{0,160},\s*",
)
_LEADING_PARTICIPLE_RE = _compile_hygiene_pattern(
    "leading_participle_pattern",
    r"(?i)^(?:demonstrating|showing|finding|observing|revealing|indicating|suggesting)\s+that\s+",
)
_FRAGMENT_PARTICIPLE_RE = _compile_hygiene_pattern("fragment_participle_pattern", r"(?i)^(?:demonstrating|showing|revealing|highlighting|indicating)\b")
_PROMISSORY_SELF_NARRATION_RE = _compile_hygiene_pattern(
    "promissory_self_narration_pattern",
    r"(?i)^(?:we\s+hope|we\s+aim|our\s+(?:survey|paper|work|study)\s+aims?|this\s+(?:survey|paper|work|study)\s+aims?)\b",
)
_LEADING_DISCOURSE_RE = _compile_hygiene_pattern("leading_discourse_pattern", r"(?i)^(?:moreover|furthermore|additionally|in addition),\s*")
_LEADING_WHERE_ARTIFACT_RE = _compile_hygiene_pattern(
    "leading_where_artifact_pattern",
    r"(?i)^where\s+([A-Z][A-Za-z0-9._-]{1,80})\s+",
)
_RELATIVE_CLAUSE_ARTIFACT_RE = _compile_hygiene_pattern(
    "relative_clause_artifact_pattern",
    r"^([A-Z][A-Za-z0-9._-]{1,80}),\s+(?:which|that)\s+",
)
_POST_ACTION_ARTIFACT_RE = _compile_hygiene_pattern("post_action_artifact_pattern", r"^([A-Z][A-Za-z0-9._-]{1,80}),\s+(.*)$")
_NAMED_ARTIFACT_RE = _compile_hygiene_pattern(
    "named_artifact_pattern",
    r"(?i)^(?:here,\s*)?(?:we|the authors)\s+(?:introduce|present|propose|develop|describe)\s+([A-Z][A-Za-z0-9][^,.;:]{0,120}),\s+(.*)$",
)
_GENERIC_SELF_NARRATION_RE = _compile_hygiene_pattern(
    "generic_self_narration_pattern",
    r"(?i)^(?:here,\s*)?(?:we|our)\s+(?:(?:also|broadly|comprehensively)\s+)?(?:introduce|present|propose|develop|describe|compare|conduct|discuss|summarize|review|explore|analyze|evaluate|study|design|build|construct|divide)\b",
)
_STUDY_SELF_NARRATION_RE = _compile_hygiene_pattern("study_self_narration_pattern", r"(?i)^(?:this|our)\s+(?:survey|paper|work|study|article)\b")
_GENERIC_META_RE = _compile_hygiene_pattern(
    "generic_meta_pattern",
    r"(?i)\b(?:survey|review|overview|taxonomy|history|landscape|main contribution is a detailed breakdown)\b",
)


def _has_negative_limit_signal(text: str) -> bool:
    # main() establishes the checkout import path before this policy is used.
    from tooling.source_text_hygiene import has_limitation_signal

    return has_limitation_signal(text)
_EVIDENCE_POLICY_DISCLAIMER_RE = re.compile(
    r"(?i)\b(?:abstract(?:-|\s+)(?:only|level)\s+evidence|title(?:-|\s+)only\s+evidence|"
    r"verify\s+evaluation\s+protocol.*full\s+paper|claims?\s+remain\s+provisional\s+under\s+abstract)\b"
)
_GENERIC_SUMMARY_PATTERNS = _compile_hygiene_pattern_list(
    "generic_summary_patterns",
    [
        r"(?i)^benchmarks? are crucial for evaluating progress\b",
        r"(?i)^evaluations? are critical to assess progress\b",
        r"(?i)^recent work has advanced such general robot policies\b",
        r"(?i)^in this machine learning-focused workflow\b",
        r"(?i)^we benchmark our method against\b",
        r"(?i)^from a detailed search of \d+ articles\b",
        r"(?i)^the experiments also provide an extensive evaluation\b",
    ],
)
_TOKEN_STOPWORDS = {
    str(x).strip().lower()
    for x in (
        _SOURCE_HYGIENE.get("topic_token_stopwords")
        if isinstance(_SOURCE_HYGIENE.get("topic_token_stopwords"), list)
        else [
            "and","the","with","from","into","across","under","over","between","task","tasks","study","studies",
            "design","system","systems","model","models","method","methods","paper","papers","evaluation","protocol",
        ]
    )
    if str(x).strip()
}


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)


def _trim(text: str, *, max_len: int = 400) -> str:
    """Normalize and bound text without creating a plausible-looking fragment."""

    from tooling.common import bounded_complete_text

    return bounded_complete_text(text, max_chars=int(max_len), overflow_factor=2.5)


def _is_availability_boilerplate(text: str) -> bool:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if not s:
        return True
    low = s.lower()
    has_link = bool(_URL_RE.search(s))
    mentions_artifact = bool(_AVAILABILITY_ARTIFACT_RE.search(s))
    if has_link and mentions_artifact:
        return True
    if _INVITE_READERS_RE.search(s) and mentions_artifact:
        return True
    if _AVAILABILITY_ACTION_RE.search(s) and _AVAILABILITY_LOCATION_RE.search(s):
        return True
    if _OUR_ARTIFACT_RE.search(s):
        return True
    if _AVAILABILITY_PHRASE_RE.search(low):
        return mentions_artifact or has_link
    if re.search(r"(?i)\b(?:our|the)\s+(?:code|project|repository|repo|dataset|data|collection|resources?)\b", s):
        return has_link or bool(_AVAILABILITY_VERB_RE.search(s))
    if _AVAILABILITY_GENERIC_ARTIFACT_RE.search(s) and _AVAILABILITY_VERB_RE.search(s):
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
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;:")
    s = _LEADING_CONTEXT_RE.sub("", s)
    s = _LEADING_DISCOURSE_RE.sub("", s)
    s = _LEADING_SELF_REF_RE.sub("", s)
    s = _LEADING_AUTHOR_FINDING_RE.sub("", s)
    s = _LEADING_AUTHOR_PREDICATE_RE.sub("", s)
    s = _LEADING_AUTHOR_ACTION_RE.sub("", s)
    s = _LEADING_PARTICIPLE_RE.sub("", s)
    s = _LEADING_WHERE_ARTIFACT_RE.sub(r"\1 ", s)

    if _PROMISSORY_SELF_NARRATION_RE.match(s) or _FRAGMENT_PARTICIPLE_RE.match(s):
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
    if any(pattern.search(s) for pattern in _GENERIC_SUMMARY_PATTERNS):
        return ""
    if len(s) < 16:
        return ""
    if s[-1] not in ".!?":
        s = f"{s}."
    return s


def _sanitize_source_text(text: str) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", raw)
    if not parts:
        parts = [raw]

    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = _sanitize_source_sentence(part)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return " ".join(out).strip()


def _profile_limits(draft_profile: str) -> dict[str, int]:
    requested = str(draft_profile or "").strip().lower().replace("-", "_")
    key = requested if requested in {"survey", "deep", "course_paper"} else "survey"
    cfg = ((_CONTEXT_PACK_POLICY.get("profile_limits") or {}).get(key) or {})
    comparison_min = 3 if key == "course_paper" else 5
    pair_min = 3 if key == "course_paper" else 5
    return {
        "comparison_keep_limit": max(comparison_min, int(cfg.get("comparison_keep_limit") or (9 if key == "deep" else 7))),
        "comparison_pair_limit": max(pair_min, int(cfg.get("comparison_pair_limit") or (9 if key == "deep" else 7))),
        "claim_keep_limit": max(4, int(cfg.get("claim_keep_limit") or 6)),
    }


def _topic_tokens(*, title: str, axes: list[str], extras: list[str] | None = None) -> set[str]:
    raw = " ".join([title] + [str(a or "") for a in (axes or [])] + [str(x or "") for x in (extras or [])])
    tokens = {
        tok
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", raw.lower())
        if tok not in _TOKEN_STOPWORDS and len(tok) >= 4
    }
    return tokens


def _text_relevant_to_topic(text: str, *, title: str, axes: list[str], extras: list[str] | None = None) -> bool:
    low = re.sub(r"\s+", " ", str(text or "").lower())
    tokens = _topic_tokens(title=title, axes=axes, extras=extras)
    if not tokens:
        return True
    return any(tok in low for tok in tokens)


def _normalized_text_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _rank_text_records(
    records: list[dict[str, Any]],
    *,
    title: str,
    axes: list[str],
    extras: list[str] | None = None,
    global_text_usage: dict[str, int],
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_local: set[str] = set()
    for rec in records:
        key = _normalized_text_key(rec.get("text") or rec.get("claim") or rec.get("excerpt") or "")
        if not key or key in seen_local:
            continue
        seen_local.add(key)
        deduped.append(rec)

    def _score(rec: dict[str, Any]) -> tuple[int, int, int, int]:
        text = str(rec.get("text") or rec.get("claim") or rec.get("excerpt") or "").strip()
        key = _normalized_text_key(text)
        reuse = global_text_usage.get(key, 0)
        relevant = 1 if _text_relevant_to_topic(text, title=title, axes=axes, extras=extras) else 0
        concrete = 1 if re.search(r"(?i)\d|\b(?:benchmark|dataset|metric|transfer|real-world|simulation|failure|latency|cost|robust)\b", text) else 0
        return (reuse, -relevant, -concrete, -len(text))

    ranked = sorted(deduped, key=_score)
    out: list[dict[str, Any]] = []
    for rec in ranked:
        key = _normalized_text_key(rec.get("text") or rec.get("claim") or rec.get("excerpt") or "")
        enriched = dict(rec)
        enriched["global_reuse_count"] = int(global_text_usage.get(key, 0))
        out.append(enriched)
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size <= 0:
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _bib_keys(bib_path: Path) -> set[str]:
    text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    return set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", text))




def _normalize_cite_keys(citations: Any, *, bibkeys: set[str]) -> list[str]:
    # Normalize citation keys to raw BibTeX keys (no @ prefix).
    # Tolerates: @Key, [@Key], Key, and semicolon/comma-separated strings.

    out: list[str] = []
    if not isinstance(citations, list):
        return out

    for c in citations:
        s = str(c or "").strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1].strip()
        if s.startswith("@"):  # tolerate @Key
            s = s[1:].strip()

        # Split multi-key strings best-effort (e.g., "@a; @b").
        for k in re.findall(r"[A-Za-z0-9:_-]+", s.replace("@", " ")):
            k = k.strip()
            if not k:
                continue
            if bibkeys and k not in bibkeys:
                continue
            if k not in out:
                out.append(k)

    return out
def _stable_choice(key: str, options: list[str]) -> str:
    if not options:
        return ""
    digest = hashlib.sha1((key or "").encode("utf-8", errors="ignore")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def _iter_outline_subsections(outline: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(outline, list):
        return out
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        sec_title = str(sec.get("title") or "").strip()
        for sub in sec.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sub_id = str(sub.get("id") or "").strip()
            title = str(sub.get("title") or "").strip()
            if sec_id and sec_title and sub_id and title:
                out.append({"sub_id": sub_id, "title": title, "section_id": sec_id, "section_title": sec_title})
    return out


def _draft_profile(workspace: Path) -> str:
    """Best-effort parse from `queries.md`."""

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
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower().replace("-", "_")
            if value in {"survey", "deep", "course_paper"}:
                return value
            return "survey"
    except Exception:
        return "survey"
    return "survey"



def _load_voice_palette(*, workspace: Path, repo_root: Path) -> dict[str, Any]:
    """Load a paper-voice palette used by writer packs.

    Precedence (most specific first):
    - Workspace override: outline/paper_voice_palette.json
    - Repo default: .codex/skills/writer-context-pack/assets/paper_voice_palette.json

    Keep this file small and semantic: it is a rewrite guide, not a prose template.
    """

    candidates = [
        workspace / 'outline' / 'paper_voice_palette.json',
        repo_root / '.codex' / 'skills' / 'writer-context-pack' / 'assets' / 'paper_voice_palette.json',
    ]

    for p in candidates:
        try:
            if not p.exists() or p.stat().st_size <= 0:
                continue
            data = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
            if isinstance(data, dict):
                return data
        except Exception:
            continue

    return {}

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

    from tooling.common import ensure_dir, latest_outline_state, load_workspace_pipeline_spec, load_yaml, now_iso_seconds, parse_semicolon_list, write_jsonl
    from tooling.quality_gate import _global_citation_min_subsections

    workspace = Path(args.workspace).resolve()
    spec = load_workspace_pipeline_spec(workspace)
    if spec is not None and str(spec.structure_mode or "").strip() == "section_first":
        state = latest_outline_state(workspace)
        if not state:
            raise SystemExit("Missing outline_state.jsonl; run the section-first C2 planner pass before writer-context-pack.")
        if str(state.get("structure_phase") or "").strip() != "decomposed" or str(state.get("h3_status") or "").strip() != "stable":
            raise SystemExit("Section-first cutover not ready: `outline_state.jsonl` must report `structure_phase: decomposed` and `h3_status: stable` before writer-context-pack.")

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/outline.yml",
        "outline/subsection_briefs.jsonl",
        "outline/chapter_briefs.jsonl",
        "outline/evidence_drafts.jsonl",
        "outline/anchor_sheet.jsonl",
        "outline/evidence_bindings.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/writer_context_packs.jsonl"]

    outline_path = workspace / inputs[0]
    briefs_path = workspace / inputs[1]
    chapter_path = workspace / inputs[2]
    packs_path = workspace / inputs[3]
    anchors_path = workspace / inputs[4]
    bindings_path = workspace / inputs[5]
    bib_path = workspace / inputs[6]

    out_path = workspace / (outputs[0] if outputs else "outline/writer_context_packs.jsonl")
    ensure_dir(out_path.parent)

    freeze_marker = out_path.parent / "writer_context_packs.refined.ok"
    if out_path.exists() and out_path.stat().st_size > 0 and freeze_marker.exists():
        return 0
    if out_path.exists() and out_path.stat().st_size > 0:
        _backup_existing(out_path)

    _assert_h3_cutover_ready(workspace=workspace, consumer="writer-context-pack")

    outline = load_yaml(outline_path) if outline_path.exists() else []
    subsections = _iter_outline_subsections(outline)
    if not subsections:
        raise SystemExit(f"No H3 subsections found in {outline_path}")

    bibkeys = _bib_keys(bib_path)

    briefs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(briefs_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            briefs_by_sub[sid] = rec

    chapters_by_sec: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(chapter_path):
        sec_id = str(rec.get("section_id") or "").strip()
        if sec_id:
            chapters_by_sec[sec_id] = rec

    packs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(packs_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            packs_by_sub[sid] = rec

    anchors_by_sub: dict[str, list[dict[str, Any]]] = {}
    for rec in _load_jsonl(anchors_path):
        sid = str(rec.get("sub_id") or "").strip()
        anchors = rec.get("anchors") or []
        if sid and isinstance(anchors, list):
            anchors_by_sub[sid] = [a for a in anchors if isinstance(a, dict)]

    bindings_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(bindings_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            bindings_by_sub[sid] = rec

    # Chapter-scoped union of mapped bibkeys.
    chapter_union: dict[str, set[str]] = {}
    for sub in subsections:
        sid = sub["sub_id"]
        sec_id = sub["section_id"]
        mapped = (bindings_by_sub.get(sid) or {}).get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        bucket = chapter_union.setdefault(sec_id, set())
        for bk in mapped:
            bk = str(bk).strip()
            if bk and (not bibkeys or bk in bibkeys):
                bucket.add(bk)

    # Global bibkeys: mapped across multiple subsections (cross-cutting foundations/benchmarks/surveys).
    mapped_counts: dict[str, int] = {}
    for rec in bindings_by_sub.values():
        mapped = rec.get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        for bk in mapped:
            bk = str(bk).strip()
            if not bk:
                continue
            if bibkeys and bk not in bibkeys:
                continue
            mapped_counts[bk] = mapped_counts.get(bk, 0) + 1
    global_threshold = _global_citation_min_subsections(workspace)
    mapped_global = sorted([k for k, n in mapped_counts.items() if n >= int(global_threshold)])

    # Trim policy (avoid silent truncation; keep long enough to preserve concrete detail).
    TRIM = {
        "default": 400,
        "anchor_fact": 420,
        "highlight_excerpt": 280,
        "comparison_write_prompt": 420,
        "eval_bullet": 320,
        "limitation_excerpt": 320,
    }

    # Paper voice palette is data-driven (semantic), not hard-coded.
    # Users may override per-workspace via `outline/paper_voice_palette.json`.
    palette = _load_voice_palette(workspace=workspace, repo_root=repo_root)

    forbidden = [str(x).strip() for x in (palette.get('forbidden_pipeline_voice') or []) if str(x).strip()]
    high_risk = [str(x).strip() for x in (palette.get('high_risk_templates') or []) if str(x).strip()]

    # Back-compat: keep a single flat list for writers that expect `do_not_repeat_phrases`.
    # Treat `forbidden` as hard (must not appear). Treat `high_risk` as rewrite triggers.
    DO_NOT_REPEAT = list(dict.fromkeys(forbidden + high_risk))

    # Positive guidance (paper voice): small phrase palettes + rewrite stems.
    # Keep these semantic and short; the draft must not read like template narration.
    PAPER_VOICE_PALETTE = {
        'forbidden_pipeline_voice': forbidden,
        'high_risk_templates': high_risk,
        'opener_archetypes': palette.get('opener_archetypes') or {
            'tension-first': ['A key tension is', 'The central trade-off is', 'A recurring constraint is'],
            'decision-first': ['A practical decision is', 'One design choice is', 'One consequential design choice is'],
            'scope-first': ['What matters first is whether', 'The comparison only stabilizes when', 'The useful question is whether'],
            'contrast-first': ['A useful contrast is between', 'One sharp contrast is between', 'A persistent contrast is between'],
        },
        'synthesis_stems': palette.get('synthesis_stems')
        or ['Across these studies,', 'Collectively,', 'In summary,', 'The evidence suggests that', 'A consistent theme is that'],
        'rewrite_rules': palette.get('rewrite_rules')
        or [
            {'avoid_stem': 'This subsection surveys', 'prefer_stem': 'A key tension is'},
            {'avoid_stem': 'In this subsection', 'prefer_stem': 'We focus on'},
            {'avoid_stem': 'Next, we move', 'prefer_stem': 'Having established'},
            {'avoid_stem': 'We now turn', 'prefer_stem': 'We then examine'},
            {'avoid_stem': 'survey comparisons should', 'prefer_stem': 'Across protocols, we observe'},
        ],
        "discourse_stem_watchlist": [str(x).strip() for x in (palette.get("discourse_stem_watchlist") or []) if str(x).strip()],
        "discourse_stem_rewrites": palette.get("discourse_stem_rewrites") or {},
        "role_cards": palette.get("role_cards") or {},
        "version": str(palette.get("version") or "").strip(),
    }

    records: list[dict[str, Any]] = []
    now = now_iso_seconds()
    draft_profile = _draft_profile(workspace)
    global_text_usage: dict[str, int] = {}

    for sub in subsections:
        sid = sub["sub_id"]
        title = sub["title"]
        sec_id = sub["section_id"]
        sec_title = sub["section_title"]

        brief = briefs_by_sub.get(sid) or {}
        pack = packs_by_sub.get(sid) or {}
        binding = bindings_by_sub.get(sid) or {}
        chapter = chapters_by_sec.get(sec_id) or {}
        upstream_blocking = [str(x).strip() for x in (pack.get("blocking_missing") or []) if str(x).strip()]
        upstream_downgrade = [str(x).strip() for x in (pack.get("downgrade_signals") or []) if str(x).strip()]

        rq = str(brief.get("rq") or "").strip()
        thesis = str(brief.get("thesis") or "").strip()
        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        clusters = [x for x in (brief.get("clusters") or []) if isinstance(x, dict)]
        paragraph_plan = brief.get("paragraph_plan") or []

        tension_statement = str(brief.get("tension_statement") or "").strip()
        eval_anchor = brief.get("evaluation_anchor_minimal") or {}
        if not isinstance(eval_anchor, dict):
            eval_anchor = {}
        bridge_terms = [str(x).strip() for x in (brief.get("bridge_terms") or []) if str(x).strip()]
        contrast_hook = re.sub(r"\s+", " ", str(brief.get("contrast_hook") or "").strip())
        required_fields = [str(x).strip() for x in (brief.get("required_evidence_fields") or []) if str(x).strip()]
        relevance_terms = bridge_terms + ([contrast_hook] if contrast_hook else []) + required_fields
        profile_limits = _profile_limits(draft_profile)

        mapped = [str(x).strip() for x in (binding.get("mapped_bibkeys") or []) if str(x).strip()]
        selected = [str(x).strip() for x in (binding.get("bibkeys") or []) if str(x).strip()]
        mapped = [k for k in mapped if (not bibkeys or k in bibkeys)]
        selected = [k for k in selected if (not bibkeys or k in bibkeys)]

        # Anchor facts (evidence hooks).
        anchors_raw = anchors_by_sub.get(sid) or []
        anchor_pool: list[dict[str, Any]] = []
        anchor_facts: list[dict[str, Any]] = []
        anchors_considered = 0
        anchors_dropped_no_cites = 0
        anchors_dropped_sanitized = 0

        raw_limit = 10 if draft_profile == "course_paper" else 16
        keep_limit = 6 if draft_profile == "course_paper" else (12 if draft_profile == "deep" else 10)

        for a in anchors_raw[:raw_limit]:
            anchors_considered += 1
            cites = _normalize_cite_keys(a.get("citations") or [], bibkeys=bibkeys)
            if not cites:
                anchors_dropped_no_cites += 1
                continue
            text = _sanitize_source_text(a.get("text") or "")
            if not text or _EVIDENCE_POLICY_DISCLAIMER_RE.search(text):
                anchors_dropped_sanitized += 1
                continue

            anchor_pool.append(
                {
                    "hook_type": str(a.get("hook_type") or "").strip(),
                    "text": _trim(text, max_len=TRIM["anchor_fact"]),
                    "citations": cites,
                    "paper_id": str(a.get("paper_id") or "").strip(),
                    "evidence_id": str(a.get("evidence_id") or "").strip(),
                    "pointer": str(a.get("pointer") or "").strip(),
                }
            )
        anchor_facts = _rank_text_records(anchor_pool, title=title, axes=axes, extras=relevance_terms, global_text_usage=global_text_usage)[:keep_limit]

        # Comparison cards (A-vs-B contrasts).
        raw_comparisons = pack.get("concrete_comparisons") or []
        raw_claims = pack.get("claim_candidates") or []
        comparisons_considered = 0
        comparisons_dropped_no_highlights = 0
        comparisons_dropped_one_sided = 0
        hl_dropped_no_cites = 0
        hl_dropped_sanitized = 0

        comparison_cards: list[dict[str, Any]] = []
        comp_raw_limit = 14
        comp_keep_limit = int(profile_limits.get("comparison_keep_limit") or (9 if draft_profile == "deep" else 7))
        pair_keep_limit = int(profile_limits.get("comparison_pair_limit") or comp_keep_limit)

        pair_seen_counts: dict[tuple[str, str], int] = {}
        for comp in (raw_comparisons or [])[:comp_raw_limit]:
            if not isinstance(comp, dict):
                continue
            comparisons_considered += 1

            cites = _normalize_cite_keys(comp.get("citations") or [], bibkeys=bibkeys)

            def _hl(side: str) -> list[dict[str, Any]]:
                nonlocal hl_dropped_no_cites, hl_dropped_sanitized
                out: list[dict[str, Any]] = []
                for hl in (comp.get(side) or [])[:3]:
                    if not isinstance(hl, dict):
                        continue
                    hcites = _normalize_cite_keys(hl.get("citations") or [], bibkeys=bibkeys)
                    if not hcites:
                        hl_dropped_no_cites += 1
                        continue
                    excerpt = _sanitize_source_text(hl.get("excerpt") or "")
                    if not excerpt:
                        hl_dropped_sanitized += 1
                        continue
                    out.append(
                        {
                            "paper_id": str(hl.get("paper_id") or "").strip(),
                            "evidence_id": str(hl.get("evidence_id") or "").strip(),
                            "excerpt": _trim(excerpt, max_len=TRIM["highlight_excerpt"]),
                            "citations": hcites,
                            "pointer": str(hl.get("pointer") or "").strip(),
                        }
                    )
                return out

            card = {
                "axis": str(comp.get("axis") or "").strip(),
                "A_label": str(comp.get("A_label") or "").strip(),
                "B_label": str(comp.get("B_label") or "").strip(),
                "citations": cites,
                "A_highlights": _hl("A_highlights"),
                "B_highlights": _hl("B_highlights"),
                "write_prompt": _trim(comp.get("write_prompt") or "", max_len=TRIM["comparison_write_prompt"]),
            }
            if not card["A_highlights"] or not card["B_highlights"]:
                comparisons_dropped_one_sided += 1
                continue
            pair_key = tuple(sorted([card["A_label"], card["B_label"]]))
            if card["axis"] and (card["A_highlights"] and card["B_highlights"] and card["citations"]):
                if pair_seen_counts.get(pair_key, 0) >= pair_keep_limit:
                    comparisons_dropped_no_highlights += 1
                    continue
                comparison_cards.append(card)
                pair_seen_counts[pair_key] = pair_seen_counts.get(pair_key, 0) + 1
            else:
                comparisons_dropped_no_highlights += 1

            if len(comparison_cards) >= comp_keep_limit:
                break

        claim_pool: list[dict[str, Any]] = []
        claim_candidates: list[dict[str, Any]] = []
        claims_considered = 0
        claims_dropped_no_cites = 0
        claims_dropped_sanitized = 0
        for claim in (raw_claims or [])[:8]:
            if not isinstance(claim, dict):
                continue
            claims_considered += 1
            cites = _normalize_cite_keys(claim.get("citations") or [], bibkeys=bibkeys)
            if not cites:
                claims_dropped_no_cites += 1
                continue
            text = _sanitize_source_text(claim.get("claim") or "")
            if not text:
                claims_dropped_sanitized += 1
                continue
            if _GENERIC_META_RE.search(text) or not _text_relevant_to_topic(text, title=title, axes=axes, extras=relevance_terms):
                claims_dropped_sanitized += 1
                continue
            claim_pool.append(
                {
                    "claim": text,
                    "citations": cites,
                    "evidence_field": str(claim.get("evidence_field") or "").strip(),
                }
            )
        claim_candidates = _rank_text_records(claim_pool, title=title, axes=axes, extras=relevance_terms, global_text_usage=global_text_usage)[: int(profile_limits.get("claim_keep_limit") or 6)]

        if len(anchor_facts) < keep_limit:
            backfill_anchor_pool: list[dict[str, Any]] = list(anchor_facts)
            for card in comparison_cards:
                for side in ("A_highlights", "B_highlights"):
                    for hl in (card.get(side) or [])[:2]:
                        if not isinstance(hl, dict):
                            continue
                        excerpt = _sanitize_source_text(hl.get("excerpt") or "")
                        cites = _normalize_cite_keys(hl.get("citations") or [], bibkeys=bibkeys)
                        if not excerpt or not cites:
                            continue
                        backfill_anchor_pool.append(
                            {
                                "hook_type": "comparison_highlight",
                                "text": _trim(excerpt, max_len=TRIM["anchor_fact"]),
                                "citations": cites,
                                "paper_id": str(hl.get("paper_id") or "").strip(),
                                "evidence_id": str(hl.get("evidence_id") or "").strip(),
                                "pointer": str(hl.get("pointer") or "").strip(),
                            }
                        )
            for claim in claim_candidates:
                text_claim = _sanitize_source_text(claim.get("claim") or "")
                cites = _normalize_cite_keys(claim.get("citations") or [], bibkeys=bibkeys)
                if not text_claim or not cites:
                    continue
                backfill_anchor_pool.append(
                    {
                        "hook_type": "claim_backfill",
                        "text": _trim(text_claim, max_len=TRIM["anchor_fact"]),
                        "citations": cites,
                        "paper_id": "",
                        "evidence_id": "",
                        "pointer": "",
                    }
                )
            anchor_facts = _rank_text_records(
                backfill_anchor_pool,
                title=title,
                axes=axes,
                extras=relevance_terms,
                global_text_usage=global_text_usage,
            )[:keep_limit]

        for rec in anchor_facts:
            key = _normalized_text_key(rec.get("text") or "")
            if key:
                global_text_usage[key] = global_text_usage.get(key, 0) + 1
        for rec in claim_candidates:
            key = _normalized_text_key(rec.get("claim") or "")
            if key:
                global_text_usage[key] = global_text_usage.get(key, 0) + 1

        # Evaluation protocol bullets.
        raw_eval = pack.get("evaluation_protocol") or []
        eval_considered = 0
        eval_dropped_no_cites = 0

        eval_token_list_style = False
        eval_inventory_count = 0

        eval_proto: list[dict[str, Any]] = []
        for it in (raw_eval or [])[:10]:
            if not isinstance(it, dict):
                continue
            eval_considered += 1
            cites = _normalize_cite_keys(it.get("citations") or [], bibkeys=bibkeys)
            if not cites:
                eval_dropped_no_cites += 1
                continue
            bullet = _trim(it.get("bullet") or "", max_len=TRIM["eval_bullet"])
            kind = re.sub(r"\s+", " ", str(it.get("kind") or "").strip()) or "protocol_guardrail"
            if re.match(r"(?i)^evaluation tokens mentioned in mapped evidence:\s*", bullet):
                eval_token_list_style = True
                bullet = re.sub(r"(?i)^evaluation tokens mentioned in mapped evidence:\s*", "Evaluation mentions include: ", bullet)
                bullet = bullet.replace(";", ",")
                bullet = re.sub(r"\s+,", ",", bullet)
                bullet = re.sub(r"\s{2,}", " ", bullet).strip()
                kind = "benchmark_inventory"
            if re.match(r"(?i)^evaluation mentions include:\s*", bullet):
                eval_token_list_style = True
                kind = "benchmark_inventory"
            if kind == "benchmark_inventory":
                eval_inventory_count += 1
            eval_proto.append({"kind": kind, "bullet": bullet, "citations": cites})
            if len(eval_proto) >= 8:
                break

        # Failure/limitation hooks.
        raw_lim = pack.get("failures_limitations") or []
        lim_considered = 0
        lim_dropped_no_cites = 0
        lim_dropped_sanitized = 0

        lim_pool: list[dict[str, Any]] = []
        lim_hooks: list[dict[str, Any]] = []
        for it in (raw_lim or [])[:14]:
            if not isinstance(it, dict):
                continue
            lim_considered += 1
            cites = _normalize_cite_keys(it.get("citations") or [], bibkeys=bibkeys)
            if not cites:
                lim_dropped_no_cites += 1
                continue
            # `evidence-draft` uses `bullet` (not `excerpt`) for failures/limitations.
            text = it.get("excerpt") or it.get("bullet") or it.get("text") or ""
            excerpt = _sanitize_source_text(text)
            if not excerpt or _EVIDENCE_POLICY_DISCLAIMER_RE.search(excerpt):
                lim_dropped_sanitized += 1
                continue
            if not _has_negative_limit_signal(excerpt):
                lim_dropped_sanitized += 1
                continue
            lim_pool.append(
                {
                    "excerpt": _trim(excerpt, max_len=TRIM["limitation_excerpt"]),
                    "citations": cites,
                    "pointer": str(it.get("pointer") or "").strip(),
                }
            )
        lim_keep_limit = 5 if draft_profile == "course_paper" else (10 if draft_profile == "deep" else 8)
        lim_hooks = _rank_text_records(lim_pool, title=title, axes=axes, extras=relevance_terms, global_text_usage=global_text_usage)[:lim_keep_limit]
        for rec in lim_hooks:
            key = _normalized_text_key(rec.get("excerpt") or "")
            if key:
                global_text_usage[key] = global_text_usage.get(key, 0) + 1

        # Availability minima (used by gates and self-loops).
        if draft_profile == "course_paper":
            min_anchor = 6
            min_comp = 3
            min_lim = 2
        elif draft_profile == "deep":
            min_anchor = 12
            min_comp = 6
            min_lim = 3
        else:
            min_anchor = 10
            min_comp = 4
            min_lim = 3

        # Writer-executable minima: smaller than availability minima, but still forces real argument moves.
        # A150++ (survey deliverable) expects denser packs; keep the writer minima non-trivial so drafting
        # does not collapse into per-paper summaries.
        if draft_profile == "course_paper":
            must_anchor = 3
            must_comp = 2
            must_lim = 1
        elif draft_profile == "deep":
            must_anchor = 6
            must_comp = 6
            must_lim = 3
        else:
            must_anchor = 5
            must_comp = 5
            must_lim = 3

        must_use = {
            "min_anchor_facts": must_anchor,
            "min_comparison_cards": must_comp,
            "min_limitation_hooks": must_lim,
            "require_cited_numeric_if_available": not any(
                "quantitative evidence lacks enough protocol context" in low.lower() or "abstract-level" in low.lower()
                for low in upstream_downgrade
            ),
            "require_multi_cite_synthesis_paragraph": True,
            "thesis_required": True,
        }

        pack_warnings: list[str] = []
        if not thesis:
            pack_warnings.append(
                "Missing `thesis` in subsection briefs; fix `subsection-briefs` so the writer has a central claim to execute."
            )
        if eval_token_list_style:
            pack_warnings.append(
                "Evaluation protocol bullets are token-list style; avoid copying them as sentences. Prefer subsection-specific benchmarks/metrics from `anchor_facts` and state task/metric/constraint explicitly."
            )
        if len(anchor_facts) < min_anchor:
            pack_warnings.append(
                "Too few anchor facts after trimming; strengthen `anchor-sheet` or upstream evidence packs to avoid generic prose."
            )
        if len(comparison_cards) < min_comp:
            pack_warnings.append(
                "Too few comparison cards after trimming; strengthen `evidence-draft` (excerpt-level A-vs-B contrasts) to avoid per-paper summaries."
            )
        if comparisons_dropped_one_sided:
            pack_warnings.append(
                "Some comparison cards were dropped because only one side had usable highlights; fix `evidence-draft` instead of letting the writer improvise an A-vs-B contrast."
            )
        if len(claim_candidates) < 2:
            pack_warnings.append(
                "Too few usable claim candidates after trimming; strengthen `evidence-draft` so the writer can state concrete subsection-level takeaways instead of replaying comparison templates."
            )
        if len(eval_proto) < 1:
            pack_warnings.append(
                "Missing evaluation protocol bullets; strengthen `evidence-draft` so the writer can anchor comparisons to benchmarks/metrics."
            )
        if len(lim_hooks) < min_lim:
            pack_warnings.append(
                "Too few limitation hooks; strengthen `evidence-draft` so limitations are concrete (not generic future work)."
            )
        if eval_inventory_count and eval_inventory_count == len(eval_proto):
            pack_warnings.append(
                "Evaluation protocol is mostly benchmark inventory metadata; downstream writers should anchor numbers with subsection-specific evidence rather than replaying benchmark-name lists."
            )
        for msg in upstream_blocking:
            if msg not in pack_warnings:
                pack_warnings.append(f"Upstream blocker: {msg}")
        for msg in upstream_downgrade:
            if msg not in pack_warnings:
                pack_warnings.append(f"Upstream caution: {msg}")

        if anchors_considered and anchors_dropped_no_cites / max(1, anchors_considered) >= 0.5:
            pack_warnings.append(
                "Many anchor facts were dropped due to missing citations; ensure `anchor-sheet` records citations for each anchor."
            )

        pack_stats = {
            "anchors": {
                "raw": len(anchors_raw),
                "considered": anchors_considered,
                "kept": len(anchor_facts),
                "dropped_no_cites": anchors_dropped_no_cites,
                "dropped_sanitized": anchors_dropped_sanitized,
            },
            "comparisons": {
                "raw": len([c for c in (raw_comparisons or []) if isinstance(c, dict)]),
                "considered": comparisons_considered,
                "kept": len(comparison_cards),
                "dropped_no_highlights": comparisons_dropped_no_highlights,
                "dropped_one_sided": comparisons_dropped_one_sided,
                "highlights_dropped_no_cites": hl_dropped_no_cites,
                "highlights_dropped_sanitized": hl_dropped_sanitized,
            },
            "claims": {
                "raw": len([c for c in (raw_claims or []) if isinstance(c, dict)]),
                "considered": claims_considered,
                "kept": len(claim_candidates),
                "dropped_no_cites": claims_dropped_no_cites,
                "dropped_sanitized": claims_dropped_sanitized,
            },
            "evaluation_protocol": {
                "raw": len([e for e in (raw_eval or []) if isinstance(e, dict)]),
                "considered": eval_considered,
                "kept": len(eval_proto),
                "dropped_no_cites": eval_dropped_no_cites,
            },
            "limitation_hooks": {
                "raw": len([l for l in (raw_lim or []) if isinstance(l, dict)]),
                "considered": lim_considered,
                "kept": len(lim_hooks),
                "dropped_no_cites": lim_dropped_no_cites,
                "dropped_sanitized": lim_dropped_sanitized,
            },
            "trim_policy": TRIM,
        }

        opener_mode = _stable_choice(f"opener:{sid}", ["tension-first", "decision-first", "contrast-first", "protocol-first", "lens-first"]) or "tension-first"
        opener_hint = {
            "tension-first": "Start with the subsection’s central tension/trade-off; end paragraph 1 with the thesis.",
            "decision-first": "Start with a builder/research decision; state what it depends on; end paragraph 1 with the thesis.",
            "contrast-first": "Start with an explicit A-vs-B contrast; state why it matters; end paragraph 1 with the thesis.",
            "protocol-first": "Start with comparability constraints (protocol/budget/tool access); state what they make meaningful; end paragraph 1 with the thesis.",
            "lens-first": "Start by naming the lens (interface/protocol/threat model); state what it reveals; end paragraph 1 with the thesis.",
        }.get(opener_mode, "")


        record = {
            "sub_id": sid,
            "title": title,
            "section_id": sec_id,
            "section_title": sec_title,
            "rq": rq,
            "thesis": thesis,
            "tension_statement": tension_statement,
            "evaluation_anchor_minimal": eval_anchor,
            "paper_voice_palette": PAPER_VOICE_PALETTE,
            "opener_mode": opener_mode,
            "opener_hint": opener_hint,
            "axes": axes,
            # Transition handles (NO NEW FACTS): carried from subsection briefs so writers
            # can keep connectors specific without leaking outline meta into the final draft.
            "bridge_terms": [str(x).strip() for x in (brief.get("bridge_terms") or []) if str(x).strip()],
            "contrast_hook": str(brief.get("contrast_hook") or "").strip(),
            "required_evidence_fields": [str(x).strip() for x in (brief.get("required_evidence_fields") or []) if str(x).strip()],
            "paragraph_plan": paragraph_plan,
            "clusters": clusters,
            "chapter_throughline": chapter.get("throughline") or [],
            "chapter_key_contrasts": chapter.get("key_contrasts") or [],
            "chapter_synthesis_mode": str(chapter.get("synthesis_mode") or "").strip(),
            "allowed_bibkeys_selected": selected,
            "allowed_bibkeys_mapped": mapped,
            "allowed_bibkeys_chapter": sorted(chapter_union.get(sec_id, set())),
            "allowed_bibkeys_global": mapped_global,
            "evidence_ids": [str(e).strip() for e in (binding.get("evidence_ids") or []) if str(e).strip()],
            "anchor_facts": anchor_facts,
            "comparison_cards": comparison_cards,
            "claim_candidates": claim_candidates,
            "evaluation_protocol": eval_proto,
            "limitation_hooks": lim_hooks,
            "blocking_missing": upstream_blocking,
            "downgrade_signals": upstream_downgrade,
            "must_use": must_use,
            "do_not_repeat_phrases": DO_NOT_REPEAT,
            "pack_warnings": pack_warnings,
            "pack_stats": pack_stats,
            "generated_at": now,
        }

        records.append(record)

    write_jsonl(out_path, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
