"""Projection Contracts Module for Rig.

This module provides the canonical projection contract framework for Phase 4.
Projections are presentation contracts derived from canonical authority state.

Core doctrine:
- All projection contracts are deterministic and JSON-serializable
- All validation is pure (no side effects, no filesystemmutation)
- Authority claims must be traceable to canonical receipts/audit events
- Placeholders are explicit, never null/None
- No frontend authority logic

file: src/rig/domain/projection_contracts.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Placeholder Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_UNKNOWN = "unknown"
PLACEHOLDER_UNAVAILABLE = "unavailable"
PLACEHOLDER_NOT_CREATED = "not_created"
PLACEHOLDER_NOT_RUN = "not_run"
PLACEHOLDER_NOT_PROOF = "not_proof"
PLACEHOLDER_ADVISORY_ONLY = "advisory_only"
PLACEHOLDER_NOT_AUTHORITATIVE = "not_authoritative"
PLACEHOLDER_NO_RECEIPT = "no_receipt"

# ---------------------------------------------------------------------------
# Authority Binding Types
# ---------------------------------------------------------------------------

class AuthorityBindingType(Enum):
    """Types of authority bindings for projection fields."""
    
    CANONICAL = "canonical"           # Directly from canonical receipt/audit state
    DERIVED = "derived"               # Derived from canonical state (deterministic)
    ADVISORY = "advisory"             # Advisory only, not authoritative
    STATIC = "static"                 # Static display, no authority
    PLACEHOLDER = "placeholder"        # Explicit placeholder


class ReceiptBackingRequirement(Enum):
    """Receipt backing requirements for projection fields."""
    
    REQUIRED = "required"             # Field must have receipt backing
    OPTIONAL = "optional"             # Field may have receipt backing
    NOT_REQUIRED = "not_required"     # Field does not need receipt backing
    PROHIBITED = "prohibited"         # Field must NOT claim receipt backing


class AuditBackingRequirement(Enum):
    """Audit backing requirements for projection fields."""
    
    REQUIRED = "required"             # Field must have audit event backing
    OPTIONAL = "optional"             # Field may have audit event backing
    NOT_REQUIRED = "not_required"     # Field does not need audit backing
    PROHIBITED = "prohibited"         # Field must NOT claim audit backing


# ---------------------------------------------------------------------------
# Violation Types
# ---------------------------------------------------------------------------

class ProjectionContractViolationCode(Enum):
    """Canonical violation codes for projection contract violations.
    
    These map to PC-* codes in the integrity violation catalog.
    """
    MISSING_REQUIRED_FIELD = "PC-001-MISSING-REQUIRED"
    INVALID_PLACEHOLDER_USAGE = "PH-002-INVALID-PLACEHOLDER"
    AUTHORITATIVE_FIELD_PLACEHOLDER = "PH-004-AUTH-PLACEHOLDER"
    FALSE_AUTHORITATIVE_CLAIM = "PC-003-FALSE-AUTHORITY"
    FRONTEND_AUTHORITY_INFERENCE = "PC-004-FRONTEND-AUTHORITY"
    READ_ONLY_VIOLATION = "PC-005-READ-ONLY"
    RECEIPT_BACKING_MISSING = "PC-006-RECEIPT-BACKING"
    AUDIT_BACKING_MISSING = "PC-007-AUDIT-BACKING"
    AUTHORITY_BINDING_FAILURE = "PC-008-BINDING-FAILURE"
    CONTRACT_MISMATCH = "PC-009-CONTRACT-MISMATCH"


class ProjectionViolationSeverity(Enum):
    """Severity levels for projection contract violations."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Projection Field Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProjectionField:
    """A single field in a projection contract.
    
    Defines the field's name, type, requirements, and authority bindings.
    
    Attributes:
        field_name: The name of the field in the projection data
        field_type: The expected type ("string", "number", "boolean", "array", "object", "null")
        required: Whether this field is required
        placeholder: The explicit placeholder value if field is missing
        authority_binding: How this field relates to canonical authority
        receipt_backing: Whether this field requires receipt backing
        audit_backing: Whether this field requires audit event backing
        allowed_values: Optional set of allowed values (for enums/constrained strings)
        min_value: Optional minimum value (for numbers)
        max_value: Optional maximum value (for numbers)
        description: Human-readable description of the field
    """
    
    field_name: str
    field_type: str = "string"
    required: bool = False
    placeholder: Any = None
    authority_binding: AuthorityBindingType = AuthorityBindingType.STATIC
    receipt_backing: ReceiptBackingRequirement = ReceiptBackingRequirement.NOT_REQUIRED
    audit_backing: AuditBackingRequirement = AuditBackingRequirement.NOT_REQUIRED
    allowed_values: Optional[Set[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    
    def __hash__(self) -> int:
        # Handle potentially unhashable placeholder by using its type and repr
        placeholder_hashable = self.placeholder
        if placeholder_hashable is not None:
            try:
                hash(placeholder_hashable)
            except TypeError:
                # Unhashable - use type and repr for deterministic hash
                placeholder_hashable = (type(placeholder_hashable).__name__, repr(placeholder_hashable))
        return hash((
            self.field_name,
            self.field_type,
            self.required,
            placeholder_hashable,
            self.authority_binding,
            self.receipt_backing,
            self.audit_backing,
            frozenset(self.allowed_values) if self.allowed_values else None,
            self.min_value,
            self.max_value,
            self.description,
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "required": self.required,
            "placeholder": self.placeholder,
            "authority_binding": self.authority_binding.value,
            "receipt_backing": self.receipt_backing.value,
            "audit_backing": self.audit_backing.value,
            "allowed_values": list(self.allowed_values) if self.allowed_values else [],
            "min_value": self.min_value,
            "max_value": self.max_value,
            "description": self.description,
        }
    
    def validate_value(self, value: Any, repo_root: Optional["Path"] = None) -> Optional["ProjectionContractViolation"]:
        """Validate a field value against this field definition.
        
        Returns a violation if the value is invalid, None otherwise.
        """
        # Check required fields - missing value is a violation regardless of placeholder
        if self.required and value is None:
            return ProjectionContractViolation(
                violation_id=f"{self.field_name}_required_missing",
                violation_code=ProjectionContractViolationCode.MISSING_REQUIRED_FIELD,
                severity=ProjectionViolationSeverity.ERROR,
                title=f"Missing required field: {self.field_name}",
                message=f"Field '{self.field_name}' is required but is missing or None",
                field_name=self.field_name,
                expected_type=self.field_type,
                actual_value=None,
            )
        
        # Check for placeholder in authoritative fields
        # Only flag if field is required (if not required, None means genuinely absent)
        # or if value matches a known placeholder string
        if self.authority_binding in (AuthorityBindingType.CANONICAL, AuthorityBindingType.DERIVED):
            # If field is not required and value is None, that's OK (field genuinely absent)
            # If field is required and None, that was already caught above
            # Check for string placeholders in authoritative fields
            if isinstance(value, str):
                if value == PLACEHOLDER_UNKNOWN or value in ("", "null", "undefined"):
                    return ProjectionContractViolation(
                        violation_id=f"{self.field_name}_authoritative_placeholder",
                        violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                        severity=ProjectionViolationSeverity.ERROR,
                        title=f"Authoritative field has placeholder: {self.field_name}",
                        message=f"Field '{self.field_name}' is authoritative but has placeholder value: {value}",
                        field_name=self.field_name,
                        expected_type=self.field_type,
                        actual_value=value,
                    )
            # Non-string None/empty: OK if field is not required (genuinely absent)
            # If required and None, already caught by required check above
        
        # Type checking
        if value is not None:
            if self.field_type == "string" and not isinstance(value, str):
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected {self.field_type} but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            elif self.field_type == "number" and not isinstance(value, (int, float)):
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected number but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            elif self.field_type == "boolean" and not isinstance(value, bool):
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected boolean but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            elif self.field_type == "array" and not isinstance(value, (list, tuple)):
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected array but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            elif self.field_type == "object" and not isinstance(value, dict):
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected object but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            elif self.field_type == "null" and value is not None:
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_type_mismatch",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Type mismatch for field: {self.field_name}",
                    message=f"Field '{self.field_name}' expected null but got {type(value).__name__}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
        
        # Check allowed values
        if self.allowed_values and value is not None:
            if str(value) not in self.allowed_values:
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_invalid_value",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Invalid value for field: {self.field_name}",
                    message=f"Field '{self.field_name}' has value '{value}' not in allowed set: {self.allowed_values}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                    details={"allowed_values": list(self.allowed_values)},
                )
        
        # Numeric range checks
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_below_min",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Value below minimum for field: {self.field_name}",
                    message=f"Field '{self.field_name}' value {value} is below minimum {self.min_value}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
            if self.max_value is not None and value > self.max_value:
                return ProjectionContractViolation(
                    violation_id=f"{self.field_name}_above_max",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.WARNING,
                    title=f"Value above maximum for field: {self.field_name}",
                    message=f"Field '{self.field_name}' value {value} is above maximum {self.max_value}",
                    field_name=self.field_name,
                    expected_type=self.field_type,
                    actual_value=value,
                )
        
        return None


@dataclass(frozen=True, slots=True)
class ProjectionAuthorityBinding:
    """Authority binding definition for a projection contract.
    
    Defines how the projection relates to canonical authority state.
    
    Attributes:
        binding_id: Unique identifier for this binding
        source_module: The source module providing canonical authority (e.g., "workspace", "receipt_envelope", "workspace_audit")
        source_function: The source function that provides the data
        source_type: The type of canonical state ("receipt", "audit_event", "workspace_record", "static", "derived")
        mutable: Whether the source can be mutated (should be False for canonical state)
        description: Human-readable description
    """
    
    binding_id: str
    source_module: str
    source_function: str
    source_type: str
    mutable: bool = False
    description: str = ""
    
    def is_authoritative(self) -> bool:
        """Check if this binding is authoritative."""
        return self.source_type in ("receipt", "audit_event", "workspace_record") and not self.mutable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "binding_id": self.binding_id,
            "source_module": self.source_module,
            "source_function": self.source_function,
            "source_type": self.source_type,
            "mutable": self.mutable,
            "description": self.description,
            "authoritative": self.is_authoritative(),
        }


# ---------------------------------------------------------------------------
# Projection Contract Violation Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProjectionContractViolation:
    """A single violation of a projection contract.
    
    Represents a failure to meet contract requirements.
    
    Attributes:
        violation_id: Unique identifier for this violation
        violation_code: The canonical violation code
        severity: The severity level
        title: Human-readable title
        message: Detailed message about the violation
        field_name: The field name where the violation occurred (if applicable)
        expected_type: The expected type (if applicable)
        actual_value: The actual value found (if applicable)
        contract_id: The contract ID this violation relates to
        widget_type: The widget type this violation relates to
        details: Additional details about the violation
    """
    
    violation_id: str
    violation_code: ProjectionContractViolationCode
    severity: ProjectionViolationSeverity
    title: str
    message: str
    field_name: Optional[str] = None
    expected_type: Optional[str] = None
    actual_value: Any = None
    contract_id: Optional[str] = None
    widget_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "violation_id": self.violation_id,
            "violation_code": self.violation_code.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "field_name": self.field_name,
            "expected_type": self.expected_type,
            "actual_value": self.actual_value,
            "contract_id": self.contract_id,
            "widget_type": self.widget_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }
    
    @property
    def severity_order(self) -> int:
        """Numeric order for severity comparison (higher = more severe)."""
        return {
            ProjectionViolationSeverity.INFO: 0,
            ProjectionViolationSeverity.WARNING: 1,
            ProjectionViolationSeverity.ERROR: 2,
            ProjectionViolationSeverity.CRITICAL: 3,
        }.get(self.severity, 0)


@dataclass(frozen=True, slots=True)
class ProjectionContractCheckResult:
    """Result of checking a projection against its contract.
    
    Attributes:
        contract_id: The ID of the contract being checked
        widget_type: The widget type
        passed: Whether the check passed
        violations: All violations found
        warnings: Count of warning-level violations
        errors: Count of error-level violations
        critical: Count of critical-level violations
        info: Count of info-level violations
    """
    
    contract_id: str
    widget_type: str
    passed: bool
    violations: Tuple[ProjectionContractViolation, ...] = ()
    warnings: int = 0
    errors: int = 0
    critical: int = 0
    info: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "contract_id": self.contract_id,
            "widget_type": self.widget_type,
            "passed": self.passed,
            "violation_count": len(self.violations),
            "warnings": self.warnings,
            "errors": self.errors,
            "critical": self.critical,
            "info": self.info,
            "violations": [v.to_dict() for v in self.violations],
        }


# ---------------------------------------------------------------------------
# Projection Contract Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProjectionContract:
    """A projection contract defining the expected shape of a widget's data.
    
    This is the canonical contract that widgets must adhere to.
    
    Attributes:
        contract_id: Unique identifier for this contract
        widget_type: The type of widget this contract is for
        version: Contract version (e.g., "v1", "v2")
        description: Human-readable description
        fields: Dictionary of field name to ProjectionField
        field_list: List of all fields (for ordered iteration)
        authority_bindings: List of authority bindings for this contract
        requires_receipt_backing: Whether any fields in this contract require receipt backing
        requires_audit_backing: Whether any fields in this contract require audit backing
        validation_order: Deterministic order for field validation
        invariant_checks: Custom invariant checks (callables that return violations)
    """
    
    contract_id: str
    widget_type: str
    version: str = "v1"
    description: str = ""
    fields: Dict[str, ProjectionField] = field(default_factory=dict)
    field_list: Tuple[str, ...] = ()
    authority_bindings: Tuple[ProjectionAuthorityBinding, ...] = ()
    requires_receipt_backing: bool = False
    requires_audit_backing: bool = False
    validation_order: Tuple[str, ...] = ()
    invariant_checks: Tuple[Callable[[Dict[str, Any]], Optional[ProjectionContractViolation]], ...] = ()
    
    def __post_init__(self):
        # Ensure frozen
        # Compute derived fields
        object.__setattr__(self, 'requires_receipt_backing', any(
            f.receipt_backing == ReceiptBackingRequirement.REQUIRED
            for f in self.fields.values()
        ))
        object.__setattr__(self, 'requires_audit_backing', any(
            f.audit_backing == AuditBackingRequirement.REQUIRED
            for f in self.fields.values()
        ))
        
        # Ensure field_list is populated
        if not self.field_list:
            object.__setattr__(self, 'field_list', tuple(self.fields.keys()))
        
        # Ensure validation_order is populated
        if not self.validation_order:
            object.__setattr__(self, 'validation_order', self.field_list)
    
    def __hash__(self) -> int:
        # Exclude callable fields (invariant_checks) from hash as they are not hashable
        # Hash only the structural parts that are deterministic
        return hash((
            self.contract_id,
            self.widget_type,
            self.version,
            self.description,
            frozenset((k, v) for k, v in sorted(self.fields.items())),
            self.field_list,
            self.authority_bindings,
            self.requires_receipt_backing,
            self.requires_audit_backing,
            self.validation_order,
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "contract_id": self.contract_id,
            "widget_type": self.widget_type,
            "version": self.version,
            "description": self.description,
            "fields": {name: field.to_dict() for name, field in self.fields.items()},
            "field_list": list(self.field_list),
            "authority_bindings": [b.to_dict() for b in self.authority_bindings],
            "requires_receipt_backing": self.requires_receipt_backing,
            "requires_audit_backing": self.requires_audit_backing,
            "validation_order": list(self.validation_order),
        }
    
    def validate(self, data: Dict[str, Any], repo_root: Optional["Path"] = None) -> ProjectionContractCheckResult:
        """Validate projection data against this contract.
        
        Args:
            data: The projection data to validate
            repo_root: Optional repository root for path-based validation
            
        Returns:
            ProjectionContractCheckResult with all violations found
        """
        violations: List[ProjectionContractViolation] = []
        
        # Check required fields
        for field_name in self.validation_order:
            if field_name not in self.fields:
                continue
            
            field_def = self.fields[field_name]
            value = data.get(field_name)
            
            # Validate the field
            violation = field_def.validate_value(value, repo_root)
            if violation is not None:
                # Add contract/widglet info
                violation = ProjectionContractViolation(
                    violation_id=violation.violation_id,
                    violation_code=violation.violation_code,
                    severity=violation.severity,
                    title=violation.title,
                    message=violation.message,
                    field_name=violation.field_name,
                    expected_type=violation.expected_type,
                    actual_value=violation.actual_value,
                    contract_id=self.contract_id,
                    widget_type=self.widget_type,
                    details=violation.details,
                    timestamp=violation.timestamp,
                )
                violations.append(violation)
        
        # Run invariant checks
        for check in self.invariant_checks:
            try:
                violation = check(data)
                if violation is not None:
                    # Add contract info
                    violation = ProjectionContractViolation(
                        violation_id=violation.violation_id,
                        violation_code=violation.violation_code,
                        severity=violation.severity,
                        title=violation.title,
                        message=violation.message,
                        field_name=violation.field_name,
                        expected_type=violation.expected_type,
                        actual_value=violation.actual_value,
                        contract_id=self.contract_id,
                        widget_type=self.widget_type,
                        details=violation.details,
                        timestamp=violation.timestamp,
                    )
                    violations.append(violation)
            except Exception:
                # Invariant check raised an exception - treat as error
                violations.append(ProjectionContractViolation(
                    violation_id=f"{self.contract_id}_invariant_error",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.ERROR,
                    title=f"Invariant check failed for {self.contract_id}",
                    message="An invariant check raised an exception",
                    contract_id=self.contract_id,
                    widget_type=self.widget_type,
                ))
        
        # Count by severity
        warning_count = sum(1 for v in violations if v.severity == ProjectionViolationSeverity.WARNING)
        error_count = sum(1 for v in violations if v.severity == ProjectionViolationSeverity.ERROR)
        critical_count = sum(1 for v in violations if v.severity == ProjectionViolationSeverity.CRITICAL)
        info_count = sum(1 for v in violations if v.severity == ProjectionViolationSeverity.INFO)
        
        return ProjectionContractCheckResult(
            contract_id=self.contract_id,
            widget_type=self.widget_type,
            passed=len(violations) == 0,
            violations=tuple(violations),
            warnings=warning_count,
            errors=error_count,
            critical=critical_count,
            info=info_count,
        )


# ---------------------------------------------------------------------------
# Projection Contract Summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProjectionContractSummary:
    """Summary of all projection contract validation results.
    
    Attributes:
        total_contracts: Total number of contracts checked
        total_violations: Total number of violations found
        contracts_checked: Number of contracts that were checked
        violations_by_contract: Violations grouped by contract
        violations_by_severity: Violations grouped by severity
        violations_by_widget_type: Violations grouped by widget type
        authority_binding_failures: Count of authority binding failures
        receipt_backing_failures: Count of receipt backing failures
        audit_backing_failures: Count of audit backing failures
        placeholder_violations: Count of placeholder violations
        overall_status: Overall status string
    """
    
    total_contracts: int = 0
    total_violations: int = 0
    contracts_checked: int = 0
    violations_by_contract: Dict[str, int] = field(default_factory=dict)
    violations_by_severity: Dict[str, int] = field(default_factory=dict)
    violations_by_widget_type: Dict[str, int] = field(default_factory=dict)
    authority_binding_failures: int = 0
    receipt_backing_failures: int = 0
    audit_backing_failures: int = 0
    placeholder_violations: int = 0
    overall_status: str = "unknown"
    contract_results: Tuple[ProjectionContractCheckResult, ...] = ()
    all_violations: Tuple[ProjectionContractViolation, ...] = ()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "total_contracts": self.total_contracts,
            "total_violations": self.total_violations,
            "contracts_checked": self.contracts_checked,
            "violations_by_contract": dict(self.violations_by_contract),
            "violations_by_severity": dict(self.violations_by_severity),
            "violations_by_widget_type": dict(self.violations_by_widget_type),
            "authority_binding_failures": self.authority_binding_failures,
            "receipt_backing_failures": self.receipt_backing_failures,
            "audit_backing_failures": self.audit_backing_failures,
            "placeholder_violations": self.placeholder_violations,
            "overall_status": self.overall_status,
            "contract_results": [r.to_dict() for r in self.contract_results],
            "all_violations": [v.to_dict() for v in self.all_violations],
        }


# ---------------------------------------------------------------------------
# Contract Registry
# ---------------------------------------------------------------------------

class ProjectionContractRegistry:
    """Registry of all known projection contracts.
    
    This is a singleton that holds all projection contracts for validation.
    """
    
    _instance: Optional["ProjectionContractRegistry"] = None
    
    def __new__(cls) -> "ProjectionContractRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._contracts: Dict[str, ProjectionContract] = {}
        return cls._instance
    
    def register(self, contract: ProjectionContract) -> None:
        """Register a projection contract."""
        self._contracts[contract.contract_id] = contract
        self._contracts[contract.widget_type] = contract  # Also index by widget type
    
    def get(self, contract_id: str) -> Optional[ProjectionContract]:
        """Get a contract by ID or widget type."""
        return self._contracts.get(contract_id)
    
    def get_by_widget_type(self, widget_type: str) -> Optional[ProjectionContract]:
        """Get a contract by widget type."""
        return self._contracts.get(widget_type)
    
    def all_contracts(self) -> Tuple[ProjectionContract, ...]:
        """Get all registered contracts."""
        # Return unique contracts (deduplicated by contract_id)
        seen_ids: Set[str] = set()
        result: List[ProjectionContract] = []
        for contract in self._contracts.values():
            if contract.contract_id not in seen_ids:
                seen_ids.add(contract.contract_id)
                result.append(contract)
        return tuple(result)
    
    def reset(self) -> None:
        """Reset the registry (mainly for testing)."""
        self._contracts.clear()
        self._instance = None


# Get the global registry instance
get_contract_registry = ProjectionContractRegistry


# ---------------------------------------------------------------------------
# Contract Builder Helpers
# ---------------------------------------------------------------------------

def _field(
    name: str,
    type_: str = "string",
    required: bool = False,
    placeholder: Any = None,
    authority: AuthorityBindingType = AuthorityBindingType.STATIC,
    receipt_backing: ReceiptBackingRequirement = ReceiptBackingRequirement.NOT_REQUIRED,
    audit_backing: AuditBackingRequirement = AuditBackingRequirement.NOT_REQUIRED,
    allowed_values: Optional[Set[str]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    description: str = "",
) -> ProjectionField:
    """Helper to create a ProjectionField with defaults."""
    return ProjectionField(
        field_name=name,
        field_type=type_,
        required=required,
        placeholder=placeholder,
        authority_binding=authority,
        receipt_backing=receipt_backing,
        audit_backing=audit_backing,
        allowed_values=allowed_values,
        min_value=min_value,
        max_value=max_value,
        description=description,
    )


def _contract(
    contract_id: str,
    widget_type: str,
    description: str = "",
    version: str = "v1",
    fields: Optional[Dict[str, ProjectionField]] = None,
    authority_bindings: Optional[List[ProjectionAuthorityBinding]] = None,
    invariant_checks: Optional[List[Callable[[Dict[str, Any]], Optional[ProjectionContractViolation]]]] = None,
    requires_receipt_backing: bool = False,
    requires_audit_backing: bool = False,
) -> ProjectionContract:
    """Helper to create a ProjectionContract with defaults."""
    return ProjectionContract(
        contract_id=contract_id,
        widget_type=widget_type,
        description=description,
        version=version,
        fields=fields or {},
        authority_bindings=tuple(authority_bindings or []),
        invariant_checks=tuple(invariant_checks or []),
        requires_receipt_backing=requires_receipt_backing,
        requires_audit_backing=requires_audit_backing,
    )


# ---------------------------------------------------------------------------
# Canonical Projection Contracts
# ---------------------------------------------------------------------------

def _invariant_transient_progress(
    data: Dict[str, Any],
    field_path: str = "progress_state.transient",
    expected: bool = True,
) -> Optional[ProjectionContractViolation]:
    """Invariant: progress_state.transient must be True."""
    progress_state = data.get("progress_state")
    if isinstance(progress_state, dict):
        transient = progress_state.get("transient")
        if transient is not True:
            return ProjectionContractViolation(
                violation_id="invariant_transient_progress",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="progress_state.transient must be True",
                message=f"Invariant violation: {field_path} must be True but is {transient}",
                field_name=field_path,
                expected_type="boolean",
                actual_value=transient,
            )
    return None


def _invariant_progress_source(
    data: Dict[str, Any],
) -> Optional[ProjectionContractViolation]:
    """Invariant: progress_state.source must be 'progress_event'."""
    progress_state = data.get("progress_state")
    if isinstance(progress_state, dict):
        source = progress_state.get("source")
        if source != "progress_event":
            return ProjectionContractViolation(
                violation_id="invariant_progress_source",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="progress_state.source must be 'progress_event'",
                message=f"Invariant violation: progress_state.source must be 'progress_event' but is '{source}'",
                field_name="progress_state.source",
                expected_type="string",
                actual_value=source,
            )
    return None


def _invariant_advisory_only_warning(
    data: Dict[str, Any],
    warning_field: str = "advisory_only_warning",
) -> Optional[ProjectionContractViolation]:
    """Invariant: advisory_only_widgets must contain advisory warning."""
    warning = data.get(warning_field)
    if isinstance(warning, str):
        warning_lower = warning.lower()
        if "advisory" not in warning_lower or "not authoritative" not in warning_lower:
            return ProjectionContractViolation(
                violation_id="invariant_missing_advisory_warning",
                violation_code=ProjectionContractViolationCode.FALSE_AUTHORITATIVE_CLAIM,
                severity=ProjectionViolationSeverity.ERROR,
                title="Missing or insufficient advisory_only warning",
                message=f"Field '{warning_field}' must contain 'advisory' and 'not authoritative' but is: '{warning}'",
                field_name=warning_field,
                expected_type="string",
                actual_value=warning,
            )
    return None


def _invariant_progress_receipts_not_created(
    data: Dict[str, Any],
) -> Optional[ProjectionContractViolation]:
    """Invariant: auditability_state.progress_receipts must be 'not_created'."""
    auditability_state = data.get("auditability_state")
    if isinstance(auditability_state, dict):
        progress_receipts = auditability_state.get("progress_receipts")
        if progress_receipts != "not_created":
            return ProjectionContractViolation(
                violation_id="invariant_progress_receipts_not_created",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="auditability_state.progress_receipts must be 'not_created'",
                message=f"Invariant violation: auditability_state.progress_receipts must be 'not_created' but is '{progress_receipts}'",
                field_name="auditability_state.progress_receipts",
                expected_type="string",
                actual_value=progress_receipts,
            )
    return None


def _invariant_progress_receipt_plan_advisory_only(
    data: Dict[str, Any],
) -> Optional[ProjectionContractViolation]:
    """Invariant: auditability_state.progress_receipt_plan must be 'advisory_only'."""
    auditability_state = data.get("auditability_state")
    if isinstance(auditability_state, dict):
        plan = auditability_state.get("progress_receipt_plan")
        if plan != "advisory_only":
            return ProjectionContractViolation(
                violation_id="invariant_progress_receipt_plan",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="auditability_state.progress_receipt_plan must be 'advisory_only'",
                message=f"Invariant violation: auditability_state.progress_receipt_plan must be 'advisory_only' but is '{plan}'",
                field_name="auditability_state.progress_receipt_plan",
                expected_type="string",
                actual_value=plan,
            )
    return None


def _invariant_receipt_candidate_inert(
    data: Dict[str, Any],
) -> Optional[ProjectionContractViolation]:
    """Invariant: auditability_state.receipt_candidate must be 'inert'."""
    auditability_state = data.get("auditability_state")
    if isinstance(auditability_state, dict):
        candidate = auditability_state.get("receipt_candidate")
        if candidate != "inert":
            return ProjectionContractViolation(
                violation_id="invariant_receipt_candidate_inert",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="auditability_state.receipt_candidate must be 'inert'",
                message=f"Invariant violation: auditability_state.receipt_candidate must be 'inert' but is '{candidate}'",
                field_name="auditability_state.receipt_candidate",
                expected_type="string",
                actual_value=candidate,
            )
    return None


def _invariant_evidence_refs_inert(
    data: Dict[str, Any],
) -> Optional[ProjectionContractViolation]:
    """Invariant: auditability_state.evidence_refs must be 'inert'."""
    auditability_state = data.get("auditability_state")
    if isinstance(auditability_state, dict):
        evidence_refs = auditability_state.get("evidence_refs")
        if evidence_refs != "inert":
            return ProjectionContractViolation(
                violation_id="invariant_evidence_refs_inert",
                violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                severity=ProjectionViolationSeverity.CRITICAL,
                title="auditability_state.evidence_refs must be 'inert'",
                message=f"Invariant violation: auditability_state.evidence_refs must be 'inert' but is '{evidence_refs}'",
                field_name="auditability_state.evidence_refs",
                expected_type="string",
                actual_value=evidence_refs,
            )
    return None


# ---------------------------------------------------------------------------
# Define Canonical Projection Contracts
# ---------------------------------------------------------------------------

# AppTitle contract
APP_TITLE_CONTRACT = _contract(
    contract_id="projection.contract.app_title",
    widget_type="AppTitle",
    description="App title widget displaying application name and subtitle",
    fields={
        "title": _field("title", required=True, placeholder="Rig", authority=AuthorityBindingType.STATIC),
        "subtitle": _field("subtitle", required=False, placeholder="", authority=AuthorityBindingType.STATIC),
    },
)

# GateBadge contract
GATE_BADGE_CONTRACT = _contract(
    contract_id="projection.contract.gate_badge",
    widget_type="GateBadge",
    description="Status badge with severity level",
    fields={
        "label": _field("label", required=True, placeholder="No active gate", authority=AuthorityBindingType.DERIVED),
        "severity": _field("severity", required=True, placeholder="idle", 
                          allowed_values={"info", "success", "warning", "attention", "danger", "idle"},
                          authority=AuthorityBindingType.DERIVED),
    },
)

# MetricStack contract
METRIC_STACK_CONTRACT = _contract(
    contract_id="projection.contract.metric_stack",
    widget_type="MetricStack",
    description="Stack of metric items",
    fields={
        "title": _field("title", required=True, placeholder="Metrics", authority=AuthorityBindingType.STATIC),
        "items": _field("items", type_="array", required=True, placeholder=[], authority=AuthorityBindingType.ADVISORY),
    },
)

# WorkspaceHeader contract
WORKSPACE_HEADER_CONTRACT = _contract(
    contract_id="projection.contract.workspace_header",
    widget_type="WorkspaceHeader",
    description="Workspace identity and status header",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="workspace_header_source",
            source_module="rig.domain.workspace_status",
            source_function="build_workspace_status_summary",
            source_type="workspace_record",
            mutable=False,
            description="Workspace header data derived from WorkspaceStatusSummary",
        ),
    ],
    fields={
        "repo_root": _field("repo_root", required=True, placeholder="", 
                            authority=AuthorityBindingType.CANONICAL, description="Repository root path"),
        "workspace_id": _field("workspace_id", required=False, placeholder=None, 
                               authority=AuthorityBindingType.CANONICAL, description="Current workspace ID"),
        "workspace_status": _field("workspace_status", required=True, placeholder="unselected",
                                   authority=AuthorityBindingType.CANONICAL, description="Workspace status string"),
        "workspace_path": _field("workspace_path", required=False, placeholder=None,
                                  authority=AuthorityBindingType.CANONICAL, description="Workspace filesystem path"),
        "branch": _field("branch", required=True, placeholder="", 
                         authority=AuthorityBindingType.CANONICAL, description="Current git branch"),
        "head": _field("head", required=False, placeholder=None,
                       authority=AuthorityBindingType.CANONICAL, description="Current commit hash"),
        "authority_label": _field("authority_label", required=True, placeholder="Workspace control plane",
                                   authority=AuthorityBindingType.STATIC),
    },
)

# WorkspaceGitState contract
WORKSPACE_GIT_STATE_CONTRACT = _contract(
    contract_id="projection.contract.workspace_git_state",
    widget_type="WorkspaceGitState",
    description="Git state for the workspace",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="git_state_source",
            source_module="projection_builder",
            source_function="_git_capture",
            source_type="git_commands",
            mutable=False,
            description="Git state derived from git commands",
        ),
    ],
    fields={
        "branch": _field("branch", required=True, placeholder="HEAD", 
                         authority=AuthorityBindingType.CANONICAL),
        "head": _field("head", required=False, placeholder=None, 
                       authority=AuthorityBindingType.CANONICAL),
        "dirty": _field("dirty", type_="boolean", required=True, placeholder=False,
                        authority=AuthorityBindingType.CANONICAL),
        "dirty_files_count": _field("dirty_files_count", type_="number", required=True, placeholder=0,
                                     min_value=0, authority=AuthorityBindingType.CANONICAL),
        "safe_to_commit": _field("safe_to_commit", type_="boolean", required=True, placeholder=False,
                                  authority=AuthorityBindingType.CANONICAL),
        "reason": _field("reason", required=True, placeholder="", 
                         authority=AuthorityBindingType.DERIVED, description="Human-readable reason for safe_to_commit"),
    },
)

# WorkspaceLaneSummary contract
WORKSPACE_LANE_SUMMARY_CONTRACT = _contract(
    contract_id="projection.contract.workspace_lane_summary",
    widget_type="WorkspaceLaneSummary",
    description="Agent lane summary (advisory - lanes not connected yet)",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="lane_summary_connectivity",
            source_module="projection_builder",
            source_function="_workspace_lane_summary_widget",
            source_type="advisory",
            mutable=False,
            description="Lane data is advisory only - not connected to workspace yet",
        ),
    ],
    fields={
        "status": _field("status", required=True, placeholder="not_connected",
                         authority=AuthorityBindingType.ADVISORY),
        "lane_count": _field("lane_count", type_="number", required=True, placeholder=0,
                             min_value=0, authority=AuthorityBindingType.ADVISORY),
        "active_lanes": _field("active_lanes", type_="number", required=True, placeholder=0,
                              min_value=0, authority=AuthorityBindingType.ADVISORY),
        "clean_lanes": _field("clean_lanes", type_="number", required=True, placeholder=0,
                             min_value=0, authority=AuthorityBindingType.ADVISORY),
        "review_ready_lanes": _field("review_ready_lanes", type_="number", required=True, placeholder=0,
                                    min_value=0, authority=AuthorityBindingType.ADVISORY),
        "workspace_records": _field("workspace_records", type_="number", required=True, placeholder=0,
                                   min_value=0, authority=AuthorityBindingType.ADVISORY),
        "connected": _field("connected", type_="boolean", required=True, placeholder=False,
                           authority=AuthorityBindingType.ADVISORY),
        "message": _field("message", required=True, placeholder="", 
                          authority=AuthorityBindingType.ADVISORY),
        "next_action": _field("next_action", required=False, placeholder="",
                              authority=AuthorityBindingType.ADVISORY),
    },
)

# ProposalLifecycleConsole contract
PROPOSAL_LIFECYCLE_CONSOLE_CONTRACT = _contract(
    contract_id="projection.contract.proposal_lifecycle_console",
    widget_type="ProposalLifecycleConsole",
    description="Proposal lifecycle state console",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="lifecycle_workspace_summary",
            source_module="rig.domain.workspace_status",
            source_function="build_workspace_status_summary",
            source_type="workspace_record",
            mutable=False,
            description="Lifecycle projection derived from WorkspaceStatusSummary",
        ),
        ProjectionAuthorityBinding(
            binding_id="lifecycle_worksapce_records",
            source_module="rig.domain.workspace",
            source_function="list_workspaces_read_only",
            source_type="workspace_record",
            mutable=False,
            description="Uses workspace records for enrichment",
        ),
    ],
    fields={
        "lifecycle_id": _field("lifecycle_id", required=True, placeholder="workspace.proposal_lifecycle",
                              authority=AuthorityBindingType.CANONICAL),
        "stage": _field("stage", required=True, placeholder="workspace_unselected",
                        allowed_values={
                            "workspace_unselected", "workspace_ready", "gate_a_active",
                            "recommendation_available", "proposal_pending", "validation_pending",
                            "validation_passed", "validation_failed", "review_ready", "apply_blocked",
                        },
                        authority=AuthorityBindingType.CANONICAL),
        "title": _field("title", required=True, placeholder="Proposal Lifecycle Console",
                       authority=AuthorityBindingType.DERIVED),
        "summary": _field("summary", required=True, placeholder="", 
                         authority=AuthorityBindingType.DERIVED),
        "workspace_path": _field("workspace_path", required=False, placeholder=None,
                                  authority=AuthorityBindingType.CANONICAL),
        "current_gate": _field("current_gate", required=True, placeholder="A",
                               authority=AuthorityBindingType.CANONICAL),
        "allowed_actions": _field("allowed_actions", type_="array", required=True, placeholder=[],
                                  authority=AuthorityBindingType.CANONICAL),
        "blocked_actions": _field("blocked_actions", type_="array", required=True, placeholder=[],
                                 authority=AuthorityBindingType.CANONICAL),
        "next_safe_action": _field("next_safe_action", required=True, placeholder="",
                                    authority=AuthorityBindingType.DERIVED),
        "recommendation_state": _field("recommendation_state", type_="object", required=True, placeholder={},
                                       authority=AuthorityBindingType.CANONICAL, 
                                       description="Normalized recommendation summary"),
        "proposal_state": _field("proposal_state", type_="object", required=True, placeholder={},
                                authority=AuthorityBindingType.CANONICAL,
                                description="Normalized proposal summary"),
        "validation_state": _field("validation_state", type_="object", required=True, placeholder={},
                                 authority=AuthorityBindingType.CANONICAL,
                                 description="Normalized validation summary"),
        "progress_state": _field("progress_state", type_="object", required=True, placeholder={},
                                authority=AuthorityBindingType.STATIC,
                                description="Progress telemetry state (transient)"),
        "auditability_state": _field("auditability_state", type_="object", required=True, placeholder={},
                                     authority=AuthorityBindingType.STATIC,
                                     description="Auditability markers (inert)"),
        "warnings": _field("warnings", type_="array", required=True, placeholder=[],
                           authority=AuthorityBindingType.STATIC),
        "metadata": _field("metadata", type_="object", required=True, placeholder={},
                          authority=AuthorityBindingType.STATIC),
    },
    invariant_checks=[
        _invariant_transient_progress,
        _invariant_progress_source,
        _invariant_progress_receipts_not_created,
        _invariant_progress_receipt_plan_advisory_only,
        _invariant_receipt_candidate_inert,
        _invariant_evidence_refs_inert,
    ],
)

# AuditTrailCard contract
AUDIT_TRAIL_CARD_CONTRACT = _contract(
    contract_id="projection.contract.audit_trail_card",
    widget_type="AuditTrailCard",
    description="Audit trail visibility card",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="audit_trail_directory",
            source_module="rig.domain.workspace_audit",
            source_function="build_auditability_state",
            source_type="audit_event",
            mutable=False,
            description="Audit state from audit directory and workspace records",
        ),
    ],
    fields={
        "audit_completeness": _field("audit_completeness", required=True,
                                     allowed_values={
                                         "unknown", "not_created", "not_proof", "not_run", "complete",
                                     },
                                     placeholder="unknown",
                                     authority=AuthorityBindingType.CANONICAL),
        "last_authoritative_event_id": _field("last_authoritative_event_id", required=False,
                                              placeholder="unknown",
                                              authority=AuthorityBindingType.CANONICAL),
        "receipt_status_summary": _field("receipt_status_summary", type_="object", required=True,
                                        placeholder={}, authority=AuthorityBindingType.CANONICAL),
        "missing_receipts": _field("missing_receipts", type_="array", required=True,
                                  placeholder=[], authority=AuthorityBindingType.CANONICAL),
        "advisory_only_events": _field("advisory_only_events", type_="number", required=True,
                                      placeholder=0, min_value=0,
                                      authority=AuthorityBindingType.CANONICAL),
        "authoritative_events": _field("authoritative_events", type_="number", required=True,
                                       placeholder=0, min_value=0,
                                       authority=AuthorityBindingType.CANONICAL),
        "next_missing_audit_action": _field("next_missing_audit_action", required=True,
                                           placeholder="no_receipt",
                                           authority=AuthorityBindingType.DERIVED),
        "advisory_only_warning": _field("advisory_only_warning", required=True,
                                        placeholder="Public intake and funding data is advisory_only. External systems are NOT authoritative.",
                                        authority=AuthorityBindingType.STATIC),
    },
    requires_audit_backing=True,
)

# EmptyStateCard contract
EMPTY_STATE_CARD_CONTRACT = _contract(
    contract_id="projection.contract.empty_state_card",
    widget_type="EmptyStateCard",
    description="Empty state display card",
    fields={
        "title": _field("title", required=True, placeholder="", authority=AuthorityBindingType.STATIC),
        "body": _field("body", required=True, placeholder="", authority=AuthorityBindingType.STATIC),
    },
)

# EvidenceCard contract
EVIDENCE_CARD_CONTRACT = _contract(
    contract_id="projection.contract.evidence_card",
    widget_type="EvidenceCard",
    description="Evidence summary card",
    fields={
        "title": _field("title", required=True, placeholder="Evidence", authority=AuthorityBindingType.STATIC),
        "state": _field("state", type_="object", required=True, placeholder={},
                       authority=AuthorityBindingType.DERIVED,
                       description="State object with label and severity"),
        "body": _field("body", required=True, placeholder="", authority=AuthorityBindingType.STATIC),
    },
)

# ValidatorStack contract
VALIDATOR_STACK_CONTRACT = _contract(
    contract_id="projection.contract.validator_stack",
    widget_type="ValidatorStack",
    description="Validator stack with state and results",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="validator_receipts",
            source_module="rig.domain.workspace",
            source_function="generate_validation_result",
            source_type="receipt",
            mutable=False,
            description="Validator receipts back this data",
        ),
    ],
    fields={
        "title": _field("title", required=True, placeholder="Validators", authority=AuthorityBindingType.STATIC),
        "state": _field("state", type_="object", required=True, placeholder={},
                       authority=AuthorityBindingType.CANONICAL,
                       description="State with label and severity"),
        "summary": _field("summary", required=True, placeholder="No validation performed yet.",
                          authority=AuthorityBindingType.DERIVED),
        "items": _field("items", type_="array", required=True, placeholder=[],
                        authority=AuthorityBindingType.CANONICAL),
        "run_in_progress": _field("run_in_progress", type_="boolean", required=True, placeholder=False,
                                  authority=AuthorityBindingType.CANONICAL),
        "running_validator_id": _field("running_validator_id", required=False, placeholder=None,
                                       authority=AuthorityBindingType.CANONICAL),
    },
    requires_receipt_backing=True,
)

# ReceiptList contract
RECEIPT_LIST_CONTRACT = _contract(
    contract_id="projection.contract.receipt_list",
    widget_type="ReceiptList",
    description="List of receipts",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="receipt_store",
            source_module="rig.domain.receipts",
            source_function="get_receipt_store",
            source_type="receipt",
            mutable=False,
            description="Receipts come from the canonical receipt store",
        ),
    ],
    fields={
        "title": _field("title", required=True, placeholder="Receipts", authority=AuthorityBindingType.STATIC),
        "receipts": _field("receipts", type_="array", required=True, placeholder=[],
                           authority=AuthorityBindingType.CANONICAL,
                           receipt_backing=ReceiptBackingRequirement.REQUIRED),
    },
    requires_receipt_backing=True,
)

# BackendStatus contract
BACKEND_STATUS_CONTRACT = _contract(
    contract_id="projection.contract.backend_status",
    widget_type="BackendStatus",
    description="Native bridge backend status",
    fields={
        "title": _field("title", required=True, placeholder="Native bridge", authority=AuthorityBindingType.STATIC),
        "body": _field("body", required=True, placeholder="pywebview · WebSocket streaming",
                       authority=AuthorityBindingType.STATIC),
        "revision": _field("revision", type_="number", required=True, placeholder=1,
                           min_value=0, authority=AuthorityBindingType.STATIC),
    },
)

# CommandProgressCard contract
COMMAND_PROGRESS_CARD_CONTRACT = _contract(
    contract_id="projection.contract.command_progress_card",
    widget_type="CommandProgressCard",
    description="Command progress tracking card",
    fields={
        "command": _field("command", required=True, placeholder="", authority=AuthorityBindingType.ADVISORY),
        "phase": _field("phase", required=True, placeholder="operation.log", 
                        authority=AuthorityBindingType.ADVISORY),
        "status": _field("status", required=True, placeholder="unknown",
                         authority=AuthorityBindingType.ADVISORY),
        "level": _field("level", required=True, placeholder="info",
                        allowed_values={"debug", "info", "warning", "error"},
                        authority=AuthorityBindingType.ADVISORY),
        "message": _field("message", required=True, placeholder="", authority=AuthorityBindingType.ADVISORY),
        "sequence": _field("sequence", type_="number", required=True, placeholder=0,
                           min_value=0, authority=AuthorityBindingType.ADVISORY),
        "timestamp": _field("timestamp", required=True, placeholder="", authority=AuthorityBindingType.ADVISORY),
        "events": _field("events", type_="array", required=True, placeholder=[],
                        authority=AuthorityBindingType.ADVISORY),
        "metadata": _field("metadata", type_="object", required=True, placeholder={},
                          authority=AuthorityBindingType.ADVISORY),
    },
)

# FundingSummaryCard contract (ADVISORY ONLY)
FUNDING_SUMMARY_CARD_CONTRACT = _contract(
    contract_id="projection.contract.funding_summary_card",
    widget_type="FundingSummaryCard",
    description="Funding summary - ADVISORY ONLY",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="funding_advisory",
            source_module="public_intake",
            source_function="",
            source_type="public_intake_packet",
            mutable=False,
            description="Funding data is ADVISORY ONLY - External systems are NOT authoritative",
        ),
    ],
    fields={
        "title": _field("title", required=True, placeholder="", authority=AuthorityBindingType.ADVISORY),
        "summary": _field("summary", required=True, placeholder="", authority=AuthorityBindingType.ADVISORY),
        "total": _field("total", type_="number", required=True, placeholder=0, min_value=0,
                        authority=AuthorityBindingType.ADVISORY),
        "advisory_note": _field("advisory_note", required=True,
                                placeholder="External funding data is advisory only. Do not treat as authoritative.",
                                authority=AuthorityBindingType.STATIC),
        "pledge_count": _field("pledge_count", type_="number", required=False, placeholder=0,
                              min_value=0, authority=AuthorityBindingType.ADVISORY),
        "backer_count": _field("backer_count", type_="number", required=False, placeholder=0,
                              min_value=0, authority=AuthorityBindingType.ADVISORY),
        "funding_status": _field("funding_status", required=False, placeholder="advisory_only",
                                 authority=AuthorityBindingType.ADVISORY),
    },
    invariant_checks=[_invariant_advisory_only_warning],
)

# IntegrityStatusCard contract (NEW for Phase 4)
INTEGRITY_STATUS_CARD_CONTRACT = _contract(
    contract_id="projection.contract.integrity_status_card",
    widget_type="IntegrityStatusCard",
    description="Projection integrity status card",
    authority_bindings=[
        ProjectionAuthorityBinding(
            binding_id="integrity_summary",
            source_module="rig.domain.integrity",
            source_function="validate_repository_integrity",
            source_type="integrity_finding",
            mutable=False,
            description="Integrity status derived from IntegritySummary",
        ),
    ],
    fields={
        "integrity_status": _field("integrity_status", required=True, placeholder="unknown",
                                  allowed_values={
                                      "unknown", "clean", "warnings", "errors", "critical",
                                  },
                                  authority=AuthorityBindingType.CANONICAL),
        "contract_status": _field("contract_status", required=True, placeholder="unknown",
                                 allowed_values={
                                     "unknown", "all_passed", "violations_found",
                                 },
                                 authority=AuthorityBindingType.CANONICAL),
        "projection_violation_count": _field("projection_violation_count", type_="number", required=True,
                                            placeholder=0, min_value=0,
                                            authority=AuthorityBindingType.CANONICAL),
        "authority_mismatch_count": _field("authority_mismatch_count", type_="number", required=True,
                                          placeholder=0, min_value=0,
                                          authority=AuthorityBindingType.CANONICAL),
        "receipt_backing_failure_count": _field("receipt_backing_failure_count", type_="number", required=True,
                                               placeholder=0, min_value=0,
                                               authority=AuthorityBindingType.CANONICAL),
        "audit_backing_failure_count": _field("audit_backing_failure_count", type_="number", required=True,
                                              placeholder=0, min_value=0,
                                              authority=AuthorityBindingType.CANONICAL),
        "next_integrity_action": _field("next_integrity_action", required=True,
                                       placeholder="No integrity issues detected",
                                       authority=AuthorityBindingType.DERIVED),
        "stale_receipt_detected": _field("stale_receipt_detected", type_="boolean", required=True,
                                        placeholder=False, authority=AuthorityBindingType.CANONICAL),
        "orphaned_receipt_detected": _field("orphaned_receipt_detected", type_="boolean", required=True,
                                          placeholder=False, authority=AuthorityBindingType.CANONICAL),
        "orphaned_audit_detected": _field("orphaned_audit_detected", type_="boolean", required=True,
                                         placeholder=False, authority=AuthorityBindingType.CANONICAL),
    },
    requires_receipt_backing=True,
    requires_audit_backing=True,
)


# ---------------------------------------------------------------------------
# Contract Registration
# ---------------------------------------------------------------------------

def register_all_contracts(registry: Optional[ProjectionContractRegistry] = None) -> ProjectionContractRegistry:
    """Register all canonical projection contracts.
    
    Args:
        registry: Optional registry to use (defaults to global registry)
        
    Returns:
        The registry with all contracts registered
    """
    if registry is None:
        registry = get_contract_registry()
    
    # Register all contracts
    for contract in [
        APP_TITLE_CONTRACT,
        GATE_BADGE_CONTRACT,
        METRIC_STACK_CONTRACT,
        WORKSPACE_HEADER_CONTRACT,
        WORKSPACE_GIT_STATE_CONTRACT,
        WORKSPACE_LANE_SUMMARY_CONTRACT,
        PROPOSAL_LIFECYCLE_CONSOLE_CONTRACT,
        AUDIT_TRAIL_CARD_CONTRACT,
        EMPTY_STATE_CARD_CONTRACT,
        EVIDENCE_CARD_CONTRACT,
        VALIDATOR_STACK_CONTRACT,
        RECEIPT_LIST_CONTRACT,
        BACKEND_STATUS_CONTRACT,
        COMMAND_PROGRESS_CARD_CONTRACT,
        FUNDING_SUMMARY_CARD_CONTRACT,
        INTEGRITY_STATUS_CARD_CONTRACT,
    ]:
        registry.register(contract)
    
    return registry


# Auto-register contracts on module load
register_all_contracts()


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_projection_contract(
    widget_type: str,
    data: Dict[str, Any],
    repo_root: Optional["Path"] = None,
    registry: Optional[ProjectionContractRegistry] = None,
) -> ProjectionContractCheckResult:
    """Validate projection data against its registered contract.
    
    Args:
        widget_type: The type of widget to validate
        data: The projection data
        repo_root: Optional repository root for path validation
        registry: Optional contract registry to use
        
    Returns:
        ProjectionContractCheckResult with violations
    """
    if registry is None:
        registry = get_contract_registry()
    
    contract = registry.get_by_widget_type(widget_type)
    if contract is None:
        # Widget type not registered - this is a drift issue
        return ProjectionContractCheckResult(
            contract_id="unknown",
            widget_type=widget_type,
            passed=False,
            violations=(
                ProjectionContractViolation(
                    violation_id=f"unknown_contract_{widget_type}",
                    violation_code=ProjectionContractViolationCode.CONTRACT_MISMATCH,
                    severity=ProjectionViolationSeverity.ERROR,
                    title=f"Unknown widget type: {widget_type}",
                    message=f"No projection contract registered for widget type '{widget_type}'",
                    widget_type=widget_type,
                ),
            ),
            warnings=0,
            errors=1,
            critical=0,
            info=0,
        )
    
    return contract.validate(data, repo_root)


def validate_projection_authority_bindings(
    widget_type: str,
    data: Dict[str, Any],
    registry: Optional[ProjectionContractRegistry] = None,
) -> Tuple[ProjectionContractViolation, ...]:
    """Validate that authority-sensitive fields have proper bindings.
    
    Args:
        widget_type: The widget type to check
        data: The projection data
        registry: Optional contract registry
        
    Returns:
        Tuple of violations for authority binding issues
    """
    if registry is None:
        registry = get_contract_registry()
    
    contract = registry.get_by_widget_type(widget_type)
    if contract is None:
        return ()
    
    violations: List[ProjectionContractViolation] = []
    
    # Check if contract requires receipt backing but fields are missing
    if contract.requires_receipt_backing:
        # Look for receipt-related fields
        # Empty arrays/lists count as valid (no receipts = nothing to back)
        has_receipt_data = any(
            key in data and data[key] is not None for key in ("receipts", "receipt_status_summary", "receipt_paths")
        )
        if not has_receipt_data:
            violations.append(ProjectionContractViolation(
                violation_id=f"{widget_type}_missing_receipt_backing",
                violation_code=ProjectionContractViolationCode.RECEIPT_BACKING_MISSING,
                severity=ProjectionViolationSeverity.WARNING,
                title=f"Contract requires receipt backing but no receipt data found",
                message=f"Widget '{widget_type}' contract requires receipt backing but projection has no receipt data",
                contract_id=contract.contract_id,
                widget_type=widget_type,
            ))
    
    # Check if contract requires audit backing
    if contract.requires_audit_backing:
        has_audit_data = any(
            key in data and data[key] is not None for key in (
                "audit_completeness", "audit_events", "audit_trail",
                "authoritative_events", "advisory_only_events",
            )
        )
        if not has_audit_data:
            violations.append(ProjectionContractViolation(
                violation_id=f"{widget_type}_missing_audit_backing",
                violation_code=ProjectionContractViolationCode.AUDIT_BACKING_MISSING,
                severity=ProjectionViolationSeverity.WARNING,
                title=f"Contract requires audit backing but no audit data found",
                message=f"Widget '{widget_type}' contract requires audit backing but projection has no audit data",
                contract_id=contract.contract_id,
                widget_type=widget_type,
            ))
    
    return tuple(violations)


def validate_projection_placeholders(
    widget_type: str,
    data: Dict[str, Any],
    registry: Optional[ProjectionContractRegistry] = None,
) -> Tuple[ProjectionContractViolation, ...]:
    """Validate placeholder usage in projection data.
    
    Args:
        widget_type: The widget type
        data: The projection data
        registry: Optional contract registry
        
    Returns:
        Tuple of violations for placeholder issues
    """
    if registry is None:
        registry = get_contract_registry()
    
    contract = registry.get_by_widget_type(widget_type)
    if contract is None:
        return ()
    
    violations: List[ProjectionContractViolation] = []
    
    for field_name, field_def in contract.fields.items():
        value = data.get(field_name)
        
        # Check if this field is authority-sensitive and has a placeholder
        if field_def.authority_binding in (AuthorityBindingType.CANONICAL, AuthorityBindingType.DERIVED):
            # Only flag string placeholders. None is OK for non-required fields (genuinely absent)
            if isinstance(value, str):
                forbidden_string_placeholders = {
                    "",
                    "null",
                    "undefined",
                    PLACEHOLDER_UNKNOWN,
                    PLACEHOLDER_UNAVAILABLE,
                    PLACEHOLDER_NOT_CREATED,
                    PLACEHOLDER_NOT_RUN,
                    PLACEHOLDER_NOT_PROOF,
                }
                try:
                    is_forbidden = value in forbidden_string_placeholders
                except TypeError:
                    is_forbidden = False
            else:
                # Non-string values: only None on required fields is forbidden
                is_forbidden = (value is None and field_def.required)
            
            if is_forbidden:
                violations.append(ProjectionContractViolation(
                    violation_id=f"{widget_type}_{field_name}_placeholder",
                    violation_code=ProjectionContractViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER,
                    severity=ProjectionViolationSeverity.ERROR,
                    title=f"Authoritative field '{field_name}' has invalid placeholder",
                    message=f"Field '{field_name}' in widget '{widget_type}' is authoritative but has value: {value}",
                    field_name=field_name,
                    contract_id=contract.contract_id,
                    widget_type=widget_type,
                    actual_value=value,
                ))
    
    return tuple(violations)


def validate_projection_receipt_backing(
    widget_type: str,
    data: Dict[str, Any],
    repo_root: Optional["Path"] = None,
    all_receipt_ids: Optional[Set[str]] = None,
    registry: Optional[ProjectionContractRegistry] = None,
) -> Tuple[ProjectionContractViolation, ...]:
    """Validate that receipt-backed fields have valid receipt references.
    
    Args:
        widget_type: The widget type
        data: The projection data
        repo_root: Optional repository root
        all_receipt_ids: Set of all known receipt IDs
        registry: Optional contract registry
        
    Returns:
        Tuple of violations for receipt backing issues
    """
    # This is a placeholder - full implementation requires receipt scanning
    # which is handled by the integrity module
    return ()


def validate_projection_audit_backing(
    widget_type: str,
    data: Dict[str, Any],
    repo_root: Optional["Path"] = None,
    all_audit_event_ids: Optional[Set[str]] = None,
    registry: Optional[ProjectionContractRegistry] = None,
) -> Tuple[ProjectionContractViolation, ...]:
    """Validate that audit-backed fields have valid audit event references.
    
    Args:
        widget_type: The widget type
        data: The projection data
        repo_root: Optional repository root
        all_audit_event_ids: Set of all known audit event IDs
        registry: Optional contract registry
        
    Returns:
        Tuple of violations for audit backing issues
    """
    # This is a placeholder - full implementation requires audit event scanning
    # which is handled by the integrity module
    return ()


def build_projection_contract_summary(
    projection_data: Dict[str, Any],
    repo_root: Optional["Path"] = None,
    registry: Optional[ProjectionContractRegistry] = None,
) -> ProjectionContractSummary:
    """Build a summary of all projection contract violations in a full projection.
    
    Args:
        projection_data: The full UIProjection data
        repo_root: Optional repository root
        registry: Optional contract registry
        
    Returns:
        ProjectionContractSummary with all violations found
    """
    if registry is None:
        registry = get_contract_registry()
    
    # Collect all widget data from the projection
    widget_data_list: List[Tuple[str, str, Dict[str, Any]]] = []
    
    if "widgets" in projection_data and isinstance(projection_data["widgets"], dict):
        for widget_id, widget_projection in projection_data["widgets"].items():
            if hasattr(widget_projection, 'type') and hasattr(widget_projection, 'data'):
                widget_data_list.append((widget_id, widget_projection.type, widget_projection.data))
            elif isinstance(widget_projection, dict):
                widget_type = widget_projection.get("type", "unknown")
                data = widget_projection.get("data", widget_projection)
                widget_data_list.append((widget_id, widget_type, data))
    
    # Validate each widget against its contract
    all_violations: List[ProjectionContractViolation] = []
    contract_results: List[ProjectionContractCheckResult] = []
    
    total_contracts = len(registry.all_contracts())
    contracts_checked = 0
    
    violations_by_contract: Dict[str, int] = {}
    violations_by_severity: Dict[str, int] = {
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0,
    }
    violations_by_widget_type: Dict[str, int] = {}
    
    authority_binding_failures = 0
    receipt_backing_failures = 0
    audit_backing_failures = 0
    placeholder_violations = 0
    
    for widget_id, widget_type, data in widget_data_list:
        contracts_checked += 1
        
        # Validate contract
        result = validate_projection_contract(widget_type, data, repo_root, registry)
        contract_results.append(result)
        all_violations.extend(result.violations)
        
        # Validate authority bindings
        binding_violations = validate_projection_authority_bindings(widget_type, data, registry)
        all_violations.extend(binding_violations)
        authority_binding_failures += len(binding_violations)
        
        # Validate placeholders
        placeholder_viols = validate_projection_placeholders(widget_type, data, registry)
        all_violations.extend(placeholder_viols)
        placeholder_violations += len(placeholder_viols)
        
        # Count violations
        for violation in result.violations + binding_violations + placeholder_viols:
            # By contract
            contract_id = violation.contract_id or widget_type
            violations_by_contract[contract_id] = violations_by_contract.get(contract_id, 0) + 1
            
            # By severity
            severity_str = violation.severity.value
            violations_by_severity[severity_str] = violations_by_severity.get(severity_str, 0) + 1
            
            # By widget type
            violations_by_widget_type[widget_type] = violations_by_widget_type.get(widget_type, 0) + 1
            
            # Categorize
            if violation.violation_code in (
                ProjectionContractViolationCode.RECEIPT_BACKING_MISSING,
                ProjectionContractViolationCode.AUDIT_BACKING_MISSING,
            ):
                if violation.violation_code == ProjectionContractViolationCode.RECEIPT_BACKING_MISSING:
                    receipt_backing_failures += 1
                elif violation.violation_code == ProjectionContractViolationCode.AUDIT_BACKING_MISSING:
                    audit_backing_failures += 1
    
    # Determine overall status
    has_critical = violations_by_severity.get("critical", 0) > 0
    has_errors = violations_by_severity.get("error", 0) > 0
    has_warnings = violations_by_severity.get("warning", 0) > 0
    
    if has_critical:
        overall_status = "critical"
    elif has_errors:
        overall_status = "errors"
    elif has_warnings:
        overall_status = "warnings"
    else:
        overall_status = "clean"
    
    return ProjectionContractSummary(
        total_contracts=total_contracts,
        total_violations=len(all_violations),
        contracts_checked=contracts_checked,
        violations_by_contract=violations_by_contract,
        violations_by_severity=violations_by_severity,
        violations_by_widget_type=violations_by_widget_type,
        authority_binding_failures=authority_binding_failures,
        receipt_backing_failures=receipt_backing_failures,
        audit_backing_failures=audit_backing_failures,
        placeholder_violations=placeholder_violations,
        overall_status=overall_status,
        contract_results=tuple(contract_results),
        all_violations=tuple(all_violations),
    )


# ---------------------------------------------------------------------------
# Default Registry Access
# ---------------------------------------------------------------------------

# When imported, contracts are auto-registered
def get_all_contracts() -> Tuple[ProjectionContract, ...]:
    """Get all registered projection contracts."""
    return get_contract_registry().all_contracts()


def get_contract_by_widget_type(widget_type: str) -> Optional[ProjectionContract]:
    """Get a contract by widget type."""
    return get_contract_registry().get_by_widget_type(widget_type)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Types
    "AuthorityBindingType",
    "ReceiptBackingRequirement",
    "AuditBackingRequirement",
    "ProjectionContractViolationCode",
    "ProjectionViolationSeverity",
    "ProjectionField",
    "ProjectionAuthorityBinding",
    "ProjectionContractViolation",
    "ProjectionContractCheckResult",
    "ProjectionContractSummary",
    "ProjectionContractRegistry",
    # Constants
    "PLACEHOLDER_UNKNOWN",
    "PLACEHOLDER_UNAVAILABLE",
    "PLACEHOLDER_NOT_CREATED",
    "PLACEHOLDER_NOT_RUN",
    "PLACEHOLDER_NOT_PROOF",
    "PLACEHOLDER_ADVISORY_ONLY",
    "PLACEHOLDER_NOT_AUTHORITATIVE",
    "PLACEHOLDER_NO_RECEIPT",
    # Contracts
    "APP_TITLE_CONTRACT",
    "GATE_BADGE_CONTRACT",
    "METRIC_STACK_CONTRACT",
    "WORKSPACE_HEADER_CONTRACT",
    "WORKSPACE_GIT_STATE_CONTRACT",
    "WORKSPACE_LANE_SUMMARY_CONTRACT",
    "PROPOSAL_LIFECYCLE_CONSOLE_CONTRACT",
    "AUDIT_TRAIL_CARD_CONTRACT",
    "EMPTY_STATE_CARD_CONTRACT",
    "EVIDENCE_CARD_CONTRACT",
    "VALIDATOR_STACK_CONTRACT",
    "RECEIPT_LIST_CONTRACT",
    "BACKEND_STATUS_CONTRACT",
    "COMMAND_PROGRESS_CARD_CONTRACT",
    "FUNDING_SUMMARY_CARD_CONTRACT",
    "INTEGRITY_STATUS_CARD_CONTRACT",
    # Helpers
    "_field",
    "_contract",
    "register_all_contracts",
    "get_contract_registry",
    "get_all_contracts",
    "get_contract_by_widget_type",
    # Validation functions
    "validate_projection_contract",
    "validate_projection_authority_bindings",
    "validate_projection_placeholders",
    "validate_projection_receipt_backing",
    "validate_projection_audit_backing",
    "build_projection_contract_summary",
]
