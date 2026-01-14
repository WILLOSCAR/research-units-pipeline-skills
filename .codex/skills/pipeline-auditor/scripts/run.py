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

    issues: list[str] = []

    if not draft_path.exists() or draft_path.stat().st_size == 0:
        issues.append(f"missing draft: `{draft_rel}`")
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
        issues.append("draft contains unicode ellipsis (…)")
    if re.search(r"(?m)\.\.\.+", draft):
        issues.append("draft contains truncation dots (...)")
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", draft):
        issues.append("draft contains TODO/TBD/FIXME placeholders")

    # Bib health.
    bib_keys: list[str] = []
    dup_bib = 0
    if bib_path.exists() and bib_path.stat().st_size > 0:
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)
        dup_bib = len(bib_keys) - len(set(bib_keys))
        if dup_bib:
            issues.append(f"ref.bib has duplicate bibkeys ({dup_bib})")
    else:
        issues.append(f"missing ref.bib: `{bib_rel}`")

    bib_set = set(bib_keys)

    # Draft citation health.
    cited = set(_extract_cites(draft))
    missing_in_bib = sorted([k for k in cited if bib_set and k not in bib_set])
    if missing_in_bib:
        sample = ", ".join(missing_in_bib[:10])
        issues.append(f"draft cites keys missing from ref.bib (e.g., {sample})")

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

    missing_h3 = []
    if expected:
        for _, sid in expected.items():
            if sid not in found:
                missing_h3.append(sid)
        if missing_h3:
            issues.append(f"draft missing some H3 subsections from outline (e.g., {', '.join(missing_h3[:6])})")

    # Per-H3 cite density (hard target for survey-like drafts).
    low_cite: list[str] = []
    for sid, rec in found.items():
        uniq = set(rec.get("citations") or [])
        if len(uniq) < 3:
            low_cite.append(f"{sid}({len(uniq)})")
    if low_cite:
        issues.append(f"some H3 have <3 unique citations: {', '.join(low_cite[:10])}")

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
            issues.append(
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
            issues.append(f"too many uncited content paragraphs ({uncited}/{content_paras} = {rate:.1%}; max={max_uncited:.0%})")

    # Boilerplate repetition.
    rep = _repeated_sentences(draft)
    if rep:
        example, count = rep
        issues.append(f"repeated boilerplate sentence ({count}×): `{example}`")

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

    status = "PASS" if not issues else "FAIL"

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

    if issues:
        lines.append("## Blocking issues")
        for it in issues:
            lines.append(f"- {it}")
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
