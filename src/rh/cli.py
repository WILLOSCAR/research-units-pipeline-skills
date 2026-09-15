"""``rh`` — the command-line face of the one surface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rh.api import Harness, HarnessError, Outcome
from rh.kernel import lessons
from rh.kernel.artifact import ArtifactError
from rh.kernel.evidence import EvidenceCorrupt
from rh.kernel.kinds import KINDS_DIR, list_kinds, load_kind
from rh.kernel.run import RunConflict
from rh.kernel.steps import InputsUnavailable

DEFAULT_WORKSPACE = os.environ.get("RH_WORKSPACE", "workspaces/current")

# Every error the kernel raises on purpose; KindError, SpecError, DecisionError … are ValueErrors,
# RunNotFound and SkillNotFound are FileNotFoundErrors.
REPORTED = (HarnessError, RunConflict, EvidenceCorrupt, ArtifactError, InputsUnavailable, ValueError, FileNotFoundError)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rh", description="Research Harness: start, continue, decide, inspect.")
    parser.add_argument("-w", "--workspace", default=DEFAULT_WORKSPACE, help=f"Run directory (default {DEFAULT_WORKSPACE}, or $RH_WORKSPACE)")
    parser.add_argument("--skills", type=Path, default=None, help="Skill library root (default: the repo's .codex/skills)")
    parser.add_argument("--kinds", type=Path, default=KINDS_DIR, help="directory of Loop kind YAML files")
    parser.add_argument("--project", type=Path, default=None, help="project root for lessons/ and evolve/ (default: the repo root)")
    parser.add_argument("--json", action="store_true", help="print the Outcome as JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="start a Run from a Goal")
    p.add_argument("--goal", required=True, type=Path, help="path to goal.md")
    p.add_argument("--kind", required=True, help="Loop kind (see `rh kinds`)")
    p.add_argument("--format", default="md")

    sub.add_parser("continue", help="hand out the next packet, or take back the one just finished")

    p = sub.add_parser("decide", help="answer a pending Decision")
    p.add_argument("decision", help="D0, D-final, or the id shown by `rh inspect`")
    how = p.add_mutually_exclusive_group(required=True)
    how.add_argument("--accept", action="store_true")
    how.add_argument("--reject", action="store_true")
    how.add_argument("--extend", type=int, metavar="N", help="grant N more passes and resume")
    how.add_argument("--revise", action="store_true", help="send the Success Spec back for revision")
    how.add_argument("--abandon", action="store_true")
    p.add_argument("--reason", default=None)
    p.add_argument("--criterion", default=None, help="criterion id a rejection names")
    p.add_argument("--by", default=None)

    sub.add_parser("inspect", help="state, plan, gates, open Faults, pending Decision, integrity")

    p = sub.add_parser("plan", help="adapt the plan below the Success Spec")
    plan = p.add_subparsers(dest="plan_command", required=True)
    q = plan.add_parser("add", help="insert a step from a YAML file")
    q.add_argument("step", type=Path)
    q = plan.add_parser("skip", help="skip a step the kind marks skippable")
    q.add_argument("step")

    p = sub.add_parser("escalate", help="the agent stops and asks for a Decision")
    p.add_argument("--reason", required=True)

    sub.add_parser("kinds", help="list Loop kinds")

    p = sub.add_parser("lessons", help="the outer loop: Lessons and evolves")
    les = p.add_subparsers(dest="lessons_command", required=True)
    les.add_parser("list")
    q = les.add_parser("show")
    q.add_argument("run_id")
    q = les.add_parser("evolve")
    ev = q.add_subparsers(dest="evolve_command", required=True)
    r = ev.add_parser("propose")
    r.add_argument("target", help="gate:<id> | kind:<kind> | skill:<name>")
    r.add_argument("--lessons", required=True, help="comma-separated run ids")
    r.add_argument("--rationale", required=True)
    r.add_argument("--by", default=None)
    r = ev.add_parser("replay")
    r.add_argument("evolve_id")
    r = ev.add_parser("attest")
    r.add_argument("evolve_id")
    r.add_argument("--lesson", required=True)
    r.add_argument("--gate", required=True)
    caught = r.add_mutually_exclusive_group(required=True)
    caught.add_argument("--caught", action="store_true")
    caught.add_argument("--missed", action="store_true")
    r.add_argument("--by", required=True)
    r = ev.add_parser("adopt")
    r.add_argument("evolve_id")
    r.add_argument("--by", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data, text = _run(args)
    except REPORTED as exc:
        sys.stderr.write(f"rh: {exc}\n")
        return 2
    sys.stdout.write(_json(data) if args.json else text)
    return 0


def _json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _run(args: argparse.Namespace) -> tuple[object, str]:
    """Execute one command; return what `--json` prints and what the plain rendering prints."""
    if args.command == "kinds":
        kinds = [load_kind(name, args.kinds) for name in list_kinds(args.kinds)]
        rows = [{"kind": k.kind, "title": k.title, "deliverable": k.deliverable, "formats": k.formats} for k in kinds]
        return rows, "".join(f"{k.kind:20s} {k.title} -> {k.deliverable} ({', '.join(k.formats)})\n" for k in kinds)
    harness = Harness(args.workspace, skills_root=args.skills, kinds_dir=args.kinds, project=args.project)
    if args.command == "lessons":
        return _lessons(args, harness.project)
    if args.command == "inspect":
        report = harness.inspect()
        return report, render_inspect(report)
    outcome = _dispatch(args, harness)
    return outcome.to_dict(), render_outcome(outcome)


def _dispatch(args: argparse.Namespace, harness: Harness) -> Outcome:
    if args.command == "start":
        return harness.start(args.goal.read_text(encoding="utf-8"), args.kind, args.format)
    if args.command == "continue":
        return harness.continue_()
    if args.command == "decide":
        outcome = "accept" if args.accept else "reject" if args.reject else "revise" if args.revise else "abandon" if args.abandon else "extend"
        return harness.decide(args.decision, outcome, reason=args.reason, criterion=args.criterion, extend=args.extend, by=args.by)
    if args.command == "plan":
        if args.plan_command == "add":
            return harness.plan_add(args.step.read_text(encoding="utf-8"))
        return harness.plan_skip(args.step)
    return harness.escalate(args.reason)


def _lessons(args: argparse.Namespace, project: Path) -> tuple[object, str]:
    if args.lessons_command == "list":
        items = lessons.list_lessons(project)
        return items, "".join(f"{i['run_id']:40s} {i['kind']:12s} {i['status']:10s} {i.get('stop') or ''}\n" for i in items)
    if args.lessons_command == "show":
        result = lessons.load_lesson(project, args.run_id)
    elif args.evolve_command == "propose":
        run_ids = [s.strip() for s in args.lessons.split(",") if s.strip()]
        evolve_id = lessons.propose(project, args.target, run_ids, args.rationale, by=args.by)
        return {"evolve_id": evolve_id}, f"{evolve_id}\n"
    elif args.evolve_command == "replay":
        result = lessons.replay(project, args.evolve_id)
    elif args.evolve_command == "attest":
        result = lessons.attest(project, args.evolve_id, args.lesson, args.gate, args.caught, args.by)
    else:
        result = lessons.adopt(project, args.evolve_id, args.by)
    return result, _json(result)


def render_outcome(outcome: Outcome) -> str:
    lines = [f"{outcome.kind.value}  {outcome.run_id}", outcome.message]
    if outcome.packet:
        lines.append(f"packet: {outcome.packet}")
    if outcome.decision:
        d = outcome.decision
        lines.append(f"decision {d['id']}: {', '.join(d['options'])}")
        for entry in d.get("basis", []):
            lines.append(f"  reviewed {entry['name']} {entry['hash'][:12]}")
    if outcome.stop:
        lines.append(f"stop: {outcome.stop['reason']}" + (f" at {outcome.stop['gate']}" if outcome.stop.get("gate") else ""))
    if outcome.artifact:
        for name, digest in outcome.artifact.items():
            lines.append(f"artifact {name}: {digest[:12]}")
    return "\n".join(lines) + "\n"


def render_inspect(report: dict) -> str:
    lines = [
        f"Run {report['run_id']}  kind {report['kind']}  status {report['status']}  v{report['version']}",
        f"workspace: {report['workspace']}",
        f"budget: {report['budget']['passes_used']}/{report['budget']['passes_total']} passes"
        f" ({report['budget']['passes_per_gate']} per gate, stall {report['budget']['stall_passes']})",
        "",
        "plan:",
    ]
    for step in report["plan"]:
        admitted = f" <- {step['admitted_pass']}" if step["admitted_pass"] else ""
        lines.append(f"  {step['step']:14s} {step['status']:9s} {step['skill']}{admitted}")
    if report["gates"]:
        lines += ["", "gates (latest):"]
        for g in report["gates"]:
            score = f" {g['score']:.2f}" if g["score"] is not None else ""
            lines.append(f"  {g['step']}/{g['gate']:22s} {g['verdict']:4s}{score}  {g['pass_id']} ({g['executor']})")
    if report["open_faults"]:
        lines += ["", "open Faults:"]
        for f in report["open_faults"]:
            lines.append(f"  {f['id']} {f['gate']} on {f['step']}: {f['message'][:100]}")
    if report["pending_decision"]:
        d = report["pending_decision"]
        lines += ["", f"pending Decision {d['id']}: {', '.join(d['options'])}", f"  {d['prompt']}"]
        if report["reviewed_changed"]:
            lines.append(f"  reviewed files changed on disk: {', '.join(report['reviewed_changed'])}")
    if report["pending_pass"]:
        p = report["pending_pass"]
        lines += ["", f"open packet {p['id']} ({p['role']}{' ' + p['gate'] if p['gate'] else ''}): {p['packet']}"]
    if report["stop"]:
        lines += ["", f"stop: {report['stop']['reason']}"]
    if report["artifact"]:
        lines += ["", "artifact:"] + [f"  {k}: {v[:12]}" for k, v in report["artifact"].items()]
    lines += ["", "integrity: " + ("clean" if not report["integrity"] else "; ".join(report["integrity"]))]
    return "\n".join(lines) + "\n"
