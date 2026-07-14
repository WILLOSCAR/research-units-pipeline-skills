from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


_OUTLINE_SCAFFOLD_TOKENS = {
    "anchors",
    "appear",
    "architecture",
    "based",
    "belongs",
    "canonical",
    "chapter",
    "choices",
    "comparison",
    "comparisons",
    "compute",
    "concrete",
    "constraints",
    "core",
    "cues",
    "design",
    "differs",
    "drive",
    "evidence",
    "expected",
    "explain",
    "explicit",
    "failure",
    "identify",
    "include",
    "intent",
    "latency",
    "limitations",
    "major",
    "measured",
    "mechanism",
    "modes",
    "must",
    "name",
    "needs",
    "neighboring",
    "paper",
    "possible",
    "recent",
    "representative",
    "scope",
    "section",
    "seminal",
    "setup",
    "subsection",
    "subtopics",
    "training",
    "trade",
    "within",
    "work",
}

_DEFAULT_MINIMUM_SCORE = 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--per-subsection", type=int, default=0)
    parser.add_argument(
        "--diversity-penalty",
        type=int,
        default=3,
        help="Penalty applied per prior assignment to reduce over-reuse of the same paper across many subsections.",
    )
    parser.add_argument(
        "--soft-limit",
        type=int,
        default=0,
        help="Soft cap for how many subsections a paper can appear in (0 = auto).",
    )
    parser.add_argument(
        "--hard-limit",
        type=int,
        default=0,
        help="Hard cap for how many subsections a paper can appear in (0 = auto).",
    )
    parser.add_argument(
        "--minimum-score",
        type=int,
        default=_DEFAULT_MINIMUM_SCORE,
        help=(
            "Minimum section-specific relevance score required for an automatic mapping. "
            "Candidates below the threshold are left unmapped instead of being used as filler."
        ),
    )
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
        load_yaml,
        normalize_title_for_dedupe,
        parse_semicolon_list,
        read_jsonl,
        refinement_marker_is_current,
        tokenize,
        write_tsv,
    )

    workspace = Path(args.workspace).resolve()

    per_cfg = _per_subsection_from_queries(workspace / "queries.md")
    if int(args.per_subsection) <= 0:
        args.per_subsection = int(per_cfg) if per_cfg else _default_per_subsection_for_workspace(workspace)
    inputs = parse_semicolon_list(args.inputs) or ["papers/core_set.csv", "outline/outline.yml"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/mapping.tsv"]

    core_path = workspace / inputs[0]
    outline_path = workspace / inputs[1]
    out_path = workspace / outputs[0]

    # Explicit freeze policy: only skip regeneration if the user creates `outline/mapping.refined.ok`.
    # Otherwise always regenerate and keep a timestamped backup of the previous file.
    freeze_marker = out_path.parent / "mapping.refined.ok"
    domain_pack_paths = sorted((Path(__file__).resolve().parents[1] / "assets" / "domain_packs").glob("*.json"))
    prerequisites = [out_path, core_path, outline_path, workspace / "queries.md", Path(__file__), *domain_pack_paths]
    if out_path.exists() and out_path.stat().st_size > 0:
        if refinement_marker_is_current(freeze_marker, prerequisites):
            return 0
        if freeze_marker.exists():
            freeze_marker.unlink()
        _backup_existing(out_path)

    papers = _load_core_set(core_path)
    metadata = read_jsonl(workspace / "papers" / "papers_dedup.jsonl")
    outline = load_yaml(outline_path) or []
    workspace_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (workspace / "GOAL.md", workspace / "queries.md")
        if path.exists()
    )
    domain_packs = _load_domain_packs(domain_pack_paths)

    meta_by_url = {str(r.get("url") or r.get("id") or "").strip(): r for r in metadata}
    meta_by_key: dict[str, dict[str, Any]] = {}
    for rec in metadata:
        title = str(rec.get("title") or "").strip()
        year = str(rec.get("year") or "").strip()
        if not title:
            continue
        key = f"{normalize_title_for_dedupe(title)}::{year}"
        meta_by_key[key] = rec

    enriched: list[dict[str, Any]] = []
    for paper in papers:
        url = str(paper.get("url") or "").strip()
        title = str(paper.get("title") or "").strip()
        year = str(paper.get("year") or "").strip()
        meta = meta_by_url.get(url)
        if not meta and title and year:
            meta = meta_by_key.get(f"{normalize_title_for_dedupe(title)}::{year}")
        abstract = str((meta or {}).get("abstract") or "").strip()
        enriched.append(
            {
                **paper,
                "abstract": abstract,
                "_title_tokens": set(_filter_tokens(tokenize(title))),
                "_abstract_tokens": set(_filter_tokens(tokenize(abstract))),
                "_tokens": set(_filter_tokens(tokenize(f"{title} {abstract}"))),
            }
        )

    subsections = _iter_subsections(outline)
    if not subsections:
        write_tsv(out_path, [], fieldnames=["section_id", "section_title", "paper_id", "why"])
        return 0

    per_subsection = max(1, int(args.per_subsection))
    diversity_penalty = max(0, int(args.diversity_penalty))
    minimum_score = max(1, int(args.minimum_score))
    soft_limit, hard_limit = _compute_limits(
        soft_limit=int(args.soft_limit),
        hard_limit=int(args.hard_limit),
        subsections=len(subsections),
        papers=len(enriched),
        per_subsection=per_subsection,
    )

    candidate_corpus_tokens = [
        set(
            _filter_tokens(
                tokenize(f"{str(record.get('title') or '')} {str(record.get('abstract') or '')}")
            )
        )
        for record in metadata
        if str(record.get("title") or "").strip()
    ]
    if not candidate_corpus_tokens:
        candidate_corpus_tokens = [set(paper.get("_tokens") or set()) for paper in enriched]
    paper_common_tokens = _common_document_tokens(candidate_corpus_tokens, ratio=0.65)
    paper_token_frequencies = _document_token_frequencies(
        candidate_corpus_tokens
    )
    high_signal_ceiling = max(2, math.ceil(max(1, len(candidate_corpus_tokens)) * 0.20))
    high_signal_tokens = {
        token for token, count in paper_token_frequencies.items() if count <= high_signal_ceiling
    }
    subsection_token_sets = [
        set(_filter_tokens(tokenize(f"{subsection['title']} {' '.join(str(b) for b in subsection.get('bullets') or [])}")))
        for subsection in subsections
    ]
    subsection_common_tokens = _common_document_tokens(subsection_token_sets, ratio=0.60)
    excluded_query_tokens = paper_common_tokens | subsection_common_tokens | _OUTLINE_SCAFFOLD_TOKENS

    scored_by_subsection: dict[str, list[tuple[int, int, str, list[str], dict[str, Any]]]] = {}
    query_terms_by_subsection: dict[str, list[str]] = {}
    query_token_sets_by_subsection: dict[str, tuple[set[str], set[str]]] = {}
    domain_rules_by_subsection: dict[str, list[dict[str, Any]]] = {}
    hardness: list[tuple[int, int, str]] = []
    for idx, subsection in enumerate(subsections):
        section_id = subsection["id"]
        title = subsection["title"]
        bullets = subsection.get("bullets") or []
        raw_title_tokens = set(_filter_tokens(tokenize(title)))
        raw_context_tokens = set(_filter_tokens(tokenize(f"{title} {' '.join([str(b) for b in bullets])}")))
        title_tokens = raw_title_tokens - paper_common_tokens - _OUTLINE_SCAFFOLD_TOKENS
        context_tokens = raw_context_tokens - excluded_query_tokens
        if not title_tokens:
            title_tokens = raw_title_tokens - _OUTLINE_SCAFFOLD_TOKENS - paper_common_tokens
        if not context_tokens:
            context_tokens = set(title_tokens)
        query_terms_by_subsection[section_id] = sorted(title_tokens | context_tokens)
        query_token_sets_by_subsection[section_id] = (title_tokens, context_tokens)
        domain_rules = _domain_section_rules(
            workspace_text=workspace_text,
            section_title=title,
            packs=domain_packs,
        )
        domain_rules_by_subsection[section_id] = domain_rules
        scored: list[tuple[int, int, str, list[str], dict[str, Any]]] = []
        for paper in enriched:
            score, matched_terms = _score_candidate(
                title_tokens=title_tokens,
                context_tokens=context_tokens,
                paper_title_tokens=set(paper.get("_title_tokens") or set()),
                paper_abstract_tokens=set(paper.get("_abstract_tokens") or set()),
                high_signal_tokens=high_signal_tokens,
            )
            score, matched_terms = _apply_domain_section_rules(
                score=score,
                matched_terms=matched_terms,
                paper_title=str(paper.get("title") or ""),
                paper_abstract=str(paper.get("abstract") or ""),
                rules=domain_rules,
            )
            year_raw = str(paper.get("year") or "").strip()
            year_int = int(year_raw) if year_raw.isdigit() else 0
            scored.append((score, year_int, paper.get("paper_id") or "", matched_terms[:6], paper))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
        scored_by_subsection[section_id] = scored
        positive = sum(1 for s, _, _, _, _ in scored[: max(30, per_subsection * 12)] if s >= minimum_score)
        hardness.append((positive, idx, section_id))

    usage_count: dict[str, int] = {}
    picks_by_subsection: dict[str, list[tuple[int, int, str, list[str], dict[str, Any], int]]] = {}

    # Process "hard" subsections first so scarce relevant papers are allocated before global reuse builds up.
    hardness.sort(key=lambda t: (t[0], t[1], t[2]))
    for _, _, section_id in hardness:
        scored = scored_by_subsection.get(section_id) or []
        picks = _pick_diverse(
            scored,
            k=per_subsection,
            usage_count=usage_count,
            diversity_penalty=diversity_penalty,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            minimum_score=minimum_score,
        )
        picks_by_subsection[section_id] = picks
        for _, _, paper_id, _, _, uses_before in picks:
            usage_count[paper_id] = max(usage_count.get(paper_id, 0), uses_before + 1)

    rows: list[dict] = []
    for subsection in subsections:
        section_id = subsection["id"]
        title = subsection["title"]
        for score, _, _, matched_terms, paper, uses_before in picks_by_subsection.get(section_id, []):
            rows.append(
                {
                    "section_id": section_id,
                    "section_title": title,
                    "paper_id": paper["paper_id"],
                    "why": _rationale(section_title=title, paper_title=str(paper.get("title") or ""), matched_terms=matched_terms, score=score, uses_before=uses_before),
                }
            )

    write_tsv(out_path, rows, fieldnames=["section_id", "section_title", "paper_id", "why"])

    core_keys = {
        f"{normalize_title_for_dedupe(str(paper.get('title') or ''))}::{str(paper.get('year') or '').strip()}"
        for paper in papers
    }
    gap_candidates = _build_gap_candidate_rows(
        subsections=subsections,
        picks_by_subsection=picks_by_subsection,
        query_token_sets_by_subsection=query_token_sets_by_subsection,
        candidate_records=metadata,
        core_keys=core_keys,
        per_subsection=per_subsection,
        minimum_score=minimum_score,
        high_signal_tokens=high_signal_tokens,
        tokenize=tokenize,
        normalize_title=normalize_title_for_dedupe,
        domain_rules_by_subsection=domain_rules_by_subsection,
    )
    write_tsv(
        workspace / "outline" / "mapping_gap_candidates.tsv",
        gap_candidates,
        fieldnames=[
            "section_id",
            "section_title",
            "missing_slots",
            "candidate_title",
            "year",
            "url",
            "relevance_score",
            "discriminative_terms",
        ],
    )

    try:
        from tooling.common import atomic_write_text

        report_path = workspace / "outline" / "mapping_report.md"
        atomic_write_text(
            report_path,
            _render_mapping_report(
                subsections=subsections,
                picks_by_subsection=picks_by_subsection,
                usage_count=usage_count,
                diversity_penalty=diversity_penalty,
                soft_limit=soft_limit,
                hard_limit=hard_limit,
                per_subsection=per_subsection,
                minimum_score=minimum_score,
                query_terms_by_subsection=query_terms_by_subsection,
            ),
        )
    except Exception:
        # Best-effort side artifact only.
        pass
    return 0



def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

def _load_core_set(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Missing core set: {path}")
    papers: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            paper_id = str(row.get("paper_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if not paper_id or not title:
                continue
            papers.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "year": str(row.get("year") or "").strip(),
                    "url": str(row.get("url") or "").strip(),
                }
            )
    return papers


def _iter_subsections(outline: list) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in outline:
        if not isinstance(section, dict):
            continue
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sid = str(subsection.get("id") or "").strip()
            title = str(subsection.get("title") or "").strip()
            if sid and title:
                items.append(
                    {
                        "id": sid,
                        "title": title,
                        "bullets": subsection.get("bullets") or [],
                    }
                )
    return items


def _filter_tokens(tokens: list[str]) -> list[str]:
    stop = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "also",
        "about",
        "after",
        "be",
        "between",
        "by",
        "can",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "more",
        "most",
        "of",
        "on",
        "or",
        "over",
        "that",
        "the",
        "their",
        "than",
        "this",
        "through",
        "to",
        "under",
        "using",
        "via",
        "were",
        "which",
        "while",
        "will",
        "with",
    }
    out: list[str] = []
    for t in tokens:
        if len(t) < 3:
            continue
        if t in stop:
            continue
        out.append(t)
    return out


def _common_document_tokens(
    documents: list[set[str]],
    *,
    ratio: float,
    minimum_documents: int = 3,
) -> set[str]:
    """Find corpus-wide tokens that cannot distinguish one document from another."""
    docs = [set(doc) for doc in documents if doc]
    if len(docs) < minimum_documents:
        return set()
    threshold = max(minimum_documents, math.ceil(len(docs) * max(0.0, min(1.0, ratio))))
    frequencies = _document_token_frequencies(docs)
    return {token for token, count in frequencies.items() if count >= threshold}


def _document_token_frequencies(documents: list[set[str]]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for doc in documents:
        frequencies.update(set(doc))
    return frequencies


def _score_candidate(
    *,
    title_tokens: set[str],
    context_tokens: set[str],
    paper_title_tokens: set[str],
    paper_abstract_tokens: set[str],
    high_signal_tokens: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Score section-specific evidence, weighting title alignment over generic prose overlap."""
    primary_match = title_tokens & (paper_title_tokens | paper_abstract_tokens)
    if not primary_match:
        return 0, []

    title_title = title_tokens & paper_title_tokens
    signal_tokens = high_signal_tokens if high_signal_tokens is not None else (title_tokens | context_tokens)
    high_signal_match = primary_match & signal_tokens
    high_signal_context = (context_tokens & (paper_title_tokens | paper_abstract_tokens)) & signal_tokens
    high_signal_context_title = high_signal_context & paper_title_tokens
    primary_supported = bool(title_title or high_signal_match or len(primary_match) >= 2)
    context_supported = bool(high_signal_context_title or len(high_signal_context) >= 2)
    if not primary_supported and not context_supported:
        return 0, []

    title_abstract = (title_tokens & paper_abstract_tokens) - title_title
    context_title = (context_tokens & paper_title_tokens) - title_title
    already_matched = title_title | title_abstract | context_title
    context_abstract = (context_tokens & paper_abstract_tokens) - already_matched

    score = (
        8 * len(title_title)
        + 3 * len(title_abstract)
        + 4 * len(context_title)
        + len(context_abstract)
    )
    matched_terms = (
        sorted(title_title)
        + sorted(title_abstract)
        + sorted(context_title)
        + sorted(context_abstract)
    )
    return score, matched_terms


def _load_domain_packs(paths: list[Path]) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if isinstance(data, dict):
            packs.append(data)
    return packs


def _domain_section_rules(
    *,
    workspace_text: str,
    section_title: str,
    packs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    workspace_low = str(workspace_text or "").lower()
    title_low = str(section_title or "").lower()
    selected: list[dict[str, Any]] = []
    for pack in packs:
        detect = pack.get("detect") if isinstance(pack.get("detect"), dict) else {}
        groups = detect.get("all_any_groups") if isinstance(detect, dict) else []
        if groups and not all(
            any(str(term or "").strip().lower() in workspace_low for term in group)
            for group in groups
            if isinstance(group, list) and group
        ):
            continue
        for rule in pack.get("section_rules") or []:
            if not isinstance(rule, dict):
                continue
            match_any = [str(term or "").strip().lower() for term in (rule.get("match_any") or [])]
            if match_any and not any(term and term in title_low for term in match_any):
                continue
            selected.append(rule)
    return selected


def _apply_domain_section_rules(
    *,
    score: int,
    matched_terms: list[str],
    paper_title: str,
    paper_abstract: str,
    rules: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    if not rules:
        return score, matched_terms

    title_low = str(paper_title or "").lower()
    abstract_low = str(paper_abstract or "").lower()
    adjusted = int(score)
    terms = list(matched_terms)
    for rule in rules:
        rejected = [str(term or "").strip().lower() for term in (rule.get("reject_title_any") or [])]
        if any(term and term in title_low for term in rejected):
            return 0, []

        required = [str(term or "").strip().lower() for term in (rule.get("title_require_any") or [])]
        required_hits = [term for term in required if term and term in title_low]
        if required and not required_hits:
            return 0, []

        title_boost_terms = [str(term or "").strip().lower() for term in (rule.get("title_boost_any") or [])]
        abstract_boost_terms = [str(term or "").strip().lower() for term in (rule.get("abstract_boost_any") or [])]
        title_hits = [term for term in title_boost_terms if term and term in title_low]
        abstract_hits = [term for term in abstract_boost_terms if term and term in abstract_low]
        adjusted += min(2, len(title_hits)) * max(0, int(rule.get("title_boost") or 0))
        adjusted += min(2, len(abstract_hits)) * max(0, int(rule.get("abstract_boost") or 0))
        for term in required_hits + title_hits + abstract_hits:
            label = term.strip(" .,-")
            if label and label not in terms:
                terms.append(label)

    return adjusted, terms


def _build_gap_candidate_rows(
    *,
    subsections: list[dict[str, Any]],
    picks_by_subsection: dict[str, list[tuple[int, int, str, list[str], dict[str, Any], int]]],
    query_token_sets_by_subsection: dict[str, tuple[set[str], set[str]]],
    candidate_records: list[dict[str, Any]],
    core_keys: set[str],
    per_subsection: int,
    minimum_score: int,
    high_signal_tokens: set[str],
    tokenize: Any,
    normalize_title: Any,
    domain_rules_by_subsection: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subsection in subsections:
        section_id = str(subsection.get("id") or "").strip()
        section_title = str(subsection.get("title") or "").strip()
        missing_slots = max(0, per_subsection - len(picks_by_subsection.get(section_id) or []))
        if not section_id or missing_slots <= 0:
            continue
        title_tokens, context_tokens = query_token_sets_by_subsection.get(section_id, (set(), set()))
        domain_rules = (domain_rules_by_subsection or {}).get(section_id) or []
        scored: list[tuple[int, int, str, list[str], dict[str, Any]]] = []
        for record in candidate_records:
            title = str(record.get("title") or "").strip()
            year = str(record.get("year") or "").strip()
            if not title:
                continue
            key = f"{normalize_title(title)}::{year}"
            if key in core_keys:
                continue
            abstract = str(record.get("abstract") or "").strip()
            score, matched_terms = _score_candidate(
                title_tokens=title_tokens,
                context_tokens=context_tokens,
                paper_title_tokens=set(_filter_tokens(tokenize(title))),
                paper_abstract_tokens=set(_filter_tokens(tokenize(abstract))),
                high_signal_tokens=high_signal_tokens,
            )
            score, matched_terms = _apply_domain_section_rules(
                score=score,
                matched_terms=matched_terms,
                paper_title=title,
                paper_abstract=abstract,
                rules=domain_rules,
            )
            if score < minimum_score:
                continue
            year_int = int(year) if year.isdigit() else 0
            url = str(record.get("url") or record.get("id") or "").strip()
            scored.append((score, year_int, url, matched_terms, record))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        suggestion_limit = max(6, missing_slots * 3)
        for score, _, url, matched_terms, record in scored[:suggestion_limit]:
            rows.append(
                {
                    "section_id": section_id,
                    "section_title": section_title,
                    "missing_slots": missing_slots,
                    "candidate_title": str(record.get("title") or "").strip(),
                    "year": str(record.get("year") or "").strip(),
                    "url": url,
                    "relevance_score": score,
                    "discriminative_terms": ", ".join(matched_terms[:6]),
                }
            )
    return rows


def _rationale(*, section_title: str, paper_title: str, matched_terms: list[str], score: int, uses_before: int) -> str:
    section_title = (section_title or "").strip()
    paper_title = (paper_title or "").strip()
    terms = [t for t in (matched_terms or []) if str(t).strip()]
    term_str = ", ".join([str(t).strip() for t in terms[:3]])
    reuse = f" (also mapped {uses_before}× already)" if uses_before else ""

    if score <= 0:
        return f"Low-confidence candidate for '{section_title}'; manual review is required.{reuse}"
    if term_str:
        return f"Section-specific evidence for '{section_title}'; discriminative concepts: {term_str}.{reuse}"
    if paper_title:
        return f"Title suggests relevance to subsection '{section_title}' (sparse explicit term overlap).{reuse}"
    return f"Selected as a representative for subsection '{section_title}' based on overall similarity.{reuse}"



def _compute_limits(*, soft_limit: int, hard_limit: int, subsections: int, papers: int, per_subsection: int) -> tuple[int, int]:
    if soft_limit > 0 and hard_limit > 0 and hard_limit < soft_limit:
        soft_limit, hard_limit = hard_limit, soft_limit
    if soft_limit > 0 and hard_limit > 0:
        return soft_limit, hard_limit

    total_assignments = max(1, int(subsections) * int(per_subsection))
    avg = total_assignments / max(1, int(papers))
    auto_soft = max(2, min(6, int(avg * 2) + 1))
    minimum_for_capacity = max(1, math.ceil(total_assignments / max(1, int(papers))))
    ratio_cap = max(3, math.ceil(max(1, int(subsections)) * 0.60))
    auto_hard = max(minimum_for_capacity, min(auto_soft + 3, ratio_cap))
    auto_soft = min(auto_soft, auto_hard)
    if soft_limit <= 0:
        soft_limit = auto_soft
    if hard_limit <= 0:
        hard_limit = auto_hard
    return soft_limit, hard_limit


def _pick_diverse(
    scored: list[tuple[int, int, str, list[str], dict[str, Any]]],
    *,
    k: int,
    usage_count: dict[str, int],
    diversity_penalty: int,
    soft_limit: int,
    hard_limit: int,
    minimum_score: int = _DEFAULT_MINIMUM_SCORE,
) -> list[tuple[int, int, str, list[str], dict[str, Any], int]]:
    """Pick K papers with a global reuse penalty + optional classic slot."""
    if k <= 0:
        return []

    pool = scored[: max(40, k * 12)]
    picked: list[tuple[int, int, str, list[str], dict[str, Any], int]] = []
    picked_ids: set[str] = set()

    def _allowed(pid: str) -> bool:
        return usage_count.get(pid, 0) < hard_limit

    def _adjusted(item: tuple[int, int, str, list[str], dict[str, Any]]) -> int:
        score, _, pid, _, _ = item
        uses = usage_count.get(pid, 0)
        penalty = diversity_penalty * uses
        if uses >= soft_limit:
            penalty += diversity_penalty * 2 * (uses - soft_limit + 1)
        return score - penalty

    def _iter_sorted(cands: list[tuple[int, int, str, list[str], dict[str, Any]]]) -> list[tuple[int, int, str, list[str], dict[str, Any]]]:
        return sorted(cands, key=lambda it: (-_adjusted(it), -it[0], -it[1], it[2]))

    def _pick_from(cands: list[tuple[int, int, str, list[str], dict[str, Any]]], *, target: int) -> None:
        for score, year, pid, matched_terms, paper in _iter_sorted(cands):
            if len(picked) >= target:
                return
            if not pid or pid in picked_ids:
                continue
            if not _allowed(pid):
                continue
            if score < minimum_score:
                continue
            uses_before = usage_count.get(pid, 0)
            picked.append((score, year, pid, matched_terms, paper, uses_before))
            picked_ids.add(pid)

    target_high = k if k == 1 else max(1, k - 1)
    _pick_from(pool, target=target_high)

    # Reserve 1 slot for an older "classic" (when possible) to encourage evolutionary context.
    if k >= 2 and len(picked) < k:
        classic_candidates = [
            it
            for it in pool
            if it[0] >= minimum_score and it[1] > 0 and it[2] not in picked_ids and _allowed(it[2])
        ]
        if classic_candidates:
            classic = min(
                classic_candidates,
                key=lambda it: (
                    it[1],  # oldest year
                    -it[0],  # but still relevant
                    usage_count.get(it[2], 0),  # prefer less-used
                    it[2],
                ),
            )
            score, year, pid, matched_terms, paper = classic
            uses_before = usage_count.get(pid, 0)
            picked.append((score, year, pid, matched_terms, paper, uses_before))
            picked_ids.add(pid)

    _pick_from(pool, target=k)
    return picked[:k]


def _render_mapping_report(
    *,
    subsections: list[dict[str, Any]],
    picks_by_subsection: dict[str, list[tuple[int, int, str, list[str], dict[str, Any], int]]],
    usage_count: dict[str, int],
    diversity_penalty: int,
    soft_limit: int,
    hard_limit: int,
    per_subsection: int,
    minimum_score: int,
    query_terms_by_subsection: dict[str, list[str]],
) -> str:
    total_subsections = len(subsections)
    total_picks = sum(len(v) for v in picks_by_subsection.values())
    unique_papers = len([p for p, c in usage_count.items() if c > 0])

    lines: list[str] = [
        "# Mapping report",
        "",
        f"- Subsections: `{total_subsections}`",
        f"- Per-subsection target: `{per_subsection}`",
        f"- Total assignments: `{total_picks}`",
        f"- Unique papers used: `{unique_papers}`",
        f"- Diversity: `penalty={diversity_penalty}`, `soft_limit={soft_limit}`, `hard_limit={hard_limit}`",
        f"- Automatic relevance floor: `score >= {minimum_score}`",
        "- Gap repair candidates: `outline/mapping_gap_candidates.tsv`",
        "",
        "## Most reused papers",
        "",
        "| paper_id | subsections |",
        "|---|---:|",
    ]
    for pid, count in sorted(usage_count.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
        if count <= 1:
            continue
        lines.append(f"| {pid} | {count} |")
    if lines[-1] == "|---|---:|":
        lines.append("| (none) | 0 |")

    lines.extend(["", "## Coverage and relevance diagnostics", "", "| subsection | mapped | picked_scores | discriminative_terms | notes |", "|---|---:|---|---|---|"])
    weak = 0
    for subsection in subsections:
        sid = subsection["id"]
        title = subsection["title"]
        picks = picks_by_subsection.get(sid) or []
        scores = [p[0] for p in picks]
        terms = ", ".join((query_terms_by_subsection.get(sid) or [])[:10]) or "(none)"
        if not scores:
            weak += 1
            note = "no candidate met the relevance floor; expand evidence or refine the outline"
        elif len(scores) < per_subsection:
            weak += 1
            note = "target not met; do not fill with low-confidence papers"
        else:
            note = "PASS"
        lines.append(f"| {sid} {title} | {len(scores)}/{per_subsection} | {scores} | {terms} | {note} |")
    lines.append("")
    return "\n".join(lines)


def _per_subsection_from_queries(path: Path) -> int:
    if not path.exists():
        return 0
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        if key not in {"per_subsection", "mapping_per_subsection", "section_mapper_per_subsection"}:
            continue
        value = value.split('#', 1)[0].strip().strip('"').strip("'")
        try:
            n = int(value)
        except Exception:
            return 0
        return n if n > 0 else 0
    return 0



def _default_per_subsection_for_workspace(workspace: Path) -> int:
    from tooling.common import pipeline_profile

    profile = pipeline_profile(workspace)
    if profile == "arxiv-survey":
        return 28
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
