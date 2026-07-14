from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


_META_ANCHOR_RE = re.compile(
    r"(?i)^(?:evaluation mentions include:|our contributions are\b|this document is a practical framework\b|"
    r"when comparing results, anchor the paragraph with|prefer head-to-head comparisons only when|"
    r"avoid underspecified model|if a claim relies on a single reported number|"
    r"if budgets or environments differ across papers|use conservative language)"
)


def _is_usable_anchor_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return bool(normalized and not _META_ANCHOR_RE.search(normalized))


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

    from tooling.common import ensure_dir, latest_outline_state, load_workspace_pipeline_spec, now_iso_seconds, parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()
    spec = load_workspace_pipeline_spec(workspace)
    if spec is not None and str(spec.structure_mode or "").strip() == "section_first":
        state = latest_outline_state(workspace)
        if not state:
            raise SystemExit("Missing outline_state.jsonl; run the section-first C2 planner pass before anchor-sheet.")
        if str(state.get("structure_phase") or "").strip() != "decomposed" or str(state.get("h3_status") or "").strip() != "stable":
            raise SystemExit("Section-first cutover not ready: `outline_state.jsonl` must report `structure_phase: decomposed` and `h3_status: stable` before anchor-sheet.")
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

    _assert_h3_cutover_ready(workspace=workspace, consumer="anchor-sheet")

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
            if not _is_usable_anchor_text(text):
                return
            norm: list[str] = []
            seen: set[str] = set()
            for c in citations:
                k = _normalize_cite_key(c, bib_keys=bib_keys)
                if k and k not in seen:
                    seen.add(k)
                    norm.append(k)
            citations = norm
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
                text=str(it.get("excerpt") or it.get("bullet") or it.get("text") or "").strip(),
                citations=[str(c).strip() for c in (it.get("citations") or []) if str(c).strip()],
                paper_id=str(it.get("paper_id") or "").strip(),
                evidence_id=str(it.get("evidence_id") or "").strip(),
                pointer=str(it.get("pointer") or "").strip(),
            )

        # Claim candidates: preserve cite-backed, non-placeholder claim sentences as additional anchors.
        for it in rec.get("claim_candidates") or []:
            if not isinstance(it, dict):
                continue
            add_anchor(
                hook_type="claim",
                text=str(it.get("claim") or "").strip(),
                citations=[str(c).strip() for c in (it.get("citations") or []) if str(c).strip()],
                paper_id=str(it.get("paper_id") or "").strip(),
                evidence_id=str(it.get("evidence_id") or "").strip(),
                pointer=str(it.get("pointer") or "").strip(),
            )

        # If still thin, top off with any remaining cite-backed evidence snippets rather than failing on extraction narrowness.
        if len(anchors) < 12:
            for sn in rec.get("evidence_snippets") or []:
                if not isinstance(sn, dict):
                    continue
                add_anchor(
                    hook_type="fact",
                    text=str(sn.get("text") or "").strip(),
                    citations=[str(c).strip() for c in (sn.get("citations") or []) if str(c).strip()],
                    paper_id=str(sn.get("paper_id") or "").strip(),
                    evidence_id=str(sn.get("evidence_id") or "").strip(),
                    pointer=str((sn.get("provenance") or {}).get("pointer") or "").strip(),
                )
                if len(anchors) >= 12:
                    break

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

        def try_append(*, hook_type: str, text: str, citations: list[str], paper_id: str = "", evidence_id: str = "", pointer: str = "") -> None:
            if len(deduped) >= 12:
                return
            norm_text = _trim(text)
            if not _is_usable_anchor_text(norm_text):
                return
            norm = re.sub(r"\s+", " ", norm_text.strip().lower())
            norm = re.sub(r"\[@[^\]]+\]", "", norm)
            if not norm or norm in seen:
                return
            cite_list = []
            seen_cites: set[str] = set()
            for c in citations:
                key = _normalize_cite_key(c, bib_keys=bib_keys)
                if key and key not in seen_cites:
                    seen_cites.add(key)
                    cite_list.append(key)
            if not cite_list:
                return
            seen.add(norm)
            deduped.append({
                "hook_type": hook_type,
                "text": norm_text,
                "citations": cite_list,
                "paper_id": paper_id,
                "evidence_id": evidence_id,
                "pointer": pointer,
            })

        if len(deduped) < 12:
            for sn in rec.get("evidence_snippets") or []:
                if not isinstance(sn, dict):
                    continue
                try_append(
                    hook_type="fact",
                    text=str(sn.get("text") or "").strip(),
                    citations=[str(c).strip() for c in (sn.get("citations") or []) if str(c).strip()],
                    paper_id=str(sn.get("paper_id") or "").strip(),
                    evidence_id=str(sn.get("evidence_id") or "").strip(),
                    pointer=str((sn.get("provenance") or {}).get("pointer") or "").strip(),
                )
                if len(deduped) >= 12:
                    break

        if len(deduped) < 12:
            for it in rec.get("claim_candidates") or []:
                if not isinstance(it, dict):
                    continue
                try_append(
                    hook_type="claim",
                    text=str(it.get("claim") or "").strip(),
                    citations=[str(c).strip() for c in (it.get("citations") or []) if str(c).strip()],
                    paper_id=str(it.get("paper_id") or "").strip(),
                    evidence_id=str(it.get("evidence_id") or "").strip(),
                    pointer=str(it.get("pointer") or "").strip(),
                )
                if len(deduped) >= 12:
                    break

        if len(deduped) < 12:
            for it in rec.get("evaluation_protocol") or []:
                if not isinstance(it, dict):
                    continue
                if str(it.get("kind") or "").strip().lower() == "protocol_guardrail":
                    continue
                try_append(
                    hook_type="eval",
                    text=str(it.get("bullet") or "").strip(),
                    citations=[str(c).strip() for c in (it.get("citations") or []) if str(c).strip()],
                    pointer=str(it.get("pointer") or "").strip(),
                )
                if len(deduped) >= 12:
                    break

        records.append({"sub_id": sub_id, "title": title, "anchors": deduped[:12], "generated_at": now_iso_seconds()})

    _check_no_placeholders(records)
    ensure_dir(out_path.parent)
    write_jsonl(out_path, records)
    return 0


def _normalize_cite_key(cite: str, *, bib_keys: set[str]) -> str:
    cite = str(cite or "").strip()
    if cite.startswith("[@") and cite.endswith("]"):
        cite = cite[2:-1].strip()
    if cite.startswith("@"):
        cite = cite[1:].strip()
    key = cite.strip()
    if not key:
        return ""
    if bib_keys and key not in bib_keys:
        return ""
    return key


def _trim(text: str, *, max_len: int = 280) -> str:
    from tooling.common import bounded_complete_text

    return bounded_complete_text(text, max_chars=int(max_len), overflow_factor=3.0)


def _check_no_placeholders(records: list[dict[str, Any]]) -> None:
    raw = json.dumps(records, ensure_ascii=False)
    low = raw.lower()
    if "(placeholder)" in low:
        raise SystemExit("anchor_sheet contains placeholder markers")
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", raw):
        raise SystemExit("anchor_sheet contains TODO/TBD/FIXME")


if __name__ == "__main__":
    raise SystemExit(main())
