"""Deterministic Workflow acceptance adapters.

The acceptance module depends only on the typed domain read model. Concrete
quality implementations enter through :class:`AcceptanceEvaluator`; they do
not need to expose legacy Run-state helpers to the Harness. The quality-check
backend enters through the :class:`QualityCheckProvider` Port.

Provider selection (opt-in cutover seam)
----------------------------------------
:func:`default_quality_provider` is the single place that picks the backend.
It is legacy by default -- :class:`LegacyToolingQualityProvider`, the
transitional adapter over ``tooling.quality_gate`` -- so with no opt-in set,
behavior is byte-for-byte identical to before this seam existed.

Setting the ``RESEARCH_HARNESS_QUALITY_PROVIDER`` environment variable to
``native`` selects :class:`NativeQualityProvider` instead: the first
tooling-free slice behind the same Port. It answers registry introspection
and four self-contained output checks natively and delegates every other
check to the legacy adapter, so selecting it yields the same acceptance
outcomes for all Skills. Any other value -- unset, empty, or unrecognized --
resolves to legacy (parsing is deliberately defensive). Nothing wires native
as the default; flipping the cutover is a future, separately gated step.
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
