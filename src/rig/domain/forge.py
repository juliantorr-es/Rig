"""Forge adapter domain types and pure functions.

This module provides the forge-neutral abstraction for repository bootstrap
and promotion as defined in ADR 0010. Git is the canonical substrate.
Remote forges (GitHub, GitLab, Gitea) are adapters.

Core principles:
- Git is the substrate: all operations use local git commands
- No remote API calls in this module (pure domain contract)
- No mutation: all functions are read-only
- Local-only mode is first-class and valid
- Graceful degradation: return None/Unknown on failure, not crash
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ForgeMode(Enum):
    """Supported forge modes.
    
    Git is the canonical substrate. These modes represent how Rig
    interacts with remote forges (or doesn't, for LOCAL_ONLY).
    """
    LOCAL_ONLY = auto()
    GITHUB = auto()
    GITLAB = auto()
    GITEA = auto()
    UNKNOWN = auto()


class PromotionMode(Enum):
    """Supported promotion modes.
    
    Maps forge modes to their respective promotion mechanisms.
    LOCAL_BRANCH: Local git merge only (no remote)
    PULL_REQUEST: GitHub/Gitea style PR flow
    MERGE_REQUEST: GitLab style MR flow
    MANUAL: Human intervention required (unknown forge)
    """
    LOCAL_BRANCH = auto()
    PULL_REQUEST = auto()
    MERGE_REQUEST = auto()
    MANUAL = auto()


class ForgeDoctorSeverity(Enum):
    """Severity levels for forge doctor findings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ForgeCapabilities:
    """Capabilities of a forge adapter.
    
    Describes what operations a forge mode supports.
    All fields default to False (no capability).
    """
    supports_remote: bool = False
    supports_pull_request: bool = False
    supports_merge_request: bool = False
    supports_required_checks: bool = False
    supports_protected_branches: bool = False
    supports_linear_history: bool = False
    supports_review_approvals: bool = False
    supports_conversation_resolution: bool = False


@dataclass(frozen=True, slots=True)
class ForgeIdentity:
    """Identity information for the repository's forge.
    
    Represents the detected forge configuration from git inspection.
    """
    mode: ForgeMode
    remote_url: str | None = None
    host: str | None = None
    owner: str | None = None
    repository: str | None = None
    default_branch: str = "main"
    preproduction_branch: str = "preproduction"


@dataclass(frozen=True, slots=True)
class ForgeDoctorFinding:
    """A single finding from forge doctor.
    
    Represents an issue, warning, or informational item found during
    forge configuration inspection.
    """
    code: str
    severity: ForgeDoctorSeverity
    message: str
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class ForgeDoctorReport:
    """Complete report from forge doctor.
    
    The result of inspecting forge configuration for a repository.
    """
    identity: ForgeIdentity
    capabilities: ForgeCapabilities
    promotion_mode: PromotionMode
    findings: tuple[ForgeDoctorFinding, ...] = ()
    overall_status: str = "clean"


@dataclass(frozen=True, slots=True)
class ReviewabilityBudget:
    """Reviewability budget configuration for promotion gating.
    
    Defines the maximum number of changed files allowed for promotion.
    Based on ADR 0010 reviewability budget specification.
    """
    max_changed_files: int = 300
    max_listed_files: int = 300
    default_action: str = "block_promotion"
    override_allowed: bool = True
    override_requires_reason: bool = True


@dataclass(frozen=True, slots=True)
class ReviewabilityReport:
    """Report on repository reviewability against budget constraints.
    
    Result of analyzing changed files between two git references
    to determine if the change falls within reviewability budget.
    """
    target_ref: str
    head_ref: str
    merge_base: str | None
    changed_file_count: int
    max_changed_files: int
    over_budget: bool
    default_action: str
    override_required: bool
    changed_files: tuple[str, ...]
    truncated: bool
    findings: tuple[ForgeDoctorFinding, ...]


# ---------------------------------------------------------------------------
# Pure Classification Functions
# ---------------------------------------------------------------------------

def classify_remote_url(url: str | None) -> ForgeMode:
    """Classify a remote URL to determine forge mode.
    
    Args:
        url: The Git remote URL (e.g., from `git remote get-url origin`)
        
    Returns:
        ForgeMode: The classified forge mode. LOCAL_ONLY if url is None.
        
    Note:
        This is a simple string-based classification. Full URL parsing
        (extracting owner/repo) is deferred to future missions.
    """
    if url is None:
        return ForgeMode.LOCAL_ONLY
    
    url_lower = url.lower()
    
    # Check for GitHub
    if "github.com" in url_lower:
        return ForgeMode.GITHUB
    
    # Check for GitLab
    if "gitlab.com" in url_lower:
        return ForgeMode.GITLAB
    
    # Check for Gitea (self-hosted or gitea.com)
    if "gitea" in url_lower or "gitea.com" in url_lower:
        return ForgeMode.GITEA
    
    return ForgeMode.UNKNOWN


def derive_promotion_mode(mode: ForgeMode) -> PromotionMode:
    """Derive promotion mode from forge mode.
    
    Args:
        mode: The forge mode
        
    Returns:
        PromotionMode: The corresponding promotion mode.
    """
    match mode:
        case ForgeMode.LOCAL_ONLY:
            return PromotionMode.LOCAL_BRANCH
        case ForgeMode.GITHUB:
            return PromotionMode.PULL_REQUEST
        case ForgeMode.GITLAB:
            return PromotionMode.MERGE_REQUEST
        case ForgeMode.GITEA:
            # Gitea uses Pull Request terminology
            return PromotionMode.PULL_REQUEST
        case ForgeMode.UNKNOWN:
            return PromotionMode.MANUAL


def capabilities_for_mode(mode: ForgeMode) -> ForgeCapabilities:
    """Get capabilities for a forge mode.
    
    Args:
        mode: The forge mode
        
    Returns:
        ForgeCapabilities: The capabilities supported by this mode.
    """
    match mode:
        case ForgeMode.LOCAL_ONLY:
            return ForgeCapabilities(
                supports_remote=False,
                supports_pull_request=False,
                supports_merge_request=False,
                supports_required_checks=False,
                supports_protected_branches=False,
                supports_linear_history=True,
                supports_review_approvals=False,
                supports_conversation_resolution=False,
            )
        case ForgeMode.GITHUB:
            return ForgeCapabilities(
                supports_remote=True,
                supports_pull_request=True,
                supports_merge_request=False,
                supports_required_checks=True,
                supports_protected_branches=True,
                supports_linear_history=True,
                supports_review_approvals=True,
                supports_conversation_resolution=True,
            )
        case ForgeMode.GITLAB:
            return ForgeCapabilities(
                supports_remote=True,
                supports_pull_request=False,
                supports_merge_request=True,
                supports_required_checks=True,
                supports_protected_branches=True,
                supports_linear_history=True,
                supports_review_approvals=True,
                supports_conversation_resolution=True,
            )
        case ForgeMode.GITEA:
            return ForgeCapabilities(
                supports_remote=True,
                supports_pull_request=True,
                supports_merge_request=False,
                supports_required_checks=True,
                supports_protected_branches=True,
                supports_linear_history=True,
                supports_review_approvals=True,
                supports_conversation_resolution=False,
            )
        case ForgeMode.UNKNOWN:
            return ForgeCapabilities()


# ---------------------------------------------------------------------------
# Local Git Inspection Helpers
# ---------------------------------------------------------------------------

def _git_run(repo_root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the CompletedProcess.
    
    Internal helper for git subcommands.
    
    Args:
        repo_root: Path to the git repository (or worktree)
        *args: Git subcommand arguments
        check: Whether to raise on non-zero exit
        
    Returns:
        CompletedProcess with captured stdout/stderr
    """
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def git_remote_url(repo_root: Path, remote: str = "origin") -> str | None:
    """Get the remote URL for a given remote.
    
    Args:
        repo_root: Path to the git repository
        remote: The remote name to query (default: "origin")
        
    Returns:
        The remote URL as a string, or None if not found/on error.
    """
    proc = _git_run(repo_root, "remote", "get-url", remote)
    if proc.returncode != 0:
        return None
    result = proc.stdout.strip()
    return result if result else None


def git_current_branch(repo_root: Path) -> str | None:
    """Get the current branch name.
    
    Args:
        repo_root: Path to the git repository
        
    Returns:
        The current branch name as a string, or None if detached HEAD/on error.
    """
    proc = _git_run(repo_root, "branch", "--show-current")
    if proc.returncode != 0:
        return None
    result = proc.stdout.strip()
    return result if result else None


def git_rev_parse(repo_root: Path, rev: str = "HEAD") -> str | None:
    """Get the short hash for a revision.
    
    Args:
        repo_root: Path to the git repository
        rev: The revision to parse (default: "HEAD")
        
    Returns:
        The short commit hash as a string, or None on error.
    """
    proc = _git_run(repo_root, "rev-parse", "--short", rev)
    if proc.returncode != 0:
        return None
    result = proc.stdout.strip()
    return result if result else None


def git_branch_exists(repo_root: Path, branch: str) -> bool:
    """Check if a branch exists locally.
    
    Args:
        repo_root: Path to the git repository
        branch: The branch name to check
        
    Returns:
        True if the branch exists locally, False otherwise.
    """
    proc = _git_run(repo_root, "branch", "--list", branch)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def git_inside_repo(repo_root: Path) -> bool:
    """Check if a path is inside a git repository.
    
    Args:
        repo_root: Path to check
        
    Returns:
        True if inside a git repo, False otherwise.
    """
    proc = _git_run(repo_root, "rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and proc.stdout.strip() == "true"


# ---------------------------------------------------------------------------
# Identity Building
# ---------------------------------------------------------------------------

def build_forge_identity(repo_root: Path, remote: str = "origin") -> ForgeIdentity:
    """Build forge identity from git inspection.
    
    Inspects the git repository to determine its forge configuration.
    
    Args:
        repo_root: Path to the git repository
        remote: The remote name to query (default: "origin")
        
    Returns:
        ForgeIdentity with detected configuration.
        
    Note:
        Owner and repository fields are currently None. Full URL parsing
        is deferred to a future mission. Only the mode, remote_url, and host
        are populated based on simple string classification.
    """
    remote_url = git_remote_url(repo_root, remote)
    mode = classify_remote_url(remote_url)
    
    # Parse remote URL for host (simple string matching)
    host = None
    if remote_url:
        url_lower = remote_url.lower()
        if "github.com" in url_lower:
            host = "github.com"
        elif "gitlab.com" in url_lower:
            host = "gitlab.com"
        elif "gitea" in url_lower:
            host = "gitea"
    
    return ForgeIdentity(
        mode=mode,
        remote_url=remote_url,
        host=host,
        owner=None,  # Deferred to future mission
        repository=None,  # Deferred to future mission
    )


# ---------------------------------------------------------------------------
# Doctor Report Building
# ---------------------------------------------------------------------------

def build_doctor_findings(repo_root: Path, identity: ForgeIdentity) -> list[ForgeDoctorFinding]:
    """Build findings for forge doctor report.
    
    Inspects the repository and identities to generate diagnostic findings.
    
    Args:
        repo_root: Path to the git repository
        identity: The forge identity
        
    Returns:
        List of ForgeDoctorFinding objects.
    """
    findings = []
    
    # Check if we're inside a git repo
    if not git_inside_repo(repo_root):
        findings.append(ForgeDoctorFinding(
            code="FORGE-001",
            severity=ForgeDoctorSeverity.ERROR,
            message="Not inside a Git repository",
            remediation="Initialize a git repository with 'git init' or navigate to a git repo",
        ))
        return findings
    
    # Check for remote
    if identity.remote_url is None:
        findings.append(ForgeDoctorFinding(
            code="FORGE-002",
            severity=ForgeDoctorSeverity.INFO,
            message="No remote configured",
            remediation="Configure a remote with 'git remote add origin <url>' for forge features",
        ))
    
    # Check for preproduction branch
    if not git_branch_exists(repo_root, "preproduction"):
        findings.append(ForgeDoctorFinding(
            code="FORGE-003",
            severity=ForgeDoctorSeverity.WARNING,
            message="preproduction branch does not exist locally",
            remediation="Create preproduction branch: git branch preproduction origin/main",
        ))
    
    # Check current branch
    current_branch = git_current_branch(repo_root)
    if current_branch is None:
        findings.append(ForgeDoctorFinding(
            code="FORGE-004",
            severity=ForgeDoctorSeverity.WARNING,
            message="Could not determine current branch",
            remediation="Ensure HEAD is not detached",
        ))
    
    return findings


def build_doctor_report(repo_root: Path) -> ForgeDoctorReport:
    """Build a complete forge doctor report for a repository.
    
    Args:
        repo_root: Path to the git repository
        
    Returns:
        ForgeDoctorReport with full forge configuration analysis.
    """
    identity = build_forge_identity(repo_root)
    capabilities = capabilities_for_mode(identity.mode)
    promotion_mode = derive_promotion_mode(identity.mode)
    findings = build_doctor_findings(repo_root, identity)
    
    # Determine overall status
    severities = [f.severity for f in findings]
    if any(s == ForgeDoctorSeverity.CRITICAL for s in severities):
        overall_status = "critical"
    elif any(s == ForgeDoctorSeverity.ERROR for s in severities):
        overall_status = "error"
    elif any(s == ForgeDoctorSeverity.WARNING for s in severities):
        overall_status = "warning"
    else:
        overall_status = "clean"
    
    return ForgeDoctorReport(
        identity=identity,
        capabilities=capabilities,
        promotion_mode=promotion_mode,
        findings=tuple(findings),
        overall_status=overall_status,
    )


# ---------------------------------------------------------------------------
# Reviewability Budget Git Helpers
# ---------------------------------------------------------------------------

def git_merge_base(repo_root: Path, target_ref: str, head_ref: str = "HEAD") -> str | None:
    """Get the merge base commit between two git references.
    
    Args:
        repo_root: Path to the git repository
        target_ref: Target reference (branch, tag, or commit)
        head_ref: Head reference (default: "HEAD")
        
    Returns:
        The merge base commit hash as a string, or None on error.
    """
    proc = _git_run(repo_root, "merge-base", target_ref, head_ref)
    if proc.returncode != 0:
        return None
    result = proc.stdout.strip()
    return result if result else None


def git_changed_files(
    repo_root: Path,
    base_ref: str,
    head_ref: str = "HEAD",
) -> tuple[str, ...]:
    """Get list of changed files between two git references.
    
    Args:
        repo_root: Path to the git repository
        base_ref: Base reference (branch, tag, or commit)
        head_ref: Head reference (default: "HEAD")
        
    Returns:
        Tuple of changed file paths (relative to repo root), empty tuple on error.
    """
    proc = _git_run(repo_root, "diff", "--name-only", base_ref, head_ref)
    if proc.returncode != 0:
        return ()
    
    raw_files = proc.stdout.strip()
    if not raw_files:
        return ()
    
    # Split by newlines, strip whitespace, filter empty
    files = [f.strip() for f in raw_files.split("\n") if f.strip()]
    return tuple(files)


# ---------------------------------------------------------------------------
# Reviewability Report Building
# ---------------------------------------------------------------------------

def build_reviewability_report(
    repo_root: Path,
    budget: ReviewabilityBudget | None = None,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
) -> ReviewabilityReport:
    """Build a reviewability report for promotion gating.
    
    Analyzes the changed files between target_ref and head_ref to determine
    if the promotion is within the reviewability budget.
    
    Args:
        repo_root: Path to the git repository
        budget: Reviewability budget configuration (uses defaults if None)
        target_ref: Target reference for promotion (default: "preproduction")
        head_ref: Head reference to compare against (default: "HEAD")
        
    Returns:
        ReviewabilityReport with analysis results and findings.
    """
    if budget is None:
        budget = ReviewabilityBudget()
    
    findings: list[ForgeDoctorFinding] = []
    
    # Find merge base
    merge_base = git_merge_base(repo_root, target_ref, head_ref)
    
    if merge_base is None:
        findings.append(ForgeDoctorFinding(
            code="REVIEW-001",
            severity=ForgeDoctorSeverity.WARNING,
            message=f"Could not find merge base between {target_ref} and {head_ref}",
            remediation=f"Ensure {target_ref} exists and is reachable from {head_ref}",
        ))
        # Return a graceful report with no changed files
        return ReviewabilityReport(
            target_ref=target_ref,
            head_ref=head_ref,
            merge_base=None,
            changed_file_count=0,
            max_changed_files=budget.max_changed_files,
            over_budget=False,
            default_action=budget.default_action,
            override_required=False,
            changed_files=(),
            truncated=False,
            findings=tuple(findings),
        )
    
    # Check if target_ref exists as a branch
    if not git_branch_exists(repo_root, target_ref):
        findings.append(ForgeDoctorFinding(
            code="REVIEW-002",
            severity=ForgeDoctorSeverity.WARNING,
            message=f"Target reference {target_ref} does not exist as a local branch",
            remediation=f"Fetch the branch with 'git fetch origin {target_ref}:{target_ref}'",
        ))
    
    # Get changed files
    changed_files = git_changed_files(repo_root, merge_base, head_ref)
    changed_file_count = len(changed_files)
    
    # Determine over_budget status
    over_budget = changed_file_count > budget.max_changed_files
    
    # Truncate changed files list if needed
    truncated = False
    if len(changed_files) > budget.max_listed_files:
        changed_files = changed_files[:budget.max_listed_files]
        truncated = True
    
    # Determine if override is required
    override_required = over_budget and budget.override_requires_reason
    
    # Add finding if over budget
    if over_budget:
        findings.append(ForgeDoctorFinding(
            code="REVIEW-003",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Changed file count ({changed_file_count}) exceeds budget ({budget.max_changed_files})",
            remediation=f"Reduce changes to {budget.max_changed_files} files or request override with reason",
        ))
    
    return ReviewabilityReport(
        target_ref=target_ref,
        head_ref=head_ref,
        merge_base=merge_base,
        changed_file_count=changed_file_count,
        max_changed_files=budget.max_changed_files,
        over_budget=over_budget,
        default_action=budget.default_action,
        override_required=override_required,
        changed_files=changed_files,
        truncated=truncated,
        findings=tuple(findings),
    )
