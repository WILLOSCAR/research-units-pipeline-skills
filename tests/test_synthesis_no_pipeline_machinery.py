"""Regression: the evidence-review SYNTHESIS prose exposes no pipeline machinery.

A read of a rendered SYNTHESIS.md found its prose foregrounded the
harness's own machinery to the reader: "follows the current protocol and only
reports what the extraction table supports", "The deterministic pass keeps
findings conservative", "the current extracted evidence clusters around", and
"richer extraction fields".

`render_evidence_synthesis_markdown` now uses reader-facing systematic-review
phrasing (conclusions the included studies support; findings kept conservative;
studies that report richer outcome data), while keeping the required section
headings (including the "## Extracted evidence table" contract label) intact.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.evidence_review_evaluation import REQUIRED_SYNTHESIS_SECTIONS
from tooling.review_render import render_evidence_synthesis_markdown

# Machinery / process vocabulary that must not appear in the reader-facing PROSE.
_BANNED_PROSE = (
    "deterministic pass",
    "extraction fields",
    "extraction table supports",
    "current extracted evidence",
    "follows the current protocol",
    "extracted evidence supports",
    "not present in the table",
)

_ROWS = [
    {"paper_id": "P0001", "title": "Clinical summarization with negation handling", "year": "2023",
     "population_or_setting": "MIMIC-III", "task": "clinical note summarization", "metric": "ROUGE-L",
     "study_type": "benchmark", "rob_overall": "low", "evidence_pointer": "abs/2301.1"},
    {"paper_id": "P0002", "title": "Ontology-guided content selection", "year": "2020",
     "population_or_setting": "MIMIC-CXR", "task": "clinical abstractive summarization", "metric": "factual F1",
     "study_type": "benchmark", "rob_overall": "unclear", "evidence_pointer": "abs/2007.2"},
]


def test_synthesis_prose_has_no_pipeline_machinery() -> None:
    md = render_evidence_synthesis_markdown(_ROWS)
    # Strip the fixed section-heading contract label before scanning the prose.
    prose = md.replace("## Extracted evidence table", "")
    low = prose.lower()
    for phrase in _BANNED_PROSE:
        assert phrase not in low, (phrase, prose)


def test_synthesis_keeps_required_section_contract() -> None:
    md = render_evidence_synthesis_markdown(_ROWS)
    for heading in REQUIRED_SYNTHESIS_SECTIONS:
        assert heading in md, heading


def test_synthesis_states_conservative_findings_in_reader_terms() -> None:
    md = render_evidence_synthesis_markdown(_ROWS)
    assert "the included studies directly support" in md, md
    assert "no effect is claimed beyond what the included studies report" in md, md
    assert "studies that report richer outcome data" in md, md
