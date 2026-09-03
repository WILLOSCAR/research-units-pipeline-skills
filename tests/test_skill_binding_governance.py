"""Regression: Skill binding governance keeps every Skill reachable-by-record.

`scripts/validate_repo.py` gained `_validate_skill_binding_governance`, which
requires each Skill directory to be *governed*: either referenced from some
`templates/UNITS.*.csv` `skill` column, or carrying a `binding:` frontmatter key
of `manual` | `library` | `staged`.

The check and the 27 `binding:` declarations that satisfy it are one contract:
shipping the gate without the declarations would fail the repository, and
shipping the declarations without the gate would leave the orphan condition
unenforced. These tests cover all four states of that contract — bound by
template, governed by a valid `binding:`, ungoverned (orphan), and an
unsupported `binding:` value — plus the invariant that the real repository is
clean.

`binding:` is a governance record of how a Skill is reached. It does not widen
what may invoke a Skill, which is why it is allowed in front matter alongside
`name` and `description` (SKILLS_STANDARD.md, "Progressive disclosure").
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_repo import (  # noqa: E402
    ALLOWED_SKILL_BINDINGS,
    _validate_skill_binding_governance,
)

SKILL_TEMPLATE = """---
name: {name}
{binding_line}description: "Does one narrow thing for a test."
---

# {name}

Body.
"""


def _write_skill(skills_dir: Path, name: str, binding: str | None) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    binding_line = f"binding: {binding}\n" if binding is not None else ""
    (skill_dir / "SKILL.md").write_text(
        SKILL_TEMPLATE.format(name=name, binding_line=binding_line), encoding="utf-8"
    )


def _units_template(tmp_path: Path, skills: list[str]) -> Path:
    """Build a valid pipeline contract plus the Units template it names.

    The validator resolves the template through `PipelineSpec.load` front matter,
    not by guessing a filename, so the fixture pipeline must be a loadable spec.
    """
    (tmp_path / "templates").mkdir(exist_ok=True)
    rows = ["unit_id,title,skill"] + [f"U{i},Unit {i},{s}" for i, s in enumerate(skills, 1)]
    (tmp_path / "templates" / "UNITS.demo.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    (tmp_path / "pipelines").mkdir(exist_ok=True)
    pipeline = tmp_path / "pipelines" / "demo.pipeline.md"
    pipeline.write_text(
        "---\n"
        "name: demo\n"
        "version: 1.0\n"
        "profile: demo\n"
        "units_template: templates/UNITS.demo.csv\n"
        "default_checkpoints: [C0]\n"
        "target_artifacts:\n"
        "  - STATUS.md\n"
        "---\n\n"
        "# Pipeline: demo\n",
        encoding="utf-8",
    )
    return pipeline


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the validator's module-level paths at a temporary repository."""
    import scripts.validate_repo as vr

    skills_dir = tmp_path / ".codex" / "skills"
    skills_dir.mkdir(parents=True)
    monkeypatch.setattr(vr, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    return tmp_path, skills_dir


def _messages(findings) -> str:
    return "\n".join(f.message for f in findings)


def test_skill_bound_by_units_template_is_governed(sandbox) -> None:
    tmp_path, skills_dir = sandbox
    _write_skill(skills_dir, "bound-skill", binding=None)
    pipeline = _units_template(tmp_path, ["bound-skill"])

    findings = _validate_skill_binding_governance([pipeline])

    assert findings == [], _messages(findings)


@pytest.mark.parametrize("binding", sorted(ALLOWED_SKILL_BINDINGS))
def test_valid_binding_key_governs_an_untemplated_skill(sandbox, binding: str) -> None:
    tmp_path, skills_dir = sandbox
    _write_skill(skills_dir, "library-skill", binding=binding)
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    assert findings == [], _messages(findings)


def test_ungoverned_skill_is_reported_as_unbound(sandbox) -> None:
    tmp_path, skills_dir = sandbox
    _write_skill(skills_dir, "orphan-skill", binding=None)
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    assert len(findings) == 1, _messages(findings)
    assert findings[0].level == "WARN"
    assert "orphan-skill" in findings[0].message
    assert "UNITS" in findings[0].message


def test_unsupported_binding_value_is_rejected_under_strict(sandbox) -> None:
    """A misspelled binding must not pass governance.

    The contract is that `--strict` refuses the repository, which `_report`
    derives from any WARN. Asserting a second, UNITS-flavoured message would
    demand duplicate reporting the contract does not call for.
    """
    import scripts.validate_repo as vr

    tmp_path, skills_dir = sandbox
    _write_skill(skills_dir, "typo-skill", binding="libary")
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    assert [f.level for f in findings] == ["WARN"], _messages(findings)
    assert "unsupported `binding: libary`" in findings[0].message
    assert "typo-skill" in findings[0].message
    # The value is named so an author can correct it.
    for allowed in sorted(ALLOWED_SKILL_BINDINGS):
        assert allowed in findings[0].message

    # And the WARN is load-bearing: --strict refuses this repository.
    assert vr._report(findings, strict=True, report_path=None) == 2
    assert vr._report(findings, strict=False, report_path=None) == 0


def test_unbound_skills_are_reported_in_one_aggregated_finding(sandbox) -> None:
    tmp_path, skills_dir = sandbox
    for name in ("orphan-a", "orphan-b", "orphan-c"):
        _write_skill(skills_dir, name, binding=None)
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    unbound = [f for f in findings if "UNITS" in f.message]
    assert len(unbound) == 1, _messages(findings)
    for name in ("orphan-a", "orphan-b", "orphan-c"):
        assert name in unbound[0].message


def _write_raw_skill(skills_dir: Path, name: str, text: str) -> Path:
    """Write a SKILL.md whose front matter is missing, unterminated, or invalid."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


UNPARSEABLE_SKILLS = {
    # No front matter at all: nothing declares a binding, nothing is templated.
    "no-frontmatter": "# no-frontmatter\n\nBody only.\n",
    # Opened but never closed: a truncated or hand-edited file.
    "unterminated": "---\nname: unterminated\nbinding: library\n\n# unterminated\n",
    # Structurally invalid YAML inside the fences.
    "malformed-yaml": "---\nname: malformed-yaml\nbinding: [unclosed\n---\n\n# malformed-yaml\n",
    # Parses, but to a scalar rather than a mapping, so `.get` is unavailable.
    "scalar-frontmatter": "---\njust a string\n---\n\n# scalar-frontmatter\n",
}


@pytest.mark.parametrize("name,text", sorted(UNPARSEABLE_SKILLS.items()))
def test_unreadable_frontmatter_cannot_bypass_governance(sandbox, name: str, text: str) -> None:
    """A Skill whose front matter cannot be read is ungoverned, not exempt.

    Skipping it would let a Skill that is indexed but referenced by no Units
    template escape `--strict` simply by having missing or broken front matter —
    the governance hole this check exists to close.
    """
    import scripts.validate_repo as vr

    tmp_path, skills_dir = sandbox
    _write_raw_skill(skills_dir, name, text)
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    assert findings, f"{name} produced no finding and would pass --strict silently"
    assert any(name in f.message for f in findings), _messages(findings)
    assert vr._report(findings, strict=True, report_path=None) == 2


@pytest.mark.parametrize("name,text", sorted(UNPARSEABLE_SKILLS.items()))
def test_unreadable_frontmatter_findings_do_not_echo_file_content(
    sandbox, name: str, text: str
) -> None:
    """Report the Skill and the rule, never the raw YAML or exception text."""
    tmp_path, skills_dir = sandbox
    _write_raw_skill(skills_dir, name, text)
    pipeline = _units_template(tmp_path, [])

    findings = _validate_skill_binding_governance([pipeline])

    for finding in findings:
        assert "unclosed" not in finding.message
        assert "just a string" not in finding.message
        for line in text.splitlines():
            body = line.strip()
            if body and not body.startswith(("#", "-")) and body != f"name: {name}":
                assert body not in finding.message, finding.message


def test_templated_skill_with_unreadable_frontmatter_is_still_governed(sandbox) -> None:
    """Front matter that will not parse is not itself a violation.

    A Skill referenced by a Units template is governed by that reference, so it
    must not be reported here; broken front matter is other checks' business.
    """
    tmp_path, skills_dir = sandbox
    _write_raw_skill(skills_dir, "templated-broken", "# templated-broken\n\nNo front matter.\n")
    pipeline = _units_template(tmp_path, ["templated-broken"])

    findings = _validate_skill_binding_governance([pipeline])

    assert findings == [], _messages(findings)


def test_real_repository_has_no_ungoverned_skill() -> None:
    """The contract closes: every Skill in this repository is governed."""
    pipelines = sorted((REPO_ROOT / "pipelines").glob("*.pipeline.md"))
    assert pipelines, "no pipeline contracts found"

    findings = _validate_skill_binding_governance(pipelines)

    assert findings == [], _messages(findings)
