from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str


def has_placeholder_markers(text: str) -> bool:
    if not text:
        return False
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return True
    lowered = text.lower()
    return "(placeholder)" in lowered or "<!-- scaffold" in lowered
