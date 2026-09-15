"""Gates: how verify is executed.

Kernel gates are recomputed here from Evidence bytes, never read from an
agent's report. Agent gates are executed by a prover Skill in a fresh
context; the kernel only admits a GateResult that names its gate, cites
resolvable Evidence, and comes from a Skill other than the producer's.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Callable

import yaml

from rh.kernel.evidence import EvidenceStore
from rh.kernel.records import (
    Criterion,
    Executor,
    Finding,
    GateDecl,
    GateKind,
    GateResult,
    Ground,
    Pass,
    Relation,
    Step,
    Verdict,
    decode,
)
from rh.kernel.skills import Skill

STATEMENTS_SCHEMA = "rh.statements/1"
GATE_RESULT_SCHEMA = "rh.gate_result/1"
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b")


class GateResultInvalid(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def result_text(body: dict) -> str:
    """The bytes a GateResult is hashed as when it enters Evidence: its JSON shape without ``hash``, keys sorted."""
    return json.dumps({k: v for k, v in body.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)


@dataclass
class GateContext:
    step: Step
    pass_: Pass
    outputs: dict[str, bytes]
    criteria: list[Criterion]
    store: EvidenceStore
    producer: Skill
    deliverable: str
    statements: str
    inputs: set[str] | None = None  # hashes the pass was given; None when unknown (replay)


# --- statements ----------------------------------------------------------


@dataclass
class Pointer:
    hash: str
    relation: Relation
    locator: str = ""


@dataclass
class Statement:
    id: str
    text: str
    evidence: list[Pointer] = field(default_factory=list)


def parse_statements(data: bytes) -> tuple[list[Statement], list[str]]:
    problems: list[str] = []
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [], [f"statements: not valid JSON ({exc})"]
    if not isinstance(raw, dict) or raw.get("schema") != STATEMENTS_SCHEMA:
        problems.append(f"statements: schema must be {STATEMENTS_SCHEMA}")
    items = raw.get("statements") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return [], problems + ["statements: 'statements' must be a list"]
    out: list[Statement] = []
    for i, item in enumerate(items):
        try:
            out.append(decode(Statement, item))
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"statements[{i}]: {exc}")
    ids = [s.id for s in out]
    if len(set(ids)) != len(ids):
        problems.append("statements: duplicate ids")
    return out, problems


def paragraphs(markdown: str) -> list[str]:
    """Body paragraphs of a deliverable: no headings, comments, or front matter.

    A fenced code block belongs to the paragraph it follows: blank lines and
    ``#`` lines inside a fence do not split or strip anything.
    """
    text = markdown
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[end + 4 :]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    blocks: list[list[str]] = [[]]
    in_fence = False
    for line in text.splitlines():
        if re.match(r"\s*(```|~~~)", line):
            in_fence = not in_fence
            blocks[-1].append(line)
        elif in_fence:
            blocks[-1].append(line)
        elif not line.strip():
            if blocks[-1]:
                blocks.append([])
        elif not line.startswith("#"):  # a heading glued to its body
            blocks[-1].append(line)
    out: list[str] = []
    for lines in blocks:
        block = "\n".join(lines).strip()
        if not block or re.fullmatch(r"[-*_]{3,}", block):
            continue
        out.append(block)
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- kernel gates -----------------------------------------------------------


@dataclass
class KernelGate:
    id: str
    serves: list[str]
    check: Callable[[GateContext], list[Finding]]
    kind: GateKind = GateKind.STRUCTURAL
    ground: Ground = Ground.COMPUTATION
    required: bool = True  # a Success Spec must bind this gate when the kind declares it

    def declare(self, applies_to: list[str]) -> GateDecl:
        return GateDecl(
            id=self.id,
            kind=self.kind,
            ground=self.ground,
            executor=Executor.KERNEL,
            serves=list(self.serves),
            applies_to=applies_to,
            calibration={"status": "deterministic"},
        )

    def run(self, ctx: GateContext) -> GateResult:
        findings = self.check(ctx)
        return GateResult(
            gate=self.id,
            step=ctx.step.id,
            pass_id=ctx.pass_.id,
            verdict=Verdict.FAIL if findings else Verdict.PASS,
            criteria=[c.id for c in ctx.criteria],
            findings=findings,
            produced_by="kernel",
            executor=Executor.KERNEL,
            kind=self.kind,
            ground=self.ground,
            calibration={"status": "deterministic"},
        )


def _statements_of(ctx: GateContext) -> tuple[list[Statement], list[Finding]]:
    data = ctx.outputs.get(ctx.statements)
    if data is None:
        return [], [Finding(f"{ctx.statements} is not an output of step {ctx.step.id}")]
    statements, problems = parse_statements(data)
    return statements, [Finding(p) for p in problems]


def check_pointer_resolution(ctx: GateContext) -> list[Finding]:
    statements, findings = _statements_of(ctx)
    for s in statements:
        if not s.evidence:
            findings.append(Finding(f"statement {s.id} cites no evidence", statement=s.id))
        for p in s.evidence:
            if not ctx.store.has(p.hash):
                findings.append(Finding(f"statement {s.id} cites unresolvable evidence {p.hash[:12]}", statement=s.id))
            elif ctx.inputs is not None and p.hash not in ctx.inputs:
                findings.append(
                    Finding(f"statement {s.id} cites evidence {p.hash[:12]} the step was not given", statement=s.id)
                )
            else:
                ctx.store.get(p.hash)  # a body that no longer matches its hash is corruption: fail closed
    return findings


def check_provenance_present(ctx: GateContext) -> list[Finding]:
    statements, findings = _statements_of(ctx)
    body = ctx.outputs.get(ctx.deliverable)
    if body is None:
        return findings + [Finding(f"{ctx.deliverable} is not an output of step {ctx.step.id}")]
    texts = [_norm(s.text) for s in statements if s.evidence]
    for i, para in enumerate(paragraphs(body.decode("utf-8", errors="replace"))):
        normalized = _norm(para)
        if not any(t and t in normalized for t in texts):
            findings.append(Finding(f"paragraph {i + 1} has no statement with evidence: {para[:80]!r}"))
    return findings


def check_scaffold_absent(ctx: GateContext) -> list[Finding]:
    marker = ctx.producer.scaffold_marker
    findings: list[Finding] = []
    for name, data in ctx.outputs.items():
        text = data.decode("utf-8", errors="replace")
        if marker in text:
            findings.append(Finding(f"{name} still contains the scaffold marker {marker!r}"))
        hit = PLACEHOLDER.search(text)
        if hit:
            findings.append(Finding(f"{name} contains placeholder token {hit.group(0)!r}"))
    return findings


def check_schema_valid(ctx: GateContext) -> list[Finding]:
    findings: list[Finding] = []
    for name, data in ctx.outputs.items():
        text = data.decode("utf-8", errors="replace")
        try:
            if name == ctx.statements:
                _, problems = parse_statements(data)
                findings.extend(Finding(p) for p in problems)
            elif name.endswith(".json"):
                json.loads(text)
            elif name.endswith(".jsonl"):
                rows = [json.loads(line) for line in text.splitlines() if line.strip()]
                if not rows:
                    findings.append(Finding(f"{name} has no records"))
            elif name.endswith((".yaml", ".yml")):
                if yaml.safe_load(text) is None:
                    findings.append(Finding(f"{name} is empty"))
            elif name.endswith((".csv", ".tsv")):
                dialect = csv.excel_tab if name.endswith(".tsv") else csv.excel
                rows = list(csv.reader(io.StringIO(text), dialect=dialect))
                if not rows or not any(rows[0]):
                    findings.append(Finding(f"{name} has no header"))
                elif any(len(r) != len(rows[0]) for r in rows[1:] if r):
                    findings.append(Finding(f"{name} has ragged rows"))
                # a header with no rows is a valid, honest table (e.g. zero included studies);
                # whether emptiness is acceptable is a coverage question for a prover
        except (json.JSONDecodeError, yaml.YAMLError, csv.Error) as exc:
            findings.append(Finding(f"{name} does not parse: {exc}"))
    return findings


def check_length_bound(ctx: GateContext) -> list[Finding]:
    body = ctx.outputs.get(ctx.deliverable)
    if body is None:
        return []
    words = len(" ".join(paragraphs(body.decode("utf-8", errors="replace"))).split())
    findings: list[Finding] = []
    for c in ctx.criteria:
        limit = c.params.get("max_words")
        floor = c.params.get("min_words")
        if limit is not None and words > int(limit):
            findings.append(Finding(f"{ctx.deliverable} has {words} words, over {limit}", criterion=c.id))
        if floor is not None and words < int(floor):
            findings.append(Finding(f"{ctx.deliverable} has {words} words, under {floor}", criterion=c.id))
    return findings


KERNEL_GATES: dict[str, KernelGate] = {
    g.id: g
    for g in (
        KernelGate("pointer-resolution", ["provenance"], check_pointer_resolution),
        KernelGate("provenance-present", ["provenance"], check_provenance_present),
        KernelGate("scaffold-absent", ["scaffold"], check_scaffold_absent),
        KernelGate("schema-valid", ["format"], check_schema_valid),
        KernelGate("length-bound", ["length"], check_length_bound, required=False),
    )
}


# --- agent gates -------------------------------------------------------------


def validate_agent_result(
    raw: bytes,
    decl: GateDecl,
    prover_pass: Pass,
    checked_pass: Pass,
    criteria: list[Criterion],
    store: EvidenceStore,
    prover: Skill,
    producer: Skill,
    inputs: set[str] | None = None,
) -> GateResult:
    """Admit a prover's ``gate_result.json`` or refuse it with reasons.

    ``inputs`` are the hashes the prover packet listed; when given, a finding
    may cite only those.
    """
    problems: list[str] = []
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateResultInvalid([f"gate_result.json is not valid JSON ({exc})"]) from exc
    if not isinstance(data, dict):
        raise GateResultInvalid(["gate_result.json must be an object"])
    if data.get("schema") != GATE_RESULT_SCHEMA:
        problems.append(f"schema must be {GATE_RESULT_SCHEMA}")
    if data.get("gate") != decl.id:
        problems.append(f"gate must be {decl.id!r}, got {data.get('gate')!r}")
    if data.get("step") != checked_pass.step:
        problems.append(f"step must be {checked_pass.step!r}")
    if data.get("pass_id") != checked_pass.id:
        problems.append(f"pass_id must be {checked_pass.id!r} (the pass under check)")
    try:
        verdict = Verdict(data.get("verdict"))
    except ValueError:
        problems.append("verdict must be 'pass' or 'fail'")
        verdict = Verdict.FAIL
    score = data.get("score")
    if score is not None and not (isinstance(score, (int, float)) and 0 <= score <= 1):
        problems.append("score must be a number in [0, 1]")
    if prover.identity == producer.identity or (prover_pass.skill_identity and prover_pass.skill_identity == checked_pass.skill_identity):
        problems.append(f"prover Skill {prover.name!r} is the producer Skill; a step may not verify itself")
    findings: list[Finding] = []
    for i, item in enumerate(data.get("findings") or []):
        try:
            finding = decode(Finding, item)
        except (KeyError, TypeError) as exc:
            problems.append(f"findings[{i}]: {exc}")
            continue
        broken = store.verify_all(finding.evidence)
        if broken:
            problems.append(f"findings[{i}] cites unresolvable evidence {[b[:12] for b in broken]}")
        elif inputs is not None:
            foreign = [h for h in finding.evidence if h not in inputs]
            if foreign:
                problems.append(f"findings[{i}] cites evidence the prover was not given {[h[:12] for h in foreign]}")
        findings.append(finding)
    if verdict is Verdict.FAIL and not findings:
        problems.append("a failing verdict must carry at least one finding")
    if verdict is Verdict.FAIL and not any(f.evidence for f in findings):
        problems.append("a failing verdict must cite Evidence in at least one finding")
    known = {c.id for c in criteria}
    for f in findings:
        if f.criterion is not None and f.criterion not in known:
            problems.append(f"finding names unknown criterion {f.criterion!r}")
    if problems:
        raise GateResultInvalid(problems)
    return GateResult(
        gate=decl.id,
        step=checked_pass.step,
        pass_id=checked_pass.id,
        verdict=verdict,
        criteria=[c.id for c in criteria],
        score=float(score) if score is not None else None,
        findings=findings,
        produced_by=prover_pass.skill_identity or prover.identity,
        prover_pass=prover_pass.id,
        executor=Executor.AGENT,
        kind=decl.kind,
        ground=decl.ground,
        calibration=dict(decl.calibration),
    )
