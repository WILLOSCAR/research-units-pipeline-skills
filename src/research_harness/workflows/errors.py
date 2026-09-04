from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkflowContractIssue:
    """One actionable problem in a Workflow contract."""

    code: str
    message: str
    source: Path | None = None
    field: str = ""

    def __str__(self) -> str:
        location = ""
        if self.source is not None:
            location = str(self.source)
            if self.field:
                location = f"{location}:{self.field}"
        elif self.field:
            location = self.field
        prefix = f"{location}: " if location else ""
        return f"[{self.code}] {prefix}{self.message}"


class WorkflowContractError(ValueError):
    """Base error for a Workflow contract that cannot be compiled."""

    heading = "Workflow contract error"

    def __init__(self, issues: Iterable[WorkflowContractIssue]) -> None:
        collected = tuple(issues)
        if not collected:
            raise ValueError("WorkflowContractError requires at least one issue")
        self.issues = collected
        detail = "\n".join(f"- {issue}" for issue in collected)
        super().__init__(f"{self.heading} ({len(collected)} issue(s)):\n{detail}")

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(issue.code for issue in self.issues)


class WorkflowSourceError(WorkflowContractError):
    """A Pipeline or UNITS source cannot be located or read."""

    heading = "Workflow source error"


class WorkflowSyntaxError(WorkflowContractError):
    """A Pipeline frontmatter or UNITS CSV source is malformed."""

    heading = "Workflow syntax error"


class WorkflowValidationError(WorkflowContractError):
    """Parsed Pipeline and UNITS contracts disagree or violate invariants."""

    heading = "Workflow validation error"
