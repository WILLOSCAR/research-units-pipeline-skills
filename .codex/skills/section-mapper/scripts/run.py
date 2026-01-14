from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


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
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import load_yaml, normalize_title_for_dedupe, parse_semicolon_list, read_jsonl, tokenize, write_tsv

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
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

    papers = _load_core_set(core_path)
    metadata = read_jsonl(workspace / "papers" / "papers_dedup.jsonl")
    outline = load_yaml(outline_path) or []

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
                "_tokens": set(_filter_tokens(tokenize(f"{title} {abstract}"))),
            }
        )

    subsections = _iter_subsections(outline)
    if not subsections:
        write_tsv(out_path, [], fieldnames=["section_id", "section_title", "paper_id", "why"])
        return 0

    per_subsection = max(1, int(args.per_subsection))
    diversity_penalty = max(0, int(args.diversity_penalty))
    soft_limit, hard_limit = _compute_limits(
        soft_limit=int(args.soft_limit),
        hard_limit=int(args.hard_limit),
        subsections=len(subsections),
        papers=len(enriched),
        per_subsection=per_subsection,
    )

    scored_by_subsection: dict[str, list[tuple[int, int, str, list[str], dict[str, Any]]]] = {}
    hardness: list[tuple[int, int, str]] = []
    for idx, subsection in enumerate(subsections):
        section_id = subsection["id"]
        title = subsection["title"]
        bullets = subsection.get("bullets") or []
        tokens = set(_filter_tokens(tokenize(f"{title} {' '.join([str(b) for b in bullets])}")))
        scored: list[tuple[int, int, str, list[str], dict[str, Any]]] = []
        title_tokens = set(_filter_tokens(tokenize(title)))
        for paper in enriched:
            ptokens = paper.get("_tokens") or set()
            overlap = sorted(tokens & ptokens)
            paper_title_tokens = set(_filter_tokens(tokenize(str(paper.get("title") or ""))))
            title_overlap = sorted(title_tokens & paper_title_tokens)
            score = len(overlap) + 5 * len(title_overlap)
            year_raw = str(paper.get("year") or "").strip()
            year_int = int(year_raw) if year_raw.isdigit() else 0
            scored.append((score, year_int, paper.get("paper_id") or "", (title_overlap + overlap)[:6], paper))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
        scored_by_subsection[section_id] = scored
        positive = sum(1 for s, _, _, _, _ in scored[: max(30, per_subsection * 12)] if s > 0)
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
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
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


def _rationale(*, section_title: str, paper_title: str, matched_terms: list[str], score: int, uses_before: int) -> str:
    section_title = (section_title or "").strip()
    paper_title = (paper_title or "").strip()
    terms = [t for t in (matched_terms or []) if str(t).strip()]
    term_str = ", ".join([str(t).strip() for t in terms[:3]])
    reuse = f" (also mapped {uses_before}× already)" if uses_before else ""

    if score <= 0:
        return f"Included for coverage/diversity despite weak lexical overlap; broadly relevant to '{section_title}'.{reuse}"
    if term_str:
        return f"Matches subsection '{section_title}' via shared terms ({term_str}) in the paper title/abstract.{reuse}"
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
    auto_hard = auto_soft + 3
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

    def _pick_from(cands: list[tuple[int, int, str, list[str], dict[str, Any]]], *, target: int, require_positive: bool) -> None:
        for score, year, pid, matched_terms, paper in _iter_sorted(cands):
            if len(picked) >= target:
                return
            if not pid or pid in picked_ids:
                continue
            if not _allowed(pid):
                continue
            if require_positive and score <= 0:
                continue
            uses_before = usage_count.get(pid, 0)
            picked.append((score, year, pid, matched_terms, paper, uses_before))
            picked_ids.add(pid)

    target_high = k if k == 1 else max(1, k - 1)
    _pick_from(pool, target=target_high, require_positive=True)

    # Reserve 1 slot for an older "classic" (when possible) to encourage evolutionary context.
    if k >= 2 and len(picked) < k:
        classic_candidates = [
            it
            for it in pool
            if it[0] > 0 and it[1] > 0 and it[2] not in picked_ids and _allowed(it[2])
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

    _pick_from(pool, target=k, require_positive=True)
    _pick_from(pool, target=k, require_positive=False)
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

    lines.extend(["", "## Subsections with weak lexical signal", "", "| subsection | picked_scores | notes |", "|---|---|---|"])
    weak = 0
    for subsection in subsections:
        sid = subsection["id"]
        title = subsection["title"]
        picks = picks_by_subsection.get(sid) or []
        scores = [p[0] for p in picks]
        if not scores:
            continue
        if max(scores) <= 0:
            weak += 1
            lines.append(f"| {sid} {title} | {scores} | all picks have score<=0; refine outline tokens or mapping |")
        elif sum(1 for s in scores if s > 0) < max(1, per_subsection // 2):
            weak += 1
            lines.append(f"| {sid} {title} | {scores} | few positive-score picks; consider manual semantic mapping |")
    if weak == 0:
        lines.append("| (none) | - | - |")
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
    lock_path = workspace / "PIPELINE.lock.md"
    if lock_path.exists():
        try:
            for raw in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line.startswith("pipeline:"):
                    continue
                pipeline = line.split(":", 1)[1].strip().lower()
                if "arxiv-survey" in pipeline:
                    # Survey drafting needs high cite density to enable evidence-first writing.
                    return 18
                break
        except Exception:
            pass
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
