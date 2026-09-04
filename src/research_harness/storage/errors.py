from __future__ import annotations

from research_harness.domain.errors import ErrorCode, HarnessError


class StorageError(RuntimeError):
    """Base class for failures at the durable local-storage seam."""


class StorageConfigurationError(StorageError):
    """The workspace or local platform cannot host durable storage safely."""


class StorageIOError(StorageError):
    """A filesystem operation failed before its durable result was known."""


class StorageCorruptionError(StorageError):
    """Persisted data is malformed, inconsistent, or unsafe to interpret."""


class StorageCodecError(StorageCorruptionError):
    """A versioned JSON payload cannot be decoded into the domain model."""


class StorageIdentityError(StorageCorruptionError):
    """A workspace contains a different canonical Run identity."""


class InvalidArtifactPathError(StorageError, ValueError):
    """An Artifact path is unsafe or cannot be fingerprinted deterministically."""


class ArtifactChangedError(StorageError):
    """An Artifact changed while a deterministic fingerprint was being taken."""


class ManifestConflictError(StorageCorruptionError):
    """A Manifest identity is already bound to different durable evidence."""


class ManifestNotFoundError(StorageError, KeyError):
    """A requested durable Completion Manifest does not exist."""


class InvalidManifestTransitionError(StorageError, ValueError):
    """A durable Manifest status transition is not permitted."""


class ConcurrentStorageInvocationError(HarnessError, StorageError):
    """Another process owns the non-blocking workspace invocation lock."""

    def __init__(self, *, run_id: str, operation: str) -> None:
        HarnessError.__init__(
            self,
            ErrorCode.CONCURRENT_INVOCATION,
            f"Run {run_id} is already executing another invocation.",
            run_id=run_id,
            details={"operation": operation},
        )


class ConcurrentStorageWriteError(HarnessError, StorageError):
    """The canonical aggregate did not have the expected version."""

    def __init__(self, message: str, *, run_id: str) -> None:
        HarnessError.__init__(
            self,
            ErrorCode.CONCURRENT_WRITE,
            message,
            run_id=run_id,
        )
