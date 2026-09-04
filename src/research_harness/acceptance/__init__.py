"""Deterministic Workflow acceptance adapters.

The acceptance module depends only on the typed domain read model. Concrete
quality implementations enter through :class:`AcceptanceEvaluator`; they do
not need to expose legacy Run-state helpers to the Harness. The quality-check
backend enters through the :class:`QualityCheckProvider` Port.

Provider selection (opt-in cutover seam)
----------------------------------------
:func:`default_quality_provider` is the single place that picks the backend.
It is native by default -- :class:`NativeQualityProvider`, the tooling-free
implementation that reimplements every registered output check and the
completion invariant behind the same Port -- so with no opt-in set,
acceptance runs natively.

Setting the ``RESEARCH_HARNESS_QUALITY_PROVIDER`` environment variable to
``legacy`` selects :class:`LegacyToolingQualityProvider` instead: the
transitional adapter over ``tooling.quality_gate``, retained as a reversible
escape hatch. Any other value -- unset, empty, or unrecognized -- resolves to
native (parsing is deliberately defensive, so a typo can never silently
revert to the legacy path).
"""

from .legacy_tooling import (
    LegacyToolingPolicyReader,
    LegacyToolingQualityProvider,
    default_quality_provider,
    default_workspace_policy_reader,
)
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
from .workspace_policy import WorkspacePolicyPort

__all__ = [
    "AcceptanceEvaluator",
    "AcceptanceRequest",
    "LegacyToolingPolicyReader",
    "LegacyToolingQualityProvider",
    "NativeQualityProvider",
    "QualityCheckProvider",
    "QualityIssueLike",
    "RepositoryQualityEvaluator",
    "WorkspacePolicyPort",
    "WorkspaceResolver",
    "WorkflowAcceptancePolicy",
    "build_repository_acceptance_policy",
    "default_quality_provider",
    "default_workspace_policy_reader",
]
