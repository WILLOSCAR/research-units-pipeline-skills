from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.skill_invocation_eval import (
    build_candidate_pack,
    build_invocation_evaluation,
    load_invocation_corpus,
    load_invocation_predictions,
    load_skill_catalog,
    render_candidate_pack,
    render_invocation_json,
    render_invocation_markdown,
    render_prediction_template,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate model-produced repository Skill selections against a stable invocation corpus."
    )
    parser.add_argument(
        "--corpus",
        default=str(REPO_ROOT / "tests" / "fixtures" / "skill_invocation_cases.yaml"),
        help="Invocation case corpus in YAML.",
    )
    parser.add_argument(
        "--predictions",
        default="",
        help="Optional model prediction JSONL. Without it, the corpus and current Skill context load are reported as UNSCORED.",
    )
    parser.add_argument(
        "--skills-dir",
        default=str(REPO_ROOT / ".codex" / "skills"),
        help="Repository Skill root.",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--report", default="", help="Optional evaluation report path.")
    parser.add_argument(
        "--emit-candidate-pack",
        default="",
        help="Optional path for a gold-label-free JSON pack containing Skill descriptions and case prompts.",
    )
    parser.add_argument(
        "--emit-prediction-template",
        default="",
        help="Optional path for a JSONL template with one empty prediction per corpus case.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit 2 unless the scored evaluation verdict is PASS.")
    args = parser.parse_args()

    try:
        catalog = load_skill_catalog(Path(args.skills_dir).resolve())
        scope, cases = load_invocation_corpus(Path(args.corpus).resolve(), catalog=catalog)
        predictions = (
            load_invocation_predictions(
                Path(args.predictions).resolve(),
                case_ids={case.id for case in cases},
            )
            if args.predictions
            else []
        )
        if args.emit_prediction_template:
            template_path = Path(args.emit_prediction_template).resolve()
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(render_prediction_template(cases), encoding="utf-8")
        if args.emit_candidate_pack:
            pack_path = Path(args.emit_candidate_pack).resolve()
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            pack_path.write_text(
                render_candidate_pack(build_candidate_pack(scope=scope, cases=cases, catalog=catalog)),
                encoding="utf-8",
            )
        payload = build_invocation_evaluation(
            scope=scope,
            cases=cases,
            predictions=predictions,
            catalog=catalog,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = render_invocation_json(payload) if args.format == "json" else render_invocation_markdown(payload)
    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    if args.strict and payload["verdict"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
