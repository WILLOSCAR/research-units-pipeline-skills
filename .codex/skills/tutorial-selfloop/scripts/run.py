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

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["output/TUTORIAL_SELFLOOP_TODO.md"]
    report_path = workspace / outputs[0]
    ensure_dir(report_path.parent)

    tutorial_path = workspace / "output" / "TUTORIAL.md"
    if not tutorial_path.exists():
        _write_report(report_path, status="FAIL", issues=["Missing `output/TUTORIAL.md`."])
        return 2

    from tooling.quality_checks.source_tutorial import tutorial_structure_issues

    issues = tutorial_structure_issues(tutorial_path)

    status = "PASS" if not issues else "FAIL"
    _write_report(report_path, status=status, issues=issues)
    return 0 if not issues else 2


def _write_report(path: Path, *, status: str, issues: list[str]) -> None:
    from tooling.common import atomic_write_text

    lines = [
        "# Tutorial self-loop",
        "",
        f"- Status: {status}",
        "- Deliverable: `output/TUTORIAL.md`",
        "",
        "## Summary",
        "- The tutorial gate checks whether the deliverable still reads like a teachable tutorial rather than a generic long-form article.",
        "",
        "## Remaining blockers",
    ]
    if issues:
        lines.extend([f"- {issue}" for issue in issues])
        lines.extend(["", "## Next step", "- Fix the missing teaching sections in `output/TUTORIAL.md` and rerun this unit."])
    else:
        lines.extend(["- (none)", "", "## Next step", "- Proceed to article/slides delivery."])
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
