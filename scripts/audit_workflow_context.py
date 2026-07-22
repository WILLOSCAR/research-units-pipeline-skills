from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.workflow_context import (
    build_workflow_context_footprint,
    render_workflow_context_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure declared Workflow-to-Skill context without treating it as runtime token telemetry."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--report", default="", help="Optional report path.")
    args = parser.parse_args()

    payload = build_workflow_context_footprint(repo_root=Path(args.repo_root))
    rendered = (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_workflow_context_markdown(payload)
    )
    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
