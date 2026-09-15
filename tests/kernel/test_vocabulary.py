"""vocabulary: new code under ``src/rh`` speaks the story's language and imports none of the old engines.

Enforced by ``AGENTS.md``: new code must not import ``tooling`` or
``research_harness``, and the legacy nouns must not appear in identifiers.
Only NAME tokens are inspected, so comments, docstrings and string literals
may still mention the old words when explaining what replaced them.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "rh"

LEGACY_FRAGMENT = re.compile(r"\w*(Unit|Attempt|Checkpoint|Case|Workflow|Pipeline)\w*")
LEGACY_WORDS = frozenset({"unit", "attempt", "checkpoint", "workflow", "pipeline"})
LEGACY_MODULES = frozenset({"tooling", "research_harness"})
LEGACY_IMPORT_LINE = re.compile(r"^\s*(from|import)\s+(tooling|research_harness)\b")


def python_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def name_tokens(text: str) -> list[tokenize.TokenInfo]:
    return [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type == tokenize.NAME]


def imported_roots(text: str) -> list[tuple[int, str]]:
    """``(line, top-level module)`` for every import statement in ``text``."""
    roots: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            roots.extend((node.lineno, alias.name.split(".")[0]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.append((node.lineno, node.module.split(".")[0]))
    return roots


def is_legacy_name(name: str) -> bool:
    return bool(LEGACY_FRAGMENT.fullmatch(name)) or name in LEGACY_WORDS


def test_the_kernel_package_exists_and_has_modules():
    files = python_files()

    assert files, f"no Python files under {SRC}"
    assert any(p.name == "records.py" for p in files)


def test_no_module_imports_the_old_engines():
    hits: list[str] = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        for line_no, root in imported_roots(text):
            if root in LEGACY_MODULES:
                hits.append(f"{rel(path)}:{line_no}: imports {root}")
        for line_no, line in enumerate(text.splitlines(), 1):  # belt and braces on the raw lines
            if LEGACY_IMPORT_LINE.match(line):
                hits.append(f"{rel(path)}:{line_no}: {line.strip()}")

    assert hits == [], "\n".join(hits)


def test_no_identifier_carries_a_legacy_noun():
    hits: list[str] = []
    for path in python_files():
        for tok in name_tokens(path.read_text(encoding="utf-8")):
            if is_legacy_name(tok.string):
                hits.append(f"{rel(path)}:{tok.start[0]}: {tok.string}")

    assert hits == [], "legacy vocabulary in identifiers:\n" + "\n".join(hits)


def test_the_legacy_detector_flags_what_it_should_and_nothing_else():
    flagged = ["RunUnit", "attempt", "Checkpoint", "CaseFile", "WorkflowSpec", "pipeline", "PipelineRunner", "unit"]
    allowed = ["Pass", "Step", "Decision", "Gate", "Run", "Fault", "UnionType", "lowercase", "casefold"]

    assert [w for w in flagged if not is_legacy_name(w)] == []
    assert [w for w in allowed if is_legacy_name(w)] == []
    assert imported_roots("import tooling.x as t\nfrom research_harness.engine import run\nfrom . import y\n") == [
        (1, "tooling"),
        (2, "research_harness"),
    ]
