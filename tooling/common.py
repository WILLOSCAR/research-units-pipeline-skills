from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


_NONTERMINAL_ABBREVIATION_RE = re.compile(
    r"(?i)(?:\bvs|\bet\s+al|e\.g|i\.e)\.$"
)
_SENTENCE_ABBREVIATION_RE = re.compile(
    r"\b(?:e\.g\.|i\.e\.|etc\.|cf\.|vs\.|et al\.|fig\.|figs\.|eq\.|eqs\.|"
    r"sec\.|secs\.|no\.|dr\.|mr\.|ms\.|prof\.)",
    flags=re.IGNORECASE,
)

_STRONG_BOUNDED_SURVEY_DELIVERABLE_EN = (
    r"(?:course\s+paper|term\s+paper|course\s+report|class\s+report|"
    r"seminar\s+paper|seminar\s+report|end(?:-|\s+)of(?:-|\s+)term\s+(?:paper|report)|"
    r"short\s+literature(?:-|\s+)review(?:\s+report)?|literature\s+review\s+report)"
)
_GENERIC_BOUNDED_SURVEY_DELIVERABLE_EN = (
    r"(?:topic\s+report|technical\s+(?:literature|survey|research)\s+report|"
    r"research(?:-|\s+)landscape\s+report)"
)
_STRONG_BOUNDED_SURVEY_DELIVERABLE_ZH = (
    r"(?:课程论文|课程报告|期末论文|期末报告|结课论文|结课报告|"
    r"研讨课论文|研讨课报告|文献综述报告|短文献综述|短篇文献综述)"
)
_GENERIC_BOUNDED_SURVEY_DELIVERABLE_ZH = (
    r"(?:专题报告|专题调研报告|技术调研报告|技术综述报告|研究现状报告)"
)
_BOUNDED_SURVEY_DELIVERABLE_EN = (
    rf"(?:{_STRONG_BOUNDED_SURVEY_DELIVERABLE_EN}|{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_EN})"
)
_BOUNDED_SURVEY_DELIVERABLE_ZH = (
    rf"(?:{_STRONG_BOUNDED_SURVEY_DELIVERABLE_ZH}|{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_ZH})"
)
_NON_LITERATURE_REPORT_CONTEXT_RE = re.compile(
    r"(?i)\b(?:market|pricing|prices?|buying|purchasing|procurement|vendors?|"
    r"competitive\s+intelligence|investment|stocks?|live\s+web|current\s+policy|"
    r"current\s+regulation)\b|(?:市场|价格|采购|厂商|竞品|投资|股票|实时网页|舆情|现行政策|现行法规)"
)


def today_iso() -> str:
    return date.today().isoformat()


def now_iso_seconds() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def bounded_complete_text(text: str, *, max_chars: int, overflow_factor: float = 2.5) -> str:
    """Bound text without emitting a partial sentence or silently clipped clause.

    The preferred bound may be exceeded to preserve the first complete sentence.
    If no complete boundary exists within the hard overflow bound, return an
    empty string so callers can choose another evidence item.
    """

    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return ""
    preferred = max(1, int(max_chars))
    if len(normalized) <= preferred:
        return normalized

    hard_limit = max(preferred, int(preferred * max(1.0, float(overflow_factor))))
    bounded = normalized[:hard_limit]
    boundaries: list[int] = []
    for match in re.finditer(r"[.!?](?=\s|$)", bounded):
        if match.group() == "." and _NONTERMINAL_ABBREVIATION_RE.search(
            bounded[: match.end()]
        ):
            continue
        boundaries.append(match.end())
    before = [offset for offset in boundaries if offset <= preferred]
    if before:
        return normalized[: before[-1]].strip()
    after = [offset for offset in boundaries if offset > preferred]
    if after:
        return normalized[: after[0]].strip()
    if len(normalized) <= hard_limit and normalized.endswith((".", "!", "?")):
        return normalized
    return ""


def split_sentences(text: str) -> list[str]:
    """Split prose on sentence boundaries without breaking common abbreviations."""

    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return []

    protected = _SENTENCE_ABBREVIATION_RE.sub(
        lambda match: (match.group(0) or "").replace(".", "__DOT__"),
        normalized,
    )
    return [
        part.replace("__DOT__", ".").strip()
        for part in re.split(r"(?<=[.!?])\s+", protected)
        if part.strip()
    ]


def shell_quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def pipeline_cli_command(action: str, *, workspace: str | Path, extra_args: Iterable[str] = ()) -> str:
    parts = [
        "uv",
        "run",
        "python",
        "scripts/pipeline.py",
        action,
        "--workspace",
        str(workspace),
        *list(extra_args),
    ]
    return " ".join(shell_quote(part) for part in parts)


def backup_existing(path: Path) -> Path:
    """Rename an existing file to a timestamped `.bak.*` sibling and return the backup path."""
    if not path.exists():
        return path
    stamp = datetime.now().replace(microsecond=0).isoformat().replace("-", "").replace(":", "")
    backup = path.with_name(f"{path.name}.bak.{stamp}")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.bak.{stamp}.{counter}")
        counter += 1
    path.replace(backup)
    return backup


def refinement_marker_is_current(marker_path: Path, prerequisites: Iterable[Path]) -> bool:
    """Return true only when an explicit review marker is newer than every live prerequisite."""
    if not marker_path.exists():
        return False
    marker_mtime = marker_path.stat().st_mtime_ns
    existing = [Path(path) for path in prerequisites if Path(path).exists()]
    if not existing:
        return True
    return marker_mtime >= max(path.stat().st_mtime_ns for path in existing)


def parse_semicolon_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def normalize_title_for_dedupe(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def normalize_axis_label(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip().lower())
    text = text.rstrip(" .;:，；。")
    text = re.sub(r"\s*/\s*", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def subsection_brief_generic_axis_norms() -> set[str]:
    """Axis labels that strict survey gates treat as scaffold-level defaults.

    Keep this aligned across brief generation and quality-gate checks so the
    generator does not promote an axis that the gate later classifies as generic.
    """

    axes = {
        "core mechanism and system architecture",
        "training and data setup",
        "evaluation protocol",
        "evaluation protocol (benchmarks / metrics / human)",
        "evaluation protocol (datasets / metrics / human)",
        "evaluation protocol (datasets, metrics, human evaluation)",
        "compute and efficiency",
        "compute and latency constraints",
        "efficiency and compute",
        "tool interface contract (schemas / protocols)",
        "tool selection / routing policy",
        "sandboxing / permissions / observability",
        "failure modes and limitations",
    }
    return {normalize_axis_label(axis) for axis in axes}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def refresh_sections_manifest(
    workspace: Path,
    manifest_rel: str = "sections/sections_manifest.jsonl",
) -> list[dict[str, Any]]:
    """Refresh section fingerprints without changing manifest ownership metadata."""

    manifest_path = workspace / manifest_rel
    records = read_jsonl(manifest_path)
    generated_at = now_iso_seconds()
    refreshed: list[dict[str, Any]] = []
    for source in records:
        record = dict(source)
        relpath = str(record.get("path") or "").strip()
        path = workspace / relpath if relpath else Path()
        exists = bool(relpath and path.exists() and path.is_file() and path.stat().st_size > 0)
        record["exists"] = exists
        record["generated_at"] = generated_at
        if exists:
            text = path.read_text(encoding="utf-8", errors="ignore")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            record["citations"] = list(dict.fromkeys(re.findall(r"\[@([^\]]+)\]", text)))
            record["bytes"] = path.stat().st_size
            record["sha256"] = digest
        else:
            record.pop("citations", None)
            record.pop("bytes", None)
            record.pop("sha256", None)
        refreshed.append(record)
    write_jsonl(manifest_path, refreshed)
    return refreshed


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class UnitsTable:
    fieldnames: list[str]
    rows: list[dict[str, str]]

    @staticmethod
    def load(path: Path) -> "UnitsTable":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        return UnitsTable(fieldnames=fieldnames, rows=rows)

    def save(self, path: Path) -> None:
        ensure_dir(path.parent)
        fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
                writer.writeheader()
                for row in self.rows:
                    writer.writerow({key: row.get(key, "") for key in self.fieldnames})
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    atomic_write_text(path, text)


def copy_tree(src_dir: Path, dst_dir: Path, *, overwrite: bool) -> None:
    if not src_dir.is_dir():
        raise ValueError(f"Template directory not found: {src_dir}")
    ensure_dir(dst_dir)
    for src_path in src_dir.rglob("*"):
        rel = src_path.relative_to(src_dir)
        dst_path = dst_dir / rel
        if src_path.is_dir():
            ensure_dir(dst_path)
            continue
        ensure_dir(dst_path.parent)
        if dst_path.exists() and not overwrite:
            continue
        shutil.copy2(src_path, dst_path)


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if token]


_EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "we",
    "our",
    "via",
    "towards",
    "toward",
    "using",
    "use",
    "based",
    "new",
    "towards",
    "into",
    "over",
    "under",
    "between",
    "within",
    "without",
    "beyond",
}

_GENERIC_PAPER_WORDS = {
    "survey",
    "review",
    "tutorial",
    "paper",
    "approach",
    "method",
    "methods",
    "model",
    "models",
    "framework",
    "frameworks",
    "system",
    "systems",
    "learning",
    "deep",
    "neural",
    "network",
    "networks",
    "analysis",
    "benchmark",
    "benchmarks",
    "dataset",
    "datasets",
    "evaluation",
    "evaluating",
    "towards",
    "using",
    "based",
    "study",
    "studies",
}


def candidate_keywords(titles: Iterable[str], *, top_k: int, min_freq: int) -> list[str]:
    freq: dict[str, int] = {}
    for title in titles:
        for token in tokenize(title):
            if token in _EN_STOPWORDS or token in _GENERIC_PAPER_WORDS:
                continue
            if len(token) < 3:
                continue
            freq[token] = freq.get(token, 0) + 1
    candidates = [t for t, c in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])) if c >= min_freq]
    return candidates[:top_k]


def update_status_log(status_path: Path, line: str) -> None:
    ensure_dir(status_path.parent)
    if status_path.exists():
        existing = status_path.read_text(encoding="utf-8")
    else:
        existing = "# Status\n"
    if "## Run log" not in existing:
        existing = existing.rstrip() + "\n\n## Run log\n"
    updated = existing.rstrip() + f"\n- {line}\n"
    atomic_write_text(status_path, updated)


def update_status_field(status_path: Path, heading: str, value: str) -> None:
    heading_line = f"## {heading}".strip()
    bullet_line = f"- `{value}`"

    if status_path.exists():
        lines = status_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Status"]

    out: list[str] = []
    i = 0
    updated = False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() == heading_line:
            if i + 1 < len(lines) and lines[i + 1].lstrip().startswith("-"):
                out.append(bullet_line)
                i += 2
                updated = True
                continue
            out.append(bullet_line)
            updated = True
        i += 1

    if not updated:
        out.extend(["", heading_line, bullet_line])

    atomic_write_text(status_path, "\n".join(out).rstrip() + "\n")


def decisions_has_approval(decisions_path: Path, checkpoint: str) -> bool:
    if not checkpoint:
        return False
    if not decisions_path.exists():
        return False
    text = decisions_path.read_text(encoding="utf-8")
    pattern = rf"^\s*-\s*\[[xX]\]\s*(?:Approve\s*)?{re.escape(checkpoint)}\b"
    return re.search(pattern, text, flags=re.MULTILINE) is not None


def ensure_decisions_approval_checklist(decisions_path: Path) -> None:
    if decisions_path.exists():
        text = decisions_path.read_text(encoding="utf-8")
    else:
        text = "# Decisions log\n"

    if re.search(r"^##\s+Approvals\b", text, flags=re.MULTILINE):
        return

    workspace = decisions_path.parent
    checkpoints = _human_checkpoints_from_units(workspace)

    if not checkpoints:
        return

    checklist_lines = ["## Approvals (check to unblock)"]
    for checkpoint in checkpoints:
        hint = _approval_hint(checkpoint)
        suffix = f" ({hint})" if hint else ""
        checklist_lines.append(f"- [ ] Approve {checkpoint}{suffix}")
    checklist_lines.append("")
    checklist = "\n".join(checklist_lines)

    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        new_text = "\n".join([lines[0], "", checklist] + lines[1:]).rstrip() + "\n"
    else:
        new_text = (checklist + "\n" + text).rstrip() + "\n"
    atomic_write_text(decisions_path, new_text)


def set_decisions_approval(decisions_path: Path, checkpoint: str, *, approved: bool) -> None:
    checkpoint = checkpoint.strip()
    if not checkpoint:
        raise ValueError("checkpoint must be non-empty")

    ensure_decisions_approval_checklist(decisions_path)
    text = decisions_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    pattern = re.compile(rf"^\s*-\s*\[\s*[xX ]\s*\]\s*(?:Approve\s*)?{re.escape(checkpoint)}\b")
    updated = False
    for idx, line in enumerate(lines):
        if pattern.search(line):
            lines[idx] = re.sub(
                r"\[\s*[xX ]\s*\]",
                "[x]" if approved else "[ ]",
                line,
                count=1,
            )
            updated = True
            break

    if not updated:
        insert_at = None
        for idx, line in enumerate(lines):
            if line.strip().startswith("## Approvals"):
                insert_at = idx + 1
                break
        if insert_at is None:
            lines.append("")
            lines.append("## Approvals (check to unblock)")
            insert_at = len(lines)
        lines.insert(insert_at, f"- [{'x' if approved else ' '}] Approve {checkpoint}")

    atomic_write_text(decisions_path, "\n".join(lines).rstrip() + "\n")


def _human_checkpoints_from_units(workspace: Path) -> list[str]:
    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        return []

    try:
        table = UnitsTable.load(units_path)
    except Exception:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for row in table.rows:
        owner = (row.get("owner") or "").strip().upper()
        if owner != "HUMAN":
            continue
        checkpoint = (row.get("checkpoint") or "").strip()
        if checkpoint and checkpoint not in seen:
            seen.add(checkpoint)
            out.append(checkpoint)
    return out


def _approval_hint(checkpoint: str) -> str:
    hints = {
        "C0": "kickoff: scope/sources/time window/constraints",
        "C1": "retrieval + core set",
        "C2": "scope + outline",
        "C3": "evidence ready",
        "C4": "citations verified",
        "C5": "allow prose writing",
    }
    return hints.get(checkpoint, "")


def upsert_checkpoint_block(decisions_path: Path, checkpoint: str, markdown_block: str) -> None:
    begin = f"<!-- BEGIN CHECKPOINT:{checkpoint} -->"
    end = f"<!-- END CHECKPOINT:{checkpoint} -->"
    block = "\n".join([begin, markdown_block.rstrip(), end, ""]).rstrip() + "\n"

    if decisions_path.exists():
        text = decisions_path.read_text(encoding="utf-8")
    else:
        text = "# Decisions log\n\n"

    ensure_decisions_approval_checklist(decisions_path)
    text = decisions_path.read_text(encoding="utf-8")

    pattern = re.compile(
        rf"{re.escape(begin)}.*?{re.escape(end)}\n?",
        flags=re.DOTALL,
    )
    if pattern.search(text):
        new_text = pattern.sub(block, text)
    else:
        new_text = text.rstrip() + "\n\n" + block
    atomic_write_text(decisions_path, new_text)


def seed_queries_from_topic(queries_path: Path, topic: str) -> None:
    topic = topic.strip()
    if not topic:
        return

    if queries_path.exists():
        lines = queries_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# Queries",
            "",
            "## Primary query",
            "- keywords:",
            "  - \"\"",
            "- exclude:",
            "  - \"\"",
            "- max_results: \"\"",
            "- core_size: \"\"",
            "- time window:",
            "  - from: \"\"",
            "  - to: \"\"",
            "",
            "## Notes",
            "-",
        ]

    def _has_nonempty_values(token: str) -> bool:
        in_block = False
        for raw in lines:
            stripped = raw.strip()
            if stripped.startswith(f"- {token}:"):
                in_block = True
                continue
            if not in_block:
                continue
            if raw.startswith("  - "):
                value = stripped[2:].strip().strip('"').strip("'")
                if value:
                    return True
                continue
            if stripped.startswith("- "):
                break
        return False

    def _has_nonempty_scalar(token: str) -> bool:
        for raw in lines:
            stripped = raw.strip()
            if not stripped.startswith(f"- {token}:"):
                continue
            value = stripped.split(":", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
            return bool(value)
        return False

    def _has_nonempty_time_field(field: str) -> bool:
        # Looks for lines like: '  - from: "2022"'
        for raw in lines:
            stripped = raw.strip()
            if not stripped.startswith(f"- {field}:"):
                continue
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            return bool(value)
        return False

    has_keywords = _has_nonempty_values("keywords")
    has_excludes = _has_nonempty_values("exclude")
    has_time_from = _has_nonempty_time_field("from")
    has_time_to = _has_nonempty_time_field("to")
    workspace = queries_path.parent
    profile = pipeline_profile(workspace)
    query_defaults = pipeline_query_defaults(workspace)
    allowed_fields = pipeline_overridable_query_fields(workspace)
    if not query_defaults and not allowed_fields:
        return

    evidence_mode = requested_evidence_mode(topic)
    if evidence_mode and "evidence_mode" in allowed_fields:
        query_defaults = {**query_defaults, "evidence_mode": evidence_mode}

    raw_tlow = topic.lower()
    use_bounded_report_profile = profile == "arxiv-survey" and bounded_survey_profile_requested(topic)
    if use_bounded_report_profile:
        query_defaults = {
            **query_defaults,
            "max_results": 320,
            "core_size": 48,
            "per_subsection": 6,
            "global_citation_min_subsections": 3,
            "draft_profile": "course_paper",
            "citation_target": "hard",
        }

    topic_for_queries = _sanitize_topic_for_query_seed(topic)
    keyword_suggestions = _query_seed_variants(topic_for_queries)
    tlow = topic_for_queries.lower()
    is_agent = any(t in tlow for t in ("agent", "agents", "agentic"))
    is_llm_agent = is_agent and any(
        t in tlow for t in ("llm", "language model", "large language model", "gpt")
    )
    is_embodied = any(
        t in tlow
        for t in (
            "embodied ai",
            "embodied intelligence",
            "embodied agent",
            "embodied robotics",
            "robot foundation model",
            "robot learning",
            "robot manipulation",
            "vision-language-action",
            "vla",
            "generalist robot",
        )
    )
    is_text_to_image = any(t in tlow for t in ("text-to-image", "text to image", "t2i"))
    is_text_to_video = any(t in tlow for t in ("text-to-video", "text to video", "t2v"))
    is_diffusion = "diffusion" in tlow
    is_generative = is_text_to_image or is_text_to_video or is_diffusion or ("image generation" in tlow) or ("generative" in tlow)

    if is_llm_agent:
        keyword_suggestions.extend(
            [
                "LLM agent",
                "language model agent",
                "tool use",
                "function calling",
                "tool-using agent",
                "planning",
                "memory",
                "multi-agent",
                "benchmark",
                "safety",
            ]
        )
    exclude_suggestions: list[str] = []
    if is_agent:
        exclude_suggestions.append("agent-based modeling")
        exclude_suggestions.extend(["react hooks", "perovskite", "banach", "coxeter"])

    if is_embodied:
        adaptation_focus = any(
            term in tlow
            for term in (
                "adaptation",
                "distribution shift",
                "domain shift",
                "out-of-distribution",
                "test-time",
                "continual learning",
                "sim-to-real",
            )
        )
        if adaptation_focus:
            if profile == "research-brief":
                keyword_suggestions.append(
                    "(all:robot OR all:robotic OR all:embodied) AND "
                    "(all:adaptation OR all:shift OR all:sim-to-real OR "
                    "all:continual OR all:out-of-distribution)"
                )
            keyword_suggestions.extend(
                [
                    "embodied agent adaptation",
                    "robot policy adaptation",
                    "robot learning distribution shift",
                    "robot domain adaptation",
                    "robot test-time adaptation",
                    "sim-to-real policy adaptation",
                    "continual robot learning",
                    "out-of-distribution robot policy",
                ]
            )
        else:
            keyword_suggestions.extend(
                [
                    "embodied AI survey",
                    "embodied AI review",
                    "embodied intelligence survey",
                    "embodied agent survey",
                    "robot foundation model survey",
                    "robot learning survey",
                    "robot manipulation survey",
                    "embodied robotics survey",
                    "vision-language-action survey",
                    "vision-language-action model",
                    "robot foundation model",
                    "generalist robot policy",
                    "world model robot",
                ]
            )

    stripped_output_terms = topic_for_queries.lower().strip() != raw_tlow.strip()
    if stripped_output_terms and any(t in raw_tlow for t in ("latex", "pdf", "markdown", "typesetting")):
        exclude_suggestions.extend(["latex", "pdf", "typesetting", "document layout"])

    if is_generative:
        keyword_suggestions.extend(
            [
                "text-to-image generation",
                "text-guided image generation",
                "diffusion model",
                "denoising diffusion probabilistic model",
                "latent diffusion",
                "stable diffusion",
                "classifier-free guidance",
                "diffusion transformer",
                "DiT",
                "masked generative transformer",
                "MaskGIT",
                "autoregressive image generation",
                "VQGAN",
                "VQ-VAE",
                "ControlNet",
                "DreamBooth",
                "textual inversion",
                "LoRA fine-tuning",
            ]
        )

    default_max_results = query_defaults.get("max_results")
    max_results_suggestion = str(default_max_results) if str(default_max_results or "").strip() else (
        1800 if profile == "arxiv-survey" else (800 if (is_agent or is_generative or is_embodied) else 300)
    )
    time_from_suggestion = (
        "2018" if is_embodied
        else ("2022" if (is_agent and ("llm" in tlow or "language model" in tlow)) else ("2020" if is_generative else ""))
    )
    core_size_suggestion = str(query_defaults.get("core_size") or "").strip() or ("300" if profile == "arxiv-survey" else "")

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("- keywords:") and not has_keywords and "keywords" in allowed_fields:
            out.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            for kw in _dedupe_preserve_order(keyword_suggestions)[:14]:
                out.append(f"  - \"{kw}\"")
            continue

        if stripped.startswith("- exclude:") and not has_excludes and "exclude" in allowed_fields:
            out.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            for ex in _dedupe_preserve_order(exclude_suggestions)[:10]:
                out.append(f"  - \"{ex}\"")
            continue

        materialized = False
        for key, value in query_defaults.items():
            normalized_key = str(key or "").strip().lower().replace(" ", "_").replace("-", "_")
            if not normalized_key or not stripped.startswith(f"- {normalized_key}:"):
                continue
            if normalized_key not in allowed_fields:
                continue
            if _has_nonempty_scalar(normalized_key):
                break
            rendered = _render_query_scalar(value)
            if rendered is not None:
                out.append(f'- {normalized_key}: "{rendered}"')
                i += 1
                materialized = True
            break
        if materialized:
            continue

        if (
            stripped.startswith("- max_results:")
            and "max_results" in allowed_fields
            and not _has_nonempty_scalar("max_results")
            and max_results_suggestion
        ):
            out.append(f"- max_results: \"{max_results_suggestion}\"")
            i += 1
            continue

        if (
            stripped.startswith("- core_size:")
            and "core_size" in allowed_fields
            and not _has_nonempty_scalar("core_size")
            and core_size_suggestion
        ):
            out.append(f"- core_size: \"{core_size_suggestion}\"")
            i += 1
            continue

        if (
            stripped.startswith("- time window:")
            and {"time_window.from", "time_window.to"}.intersection(allowed_fields)
            and not (has_time_from or has_time_to)
            and time_from_suggestion
        ):
            out.append(line)
            i += 1
            # Skip existing from/to lines if present.
            while i < len(lines) and lines[i].startswith("  -"):
                i += 1
            out.append(f"  - from: \"{time_from_suggestion}\"")
            out.append("  - to: \"\"")
            continue

        out.append(line)
        i += 1

    out = _materialize_missing_query_defaults(out, query_defaults, allowed_fields=allowed_fields)
    atomic_write_text(queries_path, "\n".join(out).rstrip() + "\n")


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def bounded_survey_profile_requested(request: str) -> bool:
    """Return whether a survey request explicitly asks for a bounded report deliverable."""

    text = re.sub(r"\s+", " ", str(request or "").strip())
    if not text:
        return False

    en_request = (
        r"(?i)(?:\b(?:please\s+)?(?:write|draft|prepare|create|produce|deliver|compile|develop)\b"
        r"|\b(?:need|want)\s+(?:an?\s+|the\s+)?)"
    )
    zh_request = r"(?:写|撰写|生成|准备|制作|完成|交付)"
    strong_requested = bool(
        re.search(rf"{en_request}[^.!?\n]{{0,140}}{_STRONG_BOUNDED_SURVEY_DELIVERABLE_EN}", text)
        or re.search(rf"{zh_request}[^。！？\n]{{0,140}}{_STRONG_BOUNDED_SURVEY_DELIVERABLE_ZH}", text)
        or re.match(
            rf"(?i)^\s*(?:an?\s+|the\s+)?{_STRONG_BOUNDED_SURVEY_DELIVERABLE_EN}\s+(?:on|about|covering)\b",
            text,
        )
        or re.search(
            rf"(?i)\b(?:as|into)\s+(?:an?\s+|the\s+)?{_STRONG_BOUNDED_SURVEY_DELIVERABLE_EN}\s*[.!]?$",
            text,
        )
        or re.match(rf"^\s*{_STRONG_BOUNDED_SURVEY_DELIVERABLE_ZH}(?:关于|：|:)", text)
    )
    if strong_requested:
        return True

    generic_requested = bool(
        re.search(rf"{en_request}[^.!?\n]{{0,140}}{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_EN}", text)
        or re.search(rf"{zh_request}[^。！？\n]{{0,140}}{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_ZH}", text)
        or re.match(
            rf"(?i)^\s*(?:an?\s+|the\s+)?{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_EN}\s+(?:on|about|covering)\b",
            text,
        )
        or re.search(
            rf"(?i)\b(?:as|into)\s+(?:an?\s+|the\s+)?{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_EN}\s*[.!]?$",
            text,
        )
        or re.match(rf"^\s*{_GENERIC_BOUNDED_SURVEY_DELIVERABLE_ZH}(?:关于|：|:)", text)
    )
    return generic_requested and not _NON_LITERATURE_REPORT_CONTEXT_RE.search(text)


def _sanitize_topic_for_query_seed(topic: str) -> str:
    text = str(topic or "").strip()
    if not text:
        return ""

    brief_prefix = re.compile(
        r"(?i)^\s*(?:please\s+)?(?:produce|write|draft|prepare|create)\s+"
        r"(?:an?\s+)?(?:(?:compact|traceable|concise|high-signal|one-page)\s*,?\s*)*"
        r"(?:research\s+)?(?:brief|briefing|snapshot|overview)\s+(?:on|about)\s+"
    )
    if brief_prefix.match(text):
        text = brief_prefix.sub("", text)
        text = re.sub(
            r"(?i),\s+with\s+(?:an?\s+)?(?:bounded|explicit|clear|concise|short)\b.*$",
            "",
            text,
        )

    patterns = [
        r"(?i)^\s*(?:please\s+)?(?:use|run)\s+(?:the\s+)?arxiv[-_\s]survey(?:[-_\s]latex)?(?:\s+workflow)?\s+(?:to\s+)?",
        r"^\s*(?:请)?使用\s*arxiv[-_\s]survey(?:[-_\s]latex)?(?:\s*工作流)?(?:来|去)?\s*",
        rf"(?i)^\s*(?:please\s+)?(?:write|draft|prepare|create)\s+(?:an?\s+)?(?:(?:\d+\s*(?:-|–|to)\s*\d+|\d+)\s*(?:-\s*)?pages?\s+)?(?:compact\s+)?{_BOUNDED_SURVEY_DELIVERABLE_EN}\s+(?:on|about)\s+",
        r"[,，;；]?\s*(?:并|且)?(?:最终|最后)?(?:输出|生成|交付)(?:一份)?\s*(?:PDF|LaTeX|Markdown)(?:文件|版本)?\s*$",
        r"(?i)[,;]?\s*as\s+(?:an?\s+)?(?:final\s+)?(?:latex(?:\s*/\s*pdf)?|pdf|markdown)(?:\s+(?:output|deliverable|version))?\s*\.?$",
        r"(?i)[,;]?\s*with\s+(?:a\s+)?(?:final\s+)?(?:latex(?:\s*/\s*pdf)?|pdf|markdown)(?:\s+(?:output|deliverable|version))?\s*\.?$",
        r"(?i)[,;]?\s*(?:and\s+)?(?:produce|return|deliver|include|generate)\s+(?:a\s+)?(?:final\s+)?(?:latex(?:\s*/\s*pdf)?|pdf|markdown)(?:\s+(?:output|deliverable|version))?\s*\.?$",
        r"(?i)[,，;；]?\s*(?:target(?:ing)?\s+)?(?:\d+\s*(?:-|–|—|to|到|至)\s*\d+|\d+)\s*(?:-\s*)?(?:pages?|页)(?:\s+(?:long|in\s+length))?\s*\.?$",
    ]
    if bounded_survey_profile_requested(topic):
        patterns.extend(
            [
                r"^\s*请?(?:帮我)?(?:写|撰写|生成|准备|制作|完成)(?:一篇|一份)?(?:\s*\d+\s*(?:-|—|–|到|至)\s*\d+\s*页)?\s*(?:的|、?关于)?",
                rf"(?i)\s+(?:as\s+|into\s+)?(?:an?\s+|the\s+)?{_BOUNDED_SURVEY_DELIVERABLE_EN}\s*[.!]?$",
                rf"(?:的)?{_BOUNDED_SURVEY_DELIVERABLE_ZH}\s*$",
            ]
        )
    if requested_delivery_formats(topic):
        patterns.extend(
            [
                r"(?i)\bwith\s+latex\s*/\s*pdf\s+output\b",
                r"(?i)\bwith\s+latex\s+output\b",
                r"(?i)\bwith\s+pdf\s+output\b",
                r"(?i)\bwith\s+markdown\s+output\b",
                r"(?i)\blatex\s*/\s*pdf\s+output\b",
                r"(?i)\bpdf\s+output\b",
                r"(?i)\blatex\s+output\b",
                r"(?i)\bmarkdown\s+output\b",
                r"(?i)\bfor\s+latex\s*/\s*pdf\b",
            ]
        )
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return text or topic


def research_subject_from_request(topic: str) -> str:
    """Return a reader-facing research subject, not a delivery instruction."""

    cleaned = _sanitize_topic_for_query_seed(topic).strip().rstrip(".")
    question = re.match(
        r"(?i)^how\s+(.+?)\s+(?:should|can|could|may|might)\s+be\s+"
        r"(evaluated|assessed|measured|compared|designed)\??$",
        cleaned,
    )
    if not question:
        return cleaned

    subject = re.sub(r"\s+", " ", question.group(1)).strip(" ,;:-")
    noun = {
        "evaluated": "evaluation",
        "assessed": "assessment",
        "measured": "measurement",
        "compared": "comparison",
        "designed": "design",
    }[question.group(2).lower()]
    return f"the {noun} of {subject}"


def _title_case_generated_subject(text: str) -> str:
    small_words = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "via"}
    tokens = re.split(r"(\s+)", str(text or "").strip())
    word_index = 0
    out: list[str] = []
    for token in tokens:
        if not token or token.isspace():
            out.append(token)
            continue
        parts = token.split("-")
        rendered: list[str] = []
        for part_index, part in enumerate(parts):
            bare = re.sub(r"[^A-Za-z0-9]", "", part)
            low = part.lower()
            if bare.isupper() and len(bare) > 1:
                rendered.append(part)
            elif word_index > 0 and part_index == 0 and low in small_words:
                rendered.append(low)
            else:
                rendered.append(part[:1].upper() + part[1:])
        out.append("-".join(rendered))
        word_index += 1
    return "".join(out)


def research_title_from_request(topic: str) -> str:
    """Return a concise paper title derived from a natural-language request."""

    cleaned = _sanitize_topic_for_query_seed(topic).strip().rstrip(".")
    question = re.match(
        r"(?i)^how\s+(.+?)\s+(?:should|can|could|may|might)\s+be\s+"
        r"(evaluated|assessed|measured|compared|designed)\??$",
        cleaned,
    )
    if not question:
        return cleaned

    verb = {
        "evaluated": "Evaluating",
        "assessed": "Assessing",
        "measured": "Measuring",
        "compared": "Comparing",
        "designed": "Designing",
    }[question.group(2).lower()]
    subject = _title_case_generated_subject(question.group(1))
    return f"{verb} {subject}".strip()


def reader_request_leakage(text: str) -> list[str]:
    """Describe delivery-request fragments that must not appear in a final paper."""

    checks = [
        (
            "imperative paper request",
            r"(?i)\b(?:please\s+)?(?:write|draft|prepare|create)\s+(?:an?\s+)?"
            r"(?:(?:\d+\s*(?:-|–|to)\s*\d+|\d+)\s*(?:-\s*)?pages?\s+)?"
            rf"(?:compact\s+)?{_BOUNDED_SURVEY_DELIVERABLE_EN}\s+(?:on|about)\b",
        ),
        (
            "delivery-format request",
            r"(?i)\bwith\s+(?:a\s+)?(?:final\s+)?(?:latex(?:\s*/\s*pdf)?|pdf|markdown)"
            r"(?:\s+(?:output|deliverable|version))?\b",
        ),
        (
            "Chinese paper request",
            r"(?:请?(?:帮我)?(?:写|生成|准备)(?:一篇)?(?:\s*\d+\s*(?:-|—|–|到|至)\s*\d+\s*页)?(?:关于)?)"
            rf"[^\n。]{{0,180}}{_BOUNDED_SURVEY_DELIVERABLE_ZH}",
        ),
    ]
    return [label for label, pattern in checks if re.search(pattern, text or "")]


def goal_constraints_from_request(request: str) -> dict[str, Any]:
    """Extract the small set of delivery constraints the harness can enforce."""

    text = re.sub(r"\s+", " ", str(request or "").strip())
    constraints: dict[str, Any] = {}
    page_match = re.search(
        r"(?i)\b(\d{1,3})\s*(?:-|–|—|to)\s*(\d{1,3})\s*(?:-\s*)?pages?\b",
        text,
    ) or re.search(r"(\d{1,3})\s*(?:-|–|—|到|至)\s*(\d{1,3})\s*页", text)
    if page_match:
        low, high = int(page_match.group(1)), int(page_match.group(2))
        if low > high:
            low, high = high, low
        if 1 <= low <= high <= 500:
            constraints["page_range"] = {
                "min": low,
                "max": high,
                "scope": "compiled_pdf_total",
            }

    formats = requested_delivery_formats(text)
    if formats:
        constraints["deliverable_formats"] = formats
    evidence_mode = requested_evidence_mode(text)
    if evidence_mode:
        constraints["evidence_mode"] = evidence_mode
    return constraints


def requested_evidence_mode(request: str) -> str:
    """Return an explicitly requested research-evidence mode, if present."""

    text = re.sub(r"\s+", " ", str(request or "").strip())
    if not text:
        return ""
    if re.search(r"(?i)\bevidence[_ -]?mode\s*[:=]\s*fulltext\b", text):
        return "fulltext"
    if re.search(
        r"(?i)\b(?:use|using|require|requiring|with|ground|grounded|grounding)\b"
        r"[^.!?\n]{0,40}\bfull[- ]?text\b(?:\s+(?:evidence|sources?|access|grounding))?",
        text,
    ) or re.search(r"(?:使用|要求|基于|采用|需要)[^。！？\n]{0,24}(?:全文证据|论文全文|全文来源|逐篇全文)", text):
        return "fulltext"
    if re.search(r"(?i)\bevidence[_ -]?mode\s*[:=]\s*abstract\b", text):
        return "abstract"
    if re.search(
        r"(?i)\b(?:use|using|with|limit(?:ed)?\s+to)\b[^.!?\n]{0,32}\babstract[- ]?(?:only|backed)?\s+evidence\b",
        text,
    ) or re.search(r"(?:仅使用|基于|采用)[^。！？\n]{0,20}(?:摘要证据|论文摘要)", text):
        return "abstract"
    return ""


def requested_delivery_formats(request: str) -> list[str]:
    """Return output formats requested as deliverables, not formats named as subjects."""

    text = re.sub(r"\s+", " ", str(request or "").strip())
    if not text:
        return []

    formats: list[str] = []
    for name, token in (
        ("pdf", r"PDF"),
        ("latex", r"(?:LaTeX|TeX)"),
        ("markdown", r"(?:Markdown|\.md)"),
    ):
        patterns = (
            rf"(?i)\b(?:produce|generate|return|deliver|include|create|render|export|compile|provide|save)\b[^.!?\n]{{0,40}}\b{token}\b",
            rf"(?i)\b(?:with|as|in)\s+(?:an?\s+|the\s+)?(?:final\s+|compiled\s+)?{token}(?:\s+(?:output|deliverable|version|file|format))?(?=\s*(?:[,.;]|$|\band\b))",
            rf"(?i)\b{token}\s+(?:deliverable|version|file|format)\b",
            rf"(?i)(?:生成|输出|交付|导出|返回|编译|提供|保存)[^。！？\n]{{0,20}}{token}",
            rf"(?i){token}(?:文件|版本|格式|交付物)",
        )
        if any(re.search(pattern, text) for pattern in patterns):
            formats.append(name)
    return formats


def load_workspace_goal_constraints(workspace: Path) -> dict[str, Any]:
    """Load structured Goal constraints, with GOAL.md as a legacy fallback."""

    goal_path = Path(workspace) / ".harness" / "goal.json"
    if goal_path.exists():
        try:
            payload = json.loads(goal_path.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("constraints"), dict):
            return dict(payload["constraints"])

    markdown_path = Path(workspace) / "GOAL.md"
    if not markdown_path.exists():
        return {}
    request = ""
    for raw in markdown_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            request = line
            break
    return goal_constraints_from_request(request)


def _query_seed_variants(topic: str) -> list[str]:
    """Convert a research-question-shaped topic into reusable retrieval phrases."""
    text = str(topic or "").strip()
    if not text:
        return []

    variants = [text]
    question = re.match(
        r"(?i)^how\s+(.+?)\s+(?:should|can|could|may|might)\s+be\s+"
        r"(evaluated|assessed|measured|compared|designed)\??$",
        text,
    )
    if question:
        subject = re.sub(r"\s+", " ", question.group(1)).strip(" ,;:-")
        subject_base = re.sub(
            r"(?i)\s+(?:systems?|methods?|approaches?|models?|frameworks?)$",
            "",
            subject,
        ).strip()
        action = {
            "evaluated": "evaluation",
            "assessed": "assessment",
            "measured": "measurement",
            "compared": "comparison",
            "designed": "design",
        }[question.group(2).lower()]
        variants.extend([subject_base or subject, f"{subject_base or subject} {action}"])

    return _dedupe_preserve_order(variants)


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default: this file) looking for AGENTS.md."""
    candidate = (start or Path(__file__)).resolve()
    for _ in range(10):
        if (candidate / "AGENTS.md").exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise FileNotFoundError("Could not find repo root (AGENTS.md marker)")


def _normalize_pipeline_lock_value(value: str) -> str:
    return str(value or "").strip()


def resolve_pipeline_spec_path(*, repo_root: Path, pipeline_value: str) -> Path | None:
    value = _normalize_pipeline_lock_value(pipeline_value)
    if not value:
        return None

    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve()

    rel_candidate = repo_root / value
    if rel_candidate.exists():
        return rel_candidate.resolve()

    filename = Path(value).name
    if filename:
        direct = repo_root / "pipelines" / filename
        if direct.exists():
            return direct.resolve()

    stem = filename
    if stem.endswith(".pipeline.md"):
        stem = stem[: -len(".pipeline.md")]
    if stem:
        direct = repo_root / "pipelines" / f"{stem}.pipeline.md"
        if direct.exists():
            return direct.resolve()

    return None


def load_workspace_pipeline_spec(workspace: Path):
    from tooling.pipeline_spec import PipelineSpec

    try:
        # Pipeline contracts belong to the checkout executing the run. A Workspace
        # may live outside that checkout or below another directory with AGENTS.md.
        repo_root = find_repo_root(Path(__file__).resolve())
    except FileNotFoundError:
        return None

    lock_path = workspace / "PIPELINE.lock.md"
    if not lock_path.exists():
        return None

    pipeline_name = ""
    try:
        for raw in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("pipeline:"):
                pipeline_name = line.split(":", 1)[1].strip()
                break
    except Exception:
        return None

    if not pipeline_name:
        return None

    spec_path: Path | None = None
    harness_lock_path = workspace / ".harness" / "harness.lock.json"
    if harness_lock_path.exists():
        try:
            harness_lock = json.loads(harness_lock_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if isinstance(harness_lock, dict) and harness_lock.get("schema") == "harness-lock.v2":
            pipeline_lock = harness_lock.get("pipeline")
            if not isinstance(pipeline_lock, dict):
                return None
            locked_source_value = str(pipeline_lock.get("path") or "").strip()
            declared_source = resolve_pipeline_spec_path(
                repo_root=repo_root,
                pipeline_value=pipeline_name,
            )
            locked_source = resolve_pipeline_spec_path(
                repo_root=repo_root,
                pipeline_value=locked_source_value,
            )
            if (
                not locked_source_value
                or declared_source is None
                or locked_source is None
                or declared_source != locked_source
            ):
                return None
            snapshot_value = str(pipeline_lock.get("snapshot_path") or "").strip()
            expected_sha = str(pipeline_lock.get("snapshot_sha256") or "").strip()
            if not snapshot_value or not expected_sha:
                return None
            candidate = Path(snapshot_value)
            if candidate.is_absolute():
                return None
            workspace_root = workspace.resolve()
            snapshot_path = (workspace_root / candidate).resolve()
            if not snapshot_path.is_relative_to(workspace_root) or not snapshot_path.is_file():
                return None
            actual_sha = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                return None
            spec_path = snapshot_path

    if spec_path is None:
        spec_path = resolve_pipeline_spec_path(repo_root=repo_root, pipeline_value=pipeline_name)
    if spec_path is None:
        return None

    try:
        return PipelineSpec.load(spec_path)
    except Exception:
        return None


def pipeline_query_defaults(workspace: Path) -> dict[str, Any]:
    spec = load_workspace_pipeline_spec(workspace)
    return dict(spec.query_defaults) if spec is not None else {}


def pipeline_quality_contract(workspace: Path) -> dict[str, Any]:
    spec = load_workspace_pipeline_spec(workspace)
    return dict(spec.quality_contract) if spec is not None else {}


def pipeline_quality_contract_value(workspace: Path, *keys: str, default: Any = None) -> Any:
    current: Any = pipeline_quality_contract(workspace)
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(str(key))
        if current is None:
            return default
    return current


def pipeline_query_default(workspace: Path, key: str, default: Any = None) -> Any:
    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return default
    return spec.query_default(key, default)


def _normalize_query_key(key: str) -> str:
    return str(key or "").strip().lower().replace(" ", "_").replace("-", "_")


def workspace_query_scalar(workspace: Path, key: str, default: Any = None) -> Any:
    """Read a materialized scalar from `queries.md`, falling back to the pipeline contract."""
    normalized = _normalize_query_key(key)
    fallback = pipeline_query_default(workspace, normalized, default)
    path = workspace / "queries.md"
    if not path.exists():
        return fallback
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = raw.strip()
            if not stripped.startswith("- ") or ":" not in stripped:
                continue
            raw_key, raw_value = stripped[2:].split(":", 1)
            if _normalize_query_key(raw_key) != normalized:
                continue
            value = raw_value.split("#", 1)[0].strip().strip('"').strip("'")
            return value if value else fallback
    except Exception:
        return fallback
    return fallback


def pipeline_overridable_query_fields(workspace: Path) -> set[str]:
    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return set()
    return set(spec.overridable_query_fields)


def pipeline_profile(workspace: Path) -> str:
    """Return the pipeline profile for a workspace.

    Reads PIPELINE.lock.md to get the pipeline name, then loads the
    pipeline spec file and reads its ``profile`` frontmatter field.
    Falls back to ``"default"`` if anything is missing.
    """
    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return "default"
    return str(spec.profile or "default").strip() or "default"


def latest_outline_state(workspace: Path) -> dict[str, Any]:
    path = Path(workspace).resolve() / "outline" / "outline_state.jsonl"
    records = [rec for rec in read_jsonl(path) if isinstance(rec, dict)]
    return dict(records[-1]) if records else {}


def _materialize_missing_query_defaults(lines: list[str], query_defaults: dict[str, Any], *, allowed_fields: set[str] | None = None) -> list[str]:
    if not query_defaults:
        return lines

    existing_keys: set[str] = set()
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key = stripped[2:].split(":", 1)[0].strip().lower().replace(" ", "_").replace("-", "_")
        if key:
            existing_keys.add(key)

    additions: list[str] = []
    for key, value in query_defaults.items():
        norm_key = str(key or "").strip().lower().replace(" ", "_").replace("-", "_")
        if not norm_key or norm_key in existing_keys:
            continue
        if allowed_fields is not None and norm_key not in allowed_fields:
            continue
        rendered = _render_query_scalar(value)
        if rendered is None:
            continue
        additions.append(f'- {norm_key}: "{rendered}"')

    if not additions:
        return lines

    out = list(lines)
    if out and out[-1].strip():
        out.append("")
    out.extend(additions)
    return out


def _render_query_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None
