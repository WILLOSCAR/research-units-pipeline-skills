from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
DOMAIN_PACKS_DIR = ASSETS_DIR / "domain_packs"


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
        backup_existing,
        candidate_keywords,
        dump_yaml,
        parse_semicolon_list,
        read_jsonl,
        refinement_marker_is_current,
        tokenize,
    )

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["papers/core_set.csv"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/taxonomy.yml"]

    core_path = workspace / inputs[0]
    out_path = workspace / outputs[0]
    dedup_path = workspace / "papers" / "papers_dedup.jsonl"

    if not core_path.exists():
        raise SystemExit(f"Missing core set: {core_path}")

    freeze_marker = out_path.parent / "taxonomy.refined.ok"
    prerequisites = [out_path, core_path, dedup_path, workspace / "queries.md", workspace / "GOAL.md", Path(__file__)]
    if refinement_marker_is_current(freeze_marker, prerequisites):
        return 0
    if freeze_marker.exists():
        freeze_marker.unlink()
    if out_path.exists() and out_path.stat().st_size > 0:
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if not _is_placeholder(existing):
            backup_existing(out_path)

    titles: list[str] = []
    core_rows: list[dict[str, str]] = []
    with core_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row = row or {}
            title = str(row.get("title") or "").strip()
            if title:
                titles.append(title)
            core_rows.append({key: str(value or "").strip() for key, value in row.items()})

    dedup = read_jsonl(dedup_path) if dedup_path.exists() else []

    text_blob = "\n".join([_safe_lower(title) for title in titles])
    for rec in dedup:
        if not isinstance(rec, dict):
            continue
        text_blob += "\n" + _safe_lower(str(rec.get("title") or ""))
        text_blob += "\n" + _safe_lower(str(rec.get("abstract") or ""))

    profile = _detect_profile(workspace=workspace, text_blob=text_blob)

    if profile != "generic":
        taxonomy = _load_domain_pack_taxonomy(profile=profile, core_rows=core_rows)
        dump_yaml(out_path, taxonomy)
        return 0

    top_topics = candidate_keywords(titles, top_k=int(args.top_k), min_freq=int(args.min_freq))
    if not top_topics:
        top_topics = ["methods", "evaluation", "applications"]

    taxonomy: list[dict[str, Any]] = []
    for token in top_topics[:4]:
        subset = [title for title in titles if token in set(tokenize(title))]
        sub = candidate_keywords(subset, top_k=6, min_freq=1)
        sub = [item for item in sub if item not in {"overview", "benchmarks", "open", "problems"}]
        if not sub:
            sub = ["problem", "mechanisms", "evaluation", "limitations"]

        rep = _representative_papers(core_rows=core_rows, terms=[token] + list(sub))
        rep_str = ", ".join(rep[:4]) if rep else ""
        desc_terms = ", ".join([_pretty(item) for item in sub[:4]])
        desc_parts = [
            f"{_pretty(token)} groups studies whose scoped evidence emphasizes this concept.",
            f"Its corpus boundary is defined by related mechanisms or settings such as {desc_terms}." if desc_terms else "",
            f"Representative anchors in the current core set are {rep_str}." if rep_str else "",
        ]
        desc = " ".join([part for part in desc_parts if part]).strip()

        taxonomy.append(
            {
                "name": _pretty(token),
                "description": desc,
                "children": [
                    {
                        "name": _pretty(child),
                        "description": _child_description(
                            parent=_pretty(token),
                            child=_pretty(child),
                            core_rows=core_rows,
                            seed_terms=[token, child],
                        ),
                    }
                    for child in sub[:3]
                ],
            }
        )

    if all(not item.get("children") for item in taxonomy):
        raise SystemExit("Failed to build a 2-level taxonomy")

    dump_yaml(out_path, taxonomy)
    return 0



def _pretty(token: str) -> str:
    token = token.replace("_", " ").replace("-", " ").strip()
    return " ".join([word[:1].upper() + word[1:] for word in token.split() if word])



def _safe_lower(text: str) -> str:
    return (text or "").strip().lower()



def _detect_profile(*, workspace: Path, text_blob: str) -> str:
    queries_path = workspace / "queries.md"
    goal_path = workspace / "GOAL.md"
    intent_parts: list[str] = []
    if queries_path.exists():
        intent_parts.append(_safe_lower(queries_path.read_text(encoding="utf-8", errors="ignore")))
    if goal_path.exists():
        intent_parts.append(_safe_lower(goal_path.read_text(encoding="utf-8", errors="ignore")))

    # A compatibility pack changes the whole taxonomy, so explicit user intent
    # must select it. Corpus-wide term co-occurrence is too weak: unrelated
    # papers can satisfy different detection groups and silently hijack scope.
    intent = "\n".join(part for part in intent_parts if part.strip()).strip()
    low = intent or (text_blob or "").lower()

    for pack_path in _iter_domain_pack_paths():
        pack = _safe_load_domain_pack(pack_path)
        if not pack:
            continue
        detect = pack.get("detect") or {}
        if _matches_detection(low=low, detect=detect):
            return str(pack.get("profile") or pack_path.stem).strip() or pack_path.stem

    if intent:
        return "generic"

    return "generic"



def _iter_domain_pack_paths() -> list[Path]:
    return sorted(DOMAIN_PACKS_DIR.glob("*.yaml"))



def _safe_load_domain_pack(path: Path) -> dict[str, Any]:
    try:
        from tooling.common import load_yaml

        data = load_yaml(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}



def _matches_detection(*, low: str, detect: dict[str, Any]) -> bool:
    groups = detect.get("all_of_groups") or []
    if groups:
        for group in groups:
            terms = [str(term).strip().lower() for term in group if str(term).strip()]
            if terms and not any(term in low for term in terms):
                return False
        return True

    any_of = [str(term).strip().lower() for term in (detect.get("any_of") or []) if str(term).strip()]
    if any_of:
        return any(term in low for term in any_of)
    return False



def _load_domain_pack_taxonomy(*, profile: str, core_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pack_path = DOMAIN_PACKS_DIR / f"{profile}.yaml"
    if not pack_path.exists():
        raise SystemExit(f"Missing domain pack for profile '{profile}': {pack_path}")

    pack = _safe_load_domain_pack(pack_path)
    taxonomy_nodes = pack.get("taxonomy")
    if not isinstance(taxonomy_nodes, list) or not taxonomy_nodes:
        raise SystemExit(f"Invalid domain pack taxonomy: {pack_path}")

    rep_cfg = pack.get("representative_papers") or {}
    max_rep = int(rep_cfg.get("top_level_max") or 4)
    suffix_template = str(rep_cfg.get("suffix_template") or " Representative paper_id(s): {paper_ids}.")

    output: list[dict[str, Any]] = []
    for node in taxonomy_nodes:
        if not isinstance(node, dict):
            raise SystemExit(f"Invalid top-level node in domain pack: {pack_path}")
        name = str(node.get("name") or "").strip()
        desc_base = str(node.get("description_base") or node.get("description") or "").strip()
        if not name or not desc_base:
            raise SystemExit(f"Domain pack node missing name/description: {pack_path}")

        rep_terms = [str(term).strip() for term in (node.get("representative_terms") or []) if str(term).strip()]
        description = desc_base
        if rep_terms:
            rep = _representative_papers(core_rows=core_rows, terms=rep_terms)
            if rep:
                description += suffix_template.format(paper_ids=", ".join(rep[:max_rep]))

        children_out: list[dict[str, str]] = []
        for child in node.get("children") or []:
            if not isinstance(child, dict):
                raise SystemExit(f"Invalid child node in domain pack: {pack_path}")
            child_name = str(child.get("name") or "").strip()
            child_desc = str(child.get("description") or "").strip()
            if not child_name or not child_desc:
                raise SystemExit(f"Domain pack child missing name/description: {pack_path}")
            children_out.append({"name": child_name, "description": child_desc})

        output.append({"name": name, "description": description, "children": children_out})

    return output



def _representative_papers(*, core_rows: list[dict[str, str]], terms: list[str]) -> list[str]:
    terms_low = {term.strip().lower() for term in terms if str(term).strip()}
    hits: list[tuple[int, str]] = []
    for row in core_rows:
        pid = str(row.get("paper_id") or "").strip()
        title = _safe_lower(str(row.get("title") or ""))
        if not pid or not title:
            continue
        score = sum(1 for term in terms_low if term and term in title)
        if score:
            hits.append((score, pid))
    hits.sort(key=lambda item: (-item[0], item[1]))
    return [pid for _, pid in hits[:8]]



def _child_description(*, parent: str, child: str, core_rows: list[dict[str, str]], seed_terms: list[str]) -> str:
    rep = _representative_papers(core_rows=core_rows, terms=seed_terms)
    rep_str = ", ".join(rep[:3]) if rep else ""
    parts = [
        f"{child} narrows {parent} to work that explicitly studies this mechanism or setting.",
        f"The current core-set anchors are {rep_str}." if rep_str else "",
        "Include a paper here only when its title or abstract supplies direct scope evidence.",
    ]
    return " ".join([part for part in parts if part]).strip()



def _is_placeholder(text: str) -> bool:
    text = (text or "").strip().lower()
    if not text:
        return True
    if "(placeholder)" in text:
        return True
    if "<!-- scaffold" in text:
        return True
    if re.search(r"(?i)(?:todo|tbd|fixme)", text):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
