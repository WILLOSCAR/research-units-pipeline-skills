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

    # The top tokens are the cluster "spines". A child keyword must not repeat
    # the cluster's own spine, any OTHER cluster's spine, or a child already
    # claimed by an earlier cluster — otherwise clusters collapse into the same
    # reshuffled keyword set (e.g. "Time" with children Time/Adaptation/Test),
    # which propagates into near-duplicate downstream directions. Keeping
    # children distinct and non-overlapping is what makes clusters read as
    # separate sub-areas.
    spine_tokens = {t for t in top_topics[:4]}
    claimed_children: set[str] = set()
    used_labels: set[str] = set()
    used_label_folds: set[str] = set()
    cluster_label_folds: list[frozenset[str]] = []
    from tooling.common import _EN_STOPWORDS, _GENERIC_PAPER_WORDS
    _label_stop = set(_EN_STOPWORDS) | set(_GENERIC_PAPER_WORDS)

    # (Children are deduped against another top-level cluster's topic in a
    # post-build pass below, once every real cluster label is known.)

    taxonomy: list[dict[str, Any]] = []
    # Draw from a LARGER token pool but keep only 4 clusters whose LABELS are
    # distinct topic areas. On a multi-topic corpus, several top tokens
    # (clinical/text/summarization) otherwise yield overlapping fragment labels
    # ("Clinical Text Summarization", "Text Summarization", "Clinical Text") that
    # consume all top-level slots and crowd out the second topic. Skipping a
    # near-duplicate cluster label frees the slot for a distinct topic.
    for token in top_topics[:8]:
        if len(taxonomy) >= 4:
            break
        subset = [title for title in titles if token in set(tokenize(title))]
        sub = candidate_keywords(subset, top_k=12, min_freq=1)
        sub = [
            item
            for item in sub
            if item not in {"overview", "benchmarks", "open", "problems"}
            and item != token
            and item not in spine_tokens
            and item not in claimed_children
            and _is_concept_token(item)
        ]
        if not sub:
            sub = ["problem", "mechanisms", "evaluation", "limitations"]
        sub = sub[:3]

        # Prefer a corpus bigram containing the spine token as the cluster LABEL
        # (reads as a sub-area, e.g. "Interatomic Potential"); fall back to the
        # single-token spine. The spine token still drives subset membership, so
        # topic grouping is unchanged — only the human-facing label improves.
        cluster_name = (
            _spine_bigram_label(token, titles, tokenize, stop=_label_stop, used=used_labels)
            or _pretty(token)
        )
        # Skip a near-duplicate top-level cluster (substring / high token overlap
        # of an already-emitted cluster label), so distinct topics get the slots.
        cfold = _label_content_tokens(cluster_name)
        if cfold and any(_cluster_labels_near_duplicate(cfold, prev) for prev in cluster_label_folds):
            continue
        cluster_label_folds.append(cfold)
        used_labels.add(cluster_name.lower())
        claimed_children.update(sub)

        rep = _representative_papers(core_rows=core_rows, terms=[token] + list(sub))
        rep_str = ", ".join(rep[:4]) if rep else ""
        desc_terms = ", ".join([_pretty(item) for item in sub[:4]])
        desc_parts = [
            f"{cluster_name} groups studies whose scoped evidence emphasizes this concept.",
            f"Its corpus boundary is defined by related mechanisms or settings such as {desc_terms}." if desc_terms else "",
            f"Representative anchors in the current core set are {rep_str}." if rep_str else "",
        ]
        desc = " ".join([part for part in desc_parts if part]).strip()

        child_entries: list[dict[str, str]] = []
        sibling_folds: list[frozenset[str]] = []
        cluster_fold = _label_content_tokens(cluster_name)
        for child in sub[:3]:
            child_label = (
                _child_bigram_label(child, subset, tokenize, stop=_label_stop, used=used_labels)
                or _pretty(child)
            )
            # Fold plural/singular so sibling children like "Distribution Shifts"
            # and "Distribution Shift" do not both appear (a reader-facing
            # near-duplicate). Skip a child whose folded key is already used.
            fold = _label_fold(child_label)
            if fold in used_label_folds:
                continue
            # On a titles-only corpus the child bigrams are sliced from the same
            # title, so sibling children can be overlapping fragments of one phrase
            # ("Fine Grained" + "Grained Expert" from "Fine-Grained Expert
            # Segmentation"; "Laws Language" + "Scaling Laws" from "Scaling Laws
            # for Language Models"). Skip a child that shares a content token with
            # an already-kept sibling BEYOND the parent cluster's own token — they
            # are the same title fragment, not distinct sub-areas. (Sharing only
            # the parent/domain token, as on a single-topic corpus, is expected.)
            child_fold = _label_content_tokens(child_label)
            if child_fold and any((child_fold & prev) - cluster_fold for prev in sibling_folds):
                continue
            used_label_folds.add(fold)
            used_labels.add(child_label.lower())
            if child_fold:
                sibling_folds.append(child_fold)
            child_entries.append(
                {
                    "name": child_label,
                    "description": _child_description(
                        parent=cluster_name,
                        child=child_label,
                        core_rows=core_rows,
                        seed_terms=[token, child],
                    ),
                }
            )

        taxonomy.append(
            {
                "name": cluster_name,
                "description": desc,
                "children": child_entries,
            }
        )

    if all(not item.get("children") for item in taxonomy):
        raise SystemExit("Failed to build a 2-level taxonomy")

    # Post-build pass: drop a child that restates ANOTHER top-level cluster's topic
    # ("Domain Shift" child while "Domain" is a cluster; "Test Time" child while
    # "Test Time Adaptation" is a cluster) — a reader-facing cross-level near-
    # duplicate. Uses the REAL emitted cluster labels. Guard: only compare against
    # a cluster that is token-DISJOINT from the child's own parent; on a single-
    # topic corpus sibling clusters share the dominant token, so a child echoing a
    # same-family sibling is expected, not a cross-topic duplicate.
    cluster_folds = {
        str(item.get("name") or ""): _label_content_tokens(str(item.get("name") or ""))
        for item in taxonomy
    }
    for item in taxonomy:
        parent_fold = cluster_folds[str(item.get("name") or "")]
        kept: list[dict[str, str]] = []
        for child in item.get("children") or []:
            child_fold = _label_content_tokens(str(child.get("name") or ""))
            if child_fold and any(
                other_fold != parent_fold
                and not (other_fold & parent_fold)
                and _child_restates_cluster(child_fold, other_fold)
                for other_fold in cluster_folds.values()
            ):
                continue
            kept.append(child)
        item["children"] = kept

    dump_yaml(out_path, taxonomy)
    return 0



def _pretty(token: str) -> str:
    token = token.replace("_", " ").replace("-", " ").strip()
    return " ".join([word[:1].upper() + word[1:] for word in token.split() if word])


def _label_fold(label: str) -> str:
    """Plural/singular- and whitespace-insensitive key for label dedup.

    Folds "Distribution Shifts" and "Distribution Shift" (and case/spacing
    variants) to the same key so sibling children never differ only by a
    trailing 's'.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", str(label or "").lower())]
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _label_content_tokens(label: str) -> frozenset[str]:
    """Singular/plural-folded content tokens of a cluster label (>=3 chars)."""
    words = [w for w in re.findall(r"[a-z0-9]+", str(label or "").lower()) if len(w) >= 3]
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _cluster_labels_near_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    """True when two top-level cluster labels are the same topic area.

    Catches substring/fragment overlap ("Clinical Text Summarization" vs "Clinical
    Text" vs "Text Summarization") where one label's content tokens are a subset
    of the other, or the two share most tokens (Jaccard >= 0.5). Such labels are
    the same topic and should not both occupy a top-level slot.
    """
    if not a or not b:
        return False
    if a <= b or b <= a:
        return True
    inter = len(a & b)
    union = len(a | b)
    return union > 0 and (inter / union) >= 0.5


def _child_restates_cluster(child: frozenset[str], cluster: frozenset[str]) -> bool:
    """True when a CHILD label restates a whole other top-level cluster's topic.

    Stricter than :func:`_cluster_labels_near_duplicate` (which compares two
    top-level labels). A child legitimately shares a SINGLE token with some
    cluster ("Adaptation" under one parent while "Test Time Adaptation" is a
    cluster; the generic "Problem"/"Evaluation" children of a single-topic
    corpus), so only a substantial restatement is a defect:
    - the child names the same topic (equal folds), or
    - the child CONTAINS a whole cluster's topic ("Domain Shift" ⊇ "Domain",
      "Handling Domain" ⊇ "Domain"), or
    - the child is a MULTI-token fragment of a cluster ("Test Time" ⊆ "Test Time
      Adaptation"). A single-token fragment is kept.
    """
    if not child or not cluster:
        return False
    if child == cluster:
        return True
    if cluster <= child:
        return True
    return child <= cluster and len(child) >= 2



def _spine_bigram_label(token, titles, tokenize_fn, *, stop, used):
    """Longest frequent contiguous title n-gram containing `token`, as a label.

    Single high-frequency tokens ("Time", "Test", "Text") read as fragments, not
    research sub-areas — and they surface directly in the reader brief as
    "Comparison lenses". A contiguous corpus n-gram drawn in forward title order
    ("test time adaptation", "distribution shift", "clinical text summarization")
    reads as a genuine sub-area. Prefer the longest frequent n-gram (3 tokens,
    then 2) containing the token; return a `_pretty` phrase not already `used`,
    or None when none is distinct (caller keeps the single-token label).
    """
    from collections import Counter

    def _ngram_counts(n: int) -> Counter:
        counts: Counter = Counter()
        for title in titles:
            toks = [t for t in tokenize_fn(title) if t not in stop and len(t) >= 3]
            for i in range(len(toks) - n + 1):
                window = tuple(toks[i : i + n])
                if token in window:
                    counts[window] += 1
        return counts

    # Try 3-grams first (most descriptive), then 2-grams. Forward title order is
    # preserved by construction, so no reversed labels ("Adaptation Distribution").
    for n in (3, 2):
        for window, c in _ngram_counts(n).most_common():
            if c < 2:
                break
            label = _pretty(" ".join(window))
            if label.lower() not in used:
                return label
    return None




def _child_bigram_label(token, titles, tokenize_fn, *, stop, used):
    """Most frequent title bigram containing `token`, as a readable child label.

    Single high-frequency title tokens ("Shifts", "Addressing", "Aware") read as
    fragments, not research sub-areas. A corpus bigram containing the token
    ("Distribution Shift", "Confidence Maximization") reads as a genuine
    sub-area. Returns a `_pretty` bigram not already `used` by another cluster or
    child, or None when no distinct bigram exists (caller keeps the single
    token). min_freq is 1 here (child subsets are small) unlike the spine label.
    """
    from collections import Counter

    counts: Counter = Counter()
    for title in titles:
        toks = [t for t in tokenize_fn(title) if t not in stop and len(t) >= 3]
        for a, b in zip(toks, toks[1:]):
            if token in (a, b):
                counts[(a, b)] += 1
    for (a, b), _c in counts.most_common():
        label = _pretty(f"{a} {b}")
        if label.lower() not in used:
            return label
    return None


# Tokens that survive the keyword filter but do not name a research sub-area:
# bare connectives/verbs and years. A taxonomy child of "Against" or "2023"
# reads as noise, not a topic.
_NON_CONCEPT_CHILDREN = {
    "against", "can", "via", "toward", "towards", "using", "based",
    "addressing", "aware", "applications", "study", "studies", "approach",
    "approaches", "method", "methods", "learning",
}


def _is_concept_token(token: str) -> bool:
    """True when a single title token can stand in as a concept child.

    Rejects bare years (e.g. "2023") and generic connective/verb tokens that
    read as noise rather than a research sub-area. Real topical tokens
    ("distribution", "shift", "summarization") pass and are then upgraded to a
    bigram phrase label when the corpus supports one.
    """

    low = str(token or "").strip().lower()
    if not low or low.isdigit():
        return False
    if low in _NON_CONCEPT_CHILDREN:
        return False
    return True


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
