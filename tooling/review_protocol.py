from __future__ import annotations

import re
from typing import Any

from tooling.common import now_iso_seconds


def parse_protocol_extraction_fields(text: str) -> list[dict[str, str]]:
    lines = (text or "").splitlines()
    fields: list[dict[str, str]] = []
    in_table = False
    for raw in lines:
        line = raw.strip()
        if line == "## Extraction Schema":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cols = [col.strip() for col in line.strip("|").split("|")]
        if not cols or cols[0] in {"field", "---"}:
            continue
        if len(cols) < 4:
            continue
        fields.append({"field": cols[0], "definition": cols[1], "allowed_values": cols[2], "notes": cols[3]})
    return fields


def parse_protocol(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "review_questions": [],
        "include_keywords": [],
        "exclude_keywords": [],
        "time_window_from": "",
        "time_window_to": "",
        "inclusion": [],
        "exclusion": [],
        "extraction_fields": [],
    }
    lines = (text or "").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- RQ"):
            data["review_questions"].append(stripped[2:].strip())
        elif stripped.startswith("- include_keywords:"):
            data["include_keywords"] = [item.strip() for item in stripped.split(":", 1)[1].split(";") if item.strip()]
        elif stripped.startswith("- exclude_keywords:"):
            data["exclude_keywords"] = [item.strip() for item in stripped.split(":", 1)[1].split(";") if item.strip()]
        elif stripped.startswith("- time_window_from:"):
            data["time_window_from"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- time_window_to:"):
            data["time_window_to"] = stripped.split(":", 1)[1].strip()
        elif re.match(r"^- I[0-9]+:", stripped):
            code, body = stripped[2:].split(":", 1)
            data["inclusion"].append((code.strip(), body.strip()))
        elif re.match(r"^- E[0-9]+:", stripped):
            code, body = stripped[2:].split(":", 1)
            data["exclusion"].append((code.strip(), body.strip()))
    data["extraction_fields"] = parse_protocol_extraction_fields(text)
    return data


def maybe_parse_queries_md(path) -> tuple[list[str], list[str], str, str]:
    if not path.exists():
        return [], [], "", ""
    keywords: list[str] = []
    exclude: list[str] = []
    time_from = ""
    time_to = ""
    mode = ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if indent == 0 and line.startswith("- keywords:"):
            mode = "keywords"
            continue
        if indent == 0 and line.startswith("- exclude:"):
            mode = "exclude"
            continue
        if indent == 0 and line.startswith("- time_window.from:"):
            time_from = line.split(":", 1)[1].strip()
            mode = ""
            continue
        if indent == 0 and line.startswith("- time_window.to:"):
            time_to = line.split(":", 1)[1].strip()
            mode = ""
            continue
        if indent > 0 and mode in {"keywords", "exclude"} and line.startswith("- "):
            value = line[2:].strip().strip('"').strip("'")
            if value:
                (keywords if mode == "keywords" else exclude).append(value)
            continue
        if indent == 0 and line.startswith("- "):
            mode = ""
    return keywords, exclude, time_from, time_to


def protocol_markdown(
    *,
    goal: str,
    review_questions: list[str],
    include_keywords: list[str],
    exclude_keywords: list[str],
    time_window_from: str,
    time_window_to: str,
    sources: list[str],
    extraction_fields: list[dict[str, str]],
) -> str:
    lines = [
        "# Evidence Review Protocol",
        "",
        "## Scope",
        f"- Goal: {goal or 'Review the target evidence base.'}",
        "",
        "## Review Questions",
    ]
    for idx, rq in enumerate(review_questions, start=1):
        lines.append(f"- RQ{idx}: {rq}")
    lines.extend(["", "## Databases and Sources"])
    for source in sources:
        lines.append(f"- {source}")
    lines.extend(
        [
            "",
            "## Search Terms",
            f"- include_keywords: {'; '.join(include_keywords) if include_keywords else 'review topic'}",
            f"- exclude_keywords: {'; '.join(exclude_keywords) if exclude_keywords else 'none'}",
            "",
            "## Time Window",
            f"- time_window_from: {time_window_from or '2000'}",
            f"- time_window_to: {time_window_to or 'present'}",
            f"- search_date: {now_iso_seconds()}",
            "",
            "## Inclusion Criteria",
            f"- I1: Include studies directly about {goal or 'the review topic'}.",
            "- I2: Include studies that report a concrete method, system, or evidence claim.",
            "",
            "## Exclusion Criteria",
            "- E1: Exclude studies outside the target topic boundary.",
            "- E2: Exclude records without enough title/abstract detail to judge inclusion.",
            "- E3: Exclude duplicates or near-duplicates once deduplicated upstream.",
            "",
            "## Screening Plan",
            "- Title/abstract screening first; full-text checks only if the abstract is borderline.",
            "- Every row in `papers/screening_log.csv` must include `decision`, `reason`, and `reason_codes`.",
            "",
            "## Extraction Schema",
            "| field | definition | allowed_values | notes |",
            "|---|---|---|---|",
        ]
    )
    for field in extraction_fields:
        lines.append(f"| {field['field']} | {field['definition']} | {field['allowed_values']} | {field['notes']} |")
    lines.extend(
        [
            "",
            "## Bias Plan",
            "- Use `low|unclear|high` for each bias domain and keep notes short and specific.",
            "",
            "## Approval",
            "- HUMAN approval required before screening.",
            "",
        ]
    )
    return "\n".join(lines)
