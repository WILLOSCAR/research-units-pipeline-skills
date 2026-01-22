from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _norm_title(x: str) -> str:
    x = re.sub(r"\s+", " ", (x or "").strip()).lower()
    x = re.sub(r"[^a-z0-9]+", " ", x).strip()
    return x


def _sha1(x: str) -> str:
    return hashlib.sha1((x or "").encode("utf-8", errors="ignore")).hexdigest()


def _split_paragraphs(md: str) -> list[str]:
    # Split on blank lines; keep reasonably large blocks only.
    blocks = [b.strip() for b in re.split(r"\n\s*\n", md or "")]
    return [b for b in blocks if b]


def _extract_cites(text: str) -> list[str]:
    keys: list[str] = []
    for m in re.finditer(r"\[@([^\]]+)\]", text or ""):
        inside = (m.group(1) or "").strip()
        for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
            if k and k not in keys:
                keys.append(k)
    return keys


def _repeated_sentences(text: str, *, min_len: int = 90, min_repeats: int = 6) -> tuple[str, int] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    compact = re.sub(r"\[@[^\]]+\]", "", raw)
    compact = re.sub(r"\s+", " ", compact).strip()
    if not compact:
        return None
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]
    counts: dict[str, int] = {}
    for s in sents:
        if len(s) < int(min_len):
            continue
        norm = re.sub(r"\s+", " ", s).strip().lower()
        counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return None
    top_norm, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if top_count >= int(min_repeats):
        return top_norm[:140], top_count
    return None


def _examples(text: str, pattern: str, *, max_examples: int = 3, window: int = 90) -> list[str]:
    """Return small context snippets around regex matches (deterministic, bounded)."""

    out: list[str] = []
    if not text:
        return out
    for m in re.finditer(pattern, text):
        start = max(0, m.start() - int(window))
        end = min(len(text), m.end() + int(window))
        snippet = text[start:end].replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if snippet and snippet not in out:
            out.append(snippet[:220])
        if len(out) >= int(max_examples):
            break
    return out




def _first_sentence_no_cites(text: str) -> str:
    blob = re.sub(r"\[@[^\]]+\]", "", text or "")
    blob = re.sub(r"\s+", " ", blob).strip()
    if not blob:
        return ""
    # Cheap sentence split; good enough for opener-stem warnings.
    parts = re.split(r"(?<=[.!?])\s+", blob)
    return (parts[0] if parts else blob).strip()


def _stem(text: str, *, n_words: int = 4) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", (text or "").lower()) if w]
    return " ".join(words[: int(n_words)])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, load_yaml, parse_semicolon_list, read_jsonl
    from tooling.quality_gate import _draft_profile, _pipeline_profile

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "output/DRAFT.md",
        "outline/outline.yml",
        "outline/evidence_bindings.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["output/AUDIT_REPORT.md"]

    draft_rel = next((p for p in inputs if p.endswith("output/DRAFT.md") or p.endswith("DRAFT.md")), "output/DRAFT.md")
    outline_rel = next((p for p in inputs if p.endswith("outline/outline.yml") or p.endswith("outline.yml")), "outline/outline.yml")
    bindings_rel = next((p for p in inputs if p.endswith("outline/evidence_bindings.jsonl") or p.endswith("evidence_bindings.jsonl")), "outline/evidence_bindings.jsonl")
    bib_rel = next((p for p in inputs if p.endswith("citations/ref.bib") or p.endswith("ref.bib")), "citations/ref.bib")

    out_rel = outputs[0] if outputs else "output/AUDIT_REPORT.md"

    draft_path = workspace / draft_rel
    outline_path = workspace / outline_rel
    bindings_path = workspace / bindings_rel
    bib_path = workspace / bib_rel

    blocking: list[str] = []
    warnings: list[str] = []

    if not draft_path.exists() or draft_path.stat().st_size == 0:
        blocking.append(f"missing draft: `{draft_rel}`")
        report = "\n".join([
            "# Audit report",
            "",
            "- Status: FAIL",
            f"- Reason: missing `{draft_rel}`",
            "",
        ])
        (workspace / out_rel).parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(workspace / out_rel, report)
        return 2

    draft = draft_path.read_text(encoding="utf-8", errors="ignore")

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)

    # Placeholder leakage.
    if "…" in draft:
        blocking.append("draft contains unicode ellipsis (…)")
    if re.search(r"(?m)\.\.\.+", draft):
        blocking.append("draft contains truncation dots (...)")
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", draft):
        blocking.append("draft contains TODO/TBD/FIXME placeholders")

    # Evidence-policy disclaimer spam: keep this once in front matter, not repeated per H3.
    evidence_disclaimer_details: list[tuple[str, int, list[str]]] = []
    evidence_disclaimer_n = 0
    for label, pat in [
        ("abstract-only/level evidence", r"(?i)\babstract(?:-|\s+)(?:only|level)\s+evidence\b"),
        ("title-only evidence", r"(?i)\btitle(?:-|\s+)only\s+evidence\b"),
        ("claims remain provisional", r"(?i)\bclaims?\s+remain\s+provisional\b"),
    ]:
        n = len(re.findall(pat, draft))
        if n:
            evidence_disclaimer_details.append((label, n, _examples(draft, pat)))
            evidence_disclaimer_n += n
    if evidence_disclaimer_n > 2:
        warnings.append(
            f"evidence-policy disclaimer repeated too often ({evidence_disclaimer_n}×); keep it once (prefer Intro/Related Work)"
        )

    # "PPT narration" navigation phrases: prefer argument bridges over slide-like narration.
    narration_patterns: list[tuple[str, str]] = [
        ("next, we move from", r"(?i)\bnext,\s+we\s+move\s+from\b"),
        ("we now turn/move to", r"(?i)\bwe\s+now\s+(?:turn|move)\s+to\b"),
        ("in the next section/subsection", r"(?i)\bin\s+the\s+next\s+(?:section|subsection)\b"),
        ("this section/subsection surveys/argues", r"(?i)\bthis\s+(?:section|subsection)\s+(?:surveys|argues|shows|highlights)\b"),
    ]
    narration_details: list[tuple[str, int, list[str]]] = []
    narration_hits = 0
    for label, pat in narration_patterns:
        n = len(re.findall(pat, draft))
        if n:
            narration_details.append((label, n, _examples(draft, pat)))
            narration_hits += n
    if narration_hits >= 5:
        warnings.append(f"too many narration-style navigation phrases ({narration_hits}×); rewrite as argument bridges")

    # Repeated opener labels (e.g., "Key takeaway:") are a strong generator-voice signal.
    takeaway_pat = r"(?im)\b(key\s+takeaway|main\s+takeaway)\b\s*[:\-]"
    takeaway_n = len(re.findall(takeaway_pat, draft))
    takeaway_examples = _examples(draft, takeaway_pat) if takeaway_n else []
    if takeaway_n > 1:
        warnings.append(
            f"repeated takeaway-style opener label ({takeaway_n}×); avoid 'Key takeaway:' spam and vary openers"
        )

    # Suspicious model naming (often hallucinated / underspecified).
    gpt5_pat = r"(?i)\bgpt[\s\-]?5\b"
    gpt5_examples = _examples(draft, gpt5_pat) if re.search(gpt5_pat, draft) else []
    if gpt5_examples:
        warnings.append("suspicious model name 'GPT-5' appears; avoid ambiguous naming unless the cited paper uses it")

    # Discourse-marker overuse (non-blocking): a common generator-voice regression.
    discourse_patterns: list[tuple[str, str, int]] = [
        ("this suggests", r"(?i)\bthis suggests\b", 6),
        ("additionally", r"(?i)\badditionally\b", 6),
    ]
    for label, pat, warn_at in discourse_patterns:
        n = len(re.findall(pat, draft))
        if n >= warn_at:
            warnings.append(f"overused discourse stem {label} ({n}x); vary connectors and prefer content-bearing subjects over This ...")

    # Slash-style axis copying (A/B) reads like design-space notes once it accumulates.
    slash_pat = r"\b[A-Za-z][A-Za-z0-9_-]{1,18}/[A-Za-z][A-Za-z0-9_-]{1,18}\b"
    slash_n = len(re.findall(slash_pat, draft))
    if slash_n >= 40:
        warnings.append(
            f"high slash-enumeration density ({slash_n}x A/B tokens); rewrite axis labels into natural prose (use and/or) instead of copying brief-style strings"
        )

    # Pipeline/meta jargon leakage.
    packs_pat = r"(?i)\bevidence\s+packs?\b"
    packs_n = len(re.findall(packs_pat, draft))
    if packs_n:
        warnings.append(f"pipeline jargon evidence pack(s) appears in prose ({packs_n}x); rewrite as survey methodology or remove")


    # Bib health.
    bib_keys: list[str] = []
    dup_bib = 0
    if bib_path.exists() and bib_path.stat().st_size > 0:
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)
        dup_bib = len(bib_keys) - len(set(bib_keys))
        if dup_bib:
            blocking.append(f"ref.bib has duplicate bibkeys ({dup_bib})")
    else:
        blocking.append(f"missing ref.bib: `{bib_rel}`")

    bib_set = set(bib_keys)

    # Draft citation health.
    cited = set(_extract_cites(draft))
    missing_in_bib = sorted([k for k in cited if bib_set and k not in bib_set])
    if missing_in_bib:
        sample = ", ".join(missing_in_bib[:10])
        blocking.append(f"draft cites keys missing from ref.bib (e.g., {sample})")

    # Coverage by subsection titles.
    outline = load_yaml(outline_path) if outline_path.exists() else []
    expected: dict[str, str] = {}
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                title = str(sub.get("title") or "").strip()
                if sid and title:
                    expected[_norm_title(title)] = sid

    # Parse H3 chunks from draft.
    # Treat new H2 headings as boundaries; otherwise trailing global sections and
    # visuals get incorrectly attributed to the last H3.
    chunks: list[tuple[str, str]] = []  # (h3_title, body)
    cur_title = ""
    cur_lines: list[str] = []
    for raw in draft.splitlines():
        if raw.startswith("### "):
            if cur_title:
                chunks.append((cur_title, "\n".join(cur_lines).strip()))
            cur_title = raw[4:].strip()
            cur_lines = []
            continue
        if raw.startswith("## "):
            if cur_title:
                chunks.append((cur_title, "\n".join(cur_lines).strip()))
            cur_title = ""
            cur_lines = []
            continue
        if cur_title:
            cur_lines.append(raw)
    if cur_title:
        chunks.append((cur_title, "\n".join(cur_lines).strip()))

    found: dict[str, dict[str, Any]] = {}
    unknown_h3: list[str] = []
    for h3, body in chunks:
        sid = expected.get(_norm_title(h3))
        if not sid:
            unknown_h3.append(h3)
            continue
        found[sid] = {
            "title": h3,
            "citations": _extract_cites(body),
            "body": body,
        }



    # Template phrase family stats (non-blocking; helps de-templating without brittle hard blocks).
    template_family_details: list[tuple[str, int, list[str]]] = []

    def _add_family(label: str, pat: str, *, warn_at: int) -> None:
        n = len(re.findall(pat, draft))
        if not n:
            return
        exs = _examples(draft, pat, max_examples=3)
        template_family_details.append((label, n, exs))
        if n >= int(warn_at):
            warnings.append(f"template phrase family repeated ({n}×): {label}")

    # Common generator-voice families.
    _add_family(
        "transition title narration (e.g., 'From X to Y ...')",
        r"(?im)^from\s+[^\n]{3,80}\s+to\s+[^\n]{3,80}",
        warn_at=3,
    )
    _add_family(
        "injection-like 'representative works include …' opener",
        r"(?im)^(?:a\s+few\s+representative\s+references\s+include|representative\s+works\s+(?:in\s+this\s+space\s+)?include|notable\s+(?:lines\s+of\s+work|work\s+in\s+this\s+area)\s+include|recent\s+work\s+in\s+this\s+area\s+includes)\b[^\n]{0,140}\[@",
        warn_at=4,
    )
    _add_family(
        "subsection narration ('This subsection …')",
        r"(?i)\bthis\s+(?:section|subsection)\s+(?:surveys|argues|shows|highlights|demonstrates|contends)\b",
        warn_at=2,
    )
    _add_family(
        "PPT-like navigation ('We now turn to …' / 'In the next section …')",
        r"(?i)\b(?:we\s+now\s+(?:turn|move)\s+to|next,\s+we\s+move\s+from|in\s+the\s+next\s+(?:section|subsection))\b",
        warn_at=3,
    )
    _add_family(
        "pipeline voice ('this run')",
        r"(?i)\bthis\s+run\b",
        warn_at=1,
    )

    _add_family(
        "synthesis opener (Taken together, ...)",
        r"(?im)^taken together,",
        warn_at=4,
    )
    _add_family(
        "meta survey-guidance phrasing (survey ... should ...)",
        r"(?i)\bsurvey\s+(?:synthesis|comparisons?)\s+should\b",
        warn_at=3,
    )
    _add_family(
        "injection-like enumerator (Work on ... includes ... [@])",
        r"(?im)^(?:concrete\s+(?:examples|instances)\s+(?:in|for)|work\s+on|recent\s+systems\s+for|examples\s+that\s+illustrate|representative\s+systems\s+for)\b[^\n]{0,160}\binclude\b[^\n]{0,160}\[@",
        warn_at=4,
    )

    # Repeated H3 opener stems (soft warning): avoid using the exact same first-sentence stem everywhere.
    opener_stems: dict[str, int] = {}
    opener_examples: dict[str, list[str]] = {}
    for sid, rec in found.items():
        body = str(rec.get("body") or "")
        paras = _split_paragraphs(body)
        first_para = paras[0] if paras else body
        first_sent = _first_sentence_no_cites(first_para)
        stem = _stem(first_sent, n_words=4)
        if not stem:
            continue
        opener_stems[stem] = opener_stems.get(stem, 0) + 1
        exs = opener_examples.setdefault(stem, [])
        if first_sent and first_sent not in exs:
            exs.append(first_sent[:160])

    rep_stems = [(s, n) for s, n in opener_stems.items() if n >= 3]
    rep_stems.sort(key=lambda kv: (-kv[1], kv[0]))
    for stem, n in rep_stems[:3]:
        template_family_details.append((f"repeated H3 opener stem: `{stem} ...`", n, opener_examples.get(stem, [])[:3]))
    if rep_stems:
        stem0, n0 = rep_stems[0]
        warnings.append(f"repeated H3 opener stem across subsections ({n0}×): '{stem0} ...' (vary openers)")

    missing_h3 = []
    if expected:
        for _, sid in expected.items():
            if sid not in found:
                missing_h3.append(sid)
        if missing_h3:
            blocking.append(f"draft missing some H3 subsections from outline (e.g., {', '.join(missing_h3[:6])})")

    # Per-H3 cite density (hard target for survey-like drafts).
    low_cite: list[str] = []
    for sid, rec in found.items():
        uniq = set(rec.get("citations") or [])
        if len(uniq) < 3:
            low_cite.append(f"{sid}({len(uniq)})")
    if low_cite:
        blocking.append(f"some H3 have <3 unique citations: {', '.join(low_cite[:10])}")

    # Global cite coverage (encourage using more of the bibliography, not just a small subset).
    if profile == "arxiv-survey" and expected:
        h3_n = len(set(expected.values()))
        if draft_profile == "deep":
            per_h3 = 12
            base = 30
            frac = 0.55
        elif draft_profile == "lite":
            per_h3 = 6
            base = 14
            frac = 0.30
        else:
            per_h3 = 10
            base = 24
            frac = 0.45

        min_unique_struct = base + per_h3 * h3_n
        min_unique_frac = int(len(bib_keys) * frac) if bib_keys else 0
        min_unique = max(min_unique_struct, min_unique_frac)
        if bib_keys:
            min_unique = min(min_unique, len(bib_keys))

        if len(cited) < min_unique:
            blocking.append(
                f"unique citations too low ({len(cited)}; target >= {min_unique} for {draft_profile} profile)"
                + (f" [struct={min_unique_struct}, frac={min_unique_frac}, bib={len(bib_keys)}]" if bib_keys else "")
            )

    # Paragraph-level no-citation rate (content-only; ignore headings/tables/short transitions).
    paras_all = _split_paragraphs(draft)
    content_paras = 0
    uncited = 0
    for para in paras_all:
        if para.startswith(("#", "|", "```")):
            continue
        if len(para) < 240:
            continue
        if "\n|" in para:
            continue
        content_paras += 1
        if "[@" not in para:
            uncited += 1
    if content_paras:
        rate = uncited / content_paras

        max_uncited = 0.25
        if profile == "arxiv-survey":
            if draft_profile == "deep":
                max_uncited = 0.15
            elif draft_profile != "lite":
                max_uncited = 0.20

        if rate > max_uncited:
            blocking.append(
                f"too many uncited content paragraphs ({uncited}/{content_paras} = {rate:.1%}; max={max_uncited:.0%})"
            )

    # Numeric claim context (non-blocking): when a paragraph cites metric-like numbers,
    # also state minimal evaluation context (task/metric/budget/benchmark) in the same paragraph.
    eval_tok = r"(?i)(?:benchmark|dataset|datasets|metric|metrics|protocol|evaluation|eval\.|latency|cost|budget|token|tokens|throughput|compute|score|accuracy|exact|success)"
    metric_hint = r"(?i)(?:percent|accuracy|exact|f1|score|success(?:\s+rate)?|pass@|win\s+rate|\d+(?:\.\d+)?\s*%)"

    missing_numeric_ctx: list[str] = []
    for para in paras_all:
        if para.startswith(("#", "|", "```")):
            continue
        if len(para) < 240:
            continue
        if "\n|" in para:
            continue
        if "[@" not in para:
            continue
        if not re.search(r"\d", para):
            continue
        if not re.search(metric_hint, para):
            continue
        if re.search(eval_tok, para):
            continue
        missing_numeric_ctx.append(para)

    if len(missing_numeric_ctx) >= 2:
        warnings.append(
            f"numeric paragraphs lack explicit eval context ({len(missing_numeric_ctx)}×); add task/metric/budget/benchmark wording or drop the number"
        )
        exs = [re.sub(r"\s+", " ", p).strip()[:220] for p in missing_numeric_ctx[:3]]
        template_family_details.append(("numeric claim missing eval context", len(missing_numeric_ctx), exs))

    # Boilerplate repetition.
    rep = _repeated_sentences(draft)
    if rep:
        example, count = rep
        warnings.append(f"repeated boilerplate sentence ({count}×): `{example}`")

    # Evidence-binding compliance (soft but informative).
    bindings: dict[str, dict[str, Any]] = {}
    if bindings_path.exists() and bindings_path.stat().st_size > 0:
        for rec in read_jsonl(bindings_path):
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            if sid:
                bindings[sid] = rec

    compliance_rows: list[str] = []
    if bindings and found:
        for sid, rec in found.items():
            cites = set(rec.get("citations") or [])
            b = bindings.get(sid) or {}
            selected = set([str(k).strip() for k in (b.get("bibkeys") or []) if str(k).strip()])
            mapped = set([str(k).strip() for k in (b.get("mapped_bibkeys") or []) if str(k).strip()])
            if not cites:
                continue
            in_sel = len([c for c in cites if c in selected])
            in_map = len([c for c in cites if c in mapped]) if mapped else in_sel
            compliance_rows.append(
                f"| {sid} | {len(cites)} | {in_sel}/{len(cites)} | {in_map}/{len(cites)} |"
            )

    status = "PASS" if not blocking else "FAIL"

    lines: list[str] = [
        "# Audit report",
        "",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}` (sha1={_sha1(draft)[:10]})",
        f"- Bib: `{bib_rel}` (entries={len(bib_keys)})",
        "",
        "## Summary",
        f"- Unique citations in draft: {len(cited)}",
        f"- Outline H3 expected: {len(set(expected.values())) if expected else 0}",
        f"- Draft H3 found: {len(found)}",
        "",
    ]

    if blocking:
        lines.append("## Blocking issues")
        for it in blocking:
            lines.append(f"- {it}")
        lines.append("")

    if warnings:
        lines.append("## Warnings (non-blocking)")
        for it in warnings:
            lines.append(f"- {it}")
        lines.append("")

    if template_family_details:
        lines.append("## Template phrase family stats (for fixing)")
        for label, n, exs in template_family_details:
            lines.append(f"- {label}: {n}×")
            for ex in (exs or [])[:3]:
                if ex:
                    lines.append(f"  - {ex}")
        lines.append("")

    if evidence_disclaimer_n > 2 and evidence_disclaimer_details:
        lines.append("## Evidence-policy disclaimer examples (for fixing)")
        for label, n, exs in evidence_disclaimer_details:
            lines.append(f"- {label}: {n}×")
            for ex in exs[:3]:
                lines.append(f"  - {ex}")
        lines.append("")

    if narration_hits >= 5 and narration_details:
        lines.append("## Narration-style phrase examples (for fixing)")
        for label, n, exs in narration_details:
            lines.append(f"- {label}: {n}×")
            for ex in exs[:3]:
                lines.append(f"  - {ex}")
        lines.append("")

    if takeaway_n > 1 and takeaway_examples:
        lines.append("## Repeated opener label examples (for fixing)")
        for ex in takeaway_examples[:3]:
            lines.append(f"- {ex}")
        lines.append("")

    if gpt5_examples:
        lines.append("## Suspicious model naming examples (for fixing)")
        for ex in gpt5_examples[:3]:
            lines.append(f"- {ex}")
        lines.append("")

    if unknown_h3:
        lines.append("## Unmatched H3 headings (check outline drift)")
        for t in unknown_h3[:12]:
            lines.append(f"- {t}")
        lines.append("")

    if compliance_rows:
        lines.extend([
            "## Evidence binding compliance (informative)",
            "| H3 | unique cites | in selected bibkeys | in mapped bibkeys |",
            "|---|---:|---:|---:|",
        ])
        lines.extend(compliance_rows)
        lines.append("")

    (workspace / out_rel).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(workspace / out_rel, "\n".join(lines).rstrip() + "\n")

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
