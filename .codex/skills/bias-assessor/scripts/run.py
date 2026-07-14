from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROB_COLUMNS = [
    "rob_selection",
    "rob_measurement",
    "rob_confounding",
    "rob_reporting",
    "rob_overall",
    "rob_notes",
]


def _is_reported(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and not text.startswith("not reported") and not text.startswith("not classifiable")


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

    from tooling.review_artifacts import read_csv_rows, write_csv_rows

    workspace = Path(args.workspace).resolve()
    table_path = workspace / "papers" / "extraction_table.csv"
    rows = read_csv_rows(table_path)
    if not rows:
        raise SystemExit("bias-assessor requires a non-empty `papers/extraction_table.csv`.")

    existing = list(rows[0].keys())
    fieldnames = existing[:]
    for col in ROB_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    updated = []
    for row in rows:
        measurement = "low" if _is_reported(row.get("metric")) else "unclear"
        selection = "unclear"
        confounding = "unclear"
        reporting = "low" if str(row.get("title") or "").strip() and str(row.get("url") or "").strip() else "unclear"
        overall = "high" if "high" in {selection, measurement, confounding, reporting} else ("unclear" if "unclear" in {selection, measurement, confounding, reporting} else "low")
        row = dict(row)
        row.update(
            {
                "rob_selection": selection,
                "rob_measurement": measurement,
                "rob_confounding": confounding,
                "rob_reporting": reporting,
                "rob_overall": overall,
                "rob_notes": "Deterministic lightweight RoB pass; verify manually for final use.",
            }
        )
        updated.append(row)

    write_csv_rows(table_path, updated, fieldnames=fieldnames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
