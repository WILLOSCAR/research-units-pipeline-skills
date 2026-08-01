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


def _cite_keys_in_block(block: str) -> list[str]:
    return [k for k in re.findall(r"[A-Za-z0-9:_-]+", (block or "").strip()) if k]


def _has_mid_sentence_cite(para: str, *, tail_chars: int = 45) -> bool:
    # True when at least one citation appears before the trailing tail region.
    cites = list(re.finditer(r"\[@[^\]]+\]", para or ""))
    if not cites:
        return False
    n = len(para or "")
    return any(m.start() < max(0, n - int(tail_chars)) for m in cites)

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

    from tooling.common import atomic_write_text, load_yaml, parse_semicolon_list, read_jsonl
    from tooling.quality_gate import _citation_target, _draft_profile, _pipeline_profile, survey_citation_policy
    from tooling.quality_checks.template_residue import build_template_residue_scorecard

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "output/DRAFT.md",
        "outline/outline.yml",
        "outline/evidence_bindings.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or [
        "output/AUDIT_REPORT.md",
        "output/TEMPLATE_RESIDUE_SCORECARD.json",
    ]

    draft_rel = next((p for p in inputs if p.endswith("output/DRAFT.md") or p.endswith("DRAFT.md")), "output/DRAFT.md")
    outline_rel = next((p for p in inputs if p.endswith("outline/outline.yml") or p.endswith("outline.yml")), "outline/outline.yml")
    bindings_rel = next((p for p in inputs if p.endswith("outline/evidence_bindings.jsonl") or p.endswith("evidence_bindings.jsonl")), "outline/evidence_bindings.jsonl")
    bib_rel = next((p for p in inputs if p.endswith("citations/ref.bib") or p.endswith("ref.bib")), "citations/ref.bib")

    out_rel = outputs[0] if outputs else "output/AUDIT_REPORT.md"
    residue_rel = next(
        (path for path in outputs if path.upper().endswith("TEMPLATE_RESIDUE_SCORECARD.JSON")),
        "output/TEMPLATE_RESIDUE_SCORECARD.json",
    )

    draft_path = workspace / draft_rel
    outline_path = workspace / outline_rel
    bindings_path = workspace / bindings_rel
    bib_path = workspace / bib_rel

    blocking: list[str] = []
    warnings: list[str] = []

    if not draft_path.exists() or draft_path.stat().st_size == 0:
        residue_scorecard = build_template_residue_scorecard(
            workspace=workspace,
            documents=[],
            scope="entire merged reader-facing draft",
        )
        atomic_write_text(
            workspace / residue_rel,
            json.dumps(residue_scorecard, ensure_ascii=False, indent=2) + "\n",
        )
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
    residue_scorecard = build_template_residue_scorecard(
        workspace=workspace,
        documents=[(draft_rel, draft)],
        scope="entire merged reader-facing draft",
    )
    atomic_write_text(
        workspace / residue_rel,
        json.dumps(residue_scorecard, ensure_ascii=False, indent=2) + "\n",
    )
    residue_measurement = residue_scorecard["measurement"]
    residue_policy = residue_scorecard["policy"]
    residue_selection = residue_scorecard["asset_selection"]
    residue_lock = residue_scorecard["implementation_lock"]
    if residue_scorecard["verdict"] != "PASS":
        blocking.append(
            "template residue scorecard failed "
            f"({residue_measurement['matched_sentence_count']}/{residue_measurement['sentence_count']} = "
            f"{float(residue_measurement['matched_sentence_ratio']):.1%}; "
            f"limit <= {float(residue_policy['max_ratio']):.0%}; "
            f"asset selection={residue_selection['status']}; "
            f"implementation lock={residue_lock['status']})"
        )

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    citation_target = _citation_target(workspace)

    min_h3_cites = 4 if draft_profile == "course_paper" else (14 if draft_profile == "deep" else 12)

    # Tables (survey deliverable): count Markdown tables in the merged draft.
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", draft)
    table_n = len(table_seps)

    # Placeholder leakage.
    if "…" in draft:
        blocking.append("draft contains unicode ellipsis (…)")
    if re.search(r"(?m)\.\.\.+", draft):
        blocking.append("draft contains truncation dots (...)")
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", draft):
        blocking.append("draft contains TODO/TBD/FIXME placeholders")

    min_tables = 1 if draft_profile == "course_paper" else 2
    if profile == "arxiv-survey" and table_n < min_tables:
        blocking.append(f"draft has too few tables ({table_n}; expected >= {min_tables})")

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



    # Template phrase family stats (reported always; selected families become hard blocks for survey/deep).
    template_family_details: list[tuple[str, int, list[str]]] = []
    family_counts: dict[str, int] = {}

    def _add_family(label: str, pat: str, *, warn_at: int) -> None:
        n = len(re.findall(pat, draft))
        if not n:
            return
        family_counts[label] = n
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
        "mechanical transition ('reframes the same chapter question around …')",
        r"(?i)\breframes\s+the\s+same\s+chapter\s+question\s+around\b",
        warn_at=1,
    )
    _add_family(
        "mechanical transition ('carries the discussion forward by focusing on …')",
        r"(?i)\bcarries\s+the\s+discussion\s+forward\s+by\s+focusing\s+on\b",
        warn_at=1,
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
        "bounded synthesis closer ('The safest synthesis ...' / 'That conclusion remains ...')",
        r"(?im)^(?:the\s+safest\s+synthesis|the\s+safest\s+conclusion|that\s+conclusion\s+remains|that\s+conclusion\s+still)\b",
        warn_at=3,
    )
    _add_family(
        "decision-rule closer ('The practical decision rule is therefore ...')",
        r"(?im)^the\s+(?:practical\s+)?decision\s+rule\s+is\s+therefore\b",
        warn_at=3,
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

    # Final paper-voice hard gate for all survey-family writing profiles.
    if draft_profile in {"survey", "deep", "course_paper"}:
        narr_n = family_counts.get("subsection narration ('This subsection …')", 0)
        nav_n = family_counts.get("PPT-like navigation ('We now turn to …' / 'In the next section …')", 0)
        mech_reframe_n = family_counts.get("mechanical transition ('reframes the same chapter question around …')", 0)
        mech_forward_n = family_counts.get("mechanical transition ('carries the discussion forward by focusing on …')", 0)
        taken_together_n = family_counts.get("synthesis opener (Taken together, ...)", 0)
        bounded_synthesis_n = family_counts.get("bounded synthesis closer ('The safest synthesis ...' / 'That conclusion remains ...')", 0)
        decision_rule_n = family_counts.get("decision-rule closer ('The practical decision rule is therefore ...')", 0)
        meta_guidance_n = family_counts.get("meta survey-guidance phrasing (survey ... should ...)", 0)

        if narr_n > 0:
            blocking.append(
                f"template narration opener remains ({narr_n}×, e.g., 'This subsection ...'); rewrite openers to content-bearing claims"
            )
        if nav_n > 0:
            blocking.append(
                f"slide-like navigation phrasing remains ({nav_n}×, e.g., 'We now turn to ...'); rewrite as argument bridges"
            )
        if mech_reframe_n > 0:
            blocking.append(
                f"mechanical transition stem remains ({mech_reframe_n}×: 'reframes the same chapter question around ...'); remove injected transition boilerplate"
            )
        if mech_forward_n > 0:
            blocking.append(
                f"mechanical transition stem remains ({mech_forward_n}×: 'carries the discussion forward by focusing on ...'); remove injected transition boilerplate"
            )
        if taken_together_n >= 2:
            blocking.append(
                f"repeated synthesis stem 'Taken together,' ({taken_together_n}×); vary synthesis cadence across H3"
            )
        if meta_guidance_n > 0:
            blocking.append(
                f"meta guidance phrasing remains ({meta_guidance_n}×, e.g., 'survey ... should ...'); rewrite as literature-facing observations"
            )
        if bounded_synthesis_n >= 2:
            blocking.append(
                f"repeated bounded-synthesis closer remains ({bounded_synthesis_n}×: 'The safest synthesis ...' / 'That conclusion remains ...'); vary endings and keep them section-specific"
            )
        if decision_rule_n >= 2:
            blocking.append(
                f"repeated decision-rule closer remains ({decision_rule_n}×: '... decision rule is therefore ...'); vary subsection endings"
            )
        if rep_stems and rep_stems[0][1] >= 3:
            stem0, n0 = rep_stems[0]
            blocking.append(
                f"repeated H3 opener stem still high ({n0}×: '{stem0} ...'); de-template subsection openings"
            )

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
        if len(uniq) < min_h3_cites:
            low_cite.append(f"{sid}({len(uniq)})")
    if low_cite:
        blocking.append(f"some H3 have <{min_h3_cites} unique citations: {', '.join(low_cite[:10])}")

    closer_counts: dict[str, list[str]] = {}
    fragmented_h3: list[str] = []
    for sid, rec in found.items():
        body = str(rec.get('body') or '')
        paras = _split_paragraphs(body)
        short_count = 0
        for para in paras[1:]:
            compact = re.sub(r"\[@[^\]]+\]", "", para)
            compact = re.sub(r"\s+", " ", compact).strip()
            if not compact:
                continue
            sent_n = len([s for s in re.split(r'(?<=[.!?])\s+', compact) if s.strip()])
            if sent_n <= 1 or (sent_n <= 2 and len(compact) < 180):
                short_count += 1
        if short_count >= 4 or len(paras) > 14:
            fragmented_h3.append(f"{sid}(short={short_count}, paras={len(paras)})")

        for label, pat in [
            ('The safest synthesis is therefore', re.compile(r'(?im)^the safest synthesis is therefore\b')),
            ('That conclusion remains', re.compile(r'(?im)^that conclusion remains\b')),
            ('That conclusion still', re.compile(r'(?im)^that conclusion still\b')),
            ('The evidence therefore supports', re.compile(r'(?im)^the evidence therefore supports\b')),
        ]:
            if pat.search(body):
                closer_counts.setdefault(label, []).append(sid)

    repeated_closers = [(label, sorted(set(sids))) for label, sids in closer_counts.items() if len(set(sids)) >= 2]
    repeated_closers.sort(key=lambda item: (-len(item[1]), item[0]))
    for label, sids in repeated_closers:
        blocking.append(f"repeated closing stem across H3s ({len(sids)}x): {label}")
        template_family_details.append((f"repeated closing stem: {label}", len(sids), sids[:3]))

    if fragmented_h3:
        blocking.append(f"paragraph fragmentation remains in some H3: {', '.join(fragmented_h3[:10])}")

    # Global cite coverage (encourage using more of the bibliography, not just a small subset).
    if profile == "arxiv-survey" and expected:
        policy = survey_citation_policy(workspace, bibliography_size=len(bib_keys), h3_count=len(expected))
        min_unique_hard = int(policy["hard"])
        rec_unique = int(policy["recommended"])

        target = rec_unique if citation_target == "recommended" else min_unique_hard

        if len(cited) < target:
            blocking.append(
                f"unique citations too low ({len(cited)}; target >= {target} for {draft_profile} profile; policy={citation_target})"
                + (
                    f" [hard={min_unique_hard}, rec={rec_unique}, bib={len(bib_keys)}]"
                    if bib_keys
                    else ""
                )
            )
        elif citation_target != "recommended" and rec_unique > min_unique_hard and len(cited) < rec_unique:
            warnings.append(
                f"unique citations below recommended target ({len(cited)}; recommend >= {rec_unique} for {draft_profile} profile)"
                + (
                    f" [hard={min_unique_hard}, rec_frac={int(len(bib_keys) * float(policy['recommended_fraction']))}, bib={len(bib_keys)}]"
                    if bib_keys
                    else ""
                )
            )

    # Citation-shape hard gate (reader-facing citation quality):
    # 1) no adjacent citation blocks like `... [@a] [@b]`
    # 2) no duplicate keys inside one citation block like `[@a; @a]`
    # 3) each H3 should keep a minimum ratio of mid-sentence citations to avoid tail-dump style
    adj_cite_pat = r"\[@[^\]]+\]\s*\[@[^\]]+\]"
    adj_hits = list(re.finditer(adj_cite_pat, draft))
    if adj_hits:
        blocking.append(
            f"adjacent citation blocks detected ({len(adj_hits)}×, e.g., `[@a] [@b]`); merge same-sentence citations into one block"
        )
        template_family_details.append(("adjacent citation blocks", len(adj_hits), _examples(draft, adj_cite_pat)))

    dup_in_block = 0
    for m in re.finditer(r"\[@([^\]]+)\]", draft):
        keys = _cite_keys_in_block(m.group(1))
        if keys and len(set(keys)) != len(keys):
            dup_in_block += 1
    if dup_in_block:
        blocking.append(
            f"citation blocks with duplicate keys detected ({dup_in_block}×, e.g., `[@x; @x]`); deduplicate keys inside each citation block"
        )

    mid_ratio_floor = 0.30 if draft_profile in {"survey", "deep"} else 0.20
    low_mid_ratio: list[str] = []
    for sid, rec in found.items():
        body = str(rec.get("body") or "")
        paras = _split_paragraphs(body)
        cited_paras = 0
        mid_cited_paras = 0
        for para in paras:
            if "[@" not in para:
                continue
            cited_paras += 1
            if _has_mid_sentence_cite(para):
                mid_cited_paras += 1
        if cited_paras < 4:
            continue
        ratio = mid_cited_paras / max(1, cited_paras)
        if ratio < mid_ratio_floor:
            low_mid_ratio.append(f"{sid}({mid_cited_paras}/{cited_paras}={ratio:.0%})")
    if low_mid_ratio:
        blocking.append(
            f"mid-sentence citation ratio below {int(mid_ratio_floor * 100)}% in some H3: {', '.join(low_mid_ratio[:10])}"
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
            max_uncited = 0.25 if draft_profile == "course_paper" else (0.15 if draft_profile == "deep" else 0.20)

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
        f"- Draft profile: `{draft_profile}`",
        f"- Citation target policy: `{citation_target}`",
        f"- Template residue scorecard: `{residue_rel}`",
        "",
        "## Summary",
        f"- Unique citations in draft: {len(cited)}",
        f"- Markdown tables in draft: {table_n}",
        f"- Outline H3 expected: {len(set(expected.values())) if expected else 0}",
        f"- Draft H3 found: {len(found)}",
        (
            f"- Whole-draft template residue: {residue_measurement['matched_sentence_count']}/"
            f"{residue_measurement['sentence_count']} = "
            f"{float(residue_measurement['matched_sentence_ratio']):.1%} "
            f"(limit <= {float(residue_policy['max_ratio']):.0%})"
        ),
        f"- Template asset selection: {residue_selection['status']}",
        f"- Writer implementation lock: {residue_lock['status']}",
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
