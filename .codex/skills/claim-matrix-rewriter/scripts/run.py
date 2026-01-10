from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


def _sid_key(s: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in str(s).split("."):
        try:
            out.append(int(chunk))
        except Exception:
            out.append(9999)
    return tuple(out)


def _bib_keys(bib_text: str) -> set[str]:
    return set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text or ""))


def _format_first_cite(citations: Any, *, bib_keys: set[str]) -> str:
    if not isinstance(citations, list):
        return ""
    for c in citations:
        c = str(c or "").strip()
        if not c:
            continue
        if c.startswith("[@") and c.endswith("]"):
            c = c[2:-1]
        if c.startswith("@"):
            c = c[1:]
        for k in re.findall(r"[A-Za-z0-9:_-]+", c):
            if bib_keys and k not in bib_keys:
                continue
            return f" [@{k}]"
    return ""


def _collect_bibkey_by_pid(packs_by: dict[str, dict[str, Any]]) -> dict[str, str]:
    # Best-effort: infer a paper_id -> bibkey map from evidence snippets.
    out: dict[str, str] = {}
    for pack in packs_by.values():
        for snip in pack.get("evidence_snippets") or []:
            if not isinstance(snip, dict):
                continue
            pid = str(snip.get("paper_id") or "").strip()
            if not pid:
                continue
            cite = _format_first_cite(snip.get("citations"), bib_keys=set())
            if cite.startswith(" [@") and cite.endswith("]"):
                out.setdefault(pid, cite[3:-1])
    return out


def _choose_claim(*, brief: dict[str, Any], pack: dict[str, Any]) -> str:
    title = str(brief.get("title") or pack.get("title") or "").strip() or "this subsection"

    # Prefer a concrete claim candidate if present.
    for item in pack.get("claim_candidates") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        low = claim.lower()
        if "todo" in low or "placeholder" in low or "scaffold" in low:
            continue
        if "enumerate" in low:
            continue
        # Keep short.
        claim = re.sub(r"\s+", " ", claim)
        if len(claim) > 220:
            claim = claim[:220].rstrip()
        return claim

    axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
    clusters = brief.get("clusters") or []
    labels = []
    if isinstance(clusters, list):
        for c in clusters:
            if isinstance(c, dict) and c.get("label"):
                labels.append(str(c["label"]).strip())
    c1 = labels[0] if labels else "Cluster A"
    c2 = labels[1] if len(labels) > 1 else "Cluster B"

    evsum = pack.get("evidence_level_summary") or brief.get("evidence_level_summary") or {}
    fulltext = int(evsum.get("fulltext") or 0) if isinstance(evsum, dict) else 0
    provisional = fulltext <= 0

    axis_hint = ", ".join(axes[:3]) if axes else "concrete axes"
    lead = "Provisional claim" if provisional else "Claim"

    return (
        f"{lead}: In {title}, synthesis should contrast {c1} vs {c2} along {axis_hint}, "
        "keeping scope boundaries explicit and tying every comparison to cited evidence."
    )


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

    from tooling.common import atomic_write_text, parse_semicolon_list, read_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/subsection_briefs.jsonl",
        "outline/evidence_drafts.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/claim_evidence_matrix.md"]

    briefs_path = workspace / inputs[0]
    packs_path = workspace / inputs[1]
    bib_path = workspace / inputs[2]
    out_path = workspace / outputs[0]

    briefs = read_jsonl(briefs_path)
    packs = read_jsonl(packs_path)

    if not briefs:
        raise SystemExit(f"Missing or empty briefs: {briefs_path}")
    if not packs:
        raise SystemExit(f"Missing or empty evidence packs: {packs_path}")

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    bib_keys = _bib_keys(bib_text)

    briefs_by = {
        str(b.get("sub_id") or "").strip(): b
        for b in briefs
        if isinstance(b, dict) and str(b.get("sub_id") or "").strip()
    }
    packs_by = {
        str(p.get("sub_id") or "").strip(): p
        for p in packs
        if isinstance(p, dict) and str(p.get("sub_id") or "").strip()
    }

    pid_to_bib = _collect_bibkey_by_pid(packs_by)

    parts: list[str] = [
        "# Claim–Evidence matrix",
        "",
        "This artifact is bullets-only and is meant to make evidence explicit before writing.",
        "",
        "Generated as a projection of `outline/evidence_drafts.jsonl` (evidence packs).",
        "",
    ]

    for sub_id in sorted(briefs_by.keys(), key=_sid_key):
        brief = briefs_by.get(sub_id) or {}
        pack = packs_by.get(sub_id) or {}

        title = str(brief.get("title") or pack.get("title") or "").strip()
        if not title:
            continue

        parts.append(f"## {sub_id} {title}")
        parts.append("")

        rq = str(brief.get("rq") or "").strip()
        if rq:
            parts.append(f"- RQ: {rq}")

        claim = _choose_claim(brief=brief, pack=pack)
        parts.append(f"- Claim: {claim}")

        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        if axes:
            parts.append(f"  - Axes: {'; '.join(axes[:8])}")

        evsum = pack.get("evidence_level_summary") or brief.get("evidence_level_summary") or {}
        if isinstance(evsum, dict):
            parts.append(
                "  - Evidence levels: "
                + ", ".join([f"{k}={int(evsum.get(k) or 0)}" for k in ["fulltext", "abstract", "title"]])
                + "."
            )

        # Prefer evidence snippets (with provenance); fall back to cluster paper_ids.
        evidence_written = 0
        snippets = [s for s in (pack.get("evidence_snippets") or []) if isinstance(s, dict)]
        for snip in snippets[:8]:
            text = re.sub(r"\s+", " ", str(snip.get("text") or "").strip())
            pid = str(snip.get("paper_id") or "").strip()
            cites = _format_first_cite(snip.get("citations"), bib_keys=bib_keys)
            prov = snip.get("provenance")
            prov_src = ""
            if isinstance(prov, dict):
                src = str(prov.get("source") or "").strip()
                ptr = str(prov.get("pointer") or "").strip()
                if src or ptr:
                    prov_src = f" (provenance: {src}{' | ' if src and ptr else ''}{ptr})"
            if pid and text:
                parts.append(f"  - Evidence: `{pid}`{cites} — {text}{prov_src}")
                evidence_written += 1
            elif pid:
                parts.append(f"  - Evidence: `{pid}`{cites}")
                evidence_written += 1
            if evidence_written >= 6:
                break

        if evidence_written < 2:
            # Fallback: use cluster paper ids even if snippets are missing.
            clusters = brief.get("clusters") or []
            pids: list[str] = []
            if isinstance(clusters, list):
                for c in clusters:
                    if not isinstance(c, dict):
                        continue
                    for pid in c.get("paper_ids") or []:
                        pid = str(pid).strip()
                        if pid and pid not in pids:
                            pids.append(pid)
            for pid in pids[: max(0, 2 - evidence_written)]:
                bib = pid_to_bib.get(pid, "")
                cite = f" [@{bib}]" if bib and (not bib_keys or bib in bib_keys) else ""
                parts.append(f"  - Evidence: `{pid}`{cite}")
                evidence_written += 1
                if evidence_written >= 2:
                    break

        # Provisional-mode reminder.
        if isinstance(evsum, dict) and int(evsum.get("fulltext") or 0) <= 0:
            parts.append(
                "  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations."
            )

        parts.append("")

    atomic_write_text(out_path, "\n".join(parts).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
