"""Regression: the tutorial Source-scope 'used for' list drops the source-title echo.

A read of a source-tutorial spec (docs/HARNESS_ROADMAP.md) found the Source
scope line "`s` (markdown) - Harness Roadmap - used for Harness Roadmap, ..." —
the "used for" concept list repeated the source title "Harness Roadmap" (the
title-candidate concept), which is already printed as the label, so it read as a
redundant echo.

`_source_scope_entry` now drops any concept whose title equals the source title
(case-insensitive) from the "used for" list, listing only distinct concepts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _source_scope_entry


def test_used_for_drops_source_title_echo() -> None:
    source = {"source_id": "s", "kind": "markdown", "title": "Harness Roadmap"}
    concepts = [
        {"title": "Harness Roadmap", "source_ids": ["s"]},  # echoes the source title
        {"title": "Horizon 3", "source_ids": ["s"]},
        {"title": "Deferred Or Rejected", "source_ids": ["s"]},
    ]
    entry = _source_scope_entry(source, concepts)
    # The label still shows the source title once...
    assert "- Harness Roadmap - used for" in entry, entry
    # ...but "used for" lists only distinct concepts, not the title echo.
    used_for = entry.split("used for", 1)[1]
    assert "Harness Roadmap" not in used_for, entry
    assert "Horizon 3" in used_for and "Deferred Or Rejected" in used_for, entry


def test_used_for_falls_back_to_general_context_when_only_title() -> None:
    source = {"source_id": "s", "kind": "markdown", "title": "Schemas"}
    concepts = [{"title": "Schemas", "source_ids": ["s"]}]  # only the title echo
    entry = _source_scope_entry(source, concepts)
    used_for = entry.split("used for", 1)[1]
    assert "general context" in used_for, entry
    assert "Schemas" not in used_for, entry


def test_used_for_case_insensitive_title_match() -> None:
    source = {"source_id": "s", "kind": "markdown", "title": "Pipeline Taxonomy"}
    concepts = [
        {"title": "pipeline taxonomy", "source_ids": ["s"]},  # different case
        {"title": "Loop Kinds", "source_ids": ["s"]},
    ]
    entry = _source_scope_entry(source, concepts)
    used_for = entry.split("used for", 1)[1]
    assert "pipeline taxonomy" not in used_for.lower().replace("pipeline taxonomy)", ""), entry
    assert "Loop Kinds" in used_for, entry
