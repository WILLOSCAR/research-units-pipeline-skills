#!/usr/bin/env python3
"""Repository document gate: relative links resolve, and system documents
declare their class.

Checks tracked Markdown (``git ls-files '*.md'``), excluding ``.codex/skills``,
``ref`` and ``workspaces``:

a. Every relative Markdown link ``[text](path)`` or ``[text](path#anchor)``
   points at an existing file. ``http(s)://``, ``mailto:`` and pure
   ``#anchor`` links are ignored.
b. Every top-level ``docs/*.md`` file and ``CONTEXT.md`` carries, within its
   first 15 lines, a blockquote line that names its document class:
   ``Product``, ``Implementation snapshot`` or ``Process``. ADRs under
   ``docs/adr/`` and process notes under ``docs/agents/`` are exempt.

Prints one ``path: message`` line per problem and exits 1 if any were found.
``--strict`` is accepted as a no-op so CI can call it like the older gates.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PREFIXES = (".codex/skills/", "ref/", "workspaces/")
CLASS_MARKERS = ("Product", "Implementation snapshot", "Process")
CLASS_HEADER_LINES = 15

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def tracked_markdown() -> list[Path]:
    """Markdown files git knows about: the index plus untracked files that are
    not ignored, so a document is checked before its first commit."""
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths = sorted({entry for entry in output.split("\0") if entry})
    return [
        REPO_ROOT / rel
        for rel in paths
        if not rel.startswith(EXCLUDED_PREFIXES) and (REPO_ROOT / rel).is_file()
    ]


def prose_lines(text: str):
    """Yield (line_number, line) for lines outside fenced code blocks."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield number, line


def check_links(path: Path, text: str) -> list[str]:
    problems: list[str] = []
    for number, line in prose_lines(text):
        for target in LINK_RE.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if "://" in target:
                continue
            file_part = unquote(target.split("#", 1)[0])
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                problems.append(f"line {number}: broken link -> {target}")
    return problems


def needs_class(rel: str) -> bool:
    if rel == "CONTEXT.md":
        return True
    parts = Path(rel).parts
    return len(parts) == 2 and parts[0] == "docs" and rel.endswith(".md")


def check_class(text: str) -> list[str]:
    head = text.splitlines()[:CLASS_HEADER_LINES]
    for line in head:
        stripped = line.lstrip()
        if stripped.startswith(">") and any(marker in stripped for marker in CLASS_MARKERS):
            return []
    return [
        "missing document class: no blockquote naming Product, "
        f"Implementation snapshot or Process in the first {CLASS_HEADER_LINES} lines"
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="accepted for CI symmetry; no effect")
    parser.parse_args(argv)

    files = tracked_markdown()
    problems: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        problems.extend(f"{rel}: {message}" for message in check_links(path, text))
        if needs_class(rel):
            problems.extend(f"{rel}: {message}" for message in check_class(text))

    for problem in problems:
        print(problem)
    if problems:
        print(f"check_docs: {len(problems)} problem(s) in {len(files)} files", file=sys.stderr)
        return 1
    print(f"check_docs: OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
