"""Loop-first public Interface for Research Harness.

The lower-level Run implementation remains importable from
``research_harness.harness`` for retained internal Adapters and regression
tests, but it is intentionally absent from this package's public exports.
"""

from .case import (
    Loop,
    LoopArtifact,
    LoopDetails,
    LoopFault,
    LoopInspection,
    LoopKind,
    LoopQuality,
    LoopQualitySignal,
    LoopQualityState,
    LoopResult,
    LoopState,
    Continue,
    Decide,
    PendingDecision,
    Start,
)

__version__ = "0.1.0"

__all__ = [
    "Loop",
    "LoopArtifact",
    "LoopDetails",
    "LoopFault",
    "LoopInspection",
    "LoopKind",
    "LoopQuality",
    "LoopQualitySignal",
    "LoopQualityState",
    "LoopResult",
    "LoopState",
    "Continue",
    "Decide",
    "PendingDecision",
    "Start",
]
