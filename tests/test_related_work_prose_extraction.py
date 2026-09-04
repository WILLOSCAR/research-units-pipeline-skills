"""Regression: related-work extraction reads prose "et al." citations.

A review (a manuscript that cites prior work only in a
prose Related Work section, with no `## References` bullet list) found
`extract_related_works` returned zero — it only read a References list — so a
paper that clearly named Yu/Kwon/Chen/Li/Zhao et al. got 0 related works and the
novelty scorecard hard-blocked. Verdict defective, conf 1.0.

`extract_related_works` now falls back to parsing "Surname et al." citations from
the Related Work section prose when no References list is present. The References
list path and the genuinely-no-related-work case are unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import extract_related_works


_PROSE_RW = """# Paper

## 2. Related Work
Prior work by Yu et al. and Kwon et al. studies batching. Chen et al., Li et al.,
and Zhao et al. also study serving throughput.

## 3. Limitations
One trace only.
"""

_LIST_RW = """# Paper

## Method
X.

## References
- Smith et al. A paper. 2020.
- Jones et al. Another. 2021.
"""

_NO_RW = """# Paper

## Abstract
We present X with no citations.

## Method
It works.
"""


def test_prose_et_al_citations_extracted() -> None:
    works = extract_related_works(_PROSE_RW)
    joined = " ".join(works)
    for name in ("Yu et al.", "Kwon et al.", "Chen et al.", "Li et al.", "Zhao et al."):
        assert name in joined, (name, works)
    # De-duplicated (each surname once).
    assert len(works) == len(set(w.lower() for w in works)), works


def test_references_list_path_unchanged() -> None:
    works = extract_related_works(_LIST_RW)
    assert any("Smith et al." in w for w in works), works
    assert any("Jones et al." in w for w in works), works


def test_genuinely_no_related_work_stays_empty() -> None:
    assert extract_related_works(_NO_RW) == []
