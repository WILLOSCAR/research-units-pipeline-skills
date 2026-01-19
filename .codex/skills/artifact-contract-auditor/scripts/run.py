from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_semicolon_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(";") if x.strip()]


def _strip_optional_marker(relpath: str) -> tuple[str, bool]:
    relpath = (relpath or "").strip()
    if relpath.startswith("?"):
        return relpath[1:].strip(), True
    return relpath, False


def _read_pipeline_path(workspace: Path) -> str:
    lock_path = workspace / "PIPELINE.lock.md"
    if not lock_path.exists():
        return ""
    for raw in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("pipeline:"):
            return line.split(":", 1)[1].strip()
    return ""


def _parse_frontmatter(pipeline_path: Path) -> dict[str, Any]:
    text = pipeline_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    import yaml  # type: ignore

    data = yaml.safe_load("\n".join(lines[1:end])) or {}
    return data if isinstance(data, dict) else {}


def _load_units(units_path: Path) -> list[dict[str, str]]:
    with units_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", required=True)
    p.add_argument("--unit-id", default="")
    p.add_argument("--inputs", default="")
    p.add_argument("--outputs", default="")
    p.add_argument("--checkpoint", default="")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir

    workspace = Path(args.workspace).resolve()
    current_unit_id = (args.unit_id or "").strip()

    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        raise SystemExit(f"Missing {units_path}")

    pipeline_rel = _read_pipeline_path(workspace)
    pipeline_path = (repo_root / pipeline_rel).resolve() if pipeline_rel else None

    fm: dict[str, Any] = _parse_frontmatter(pipeline_path) if (pipeline_path and pipeline_path.exists()) else {}
    targets_raw = fm.get("target_artifacts") or []
    target_artifacts: list[tuple[str, bool]] = []
    if isinstance(targets_raw, list):
        for x in targets_raw:
            rel, optional = _strip_optional_marker(str(x or ""))
            if rel:
                target_artifacts.append((rel, optional))

    rows = _load_units(units_path)

    done_status = {"DONE", "SKIP"}
    pipeline_complete = True
    missing_done_outputs: list[tuple[str, str, str]] = []  # unit_id, skill, rel

    for row in rows:
        unit_id = (row.get("unit_id") or "").strip()
        skill = (row.get("skill") or "").strip()
        status = (row.get("status") or "").strip().upper()
        # When this auditor runs via the executor, its own unit row is marked DOING
        # (the runner updates status before launching the script). Treat the
        # current unit as effectively 'done' for completeness calculation so a
        # finished pipeline can reach PASS.
        if unit_id == current_unit_id:
            if status not in done_status and status != "DOING":
                pipeline_complete = False
        elif status not in done_status:
            pipeline_complete = False

        # Never treat the auditor's own outputs as missing, since it writes them.
        if unit_id == current_unit_id:
            continue

        if status != "DONE":
            continue

        outs_raw = _parse_semicolon_list(row.get("outputs"))
        for raw in outs_raw:
            rel, optional = _strip_optional_marker(raw)
            if optional or not rel:
                continue
            if not (workspace / rel).exists():
                missing_done_outputs.append((unit_id, skill, rel))

    missing_targets: list[str] = []
    self_report_rel = "output/CONTRACT_REPORT.md"
    for rel, optional in target_artifacts:
        if optional:
            continue
        # This auditor produces the contract report; ignore its own target in the
        # pre-write missing-target scan.
        if rel == self_report_rel:
            continue
        if not (workspace / rel).exists():
            missing_targets.append(rel)

    # Status policy.
    status = "PASS"
    if missing_done_outputs:
        status = "FAIL"
    elif pipeline_complete and missing_targets:
        status = "FAIL"
    elif not pipeline_complete:
        status = "OK"

    now = datetime.now().replace(microsecond=0).isoformat()

    lines: list[str] = []
    lines.append("# Contract report")
    lines.append("")
    lines.append(f"- Timestamp: `{now}`")
    lines.append(f"- Status: {status}")
    lines.append(f"- Pipeline complete (units): {'yes' if pipeline_complete else 'no'}")
    lines.append(f"- Pipeline: `{pipeline_rel or '(missing PIPELINE.lock.md)'}`")
    if pipeline_path and pipeline_path.exists():
        lines.append(f"- Pipeline spec: `{pipeline_path.relative_to(repo_root)}`")
    lines.append("")

    lines.append("## A. DONE units missing required outputs")
    if not missing_done_outputs:
        lines.append("- (none)")
    else:
        for unit_id, skill, rel in sorted(missing_done_outputs, key=lambda t: (t[0], t[2])):
            lines.append(f"- `{unit_id}` `{skill}` missing: `{rel}`")
    lines.append("")

    lines.append("## B. Pipeline target artifacts missing")
    if not target_artifacts:
        lines.append("- (no target_artifacts found in pipeline front matter)")
    elif not missing_targets:
        lines.append("- (none)")
    else:
        for rel in missing_targets:
            lines.append(f"- `{rel}`")
    lines.append("")

    lines.append("## C. Next action")
    lines.append("")
    if status == "PASS":
        lines.append("- Workspace looks self-contained and shareable.")
    elif missing_done_outputs:
        lines.append("- Fix the contract drift: a unit is marked DONE but its outputs are missing.")
        lines.append("- Either regenerate the missing outputs (preferred) or revert the unit status to TODO/BLOCKED.")
    elif pipeline_complete and missing_targets:
        lines.append("- The pipeline is complete but target artifacts are missing.")
        lines.append("- Find which unit/skill owns each missing artifact and rerun that unit.")
    else:
        lines.append("- Pipeline is still running; treat this report as a completeness snapshot.")
        lines.append("- If you need a shareable baseline now, finish the remaining units and rerun this auditor.")
    lines.append("")

    out_path = workspace / "output" / "CONTRACT_REPORT.md"
    ensure_dir(out_path.parent)
    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")

    return 0 if status in {"PASS", "OK"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
