"""Deterministic Workflow acceptance adapters.

The acceptance module depends only on the typed domain read model. Concrete
quality implementations enter through :class:`AcceptanceEvaluator`; they do
not need to expose legacy Run-state helpers to the Harness. The quality-check
backend enters through the :class:`QualityCheckProvider` Port, whose sole
current implementation is the transitional
:class:`LegacyToolingQualityProvider`.
"""

from .legacy_tooling import LegacyToolingQualityProvider, default_quality_provider
from .policy import (
    AcceptanceEvaluator,
    AcceptanceRequest,
    WorkflowAcceptancePolicy,
)
from .quality_provider import QualityCheckProvider, QualityIssueLike
from .repository import (
    RepositoryQualityEvaluator,
    WorkspaceResolver,
    build_repository_acceptance_policy,
)

__all__ = [
    "AcceptanceEvaluator",
    "AcceptanceRequest",
    "LegacyToolingQualityProvider",
    "QualityCheckProvider",
    "QualityIssueLike",
    "RepositoryQualityEvaluator",
    "WorkspaceResolver",
    "WorkflowAcceptancePolicy",
    "build_repository_acceptance_policy",
    "default_quality_provider",
]
