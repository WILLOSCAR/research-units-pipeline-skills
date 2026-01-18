from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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

    from tooling.common import ensure_dir, now_iso_seconds, parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or [
        "outline/evidence_drafts.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/anchor_sheet.jsonl"]

    packs_path = workspace / inputs[0]
    bib_path = workspace / inputs[1]
    out_path = workspace / outputs[0]

    freeze_marker = out_path.parent / "anchor_sheet.refined.ok"
    if out_path.exists() and out_path.stat().st_size > 0 and freeze_marker.exists():
        return 0

    packs = read_jsonl(packs_path)
    if not packs:
        raise SystemExit(f"Missing or empty evidence packs: {packs_path}")

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    records: list[dict[str, Any]] = []
    for rec in packs:
        if not isinstance(rec, dict):
            continue
        sub_id = str(rec.get("sub_id") or "").strip()
        title = str(rec.get("title") or "").strip()
        if not sub_id or not title:
            continue

        anchors: list[dict[str, Any]] = []

        def add_anchor(*, hook_type: str, text: str, citations: list[str], paper_id: str = "", evidence_id: str = "", pointer: str = "") -> None:
            text = _trim(text)
            citations = [c for c in citations if _is_allowed_cite(c, bib_keys=bib_keys)]
            if not text or not citations:
                return
            anchors.append(
                {
                    "hook_type": hook_type,
                    "text": text,
                    "citations": citations,
                    "paper_id": paper_id,
                    "evidence_id": evidence_id,
                    "pointer": pointer,
                }
            )

        # Prefer quantitative excerpts from A/B highlights.
        for comp in rec.get("concrete_comparisons") or []:
            if not isinstance(comp, dict):
                continue
            for side in ("A_highlights", "B_highlights"):
                for hl in comp.get(side) or []:
                    if not isinstance(hl, dict):
                        continue
                    excerpt = str(hl.get("excerpt") or "").strip()
                    cites = [str(c).strip() for c in (hl.get("citations") or []) if str(c).strip()]
                    paper_id = str(hl.get("paper_id") or "").strip()
                    evidence_id = str(hl.get("evidence_id") or "").strip()
                    pointer = str(hl.get("pointer") or "").strip()
                    if re.search(r"\d", excerpt):
                        add_anchor(hook_type="quant", text=excerpt, citations=cites, paper_id=paper_id, evidence_id=evidence_id, pointer=pointer)

        # Evidence snippets: grab quantitative/evaluation/limitation hooks directly.
        for sn in rec.get("evidence_snippets") or []:
            if not isinstance(sn, dict):
                continue
            text = str(sn.get("text") or "").strip()
            cites = [str(c).strip() for c in (sn.get("citations") or []) if str(c).strip()]
            paper_id = str(sn.get("paper_id") or "").strip()
            evidence_id = str(sn.get("evidence_id") or "").strip()
            prov = sn.get("provenance") or {}
            pointer = str((prov or {}).get("pointer") or "").strip()

            if re.search(r"\d", text):
                add_anchor(hook_type="quant", text=text, citations=cites, paper_id=paper_id, evidence_id=evidence_id, pointer=pointer)
            if re.search(r"(?i)\b(benchmark|dataset|metric|evaluation|protocol)\b|评测|基准|数据集|指标", text):
                add_anchor(hook_type="eval", text=text, citations=cites, paper_id=paper_id, evidence_id=evidence_id, pointer=pointer)
            if re.search(r"(?i)\b(limitation|limited|failure|risk|caveat|threat)\b|局限|受限|失败|风险|待验证", text):
                add_anchor(hook_type="limitation", text=text, citations=cites, paper_id=paper_id, evidence_id=evidence_id, pointer=pointer)

        # Limitations/failures.
        for it in rec.get("failures_limitations") or []:
            if not isinstance(it, dict):
                continue
            add_anchor(
                hook_type="limitation",
                text=str(it.get("excerpt") or "").strip(),
                citations=[str(c).strip() for c in (it.get("citations") or []) if str(c).strip()],
                paper_id=str(it.get("paper_id") or "").strip(),
                evidence_id=str(it.get("evidence_id") or "").strip(),
                pointer=str(it.get("pointer") or "").strip(),
            )

        # De-dupe anchors by normalized text.
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for a in anchors:
            norm = re.sub(r"\s+", " ", str(a.get("text") or "").strip().lower())
            norm = re.sub(r"\[@[^\]]+\]", "", norm)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(a)

        records.append({"sub_id": sub_id, "title": title, "anchors": deduped[:12], "generated_at": now_iso_seconds()})

    _check_no_placeholders(records)
    ensure_dir(out_path.parent)
    write_jsonl(out_path, records)
    return 0


def _is_allowed_cite(cite: str, *, bib_keys: set[str]) -> bool:
    cite = str(cite or "").strip()
    if not cite.startswith("@"):
        return False
    key = cite[1:].strip()
    if not key:
        return False
    if bib_keys and key not in bib_keys:
        return False
    return True


def _trim(text: str, *, max_len: int = 280) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) > int(max_len):
        # Avoid adding ellipsis markers that may accidentally leak into prose.
        text = text[: int(max_len)].rstrip()
    return text


def _check_no_placeholders(records: list[dict[str, Any]]) -> None:
    raw = json.dumps(records, ensure_ascii=False)
    low = raw.lower()
    if "(placeholder)" in low:
        raise SystemExit("anchor_sheet contains placeholder markers")
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", raw):
        raise SystemExit("anchor_sheet contains TODO/TBD/FIXME")


if __name__ == "__main__":
    raise SystemExit(main())
