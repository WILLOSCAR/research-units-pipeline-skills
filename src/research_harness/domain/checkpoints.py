"""Pure Checkpoint evidence normalization shared by Artifact Adapters."""

from __future__ import annotations

import re


def checkpoint_decisions_projection(
    text: str,
    *,
    checkpoint: str,
) -> tuple[str, bool]:
    """Return the review-bound Decision block and its single approval state."""

    block = re.search(
        rf"<!-- BEGIN CHECKPOINT:{re.escape(checkpoint)} -->(.*?)"
        rf"<!-- END CHECKPOINT:{re.escape(checkpoint)} -->",
        text,
        flags=re.DOTALL,
    )
    if block is None or not block.group(1).strip():
        return "", False
    approval_matches = tuple(
        re.finditer(
            rf"^(\s*-\s*)\[([ xX])\](\s*(?:Approve\s+)?{re.escape(checkpoint)}\b.*)$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )
    approval = "\n".join(
        f"{match.group(1)}[ ]{match.group(3)}" for match in approval_matches
    )
    approved = (
        len(approval_matches) == 1 and approval_matches[0].group(2).lower() == "x"
    )
    return f"{approval}\n{block.group(0).strip()}\n", approved
