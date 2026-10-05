"""A Run's execution boundary, retained in its single state authority.

The selected kind's bytes are retained for inspection; execution requires
those bytes, the complete kernel source manifest and the named SKILL.md
identities to match. This is a local compatibility guard, not a sandbox.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import rh
from rh.kernel.evidence import sha256_file, sha256_text
from rh.kernel.kinds import Kind, parse_kind
from rh.kernel.records import ExecutionContract, Role, RunState
from rh.kernel.skills import Skill, SkillLibrary

SCHEMA = "rh.execution_contract/1"
KERNEL_ROOT = Path(__file__).resolve().parent.parent


def kernel_manifest() -> dict[str, str]:
    """Source-relative identities, including added or removed Python modules."""
    return {p.relative_to(KERNEL_ROOT).as_posix(): sha256_file(p) for p in sorted(KERNEL_ROOT.rglob("*.py"))}


# Also refuse a checkout edit within a long-lived importing process. A fresh
# process must load the restored sources before it can resume an older Run.
LOADED_KERNEL = kernel_manifest()
LOADED_VERSION = rh.__version__


def skill_names(kind: Kind) -> set[str]:
    return {s.skill for s in kind.steps} | {g.skill for g in kind.gates if g.skill}


def capture(name: str, kinds_dir: Path, library: SkillLibrary) -> tuple[ExecutionContract, Kind, dict[str, Skill]]:
    current = kernel_manifest()
    if current != LOADED_KERNEL:
        raise ValueError("execution contract: kernel changed after import; restart with the intended sources")
    source = (kinds_dir / f"{name}.yaml").read_bytes().decode("utf-8")
    kind = parse_kind(yaml.safe_load(source), source=str(kinds_dir / f"{name}.yaml"))
    if kind.kind != name:
        raise ValueError(f"execution contract: kind {name!r} declares a different name {kind.kind!r}")
    skills = {name: library.load(name) for name in sorted(skill_names(kind))}
    pin = ExecutionContract(
        kernel=current, kernel_version=LOADED_VERSION, kind_source=source,
        kind_hash=sha256_text(source), skills={name: skill.identity for name, skill in skills.items()},
    )
    return pin, kind, skills


def snapshot_kind(state: RunState) -> Kind:
    pin = state.execution_contract
    if pin is None:
        raise ValueError("execution contract is unpinned; historical provenance is unavailable; start a new Run")
    if pin.schema != SCHEMA:
        raise ValueError(f"execution contract schema {pin.schema!r} is unsupported")
    if sha256_text(pin.kind_source) != pin.kind_hash:
        raise ValueError("execution contract kind snapshot does not match its hash")
    kind = parse_kind(yaml.safe_load(pin.kind_source), source="recorded kind")
    if kind.kind != state.kind:
        raise ValueError("execution contract kind snapshot does not match the Run's kind")
    return kind


def check(state: RunState, kinds_dir: Path, library: SkillLibrary) -> tuple[list[str], Kind | None, dict[str, Skill]]:
    """Read-only diagnostics and the exact metadata checked before a transition."""
    try:
        kind = snapshot_kind(state)
    except (ValueError, yaml.YAMLError) as exc:
        return [str(exc)], None, {}
    pin = state.execution_contract
    problems: list[str] = []
    if pin.kernel_version != LOADED_VERSION:
        problems.append(f"kernel version {pin.kernel_version!r} differs from the loaded runtime {LOADED_VERSION!r}")
    try:
        current = kernel_manifest()
        for name in sorted(set(pin.kernel) | set(current) | set(LOADED_KERNEL)):
            if not (pin.kernel.get(name) == current.get(name) == LOADED_KERNEL.get(name)):
                problems.append(f"kernel source {name!r} changed, is missing, or was added")
        if not pin.kernel:
            problems.append("kernel source manifest is empty")
    except OSError as exc:
        problems.append(f"kernel sources unavailable: {exc}")
    try:
        if sha256_file(kinds_dir / f"{state.kind}.yaml") != pin.kind_hash:
            problems.append(f"kind {state.kind!r} changed")
    except OSError as exc:
        problems.append(f"kind {state.kind!r} unavailable: {exc}")
    names = skill_names(kind) | {s.skill for s in state.plan.steps}
    if names != set(pin.skills):
        problems.append("Skill identity inventory does not match the kind and plan")
    skills: dict[str, Skill] = {}
    for name in sorted(names):
        try:
            skill = library.load(name)
            if skill.identity != pin.skills.get(name):
                problems.append(f"Skill {name!r} changed or has no recorded identity")
            else:
                skills[name] = skill
        except (OSError, ValueError) as exc:
            problems.append(f"Skill {name!r} unavailable: {exc}")
    for pass_ in state.passes:
        try:
            name = kind.gate(pass_.gate).skill if pass_.role is Role.PROVER else state.plan.get(pass_.step).skill
            if pass_.skill_identity != pin.skills.get(name):
                problems.append(f"pass {pass_.id!r} Skill identity disagrees with the execution contract")
        except KeyError:
            problems.append(f"pass {pass_.id!r} has no declared Skill in the execution contract")
    return problems, kind, skills
