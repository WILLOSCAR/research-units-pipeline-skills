from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


_EVAL_STOP = {
    "ai",
    "ml",
    "llm",
    "nlp",
    "cv",
    "arxiv",
    "dataset",
    "datasets",
    "benchmark",
    "benchmarks",
    "metric",
    "metrics",
    "diffusion",
    "transformer",
}


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
        "outline/subsection_briefs.jsonl",
        "papers/paper_notes.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/evidence_drafts.jsonl"]

    briefs_path = workspace / inputs[0]
    notes_path = workspace / inputs[1]
    bib_path = workspace / inputs[2]
    out_path = workspace / outputs[0]

    if _looks_refined_jsonl(out_path):
        return 0

    briefs = read_jsonl(briefs_path)
    if not briefs:
        raise SystemExit(f"Missing or empty briefs: {briefs_path}")

    notes = read_jsonl(notes_path)
    if not notes:
        raise SystemExit(f"Missing or empty notes: {notes_path}")

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    bibkeys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    notes_by_pid: dict[str, dict[str, Any]] = {}
    for rec in notes:
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("paper_id") or "").strip()
        if pid:
            notes_by_pid[pid] = rec

    records: list[dict[str, Any]] = []
    md_dir = workspace / "outline" / "evidence_drafts"
    ensure_dir(md_dir)

    for brief in briefs:
        if not isinstance(brief, dict):
            continue
        sub_id = str(brief.get("sub_id") or "").strip()
        title = str(brief.get("title") or "").strip()
        if not sub_id or not title:
            continue

        rq = str(brief.get("rq") or "").strip()
        scope_rule = brief.get("scope_rule") or {}

        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        clusters = brief.get("clusters") or []
        evidence_summary = brief.get("evidence_level_summary") or {}

        cited_pids = _pids_from_clusters(clusters)
        cite_keys = _cite_keys_for_pids(cited_pids, notes_by_pid=notes_by_pid, bibkeys=bibkeys)

        evidence_snippets = _evidence_snippets(
            workspace=workspace,
            pids=cited_pids,
            notes_by_pid=notes_by_pid,
            bibkeys=bibkeys,
            limit=6,
        )

        fulltext_n = int(evidence_summary.get("fulltext", 0) or 0) if isinstance(evidence_summary, dict) else 0
        abstract_n = int(evidence_summary.get("abstract", 0) or 0) if isinstance(evidence_summary, dict) else 0
        title_n = int(evidence_summary.get("title", 0) or 0) if isinstance(evidence_summary, dict) else 0

        verify_fields = _verify_fields(axes=axes, evidence_summary={"fulltext": fulltext_n, "abstract": abstract_n})

        blocking_missing: list[str] = []
        if not cite_keys:
            blocking_missing.append("no usable citation keys for mapped papers (bibkey missing or not in ref.bib)")
        if (fulltext_n + abstract_n) == 0 and title_n > 0:
            blocking_missing.append("title-only evidence for this subsection (need abstracts or full text)")
        if not evidence_snippets:
            blocking_missing.append("no evidence snippets extractable from notes/fulltext (need richer abstracts/fulltext)")

        eval_tokens = _extract_eval_tokens(pids=cited_pids, notes_by_pid=notes_by_pid)
        wants_eval = any(t in " ".join(axes).lower() for t in ["evaluation", "benchmark", "metric", "dataset"])
        if wants_eval and not eval_tokens:
            blocking_missing.append("no concrete evaluation tokens (benchmarks/metrics) extractable for this subsection")

        definitions_setup = _definitions_setup(
            rq=rq,
            scope_rule=scope_rule,
            axes=axes,
            cite_keys=cite_keys,
        )

        claim_candidates = _claim_candidates(
            title=title,
            axes=axes,
            evidence_snippets=evidence_snippets,
            cite_keys=cite_keys,
            has_fulltext=(fulltext_n > 0),
        )

        concrete_comparisons = _comparisons(
            axes=axes,
            clusters=clusters,
            cite_keys=cite_keys,
        )
        if len([c for c in concrete_comparisons if isinstance(c, dict)]) < 3:
            blocking_missing.append("too few concrete comparisons (need >=3 A-vs-B comparisons grounded in clusters)")

        evaluation_protocol = _evaluation_protocol(
            tokens=eval_tokens,
            cite_keys=cite_keys,
        )

        failures_limitations = _limitations_from_notes(cited_pids, notes_by_pid=notes_by_pid, cite_keys=cite_keys)

        pack = {
            "sub_id": sub_id,
            "title": title,
            "evidence_level_summary": {
                "fulltext": fulltext_n,
                "abstract": abstract_n,
                "title": title_n,
            },
            "evidence_snippets": evidence_snippets,
            "definitions_setup": definitions_setup,
            "claim_candidates": claim_candidates,
            "concrete_comparisons": concrete_comparisons,
            "evaluation_protocol": evaluation_protocol,
            "failures_limitations": failures_limitations,
            "blocking_missing": blocking_missing,
            "verify_fields": verify_fields,
            "generated_at": now_iso_seconds(),
        }

        records.append(pack)
        _write_md_pack(md_dir / f"{sub_id}.md", pack)

    write_jsonl(out_path, records)
    return 0


def _looks_refined_jsonl(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    if "…" in text:
        return False
    if "<!-- scaffold" in low:
        return False
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", text):
        return False
    if "(placeholder)" in low:
        return False
    if path.stat().st_size < 800:
        return False
    try:
        for line in text.splitlines()[:3]:
            if line.strip():
                json.loads(line)
    except Exception:
        return False
    return True


def _pids_from_clusters(clusters: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(clusters, list):
        return out
    for c in clusters:
        if not isinstance(c, dict):
            continue
        for pid in c.get("paper_ids") or []:
            pid = str(pid).strip()
            if pid and pid not in out:
                out.append(pid)
    return out


def _cite_keys_for_pids(pids: list[str], *, notes_by_pid: dict[str, dict[str, Any]], bibkeys: set[str]) -> list[str]:
    out: list[str] = []
    for pid in pids:
        bibkey = str((notes_by_pid.get(pid) or {}).get("bibkey") or "").strip()
        if not bibkey or (bibkeys and bibkey not in bibkeys):
            continue
        key = f"@{bibkey}"
        if key not in out:
            out.append(key)
        if len(out) >= 12:
            break
    return out


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


def _evidence_snippets(*, workspace: Path, pids: list[str], notes_by_pid: dict[str, dict[str, Any]], bibkeys: set[str], limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for pid in pids:
        note = notes_by_pid.get(pid) or {}
        bibkey = str(note.get("bibkey") or "").strip()
        if not bibkey or (bibkeys and bibkey not in bibkeys):
            continue
        cite = f"@{bibkey}"

        evidence_level = str(note.get("evidence_level") or "").strip().lower() or "unknown"
        abstract = str(note.get("abstract") or "").strip()

        fulltext_rel = str(note.get("fulltext_path") or "").strip()
        fulltext_path = (workspace / fulltext_rel) if fulltext_rel else None

        text = ""
        provenance: dict[str, Any] = {"evidence_level": evidence_level}

        if evidence_level == "fulltext" and fulltext_path and fulltext_path.exists() and fulltext_path.stat().st_size > 800:
            raw = fulltext_path.read_text(encoding="utf-8", errors="ignore")[:3000]
            sents = _split_sentences(raw)
            text = " ".join(sents[:2]).strip()
            provenance.update({"source": "fulltext", "pointer": str(fulltext_rel)})
        elif abstract:
            sents = _split_sentences(abstract)
            text = " ".join(sents[:2]).strip() if sents else abstract[:240].strip()
            provenance.update({"source": "abstract", "pointer": f"papers/paper_notes.jsonl:paper_id={pid}#abstract"})
        else:
            bullets = note.get("summary_bullets") or []
            if isinstance(bullets, list):
                for b in bullets:
                    b = str(b).strip()
                    if len(b) >= 24 and not b.lower().startswith("evidence level") and not b.lower().startswith("main idea (from title)"):
                        text = b
                        provenance.update({"source": "paper_notes", "pointer": f"papers/paper_notes.jsonl:paper_id={pid}#summary_bullets"})
                        break

        if text:
            out.append(
                {
                    "text": text,
                    "paper_id": pid,
                    "citations": [cite],
                    "provenance": provenance,
                }
            )

        if len(out) >= int(limit):
            break

    return out


def _verify_fields(*, axes: list[str], evidence_summary: dict[str, Any]) -> list[str]:
    fields: list[str] = []

    def add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if x and x not in fields:
            fields.append(x)

    fulltext_n = int(evidence_summary.get("fulltext", 0) or 0)
    abstract_n = int(evidence_summary.get("abstract", 0) or 0)

    if fulltext_n == 0 and abstract_n > 0:
        add("verify fine-grained details with full text before making strong conclusions (abstract-level evidence)")

    joined = " ".join([a.lower() for a in axes])
    if "evaluation" in joined or "benchmark" in joined or "metric" in joined:
        add("named benchmarks/datasets used")
        add("metrics/human-eval protocol")
    if "compute" in joined or "efficien" in joined or "cost" in joined:
        add("compute/training/inference cost")
    if "data" in joined or "training" in joined:
        add("training data and supervision signal")
    if "failure" in joined or "limit" in joined:
        add("failure modes / known limitations")

    add("baseline choices and ablation evidence")

    return fields[:12]


def _definitions_setup(*, rq: str, scope_rule: Any, axes: list[str], cite_keys: list[str]) -> list[dict[str, Any]]:
    include = []
    exclude = []
    if isinstance(scope_rule, dict):
        include = [str(x).strip() for x in (scope_rule.get("include") or []) if str(x).strip()]
        exclude = [str(x).strip() for x in (scope_rule.get("exclude") or []) if str(x).strip()]

    rq_text = rq or "What is the subsection-specific question this section must answer?"
    scope_bits = []
    if include:
        scope_bits.append(f"in-scope: {include[0]}")
    if exclude:
        scope_bits.append(f"out-of-scope: {exclude[0]}")
    scope_txt = "; ".join(scope_bits)

    axis_txt = "; ".join([a for a in axes[:5] if a])
    bullet = f"Setup: {rq_text}"
    if scope_txt:
        bullet += f" Scope: {scope_txt}."
    if axis_txt:
        bullet += f" Axes: {axis_txt}."

    return [{"bullet": bullet.strip(), "citations": cite_keys[:3]}]


def _claim_candidates(
    *,
    title: str,
    axes: list[str],
    evidence_snippets: list[dict[str, Any]],
    cite_keys: list[str],
    has_fulltext: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    # Prefer snippet-derived claim candidates (less templated; traceable).
    for snip in evidence_snippets[:4]:
        if not isinstance(snip, dict):
            continue
        text = str(snip.get("text") or "").strip()
        if not text:
            continue
        # Keep the first sentence as a claim candidate.
        sent = _split_sentences(text)
        claim = sent[0] if sent else text
        claim = re.sub(r"\s+", " ", claim).strip()
        if len(claim) > 220:
            claim = claim[:220].rstrip()
        out.append(
            {
                "claim": claim,
                "evidence_field": "evidence_snippet",
                "citations": snip.get("citations") if isinstance(snip.get("citations"), list) else cite_keys[:2],
            }
        )
        if len(out) >= 3:
            break

    # Fill remaining slots with axis-driven hypotheses (evidence-aware language).
    lead = "Claim" if has_fulltext else "Hypothesis"
    for ax in [a for a in axes if a][:5]:
        if len(out) >= 5:
            break
        out.append(
            {
                "claim": f"{lead}: In '{title}', compare mapped works along '{ax}' and state when each choice is preferred, citing the most relevant evidence.",
                "evidence_field": ax,
                "citations": cite_keys[:3],
            }
        )

    return out[:5]


def _comparisons(*, axes: list[str], clusters: Any, cite_keys: list[str]) -> list[dict[str, Any]]:
    axes = [a for a in axes if a]
    if not axes:
        axes = ["mechanism/architecture", "evaluation protocol", "compute/efficiency"]

    labels: list[str] = []
    a_pids: list[str] = []
    b_pids: list[str] = []

    if isinstance(clusters, list):
        for c in clusters:
            if isinstance(c, dict) and c.get("label"):
                labels.append(str(c["label"]).strip())
        if clusters and isinstance(clusters[0], dict):
            a_pids = [str(x).strip() for x in (clusters[0].get("paper_ids") or []) if str(x).strip()]
        if len(clusters) > 1 and isinstance(clusters[1], dict):
            b_pids = [str(x).strip() for x in (clusters[1].get("paper_ids") or []) if str(x).strip()]

    a_label = labels[0] if labels else "Cluster A"
    b_label = labels[1] if len(labels) > 1 else "Cluster B"

    a_txt = a_label
    b_txt = b_label
    if a_pids:
        a_txt += ": " + ", ".join([f"`{p}`" for p in a_pids[:3]])
    if b_pids:
        b_txt += ": " + ", ".join([f"`{p}`" for p in b_pids[:3]])

    out: list[dict[str, Any]] = []
    for ax in axes[:3]:
        out.append(
            {
                "axis": ax,
                "A_papers": a_txt,
                "B_papers": b_txt,
                "evidence_field": ax,
                "citations": cite_keys[:6],
            }
        )
    return out


def _extract_eval_tokens(*, pids: list[str], notes_by_pid: dict[str, dict[str, Any]]) -> list[str]:
    tokens: list[str] = []

    def add(tok: str) -> None:
        t = (tok or "").strip()
        if not t:
            return
        low = t.lower()
        if low in _EVAL_STOP:
            return
        if len(t) < 3:
            return
        if t not in tokens:
            tokens.append(t)

    def scan(text: str) -> None:
        text = text or ""
        # Uppercase acronyms and CamelCase tokens are common for benchmarks/metrics.
        for m in re.findall(r"\b[A-Z]{2,}[A-Za-z0-9-]{0,18}\b", text):
            add(m)
        for m in re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9-]{1,24}\b", text):
            add(m)

    for pid in pids[:30]:
        note = notes_by_pid.get(pid) or {}
        scan(str(note.get("abstract") or ""))
        for b in (note.get("key_results") or []):
            scan(str(b or ""))
        for b in (note.get("limitations") or []):
            scan(str(b or ""))

    # Prefer a small list.
    return tokens[:12]


def _evaluation_protocol(*, tokens: list[str], cite_keys: list[str]) -> list[dict[str, Any]]:
    if tokens:
        return [
            {
                "bullet": "Evaluation tokens mentioned in mapped evidence: " + "; ".join(tokens[:10]) + ".",
                "citations": cite_keys[:4],
            }
        ]
    return [
        {
            "bullet": "Evaluation protocol details were not extractable from current abstracts/notes; treat evaluation claims as provisional and prioritize abstract/full text enrichment for this subsection.",
            "citations": cite_keys[:2],
        }
    ]


def _limitations_from_notes(pids: list[str], *, notes_by_pid: dict[str, dict[str, Any]], cite_keys: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pid in pids[:12]:
        note = notes_by_pid.get(pid) or {}
        bibkey = str(note.get("bibkey") or "").strip()
        cite = f"@{bibkey}" if bibkey else ""
        limitations = note.get("limitations") or []
        if not isinstance(limitations, list):
            continue
        for lim in limitations[:2]:
            lim = str(lim).strip()
            if not lim:
                continue
            low = lim.lower()
            if low.startswith("evidence level"):
                continue
            if low.startswith("abstract-level evidence"):
                continue
            out.append(
                {
                    "bullet": lim,
                    "citations": [cite] if cite else cite_keys[:2],
                }
            )
        if len(out) >= 4:
            break

    if not out:
        out.append(
            {
                "bullet": "No concrete limitations/failure modes were extractable from current notes; treat this as an evidence gap for the subsection.",
                "citations": cite_keys[:2],
            }
        )

    return out[:4]


def _write_md_pack(path: Path, pack: dict[str, Any]) -> None:
    from tooling.common import atomic_write_text

    sub_id = str(pack.get("sub_id") or "").strip()
    title = str(pack.get("title") or "").strip()

    lines: list[str] = [
        f"# Evidence draft: {sub_id} {title}",
        "",
        "## Evidence snippets (with provenance)",
    ]

    for s in pack.get("evidence_snippets") or []:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text") or "").strip()
        cites = " ".join([c for c in (s.get("citations") or []) if str(c).strip()])
        prov = s.get("provenance")
        prov_s = ""
        if isinstance(prov, dict):
            prov_s = " | ".join([str(prov.get("source") or "").strip(), str(prov.get("pointer") or "").strip()]).strip(" |")
        if text:
            line = f"- {text} {cites}".rstrip()
            if prov_s:
                line += f" (provenance: {prov_s})"
            lines.append(line)

    lines.extend(["", "## Definitions / setup", ""])
    for item in pack.get("definitions_setup") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    lines.extend(["", "## Claim candidates", ""])
    for item in pack.get("claim_candidates") or []:
        claim = str((item or {}).get("claim") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if claim:
            lines.append(f"- {claim} {cites}".rstrip())

    lines.extend(["", "## Concrete comparisons", ""])
    for item in pack.get("concrete_comparisons") or []:
        axis = str((item or {}).get("axis") or "").strip()
        a = str((item or {}).get("A_papers") or "").strip()
        b = str((item or {}).get("B_papers") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        lines.append(f"- Axis: {axis}; A: {a}; B: {b}. {cites}".rstrip())

    lines.extend(["", "## Evaluation protocol", ""])
    for item in pack.get("evaluation_protocol") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    lines.extend(["", "## Failures / limitations", ""])
    for item in pack.get("failures_limitations") or []:
        bullet = str((item or {}).get("bullet") or "").strip()
        cites = " ".join([c for c in (item or {}).get("citations") or [] if str(c).strip()])
        if bullet:
            lines.append(f"- {bullet} {cites}".rstrip())

    blocking = pack.get("blocking_missing") or []
    if blocking:
        lines.extend(["", "## Blocking missing (stop drafting)", ""])
        for m in blocking:
            m = str(m).strip()
            if m:
                lines.append(f"- {m}")

    verify = pack.get("verify_fields") or []
    if verify:
        lines.extend(["", "## Verify fields (non-blocking)", ""])
        for m in verify:
            m = str(m).strip()
            if m:
                lines.append(f"- {m}")

    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
