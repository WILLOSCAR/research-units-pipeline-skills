from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


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

    from tooling.review_artifacts import load_candidate_records, read_csv_rows, stable_paper_id, write_csv_rows
    from tooling.review_protocol import parse_protocol

    workspace = Path(args.workspace).resolve()
    screening_path = workspace / "papers" / "screening_log.csv"
    protocol_path = workspace / "output" / "PROTOCOL.md"
    if not screening_path.exists() or not protocol_path.exists():
        raise SystemExit("extraction-form requires `papers/screening_log.csv` and `output/PROTOCOL.md`.")

    screening_rows = read_csv_rows(screening_path)
    included = [row for row in screening_rows if str(row.get("decision") or "").strip().lower() == "include"]
    protocol = parse_protocol(protocol_path.read_text(encoding="utf-8", errors="ignore"))
    schema_fields = [field["field"] for field in protocol.get("extraction_fields") or []]
    candidate_records = load_candidate_records(workspace)
    by_id: dict[str, dict] = {}
    by_title_url: dict[tuple[str, str], dict] = {}
    for index, rec in enumerate(candidate_records, start=1):
        by_id[stable_paper_id(rec, index=index)] = rec
        by_title_url[(str(rec.get("title") or "").strip(), str(rec.get("url") or "").strip())] = rec

    rows = []
    for idx, row in enumerate(included, start=1):
        rec = by_id.get(str(row.get("paper_id") or "").strip()) or by_title_url.get(
            (str(row.get("title") or "").strip(), str(row.get("url") or "").strip()),
            {},
        )
        out = {
            "paper_id": row.get("paper_id") or stable_paper_id(rec, index=idx),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "url": row.get("url", ""),
            "notes": "Deterministic extraction; enrich manually for deeper synthesis." if not rec else "",
        }
        for field in schema_fields:
            out[field] = _extract_field(field, rec)
        rows.append(out)

    fieldnames = ["paper_id", "title", "year", "url", *schema_fields, "notes"]
    write_csv_rows(workspace / "papers" / "extraction_table.csv", rows, fieldnames=fieldnames)
    return 0


def _extract_field(field: str, record: dict) -> str:
    direct = str(record.get(field) or "").strip()
    if direct:
        return direct

    title = str(record.get("title") or "").strip()
    abstract = str(record.get("abstract") or "").strip()
    text = f"{title}. {abstract}".strip()
    unavailable = "not reported in available metadata"

    if field == "population_or_setting":
        for key in ("population", "setting", "dataset", "environment"):
            value = str(record.get(key) or "").strip()
            if value:
                return value
        return unavailable
    if field == "task":
        return str(record.get("study_focus") or record.get("domain") or "").strip() or unavailable
    if field == "metric":
        metric_match = re.search(
            r"(?i)\b(accuracy|f1(?: score)?|precision|recall|success rate|auc|bleu|rouge|latency|error rate|agreement)\b",
            text,
        )
        return metric_match.group(1) if metric_match else unavailable
    if field == "study_type":
        low = text.lower()
        if "randomized" in low or "controlled trial" in low:
            return "controlled study"
        if "user study" in low or "participants" in low:
            return "user study"
        if "benchmark" in low or "evaluation" in low or "experiment" in low:
            return "empirical benchmark evaluation"
        if "survey" in low or "review" in low:
            return "review"
        return "not classifiable from available metadata"
    if field == "result_summary":
        sentences = re.split(r"(?<=[.!?])\s+", abstract)
        result_signal = re.compile(
            r"(?i)\b(report(?:s|ed)?|find(?:s|ings)?|show(?:s|ed)?|improv(?:e|es|ed|ement)|"
            r"increas(?:e|es|ed)|decreas(?:e|es|ed)|reduc(?:e|es|ed|tion)|outperform(?:s|ed)?|"
            r"no significant|significant(?:ly)?|associated with)\b"
        )
        return next((sentence.strip() for sentence in sentences if result_signal.search(sentence)), unavailable)
    if field == "evidence_pointer":
        return str(record.get("url") or record.get("source_path") or "").strip() or unavailable
    return unavailable


if __name__ == "__main__":
    raise SystemExit(main())
