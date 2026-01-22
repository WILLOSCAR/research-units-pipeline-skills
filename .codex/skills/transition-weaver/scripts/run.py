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

    from tooling.common import ensure_dir, parse_semicolon_list
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U098").strip() or "U098"

    outputs = parse_semicolon_list(args.outputs) or ["outline/transitions.md"]
    out_rel = outputs[0] if outputs else "outline/transitions.md"

    out_path = workspace / out_rel
    ensure_dir(out_path.parent)

    # LLM-first policy: do NOT generate prose transitions in code.
    # This helper only validates the artifact and emits a quality report when missing/invalid.
    issues = check_unit_outputs(skill="transition-weaver", workspace=workspace, outputs=[out_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="transition-weaver", issues=issues)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
