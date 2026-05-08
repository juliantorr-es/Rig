"""Governed Tool Invocation Substrate for Rig.

This module provides the canonical governed tool invocation substrate for Phase 4 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Tool invocations NEVER mutate authority directly.
- All tool invocations produce receipts.
- All tool invocations are replayable.
- All tool invocations are inspectable.
- All models are pure deterministic dataclasses.
- All models are JSON-serializable.
- Proposal-only execution model.

Critical: Tool invocations are proposals, not executions.
They describe what COULD be done, not what IS done.
Authority state mutation requires explicit Rig approval.

file: src/rig/domain/runtime_tools.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime import (
        RuntimeCapabilityKind,
        RuntimeInvocation,
        RuntimeProposal,
    )

from rig.domain.runtime import (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    RuntimeCapabilityKind,
)


# =============================================================================
# Placeholder Constants
# =============================================================================

PLACEHOLDER_NO_TOOL = "no_tool"
PLACEHOLDER_NO_COMMAND = "no_command"
PLACEHOLDER_NO_PAYLOAD = "no_payload"


# =============================================================================
# Enums
# =============================================================================

class ToolInvocationKind(Enum):
    """Kinds of tool invocations."""
    SHELL_COMMAND = "shell_command"          # Shell command proposal
    PATCH = "patch"                          # Patch proposal
    DOCUMENTATION_FETCH = "documentation_fetch"  # Documentation fetch proposal
    GITHUB_FETCH = "github_fetch"            # GitHub fetch proposal
    LOCAL_ANALYSIS = "local_analysis"         # Local analysis proposal
    FILE_READ = "file_read"                  # File read proposal
    FILE_WRITE = "file_write"                # File write proposal
    NETWORK_FETCH = "network_fetch"          # Network fetch proposal


class ToolInvocationStatus(Enum):
    """Status of a tool invocation."""
    PROPOSED = "proposed"                # Invocation proposed
    VALIDATED = "validated"                # Passed initial validation
    REVIEW_PENDING = "review_pending"        # Awaiting review
    APPROVED = "approved"                  # Approved for execution
    REJECTED = "rejected"                  # Rejected
    BLOCKED = "blocked"                  # Blocked by policy
    EXPIRED = "expired"                  # Expired


class ToolSafetyLevel(Enum):
    """Safety levels for tool invocations."""
    SAFE = "safe"                      # No risk of mutation
    LOW_RISK = "low_risk"                # Minimal risk
    MEDIUM_RISK = "medium_risk"          # Moderate risk
    HIGH_RISK = "high_risk"             # High risk
    CRITICAL_RISK = "critical_risk"      # Critical risk (should be blocked)


class ToolConstraintKind(Enum):
    """Kinds of tool constraints."""
    PATH_SCOPE = "path_scope"              # Path-based scope constraint
    COMMAND_PATTERN = "command_pattern"    # Command pattern constraint
    ARGUMENT_CHECK = "argument_check"      # Argument validation
    PERMISSION_CHECK = "permission_check"  # Permission constraint
    NETWORK_DESTINATION = "network_destination"  # Network destination constraint


class ToolConstraintMode(Enum):
    """Mode of a tool constraint."""
    ALLOW = "allow"                        # Allow matching invocations
    DENY = "deny"                          # Deny matching invocations
    REQUIRE_REVIEW = "require_review"      # Require review for matching invocations


class ToolValidationCode(Enum):
    """Validation codes for tool invocation validation."""
    VALID = "valid"                        # Validation passed
    INVALID_PATH = "invalid_path"          # Invalid path
    INVALID_COMMAND = "invalid_command"    # Invalid command
    BLOCKED_PATTERN = "blocked_pattern"    # Command matches blocked pattern
    PERMISSION_DENIED = "permission_denied"  # Permission denied
    NETWORK_PROHIBITED = "network_prohibited"  # Network access prohibited
    SAFETY_VIOLATION = "safety_violation"  # Safety level violation
    CAPABILITY_MISSING = "capability_missing"  # Required capability missing
    TRUST_VIOLATION = "trust_violation"    # Trust tier violation


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


# =============================================================================
# Tool Constraint Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class ToolConstraint:
    """Represents a constraint on tool invocations.
    
    Constraints limit what tool invocations are allowed.
    They are enforced before any proposal is accepted.
    
    Attributes:
        constraint_id: Unique identifier for the constraint
        kind: The kind of constraint
        mode: The constraint mode (allow/deny/require_review)
        pattern: The pattern to match against
        scope: The scope of the constraint (global or workspace)
        workspace_id: Optional workspace-specific constraint
        safety_level: Minimum safety level required
        description: Human-readable description
    """
    constraint_id: str
    kind: ToolConstraintKind = ToolConstraintKind.PATH_SCOPE
    mode: ToolConstraintMode = ToolConstraintMode.DENY
    pattern: str = ""
    scope: str = "global"  # "global" or "workspace"
    workspace_id: Optional[str] = None
    safety_level: Optional[ToolSafetyLevel] = None
    description: str = ""
    created_at: str = field(default_factory=_utc_now)
    
    @classmethod
    def block_shell_commands(cls) -> "ToolConstraint":
        """Create a constraint that blocks all shell commands."""
        return cls(
            constraint_id=_generate_deterministic_id("tool_constraint", "block_shell"),
            kind=ToolConstraintKind.COMMAND_PATTERN,
            mode=ToolConstraintMode.DENY,
            pattern="*",
            scope="global",
            safety_level=ToolSafetyLevel.CRITICAL_RISK,
            description="Block all shell command invocations",
        )
    
    @classmethod
    def block_destructive_commands(cls) -> "ToolConstraint":
        """Create a constraint that blocks destructive commands."""
        destructive_patterns = [
            "rm",
            "git reset",
            "git clean",
            "git stash",
            "dd",
            ":() { :; } ;",  # Fork bomb protection
        ]
        # Use first pattern for ID
        return cls(
            constraint_id=_generate_deterministic_id("tool_constraint", "block_destructive"),
            kind=ToolConstraintKind.COMMAND_PATTERN,
            mode=ToolConstraintMode.DENY,
            pattern=";".join(destructive_patterns),
            scope="global",
            safety_level=ToolSafetyLevel.CRITICAL_RISK,
            description="Block destructive shell commands",
        )
    
    @classmethod
    def require_review_for_network(cls) -> "ToolConstraint":
        """Create a constraint that requires review for network access."""
        return cls(
            constraint_id=_generate_deterministic_id("tool_constraint", "review_network"),
            kind=ToolConstraintKind.NETWORK_DESTINATION,
            mode=ToolConstraintMode.REQUIRE_REVIEW,
            pattern="*",
            scope="global",
            safety_level=ToolSafetyLevel.MEDIUM_RISK,
            description="Require review for all network access",
        )
    
    @classmethod
    def restrict_to_repo(cls, repo_root: Path) -> "ToolConstraint":
        """Create a constraint that restricts file operations to repo."""
        return cls(
            constraint_id=_generate_deterministic_id("tool_constraint", "repo_scope", str(repo_root)),
            kind=ToolConstraintKind.PATH_SCOPE,
            mode=ToolConstraintMode.DENY,
            pattern=str(repo_root),
            scope="workspace",
            safety_level=ToolSafetyLevel.LOW_RISK,
            description=f"Restrict file operations to {repo_root}",
        )
    
    def applies_to(self, tool_invocation: "ToolInvocationEnvelope") -> bool:
        """Check if this constraint applies to a tool invocation."""
        if self.scope == "workspace":
            if self.workspace_id != tool_invocation.workspace_id:
                return False
        
        # Check based on constraint kind
        if self.kind == ToolConstraintKind.PATH_SCOPE:
            # Check if invocation paths are within allowed scope
            # For now, simple implementation
            return True
        
        if self.kind == ToolConstraintKind.COMMAND_PATTERN:
            # Check if command matches pattern
            if tool_invocation.tool_kind == ToolInvocationKind.SHELL_COMMAND:
                cmd_str = " ".join(tool_invocation.payload.get("argv", []))
                # Simple pattern matching - could be enhanced
                if self.pattern == "*":
                    return True
                if self.pattern in cmd_str:
                    return True
        
        if self.kind == ToolConstraintKind.NETWORK_DESTINATION:
            if tool_invocation.tool_kind in [
                ToolInvocationKind.NETWORK_FETCH,
                ToolInvocationKind.DOCUMENTATION_FETCH,
                ToolInvocationKind.GITHUB_FETCH,
            ]:
                return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "constraint_id": self.constraint_id,
            "kind": self.kind.value,
            "mode": self.mode.value,
            "pattern": self.pattern,
            "scope": self.scope,
            "workspace_id": self.workspace_id,
            "safety_level": self.safety_level.value if self.safety_level else None,
            "description": self.description,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolConstraint":
        """Deserialize from dictionary."""
        safety_level = None
        if d.get("safety_level"):
            try:
                safety_level = ToolSafetyLevel(d["safety_level"])
            except ValueError:
                pass
        
        return cls(
            constraint_id=d.get("constraint_id", _generate_deterministic_id("tool_constraint", "unknown")),
            kind=ToolConstraintKind(d.get("kind", "path_scope")),
            mode=ToolConstraintMode(d.get("mode", "deny")),
            pattern=d.get("pattern", ""),
            scope=d.get("scope", "global"),
            workspace_id=d.get("workspace_id"),
            safety_level=safety_level,
            description=d.get("description", ""),
            created_at=d.get("created_at", _utc_now()),
        )


# =============================================================================
# Tool Invocation Envelope Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class ToolInvocationEnvelope:
    """Represents a determined tool invocation envelope.
    
    An envelope wraps a tool invocation with governance metadata.
    It ensures that all tool invocations are:
    - Deterministic
    - Serializable
    - Inspectable
    - Replay-safe
    - Projection-safe
    
    Attributes:
        envelope_id: Unique identifier for the envelope
        tool_kind: The kind of tool being invoked
        payload: The tool-specific payload
        capability_kinds: Set of capability kinds required
        workspace_id: The workspace context
        actor_id: The actor initiating the invocation
        runtime_provider_id: The runtime provider
        model_id: The model identifier
        safety_level: The safety level assessment
        constraints_checked: Set of constraint IDs that were checked
        validation_code: The validation result code
        validation_message: Human-readable validation message
        created_at: When the envelope was created
    """
    envelope_id: str
    tool_kind: ToolInvocationKind = ToolInvocationKind.SHELL_COMMAND
    payload: Dict[str, Any] = field(default_factory=dict)
    capability_kinds: FrozenSet[RuntimeCapabilityKind] = field(default_factory=frozenset)
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    runtime_provider_id: Optional[str] = None
    model_id: Optional[str] = None
    safety_level: ToolSafetyLevel = ToolSafetyLevel.MEDIUM_RISK
    constraints_checked: FrozenSet[str] = field(default_factory=frozenset)
    validation_code: ToolValidationCode = ToolValidationCode.VALID
    validation_message: str = ""
    created_at: str = field(default_factory=_utc_now)
    advisory_only: bool = True  # ALL tool invocations are advisory only
    authoritative: bool = False  # ALL tool invocations are NEVER authoritative
    
    @classmethod
    def create(
        cls,
        tool_kind: ToolInvocationKind,
        payload: Dict[str, Any],
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]] = None,
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        runtime_provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a tool invocation envelope."""
        envelope_id = _generate_deterministic_id(
            "tool_envelope",
            tool_kind.value,
            json.dumps(payload, sort_keys=True, default=str),
            workspace_id or "",
        )
        
        # Determine safety level based on tool kind
        safety_level = cls._get_safety_level(tool_kind, payload)
        
        return cls(
            envelope_id=envelope_id,
            tool_kind=tool_kind,
            payload=payload,
            capability_kinds=capability_kinds or frozenset(),
            workspace_id=workspace_id,
            actor_id=actor_id,
            runtime_provider_id=runtime_provider_id,
            model_id=model_id,
            safety_level=safety_level,
        )
    
    @staticmethod
    def _get_safety_level(tool_kind: ToolInvocationKind, payload: Dict[str, Any]) -> ToolSafetyLevel:
        """Determine the safety level for a tool invocation."""
        # SAFE operations
        if tool_kind in [ToolInvocationKind.FILE_READ, ToolInvocationKind.LOCAL_ANALYSIS]:
            path = payload.get("path") or payload.get("file_path")
            if path:
                # Check for sensitive paths
                sensitive_prefixes = [".git/", ".env", "password", "secret", "token"]
                path_lower = str(path).lower()
                if any(prefix in path_lower for prefix in sensitive_prefixes):
                    return ToolSafetyLevel.MEDIUM_RISK
            return ToolSafetyLevel.SAFE
        
        # MEDIUM RISK operations
        if tool_kind in [ToolInvocationKind.DOCUMENTATION_FETCH]:
            return ToolSafetyLevel.MEDIUM_RISK
        
        # HIGH RISK operations
        if tool_kind in [
            ToolInvocationKind.FILE_WRITE,
            ToolInvocationKind.PATCH,
            ToolInvocationKind.NETWORK_FETCH,
            ToolInvocationKind.GITHUB_FETCH,
        ]:
            return ToolSafetyLevel.HIGH_RISK
        
        # SHELL_COMMAND - depends on the command
        if tool_kind == ToolInvocationKind.SHELL_COMMAND:
            argv = payload.get("argv", [])
            cmd_str = " ".join(argv) if isinstance(argv, list) else ""
            
            # Check for destructive commands
            destructive = ["rm", "dd", "mv", "git reset", "git clean", "git stash"]
            if any(d in cmd_str for d in destructive):
                return ToolSafetyLevel.CRITICAL_RISK
            
            # Check for read-only commands
            readonly = ["ls", "cat", "grep", "find", "echo", "pwd"]
            if any(r in cmd_str for r in readonly):
                return ToolSafetyLevel.SAFE
            
            return ToolSafetyLevel.HIGH_RISK
        
        return ToolSafetyLevel.MEDIUM_RISK
    
    @classmethod
    def from_shell_proposal(
        cls,
        invocation: "RuntimeInvocation",
        argv: List[str],
        cwd: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a shell command envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.SHELL_COMMAND,
            payload={
                "argv": argv,
                "cwd": cwd,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.SHELL_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_patch_proposal(
        cls,
        invocation: "RuntimeInvocation",
        file_path: str,
        diff: str,
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a patch envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.PATCH,
            payload={
                "file_path": file_path,
                "diff": diff,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.PATCH_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_file_write_proposal(
        cls,
        invocation: "RuntimeInvocation",
        file_path: str,
        content: str,
        mode: str = "overwrite",
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a file write envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.FILE_WRITE,
            payload={
                "file_path": file_path,
                "content": content,
                "mode": mode,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.FILE_WRITE_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_network_fetch(
        cls,
        invocation: "RuntimeInvocation",
        url: str,
        method: str = "GET",
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a network fetch envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.NETWORK_FETCH,
            payload={
                "url": url,
                "method": method,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_docs_fetch(
        cls,
        invocation: "RuntimeInvocation",
        source: str,
        query: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a documentation fetch envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.DOCUMENTATION_FETCH,
            payload={
                "source": source,
                "query": query,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.DOCS_FETCH_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_github_fetch(
        cls,
        invocation: "RuntimeInvocation",
        owner: str,
        repo: str,
        path: str = "",
        ref: str = "main",
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a GitHub fetch envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.GITHUB_FETCH,
            payload={
                "owner": owner,
                "repo": repo,
                "path": path,
                "ref": ref,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    @classmethod
    def from_local_analysis(
        cls,
        invocation: "RuntimeInvocation",
        analysis_type: str,
        target_path: str,
        workspace_id: Optional[str] = None,
    ) -> "ToolInvocationEnvelope":
        """Create a local analysis envelope from a runtime invocation."""
        return cls.create(
            tool_kind=ToolInvocationKind.LOCAL_ANALYSIS,
            payload={
                "analysis_type": analysis_type,
                "target_path": target_path,
            },
            capability_kinds=frozenset([RuntimeCapabilityKind.FILE_READ]),
            workspace_id=workspace_id or invocation.workspace_id,
            actor_id=invocation.actor_id,
            runtime_provider_id=invocation.provider_id,
            model_id=invocation.model_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "envelope_id": self.envelope_id,
            "tool_kind": self.tool_kind.value,
            "payload": self.payload,
            "capability_kinds": [k.value for k in self.capability_kinds],
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "runtime_provider_id": self.runtime_provider_id,
            "model_id": self.model_id,
            "safety_level": self.safety_level.value,
            "constraints_checked": list(self.constraints_checked),
            "validation_code": self.validation_code.value,
            "validation_message": self.validation_message,
            "created_at": self.created_at,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolInvocationEnvelope":
        """Deserialize from dictionary."""
        capability_kinds = set()
        for kind_str in d.get("capability_kinds", []):
            try:
                capability_kinds.add(RuntimeCapabilityKind(kind_str))
            except ValueError:
                pass
        
        return cls(
            envelope_id=d.get("envelope_id", _generate_deterministic_id("tool_envelope", "unknown")),
            tool_kind=ToolInvocationKind(d.get("tool_kind", "shell_command")),
            payload=d.get("payload", {}),
            capability_kinds=frozenset(capability_kinds),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            runtime_provider_id=d.get("runtime_provider_id"),
            model_id=d.get("model_id"),
            safety_level=ToolSafetyLevel(d.get("safety_level", "medium_risk")),
            constraints_checked=frozenset(d.get("constraints_checked", [])),
            validation_code=ToolValidationCode(d.get("validation_code", "valid")),
            validation_message=d.get("validation_message", ""),
            created_at=d.get("created_at", _utc_now()),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )
    
    def to_receipt(self) -> "ToolInvocationReceipt":
        """Convert this envelope to a tool invocation receipt."""
        return ToolInvocationReceipt.from_envelope(self)


# =============================================================================
# Tool Invocation Receipt Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class ToolInvocationReceipt:
    """Canonical receipt for tool invocation.
    
    Records evidence of a tool invocation proposal, including:
    - Envelope data
    - Validation results
    - Decision status
    - Runtime context
    - Integrity and replay metadata
    
    Receipts are:
    - Replay-compatible
    - Integrity-compatible
    - Projection-compatible
    - Audit-compatible
    
    Critical: Tool invocation receipts NEVER indicate direct authority mutation.
    They are advisory records of proposals that were made.
    """
    receipt_id: str
    kind: str = "tool_invocation"  # Receipt kind
    
    # Envelope data
    envelope_id: str = PLACEHOLDER_NO_RECEIPT
    tool_kind: ToolInvocationKind = ToolInvocationKind.SHELL_COMMAND
    payload: Dict[str, Any] = field(default_factory=dict)
    capability_kinds: FrozenSet[RuntimeCapabilityKind] = field(default_factory=frozenset)
    
    # Context
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    runtime_provider_id: Optional[str] = None
    model_id: Optional[str] = None
    
    # Validation and safety
    safety_level: ToolSafetyLevel = ToolSafetyLevel.MEDIUM_RISK
    validation_code: ToolValidationCode = ToolValidationCode.VALID
    validation_message: str = ""
    constraints_checked: FrozenSet[str] = field(default_factory=frozenset)
    
    # Decision
    status: ToolInvocationStatus = ToolInvocationStatus.PROPOSAL
    decision_reason: str = ""
    
    # Timeline
    created_at: str = field(default_factory=_utc_now)
    validated_at: Optional[str] = None
    decided_at: Optional[str] = None
    
    # Integrity and replay
    replay_refs: List[str] = field(default_factory=list)
    parent_receipt_ids: List[str] = field(default_factory=list)
    
    # Flags
    verified: bool = False
    advisory_only: bool = True  # ALWAYS True
    authoritative: bool = False  # ALWAYS False
    integrity_flags: FrozenSet[str] = field(default_factory=frozenset)
    
    # Timestamp
    timestamp: str = field(default_factory=_utc_now)
    
    def __post_init__(self):
        # Ensure invariants
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def from_envelope(
        cls,
        envelope: ToolInvocationEnvelope,
        status: ToolInvocationStatus = ToolInvocationStatus.PROPOSAL,
        decision_reason: str = "",
        validated_at: Optional[str] = None,
        decided_at: Optional[str] = None,
    ) -> "ToolInvocationReceipt":
        """Create a tool invocation receipt from an envelope."""
        receipt_id = _generate_deterministic_id(
            "tool_receipt",
            envelope.envelope_id,
            envelope.tool_kind.value,
        )
        
        now = _utc_now()
        
        return cls(
            receipt_id=receipt_id,
            envelope_id=envelope.envelope_id,
            tool_kind=envelope.tool_kind,
            payload=envelope.payload,
            capability_kinds=envelope.capability_kinds,
            workspace_id=envelope.workspace_id,
            actor_id=envelope.actor_id,
            runtime_provider_id=envelope.runtime_provider_id,
            model_id=envelope.model_id,
            safety_level=envelope.safety_level,
            validation_code=envelope.validation_code,
            validation_message=envelope.validation_message,
            constraints_checked=envelope.constraints_checked,
            status=status,
            decision_reason=decision_reason,
            created_at=envelope.created_at,
            validated_at=validated_at,
            decided_at=decided_at,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "receipt_id": self.receipt_id,
            "kind": self.kind,
            "envelope_id": self.envelope_id,
            "tool_kind": self.tool_kind.value,
            "payload": self.payload,
            "capability_kinds": [k.value for k in self.capability_kinds],
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "runtime_provider_id": self.runtime_provider_id,
            "model_id": self.model_id,
            "safety_level": self.safety_level.value,
            "validation_code": self.validation_code.value,
            "validation_message": self.validation_message,
            "constraints_checked": list(self.constraints_checked),
            "status": self.status.value,
            "decision_reason": self.decision_reason,
            "created_at": self.created_at,
            "validated_at": self.validated_at,
            "decided_at": self.decided_at,
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
    def from_dict(cls, d: Dict[str, Any]) -> "ToolInvocationReceipt":
        """Deserialize from dictionary."""
        capability_kinds = set()
        for kind_str in d.get("capability_kinds", []):
            try:
                capability_kinds.add(RuntimeCapabilityKind(kind_str))
            except ValueError:
                pass
        
        return cls(
            receipt_id=d.get("receipt_id", _generate_deterministic_id("tool_receipt", "unknown")),
            kind=d.get("kind", "tool_invocation"),
            envelope_id=d.get("envelope_id", PLACEHOLDER_NO_RECEIPT),
            tool_kind=ToolInvocationKind(d.get("tool_kind", "shell_command")),
            payload=d.get("payload", {}),
            capability_kinds=frozenset(capability_kinds),
            workspace_id=d.get("workspace_id"),
            actor_id=d.get("actor_id"),
            runtime_provider_id=d.get("runtime_provider_id"),
            model_id=d.get("model_id"),
            safety_level=ToolSafetyLevel(d.get("safety_level", "medium_risk")),
            validation_code=ToolValidationCode(d.get("validation_code", "valid")),
            validation_message=d.get("validation_message", ""),
            constraints_checked=frozenset(d.get("constraints_checked", [])),
            status=ToolInvocationStatus(d.get("status", "proposal")),
            decision_reason=d.get("decision_reason", ""),
            created_at=d.get("created_at", _utc_now()),
            validated_at=d.get("validated_at"),
            decided_at=d.get("decided_at"),
            replay_refs=d.get("replay_refs", []),
            parent_receipt_ids=d.get("parent_receipt_ids", []),
            verified=d.get("verified", False),
            integrity_flags=frozenset(d.get("integrity_flags", [])),
            timestamp=d.get("timestamp", _utc_now()),
        )


# =============================================================================
# Tool Validator
# =============================================================================

@dataclass(frozen=True, slots=True)
class ToolValidator:
    """Validator for tool invocation envelopes.
    
    Performs deterministic validation of tool invocations against
    constraints and safety policies.
    
    Properties:
    - Pure validation (no side effects)
    - Deterministic results
    - JSON-serializable output
    - Replay-safe
    """
    constraint_ids: FrozenSet[str] = field(default_factory=frozenset)
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    created_at: str = field(default_factory=_utc_now)
    
    def validate(
        self,
        envelope: ToolInvocationEnvelope,
        constraints: Optional[List[ToolConstraint]] = None,
    ) -> Tuple[bool, List[str], ToolValidationCode]:
        """Validate a tool invocation envelope.
        
        Returns (is_valid, error_messages, validation_code).
        """
        errors: List[str] = []
        
        # Check safety level
        if envelope.safety_level == ToolSafetyLevel.CRITICAL_RISK:
            errors.append(
                f"Tool invocation blocked: {envelope.tool_kind.value} has CRITICAL safety level"
            )
            return False, errors, ToolValidationCode.SAFETY_VIOLATION
        
        # Check constraints
        applicable_constraints = []
        if constraints:
            for constraint in constraints:
                if constraint.applies_to(envelope):
                    applicable_constraints.append(constraint)
        
        for constraint in applicable_constraints:
            if constraint.mode == ToolConstraintMode.DENY:
                errors.append(
                    f"Denied by constraint {constraint.constraint_id}: {constraint.description}"
                )
        
        if errors:
            return False, errors, ToolValidationCode.BLOCKED_PATTERN
        
        # Check for require_review constraints
        for constraint in applicable_constraints:
            if constraint.mode == ToolConstraintMode.REQUIRE_REVIEW:
                # This doesn't fail validation, but marks it for review
                pass
        
        if not errors:
            return True, [], ToolValidationCode.VALID
        
        return False, errors, ToolValidationCode.VALIDATION_ERROR
    
    @classmethod
    def create_default(cls, workspace_id: Optional[str] = None) -> "ToolValidator":
        """Create a default tool validator with built-in constraints."""
        # Default constraints
        constraints: Set[str] = set()
        
        # Add critical safety constraints
        block_shell = ToolConstraint.block_shell_commands()
        constraints.add(block_shell.constraint_id)
        
        block_destructive = ToolConstraint.block_destructive_commands()
        constraints.add(block_destructive.constraint_id)
        
        review_network = ToolConstraint.require_review_for_network()
        constraints.add(review_network.constraint_id)
        
        return cls(
            constraint_ids=frozenset(constraints),
            workspace_id=workspace_id,
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Placeholders
    "PLACEHOLDER_NO_TOOL",
    "PLACEHOLDER_NO_COMMAND",
    "PLACEHOLDER_NO_PAYLOAD",
    # Enums
    "ToolInvocationKind",
    "ToolInvocationStatus",
    "ToolSafetyLevel",
    "ToolConstraintKind",
    "ToolConstraintMode",
    "ToolValidationCode",
    # Models
    "ToolConstraint",
    "ToolInvocationEnvelope",
    "ToolInvocationReceipt",
    "ToolValidator",
]
