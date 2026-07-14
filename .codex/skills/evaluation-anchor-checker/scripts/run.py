from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"
NUMERIC_HYGIENE_PATH = ASSET_ROOT / "numeric_hygiene.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


NUMERIC_HYGIENE = _load_json(NUMERIC_HYGIENE_PATH)
TASK_KEYWORDS = [str(x).strip().lower() for x in (NUMERIC_HYGIENE.get("task_keywords") or []) if str(x).strip()]
METRIC_KEYWORDS = [str(x).strip().lower() for x in (NUMERIC_HYGIENE.get("metric_keywords") or []) if str(x).strip()]
CONSTRAINT_KEYWORDS = [str(x).strip().lower() for x in (NUMERIC_HYGIENE.get("constraint_keywords") or []) if str(x).strip()]
NUMERIC_PATTERNS = [re.compile(str(x)) for x in (NUMERIC_HYGIENE.get("numeric_sentence_patterns") or []) if str(x).strip()]
WEAKEN_TEMPLATES = NUMERIC_HYGIENE.get("weaken_templates") or {}
CITE_BLOCK_RE = re.compile(r"\s*\[@[^\]]+\]\s*")
AUDIT_EVAL_CONTEXT_RE = re.compile(r"(?i)(?:benchmark|dataset|datasets|metric|metrics|protocol|evaluation|eval\.|latency|cost|budget|token|tokens|throughput|compute|score|accuracy|exact|success)")
LEGACY_WEAKEN_RE = re.compile(
    r"(?i)^(?:"
    r"reported gains on the stated benchmark and task setting remain specific to the reported|"
    r"reported performance gains on the stated benchmark and task setting remain tied to the reported|"
    r"the cited number should be read as local to the reported benchmark and task setup|"
    r"this numeric result is tied to the stated evaluation setup|"
    r"this performance gain should be read within the stated evaluation setup|"
    r"the reported trade-off remains specific to the stated benchmark and task setting|"
    r"that trade-off should be read as local to the reported evaluation setup|"
    r"the reported comparison favors one system under the stated benchmark and task setting|"
    r"that numeric comparison is tied to the cited benchmark and task setup|"
    r"the comparison should be treated as local to the reported evaluation setup|"
    r"that number belongs to the cited setup|"
    r"the cited number only holds under the stated setup|"
    r"this numeric margin is still setup-bound|"
    r"the comparison only holds as stated for the cited setup|"
    r"the reported edge stays benchmark-local"
    r")"
)


def _has_numeric(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in NUMERIC_PATTERNS)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _deslash(text: str) -> str:
    s = re.sub(r"\s*/\s*", " and ", str(text or ""))
    s = re.sub(r"\band\s+and\b", "and", s)
    return _normalize_space(s)


def _split_sentences(paragraph: str) -> list[str]:
    text = _normalize_space(paragraph)
    if not text:
        return []
    protected = re.sub(r'(?i)\bvs\.', 'vs', text)
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", protected) if part.strip()]


def _extract_cites(text: str) -> str:
    cites = re.findall(r"\[@[^\]]+\]", text or "")
    return " ".join(cites).strip()


def _strip_cites(text: str) -> str:
    return _normalize_space(CITE_BLOCK_RE.sub(" ", text or "")).strip(" ,;:")


def _category_count(text: str, pack: dict[str, Any]) -> int:
    low = _strip_cites(text).lower()
    categories = 0
    task_terms = set(TASK_KEYWORDS)
    metric_terms = set(METRIC_KEYWORDS)
    constraint_terms = set(CONSTRAINT_KEYWORDS)

    eval_anchor = pack.get("evaluation_anchor_minimal") or {}
    if isinstance(eval_anchor, dict):
        task_terms.update(re.findall(r"[a-z][a-z0-9-]+", str(eval_anchor.get("task") or "").lower()))
        metric_terms.update(re.findall(r"[a-z][a-z0-9-]+", str(eval_anchor.get("metric") or "").lower()))
        constraint_terms.update(re.findall(r"[a-z][a-z0-9-]+", str(eval_anchor.get("constraint") or "").lower()))

    if any(term and term in low for term in task_terms):
        categories += 1
    if any(term and term in low for term in metric_terms):
        categories += 1
    if any(term and term in low for term in constraint_terms):
        categories += 1
    return categories


def _has_metric_context(text: str, pack: dict[str, Any]) -> bool:
    low = _strip_cites(text).lower()
    metric_terms = set(METRIC_KEYWORDS)
    eval_anchor = pack.get("evaluation_anchor_minimal") or {}
    if isinstance(eval_anchor, dict):
        metric_terms.update(re.findall(r"[a-z][a-z0-9-]+", _deslash(str(eval_anchor.get("metric") or "")).lower()))
    return any(term and term in low for term in metric_terms)


def _has_eval_context_token(text: str) -> bool:
    return bool(AUDIT_EVAL_CONTEXT_RE.search(_strip_cites(text)))


def _rewrite_kind(text: str) -> str:
    low = _strip_cites(text).lower()
    if any(word in low for word in ["latency", "cost", "budget", "trade-off", "constraint"]):
        return "tradeoff"
    if any(word in low for word in ["outperform", "higher than", "lower than", "compared to", "versus", "vs."]):
        return "comparison"
    if any(word in low for word in ["success", "accuracy", "score", "gain", "improvement", "tasks"]):
        return "performance"
    return "default"


def _pick_template(seed: str, value: Any) -> str:
    if isinstance(value, list):
        options = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not options:
            return ""
        digest = hashlib.sha1(str(seed or "").encode("utf-8", errors="ignore")).hexdigest()
        idx = int(digest[:12], 16) % len(options)
        return options[idx]
    return str(value or "").strip()


def _pack_hint(pack: dict[str, Any], field: str, fallback: str) -> str:
    eval_anchor = pack.get("evaluation_anchor_minimal") or {}
    if not isinstance(eval_anchor, dict):
        return fallback
    value = _deslash(str(eval_anchor.get(field) or ""))
    return value or fallback


def _weaken_numeric_sentence(text: str, pack: dict[str, Any]) -> str:
    cites = _extract_cites(text)
    kind = _rewrite_kind(text)
    template = _pick_template(
        f"{kind}:{pack.get('sub_id') or ''}:{pack.get('title') or ''}:{_strip_cites(text)}:{_pack_hint(pack, 'task', 'task')}:{_pack_hint(pack, 'metric', 'metric')}",
        WEAKEN_TEMPLATES.get(kind) or WEAKEN_TEMPLATES.get("default") or "",
    ).strip()
    if not template:
        template = "Reported gains remain specific to the reported setting"
    rewritten = template.format(
        title=_normalize_space(str(pack.get("title") or "")) or "this subsection",
        title_lower=(_normalize_space(str(pack.get("title") or "")).lower() or "this subsection"),
        task=_pack_hint(pack, "task", "task"),
        metric=_pack_hint(pack, "metric", "metric"),
        constraint=_pack_hint(pack, "constraint", "constraint"),
    ).strip()
    rewritten = rewritten.rstrip(" .")
    if cites:
        return f"{rewritten} {cites}."
    return f"{rewritten}."


def _load_writer_packs(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
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
        if not isinstance(rec, dict):
            continue
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            out[sid] = rec
    return out


def _sub_id_from_section_path(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("S"):
        return ""
    body = stem[1:]
    if body.endswith("_lead"):
        body = body[:-5]
    return body.replace("_", ".")


def _polish_paragraph(paragraph: str, pack: dict[str, Any]) -> tuple[str, int]:
    sentences = _split_sentences(paragraph)
    if not sentences:
        return paragraph, 0
    changed = 0
    out: list[str] = []
    for sentence in sentences:
        if LEGACY_WEAKEN_RE.search(_strip_cites(sentence)):
            out.append(_weaken_numeric_sentence(sentence, pack))
            changed += 1
            continue
        if _has_numeric(sentence) and (
            _category_count(sentence, pack) < 2
            or not _has_metric_context(sentence, pack)
            or not _has_eval_context_token(sentence)
        ):
            out.append(_weaken_numeric_sentence(sentence, pack))
            changed += 1
            continue
        out.append(sentence)
    return " ".join(out).strip(), changed


def _process_section(path: Path, pack: dict[str, Any]) -> int:
    original = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"(\n\s*\n)", original)
    changed = 0
    out: list[str] = []
    for block in blocks:
        if not block or re.fullmatch(r"\n\s*\n", block):
            out.append(block)
            continue
        stripped = block.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("```"):
            out.append(block)
            continue
        polished, delta = _polish_paragraph(stripped, pack)
        changed += delta
        out.append(polished)
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def _write_report(path: Path, total_files: int, changed_files: int, changed_sentences: int) -> None:
    lines = [
        "# Evaluation Anchor Report",
        "",
        f"- Files checked: {total_files}",
        f"- Files changed: {changed_files}",
        f"- Numeric sentences weakened: {changed_sentences}",
        "",
        "- Policy: keep numbers only when task/metric/constraint context is explicit enough in the same sentence; otherwise weaken without changing citation keys.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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

    from tooling.common import ensure_dir

    workspace = Path(args.workspace).resolve()
    sections_dir = workspace / "sections"
    packs = _load_writer_packs(workspace / "outline" / "writer_context_packs.jsonl")
    report_path = workspace / "output" / "EVAL_ANCHOR_REPORT.md"
    ensure_dir(report_path.parent)

    changed_files = 0
    changed_sentences = 0
    total_files = 0
    for path in sorted(sections_dir.glob("S*.md")):
        if path.name.endswith("_lead.md"):
            continue
        sub_id = _sub_id_from_section_path(path)
        if "." not in sub_id:
            continue
        total_files += 1
        pack = packs.get(sub_id, {})
        changed = _process_section(path, pack)
        if changed:
            changed_files += 1
            changed_sentences += changed

    _write_report(report_path, total_files, changed_files, changed_sentences)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
