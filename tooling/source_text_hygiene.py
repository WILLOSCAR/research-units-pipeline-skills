from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


LIMITATION_SIGNAL_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "limitation-signals.json"
)


@lru_cache(maxsize=1)
def limitation_signal_policy() -> dict[str, Any]:
    payload = json.loads(LIMITATION_SIGNAL_POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "limitation-signal-policy.v1":
        raise ValueError(
            f"Unsupported limitation signal policy: {payload.get('schema')!r}"
        )
    if not str(payload.get("negative_signal_pattern") or "").strip():
        raise ValueError("Limitation signal policy is missing negative_signal_pattern")
    if not isinstance(payload.get("negative_override_patterns"), list):
        raise ValueError("Limitation signal policy is missing negative_override_patterns")
    if not isinstance(payload.get("neutralization_patterns"), list):
        raise ValueError("Limitation signal policy is missing neutralization_patterns")
    return payload


@lru_cache(maxsize=1)
def _compiled_limitation_policy() -> tuple[
    re.Pattern[str],
    tuple[re.Pattern[str], ...],
    tuple[re.Pattern[str], ...],
]:
    policy = limitation_signal_policy()
    negative = re.compile(str(policy["negative_signal_pattern"]))
    overrides = tuple(
        re.compile(str(pattern))
        for pattern in policy["negative_override_patterns"]
        if str(pattern).strip()
    )
    neutralizers = tuple(
        re.compile(str(pattern))
        for pattern in policy["neutralization_patterns"]
        if str(pattern).strip()
    )
    return negative, overrides, neutralizers


def has_limitation_signal(text: str) -> bool:
    """Return whether text still carries a negative limitation after polarity cleanup."""

    candidate = re.sub(r"\s+", " ", str(text or "")).strip()
    if not candidate:
        return False
    negative, overrides, neutralizers = _compiled_limitation_policy()
    if any(pattern.search(candidate) for pattern in overrides):
        return True
    for pattern in neutralizers:
        candidate = pattern.sub(" ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    return bool(candidate and negative.search(candidate))
