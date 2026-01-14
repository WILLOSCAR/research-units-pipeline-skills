from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists() or path.stat().st_size <= 0:
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _iter_units(units_csv: Path) -> list[dict[str, str]]:
    if not units_csv.exists() or units_csv.stat().st_size <= 0:
        return []
    with units_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(r) for r in reader]


def _has_blocked_subsection_writer(workspace: Path) -> bool:
    for row in _iter_units(workspace / "UNITS.csv"):
        status = (row.get("status") or "").strip().upper()
        skill = (row.get("skill") or "").strip()
        if status == "BLOCKED" and skill == "subsection-writer":
            return True
    return False


def _extract_issues(quality_md: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    for raw in (quality_md or "").splitlines():
        line = raw.strip()
        if not line.startswith("- `"):
            continue
        m = re.match(r"^-\s*`([^`]+)`\s*:\s*(.+)$", line)
        if not m:
            continue
        code = (m.group(1) or "").strip()
        msg = (m.group(2) or "").strip()
        if code:
            issues.append((code, msg))
    return issues


def _extract_paths(msg: str) -> list[str]:
    # Prefer backticked paths, then fall back to a loose pattern.
    paths: list[str] = []
    for m in re.finditer(r"`(sections/[^`]+?\.md)`", msg):
        paths.append(m.group(1))
    if paths:
        return paths
    for m in re.finditer(r"\b(sections/[A-Za-z0-9_.-]+\.md)\b", msg):
        paths.append(m.group(1))
    return paths


def _truncate(text: str, *, max_len: int) -> str:
    s = str(text or "").strip()
    if len(s) <= int(max_len):
        return s
    return s[: int(max_len)].rstrip() + "…"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()

    # Avoid confusing stale QUALITY_GATE.md after a successful run.
    if not _has_blocked_subsection_writer(workspace):
        print("No BLOCKED `subsection-writer` unit in UNITS.csv; skip writer self-loop.", file=sys.stderr)
        return 0

    quality_path = workspace / "output" / "QUALITY_GATE.md"
    if not quality_path.exists():
        print("No output/QUALITY_GATE.md found; nothing to self-loop.", file=sys.stderr)
        return 0

    quality_md = quality_path.read_text(encoding="utf-8", errors="ignore")
    issues = _extract_issues(quality_md)
    if not issues:
        print("QUALITY_GATE.md has no issue lines; nothing to self-loop.", file=sys.stderr)
        return 0

    issue_codes = {code for code, _ in issues}

    # Context packs.
    manifest_path = workspace / "sections" / "sections_manifest.jsonl"
    manifest = _read_jsonl(manifest_path)
    manifest_by_path: dict[str, dict[str, Any]] = {}
    for rec in manifest:
        rel = str(rec.get("path") or "").strip()
        if rel:
            manifest_by_path[rel] = rec

    briefs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _read_jsonl(workspace / "outline" / "subsection_briefs.jsonl"):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            briefs_by_sub[sid] = rec

    briefs_by_sec: dict[str, dict[str, Any]] = {}
    for rec in _read_jsonl(workspace / "outline" / "chapter_briefs.jsonl"):
        sid = str(rec.get("section_id") or "").strip()
        if sid:
            briefs_by_sec[sid] = rec

    context_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _read_jsonl(workspace / "outline" / "writer_context_packs.jsonl"):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            context_by_sub[sid] = rec

    by_file: dict[str, list[tuple[str, str]]] = {}
    orphan: list[tuple[str, str]] = []

    # When the gate is `sections_missing_files`, the QUALITY_GATE message is truncated.
    # Use `sections_manifest.jsonl` (complete expected file list) to enumerate all missing paths.
    if "sections_missing_files" in issue_codes and manifest:
        for rec in manifest:
            rel = str(rec.get("path") or "").strip()
            exists = rec.get("exists")
            if rel and exists is False:
                by_file.setdefault(rel, []).append(("sections_missing_files", "Missing or empty per-section file."))

    # Add any per-file issues that are already path-specific.
    for code, msg in issues:
        paths = _extract_paths(msg)
        if not paths:
            orphan.append((code, msg))
            continue
        for p in paths:
            by_file.setdefault(p, []).append((code, msg))

    if not by_file:
        print("QUALITY_GATE issues do not reference any sections/*.md paths; skip writer self-loop.", file=sys.stderr)
        return 0

    # Deduplicate per-file issues.
    by_file_dedup: dict[str, list[tuple[str, str]]] = {}
    for rel, items in by_file.items():
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, str]] = []
        for code, msg in items:
            key = (str(code), str(msg))
            if key in seen:
                continue
            seen.add(key)
            out.append((code, msg))
        by_file_dedup[rel] = out
    by_file = by_file_dedup

    out_path = workspace / "output" / "WRITER_SELFLOOP_TODO.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().replace(microsecond=0).isoformat()
    lines: list[str] = [
        "# Writer self-loop TODO",
        "",
        f"- Timestamp: `{now}`",
        f"- Source: `{quality_path.relative_to(workspace)}`",
        "",
        "## Failing files",
        "",
    ]

    for rel in sorted(by_file.keys()):
        lines.append(f"- `{rel}`")
        rec = manifest_by_path.get(rel) or {}
        if rec:
            kind = str(rec.get("kind") or "").strip()
            sid = str(rec.get("id") or "").strip()
            title = str(rec.get("title") or "").strip()
            lines.append(f"  - kind: `{kind}` id: `{sid}` title: {title}")

            if kind == "h3" and sid:
                brief = briefs_by_sub.get(sid) or {}
                rq = str(brief.get("rq") or "").strip()
                axes = brief.get("axes") or []
                if rq:
                    lines.append(f"  - rq: {rq}")
                if isinstance(axes, list) and axes:
                    lines.append(f"  - axes: {', '.join(str(a) for a in axes[:6])}")

                ctx = context_by_sub.get(sid) or {}
                if isinstance(ctx, dict) and ctx:
                    plan = ctx.get("paragraph_plan") or []
                    if isinstance(plan, list) and plan:
                        lines.append(f"  - paragraph_plan: {len(plan)} (intent sketch)")
                        for p in plan[:8]:
                            if not isinstance(p, dict):
                                continue
                            num = p.get("para")
                            intent = _truncate(p.get("intent") or "", max_len=160)
                            if not intent:
                                continue
                            prefix = f"p{num}" if str(num).strip() else "p?"
                            lines.append(f"    - {prefix}: {intent}")

                    comps = ctx.get("comparison_cards") or []
                    if isinstance(comps, list) and comps:
                        lines.append(f"  - comparison_cards: {len(comps)} (examples)")
                        for c in comps[:3]:
                            if not isinstance(c, dict):
                                continue
                            axis = _truncate(c.get("axis") or "", max_len=80)
                            a = _truncate(c.get("A_label") or "", max_len=60)
                            b = _truncate(c.get("B_label") or "", max_len=60)
                            cites = c.get("citations") or []
                            cite_str = ", ".join(str(x).lstrip("@").strip() for x in cites if str(x).strip())
                            head = " | ".join([p for p in [axis, f"{a} vs {b}" if (a or b) else ""] if p])
                            if cite_str:
                                lines.append(f"    - {head} (cites: {cite_str})")
                            else:
                                lines.append(f"    - {head}")

                    evals = ctx.get("evaluation_protocol") or []
                    if isinstance(evals, list) and evals:
                        lines.append(f"  - evaluation_protocol: {len(evals)} (examples)")
                        for e in evals[:2]:
                            if not isinstance(e, dict):
                                continue
                            bullet = _truncate(e.get("bullet") or "", max_len=240)
                            if not bullet:
                                continue
                            cites = e.get("citations") or []
                            cite_str = ", ".join(str(x).lstrip("@").strip() for x in cites if str(x).strip())
                            if cite_str:
                                lines.append(f"    - {bullet} (cites: {cite_str})")
                            else:
                                lines.append(f"    - {bullet}")

                    lims = ctx.get("limitation_hooks") or []
                    if isinstance(lims, list) and lims:
                        lines.append(f"  - limitation_hooks: {len(lims)} (examples)")
                        for l in lims[:2]:
                            if not isinstance(l, dict):
                                continue
                            excerpt = _truncate(l.get("excerpt") or l.get("bullet") or l.get("text") or "", max_len=240)
                            if not excerpt:
                                continue
                            cites = l.get("citations") or []
                            cite_str = ", ".join(str(x).lstrip("@").strip() for x in cites if str(x).strip())
                            if cite_str:
                                lines.append(f"    - {excerpt} (cites: {cite_str})")
                            else:
                                lines.append(f"    - {excerpt}")

            if kind == "h2_lead" and sid:
                brief = briefs_by_sec.get(sid) or {}
                through = brief.get("throughline") or []
                key_contrasts = brief.get("key_contrasts") or []
                if isinstance(through, list) and through:
                    lines.append(f"  - throughline: {', '.join(str(x) for x in through[:6])}")
                if isinstance(key_contrasts, list) and key_contrasts:
                    lines.append(f"  - key_contrasts: {', '.join(str(x) for x in key_contrasts[:6])}")

            allowed_sel = rec.get("allowed_bibkeys_selected") or []
            allowed_map = rec.get("allowed_bibkeys_mapped") or []
            anchors = rec.get("anchor_facts") or []
            evidence_ids = rec.get("evidence_ids") or []
            allowed_chapter = rec.get("allowed_bibkeys_chapter") or []

            if isinstance(allowed_sel, list) and allowed_sel:
                sample = ", ".join(str(k) for k in allowed_sel[:12])
                suffix = "…" if len(allowed_sel) > 12 else ""
                lines.append(f"  - allowed_bibkeys_selected: {sample}{suffix}")
            if isinstance(allowed_map, list) and allowed_map:
                lines.append(f"  - allowed_bibkeys_mapped: {len(allowed_map)}")
            if isinstance(allowed_chapter, list) and allowed_chapter:
                lines.append(f"  - allowed_bibkeys_chapter: {len(allowed_chapter)}")
            if isinstance(evidence_ids, list) and evidence_ids:
                lines.append(f"  - evidence_ids: {len(evidence_ids)}")
            if isinstance(anchors, list) and anchors:
                # Show a couple of concrete hooks (truncate heavily).
                lines.append(f"  - anchor_facts: {len(anchors)} (examples)")
                for a in anchors[:2]:
                    if not isinstance(a, dict):
                        continue
                    hook = str(a.get("hook_type") or "").strip()
                    txt = _truncate(a.get("text") or "", max_len=220)
                    cites = a.get("citations") or []
                    cite_str = ", ".join(str(c).lstrip("@").strip() for c in cites if str(c).strip())
                    if cite_str:
                        lines.append(f"    - {hook}: {txt} (cites: {cite_str})")
                    else:
                        lines.append(f"    - {hook}: {txt}")

        for code, msg in by_file[rel]:
            lines.append(f"  - `{code}`: {msg}")

    if orphan:
        lines.extend(["", "## Orphan issues (no sections/*.md path detected)", ""])
        for code, msg in orphan:
            lines.append(f"- `{code}`: {msg}")

    lines.extend(
        [
            "",
            "## Loop",
            "",
            "1) Fix only the failing `sections/*.md` files above (follow `.codex/skills/writer-selfloop/SKILL.md`).",
            "2) Recheck:",
            "",
            "```bash",
            f"python .codex/skills/subsection-writer/scripts/run.py --workspace {workspace.as_posix()}",
            "```",
            "",
        ]
    )

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(workspace)}")

    # Non-zero exit keeps a unit BLOCKED if wired in later.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
