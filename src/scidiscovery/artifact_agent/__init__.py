"""SciDiscovery immutable artifact and generic task control plane."""

from .audit import scan_orphans, verify_artifacts
from .runtime import ArtifactAgentRuntime, open_runtime, read_secret_file
from .schema import *
from .schema import __all__ as _schema_exports
from .service import ApprovalService, ArtifactService, ExecutionService, SecureIntakeService, TaskService
from .storage import (
    ArtifactIdentityConflictError,
    ArtifactReferenceError,
    CASConfigurationError,
    CASIntegrityError,
    ContentAddressedStore,
    IdempotencyConflictError,
    RegistryConfigurationError,
    SQLiteArtifactRegistry,
)

__all__ = [
    *_schema_exports,
    "ApprovalService",
    "ArtifactAgentRuntime",
    "ArtifactService",
    "ExecutionService",
    "ArtifactReferenceError",
    "ArtifactIdentityConflictError",
    "CASConfigurationError",
    "CASIntegrityError",
    "ContentAddressedStore",
    "IdempotencyConflictError",
    "RegistryConfigurationError",
    "SecureIntakeService",
    "TaskService",
    "SQLiteArtifactRegistry",
    "open_runtime",
    "read_secret_file",
    "scan_orphans",
    "verify_artifacts",
]
