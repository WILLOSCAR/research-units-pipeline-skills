"""Regression: the tutorial's "Key idea" snippet is prose, not a table row.

`_best_snippet` scored candidate sentences by query-token overlap. A markdown
TABLE row packs many topic tokens onto one line, so it always outscored real
prose — the "Key idea" block rendered raw table markup like
"| Current workflow | Proof state | Open boundary | |---|---|---| | ...".

The selector now filters non-prose markdown (fenced code / mermaid, table rows,
headings) and only ranks prose sentences — while splitting WITHIN each
contiguous prose block so a candidate never bridges a removed block (keeping it
a contiguous substring of the raw provenance, which the grounding check needs).
A graceful fallback preserves the prior behavior when a source has no prose.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _best_snippet, _prose_blocks


_DOC = """# Title

The harness recomputes scorecards rather than trusting a declared pass.

| Requested outcome | Current workflow | Maturity |
|---|---|---|
| Orient to a topic | `research-brief` | Executed |
| Survey a field | `arxiv-survey` | Completed pilot |

```text
Goal -> Run -> Evidence -> Artifact
```

Evidence is the inward-facing, content-addressed intermediate that feeds the
next step and enables bounded local repair.
"""


def test_prose_blocks_drop_tables_and_code() -> None:
    blocks = "\n".join(_prose_blocks(_DOC))
    # Table rows and code fences are gone.
    assert "|" not in blocks
    assert "Goal -> Run -> Evidence" not in blocks
    # Real prose survives.
    assert "recomputes scorecards" in blocks
    assert "content-addressed intermediate" in blocks


def test_best_snippet_prefers_prose_over_table_row() -> None:
    # A query loaded with table tokens must still not select the table row.
    snippet = _best_snippet(_DOC, "requested outcome current workflow maturity survey field")
    assert "|" not in snippet, snippet
    assert "---" not in snippet, snippet
    # It selects an actual teaching sentence.
    assert snippet.endswith(".") or snippet.endswith(";"), snippet


def test_best_snippet_falls_back_when_no_prose() -> None:
    # A source that is ALL table/code still yields a non-empty snippet (the
    # grounding contract forbids empty), via the graceful fallback.
    table_only = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    snippet = _best_snippet(table_only, "a b")
    assert snippet != "", "fallback must not return empty for a table-only source"
