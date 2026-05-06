"""
Anigma Remediation Loop MVP

Authority Class: Class 2 Gate Validator / Diagnostic Aggregator
Mutation Behavior: Non-mutating (read-only in plan_only/dry_run modes, sandbox mode deferred)
Canonical Inputs: .build/anigma/sentinel/latest.json, sent Mini App contracts
Generated Outputs: .build/anigma/loops/<run_id>/* receipts, derived Markdown/JSON
Baseline Behavior: Reads sentinel output, never writes baselines
CI/Review Usage: validate and review phases
Owner Doctrine: Anigma Architecture Governance, Rig Loop Engine Integration

This module implements a bounded remediation loop adapter that:
1. Reads Anigma Architecture Sentinel output
2. Groups issues by family/code
3. Creates bounded remediation plans
4. Optionally runs safe validators in dry-run mode
5. Writes reviewable receipts for human approval

Core doctrine:
- Rig runs loops; Anigma does not self-modify
- No unbounded agent loops
- No main worktree patch apply in MVP
- No Git mutation
- Stop on ambiguity or human-approval need
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import subprocess

# Constants
SCHEMA_VERSION = "anigma.remediation_loop.v1"
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
LOOPS_DIR = REPO_ROOT / ".build" / "anigma" / "loops"
SENTINEL_PATH = REPO_ROOT / ".build" / "anigma" / "sentinel" / "latest.json"

# MPI Issue classifiers - these map to sentinel issue codes
ISSUE_CLASSIFIERS = {
    "native_import_unknown_tier": {
        "family": "tier_classification",
        "severity": "warning",
        "title": "Native Import in Unknown Tier Package",
        "summary": "Found native platform imports in packages not explicitly classified as Tier 1, 2, or 3.",
        "root_cause": "Package tier classification is incomplete or missing.",
        "proposed_action": "Classify the package in CONTRACT_TIER_PACKAGES or BACKEND_TIER_PACKAGES.",
        "dry_run_commands": [
            [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
        ],
        "validators": [
            "Scripts/anigma_architecture_sentinel.py",
        ],
        "stop_conditions": [
            "issue_count_exceeds_threshold",
            "tier_classification_required",
            "max_steps_reached",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
    "native_leakage": {
        "family": "native_leakage",
        "severity": "error",
        "title": "Native Platform Import in Contract Tier",
        "summary": "Found forbidden Apple/platform imports in contract-tier packages.",
        "root_cause": "Contract-tier package has direct dependency on platform-specific framework.",
        "proposed_action": "Remove native import and refactor to use portable abstraction.",
        "dry_run_commands": [
            [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
        ],
        "validators": [
            "Scripts/anigma_architecture_sentinel.py",
        ],
        "stop_conditions": [
            "contract_violation_detected",
            "max_steps_reached",
        ],
        "human_approval_required": True,
        "sandbox_ready": False,
    },
    "native_leakage_contract_tier": {
        "family": "native_leakage",
        "severity": "error",
        "title": "Native Platform Import in Contract Tier",
        "summary": "Found forbidden Apple/platform imports in contract-tier packages.",
        "root_cause": "Contract package depends on platform-specific framework.",
        "proposed_action": "Remove native import, use portable abstraction, or move to backend package.",
        "dry_run_commands": [
            [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
        ],
        "validators": [
            "Scripts/anigma_architecture_sentinel.py",
        ],
        "stop_conditions": [
            "contract_violation_detected",
            "max_steps_reached",
        ],
        "human_approval_required": True,
        "sandbox_ready": False,
    },
    "exported_import_violation": {
        "family": "exported_imports",
        "severity": "error",
        "title": "Non-Allowlisted @_exported Import",
        "summary": "Found @_exported import that is not in the allowlist.",
        "root_cause": "Module uses @_exported import creating hidden dependencies.",
        "proposed_action": "Replace with explicit imports or add to ALLOWLISTED_EXPORTED_IMPORTS.",
        "dry_run_commands": [
            [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
        ],
        "validators": [
            "Scripts/anigma_architecture_sentinel.py",
            "Scripts/validate_exported_imports.py",
        ],
        "stop_conditions": [
            "export_violation_detected",
            "max_steps_reached",
        ],
        "human_approval_required": True,
        "sandbox_ready": False,
    },
    "tier_violation_contract_to_backend": {
        "family": "dependency_tier_violation",
        "severity": "error",
        "title": "Contract-Tier Package Depends on Backend-Tier",
        "summary": "Contract package has dependency on backend/executor package.",
        "root_cause": "Dependency graph violates tier isolation (T1 -> T2/3).",
        "proposed_action": "Refactor to use contract interfaces only.",
        "dry_run_commands": [
            [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
        ],
        "validators": [
            "Scripts/anigma_architecture_sentinel.py",
            "Scripts/validate_no_cycles.py",
        ],
        "stop_conditions": [
            "tier_violation_detected",
            "max_steps_reached",
        ],
        "human_approval_required": True,
        "sandbox_ready": False,
    },
    "missing_sentinel_proof": {
        "family": "missing_proof",
        "severity": "warning",
        "title": "Missing Proof Artifact",
        "summary": "Architecture-changing implementation lacks corresponding proof artifact.",
        "root_cause": "Proof-driven development requirement not met.",
        "proposed_action": "Create Docs/proofs/<task-id>.md with implementation details.",
        "dry_run_commands": [],
        "validators": [],
        "stop_conditions": [
            "proof_required",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
    "missing_validator": {
        "family": "validator_missing",
        "severity": "warning",
        "title": "Expected Validator Not Found",
        "summary": "A validator referenced in governance is missing.",
        "root_cause": "Validator file does not exist at expected path.",
        "proposed_action": "Create the missing validator or update references.",
        "dry_run_commands": [],
        "validators": [],
        "stop_conditions": [
            "validator_missing",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
    "missing_legal_file": {
        "family": "legal_profile_warning",
        "severity": "warning",
        "title": "Legal/Profile File Missing",
        "summary": "Required legal or app store profile file is missing.",
        "root_cause": "Compliance documentation incomplete.",
        "proposed_action": "Create the missing legal file.",
        "dry_run_commands": [],
        "validators": [],
        "stop_conditions": [
            "legal_file_missing",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
    "build_command_failed": {
        "family": "build_health",
        "severity": "warning",
        "title": "Build Command Failed",
        "summary": "Required build tooling command failed.",
        "root_cause": "Tool not available or malfunctional.",
        "proposed_action": "Install missing tool or fix configuration.",
        "dry_run_commands": [],
        "validators": [],
        "stop_conditions": [
            "tool_unavailable",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
    "generated_artifact_warning": {
        "family": "generated_artifacts",
        "severity": "warning",
        "title": "Generated Artifact Issue",
        "summary": "Issue with generated/derived artifacts.",
        "root_cause": "Build artifact validation check failed.",
        "proposed_action": "Review generated artifact handling.",
        "dry_run_commands": [],
        "validators": [],
        "stop_conditions": [
            "artifact_issue",
        ],
        "human_approval_required": False,
        "sandbox_ready": False,
    },
}

# Known safe validation commands
ALLOWED_VALIDATION_COMMANDS = [
    [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
    [sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "md"],
    [sys.executable, "scripts/rig.py", "anigma", "sentinel", "--format", "json"],
    [sys.executable, "scripts/rig.py", "schema", "validate", "--family", "anigma.architecture_sentinel.v1"],
    [sys.executable, "scripts/anigma_diagnose.py", "validate", "--task-id", "anigma-remediation-loop-mvp", "--command", "true"],
]


class StopReason(Enum):
    """Stop reasons for remediation loop."""
    NO_SENTINEL_OUTPUT = "no_sentinel_output_found"
    NO_ISSUES = "no_issues_to_remediate"
    ISSUE_FAMILY_UNKNOWN = "issue_family_unknown"
    ISSUE_COUNT_EXCEEDS_THRESHOLD = "issue_count_exceeds_threshold"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    SANDBOX_MODE_UNSUPPORTED = "sandbox_mode_unsupported"
    MAX_STEPS_REACHED = "max_steps_reached"
    VALIDATOR_UNAVAILABLE = "validator_unavailable"
    DIRTY_GIT = "dirty_git_detected"
    COMMAND_UNAVAILABLE = "command_unavailable"
    COMMAND_FAILED = "command_failed"
    COMPLETED = "remediation_completed"


@dataclass
class PlannedAction:
    """A single planned remediation action."""
    action_id: str
    description: str
    command: List[str]
    expected_outcome: str
    safety_level: Literal["read_only", "safe", "action", "auto_approve"]
    expected_duration_seconds: int = 30
    requires_approval: bool = False
    stop_conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RemediationPlan:
    """A bounded remediation plan for an issue family."""
    plan_id: str
    run_id: str
    issue_family: str
    issue_code: str
    selected_issue_ids: List[str]
    issue_count: int
    summary: str
    likely_root_cause: str
    proposed_required_action: str
    planned_actions: List[PlannedAction] = field(default_factory=list)
    validation_commands: List[List[str]] = field(default_factory=list)
    stop_conditions: List[str] = field(default_factory=list)
    mode: Literal["plan_only", "dry_run", "sandbox"] = "plan_only"
    max_steps: int = 3
    status: Literal["planned", "running", "passed", "failed", "blocked", "needs_approval"] = "planned"
    stop_reason: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION
    authoritative: bool = False  # Advisor only, not authoritative

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LoopSession:
    """A remediation loop session."""
    session_id: str
    run_id: str
    plan_id: str
    status: Literal["planned", "running", "passed", "failed", "blocked", "needs_approval", "stopped"]
    current_step: int = 0
    max_steps: int = 3
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    executed_commands: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    stop_reason: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    authoritative: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LoopResult:
    """Complete result of an Anigma remediation loop."""
    schema_version: str
    run_id: str
    created_at: str
    source_sentinel_path: str
    issue_family: str
    issue_count: int
    selected_issue_ids: List[str]
    mode: Literal["plan_only", "dry_run", "sandbox"]
    max_steps: int
    status: Literal["planned", "dry_run", "blocked", "failed", "passed", "needs_approval"]
    planned_actions: List[Dict[str, Any]]
    stop_reason: Optional[str]
    validation_commands: List[List[str]]
    artifacts: List[str]
    warnings: List[str]
    loop_session: Optional[Dict[str, Any]] = None
    remediation_plan: Optional[Dict[str, Any]] = None
    authoritative: bool = False

    @classmethod
    def from_plan_and_session(
        cls,
        plan: RemediationPlan,
        session: Optional[LoopSession] = None,
        loop_module: Optional["AnigmaRemediationLoop"] = None
    ) -> "LoopResult":
        return cls(
            schema_version=SCHEMA_VERSION,
            run_id=plan.run_id,
            created_at=plan.created_at,
            source_sentinel_path=SENTINEL_PATH,
            issue_family=plan.issue_family,
            issue_count=plan.issue_count,
            selected_issue_ids=plan.selected_issue_ids,
            mode=plan.mode,
            max_steps=plan.max_steps,
            status=plan.status,
            stop_reason=plan.stop_reason,
            planned_actions=[a.to_dict() for a in plan.planned_actions],
            validation_commands=plan.validation_commands,
            artifacts=plan.artifacts,
            warnings=plan.warnings,
            loop_session=session.to_dict() if session else None,
            remediation_plan=plan.to_dict(),
            authoritative=False
        )

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Handle Optional fields that may be None
        if result.get("loop_session") is None:
            result["loop_session"] = None
        if result.get("remediation_plan") is None:
            result["remediation_plan"] = None
        return result


class AnigmaRemediationLoop:
    """
    Anigma-specific remediation loop adapter.
    
    This class consumes Anigma Architecture Sentinel output and creates
    bounded remediation plans for issue families.
    """

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or REPO_ROOT
        self.loops_dir = self.repo_root / ".build" / "anigma" / "loops"
        self.sentinel_path = self.repo_root / ".build" / "anigma" / "sentinel" / "latest.json"
        self.events: List[str] = []

    def _emit(self, message: str):
        """Emit an event to the log."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.events.append(f"[{timestamp}] {message}")

    def _load_sentinel_output(self) -> Optional[Dict[str, Any]]:
        """Load the latest Anigma sentinel JSON output."""
        if not self.sentinel_path.exists():
            self._emit(f"Sentinel output not found at {self.sentinel_path}")
            return None

        try:
            content = self.sentinel_path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            self._emit(f"Failed to load sentinel output: {e}")
            return None

    def _get_issue_family(self, issue_code: str) -> Optional[Dict[str, Any]]:
        """Get issue family configuration by code."""
        # Direct match
        if issue_code in ISSUE_CLASSIFIERS:
            return ISSUE_CLASSIFIERS[issue_code]

        # Try matching by surface pattern
        for code, classifier in ISSUE_CLASSIFIERS.items():
            if code in issue_code or issue_code in code:
                return classifier

        return None

    def _group_issues_by_family(self, sentinel_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Group sentinel issues by their family classification."""
        issues = sentinel_data.get("issues", [])
        groups: Dict[str, List[Dict[str, Any]]] = {}

        for issue in issues:
            code = issue.get("code", "")
            family_config = self._get_issue_family(code)

            if family_config is None:
                family = "unknown"
                severity = issue.get("severity", "warning")
                classifier = {
                    "family": family,
                    "severity": severity,
                    "title": f"Unknown Issue: {code}",
                    "summary": f"Issue code '{code}' not recognized by remediation loop.",
                    "root_cause": "Unknown issue type.",
                    "proposed_action": "Investigate and classify this issue.",
                    "dry_run_commands": [],
                    "validators": [],
                    "stop_conditions": ["unknown_issue"],
                    "human_approval_required": True,
                    "sandbox_ready": False,
                }
            else:
                family = family_config["family"]
                classifier = family_config

            if family not in groups:
                groups[family] = []
            
            # Add classifier info to issue for context
            augmented_issue = dict(issue)
            augmented_issue["_family"] = family
            augmented_issue["_classifier"] = classifier
            groups[family].append(augmented_issue)

        return groups

    def status(self) -> Dict[str, Any]:
        """Get current status of Anigma sentinel and loop state."""
        sentinel_data = self._load_sentinel_output()

        if sentinel_data is None:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "no_sentinel_output",
                "sentinel_path": str(self.sentinel_path.relative_to(self.repo_root)),
                "exists": False,
                "loop_artifacts": [],
                "authoritative": False,
            }

        # Check for loop artifacts
        loop_artifacts = []
        if self.loops_dir.exists():
            for artifact_path in self.loops_dir.rglob("*.json"):
                if artifact_path.is_file():
                    loop_artifacts.append(str(artifact_path.relative_to(self.repo_root)))

        # Count issues by surface
        issues_by_surface: Dict[str, Dict[str, int]] = {}
        for issue in sentinel_data.get("issues", []):
            surface = issue.get("surface", "unknown")
            code = issue.get("code", "unknown")
            severity = issue.get("severity", "warning")

            if surface not in issues_by_surface:
                issues_by_surface[surface] = {"total": 0, "by_code": {}, "by_severity": {}}
            
            issues_by_surface[surface]["total"] += 1
            issues_by_surface[surface]["by_code"][code] = issues_by_surface[surface]["by_code"].get(code, 0) + 1
            issues_by_surface[surface]["by_severity"][severity] = issues_by_surface[surface]["by_severity"].get(severity, 0) + 1

        issue_groups = self._group_issues_by_family(sentinel_data)

        return {
            "schema_version": SCHEMA_VERSION,
            "status": sentinel_data.get("status", "unknown"),
            "sentinel_path": str(self.sentinel_path.relative_to(self.repo_root)),
            "sentinel_created_at": sentinel_data.get("created_at"),
            "issue_count": sentinel_data.get("issue_count", 0),
            "exists": True,
            "surfaces": {
                surface: {
                    "status": "scanned",
                    "issues": count_info
                }
                for surface, count_info in issues_by_surface.items()
            },
            "issue_families": {
                family: {
                    "count": len(issues),
                    "codes": list(set(issue.get("code", "unknown") for issue in issues)),
                    "severities": list(set(issue.get("severity", "warning") for issue in issues)),
                }
                for family, issues in issue_groups.items()
            },
            "loop_artifacts": loop_artifacts,
            "authoritative": False,
        }

    def plan(
        self,
        issue_family: Optional[str] = None,
        issue_code: Optional[str] = None,
        max_steps: int = 3
    ) -> RemediationPlan:
        """
        Create a remediation plan for an issue family.
        
        If neither issue_family nor issue_code is specified, uses the first
        family from the sentinel output.
        """
        sentinel_data = self._load_sentinel_output()

        if sentinel_data is None:
            plan = RemediationPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                run_id=f"run-{uuid.uuid4().hex[:8]}",
                issue_family="none",
                issue_code="no_sentinel_output",
                selected_issue_ids=[],
                issue_count=0,
                summary="No sentinel output available",
                likely_root_cause="Sentinel has not been run or output not found.",
                proposed_required_action="Run python Scripts/anigma_architecture_sentinel.py --format json",
                status="blocked",
                stop_reason=StopReason.NO_SENTINEL_OUTPUT.value,
                mode="plan_only",
                max_steps=max_steps,
            )
            self._emit(f"Plan created (blocked): {plan.stop_reason}")
            return plan

        issues = sentinel_data.get("issues", [])

        if not issues:
            plan = RemediationPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                run_id=f"run-{uuid.uuid4().hex[:8]}",
                issue_family="none",
                issue_code="no_issues",
                selected_issue_ids=[],
                issue_count=0,
                summary="No issues found in sentinel output",
                likely_root_cause="All architecture checks passed.",
                proposed_required_action="No action required.",
                status="passed",
                stop_reason=None,
                mode="plan_only",
                max_steps=max_steps,
            )
            self._emit("Plan created: No issues to remediate")
            return plan

        issue_groups = self._group_issues_by_family(sentinel_data)

        # Select the issue family
        if issue_code:
            # Prefer exact code match
            for family, group_issues in issue_groups.items():
                for issue in group_issues:
                    if issue.get("code") == issue_code:
                        selected_family = family
                        selected_code = issue_code
                        selected_issues = [issue]
                        break
                else:
                    continue
                break
            else:
                # Code not found, try as family
                selected_family = issue_code
                selected_code = issue_code
                selected_issues = issue_groups.get(issue_code, [])
        elif issue_family:
            selected_family = issue_family
            # Find the first code in this family
            selected_issues = issue_groups.get(issue_family, [])
            if selected_issues:
                selected_code = selected_issues[0].get("code", issue_family)
            else:
                selected_code = issue_family
        else:
            # Use the first family with issues
            selected_family = list(issue_groups.keys())[0]
            selected_issues = list(issue_groups.values())[0]
            selected_code = selected_issues[0].get("code", selected_family)

        if not selected_issues:
            plan = RemediationPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                run_id=f"run-{uuid.uuid4().hex[:8]}",
                issue_family=selected_family,
                issue_code=selected_code,
                selected_issue_ids=[],
                issue_count=0,
                summary=f"Issue family '{selected_family}' not found",
                likely_root_cause="Unknown issue family.",
                proposed_required_action="Specify a valid issue family.",
                status="blocked",
                stop_reason=StopReason.ISSUE_FAMILY_UNKNOWN.value,
                mode="plan_only",
                max_steps=max_steps,
            )
            self._emit(f"Plan blocked: {plan.stop_reason}")
            return plan

        classifier = self._get_issue_family(selected_code)

        if classifier is None:
            # Create a safe fallback classifier
            classifier = {
                "family": selected_family,
                "severity": selected_issues[0].get("severity", "warning"),
                "title": f"Unknown Issue Family: {selected_family}",
                "summary": f"Issue family '{selected_family}' not recognized.",
                "root_cause": "Unknown issue type.",
                "proposed_action": "Investigate and classify this issue.",
                "dry_run_commands": [],
                "validators": [],
                "stop_conditions": ["unknown_issue"],
                "human_approval_required": True,
                "sandbox_ready": False,
            }

        # Extract issue IDs
        selected_issue_ids = [
            f"{issue.get('surface', 'unknown')}-{issue.get('path', 'unknown')}-{issue.get('line', '0')}"
            for issue in selected_issues
        ]

        # Check for threshold (warn if > 50 issues in family)
        if len(selected_issues) > 50:
            plan = RemediationPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                run_id=f"run-{uuid.uuid4().hex[:8]}",
                issue_family=selected_family,
                issue_code=selected_code,
                selected_issue_ids=[],
                issue_count=len(selected_issues),
                summary=f"Too many issues ({len(selected_issues)}) in family '{selected_family}'",
                likely_root_cause=classifier.get("root_cause", "Issue count exceeds threshold."),
                proposed_required_action=classifier.get("proposed_action", "Narrow the scope."),
                status="blocked",
                stop_reason=StopReason.ISSUE_COUNT_EXCEEDS_THRESHOLD.value,
                mode="plan_only",
                max_steps=max_steps,
                warnings=[
                    f"Issue count ({len(selected_issues)}) exceeds threshold of 50. "
                    f"Consider narrowing by specifying a specific issue code."
                ],
            )
            self._emit(f"Plan blocked: {plan.stop_reason}")
            return plan

        # Build planned actions
        planned_actions = []

        # Always include sentinel re-run
        planned_actions.append(PlannedAction(
            action_id="anigma_sentinel_recheck",
            description="Re-run Anigma Architecture Sentinel to verify current state",
            command=[sys.executable, "Scripts/anigma_architecture_sentinel.py", "--format", "json"],
            expected_outcome="Updated sentinel output with current architecture status",
            safety_level="read_only",
            expected_duration_seconds=30,
            requires_approval=False,
            stop_conditions=[" validator_failed"],
        ))

        # Add classifier-specific commands
        for cmd in classifier.get("dry_run_commands", []):
            planned_actions.append(PlannedAction(
                action_id=f"validator_{cmd[0]}",
                description=f"Run validation: {' '.join(cmd)}",
                command=list(cmd),
                expected_outcome="Validation passes",
                safety_level="read_only",
                expected_duration_seconds=30,
                requires_approval=False,
            ))

        # Build validation commands list (from classifier + standard)
        validation_commands = list(classifier.get("dry_run_commands", []))
        validation_commands.extend([
            cmd for cmd in ALLOWED_VALIDATION_COMMANDS
            if list(cmd) not in [list(c) for c in validation_commands]
        ])

        # Determine mode-based behavior
        mode = "plan_only"
        status = "planned"
        stop_reason = None

        if classifier.get("human_approval_required"):
            status = "needs_approval"
            stop_reason = StopReason.HUMAN_APPROVAL_REQUIRED.value

        if mode == "sandbox" and not classifier.get("sandbox_ready", False):
            mode = "plan_only"
            status = "blocked"
            stop_reason = StopReason.SANDBOX_MODE_UNSUPPORTED.value
            warnings = [
                f"Sandbox mode requested but issue family '{selected_family}' "
                f"is not sandbox-ready. Mode set to plan_only."
            ]
        else:
            warnings = []

        plan = RemediationPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            issue_family=selected_family,
            issue_code=selected_code,
            selected_issue_ids=selected_issue_ids[:max_steps],  # Limit to max_steps
            issue_count=len(selected_issues),
            summary=classifier.get("summary", ""),
            likely_root_cause=classifier.get("root_cause", ""),
            proposed_required_action=classifier.get("proposed_action", ""),
            planned_actions=planned_actions,
            validation_commands=validation_commands,
            stop_conditions=classifier.get("stop_conditions", []),
            mode=mode,
            max_steps=max_steps,
            status=status,
            stop_reason=stop_reason,
            artifacts=[],
            warnings=warnings,
        )

        self._emit(f"Plan created for family '{selected_family}' with {plan.issue_count} issues")
        return plan

    def run(
        self,
        plan: RemediationPlan,
        mode: Optional[Literal["plan_only", "dry_run", "sandbox"]] = None
    ) -> LoopResult:
        """
        Execute a remediation plan in the specified mode.
        
        In plan_only mode: just return the plan (no execution)
        In dry_run mode: run safe validators/status commands, no file edits
        In sandbox mode: deferred/blocked unless sandbox is ready
        """
        if mode:
            plan.mode = mode

        run_id = plan.run_id or f"run-{uuid.uuid4().hex[:8]}"
        plan.run_id = run_id

        self._emit(f"Starting loop run {run_id} in mode '{plan.mode}'")

        # Write plan artifact
        run_dir = self.loops_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        plan_path = run_dir / "plan.json"
        plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

        plan_md = self._generate_plan_markdown(plan)
        plan_md_path = run_dir / "plan.md"
        plan_md_path.write_text(plan_md, encoding="utf-8")

        plan.artifacts.append(str(plan_path.relative_to(self.repo_root)))
        plan.artifacts.append(str(plan_md_path.relative_to(self.repo_root)))

        # Handle plan_only mode
        if plan.mode == "plan_only":
            plan.status = "planned"
            result = LoopResult.from_plan_and_session(plan)
            
            # Also write latest
            self._write_latest(result, run_dir)
            
            self._emit(f"Loop {run_id}: plan_only mode, no execution")
            return result

        # Handle sandbox mode
        if plan.mode == "sandbox":
            classifier = self._get_issue_family(plan.issue_code)
            if not classifier or not classifier.get("sandbox_ready", False):
                plan.status = "blocked"
                plan.stop_reason = StopReason.SANDBOX_MODE_UNSUPPORTED.value
                result = LoopResult.from_plan_and_session(plan)
                self._write_latest(result, run_dir)
                self._emit(f"Loop {run_id}: sandbox mode blocked, not sandbox-ready")
                return result
            else:
                # Sandbox mode would edit files - deferred for future implementation
                plan.status = "blocked"
                plan.stop_reason = "sandbox_mode_deferred"
                result = LoopResult.from_plan_and_session(plan)
                self._write_latest(result, run_dir)
                self._emit(f"Loop {run_id}: sandbox mode deferred to future implementation")
                return result

        # Handle dry_run mode
        if plan.mode == "dry_run":
            session = self._execute_dry_run(plan, run_dir)
            plan.status = session.status
            plan.stop_reason = session.stop_reason
            result = LoopResult.from_plan_and_session(plan, session)
            
            # Write session artifacts
            session_path = run_dir / "loop.json"
            session_path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

            # Write events
            events_path = run_dir / "events.jsonl"
            events_path.write_text("\n".join(self.events), encoding="utf-8")

            # Update latest
            self._write_latest(result, run_dir)

            self._emit(f"Loop {run_id}: dry_run completed with status '{session.status}'")
            return result

        # Should not reach here
        plan.status = "blocked"
        plan.stop_reason = "invalid_mode"
        result = LoopResult.from_plan_and_session(plan)
        self._write_latest(result, run_dir)
        return result

    def _execute_dry_run(self, plan: RemediationPlan, run_dir: Path) -> LoopSession:
        """Execute actions in dry-run mode."""
        session = LoopSession(
            session_id=f"session-{uuid.uuid4().hex[:8]}",
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            status="running",
            current_step=0,
            max_steps=plan.max_steps,
        )

        self._emit(f"Dry-run session started: {session.session_id}")

        # Limit to max_steps actions
        actions_to_execute = plan.planned_actions[:plan.max_steps]
        self._emit(f"Will execute {len(actions_to_execute)} of {len(plan.planned_actions)} planned actions")

        executed = 0
        for action in actions_to_execute:
            session.current_step += 1
            executed += 1

            if executed > plan.max_steps:
                session.status = "stopped"
                session.stop_reason = StopReason.MAX_STEPS_REACHED.value
                break

            # Check if this is an allowed validation command
            command = action.command
            
            # Verify command is in allowed list ( argv lists only )
            is_allowed = any(
                all(c1 == c2 for c1, c2 in zip(cmd, command))
                for cmd in ALLOWED_VALIDATION_COMMANDS
            )

            if not is_allowed:
                # Check if it's a sentinel command
                sentinel_commands = [
                    [sys.executable, "Scripts/anigma_architecture_sentinel.py"],
                    [sys.executable, "scripts/rig.py", "anigma", "sentinel"],
                ]
                is_allowed = any(
                    command[:len(cmd)] == list(cmd)
                    for cmd in sentinel_commands
                )

            if not is_allowed:
                session.status = "blocked"
                session.stop_reason = StopReason.VALIDATOR_UNAVAILABLE.value
                session.warnings.append(f"Command not in allowed list: {' '.join(command)}")
                session.executed_commands.append({
                    "command": list(command),
                    "status": "skipped",
                    "reason": "not_allowed",
                })
                continue

            # Execute the command
            try:
                self._emit(f"Executing (dry-run): {' '.join(command)}")
                proc = subprocess.Popen(
                    command,
                    cwd=self.repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(timeout=action.expected_duration_seconds)

                result_status = "passed" if proc.returncode == 0 else "failed"
                session.executed_commands.append({
                    "command": list(command),
                    "status": result_status,
                    "exit_code": proc.returncode,
                    "stdout": stdout[:500],  # Truncate for logging
                    "stderr": stderr[:200],
                })

                if result_status == "failed":
                    session.status = "blocked"
                    session.stop_reason = StopReason.COMMAND_FAILED.value
                    session.errors.append(f"Command failed: {' '.join(command)} (exit {proc.returncode})")
                    break

                self._emit(f"Command passed: {' '.join(command)}")

            except subprocess.TimeoutExpired:
                proc.kill()
                session.status = "blocked"
                session.stop_reason = "command_timeout"
                session.errors.append(f"Command timed out: {' '.join(command)}")
                break
            except Exception as e:
                session.status = "blocked"
                session.stop_reason = StopReason.COMMAND_UNAVAILABLE.value
                session.errors.append(f"Command error: {' '.join(command)} - {str(e)}")
                break

        # Check if we completed all planned actions
        if session.status == "running":
            if executed >= len(actions_to_execute):
                session.status = "passed"
            else:
                session.status = "stopped"
                session.stop_reason = StopReason.MAX_STEPS_REACHED.value

        session.finished_at = datetime.now(timezone.utc).isoformat()
        
        # Add artifacts
        session.artifacts.append(str(run_dir / "events.jsonl"))
        for cmd_result in session.executed_commands:
            pass  # Individual command outputs are in the session

        return session

    def show(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get loop run details by run ID."""
        run_dir = self.loops_dir / run_id
        if not run_dir.exists():
            self._emit(f"Run directory not found: {run_dir}")
            return None

        # Load all artifacts
        result = {}

        # Loop result
        loop_json = run_dir / "loop.json"
        if loop_json.exists():
            try:
                result["loop"] = json.loads(loop_json.read_text())
            except Exception:
                pass

        # Plan
        plan_json = run_dir / "plan.json"
        if plan_json.exists():
            try:
                result["plan"] = json.loads(plan_json.read_text())
            except Exception:
                pass

        # Plan markdown
        plan_md = run_dir / "plan.md"
        if plan_md.exists():
            try:
                result["plan_md"] = plan_md.read_text()
            except Exception:
                pass

        # Events
        events_jsonl = run_dir / "events.jsonl"
        if events_jsonl.exists():
            try:
                result["events"] = events_jsonl.read_text().splitlines()
            except Exception:
                pass

        # Latest artifacts
        latest_dir = self.loops_dir / "latest.json"
        if latest_dir.exists():
            try:
                result["latest"] = json.loads(latest_dir.read_text())
            except Exception:
                pass

        return result if result else None

    def _generate_plan_markdown(self, plan: RemediationPlan) -> str:
        """Generate Markdown representation of a remediation plan."""
        md = [
            f"# Anigma Remediation Plan",
            "",
            f"- **Plan ID:** `{plan.plan_id}`",
            f"- **Run ID:** `{plan.run_id}`",
            f"- **Created:** {plan.created_at}",
            f"- **Issue Family:** `{plan.issue_family}`",
            f"- **Issue Code:** `{plan.issue_code}`",
            f"- **Issue Count:** {plan.issue_count}",
            f"- **Mode:** `{plan.mode}`",
            f"- **Max Steps:** {plan.max_steps}",
            f"- **Status:** `{plan.status}`",
            "",
            f"## Summary",
            f"{plan.summary}",
            "",
            f"## Likely Root Cause",
            f"{plan.likely_root_cause}",
            "",
            f"## Proposed Required Action",
            f"{plan.proposed_required_action}",
            "",
        ]

        if plan.selected_issue_ids:
            md.append("## Selected Issues")
            for issue_id in plan.selected_issue_ids:
                md.append(f"- {issue_id}")
            md.append("")

        if plan.planned_actions:
            md.append("## Planned Actions")
            for i, action in enumerate(plan.planned_actions, 1):
                md.append(f"{i}. **{action.action_id}** [{action.safety_level}]")
                md.append(f"   - Description: {action.description}")
                md.append(f"   - Command: `{' '.join(action.command)}`")
                md.append(f"   - Expected: {action.expected_outcome}")
                if action.requires_approval:
                    md.append(f"   - **REQUIRES APPROVAL**")
                if action.stop_conditions:
                    md.append(f"   - Stop if: {', '.join(action.stop_conditions)}")
            md.append("")

        if plan.validation_commands:
            md.append("## Validation Commands")
            for cmd in plan.validation_commands:
                md.append(f"- `{' '.join(cmd)}`")
            md.append("")

        if plan.stop_conditions:
            md.append("## Stop Conditions")
            for condition in plan.stop_conditions:
                md.append(f"- {condition}")
            md.append("")

        if plan.warnings:
            md.append("## Warnings")
            for warning in plan.warnings:
                md.append(f"- ⚠️  {warning}")
            md.append("")

        md.append("---")
        md.append("*This is an advisory plan. Human review required before execution.*")

        return "\n".join(md)

    def _write_latest(self, result: LoopResult, run_dir: Path):
        """Write latest artifacts."""
        latest_json = self.loops_dir / "latest.json"
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        latest_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

        # Also write markdown latest
        md_content = self._generate_result_markdown(result)
        latest_md = self.loops_dir / "latest.md"
        latest_md.write_text(md_content, encoding="utf-8")

    def _generate_result_markdown(self, result: LoopResult) -> str:
        """Generate Markdown representation of loop result."""
        md = [
            f"# Anigma Remediation Loop Result",
            "",
            f"- **Schema Version:** `{result.schema_version}`",
            f"- **Run ID:** `{result.run_id}`",
            f"- **Created:** {result.created_at}",
            f"- **Status:** `{result.status}`",
            f"- **Mode:** `{result.mode}`",
            f"- **Max Steps:** {result.max_steps}",
            "",
            f"## Source",
            f"- Sentinel: `{result.source_sentinel_path}`",
            f"- Issue Family: `{result.issue_family}`",
            f"- Issue Count: {result.issue_count}",
            "",
        ]

        if result.stop_reason:
            md.append(f"## Stop Reason")
            md.append(f"{result.stop_reason}")
            md.append("")

        if result.selected_issue_ids:
            md.append("## Selected Issues")
            for issue_id in result.selected_issue_ids:
                md.append(f"- {issue_id}")
            md.append("")

        if result.planned_actions:
            md.append("## Planned Actions")
            for i, action in enumerate(result.planned_actions, 1):
                md.append(f"{i}. **{action.get('action_id', 'unknown')}** [{action.get('safety_level', 'unknown')}]")
                md.append(f"   - {action.get('description', 'No description')}")
                md.append(f"   - `{' '.join(action.get('command', []))}`")
            md.append("")

        if result.validation_commands:
            md.append("## Validation Commands")
            for cmd in result.validation_commands:
                md.append(f"- `{' '.join(cmd)}`")
            md.append("")

        if result.warnings:
            md.append("## Warnings")
            for warning in result.warnings:
                md.append(f"- ⚠️  {warning}")
            md.append("")

        if result.artifacts:
            md.append("## Artifacts")
            for artifact in result.artifacts:
                md.append(f"- `{artifact}`")
            md.append("")

        md.append("---")
        md.append(
            f"*Authoritative: {result.authoritative} | "
            f"Loop artifacts: {self.loops_dir.relative_to(self.repo_root)}*"
        )

        return "\n".join(md)

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all loop runs."""
        runs = []
        if not self.loops_dir.exists():
            return runs

        for run_dir in self.loops_dir.iterdir():
            if run_dir.is_dir():
                loop_json = run_dir / "loop.json"
                plan_json = run_dir / "plan.json"

                info: Dict[str, Any] = {
                    "run_id": run_dir.name,
                    "has_loop": loop_json.exists(),
                    "has_plan": plan_json.exists(),
                    "has_events": (run_dir / "events.jsonl").exists(),
                    "path": str(run_dir.relative_to(self.repo_root)),
                }

                # Try to get status from artifacts
                if loop_json.exists():
                    try:
                        data = json.loads(loop_json.read_text())
                        info["status"] = data.get("status")
                        info["mode"] = data.get("mode")
                        info["issue_family"] = data.get("issue_family")
                    except Exception:
                        pass
                elif plan_json.exists():
                    try:
                        data = json.loads(plan_json.read_text())
                        info["status"] = data.get("status")
                        info["mode"] = data.get("mode")
                        info["issue_family"] = data.get("issue_family")
                    except Exception:
                        pass

                runs.append(info)

        # Sort by directory mtime (newest first)
        runs.sort(key=lambda x: (self.loops_dir / x["run_id"]).stat().st_mtime, reverse=True)
        return runs


# Convenience functions
def get_loop(repo_root: Optional[Path] = None) -> AnigmaRemediationLoop:
    """Get an AnigmaRemediationLoop instance for the repository."""
    return AnigmaRemediationLoop(repo_root)


def run_status() -> Dict[str, Any]:
    """Get current Anigma sentinel and loop status."""
    loop = get_loop()
    return loop.status()


def run_plan(
    issue_family: Optional[str] = None,
    issue_code: Optional[str] = None,
    max_steps: int = 3
) -> RemediationPlan:
    """Create a remediation plan."""
    loop = get_loop()
    return loop.plan(issue_family=issue_family, issue_code=issue_code, max_steps=max_steps)


def run_loop(
    plan: RemediationPlan,
    mode: Literal["plan_only", "dry_run", "sandbox"] = "plan_only",
) -> LoopResult:
    """Execute a remediation loop."""
    loop = get_loop()
    plan.mode = mode
    return loop.run(plan, mode=mode)


def run_show(run_id: str) -> Optional[Dict[str, Any]]:
    """Show loop run details."""
    loop = get_loop()
    return loop.show(run_id)


def run_list() -> List[Dict[str, Any]]:
    """List all loop runs."""
    loop = get_loop()
    return loop.list_runs()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Anigma Remediation Loop MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current sentinel and loop status")
    status_parser.set_defaults(func=lambda args: print(json.dumps(run_status(), indent=2)))

    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Create remediation plan")
    plan_parser.add_argument("--from-sentinel", action="store_true", help="Auto-select from sentinel")
    plan_parser.add_argument("--issue-family", default=None, help="Specific issue family to plan for")
    plan_parser.add_argument("--issue-code", default=None, help="Specific issue code to plan for")
    plan_parser.add_argument("--max-steps", type=int, default=3, help="Max steps in plan")
    plan_parser.add_argument("--format", choices=["json", "md"], default="json", help="Output format")
    plan_parser.set_defaults(func=lambda args: print_plan(args))

    # Run command
    run_parser = subparsers.add_parser("run", help="Execute remediation loop")
    run_parser.add_argument("--issue-family", default=None, help="Issue family")
    run_parser.add_argument("--issue-code", default=None, help="Issue code")
    run_parser.add_argument("--max-steps", type=int, default=3, help="Max steps")
    run_parser.add_argument("--mode", choices=["plan_only", "dry_run", "sandbox"], default="plan_only")
    run_parser.add_argument("--format", choices=["json", "md"], default="json")
    run_parser.set_defaults(func=lambda args: print_run(args))

    # Show command
    show_parser = subparsers.add_parser("show", help="Show loop run details")
    show_parser.add_argument("--run-id", required=True, help="Run ID to show")
    show_parser.add_argument("--format", choices=["json", "md"], default="json")
    show_parser.set_defaults(func=lambda args: print_show(args))

    # List command
    list_parser = subparsers.add_parser("list", help="List all loop runs")
    list_parser.add_argument("--format", choices=["json", "md"], default="json")
    list_parser.set_defaults(func=lambda args: print_list(args))

    args = parser.parse_args()
    args.func(args)


def print_plan(args):
    plan = run_plan(
        issue_family=args.issue_family,
        issue_code=args.issue_code,
        max_steps=args.max_steps
    )

    if args.format == "md":
        loop = get_loop()
        print(loop._generate_plan_markdown(plan))
    else:
        print(json.dumps(plan.to_dict(), indent=2))


def print_run(args):
    plan = run_plan(
        issue_family=args.issue_family,
        issue_code=args.issue_code,
        max_steps=args.max_steps
    )
    result = run_loop(plan, mode=args.mode)

    if args.format == "md":
        loop = get_loop()
        print(loop._generate_result_markdown(result))
    else:
        print(json.dumps(result.to_dict(), indent=2))


def print_show(args):
    data = run_show(args.run_id)
    if data is None:
        print(f"Run {args.run_id} not found", file=sys.stderr)
        sys.exit(1)

    if args.format == "md":
        # Generate markdown from the data
        md = [f"# Loop Run: {args.run_id}", ""]
        if "loop" in data:
            loop_data = data["loop"]
            md.append(f"- Status: {loop_data.get('status', 'unknown')}")
            md.append(f"- Run ID: {loop_data.get('run_id', 'unknown')}")
        if "plan" in data:
            plan_data = data["plan"]
            md.append(f"- Issue Family: {plan_data.get('issue_family', 'unknown')}")
            md.append(f"- Issue Count: {plan_data.get('issue_count', 0)}")
        if "events" in data:
            md.append("")
            md.append("## Events")
            for event in data["events"]:
                md.append(f"- {event}")
        print("\n".join(md))
    else:
        print(json.dumps(data, indent=2))


def print_list(args):
    runs = run_list()
    if args.format == "md":
        md = ["# Anigma Loop Runs", ""]
        for run in runs:
            md.append(f"- **{run['run_id']}**: {run.get('status', 'unknown')} | Family: {run.get('issue_family', 'unknown')}")
        print("\n".join(md))
    else:
        print(json.dumps(runs, indent=2))
