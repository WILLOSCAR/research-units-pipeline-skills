from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Stable failure categories at the Harness interface."""

    INVALID_COMMAND = "invalid_command"
    RUN_EXISTS = "run_exists"
    RUN_NOT_FOUND = "run_not_found"
    UNIT_NOT_FOUND = "unit_not_found"
    ATTEMPT_NOT_FOUND = "attempt_not_found"
    CHECKPOINT_NOT_FOUND = "checkpoint_not_found"
    INVALID_TRANSITION = "invalid_transition"
    DEPENDENCIES_NOT_READY = "dependencies_not_ready"
    ACTIVE_ATTEMPT_EXISTS = "active_attempt_exists"
    REVISION_DRIFT = "revision_drift"
    RECOVERY_REQUIRED = "recovery_required"
    CONCURRENT_INVOCATION = "concurrent_invocation"
    CONCURRENT_WRITE = "concurrent_write"
    ADAPTER_FAILURE = "adapter_failure"


class HarnessError(RuntimeError):
    """Structured, fail-closed error raised by the Harness interface.

    Expected research-contract failures such as missing outputs or rejected
    acceptance are returned as ``CommandResult(outcome=BLOCKED)`` instead.
    ``HarnessError`` is reserved for invalid commands, unsafe transitions,
    revision/concurrency conflicts, and adapter failures.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        run_id: str = "",
        unit_id: str = "",
        attempt_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.run_id = run_id
        self.unit_id = unit_id
        self.attempt_id = attempt_id
        self.details = dict(details or {})

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"
