"""Runtime Execution Domain Models for Rig.

This module provides the foundational runtime domain models for Phase 1 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Runtimes are advisory execution providers, not authorities.
- Runtime actions NEVER directly mutate authority state.
- All runtime execution produces deterministic, replay-safe receipts.
- All models are pure deterministic dataclasses.
- All models are JSON-serializable.
- Explicit authority classification on all models.

file: src/rig/domain/runtime.py
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Placeholder Constants
# =============================================================================

PLACEHOLDER_UNKNOWN = "unknown"
PLACEHOLDER_UNAVAILABLE = "unavailable"
PLACEHOLDER_NOT_CREATED = "not_created"
PLACEHOLDER_NOT_RUN = "not_run"
PLACEHOLDER_NOT_PROOF = "not_proof"
PLACEHOLDER_ADVISORY_ONLY = "advisory_only"
PLACEHOLDER_NOT_AUTHORITATIVE = "not_authoritative"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
PLACEHOLDER_NO_CAPABILITY = "no_capability"
PLACEHOLDER_NO_PROVIDER = "no_provider"

# All runtime-specific placeholders
REQUIRED_RUNTIME_PLACEHOLDERS = (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NOT_CREATED,
    PLACEHOLDER_NOT_RUN,
    PLACEHOLDER_NOT_PROOF,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_NO_CAPABILITY,
    PLACEHOLDER_NO_PROVIDER,
)


# =============================================================================
# Enums
# =============================================================================

class RuntimeProviderKind(Enum):
    """Kinds of runtime providers."""
    LOCAL = "local"              # Local process execution (llama.cpp, MLX, etc.)
    CLI = "cli"                # CLI-based providers (gemini, openai, etc.)
    CUSTOM = "custom"            # Custom/builtin providers
    DRY_RUN = "dry_run"          # Dry-run providers (no actual execution)
    STUB = "stub"                # Stub providers for testing


class RuntimeProviderTrustTier(Enum):
    """Trust tiers for runtime providers.
    
    Lower tiers have fewer permissions. Higher tiers have more capabilities.
    This is advisory - Rig remains the final authority.
    """
    BLOCKED = "blocked"              # No execution allowed
    ADVISORY = "advisory"            # Advisory only, proposals not executed
    REVIEWER = "reviewer"            # Can review, proposals require validation
    PLANNER = "planner"              # Can plan, proposals require review
    EXECUTOR_CANDIDATE = "executor_candidate"  # Can execute with explicit approval
    VALIDATOR = "validator"            # Can execute and validate


class RuntimeProviderStatus(Enum):
    """Operational status of a runtime provider."""
    AVAILABLE = "available"          # Ready for use
    UNAVAILABLE = "unavailable"      # Not currently available
    DEGRADED = "degraded"            # Available but with limited functionality
    BLOCKED = "blocked"              # Administratively blocked
    ERROR = "error"                  # In error state


class RuntimeCapabilityKind(Enum):
    """Kinds of runtime capabilities."""
    FILE_READ = "file_read"                # Read file contents
    FILE_WRITE_PROPOSAL = "file_write_proposal"  # Propose file writes
    SHELL_PROPOSAL = "shell_proposal"        # Propose shell commands
    PATCH_PROPOSAL = "patch_proposal"        # Propose patch changes
    REPLAY_ACCESS = "replay_access"          # Access replay history
    NETWORK_FETCH_PROPOSAL = "network_fetch_proposal"  # Propose network fetches
    DOCS_FETCH_PROPOSAL = "docs_fetch_proposal"  # Propose documentation fetches
    TELEMETRY_EXPORT_PROPOSAL = "telemetry_export_proposal"  # Propose telemetry export


class RuntimeCapabilityScope(Enum):
    """Scope of a runtime capability."""
    GLOBAL = "global"              # Applies to all workspaces
    WORKSPACE = "workspace"          # Applies to a specific workspace
    SESSION = "session"              # Applies to a specific session
    REQUEST = "request"              # Applies to a specific request


class RuntimeInvocationStatus(Enum):
    """Status of a runtime invocation."""
    PENDING = "pending"              # Not yet started
    STARTING = "starting"            # Starting up
    RUNNING = "running"              # Currently executing
    SUCCEEDED = "succeeded"          # Completed successfully
    FAILED = "failed"                # Failed with error
    TIMED_OUT = "timed_out"          # Timed out
    CANCELLED = "cancelled"          # Cancelled before completion
    BLOCKED = "blocked"              # Blocked by capability check


class RuntimeProposalStatus(Enum):
    """Status of a runtime proposal."""
    DRAFT = "draft"                  # Proposal in draft state
    SUBMITTED = "submitted"          # Submitted for review
    VALIDATED = "validated"          # Passed capability validation
    REJECTED = "rejected"            # Rejected by capability check
    BLOCKED = "blocked"              # Blocked by policy
    EXPIRED = "expired"              # Proposal expired


class RuntimeProposalDecision(Enum):
    """Decision on a runtime proposal."""
    ALLOW = "allow"                  # Proposal allowed
    DENY = "deny"                    # Proposal denied
    REVIEW = "review"                # Proposal requires review
    PENDING = "pending"              # Decision pending
    ADVISORY = "advisory"            # Advisory only


class RuntimeConstraintKind(Enum):
    """Kinds of runtime constraints."""
    TRUST_TIER = "trust_tier"        # Minimum trust tier required
    CAPABILITY = "capability"        # Specific capability required
    WORKSPACE = "workspace"          # Workspace-specific constraint
    TIMEOUT = "timeout"              # Maximum execution time
    MEMORY = "memory"                # Maximum memory usage
    CPU = "cpu"                      # Maximum CPU usage
    NETWORK = "network"              # Network access constraint
    FILESYSTEM = "filesystem"        # Filesystem access constraint


class RuntimeConstraintMode(Enum):
    """Mode of a runtime constraint."""
    REQUIRED = "required"            # Constraint must be satisfied
    OPTIONAL = "optional"            # Constraint is optional
    PROHIBITED = "prohibited"        # Constraint explicitly prohibited


class RuntimeDecisionKind(Enum):
    """Kinds of runtime decisions."""
    CAPABILITY_CHECK = "capability_check"    # Capability availability check
    TRUST_VALIDATION = "trust_validation"   # Trust tier validation
    CONSTRAINT_ENFORCEMENT = "constraint_enforcement"  # Constraint enforcement
    PROPOSAL_APPROVAL = "proposal_approval"   # Proposal approval decision
    EXECUTION_AUTHORIZATION = "execution_authorization"  # Execution authorization


class RuntimeStateKind(Enum):
    """Kinds of runtime state."""
    IDLE = "idle"                    # No active invocations
    ACTIVE = "active"                # One or more active invocations
    BLOCKED = "blocked"              # Blocked state (no new invocations)
    DEGRADED = "degraded"            # Degraded state (limited functionality)
    MAINTENANCE = "maintenance"      # Maintenance mode


class RuntimeBenchmarkKind(Enum):
    """Kinds of runtime benchmarks."""
    LATENCY = "latency"              # Execution latency
    TOKEN_THROUGHPUT = "token_throughput"  # Token processing rate
    PROPOSAL_SUCCESS = "proposal_success"  # Proposal success rate
    VALIDATION_PASS = "validation_pass"    # Validation pass rate
    REPLAY_INTEGRITY = "replay_integrity"  # Replay integrity compatibility


class RuntimeFailureCategory(Enum):
    """Categories of runtime failures."""
    CAPABILITY_MISMATCH = "capability_mismatch"  # Required capability not available
    TRUST_VIOLATION = "trust_violation"    # Trust tier violation
    CONSTRAINT_VIOLATION = "constraint_violation"  # Constraint violation
    EXECUTION_ERROR = "execution_error"    # Execution failed
    TIMEOUT = "timeout"                # Execution timed out
    NETWORK_ERROR = "network_error"      # Network error
    IO_ERROR = "io_error"                # I/O error
    VALIDATION_ERROR = "validation_error"  # Validation failed
    AUTHORITY_VIOLATION = "authority_violation"  # Attempted authority mutation


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_deterministic_id(prefix: str, *components: Any) -> str:
    """Generate a deterministic ID from components."""
    parts = [str(prefix)] + [str(c) for c in components]
    combined = "|".join(parts)
    return f"{prefix}_{hashlib.sha256(combined.encode()).hexdigest()[:16]}"


def _utc_now() -> str:
    """Get current UTC time as ISO format string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_enum(enum_val: Enum) -> str:
    """Serialize an enum to its value."""
    return enum_val.value if enum_val else PLACEHOLDER_UNKNOWN


def _serialize_optional_enum(enum_val: Optional[Enum]) -> Optional[str]:
    """Serialize an optional enum to its value or None."""
    return enum_val.value if enum_val else None


# =============================================================================
# Runtime Provider Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeProvider:
    """Represents a runtime provider.
    
    A runtime provider is an execution environment that can run models
    and produce proposals. Providers are advisory - they do not have
    authority to mutate state directly.
    
    Properties:
    - frozen dataclass: immutable
    - deterministic serialization
    - explicit authority classification (advisory_only=True)
    - replay-safe
    - projection-safe
    
    Attributes:
        provider_id: Unique identifier for the provider
        kind: The kind of provider
        trust_tier: The trust tier of the provider
        version: Provider version
        executable: Executable name or path
        offline_capable: Whether provider works offline
        supports_streaming: Whether provider supports streaming output
        supports_structured_output: Whether provider supports structured output
        can_modify_files: Provider capability to modify files (proposals only)
        rig_allows_file_mutation: Whether Rig allows file mutation from this provider
        supported_tasks: List of supported task types
        authoritative: ALWAYS False - providers are advisory only
        advisory_only: ALWAYS True - providers only propose, never execute authority
    """
    provider_id: str
    kind: RuntimeProviderKind = RuntimeProviderKind.CUSTOM
    trust_tier: RuntimeProviderTrustTier = RuntimeProviderTrustTier.ADVISORY
    version: str = PLACEHOLDER_UNKNOWN
    executable: str = PLACEHOLDER_UNAVAILABLE
    offline_capable: bool = False
    supports_streaming: bool = False
    supports_structured_output: bool = True
    can_modify_files: bool = False
    rig_allows_file_mutation: bool = False  # Rig policy: never allow direct mutation
    supported_tasks: List[str] = field(default_factory=list)
    status: RuntimeProviderStatus = RuntimeProviderStatus.UNAVAILABLE
    authoritative: bool = False  # Providers are NEVER authoritative
    advisory_only: bool = True  # Providers are ALWAYS advisory only
    manifest_hash: Optional[str] = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    
    def __post_init__(self):
        # Ensure invariant: providers are never authoritative
        object.__setattr__(self, 'authoritative', False)
        object.__setattr__(self, 'advisory_only', True)
        # Ensure invariant: rig never allows direct file mutation from providers
        object.__setattr__(self, 'rig_allows_file_mutation', False)
    
    @classmethod
    def dry_run(cls) -> "RuntimeProvider":
        """Create a dry-run provider for testing."""
        return cls(
            provider_id="dry_run",
            kind=RuntimeProviderKind.DRY_RUN,
            trust_tier=RuntimeProviderTrustTier.ADVISORY,
            version="1.0.0",
            executable="dry-run",
            offline_capable=True,
            supports_streaming=False,
            supports_structured_output=True,
            can_modify_files=False,
            supported_tasks=["dry_run", "validate"],
            status=RuntimeProviderStatus.AVAILABLE,
            manifest_hash=_generate_deterministic_id("provider", "dry_run", "1.0.0"),
        )
    
    @classmethod
    def custom_command(cls) -> "RuntimeProvider":
        """Create a custom command provider."""
        return cls(
            provider_id="custom-command",
            kind=RuntimeProviderKind.CUSTOM,
            trust_tier=RuntimeProviderTrustTier.PLANNER,
            version="1.0.0",
            executable="built-in",
            offline_capable=True,
            supports_streaming=False,
            supports_structured_output=True,
            can_modify_files=False,
            supported_tasks=["proposal", "decode", "inspect"],
            status=RuntimeProviderStatus.AVAILABLE,
            manifest_hash=_generate_deterministic_id("provider", "custom-command", "1.0.0"),
        )
    
    @classmethod
    def from_manifest(cls, manifest: Dict[str, Any]) -> "RuntimeProvider":
        """Create a RuntimeProvider from a manifest dictionary."""
        provider_id = manifest.get("provider_id", PLACEHOLDER_NO_PROVIDER)
        kind_str = manifest.get("kind", "custom")
        trust_tier_str = manifest.get("trust_tier", "advisory")
        
        try:
            kind = RuntimeProviderKind(kind_str)
        except ValueError:
            kind = RuntimeProviderKind.CUSTOM
        
        try:
            trust_tier = RuntimeProviderTrustTier(trust_tier_str)
        except ValueError:
            trust_tier = RuntimeProviderTrustTier.ADVISORY
        
        return cls(
            provider_id=provider_id,
            kind=kind,
            trust_tier=trust_tier,
            version=manifest.get("version", PLACEHOLDER_UNKNOWN),
            executable=manifest.get("executable", PLACEHOLDER_UNAVAILABLE),
            offline_capable=manifest.get("offline_capable", False),
            supports_streaming=manifest.get("supports_streaming", False),
            supports_structured_output=manifest.get("supports_structured_output", True),
            can_modify_files=manifest.get("can_modify_files", False),
            supported_tasks=manifest.get("supported_tasks", []),
            status=RuntimeProviderStatus.AVAILABLE if manifest.get("available", True) else RuntimeProviderStatus.UNAVAILABLE,
            manifest_hash=manifest.get("manifest_hash"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["kind"] = self.kind.value
        d["trust_tier"] = self.trust_tier.value
        d["status"] = self.status.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeProvider":
        """Deserialize from dictionary."""
        return cls(
            provider_id=d.get("provider_id", PLACEHOLDER_NO_PROVIDER),
            kind=RuntimeProviderKind(d.get("kind", "custom")),
            trust_tier=RuntimeProviderTrustTier(d.get("trust_tier", "advisory")),
            version=d.get("version", PLACEHOLDER_UNKNOWN),
            executable=d.get("executable", PLACEHOLDER_UNAVAILABLE),
            offline_capable=d.get("offline_capable", False),
            supports_streaming=d.get("supports_streaming", False),
            supports_structured_output=d.get("supports_structured_output", True),
            can_modify_files=d.get("can_modify_files", False),
            supported_tasks=d.get("supported_tasks", []),
            status=RuntimeProviderStatus(d.get("status", "unavailable")),
            manifest_hash=d.get("manifest_hash"),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
        )


# =============================================================================
# Runtime Capability Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    """Represents a runtime capability.
    
    A capability defines what a runtime provider is allowed to do.
    Capabilities are governed and verified by Rig before any execution.
    
    Critical: Capabilities DO NOT execute authority directly.
    They authorize proposal generation only.
    
    Attributes:
        capability_id: Unique identifier for the capability
        kind: The kind of capability
        scope: The scope of the capability
        workspace_id: Optional workspace-specific capability
        allowed_providers: Set of provider IDs that have this capability
        constraints: List of constraints on this capability
        requires_validation: Whether capability requires validation
        requires_review: Whether capability requires review
        advisory_only: Whether this capability is advisory only
    """
    capability_id: str
    kind: RuntimeCapabilityKind = RuntimeCapabilityKind.FILE_READ
    scope: RuntimeCapabilityScope = RuntimeCapabilityScope.GLOBAL
    workspace_id: Optional[str] = None
    allowed_providers: FrozenSet[str] = field(default_factory=frozenset)
    constraints: List[str] = field(default_factory=list)  # Constraint IDs
    requires_validation: bool = True
    requires_review: bool = False
    advisory_only: bool = True  # Capabilities are advisory - proposals only
    description: str = ""
    created_at: str = field(default_factory=_utc_now)
    
    def __post_init__(self):
        # Ensure invariant: capabilities are always advisory only
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def file_read(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a file read capability."""
        cap_id = _generate_deterministic_id("cap", "file_read", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.FILE_READ,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=False,
            requires_review=False,
            advisory_only=True,
            description="Read file contents",
        )
    
    @classmethod
    def file_write_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a file write proposal capability."""
        cap_id = _generate_deterministic_id("cap", "file_write_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.FILE_WRITE_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,  # Proposals only, never direct writes
            description="Propose file write operations",
        )
    
    @classmethod
    def shell_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a shell command proposal capability."""
        cap_id = _generate_deterministic_id("cap", "shell_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.SHELL_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,
            description="Propose shell command execution",
        )
    
    @classmethod
    def patch_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a patch proposal capability."""
        cap_id = _generate_deterministic_id("cap", "patch_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.PATCH_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,
            description="Propose patch changes",
        )
    
    @classmethod
    def replay_access(cls) -> "RuntimeCapability":
        """Create a replay access capability."""
        return cls(
            capability_id=_generate_deterministic_id("cap", "replay_access", "global"),
            kind=RuntimeCapabilityKind.REPLAY_ACCESS,
            scope=RuntimeCapabilityScope.GLOBAL,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=False,
            requires_review=False,
            advisory_only=True,
            description="Access replay history and timelines",
        )
    
    @classmethod
    def network_fetch_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a network fetch proposal capability."""
        cap_id = _generate_deterministic_id("cap", "network_fetch_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,
            description="Propose network fetch operations",
        )
    
    @classmethod
    def docs_fetch_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a documentation fetch proposal capability."""
        cap_id = _generate_deterministic_id("cap", "docs_fetch_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.DOCS_FETCH_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,
            description="Propose documentation fetch operations",
        )
    
    @classmethod
    def telemetry_export_proposal(cls, workspace_id: Optional[str] = None) -> "RuntimeCapability":
        """Create a telemetry export proposal capability."""
        cap_id = _generate_deterministic_id("cap", "telemetry_export_proposal", workspace_id or "global")
        return cls(
            capability_id=cap_id,
            kind=RuntimeCapabilityKind.TELEMETRY_EXPORT_PROPOSAL,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            allowed_providers=frozenset(["custom-command", "dry_run"]),
            requires_validation=True,
            requires_review=True,
            advisory_only=True,
            description="Propose telemetry export operations",
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "capability_id": self.capability_id,
            "kind": self.kind.value,
            "scope": self.scope.value,
            "workspace_id": self.workspace_id,
            "allowed_providers": list(self.allowed_providers),
            "constraints": self.constraints,
            "requires_validation": self.requires_validation,
            "requires_review": self.requires_review,
            "advisory_only": self.advisory_only,
            "description": self.description,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeCapability":
        """Deserialize from dictionary."""
        return cls(
            capability_id=d.get("capability_id", _generate_deterministic_id("cap", "unknown")),
            kind=RuntimeCapabilityKind(d.get("kind", "file_read")),
            scope=RuntimeCapabilityScope(d.get("scope", "global")),
            workspace_id=d.get("workspace_id"),
            allowed_providers=frozenset(d.get("allowed_providers", [])),
            constraints=d.get("constraints", []),
            requires_validation=d.get("requires_validation", True),
            requires_review=d.get("requires_review", False),
            advisory_only=d.get("advisory_only", True),
            description=d.get("description", ""),
            created_at=d.get("created_at", _utc_now()),
        )


# =============================================================================
# Runtime Constraint Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeConstraint:
    """Represents a runtime constraint.
    
    Constraints limit what runtime providers can do. They are enforced
    before any execution is allowed.
    
    Attributes:
        constraint_id: Unique identifier for the constraint
        kind: The kind of constraint
        mode: The constraint mode (required/optional/prohibited)
        value: The constraint value (e.g., minimum trust tier, timeout seconds)
        scope: The scope of the constraint
        workspace_id: Optional workspace-specific constraint
        applies_to: Set of capability kinds this constraint applies to
    """
    constraint_id: str
    kind: RuntimeConstraintKind = RuntimeConstraintKind.TRUST_TIER
    mode: RuntimeConstraintMode = RuntimeConstraintMode.REQUIRED
    value: Any = None
    scope: RuntimeCapabilityScope = RuntimeCapabilityScope.GLOBAL
    workspace_id: Optional[str] = None
    applies_to: FrozenSet[RuntimeCapabilityKind] = field(default_factory=frozenset)
    description: str = ""
    created_at: str = field(default_factory=_utc_now)
    
    @classmethod
    def trust_tier_minimum(
        cls, 
        minimum_tier: RuntimeProviderTrustTier,
        workspace_id: Optional[str] = None
    ) -> "RuntimeConstraint":
        """Create a minimum trust tier constraint."""
        constraint_id = _generate_deterministic_id(
            "constraint", "trust_tier", minimum_tier.value, workspace_id or "global"
        )
        return cls(
            constraint_id=constraint_id,
            kind=RuntimeConstraintKind.TRUST_TIER,
            mode=RuntimeConstraintMode.REQUIRED,
            value=minimum_tier.value,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            applies_to=frozenset([
                RuntimeCapabilityKind.FILE_WRITE_PROPOSAL,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.PATCH_PROPOSAL,
                RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL,
            ]),
            description=f"Minimum trust tier: {minimum_tier.value}",
        )
    
    @classmethod
    def timeout_maximum(
        cls,
        max_seconds: float,
        workspace_id: Optional[str] = None
    ) -> "RuntimeConstraint":
        """Create a maximum timeout constraint."""
        constraint_id = _generate_deterministic_id(
            "constraint", "timeout", str(max_seconds), workspace_id or "global"
        )
        return cls(
            constraint_id=constraint_id,
            kind=RuntimeConstraintKind.TIMEOUT,
            mode=RuntimeConstraintMode.REQUIRED,
            value=max_seconds,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            applies_to=frozenset([RuntimeCapabilityKind(k) for k in RuntimeCapabilityKind]),
            description=f"Maximum execution timeout: {max_seconds}s",
        )
    
    @classmethod
    def no_network(cls, workspace_id: Optional[str] = None) -> "RuntimeConstraint":
        """Create a no-network constraint."""
        constraint_id = _generate_deterministic_id(
            "constraint", "network", "prohibited", workspace_id or "global"
        )
        return cls(
            constraint_id=constraint_id,
            kind=RuntimeConstraintKind.NETWORK,
            mode=RuntimeConstraintMode.PROHIBITED,
            value=False,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            applies_to=frozenset([RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL]),
            description="Network access prohibited",
        )
    
    @classmethod
    def no_filesystem_writes(cls, workspace_id: Optional[str] = None) -> "RuntimeConstraint":
        """Create a no-filesystem-writes constraint."""
        constraint_id = _generate_deterministic_id(
            "constraint", "filesystem", "no_writes", workspace_id or "global"
        )
        return cls(
            constraint_id=constraint_id,
            kind=RuntimeConstraintKind.FILESYSTEM,
            mode=RuntimeConstraintMode.PROHIBITED,
            value=False,
            scope=RuntimeCapabilityScope.WORKSPACE if workspace_id else RuntimeCapabilityScope.GLOBAL,
            workspace_id=workspace_id,
            applies_to=frozenset([
                RuntimeCapabilityKind.FILE_WRITE_PROPOSAL,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.PATCH_PROPOSAL,
            ]),
            description="Filesystem writes prohibited",
        )
    
    def applies_to_capability(self, capability: RuntimeCapability) -> bool:
        """Check if this constraint applies to a given capability."""
        if self.scope == RuntimeCapabilityScope.WORKSPACE:
            if self.workspace_id != capability.workspace_id:
                return False
        return capability.kind in self.applies_to
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "constraint_id": self.constraint_id,
            "kind": self.kind.value,
            "mode": self.mode.value,
            "value": self.value,
            "scope": self.scope.value,
            "workspace_id": self.workspace_id,
            "applies_to": [k.value for k in self.applies_to],
            "description": self.description,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeConstraint":
        """Deserialize from dictionary."""
        applies_to = set()
        for kind_str in d.get("applies_to", []):
            try:
                applies_to.add(RuntimeCapabilityKind(kind_str))
            except ValueError:
                pass
        
        return cls(
            constraint_id=d.get("constraint_id", _generate_deterministic_id("constraint", "unknown")),
            kind=RuntimeConstraintKind(d.get("kind", "trust_tier")),
            mode=RuntimeConstraintMode(d.get("mode", "required")),
            value=d.get("value"),
            scope=RuntimeCapabilityScope(d.get("scope", "global")),
            workspace_id=d.get("workspace_id"),
            applies_to=frozenset(applies_to),
            description=d.get("description", ""),
            created_at=d.get("created_at", _utc_now()),
        )


# =============================================================================
# Runtime Invocation Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeInvocation:
    """Represents a runtime invocation.
    
    An invocation is a request to a runtime provider to execute a task.
    Invocations are tracked for audit and replay purposes.
    
    Critical: Invocations NEVER directly mutate authority state.
    They produce proposals that must be reviewed and validated.
    
    Attributes:
        invocation_id: Unique identifier for the invocation
        provider_id: The runtime provider being invoked
        model_id: The model identifier
        capability_ids: Set of capability IDs being used
        request: The invocation request payload
        status: Current status of the invocation
        started_at: When the invocation started
        completed_at: When the invocation completed
        exit_code: Exit code if applicable
        raw_output: Raw output from the provider
        error_message: Error message if failed
    """
    invocation_id: str
    provider_id: str = PLACEHOLDER_NO_PROVIDER
    model_id: str = PLACEHOLDER_UNKNOWN
    capability_ids: FrozenSet[str] = field(default_factory=frozenset)
    request: Dict[str, Any] = field(default_factory=dict)
    status: RuntimeInvocationStatus = RuntimeInvocationStatus.PENDING
    started_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None
    exit_code: Optional[int] = None
    raw_output: str = ""
    error_message: str = ""
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    advisory_only: bool = True  # Invocations are always advisory only
    
    def __post_init__(self):
        # Ensure invariant: invocations are always advisory only
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        provider_id: str,
        model_id: str,
        request: Dict[str, Any],
        capability_ids: Optional[FrozenSet[str]] = None,
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        status: RuntimeInvocationStatus = RuntimeInvocationStatus.STARTING,
    ) -> "RuntimeInvocation":
        """Create a new runtime invocation."""
        invocation_id = _generate_deterministic_id(
            "invocation",
            provider_id,
            model_id,
            json.dumps(request, sort_keys=True, default=str),
        )
        return cls(
            invocation_id=invocation_id,
            provider_id=provider_id,
            model_id=model_id,
            capability_ids=capability_ids or frozenset(),
            request=request,
            status=status,
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "invocation_id": self.invocation_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "capability_ids": list(self.capability_ids),
            "request": self.request,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "exit_code": self.exit_code,
            "raw_output": self.raw_output,
            "error_message": self.error_message,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "advisory_only": self.advisory_only,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeInvocation":
        """Deserialize from dictionary."""
        return cls(
            invocation_id=d.get("invocation_id", _generate_deterministic_id("invocation", "unknown")),
            provider_id=d.get("provider_id", PLACEHOLDER_NO_PROVIDER),
            model_id=d.get("model_id", PLACEHOLDER_UNKNOWN),
            capability_ids=frozenset(d.get("capability_ids", [])),
            request=d.get("request", {}),
            status=RuntimeInvocationStatus(d.get("status", "pending")),
            started_at=d.get("started_at", _utc_now()),
            completed_at=d.get("completed_at"),
            exit_code=d.get("exit_code"),
            raw_output=d.get("raw_output", ""),
            error_message=d.get("error_message", ""),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Proposal Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeProposal:
    """Represents a runtime proposal.
    
    A proposal is the output of a runtime invocation. It describes
    what the runtime wants to do, but does NOT execute it directly.
    
    Critical: Proposals NEVER directly mutate authority state.
    They must go through Rig's validation and approval workflow.
    
    Attributes:
        proposal_id: Unique identifier for the proposal
        invocation_id: The invocation that generated this proposal
        provider_id: The runtime provider that generated this proposal
        model_id: The model identifier
        capability_ids: Set of capability IDs used
        proposal_kind: The kind of proposal (e.g., "command", "patch", "fetch")
        payload: The proposal payload (structured data)
        status: Current status of the proposal
        decision: The decision on this proposal
        validation_errors: List of validation errors if any
        created_at: When the proposal was created
    """
    proposal_id: str
    invocation_id: str = PLACEHOLDER_NO_RECEIPT
    provider_id: str = PLACEHOLDER_NO_PROVIDER
    model_id: str = PLACEHOLDER_UNKNOWN
    capability_ids: FrozenSet[str] = field(default_factory=frozenset)
    proposal_kind: str = PLACEHOLDER_UNKNOWN
    payload: Dict[str, Any] = field(default_factory=dict)
    status: RuntimeProposalStatus = RuntimeProposalStatus.DRAFT
    decision: RuntimeProposalDecision = RuntimeProposalDecision.PENDING
    validation_errors: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    advisory_only: bool = True  # Proposals are always advisory only
    authoritative: bool = False  # Proposals are never authoritative
    
    def __post_init__(self):
        # Ensure invariants: proposals are always advisory, never authoritative
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def from_invocation(
        cls,
        invocation: RuntimeInvocation,
        proposal_kind: str,
        payload: Dict[str, Any],
    ) -> "RuntimeProposal":
        """Create a proposal from an invocation."""
        proposal_id = _generate_deterministic_id(
            "proposal",
            invocation.invocation_id,
            proposal_kind,
            json.dumps(payload, sort_keys=True, default=str),
        )
        return cls(
            proposal_id=proposal_id,
            invocation_id=invocation.invocation_id,
            provider_id=invocation.provider_id,
            model_id=invocation.model_id,
            capability_ids=invocation.capability_ids,
            proposal_kind=proposal_kind,
            payload=payload,
            status=RuntimeProposalStatus.SUBMITTED,
            workspace_id=invocation.workspace_id,
            actor_id=invocation.actor_id,
        )
    
    @classmethod
    def file_write(
        cls,
        invocation: RuntimeInvocation,
        file_path: str,
        content: str,
        mode: str = "overwrite",
    ) -> "RuntimeProposal":
        """Create a file write proposal."""
        payload = {
            "action": "write",
            "file_path": file_path,
            "content": content,
            "mode": mode,
        }
        return cls.from_invocation(
            invocation=invocation,
            proposal_kind="file_write",
            payload=payload,
        )
    
    @classmethod
    def shell_command(
        cls,
        invocation: RuntimeInvocation,
        argv: List[str],
        cwd: Optional[str] = None,
    ) -> "RuntimeProposal":
        """Create a shell command proposal."""
        payload = {
            "action": "shell",
            "argv": argv,
            "cwd": cwd,
        }
        return cls.from_invocation(
            invocation=invocation,
            proposal_kind="shell",
            payload=payload,
        )
    
    @classmethod
    def patch(
        cls,
        invocation: RuntimeInvocation,
        file_path: str,
        diff: str,
    ) -> "RuntimeProposal":
        """Create a patch proposal."""
        payload = {
            "action": "patch",
            "file_path": file_path,
            "diff": diff,
        }
        return cls.from_invocation(
            invocation=invocation,
            proposal_kind="patch",
            payload=payload,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "invocation_id": self.invocation_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "capability_ids": list(self.capability_ids),
            "proposal_kind": self.proposal_kind,
            "payload": self.payload,
            "status": self.status.value,
            "decision": self.decision.value,
            "validation_errors": self.validation_errors,
            "created_at": self.created_at,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeProposal":
        """Deserialize from dictionary."""
        return cls(
            proposal_id=d.get("proposal_id", _generate_deterministic_id("proposal", "unknown")),
            invocation_id=d.get("invocation_id", PLACEHOLDER_NO_RECEIPT),
            provider_id=d.get("provider_id", PLACEHOLDER_NO_PROVIDER),
            model_id=d.get("model_id", PLACEHOLDER_UNKNOWN),
            capability_ids=frozenset(d.get("capability_ids", [])),
            proposal_kind=d.get("proposal_kind", PLACEHOLDER_UNKNOWN),
            payload=d.get("payload", {}),
            status=RuntimeProposalStatus(d.get("status", "draft")),
            decision=RuntimeProposalDecision(d.get("decision", "pending")),
            validation_errors=d.get("validation_errors", []),
            created_at=d.get("created_at", _utc_now()),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )


# =============================================================================
# Runtime Execution Receipt Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeExecutionReceipt:
    """Canonical receipt for runtime execution.
    
    Records evidence of a runtime execution, including:
    - Provider and model information
    - Capability set used
    - Invocation metadata
    - Proposal metadata
    - Execution duration
    - Token/usage metadata
    - Replay references
    - Integrity flags
    - Advisory status
    
    Receipts are:
    - Replay-compatible
    - Integrity-compatible
    - Projection-compatible
    - Audit-compatible
    
    Critical: Runtime execution receipts NEVER indicate direct authority mutation.
    They are advisory records of execution that produced proposals.
    """
    receipt_id: str
    kind: str = "runtime_execution"  # Receipt kind
    
    # Provider information
    provider_id: str = PLACEHOLDER_NO_PROVIDER
    provider_kind: RuntimeProviderKind = RuntimeProviderKind.CUSTOM
    model_id: str = PLACEHOLDER_UNKNOWN
    provider_trust_tier: RuntimeProviderTrustTier = RuntimeProviderTrustTier.ADVISORY
    
    # Capability information
    capability_ids: FrozenSet[str] = field(default_factory=frozenset)
    capability_kinds: FrozenSet[RuntimeCapabilityKind] = field(default_factory=frozenset)
    
    # Invocation metadata
    invocation_id: str = PLACEHOLDER_NO_RECEIPT
    invocation_status: RuntimeInvocationStatus = RuntimeInvocationStatus.PENDING
    
    # Proposal metadata
    proposal_ids: FrozenSet[str] = field(default_factory=frozenset)
    proposal_count: int = 0
    
    # Execution metadata
    status: str = "unknown"  # "started", "success", "failed", "cancelled"
    exit_code: Optional[int] = None
    started_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Token/usage metadata
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    
    # Output references
    raw_output_ref: Optional[str] = None
    raw_output_summary: str = ""
    
    # Context
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    purpose: str = ""
    
    # Integrity and replay
    replay_refs: List[str] = field(default_factory=list)  # Replay timeline references
    parent_receipt_ids: List[str] = field(default_factory=list)  # Parent receipts
    
    # Flags
    verified: bool = False  # Cryptographic verification status
    advisory_only: bool = True  # ALWAYS True - runtime execution is advisory
    authoritative: bool = False  # ALWAYS False - runtime execution is never authoritative
    integrity_flags: FrozenSet[str] = field(default_factory=frozenset)
    
    # Timestamp
    timestamp: str = field(default_factory=_utc_now)
    
    def __post_init__(self):
        # Ensure invariants
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def from_invocation(
        cls,
        invocation: RuntimeInvocation,
        duration_seconds: Optional[float] = None,
        proposal_ids: Optional[FrozenSet[str]] = None,
        token_metadata: Optional[Dict[str, int]] = None,
        replay_refs: Optional[List[str]] = None,
        parent_receipt_ids: Optional[List[str]] = None,
        integrity_flags: Optional[FrozenSet[str]] = None,
    ) -> "RuntimeExecutionReceipt":
        """Create a runtime execution receipt from an invocation."""
        receipt_id = _generate_deterministic_id(
            "runtime_receipt",
            invocation.invocation_id,
            invocation.provider_id,
            invocation.model_id,
        )
        
        cap_kinds = set()
        # We can't resolve capability kinds from IDs here without registry
        # This will be populated by the registry
        
        return cls(
            receipt_id=receipt_id,
            provider_id=invocation.provider_id,
            model_id=invocation.model_id,
            invocation_id=invocation.invocation_id,
            invocation_status=invocation.status,
            capability_ids=invocation.capability_ids,
            capability_kinds=frozenset(cap_kinds),
            proposal_ids=proposal_ids or frozenset(),
            proposal_count=len(proposal_ids) if proposal_ids else 0,
            status="success" if invocation.status == RuntimeInvocationStatus.SUCCEEDED else "failed",
            exit_code=invocation.exit_code,
            started_at=invocation.started_at,
            completed_at=invocation.completed_at,
            duration_seconds=duration_seconds,
            prompt_tokens=token_metadata.get("prompt_tokens") if token_metadata else None,
            completion_tokens=token_metadata.get("completion_tokens") if token_metadata else None,
            total_tokens=(
                token_metadata.get("total_tokens")
                if token_metadata and token_metadata.get("total_tokens") is not None
                else (token_metadata.get("prompt_tokens") + token_metadata.get("completion_tokens"))
                if token_metadata and token_metadata.get("prompt_tokens") is not None and token_metadata.get("completion_tokens") is not None
                else None
            ),
            raw_output_summary=invocation.raw_output[:500] if invocation.raw_output else "",
            workspace_id=invocation.workspace_id,
            actor_id=invocation.actor_id,
            purpose="runtime execution",
            replay_refs=replay_refs or [],
            parent_receipt_ids=parent_receipt_ids or [],
            integrity_flags=integrity_flags or frozenset(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "receipt_id": self.receipt_id,
            "kind": self.kind,
            "provider_id": self.provider_id,
            "provider_kind": self.provider_kind.value,
            "model_id": self.model_id,
            "provider_trust_tier": self.provider_trust_tier.value,
            "capability_ids": list(self.capability_ids),
            "capability_kinds": [k.value for k in self.capability_kinds],
            "invocation_id": self.invocation_id,
            "invocation_status": self.invocation_status.value,
            "proposal_ids": list(self.proposal_ids),
            "proposal_count": self.proposal_count,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "raw_output_ref": self.raw_output_ref,
            "raw_output_summary": self.raw_output_summary,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "purpose": self.purpose,
            "replay_refs": self.replay_refs,
            "parent_receipt_ids": self.parent_receipt_ids,
            "verified": self.verified,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
            "integrity_flags": list(self.integrity_flags),
            "timestamp": self.timestamp,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeExecutionReceipt":
        """Deserialize from dictionary."""
        cap_kinds = set()
        for kind_str in d.get("capability_kinds", []):
            try:
                cap_kinds.add(RuntimeCapabilityKind(kind_str))
            except ValueError:
                pass
        
        return cls(
            receipt_id=d.get("receipt_id", _generate_deterministic_id("runtime_receipt", "unknown")),
            kind=d.get("kind", "runtime_execution"),
            provider_id=d.get("provider_id", PLACEHOLDER_NO_PROVIDER),
            provider_kind=RuntimeProviderKind(d.get("provider_kind", "custom")),
            model_id=d.get("model_id", PLACEHOLDER_UNKNOWN),
            provider_trust_tier=RuntimeProviderTrustTier(d.get("provider_trust_tier", "advisory")),
            capability_ids=frozenset(d.get("capability_ids", [])),
            capability_kinds=frozenset(cap_kinds),
            invocation_id=d.get("invocation_id", PLACEHOLDER_NO_RECEIPT),
            invocation_status=RuntimeInvocationStatus(d.get("invocation_status", "pending")),
            proposal_ids=frozenset(d.get("proposal_ids", [])),
            proposal_count=d.get("proposal_count", 0),
            status=d.get("status", "unknown"),
            exit_code=d.get("exit_code"),
            started_at=d.get("started_at", _utc_now()),
            completed_at=d.get("completed_at"),
            duration_seconds=d.get("duration_seconds"),
            prompt_tokens=d.get("prompt_tokens"),
            completion_tokens=d.get("completion_tokens"),
            total_tokens=d.get("total_tokens"),
            raw_output_ref=d.get("raw_output_ref"),
            raw_output_summary=d.get("raw_output_summary", ""),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            purpose=d.get("purpose", ""),
            replay_refs=d.get("replay_refs", []),
            parent_receipt_ids=d.get("parent_receipt_ids", []),
            verified=d.get("verified", False),
            integrity_flags=frozenset(d.get("integrity_flags", [])),
            timestamp=d.get("timestamp", _utc_now()),
        )


# =============================================================================
# Runtime Decision Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeDecision:
    """Represents a runtime governance decision.
    
    Decisions are made by Rig based on capability checks, constraint enforcement,
    and trust tier validation. They determine whether a runtime action is allowed.
    
    Attributes:
        decision_id: Unique identifier for the decision
        kind: The kind of decision
        invocation_id: The invocation this decision relates to
        proposal_id: The proposal this decision relates to (if any)
        allowed: Whether the action was allowed
        reason: Human-readable reason for the decision
        constraint_violations: List of constraint violations
        trust_violations: List of trust tier violations
        capability_misses: List of missing capabilities
        created_at: When the decision was made
    """
    decision_id: str
    kind: RuntimeDecisionKind = RuntimeDecisionKind.CAPABILITY_CHECK
    invocation_id: Optional[str] = None
    proposal_id: Optional[str] = None
    allowed: bool = False
    reason: str = ""
    constraint_violations: List[str] = field(default_factory=list)  # Constraint IDs
    trust_violations: List[str] = field(default_factory=list)  # Trust tier violations
    capability_misses: List[str] = field(default_factory=list)  # Missing capability IDs
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    created_at: str = field(default_factory=_utc_now)
    
    @classmethod
    def allow(
        cls,
        kind: RuntimeDecisionKind,
        invocation_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        reason: str = "allowed by capability check",
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> "RuntimeDecision":
        """Create an allow decision."""
        decision_id = _generate_deterministic_id(
            "decision",
            kind.value,
            invocation_id or "",
            proposal_id or "",
            "allow",
        )
        return cls(
            decision_id=decision_id,
            kind=kind,
            invocation_id=invocation_id,
            proposal_id=proposal_id,
            allowed=True,
            reason=reason,
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    
    @classmethod
    def deny(
        cls,
        kind: RuntimeDecisionKind,
        invocation_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        reason: str = "denied by capability check",
        constraint_violations: Optional[List[str]] = None,
        trust_violations: Optional[List[str]] = None,
        capability_misses: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> "RuntimeDecision":
        """Create a deny decision."""
        decision_id = _generate_deterministic_id(
            "decision",
            kind.value,
            invocation_id or "",
            proposal_id or "",
            "deny",
        )
        return cls(
            decision_id=decision_id,
            kind=kind,
            invocation_id=invocation_id,
            proposal_id=proposal_id,
            allowed=False,
            reason=reason,
            constraint_violations=constraint_violations or [],
            trust_violations=trust_violations or [],
            capability_misses=capability_misses or [],
            workspace_id=workspace_id,
            actor_id=actor_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "decision_id": self.decision_id,
            "kind": self.kind.value,
            "invocation_id": self.invocation_id,
            "proposal_id": self.proposal_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "constraint_violations": self.constraint_violations,
            "trust_violations": self.trust_violations,
            "capability_misses": self.capability_misses,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeDecision":
        """Deserialize from dictionary."""
        return cls(
            decision_id=d.get("decision_id", _generate_deterministic_id("decision", "unknown")),
            kind=RuntimeDecisionKind(d.get("kind", "capability_check")),
            invocation_id=d.get("invocation_id"),
            proposal_id=d.get("proposal_id"),
            allowed=d.get("allowed", False),
            reason=d.get("reason", ""),
            constraint_violations=d.get("constraint_violations", []),
            trust_violations=d.get("trust_violations", []),
            capability_misses=d.get("capability_misses", []),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            created_at=d.get("created_at", _utc_now()),
        )


# =============================================================================
# Runtime Benchmark Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeBenchmark:
    """Represents a runtime benchmark record.
    
    Benchmarks track performance and quality metrics for runtime providers.
    They enable comparison and selection of providers based on objective criteria.
    
    Attributes:
        benchmark_id: Unique identifier for the benchmark
        provider_id: The runtime provider being benchmarked
        model_id: The model identifier
        kind: The kind of benchmark
        value: The benchmark value
        unit: The unit of measurement
        workspace_id: Optional workspace context
        recorded_at: When the benchmark was recorded
    """
    benchmark_id: str
    provider_id: str = PLACEHOLDER_NO_PROVIDER
    model_id: str = PLACEHOLDER_UNKNOWN
    kind: RuntimeBenchmarkKind = RuntimeBenchmarkKind.LATENCY
    value: float = 0.0
    unit: str = "seconds"
    workspace_id: Optional[str] = None
    recorded_at: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def latency(
        cls,
        provider_id: str,
        model_id: str,
        latency_seconds: float,
        workspace_id: Optional[str] = None,
    ) -> "RuntimeBenchmark":
        """Create a latency benchmark."""
        benchmark_id = _generate_deterministic_id(
            "benchmark",
            provider_id,
            model_id,
            "latency",
            str(latency_seconds),
        )
        return cls(
            benchmark_id=benchmark_id,
            provider_id=provider_id,
            model_id=model_id,
            kind=RuntimeBenchmarkKind.LATENCY,
            value=latency_seconds,
            unit="seconds",
            workspace_id=workspace_id,
            metadata={"type": "invocation"},
        )
    
    @classmethod
    def token_throughput(
        cls,
        provider_id: str,
        model_id: str,
        tokens_per_second: float,
        workspace_id: Optional[str] = None,
    ) -> "RuntimeBenchmark":
        """Create a token throughput benchmark."""
        benchmark_id = _generate_deterministic_id(
            "benchmark",
            provider_id,
            model_id,
            "token_throughput",
            str(tokens_per_second),
        )
        return cls(
            benchmark_id=benchmark_id,
            provider_id=provider_id,
            model_id=model_id,
            kind=RuntimeBenchmarkKind.TOKEN_THROUGHPUT,
            value=tokens_per_second,
            unit="tokens_per_second",
            workspace_id=workspace_id,
            metadata={"type": "token_processing"},
        )
    
    @classmethod
    def timeout_maximum(
        cls,
        provider_id: str,
        model_id: str,
        max_seconds: float,
        workspace_id: Optional[str] = None,
    ) -> "RuntimeBenchmark":
        """Create a timeout maximum benchmark (alias for latency)."""
        return cls.latency(provider_id, model_id, max_seconds, workspace_id)
    
    @classmethod
    def proposal_success_rate(
        cls,
        provider_id: str,
        model_id: str,
        success_rate: float,  # 0.0 to 1.0
        workspace_id: Optional[str] = None,
    ) -> "RuntimeBenchmark":
        """Create a proposal success rate benchmark."""
        benchmark_id = _generate_deterministic_id(
            "benchmark",
            provider_id,
            model_id,
            "proposal_success_rate",
            str(success_rate),
        )
        return cls(
            benchmark_id=benchmark_id,
            provider_id=provider_id,
            model_id=model_id,
            kind=RuntimeBenchmarkKind.PROPOSAL_SUCCESS,
            value=success_rate,
            unit="ratio",
            workspace_id=workspace_id,
            metadata={"type": "proposal_quality"},
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "benchmark_id": self.benchmark_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "kind": self.kind.value,
            "value": self.value,
            "unit": self.unit,
            "workspace_id": self.workspace_id,
            "recorded_at": self.recorded_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeBenchmark":
        """Deserialize from dictionary."""
        return cls(
            benchmark_id=d.get("benchmark_id", _generate_deterministic_id("benchmark", "unknown")),
            provider_id=d.get("provider_id", PLACEHOLDER_NO_PROVIDER),
            model_id=d.get("model_id", PLACEHOLDER_UNKNOWN),
            kind=RuntimeBenchmarkKind(d.get("kind", "latency")),
            value=d.get("value", 0.0),
            unit=d.get("unit", "seconds"),
            workspace_id=d.get("workspace_id"),
            recorded_at=d.get("recorded_at", _utc_now()),
            metadata=d.get("metadata", {}),
        )


# =============================================================================
# Runtime State Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Represents the current state of the runtime execution plane.
    
    Tracks active invocations, provider status, and overall system health.
    Used for monitoring and operational awareness.
    
    Attributes:
        state_id: Unique identifier for this state snapshot
        kind: The kind of state
        active_invocations: Set of currently active invocation IDs
        active_providers: Set of currently active provider IDs
        total_invocations: Total number of invocations
        total_proposals: Total number of proposals generated
        total_execution_receipts: Total number of execution receipts
        overall_status: Overall system status
        blocked_count: Number of blocked invocations
        failed_count: Number of failed invocations
        recorded_at: When this state snapshot was recorded
    """
    state_id: str
    kind: RuntimeStateKind = RuntimeStateKind.IDLE
    active_invocations: FrozenSet[str] = field(default_factory=frozenset)
    active_providers: FrozenSet[str] = field(default_factory=frozenset)
    total_invocations: int = 0
    total_proposals: int = 0
    total_execution_receipts: int = 0
    overall_status: str = "healthy"
    blocked_count: int = 0
    failed_count: int = 0
    recorded_at: str = field(default_factory=_utc_now)
    workspace_id: Optional[str] = None
    
    @classmethod
    def initial(cls, workspace_id: Optional[str] = None) -> "RuntimeState":
        """Create an initial runtime state."""
        state_id = _generate_deterministic_id("runtime_state", "initial", workspace_id or "global")
        return cls(
            state_id=state_id,
            kind=RuntimeStateKind.IDLE,
            recorded_at=_utc_now(),
            workspace_id=workspace_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "state_id": self.state_id,
            "kind": self.kind.value,
            "active_invocations": list(self.active_invocations),
            "active_providers": list(self.active_providers),
            "total_invocations": self.total_invocations,
            "total_proposals": self.total_proposals,
            "total_execution_receipts": self.total_execution_receipts,
            "overall_status": self.overall_status,
            "blocked_count": self.blocked_count,
            "failed_count": self.failed_count,
            "recorded_at": self.recorded_at,
            "workspace_id": self.workspace_id,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeState":
        """Deserialize from dictionary."""
        return cls(
            state_id=d.get("state_id", _generate_deterministic_id("runtime_state", "unknown")),
            kind=RuntimeStateKind(d.get("kind", "idle")),
            active_invocations=frozenset(d.get("active_invocations", [])),
            active_providers=frozenset(d.get("active_providers", [])),
            total_invocations=d.get("total_invocations", 0),
            total_proposals=d.get("total_proposals", 0),
            total_execution_receipts=d.get("total_execution_receipts", 0),
            overall_status=d.get("overall_status", "healthy"),
            blocked_count=d.get("blocked_count", 0),
            failed_count=d.get("failed_count", 0),
            recorded_at=d.get("recorded_at", _utc_now()),
            workspace_id=d.get("workspace_id"),
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Placeholders
    "PLACEHOLDER_UNKNOWN",
    "PLACEHOLDER_UNAVAILABLE",
    "PLACEHOLDER_NOT_CREATED",
    "PLACEHOLDER_NOT_RUN",
    "PLACEHOLDER_NOT_PROOF",
    "PLACEHOLDER_ADVISORY_ONLY",
    "PLACEHOLDER_NOT_AUTHORITATIVE",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_NO_CAPABILITY",
    "PLACEHOLDER_NO_PROVIDER",
    "REQUIRED_RUNTIME_PLACEHOLDERS",
    # Enums
    "RuntimeProviderKind",
    "RuntimeProviderTrustTier",
    "RuntimeProviderStatus",
    "RuntimeCapabilityKind",
    "RuntimeCapabilityScope",
    "RuntimeInvocationStatus",
    "RuntimeProposalStatus",
    "RuntimeProposalDecision",
    "RuntimeConstraintKind",
    "RuntimeConstraintMode",
    "RuntimeDecisionKind",
    "RuntimeStateKind",
    "RuntimeBenchmarkKind",
    "RuntimeFailureCategory",
    # Models
    "RuntimeProvider",
    "RuntimeCapability",
    "RuntimeConstraint",
    "RuntimeInvocation",
    "RuntimeProposal",
    "RuntimeExecutionReceipt",
    "RuntimeDecision",
    "RuntimeBenchmark",
    "RuntimeState",
]
