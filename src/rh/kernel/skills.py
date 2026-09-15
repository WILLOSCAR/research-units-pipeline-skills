"""Skills are prose contracts the agent reads; the kernel knows their identity.

A Skill's identity is the sha256 of its ``SKILL.md``. The kernel uses it to
refuse a GateResult whose prover is the same Skill as the producer it judges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from rh.kernel.evidence import sha256_file


class SkillError(ValueError):
    pass


class SkillNotFound(FileNotFoundError):
    pass


@dataclass
class Skill:
    name: str
    path: Path
    identity: str
    front: dict = field(default_factory=dict)

    @property
    def role(self) -> str:
        return str(self.front.get("role", "producer"))

    @property
    def scaffold_marker(self) -> str:
        return str(self.front.get("scaffold_marker", "<!-- scaffold -->"))


def default_skills_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".codex" / "skills"
        if candidate.is_dir():
            return candidate
    return Path.cwd() / ".codex" / "skills"


class SkillLibrary:
    def __init__(self, root: Path | None = None):
        self.root = (root or default_skills_root()).resolve()

    def has(self, name: str) -> bool:
        return (self.root / name / "SKILL.md").is_file()

    def load(self, name: str) -> Skill:
        path = self.root / name / "SKILL.md"
        if not path.is_file():
            raise SkillNotFound(f"Skill {name!r} not found under {self.root}")
        return Skill(name=name, path=path, identity=sha256_file(path), front=front_matter(path))


def front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        data = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"{path}: front matter is not valid YAML ({exc})") from exc
    return data if isinstance(data, dict) else {}
