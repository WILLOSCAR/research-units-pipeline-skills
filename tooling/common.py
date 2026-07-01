from __future__ import annotations

import csv
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
    has_max_results = _has_nonempty_scalar("max_results")
    has_core_size = _has_nonempty_scalar("core_size")

    workspace = queries_path.parent
    profile = pipeline_profile(workspace)
    query_defaults = pipeline_query_defaults(workspace)

    raw_tlow = topic.lower()
    topic_for_queries = _sanitize_topic_for_query_seed(topic)
    keyword_suggestions = [topic_for_queries]
    tlow = topic_for_queries.lower()
    is_agent = any(t in tlow for t in ("agent", "agents", "agentic"))
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

    if is_agent:
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

        if stripped.startswith("- keywords:") and not has_keywords:
            out.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            for kw in _dedupe_preserve_order(keyword_suggestions)[:14]:
                out.append(f"  - \"{kw}\"")
            continue

        if stripped.startswith("- exclude:") and not has_excludes:
            out.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            for ex in _dedupe_preserve_order(exclude_suggestions)[:10]:
                out.append(f"  - \"{ex}\"")
            continue

        if stripped.startswith("- max_results:") and not has_max_results and max_results_suggestion:
            out.append(f"- max_results: \"{max_results_suggestion}\"")
            i += 1
            continue

        if stripped.startswith("- core_size:") and not has_core_size and core_size_suggestion:
            out.append(f"- core_size: \"{core_size_suggestion}\"")
            i += 1
            continue

        if stripped.startswith("- time window:") and not (has_time_from or has_time_to) and time_from_suggestion:
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

    out = _materialize_missing_query_defaults(out, query_defaults, allowed_fields=pipeline_overridable_query_fields(workspace))
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


def _sanitize_topic_for_query_seed(topic: str) -> str:
    text = str(topic or "").strip()
    if not text:
        return ""
    patterns = [
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
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return text or topic


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
        repo_root = find_repo_root(workspace)
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
        if allowed_fields and norm_key not in allowed_fields:
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
