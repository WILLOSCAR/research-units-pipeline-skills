from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

_STOPWORDS = {
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

_GENERIC_WORDS = {
    "survey",
    "review",
    "tutorial",
    "paper",
    "approach",
    "method",
    "methods",
    "model",
    "models",
    "framework",
    "frameworks",
    "system",
    "systems",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core-size", type=int, default=0)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import ensure_dir, normalize_title_for_dedupe, parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()

    core_size_cfg = _core_size_from_queries(workspace / 'queries.md')
    if core_size_cfg:
        args.core_size = int(core_size_cfg)
    if int(args.core_size) <= 0:
        args.core_size = _default_core_size_for_workspace(workspace)

    inputs = parse_semicolon_list(args.inputs) or ["papers/papers_raw.jsonl"]
    outputs = parse_semicolon_list(args.outputs) or ["papers/papers_dedup.jsonl", "papers/core_set.csv"]

    raw_path = workspace / inputs[0]
    dedup_path = workspace / outputs[0]
    core_path = workspace / outputs[1] if len(outputs) > 1 else workspace / "papers/core_set.csv"

    records = read_jsonl(raw_path)
    if not records:
        raise SystemExit(f"No records found in {raw_path}")

    best_by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        title = str(record.get("title") or "").strip()
        if not title:
            continue
        year = record.get("year")
        try:
            year_int = int(year) if year is not None and str(year).strip() else None
        except ValueError:
            year_int = None
        key = f"{normalize_title_for_dedupe(title)}::{year_int or ''}"
        record = dict(record)
        record["dedup_key"] = key

        prev = best_by_key.get(key)
        if not prev:
            best_by_key[key] = record
            continue

        prev_abs = str(prev.get("abstract") or "")
        rec_abs = str(record.get("abstract") or "")
        prev_auth = prev.get("authors") or []
        rec_auth = record.get("authors") or []
        prev_score = len(prev_abs) + 10 * (len(prev_auth) if isinstance(prev_auth, list) else 0)
        rec_score = len(rec_abs) + 10 * (len(rec_auth) if isinstance(rec_auth, list) else 0)
        if rec_score > prev_score:
            best_by_key[key] = record

    deduped = list(best_by_key.values())
    deduped.sort(key=lambda r: (-(int(r.get("year") or 0)), str(r.get("title") or "")))
    write_jsonl(dedup_path, deduped)

    core_size = max(1, int(args.core_size))
    query_tokens = _query_tokens(workspace)
    pinned = _pinned_records(workspace, deduped)
    if query_tokens:
        scored = []
        for record in deduped:
            score = _relevance_score(record, query_tokens=query_tokens)
            scored.append((score, int(record.get("year") or 0), str(record.get("title") or ""), record))
        # Prefer relevance; break ties by recency and title.
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))

        picked: list[dict[str, Any]] = []
        picked_keys: set[str] = set()
        for record in pinned[:core_size]:
            key = str(record.get("dedup_key") or "")
            if key and key in picked_keys:
                continue
            picked_keys.add(key)
            record = dict(record)
            record["_rank_score"] = int(record.get("_rank_score") or 0) or 999
            record["_rank_reason"] = "pinned_classic"
            picked.append(record)

        for score, _, _, record in scored:
            if len(picked) >= core_size:
                break
            if score <= 0:
                continue
            key = str(record.get("dedup_key") or "")
            if key and key in picked_keys:
                continue
            picked_keys.add(key)
            record = dict(record)
            record["_rank_score"] = score
            picked.append(record)
            if len(picked) >= core_size:
                break

        # If relevance filtering is too strict, backfill by recency.
        if len(picked) < core_size:
            for record in deduped:
                key = str(record.get("dedup_key") or "")
                if key and key in picked_keys:
                    continue
                picked_keys.add(key)
                record = dict(record)
                record["_rank_score"] = 0
                record["_rank_reason"] = "backfill_by_year"
                picked.append(record)
                if len(picked) >= core_size:
                    break

        core = picked[: min(core_size, len(picked))]
    else:
        core = deduped[: min(core_size, len(deduped))]

    ensure_dir(core_path.parent)
    with core_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "paper_id",
            "title",
            "year",
            "url",
            "arxiv_id",
            "primary_category",
            "categories",
            "pdf_url",
            "topic",
            "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, record in enumerate(core, start=1):
            paper_id = f"P{idx:04d}"
            score = int(record.get("_rank_score") or 0)
            rank_reason = str(record.get("_rank_reason") or "").strip()
            reason = "ranked_by=relevance" if query_tokens else "ranked_by=year"
            if query_tokens:
                reason = f"{reason};score={score}"
                if rank_reason:
                    reason = f"{reason};{rank_reason}"
            categories = record.get("categories") or []
            if isinstance(categories, list):
                categories_str = ",".join([str(c).strip() for c in categories if str(c).strip()])
            else:
                categories_str = str(categories).strip()
            writer.writerow(
                {
                    "paper_id": paper_id,
                    "title": str(record.get("title") or "").strip(),
                    "year": str(record.get("year") or "").strip(),
                    "url": str(record.get("url") or record.get("id") or "").strip(),
                    "arxiv_id": str(record.get("arxiv_id") or "").strip(),
                    "primary_category": str(record.get("primary_category") or "").strip(),
                    "categories": categories_str,
                    "pdf_url": str(record.get("pdf_url") or "").strip(),
                    "topic": "",
                    "reason": reason,
                }
            )

    return 0


def _query_tokens(workspace: Path) -> set[str]:
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return set()
    keywords = _parse_queries_md(queries_path)
    if not keywords:
        return set()

    from tooling.common import tokenize

    tokens: set[str] = set()
    for kw in keywords:
        for t in tokenize(kw):
            if len(t) < 3:
                continue
            if t in _STOPWORDS or t in _GENERIC_WORDS:
                continue
            tokens.add(t)
    return tokens


def _core_size_from_queries(path: Path) -> int:
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
        if key not in {"core_size", "core_set_size", "dedupe_core_size"}:
            continue
        value = value.split('#', 1)[0].strip().strip('"').strip("'")
        try:
            n = int(value)
        except Exception:
            return 0
        return n if n > 0 else 0
    return 0




def _default_core_size_for_workspace(workspace: Path) -> int:
    lock_path = workspace / "PIPELINE.lock.md"
    if lock_path.exists():
        try:
            for raw in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line.startswith("pipeline:"):
                    continue
                pipeline = line.split(":", 1)[1].strip().lower()
                if "arxiv-survey" in pipeline:
                    return 150
                break
        except Exception:
            pass
    return 50


def _parse_queries_md(path: Path) -> list[str]:
    keywords: list[str] = []
    mode: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("- keywords:"):
            mode = "keywords"
            continue
        if line.startswith("- exclude:"):
            mode = None
            continue
        if line.startswith("- ") and mode == "keywords":
            value = line[2:].strip().strip('"').strip("'")
            if value:
                keywords.append(value)
    return keywords


def _looks_like_llm_agent_topic(workspace: Path) -> bool:
    queries_path = workspace / "queries.md"
    goal_path = workspace / "GOAL.md"
    text = ""
    if queries_path.exists():
        text += "\n" + queries_path.read_text(encoding="utf-8", errors="ignore")
    if goal_path.exists():
        text += "\n" + goal_path.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    return ("agent" in low or "agents" in low) and ("llm" in low or "language model" in low)


def _pinned_records(workspace: Path, deduped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _looks_like_llm_agent_topic(workspace):
        return []

    # Keep a small set of canonical classics even if they are older / lower-scoring.
    pin_terms = ["react", "toolformer", "reflexion", "autogpt"]
    by_term: dict[str, dict[str, Any]] = {}
    for term in pin_terms:
        best: tuple[int, int, str, dict[str, Any]] | None = None
        for rec in deduped:
            title = str(rec.get("title") or "").strip()
            low = title.lower()
            if term not in low:
                continue
            year = int(rec.get("year") or 0)
            # Prefer the earliest (original) paper; break ties by title length.
            score = -year
            if low.startswith(term + ":") or low.startswith(term + " "):
                score += 1000
            cand = (score, -len(low), low, rec)
            if best is None or cand > best:
                best = cand
        if best is not None:
            by_term[term] = best[-1]

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for term in pin_terms:
        rec = by_term.get(term)
        if not rec:
            continue
        key = str(rec.get("dedup_key") or "").strip()
        if key and key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _relevance_score(record: dict[str, Any], *, query_tokens: set[str]) -> int:
    from tooling.common import tokenize

    title = str(record.get("title") or "").strip()
    abstract = str(record.get("abstract") or "").strip()
    tokens = set(tokenize(f"{title} {abstract}"))
    return sum(1 for t in query_tokens if t in tokens)


if __name__ == "__main__":
    raise SystemExit(main())
