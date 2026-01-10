from __future__ import annotations

import argparse
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

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import parse_semicolon_list
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U110").strip() or "U110"

    outputs = parse_semicolon_list(args.outputs) or ["output/DRAFT.md"]
    out_rel = outputs[0] if outputs else "output/DRAFT.md"

    issues = check_unit_outputs(skill="draft-polisher", workspace=workspace, outputs=[out_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="draft-polisher", issues=issues)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
