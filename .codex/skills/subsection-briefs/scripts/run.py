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


_META_PAPER_TITLE_RE = re.compile(r"(?i)\b(?:survey|review|overview|taxonomy)\b")
_ASSET_CACHE: dict[str, Any] | None = None


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json_asset(path: Path) -> Any:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return data if isinstance(data, (dict, list)) else {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        if text:
            out.append(text)
    return out


def _runtime_assets() -> dict[str, Any]:
    global _ASSET_CACHE
    if _ASSET_CACHE is not None:
        return _ASSET_CACHE

    root = _skill_root() / "assets"
    phrase_root = root / "phrase_packs"
    domain_root = root / "domain_packs"

    phrase_packs: dict[str, dict[str, Any]] = {}
    for path in sorted(phrase_root.glob("*.json")) if phrase_root.exists() else []:
        data = _load_json_asset(path)
        if isinstance(data, dict):
            phrase_packs[path.stem] = data

    domain_packs: dict[str, dict[str, Any]] = {}
    for path in sorted(domain_root.glob("*.json")) if domain_root.exists() else []:
        data = _load_json_asset(path)
        if not isinstance(data, dict):
            continue
        name = str(data.get("name") or path.stem).strip() or path.stem
        domain_packs[name] = data

    _ASSET_CACHE = {
        "phrase_packs": phrase_packs,
        "domain_packs": domain_packs,
    }
    return _ASSET_CACHE


def _contains_any(text: str, needles: list[str]) -> bool:
    low = (text or "").lower()
    return any(str(n or "").strip().lower() in low for n in needles if str(n or "").strip())


def _selected_domain_packs(*, sub_title: str, goal: str) -> list[dict[str, Any]]:
    assets = _runtime_assets()
    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for name, pack in (assets.get("domain_packs") or {}).items():
        if name == "generic" or not isinstance(pack, dict):
            continue
        detect = pack.get("detect") or {}
        if not isinstance(detect, dict):
            continue

        title_any = _list_strings(detect.get("title_any"))
        goal_any = _list_strings(detect.get("goal_any"))
        title_all = _list_strings(detect.get("title_all"))
        goal_all = _list_strings(detect.get("goal_all"))

        has_goal_rules = bool(goal_any or goal_all)
        goal_matched = False
        title_matched = False

        if goal_any and _contains_any(goal_low, goal_any):
            goal_matched = True
        if goal_all and all(term.lower() in goal_low for term in goal_all):
            goal_matched = True

        if title_any and _contains_any(title_low, title_any):
            title_matched = True
        if title_all and all(term.lower() in title_low for term in title_all):
            title_matched = True

        matched = goal_matched or (title_matched and not has_goal_rules)
        if not matched:
            continue

        priority = int(pack.get("priority") or 100)
        ranked.append((priority, name, pack))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [pack for _, _, pack in ranked]


def _planner_policy(*, sub_title: str, goal: str) -> dict[str, int]:
    assets = _runtime_assets()
    generic = (assets.get("domain_packs") or {}).get("generic") or {}
    policy: dict[str, Any] = {}
    if isinstance(generic.get("planner_policy"), dict):
        policy.update(generic.get("planner_policy") or {})
    for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
        if isinstance(pack.get("planner_policy"), dict):
            policy.update(pack.get("planner_policy") or {})
    return {
        "axis_target": max(5, int(policy.get("axis_target") or 5)),
        "bridge_target": max(3, int(policy.get("bridge_target") or 6)),
        "cluster_min_size": max(2, int(policy.get("cluster_min_size") or 2)),
        "allow_overlap_below_papers": max(3, int(policy.get("allow_overlap_below_papers") or 4)),
        "max_clusters": max(2, int(policy.get("max_clusters") or 2)),
    }


def _apply_pack_axis_rules(*, pack: dict[str, Any], title_low: str, goal_low: str, add: Any) -> None:
    for rule in pack.get("axis_rules") or []:
        if not isinstance(rule, dict):
            continue
        source = str(rule.get("source") or "title").strip().lower()
        haystack = title_low
        if source == "goal":
            haystack = goal_low
        elif source == "both":
            haystack = f"{title_low}\n{goal_low}"

        match_any = _list_strings(rule.get("match_any"))
        if match_any and not _contains_any(haystack, match_any):
            continue

        for item in _list_strings(rule.get("items")):
            add(item)


def _first_formatted_template(*, title: str, joined: str, rules: Any, **kwargs: str) -> str:
    if not isinstance(rules, list):
        return ""
    best_template = ""
    best_score: tuple[int, int] | None = None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match_any = _list_strings(rule.get("match_any"))
        matched = [term for term in match_any if term.lower() in joined.lower()]
        if match_any and not matched:
            continue
        template = str(rule.get("template") or "").strip()
        if template:
            score = (len(matched), sum(len(term) for term in matched))
            if best_score is None or score > best_score:
                best_template = template
                best_score = score
    if not best_template:
        return ""
    context = {"title": title}
    context.update({k: v for k, v in kwargs.items() if isinstance(v, str)})
    return best_template.format(**context)


def _collect_pack_items(*, joined: str, rules: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(rules, list):
        return out
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match_any = _list_strings(rule.get("match_any"))
        if match_any and not _contains_any(joined, match_any):
            continue
        for item in _list_strings(rule.get("items")):
            if item not in out:
                out.append(item)
    return out


def _first_pack_label(*, joined: str, rules: Any) -> str:
    if not isinstance(rules, list):
        return ""
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match_any = _list_strings(rule.get("match_any"))
        if match_any and not _contains_any(joined, match_any):
            continue
        label = re.sub(r"\s+", " ", str(rule.get("label") or "").strip())
        if label:
            return label
    return ""


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

    from tooling.common import (
        ensure_dir,
        latest_outline_state,
        load_workspace_pipeline_spec,
        load_yaml,
        now_iso_seconds,
        parse_semicolon_list,
        read_jsonl,
        read_tsv,
        refinement_marker_is_current,
        write_jsonl,
    )
    from tooling.quality_gate import _draft_profile

    workspace = Path(args.workspace).resolve()
    draft_profile = _draft_profile(workspace)
    spec = load_workspace_pipeline_spec(workspace)
    if spec is not None and str(spec.structure_mode or "").strip() == "section_first":
        state = latest_outline_state(workspace)
        if not state:
            raise SystemExit("Missing outline_state.jsonl; run the section-first C2 planner pass before subsection-briefs.")
        if str(state.get("structure_phase") or "").strip() != "decomposed" or str(state.get("h3_status") or "").strip() != "stable":
            raise SystemExit("Section-first cutover not ready: `outline_state.jsonl` must report `structure_phase: decomposed` and `h3_status: stable` before subsection-briefs.")

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
    domain_pack_dir = Path(__file__).resolve().parents[1] / "assets" / "domain_packs"
    prerequisites = [
        out_path,
        Path(__file__),
        *[workspace / item for item in inputs],
        *sorted(domain_pack_dir.glob("*.json")),
    ]
    if out_path.exists() and out_path.stat().st_size > 0:
        if refinement_marker_is_current(freeze_marker, prerequisites):
            return 0
        if freeze_marker.exists():
            freeze_marker.unlink()
        _backup_existing(out_path)

    _assert_h3_cutover_ready(workspace=workspace, consumer="subsection-briefs")

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
            sub_title=sub_title,
            want=3,
        )

        thesis = _thesis_statement(
            sub_title=sub_title,
            axes=axes,
            evidence_summary=dict(evidence_summary),
            goal=goal,
            clusters=clusters,
        )

        paragraph_plan = _paragraph_plan(
            sub_id=sub_id,
            sub_title=sub_title,
            rq=rq,
            axes=axes,
            clusters=clusters,
            evidence_summary=dict(evidence_summary),
            draft_profile=draft_profile,
        )

        scope_rule = _scope_rule(goal=goal, sub_title=sub_title)

        required_fields = _required_evidence_fields(sub_title=sub_title, axes=axes, goal=goal)
        tension_statement = _tension_statement(sub_title=sub_title, axes=axes, goal=goal)
        eval_anchor = _evaluation_anchor_minimal(
            sub_title=sub_title,
            axes=axes,
            required_evidence_fields=required_fields,
            goal=goal,
        )

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
                "tension_statement": tension_statement,
                "evaluation_anchor_minimal": eval_anchor,
                "required_evidence_fields": required_fields,
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

    # Split on top-level separators, but do NOT split commas inside parentheses.
    # This prevents axes like "evaluation protocol (datasets, metrics, human evaluation)"
    # from being shredded into unusable tokens.
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in raw:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if depth == 0 and ch in ",;；":
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)

    out: list[str] = []
    for p in parts:
        p = re.sub(r"\s+", " ", (p or "").strip())
        # Remove leading conjunctions caused by list formatting ("..., and X").
        p = re.sub(r"(?i)^(?:and|or)\s+", "", p).strip()
        p = re.sub(r"^(?:以及|并且|还有)\s*", "", p).strip()
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


def _thesis_statement(
    *,
    sub_title: str,
    axes: list[str],
    evidence_summary: dict[str, int],
    goal: str,
    clusters: list[dict[str, Any]],
) -> str:
    """Return a 1-sentence, execution-oriented thesis (NO NEW FACTS)."""
    title = re.sub(r"\s+", " ", (sub_title or "").strip())
    a1 = axes[0] if axes else "mechanism and evaluation"
    a2 = axes[1] if len(axes) > 1 else ""
    axes_phrase = a1 if not a2 else f"{a1} and {a2}"
    cluster_labels = [re.sub(r"\s+", " ", str(c.get("label") or "").strip()) for c in (clusters or []) if isinstance(c, dict)]
    cluster_a = cluster_labels[0] if cluster_labels else "one route"
    cluster_b = cluster_labels[1] if len(cluster_labels) > 1 else "another route"

    has_fulltext = int(evidence_summary.get("fulltext", 0) or 0) > 0
    seed = f"thesis:{title}:{axes_phrase}:{'fulltext' if has_fulltext else 'abstract'}"
    title_axes_joined = "\n".join(
        [
            title.lower(),
            " ".join([str(a or "").lower() for a in axes[:5]]),
        ]
    )
    goal_joined = "\n".join(
        [
            title.lower(),
            (goal or "").lower(),
            " ".join([str(a or "").lower() for a in axes[:5]]),
        ]
    )

    for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
        for joined in (title_axes_joined, goal_joined):
            match = _first_formatted_template(
                title=title,
                joined=joined,
                rules=pack.get("thesis_rules"),
                axes_phrase=axes_phrase,
                primary_axis=a1,
                secondary_axis=a2,
                cluster_a=cluster_a,
                cluster_b=cluster_b,
            )
            if match:
                return match

    pack = (_runtime_assets().get("phrase_packs") or {}).get("thesis_patterns") or {}
    key = "fulltext" if has_fulltext else "abstract"
    options = []
    for template in _list_strings(pack.get(key)):
        try:
            options.append(template.format(title=title, axes_phrase=axes_phrase))
        except Exception:
            continue
    if options:
        return _pick(seed, options)

    fallback = str(pack.get("fallback") or "").strip()
    if fallback:
        try:
            return fallback.format(title=title, axes_phrase=axes_phrase)
        except Exception:
            pass

    return f"{title}: {axes_phrase}"


def _tension_statement(*, sub_title: str, axes: list[str], goal: str) -> str:
    """Return a concrete tension sentence (NO NEW FACTS).

    This is meant to be directly usable as the core of paragraph 1 without sounding like
    outline narration (avoid "This subsection...").
    """

    title = re.sub(r"\s+", " ", (sub_title or "").strip())
    axes_joined = " ".join([str(a or "").lower() for a in (axes or [])[:5]])
    title_axes_joined = " ".join([title.lower(), axes_joined]).strip()
    goal_joined = " ".join([title.lower(), (goal or "").lower(), axes_joined]).strip()

    for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
        for joined in (title_axes_joined, goal_joined):
            match = _first_formatted_template(title=title, joined=joined, rules=pack.get("tension_rules"))
            if match:
                return match

    generic_pack = (_runtime_assets().get("domain_packs") or {}).get("generic") or {}
    generic_joined = title_axes_joined
    match = _first_formatted_template(title=title, joined=generic_joined, rules=generic_pack.get("tension_rules"))
    if match:
        return match

    # Fallback: paraphrase axes to reduce slash-style leakage.
    axes_hint = ", ".join(
        [re.sub(r"\s*/\s*", " and ", str(a).strip()) for a in (axes or [])[:2] if str(a).strip()]
    )
    axes_hint = axes_hint or "mechanism and evaluation"
    fallback = str(generic_pack.get("tension_fallback") or "").strip()
    if fallback:
        try:
            return fallback.format(title=title, axes_hint=axes_hint)
        except Exception:
            pass
    return f"{title}: {axes_hint}"


def _evaluation_anchor_minimal(
    *, sub_title: str, axes: list[str], required_evidence_fields: list[str], goal: str
) -> dict[str, str]:
    """Return a minimal evaluation anchor triple (task/metric/constraint).

    Values may be "unknown" when the exact benchmark/protocol is not yet available; the point is to
    reserve slots so later evidence packs can fill them.
    """

    joined = " ".join(
        [(sub_title or "").lower(), (goal or "").lower()]
        + [str(a or "").lower() for a in (axes or [])]
        + [str(x or "").lower() for x in (required_evidence_fields or [])]
    )

    task = "unknown"
    metric = "unknown"
    constraint = "unknown"

    if any(k in joined for k in ["code", "coding", "program", "software"]):
        task = "code tasks"
        metric = "test pass rate / success"
        constraint = "sandbox and budget"
    elif any(k in joined for k in ["robot", "embodied", "manipulation", "policy", "vla", "mobile"]) and any(
        k in joined for k in ["navigation", "benchmark", "metric", "dataset", "real-world", "sim-to-real"]
    ):
        task = "embodied navigation / manipulation tasks"
        metric = "task success / generalization"
        constraint = "embodiment, sensing, and latency"
    elif any(k in joined for k in ["web", "browser", "search"]) or (
        "navigation" in joined and not any(k in joined for k in ["robot", "embodied", "manipulation", "policy", "vla", "mobile"])
    ):
        task = "web/navigation tasks"
        metric = "success rate"
        constraint = "latency and budget"
    elif any(k in joined for k in ["security", "attack", "injection", "jailbreak", "threat"]):
        task = "attack/defense evaluation"
        metric = "attack success rate"
        constraint = "policy/sandbox setting"
    elif any(k in joined for k in ["benchmark", "metric", "dataset", "evaluation"]):
        task = "benchmark tasks"
        metric = "success rate"
        constraint = "budget/cost model"

    return {"task": task, "metric": metric, "constraint": constraint}


def _clean_axis_text(x: str) -> str:
    x = re.sub(r"\s+", " ", (x or "").strip())
    x = x.rstrip(" .;:，；。")
    x = re.sub(r"\s*/\s*", " / ", x)
    return x


def _norm_axis_text(x: str) -> str:
    x = _clean_axis_text(x).lower()
    x = re.sub(r"[^a-z0-9]+", " ", x)
    return x.strip()


def _pack_axis_inventory(packs: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        for rule in pack.get("axis_rules") or []:
            if not isinstance(rule, dict):
                continue
            for item in _list_strings(rule.get("items")):
                out.add(_norm_axis_text(item))
    return out


def _choose_axes(*, sub_title: str, goal: str, evidence_needs: list[str], outline_axes: list[str]) -> list[str]:
    assets = _runtime_assets()
    generic_pack = (assets.get("domain_packs") or {}).get("generic") or {}
    domain_packs = assets.get("domain_packs") or {}
    selected_packs = _selected_domain_packs(sub_title=sub_title, goal=goal)

    pack_axes: list[str] = []
    specific_seed_axes: list[str] = []
    generic_seed_axes: list[str] = []

    def add(bucket: list[str], x: str) -> None:
        x = _clean_axis_text(x)
        if not x:
            return
        low = x.lower()
        if "refine" in low and "evidence" in low:
            return
        # Drop instruction-like scaffold leakage from upstream outline bullets.
        if re.search(r"(?i)\b(?:choose|pick|select|enumerate|avoid)\b", low):
            return
        # Drop ultra-generic axis tokens that are almost always scaffold leakage.
        if _norm_axis_text(x) in {"mechanism", "data", "evaluation", "efficiency", "limitation", "limitations"}:
            return
        if x not in bucket:
            bucket.append(x)

    gate_generic_axes = {
        "core mechanism and system architecture",
        "training and data setup",
        "evaluation protocol",
        "evaluation protocol benchmarks metrics human",
        "evaluation protocol datasets metrics human",
        "evaluation protocol datasets metrics human evaluation",
        "compute and efficiency",
        "compute and latency constraints",
        "efficiency and compute",
        "tool interface contract schemas protocols",
        "tool selection routing policy",
        "sandboxing permissions observability",
        "failure modes and limitations",
    }
    generic_axes = set(_norm_axis_text(a) for a in (_list_strings(generic_pack.get("generic_axes")) or []))
    generic_axes.update(gate_generic_axes)
    generic_axes.update(
        {
            _norm_axis_text("training / data / supervision"),
            _norm_axis_text("efficiency (compute, latency, cost)"),
            _norm_axis_text("failure modes"),
        }
    )

    selected_axis_norms = _pack_axis_inventory(selected_packs)
    foreign_axis_norms = _pack_axis_inventory(
        [
            pack
            for name, pack in domain_packs.items()
            if name not in {"generic", *[str(p.get("name") or "").strip() for p in selected_packs]}
        ]
    )

    for a in evidence_needs:
        cleaned = _clean_axis_text(a)
        axis_norm = _norm_axis_text(cleaned)
        bucket = specific_seed_axes
        if axis_norm in generic_axes or axis_norm in foreign_axis_norms:
            bucket = generic_seed_axes
        if axis_norm in selected_axis_norms:
            bucket = specific_seed_axes
        add(bucket, cleaned)
    for a in outline_axes:
        cleaned = _clean_axis_text(a)
        axis_norm = _norm_axis_text(cleaned)
        bucket = specific_seed_axes
        if axis_norm in generic_axes or axis_norm in foreign_axis_norms:
            bucket = generic_seed_axes
        if axis_norm in selected_axis_norms:
            bucket = specific_seed_axes
        add(bucket, cleaned)

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()

    for pack in selected_packs:
        _apply_pack_axis_rules(
            pack=pack,
            title_low=title_low,
            goal_low=goal_low,
            add=lambda item: add(pack_axes, item),
        )

    # Final fallback: stable generic set.
    fallback_axes = _list_strings(generic_pack.get("fallback_axes")) or [
        "core mechanism and system architecture",
        "training and data setup",
        "evaluation protocol",
        "compute and efficiency",
        "failure modes and limitations",
    ]
    for a in fallback_axes:
        add(generic_seed_axes, a)

    out: list[str] = []
    target = _planner_policy(sub_title=sub_title, goal=goal).get("axis_target", 7)
    for bucket in (pack_axes, specific_seed_axes, generic_seed_axes):
        for a in bucket:
            if a not in out:
                out.append(a)
            if len(out) >= target:
                return out[:target]

    return out[:target]




def _bridge_terms(*, sub_title: str, axes: list[str], goal: str) -> list[str]:
    """Return 3–6 bridge terms for transition-weaver (NO NEW FACTS)."""

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()
    joined = "\n".join([title_low, goal_low])
    assets = _runtime_assets()
    generic_pack = (assets.get("domain_packs") or {}).get("generic") or {}
    bridge_pack = (assets.get("phrase_packs") or {}).get("bridge_contrast") or {}

    stopwords = {x.lower() for x in _list_strings(bridge_pack.get("bridge_stopwords"))} or {"mechanism", "data", "evaluation", "efficiency", "limitations"}
    terms: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if not x:
            return
        if x.lower() in stopwords:
            return
        if x not in terms:
            terms.append(x)

    for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
        for item in _collect_pack_items(joined=joined, rules=pack.get("bridge_rules")):
            add(item)

    axes_joined = "\n".join([str(a or "").lower() for a in axes[:5]])
    for item in _collect_pack_items(joined=axes_joined, rules=generic_pack.get("bridge_axis_rules")):
        add(item)

    if not terms:
        for item in _list_strings(generic_pack.get("bridge_fallback")):
            add(item)

    target = _planner_policy(sub_title=sub_title, goal=goal).get("bridge_target", 6)
    return terms[:target]


def _contrast_hook(*, sub_title: str, axes: list[str], goal: str) -> str:
    """Return a short hook label for transitions (NO NEW FACTS)."""

    title_low = (sub_title or "").lower()
    goal_low = (goal or "").lower()
    joined = "\n".join([title_low, goal_low])
    assets = _runtime_assets()
    generic_pack = (assets.get("domain_packs") or {}).get("generic") or {}
    bridge_pack = (assets.get("phrase_packs") or {}).get("bridge_contrast") or {}

    for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
        label = _first_pack_label(joined=joined, rules=pack.get("contrast_rules"))
        if label:
            return label

    axes_joined = "\n".join([str(a or "").lower() for a in axes])
    label = _first_pack_label(joined=axes_joined, rules=generic_pack.get("contrast_axis_rules"))
    if label:
        return label

    fallback = str(generic_pack.get("contrast_fallback") or "").strip()
    first_axis = (axes[0] if axes else "").strip()
    max_len = int(bridge_pack.get("contrast_fallback_max_len") or 48)
    if fallback and first_axis:
        try:
            rendered = fallback.format(first_axis=first_axis)
            if rendered:
                return rendered[:max_len]
        except Exception:
            pass

    return first_axis[:max_len]


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
        add("failure modes and limitations")
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

    # Embodied / robotics specific bootstrap tags.
    if any(k in text for k in ["robot", "embodied", "manipulation", "navigation", "humanoid", "policy"]):
        tags.add("robot-task")
    if any(
        k in text
        for k in [
            "vision-language-action",
            " vla",
            "vla ",
            "policy backbone",
            "action model",
            "world model",
            "control policy",
        ]
    ):
        tags.add("robot-policy")
    if any(
        k in text
        for k in [
            "pretrain",
            "pre-training",
            "post-training",
            "finetun",
            "supervision",
            "demonstration",
            "dataset",
            "data scaling",
        ]
    ):
        tags.add("robot-data")
    if any(
        k in text
        for k in [
            "transfer",
            "cross-embodiment",
            "cross embodiment",
            "generalization",
            "sim-to-real",
            "sim2real",
            "real-world",
        ]
    ):
        tags.add("robot-transfer")
    if any(
        k in text
        for k in [
            "benchmark",
            "metric",
            "deployment",
            "robustness",
            "stress",
            "safety",
            "reliability",
        ]
    ):
        tags.add("robot-eval")

    return tags


def _build_clusters(*, paper_refs: list[PaperRef], goal: str, sub_title: str, want: int) -> list[dict[str, Any]]:
    """Return 2–3 paper clusters for comparison.

    Quality-gate requirement: at least **two** clusters, each with >=2 papers.
    For mapped sets with >=4 papers, prefer disjoint clusters; overlapping fallback
    is reserved for truly tiny mapped sets only.
    """

    goal_low = (goal or "").lower()
    title_low = (sub_title or "").lower()
    policy = _planner_policy(sub_title=sub_title, goal=goal)
    min_cluster_size = int(policy.get("cluster_min_size") or 2)
    allow_overlap_below_papers = int(policy.get("allow_overlap_below_papers") or 4)
    max_clusters = int(policy.get("max_clusters") or 2)
    all_paper_refs = list(paper_refs)
    filtered_refs = [p for p in paper_refs if not _META_PAPER_TITLE_RE.search(str(p.title or ''))]
    if len(filtered_refs) >= 4:
        paper_refs = filtered_refs
    forbid_video = ("text-to-image" in goal_low or "t2i" in goal_low) and ("video" not in goal_low and "t2v" not in goal_low)
    allow_overlap = len(paper_refs) < allow_overlap_below_papers

    tag_to_papers: dict[str, list[PaperRef]] = {}
    for p in paper_refs:
        tags = _paper_tags(p)
        if forbid_video:
            tags.discard("video")
        for tag in tags:
            tag_to_papers.setdefault(tag, []).append(p)

    candidates = [(tag, ps) for tag, ps in tag_to_papers.items() if len(ps) >= 2]
    candidates.sort(key=lambda t: (-len(t[1]), t[0]))
    low_value_tags = {"evaluation"}
    embodied_mode = any(k in goal_low for k in ["embodied", "robot", "vision-language-action", "vla"])
    if embodied_mode:
        low_value_tags.update({"agents", "memory", "tool-use", "orchestration"})
        if "video" not in title_low and "temporal" not in title_low:
            low_value_tags.add("video")
        if not any(k in title_low for k in ["planning", "reasoning", "world model", "memory"]):
            low_value_tags.add("planning")
    primary_candidates = [(tag, ps) for tag, ps in candidates if tag not in low_value_tags]
    secondary_candidates = [(tag, ps) for tag, ps in candidates if tag in low_value_tags]

    clusters: list[dict[str, Any]] = []
    used_pids: set[str] = set()

    def add_cluster(label: str, rationale: str, ps: list[PaperRef], *, permit_overlap: bool = False) -> bool:
        pids: list[str] = []
        bibs: list[str] = []
        local_seen: set[str] = set()
        for p in sorted(ps, key=lambda x: (-x.year, x.paper_id)):
            if p.paper_id in local_seen:
                continue
            local_seen.add(p.paper_id)
            if not permit_overlap and p.paper_id in used_pids:
                continue
            pids.append(p.paper_id)
            if p.bibkey:
                bibs.append(p.bibkey)
            if len(pids) >= 8:
                break
        bibs = [b for b in bibs if b]
        if len(pids) < min_cluster_size:
            return False
        clusters.append({"label": label, "rationale": rationale, "paper_ids": pids, "bibkeys": bibs})
        if not permit_overlap:
            used_pids.update(pids)
        return True

    def _cluster_rule_groups() -> list[dict[str, Any]]:
        joined = "\n".join([title_low, goal_low])
        built: list[dict[str, Any]] = []
        for pack in _selected_domain_packs(sub_title=sub_title, goal=goal):
            for rule in pack.get("cluster_rules") or []:
                if not isinstance(rule, dict):
                    continue
                match_any = _list_strings(rule.get("match_any"))
                if match_any and not _contains_any(joined, match_any):
                    continue
                for spec in rule.get("clusters") or []:
                    if not isinstance(spec, dict):
                        continue
                    label = re.sub(r"\s+", " ", str(spec.get("label") or "").strip())
                    rationale = re.sub(r"\s+", " ", str(spec.get("rationale") or "").strip())
                    match_terms = _list_strings(spec.get("match_any"))
                    match_tags = {x.lower() for x in _list_strings(spec.get("match_tags_any"))}
                    candidate_refs = all_paper_refs if bool(spec.get("include_meta")) else paper_refs
                    if not label:
                        continue
                    selected: list[PaperRef] = []
                    for p in candidate_refs:
                        title_text = str(p.title or "").lower()
                        paper_tags = _paper_tags(p)
                        if match_terms and _contains_any(title_text, match_terms):
                            selected.append(p)
                            continue
                        if match_tags and any(tag in paper_tags for tag in match_tags):
                            selected.append(p)
                    if add_cluster(label, rationale or "Grouped by domain-pack title keywords.", selected, permit_overlap=False):
                        built.append(clusters[-1])
                    if len(clusters) >= max_clusters:
                        return built
                if len(clusters) >= 2:
                    return built
        return built

    _cluster_rule_groups()

    # Tag-based clusters (bootstrap).
    for tag, ps in (primary_candidates + secondary_candidates)[: max(1, want)]:
        if len(clusters) >= max_clusters:
            break
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
            "robot-task": "Task / embodiment settings",
            "robot-policy": "Policy backbones / action models",
            "robot-data": "Data and supervision strategies",
            "robot-transfer": "Transfer / adaptation studies",
            "robot-eval": "Benchmark / deployment studies",
        }.get(tag, f"{tag} cluster")
        added = add_cluster(label, f"Grouped by keyword tag `{tag}` from titles (bootstrap).", ps, permit_overlap=allow_overlap)
        if added and len(clusters) >= max_clusters:
            break

    # Fallback 1: recency split.
    if len(clusters) < 2 and paper_refs:
        years = [p.year for p in paper_refs if p.year]
        cutoff = (max(years) - 2) if years else 0
        recent = [p for p in paper_refs if p.year and p.year >= cutoff]
        classic = [p for p in paper_refs if p not in recent]
        add_cluster("Recent representative works", "Grouped by recency (bootstrap).", recent, permit_overlap=allow_overlap)
        add_cluster("Earlier / related works", "Grouped by older years (bootstrap).", classic, permit_overlap=allow_overlap)

    # Fallback 2: if one broad bootstrap tag consumed most papers, discard that
    # one-sided partition before building two disjoint comparison groups.
    if len(clusters) < 2:
        clusters.clear()
        used_pids.clear()
        ranked = sorted(paper_refs, key=lambda x: (-x.year, x.paper_id))
        if len(ranked) >= max(min_cluster_size * 2, 4):
            mid = max(min_cluster_size, len(ranked) // 2)
            add_cluster(
                "Mapped subset A",
                "Disjoint split to keep two comparable clusters when bootstrap tags are too entangled.",
                ranked[:mid],
                permit_overlap=False,
            )
            add_cluster(
                "Mapped subset B",
                "Disjoint split to keep two comparable clusters when bootstrap tags are too entangled.",
                ranked[mid:],
                permit_overlap=False,
            )
        elif len(ranked) >= 3:
            add_cluster(
                "Mapped subset A",
                "Overlap-allowed split to ensure two comparable clusters when the mapped set is small.",
                ranked[:2],
                permit_overlap=True,
            )
            add_cluster(
                "Mapped subset B",
                "Overlap-allowed split to ensure two comparable clusters when the mapped set is small.",
                ranked[1:3],
                permit_overlap=True,
            )
        elif len(ranked) >= 2:
            add_cluster(
                "Mapped subset",
                "Small mapped set; use the same pair for both paragraphs, focusing on axis-by-axis contrasts.",
                ranked[:2],
                permit_overlap=True,
            )
            add_cluster(
                "Mapped subset (alt)",
                "Small mapped set; duplicate cluster (writer should compare within the pair along different axes).",
                ranked[:2],
                permit_overlap=True,
            )

    return clusters[:max_clusters]




def _paragraph_plan(
    *,
    sub_id: str,
    sub_title: str,
    rq: str,
    axes: list[str],
    clusters: list[dict[str, Any]],
    evidence_summary: dict[str, int],
    draft_profile: str = "survey",
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
        ["Across these studies,", "Collectively,", "Stepping back,", "Overall,"],
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
            "intent": "Explain cluster A: core mechanism and system architecture and the core approach it takes.",
            "focus": [f"cluster: {c1}", "core mechanism and system architecture", "assumptions"],
            "connector_to_prev": "grounding",
            "connector_phrase": f"baseline route ({c1})",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 3,
            "argument_role": "implementation_cluster_A",
            "intent": "Cluster A implementation details: methodology and data signals and design trade-offs that constrain behavior.",
            "focus": [f"cluster: {c1}", "methodology and design", "design trade-offs", f"axes: {axes_hint}"],
            "connector_to_prev": "elaboration",
            "connector_phrase": "implementation details (design + methodology)",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 4,
            "argument_role": "evaluation_cluster_A",
            "intent": "Cluster A evaluation/trade-offs: where it works, costs (compute/latency), and typical failure modes.",
            "focus": [f"cluster: {c1}", "evaluation anchor", "efficiency", "failure modes"],
            "connector_to_prev": "evaluation",
            "connector_phrase": "evaluation anchor (task/metric/constraint) + failure modes",
            "use_clusters": [c1] if c1 else [],
        },
        {
            "para": 5,
            "argument_role": "contrast_cluster_B",
            "intent": "Explain cluster B (contrast with A): core mechanism and system architecture and what it optimizes for.",
            "focus": [f"cluster: {c2}", f"contrast with {c1}", "core mechanism and system architecture"],
            "connector_to_prev": "contrast",
            "connector_phrase": f"contrast route ({c2} vs {c1})",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 6,
            "argument_role": "implementation_cluster_B",
            "intent": "Cluster B implementation details: methodology and data and design assumptions (mirror A for comparability).",
            "focus": [f"cluster: {c2}", "methodology and design", "design trade-offs", f"axes: {axes_hint}"],
            "connector_to_prev": "elaboration",
            "connector_phrase": "contrast implementation details (B)",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 7,
            "argument_role": "evaluation_cluster_B",
            "intent": "Cluster B evaluation/trade-offs: where it works, costs, and failure modes (mirror A).",
            "focus": [f"cluster: {c2}", "evaluation anchor", "efficiency", "failure modes"],
            "connector_to_prev": "evaluation",
            "connector_phrase": "contrast evaluation anchor + trade-offs (B)",
            "use_clusters": [c2] if c2 else ([c1] if c1 else []),
        },
        {
            "para": 8,
            "argument_role": "cross_paper_synthesis",
            "intent": "Cross-paper synthesis: compare clusters along the main axes (include >=2 citations in one paragraph).",
            "focus": [f"compare {c1} vs {c2}", "multiple citations in one paragraph", f"axes: {axes_hint}"],
            "connector_to_prev": "synthesis",
            "connector_phrase": f"cross-paper synthesis ({c1} vs {c2})",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
        {
            "para": 9,
            "argument_role": "decision_guidance",
            "intent": "Decision guidance: when to choose which route (criteria + evaluation signals + engineering constraints).",
            "focus": ["decision checklist", "evaluation protocol", "practical constraints"],
            "connector_to_prev": "consequence",
            "connector_phrase": "decision guidance / criteria",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
        {
            "para": 10,
            "argument_role": "limitations_open_questions",
            "intent": "Limitations + verification targets; end with a concrete open question to hand off.",
            "focus": ["limitations", f"evidence mode: {mode}", "what needs verification", "open question"],
            "connector_to_prev": "limitations",
            "connector_phrase": "limitations + verification targets",
            "use_clusters": [x for x in [c1, c2, c3] if x],
        },
    ]

    if str(draft_profile or "").strip().lower().replace("-", "_") == "course_paper":
        plan = [plan[index] for index in (0, 1, 3, 4, 7, 9)]
        for index, item in enumerate(plan, start=1):
            item["para"] = index

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
