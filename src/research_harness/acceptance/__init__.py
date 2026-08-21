"""Deterministic Workflow acceptance adapters.

The acceptance module depends only on the typed domain read model. Concrete
quality implementations enter through :class:`AcceptanceEvaluator`; they do
not need to expose legacy Run-state helpers to the Harness. The quality-check
backend enters through the :class:`QualityCheckProvider` Port. The default is
the transitional :class:`LegacyToolingQualityProvider`;
:class:`NativeQualityProvider` is the first tooling-free slice behind the same
Port (added but not yet the default).
"""

from .legacy_tooling import LegacyToolingQualityProvider, default_quality_provider
from .native import NativeQualityProvider
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
    "NativeQualityProvider",
    "QualityCheckProvider",
    "QualityIssueLike",
    "RepositoryQualityEvaluator",
    "WorkspaceResolver",
    "WorkflowAcceptancePolicy",
    "build_repository_acceptance_policy",
    "default_quality_provider",
]
