"""skills: a Skill's identity is the hash of its SKILL.md; its front matter is what the kernel reads."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import write_skill

import rh.kernel.skills as skills_module
from rh.kernel.evidence import sha256_bytes
from rh.kernel.skills import Skill, SkillLibrary, SkillNotFound, default_skills_root, front_matter

REPO = Path(__file__).resolve().parents[2]

PROVER_FRONT = """\
name: source-support-prover
role: prover
description: "  Check that every statement is supported by the passage it cites.  "
gate: {kind: grounded, ground: source, executor: agent, serves: [supported]}
scaffold_marker: "[[DRAFT]]"
"""


# --- front_matter -------------------------------------------------------------------------


def test_front_matter_parses_yaml_between_the_fences(tmp_path):
    path = write_skill(tmp_path, "source-support-prover", PROVER_FRONT, body="# Prover\n\n---\n\nnot front matter\n")

    front = front_matter(path)

    assert front["name"] == "source-support-prover"
    assert front["role"] == "prover"
    assert front["gate"] == {"kind": "grounded", "ground": "source", "executor": "agent", "serves": ["supported"]}
    assert front["scaffold_marker"] == "[[DRAFT]]"


def test_front_matter_is_empty_without_fences(tmp_path):
    path = write_skill(tmp_path, "brief-writer", body="# Brief writer\n\nrole: prover\n")

    assert front_matter(path) == {}


def test_front_matter_is_empty_when_the_opening_fence_is_never_closed(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: x\nrole: prover\n", encoding="utf-8")

    assert front_matter(path) == {}


def test_front_matter_is_empty_for_a_blank_or_non_mapping_block(tmp_path):
    blank = tmp_path / "blank.md"
    blank.write_text("---\n---\n# body\n", encoding="utf-8")
    listy = tmp_path / "list.md"
    listy.write_text("---\n- a\n- b\n---\n# body\n", encoding="utf-8")

    assert front_matter(blank) == {}
    assert front_matter(listy) == {}


def test_front_matter_requires_the_fence_at_the_very_start(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("\n---\nrole: prover\n---\n", encoding="utf-8")

    assert front_matter(path) == {}


# --- Skill record -------------------------------------------------------------------------------


def test_skill_defaults_when_front_matter_says_nothing():
    skill = Skill(name="brief-writer", path=Path("/x/SKILL.md"), identity="0" * 64)

    assert skill.role == "producer"
    assert skill.scaffold_marker == "<!-- scaffold -->"


def test_skill_reads_role_and_marker_from_front_matter():
    front = {"role": "prover", "scaffold_marker": "[[DRAFT]]", "description": "  Checks support.  "}
    skill = Skill(name="p", path=Path("/x/SKILL.md"), identity="0" * 64, front=front)

    assert skill.role == "prover"
    assert skill.scaffold_marker == "[[DRAFT]]"
    assert skill.front["description"] == "  Checks support.  "  # the rest of the front matter is kept verbatim


# --- SkillLibrary ------------------------------------------------------------------------------------


def test_library_load_returns_the_sha256_of_skill_md_as_identity(tmp_path):
    path = write_skill(tmp_path, "brief-writer", body="# Brief writer\n\nWrite the brief.\n")
    library = SkillLibrary(tmp_path)

    skill = library.load("brief-writer")

    assert skill.name == "brief-writer"
    assert skill.path == path.resolve()
    assert skill.identity == sha256_bytes(path.read_bytes())
    assert len(skill.identity) == 64
    assert skill.front == {}
    assert skill.role == "producer"
    assert skill.scaffold_marker == "<!-- scaffold -->"
    assert library.root == tmp_path.resolve()


def test_library_load_reads_front_matter_into_the_skill(tmp_path):
    write_skill(tmp_path, "source-support-prover", PROVER_FRONT)

    skill = SkillLibrary(tmp_path).load("source-support-prover")

    assert skill.role == "prover"
    assert skill.scaffold_marker == "[[DRAFT]]"
    assert skill.front["gate"]["serves"] == ["supported"]


def test_identity_changes_when_skill_md_changes(tmp_path):
    path = write_skill(tmp_path, "brief-writer", body="v1\n")
    library = SkillLibrary(tmp_path)
    before = library.load("brief-writer").identity

    path.write_text("v2\n", encoding="utf-8")

    assert library.load("brief-writer").identity != before


def test_two_skills_with_identical_bytes_share_an_identity(tmp_path):
    write_skill(tmp_path, "a", body="same\n")
    write_skill(tmp_path, "b", body="same\n")
    library = SkillLibrary(tmp_path)

    assert library.load("a").identity == library.load("b").identity


def test_library_has_and_load_for_a_missing_skill(tmp_path):
    write_skill(tmp_path, "brief-writer")
    (tmp_path / "empty-dir").mkdir()
    library = SkillLibrary(tmp_path)

    assert library.has("brief-writer")
    assert not library.has("empty-dir")
    assert not library.has("nope")
    with pytest.raises(SkillNotFound, match="'nope'"):
        library.load("nope")
    with pytest.raises(SkillNotFound):
        library.load("empty-dir")
    assert issubclass(SkillNotFound, FileNotFoundError)


# --- default_skills_root --------------------------------------------------------------------------------


def test_default_skills_root_finds_the_repo_codex_skills():
    root = default_skills_root()

    assert root == REPO / ".codex" / "skills"
    assert root.is_dir()


def test_library_defaults_to_the_repo_skills_root():
    assert SkillLibrary().root == (REPO / ".codex" / "skills").resolve()


def test_default_skills_root_walks_up_from_the_kernel_module(tmp_path, monkeypatch):
    module_file = tmp_path / "proj" / "src" / "rh" / "kernel" / "skills.py"
    module_file.parent.mkdir(parents=True)
    module_file.touch()
    expected = tmp_path / "proj" / ".codex" / "skills"
    expected.mkdir(parents=True)
    monkeypatch.setattr(skills_module, "__file__", str(module_file))

    assert default_skills_root() == expected.resolve()


def test_default_skills_root_falls_back_to_the_working_directory(tmp_path, monkeypatch):
    module_file = tmp_path / "elsewhere" / "skills.py"
    module_file.parent.mkdir(parents=True)
    module_file.touch()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(skills_module, "__file__", str(module_file))
    monkeypatch.chdir(cwd)

    assert default_skills_root().resolve() == (cwd / ".codex" / "skills").resolve()
