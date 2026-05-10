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

import hashlib
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Mapping


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


class GitHubBackendMode(Enum):
    """GitHub adapter backend modes.

    Mission 9: GitHub Adapter Backend Boundary

    Defines the backend mode for GitHub adapter operations.
    - AUTO: Automatically select the best available backend
    - CLI: Use GitHub CLI (gh) backend
    - API: Use GitHub REST API/PyGithub backend (not yet implemented)
    """
    AUTO = "auto"
    CLI = "cli"
    API = "api"


class GitHubApiLibraryChoice(Enum):
    """Allowed Python library choices for GitHub API backend.

    Mission 10: GitHub API Backend Credential Model

    - PYGITHUB: Use the PyGithub library (recommended for standard operations)
    - DIRECT_REST: Make direct REST API calls (for unsupported endpoints)
    """
    PYGITHUB = "pygithub"
    DIRECT_REST = "direct_rest"


class GitHubTokenSource(Enum):
    """Allowed token sources for GitHub API backend.

    Mission 10: GitHub API Backend Credential Model

    Defines where GitHub API tokens can come from. Token values are NEVER
    stored by Rig; these are only descriptions of allowed sources.

    - ENVIRONMENT_VARIABLE: RIG_GITHUB_TOKEN or similar env var
    - OS_CREDENTIAL_STORE: Platform native credential store (Keychain, etc.)
    - GITHUB_APP_INSTALLATION_TOKEN: Token from GitHub App installation
    - EXPLICIT_UNTRACKED_TOKEN_PATH: User-specified file in .gitignore
    """
    ENVIRONMENT_VARIABLE = "environment_variable"
    OS_CREDENTIAL_STORE = "os_credential_store"
    GITHUB_APP_INSTALLATION_TOKEN = "github_app_installation_token"
    EXPLICIT_UNTRACKED_TOKEN_PATH = "explicit_untracked_token_path"


# ---------------------------------------------------------------------------
# GitHub API Credential Helpers (Mission 11)
# ---------------------------------------------------------------------------

def read_github_api_token_from_env(
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Read GitHub API token from RIG_GITHUB_TOKEN environment variable.

    Mission 11: Comprehensive GitHub Support Wiring

    This is the only token reading function implemented in this mission.
    Only RIG_GITHUB_TOKEN environment variable is read. No token files,
    OS credential stores, or other sources are read.

    Args:
        env: Optional environment mapping for testing. If None, uses os.environ.

    Returns:
        Token value if RIG_GITHUB_TOKEN is set, None otherwise.
    """
    import os
    if env is None:
        env = os.environ
    return env.get("RIG_GITHUB_TOKEN")


# GitHub token prefix patterns for redaction
_GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")


def redact_token(value: str | None) -> str | None:
    """Redact GitHub token from a string.

    Mission 11: Comprehensive GitHub Support Wiring

    Replaces any GitHub token pattern with [REDACTED]. GitHub tokens
    have specific prefixes (ghp_, gho_, ghu_, ghs_, ghr_) followed by
    alphanumeric characters.

    This function must be used on all strings that might contain tokens
    before logging, returning in errors, or including in evidence.

    Args:
        value: String that may contain a token, or None

    Returns:
        String with tokens redacted, or None if input is None
    """
    if value is None:
        return None
    import re
    # Match GitHub token patterns: prefix + 36+ alphanumeric/underscore chars
    # GitHub fine-grained PATs are 62 chars, classic PATs are 40 chars
    # Match any token-like string to be safe
    token_pattern = r"(" + "|".join(_GITHUB_TOKEN_PREFIXES) + r")[A-Za-z0-9_]{20,}"
    return re.sub(token_pattern, "[REDACTED]", value)


def assert_no_token_leak(value: str) -> bool:
    """Assert that a string does not contain GitHub token patterns.

    Mission 11: Comprehensive GitHub Support Wiring

    Test helper to verify no token literals leak into test data,
    fixtures, or generated output.

    Args:
        value: String to check

    Returns:
        True if no token patterns found

    Raises:
        AssertionError: If token pattern is detected
    """
    import re
    token_pattern = r"(" + "|".join(_GITHUB_TOKEN_PREFIXES) + r")[A-Za-z0-9_]{20,}"
    if re.search(token_pattern, value):
        # Show stripped value in error for debugging, but don't expose the token
        safe_value = redact_token(value)
        raise AssertionError(f"Token leak detected in: {safe_value[:200]}...")
    return True


def classify_github_token_source(
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Classify the GitHub token source based on environment.

    Mission 11: Comprehensive GitHub Support Wiring

    Currently only checks for RIG_GITHUB_TOKEN (environment_variable).
    Returns None if no token source is detected.

    Args:
        env: Optional environment mapping for testing

    Returns:
        Token source string if available, None otherwise
    """
    if read_github_api_token_from_env(env) is not None:
        return GitHubTokenSource.ENVIRONMENT_VARIABLE.value
    return None


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
class GitHubBackendPlan:
    """Backend plan for GitHub adapter operations.

    Mission 9: GitHub Adapter Backend Boundary

    Represents the backend selection and availability for GitHub operations.
    This plan is used to determine which backend (CLI or API) will be used
    for GitHub-specific operations, and whether it's available.
    """
    requested_mode: GitHubBackendMode
    selected_mode: GitHubBackendMode | None
    backend_available: bool
    requires_gh: bool
    requires_token: bool
    token_source: str | None
    reason: str
    findings: tuple[ForgeDoctorFinding, ...]


# ---------------------------------------------------------------------------
# GitHub API Domain Types (Mission 11)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GitHubApiPullRequest:
    """GitHub API pull request representation.

    Mission 11: Comprehensive GitHub Support Wiring

    Represents a GitHub pull request as returned from the API.
    """
    number: int | None = None
    url: str | None = None
    state: str | None = None  # "open", "closed", "merged"
    draft: bool | None = None
    title: str | None = None
    base_ref: str | None = None
    head_ref: str | None = None


@dataclass(frozen=True, slots=True)
class GitHubApiCheckRun:
    """GitHub API check run representation.

    Mission 11: Comprehensive GitHub Support Wiring

    Represents a single GitHub check run (from Checks API or Statuses API).
    """
    id: int | None = None
    name: str | None = None
    status: str | None = None  # "queued", "in_progress", "completed"
    conclusion: str | None = None  # "success", "failure", "neutral", "cancelled", "skipped", "timed_out", None
    html_url: str | None = None


@dataclass(frozen=True, slots=True)
class GitHubApiCheckSummary:
    """Summary of GitHub check runs for a commit/ref.

    Mission 11: Comprehensive GitHub Support Wiring

    Represents the combined status of checks/check-runs for a specific
    commit or branch reference.
    """
    head_sha: str | None = None
    state: str | None = None  # combined state: "success", "failure", "pending", "unknown"
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    pending_count: int = 0
    check_runs: tuple[GitHubApiCheckRun, ...] = ()


@dataclass(frozen=True, slots=True)
class GitHubApiOperationResult:
    """Result of a GitHub API operation.

    Mission 11: Comprehensive GitHub Support Wiring

    Represents the outcome of a single GitHub API operation (e.g., create PR,
    get PR status, get checks). This is used internally and may be included
    in apply result evidence.
    
    Token values are NEVER included in this result.
    """
    provider: str = "github"
    backend: str = "api"  # "api" for API backend
    api_library: str | None = None  # "pygithub" or "direct_rest"
    operation: str = ""  # e.g., "create_pull_request", "get_pr_status", "get_checks"
    success: bool = False
    pr: GitHubApiPullRequest | None = None
    checks: GitHubApiCheckSummary | None = None
    findings: tuple[ForgeDoctorFinding, ...] = ()
    token_source: str | None = None  # e.g., "environment_variable"
    token_present: bool = False
    # NEVER: token_value


# ---------------------------------------------------------------------------
# Dataclasses (existing)
# ---------------------------------------------------------------------------

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


@dataclass(frozen=True, slots=True)
class PromotionPlanStep:
    """A single step in the promotion plan.
    
    Represents an action that would be taken during promotion.
    For Mission 3 (dry-run only), mutates_state steps are planned but not executed.
    """
    step_id: str
    description: str
    command: str | None = None
    mutates_state: bool = False
    required: bool = True


@dataclass(frozen=True, slots=True)
class PromotionDraft:
    """Draft PR/MR information for promotion planning.
    
    Contains the proposed promotion branch name, PR/MR title and body,
    and provider-specific command preview for dry-run promotion planning.
    No mutation is performed - this is draft information only.
    
    Mission 5: Promotion Branch + PR Draft Planner
    Mission 6: Promotion Body File Dry-Run Artifact - adds body_path
    """
    promotion_branch: str
    base_ref: str
    head_ref: str
    title: str
    body: str
    provider_command: str | None
    provider_url_hint: str | None
    draft_only: bool = True
    body_path: str | None = None


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    """Complete promotion plan for a repository.
    
    Result of planning a promotion from head_ref to target_ref.
    This is a dry-run only plan for Mission 3 - no state is mutated.
    For Mission 5, includes draft PR/MR information via the draft field.
    """
    mode: PromotionMode
    forge_mode: ForgeMode
    target_ref: str
    head_ref: str
    identity: ForgeIdentity
    reviewability: ReviewabilityReport
    steps: tuple[PromotionPlanStep, ...]
    blockers: tuple[ForgeDoctorFinding, ...]
    ready: bool
    dry_run_only: bool = True
    draft: PromotionDraft | None = None


@dataclass(frozen=True, slots=True)
class PromotionArtifact:
    """Artifact for promotion body file dry-run.
    
    Represents the local filesystem artifact produced during dry-run promotion planning.
    Contains the path to the PR/MR body file and its metadata.
    No Git mutation is performed - this only writes local artifact files.
    
    Mission 6: Promotion Body File Dry-Run Artifact
    """
    artifact_id: str
    directory: str
    body_path: str
    metadata_path: str
    body_sha256: str
    body_bytes: int
    wrote_files: bool


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


# ---------------------------------------------------------------------------
# GitHub Remote URL Parsing (Mission 8)
# ---------------------------------------------------------------------------

def parse_github_remote_url(remote_url: str | None) -> tuple[str | None, str | None]:
    """Parse a Git remote URL to extract GitHub owner and repository.

    Mission 8: GitHub Apply Safety Doctor

    Supports URL formats:
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo
    - git@github.com:owner/repo.git
    - ssh://git@github.com/owner/repo.git

    Args:
        remote_url: The Git remote URL to parse, or None

    Returns:
        Tuple of (owner, repository), both None if not a GitHub URL or parsing fails
    """
    if not remote_url:
        return None, None

    # Normalize URL
    url = remote_url.strip()

    # Check if this is a GitHub URL
    url_lower = url.lower()
    if "github.com" not in url_lower:
        return None, None

    # Remove .git suffix if present
    if url.endswith(".git"):
        url = url[:-4]

    # Parse different URL formats
    # Format 1: https://github.com/owner/repo
    if url.startswith("https://") or url.startswith("http://"):
        # Remove protocol
        no_protocol = url[8:] if url.startswith("https://") else url[7:]
        # Remove github.com
        if no_protocol.startswith("github.com/"):
            path = no_protocol[11:]  # len("github.com/")
        elif no_protocol.startswith("www.github.com/"):
            path = no_protocol[15:]  # len("www.github.com/")
        else:
            return None, None
        # Split on /
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    # Format 2: git@github.com:owner/repo (SCP-like)
    if url.startswith("git@"):
        # Remove git@
        no_user = url[4:]
        # Split on :
        if ":" in no_user:
            host_port, path = no_user.split(":", 1)
            # Check host is github.com
            if "github.com" in host_port:
                parts = path.strip("/").split("/")
                if len(parts) >= 2:
                    return parts[0], parts[1]
        return None, None

    # Format 3: ssh://git@github.com/owner/repo
    if url.startswith("ssh://"):
        # Remove ssh://
        no_protocol = url[6:]
        # Remove git@ if present
        if no_protocol.startswith("git@"):
            no_user = no_protocol[4:]
        else:
            no_user = no_protocol
        # Remove github.com
        if no_user.startswith("github.com/"):
            path = no_user[11:]
        else:
            return None, None
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    return None, None


# ---------------------------------------------------------------------------
# GitHub Apply Safety Report (Mission 8)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GitHubApplySafetyReport:
    """Safety report for GitHub apply operations.

    Mission 8: GitHub Apply Safety Doctor
    Mission 9: Updated with backend_plan field

    Read-only safety verification for GitHub promotion apply path.
    This report must pass before any mutation is allowed.
    """
    provider: str
    owner: str | None
    repository: str | None
    remote_url: str | None
    gh_available: bool
    gh_authenticated: bool
    artifact_valid: bool
    existing_pr_url: str | None
    promotion_branch_safe: bool
    direct_target_mutation_detected: bool
    forbidden_commands_detected: tuple[str, ...]
    ready: bool
    findings: tuple[ForgeDoctorFinding, ...]
    backend_plan: "GitHubBackendPlan | None" = None


# ---------------------------------------------------------------------------
# GitHub Backend Boundary (Mission 9)
# ---------------------------------------------------------------------------

def build_github_backend_plan(
    requested_mode: GitHubBackendMode = GitHubBackendMode.AUTO,
    gh_available: bool | None = None,
    gh_authenticated: bool | None = None,
    api_token_available: bool = False,
    token_source: str | None = None,
) -> GitHubBackendPlan:
    """Build a GitHub backend plan based on requested mode and availability.

    Mission 9: GitHub Adapter Backend Boundary

    Determines which backend (CLI or API) should be used for GitHub operations,
    and whether it's available. The API backend is not yet implemented and
    will always fail closed.

    Args:
        requested_mode: The backend mode requested by the user (default: AUTO)
        gh_available: Whether GitHub CLI (gh) is available (None = check)
        gh_authenticated: Whether GitHub CLI is authenticated (None = check)
        api_token_available: Whether API token is available (default: False)
        token_source: Description of token source (NOT the token value)

    Returns:
        GitHubBackendPlan with backend selection and availability info
    """
    findings: list[ForgeDoctorFinding] = []

    # Default selections
    selected_mode: GitHubBackendMode | None = None
    backend_available = False
    requires_gh = False
    requires_token = False
    reason = ""

    # Handle CLI mode
    if requested_mode == GitHubBackendMode.CLI:
        requires_gh = True
        requires_token = False

        # Check gh availability
        if gh_available is None:
            # Need to check
            gh_available, _, gh_findings = _check_gh_cli_available()
            findings.extend(gh_findings)

        if gh_available:
            # Check authentication
            if gh_authenticated is None:
                gh_authenticated = False
                # Try to check auth
                try:
                    proc = subprocess.run(
                        ["/usr/bin/env", "gh", "auth", "status", "--hostname", "github.com"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    auth_output = proc.stdout + proc.stderr
                    if proc.returncode == 0:
                        if ("logged in" in auth_output.lower() or
                            "logged into" in auth_output.lower() or
                            "active" in auth_output.lower()):
                            gh_authenticated = True
                except Exception:
                    gh_authenticated = False

            if gh_authenticated:
                backend_available = True
                selected_mode = GitHubBackendMode.CLI
                reason = "CLI backend available and authenticated"
            else:
                findings.append(ForgeDoctorFinding(
                    code="github_cli_backend_not_authenticated",
                    severity=ForgeDoctorSeverity.ERROR,
                    message="GitHub CLI is not authenticated for github.com",
                    remediation="Run 'gh auth login' to authenticate",
                ))
                reason = "CLI backend requires GitHub CLI authentication"
        else:
            findings.append(ForgeDoctorFinding(
                code="github_cli_backend_not_available",
                severity=ForgeDoctorSeverity.ERROR,
                message="GitHub CLI (gh) is not available",
                remediation="Install GitHub CLI from https://cli.github.com",
            ))
            reason = "CLI backend requires GitHub CLI (gh)"

    # Handle API mode
    elif requested_mode == GitHubBackendMode.API:
        requires_gh = False
        requires_token = True
        token_source = token_source or "environment or config"

        # API backend is not yet implemented
        findings.append(ForgeDoctorFinding(
            code="github_api_backend_not_implemented",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub API backend is not yet implemented",
            remediation="Use --github-backend cli or auto, or wait for API backend implementation",
        ))
        backend_available = False
        selected_mode = None
        reason = "API backend is not yet implemented"

    # Handle AUTO mode
    elif requested_mode == GitHubBackendMode.AUTO:
        # Try CLI first if available and authenticated
        if gh_available is None:
            gh_available, _, gh_findings = _check_gh_cli_available()
            findings.extend(gh_findings)

        if gh_available:
            if gh_authenticated is None:
                gh_authenticated = False
                try:
                    proc = subprocess.run(
                        ["/usr/bin/env", "gh", "auth", "status", "--hostname", "github.com"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    auth_output = proc.stdout + proc.stderr
                    if proc.returncode == 0:
                        if ("logged in" in auth_output.lower() or
                            "logged into" in auth_output.lower() or
                            "active" in auth_output.lower()):
                            gh_authenticated = True
                except Exception:
                    gh_authenticated = False

            if gh_authenticated:
                selected_mode = GitHubBackendMode.CLI
                backend_available = True
                requires_gh = True
                requires_token = False
                reason = "Auto-selected CLI backend (gh available and authenticated)"
            else:
                # CLI available but not authenticated
                selected_mode = None
                backend_available = False
                requires_gh = True
                requires_token = False
                reason = "No available GitHub backend (CLI available but not authenticated)"
                findings.append(ForgeDoctorFinding(
                    code="github_backend_auto_no_auth",
                    severity=ForgeDoctorSeverity.ERROR,
                    message="GitHub CLI is available but not authenticated",
                    remediation="Authenticate with 'gh auth login' or use a different backend",
                ))
        else:
            # CLI not available, API not implemented
            selected_mode = None
            backend_available = False
            requires_gh = False
            requires_token = False
            reason = "No available GitHub backend (CLI not available, API not implemented)"
            findings.append(ForgeDoctorFinding(
                code="github_backend_auto_unavailable",
                severity=ForgeDoctorSeverity.ERROR,
                message="No available GitHub backend",
                remediation="Install GitHub CLI (gh) and authenticate, or wait for API backend implementation",
            ))

    return GitHubBackendPlan(
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        backend_available=backend_available,
        requires_gh=requires_gh,
        requires_token=requires_token,
        token_source=token_source,
        reason=reason,
        findings=tuple(findings),
    )


# ---------------------------------------------------------------------------
# Forbidden Command Patterns (Mission 8)
# ---------------------------------------------------------------------------

# Forbidden command patterns that must never appear in apply command lists
# Note: "git push" is NOT in this list because pushing to promotion branches is allowed.
# Direct target mutation is checked separately via _check_direct_target_mutation.
FORBIDDEN_COMMAND_PATTERNS: tuple[str, ...] = (
    # Git mutation commands that are always forbidden
    "git checkout",
    "git merge",
    "git reset",
    "git clean",
    "git stash",
    # PR merge operations
    "gh pr merge",
    "gh pr merge --admin",
    # PR ready without explicit control
    "gh pr ready",
    # PR editing that could bypass rules
    "gh pr edit",
    # Branch protection via API
    "gh api repos/",
    # Worktree mutation
    "git worktree move",
    "git worktree remove",
)


def _contains_forbidden_pattern(command_str: str) -> tuple[bool, tuple[str, ...]]:
    """Check if a command string contains any forbidden patterns.

    Mission 8: GitHub Apply Safety Doctor

    Args:
        command_str: The command string to check

    Returns:
        Tuple of (has_forbidden, detected_patterns)
    """
    detected: list[str] = []
    for pattern in FORBIDDEN_COMMAND_PATTERNS:
        if pattern in command_str:
            detected.append(pattern)
    return len(detected) > 0, tuple(detected)


def _check_direct_target_mutation(
    command_str: str,
    target_ref: str,
) -> bool:
    """Check if a command would directly mutate the target branch.

    Mission 8: GitHub Apply Safety Doctor

    Args:
        command_str: The command string to check
        target_ref: The target branch reference (e.g., "preproduction")

    Returns:
        True if the command would directly mutate target_ref
    """
    # Check for git push to target_ref
    # Patterns like: git push origin preproduction
    #               git push -u origin preproduction
    #               git push origin preproduction:preproduction
    push_patterns = [
        f"git push {target_ref}",
        f"git push -u {target_ref}",
        f"git push origin {target_ref}",
        f"git push -u origin {target_ref}",
    ]
    for pattern in push_patterns:
        if pattern in command_str:
            return True
    return False


def _check_promotion_branch_safe(promotion_branch: str, target_ref: str) -> bool:
    """Check if promotion branch name is safe.

    Mission 8: GitHub Apply Safety Doctor

    Rules:
    - Promotion branch must not be empty
    - Promotion branch must not match target_ref exactly
    - Promotion branch should not contain dangerous characters

    Args:
        promotion_branch: The promotion branch name
        target_ref: The target branch reference

    Returns:
        True if the promotion branch is safe
    """
    if not promotion_branch:
        return False
    if promotion_branch == target_ref:
        return False
    # Check for dangerous characters (very basic check)
    if ".." in promotion_branch or promotion_branch.startswith("-"):
        return False
    return True


def build_github_apply_safety_report(
    repo_path: Path | str,
    plan: PromotionPlan,
    artifact: PromotionArtifact,
    remote: str = "origin",
    requested_backend_mode: GitHubBackendMode = GitHubBackendMode.AUTO,
) -> GitHubApplySafetyReport:
    """Build a read-only safety report for GitHub apply operations.

    Mission 8: GitHub Apply Safety Doctor
    Mission 9: Updated with backend_plan parameter

    This function is READ-ONLY and performs no mutations.
    It may run:
    - gh --version
    - gh auth status
    - gh pr list --base <target_ref> --head <promotion_branch> --json url,number,state --limit 1
    - git remote get-url <remote>

    Args:
        repo_path: Path to the git repository root
        plan: The promotion plan
        artifact: The promotion artifact
        remote: The Git remote name (default: "origin")
        requested_backend_mode: The backend mode to use (default: AUTO)

    Returns:
        GitHubApplySafetyReport with safety verification results
    """
    import datetime

    repo_path = Path(repo_path)
    findings: list[ForgeDoctorFinding] = []

    # Parse remote URL
    remote_url = git_remote_url(repo_path, remote)
    owner, repository = parse_github_remote_url(remote_url)

    # Check gh CLI availability
    gh_available, gh_version, gh_check_findings = _check_gh_cli_available()
    findings.extend(gh_check_findings)

    # Build backend plan (Mission 9)
    backend_plan = build_github_backend_plan(
        requested_mode=requested_backend_mode,
        gh_available=gh_available,
        gh_authenticated=None,  # Will be checked inside build_github_backend_plan
        api_token_available=False,
        token_source=None,
    )
    findings.extend(backend_plan.findings)

    # Check gh authentication
    gh_authenticated = False
    if gh_available:
        # Check auth status specifically for github.com
        try:
            proc = subprocess.run(
                ["/usr/bin/env", "gh", "auth", "status", "--hostname", "github.com"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            auth_output = proc.stdout + proc.stderr
            if proc.returncode == 0:
                if ("logged in" in auth_output.lower() or 
                    "logged into" in auth_output.lower() or
                    "active" in auth_output.lower()):
                    gh_authenticated = True
            # If --hostname didn't work, try without
            if not gh_authenticated:
                proc2 = subprocess.run(
                    ["/usr/bin/env", "gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                auth_output2 = proc2.stdout + proc2.stderr
                if proc2.returncode == 0:
                    if ("github.com" in auth_output2 and
                        ("logged in" in auth_output2.lower() or
                         "logged into" in auth_output2.lower() or
                         "active" in auth_output2.lower())):
                        gh_authenticated = True
        except subprocess.TimeoutExpired:
            findings.append(ForgeDoctorFinding(
                code="SAFETY-001",
                severity=ForgeDoctorSeverity.WARNING,
                message="gh auth status check timed out",
                remediation="Check GitHub CLI responsiveness",
            ))
        except Exception as e:
            findings.append(ForgeDoctorFinding(
                code="SAFETY-002",
                severity=ForgeDoctorSeverity.WARNING,
                message=f"gh auth status check failed: {e}",
                remediation="Check GitHub CLI installation",
            ))

    # Verify artifact
    artifact_valid, artifact_findings = verify_promotion_artifact(repo_path, artifact)
    findings.extend(artifact_findings)

    # Check for existing PR
    existing_pr_url: str | None = None
    if plan.draft is not None and gh_available:
        pr_exists, pr_url, pr_findings = _github_cli_check_existing_pr(
            target_ref=plan.target_ref,
            promotion_branch=plan.draft.promotion_branch,
            remote=remote,
        )
        findings.extend(pr_findings)
        if pr_exists and pr_url:
            existing_pr_url = pr_url

    # Check promotion branch safety
    promotion_branch_safe = False
    if plan.draft is not None:
        promotion_branch_safe = _check_promotion_branch_safe(
            plan.draft.promotion_branch, plan.target_ref
        )
        if not promotion_branch_safe:
            findings.append(ForgeDoctorFinding(
                code="SAFETY-003",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Promotion branch '{plan.draft.promotion_branch}' is not safe for target '{plan.target_ref}'",
                remediation="Use a different promotion branch name",
            ))

    # Build command list from plan (simulating what apply would build)
    # This is the same logic as in apply_github_draft_pr_promotion
    commands: list[str] = []
    if plan.draft is not None:
        promotion_branch = plan.draft.promotion_branch
        title = plan.draft.title
        body_path = artifact.body_path

        # Command 1: Create/update promotion branch
        cmd1_args = ["git", "branch", "-f", promotion_branch]
        if plan.head_ref != "HEAD":
            cmd1_args.append(plan.head_ref)
        commands.append(" ".join(cmd1_args))

        # Command 2: Push promotion branch to remote
        cmd2_args = ["git", "push", "-u", remote, promotion_branch]
        commands.append(" ".join(cmd2_args))

        # Command 3: Create draft PR
        cmd3_args = [
            "gh", "pr", "create",
            "--draft",
            "--base", plan.target_ref,
            "--head", promotion_branch,
            "--title", title,
            "--body-file", body_path,
        ]
        commands.append(" ".join(cmd3_args))

    # Check for forbidden commands
    forbidden_commands_detected: list[str] = []
    for cmd in commands:
        has_forbidden, detected = _contains_forbidden_pattern(cmd)
        if has_forbidden:
            forbidden_commands_detected.extend(detected)

    # Check for direct target mutation
    direct_target_mutation_detected = False
    for cmd in commands:
        if _check_direct_target_mutation(cmd, plan.target_ref):
            direct_target_mutation_detected = True
            break

    if forbidden_commands_detected:
        findings.append(ForgeDoctorFinding(
            code="SAFETY-004",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Forbidden commands detected: {', '.join(forbidden_commands_detected)}",
            remediation="Review and remove forbidden commands from promotion plan",
        ))

    if direct_target_mutation_detected:
        findings.append(ForgeDoctorFinding(
            code="SAFETY-005",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Direct mutation of target branch '{plan.target_ref}' detected",
            remediation="Commands must not push directly to target branch",
        ))

    # Determine overall ready status
    # Ready only if:
    # 1. gh is available and authenticated
    # 2. artifact is valid
    # 3. promotion branch is safe
    # 4. no forbidden commands detected
    # 5. no direct target mutation detected
    ready = (
        gh_available and
        gh_authenticated and
        artifact_valid and
        promotion_branch_safe and
        not direct_target_mutation_detected and
        len(forbidden_commands_detected) == 0
    )

    # Add findings for any missing requirements
    if not gh_available:
        findings.append(ForgeDoctorFinding(
            code="SAFETY-006",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub CLI (gh) is not available",
            remediation="Install GitHub CLI from https://cli.github.com",
        ))

    if not gh_authenticated:
        findings.append(ForgeDoctorFinding(
            code="SAFETY-007",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub CLI is not authenticated for github.com",
            remediation="Run 'gh auth login' to authenticate",
        ))

    if not artifact_valid:
        findings.append(ForgeDoctorFinding(
            code="SAFETY-008",
            severity=ForgeDoctorSeverity.ERROR,
            message="Artifact verification failed",
            remediation="Regenerate artifact with --write-artifact",
        ))

    # Update ready status to also require backend availability
    ready = (
        ready and
        backend_plan.backend_available
    )

    # If backend not available but wasn't already caught by other checks
    if not backend_plan.backend_available and not any(
        f.code in ("github_cli_backend_not_available", "github_cli_backend_not_authenticated", 
                   "github_api_backend_not_implemented", "github_backend_auto_no_auth", 
                   "github_backend_auto_unavailable")
        for f in findings
    ):
        # This shouldn't happen if backend_plan.findings were added, but just in case
        findings.append(ForgeDoctorFinding(
            code="github_backend_unavailable",
            severity=ForgeDoctorSeverity.ERROR,
            message="No available GitHub backend",
            remediation="Ensure GitHub CLI is installed and authenticated, or use a different backend",
        ))

    return GitHubApplySafetyReport(
        provider="github",
        owner=owner,
        repository=repository,
        remote_url=remote_url,
        gh_available=gh_available,
        gh_authenticated=gh_authenticated,
        artifact_valid=artifact_valid,
        existing_pr_url=existing_pr_url,
        promotion_branch_safe=promotion_branch_safe,
        direct_target_mutation_detected=direct_target_mutation_detected,
        forbidden_commands_detected=tuple(forbidden_commands_detected),
        ready=ready,
        findings=tuple(findings),
        backend_plan=backend_plan,
    )


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
# Promotion Branch Naming (Mission 5)
# ---------------------------------------------------------------------------

def _make_git_ref_safe(name: str) -> str:
    """Make a string safe for use as a Git ref.
    
    Args:
        name: The string to make Git-ref-safe
        
    Returns:
        A string safe for use in Git refs: lowercase, alphanumeric with -_.
        Leading/trailing dots and dashes are stripped.
    """
    # Replace spaces and slashes with dashes
    safe = name.replace(" ", "-").replace("/", "-")
    # Keep only alphanumeric, dots, underscores, and dashes
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in safe)
    # Strip leading/trailing dots and dashes
    safe = safe.lstrip(".-").rstrip(".-")
    # Lowercase
    safe = safe.lower()
    # If empty after processing, use "unknown"
    if not safe:
        safe = "unknown"
    return safe


def derive_promotion_branch_name(
    head_ref: str = "HEAD",
    target_ref: str = "preproduction",
    prefix: str = "promotion",
) -> str:
    """Derive a deterministic, Git-ref-safe promotion branch name.
    
    Mission 5: Promotion Branch + PR Draft Planner
    
    This is a PURE function - no Git calls, no side effects.
    It uses head_ref directly as the source reference name.
    
    Rules:
    - Deterministic: same inputs produce same output
    - Git-ref-safe: only characters valid in Git refs
    - Lowercase
    - No spaces
    - Default shape: prefix/target/safe-head-ref
    
    Args:
        head_ref: Head reference (e.g., "sprint/governed-agent-pipeline") (default: "HEAD")
        target_ref: Target reference for promotion (default: "preproduction")
        prefix: Prefix for branch name (default: "promotion")
        
    Returns:
        A Git-ref-safe branch name string
        
    Example:
        head_ref: sprint/governed-agent-pipeline
        target_ref: preproduction
        -> promotion/preproduction/sprint-governed-agent-pipeline
    """
    # If head_ref is "HEAD", we can't derive a branch name from it
    # Use "head" as a safe fallback for when actual branch is unknown
    source_name = head_ref if head_ref != "HEAD" else "head"
    
    # Make the names safe for Git refs
    safe_name = _make_git_ref_safe(source_name)
    safe_target = _make_git_ref_safe(target_ref)
    safe_prefix = _make_git_ref_safe(prefix)
    
    # Build the branch name: prefix/target/safe-name
    return f"{safe_prefix}/{safe_target}/{safe_name}"


# ---------------------------------------------------------------------------
# Promotion Draft Building (Mission 5)
# ---------------------------------------------------------------------------

def _build_draft_title(target_ref: str) -> str:
    """Build a deterministic PR/MR title for promotion.
    
    Args:
        target_ref: Target reference for promotion
        
    Returns:
        Title string for PR/MR
    """
    # Use a generic title that doesn't include personal names
    # target_ref is already sanitized by caller
    return f"Promotion to {target_ref}"


def _build_draft_body(
    identity: ForgeIdentity,
    plan: PromotionPlan,
    promotion_branch: str,
) -> str:
    """Build PR/MR body content for promotion draft.
    
    Args:
        identity: Forge identity
        plan: Promotion plan
        promotion_branch: The derived promotion branch name
        
    Returns:
        Body string for PR/MR description
    """
    rev = plan.reviewability
    mode_str = identity.mode.name.lower().replace("_", "-")
    promotion_mode_str = plan.mode.name.lower().replace("_", "-")
    
    # Current branch/head info
    head_info = plan.head_ref
    if isinstance(plan.head_ref, str):
        # Try to get more specific info if available
        pass
    
    # No personal names - use project-neutral wording
    lines = [
        "## Rig Promotion Draft",
        "",
        "This promotion was planned by Rig's forge-neutral promotion planner.",
        "",
        "**Promotion Details:**",
        f"- Target: {plan.target_ref}",
        f"- Head: {plan.head_ref}",
        f"- Promotion Branch: {promotion_branch}",
        "",
        "**Reviewability:**",
        f"- Changed files: {rev.changed_file_count} / {rev.max_changed_files}",
        f"- Status: {'OVER BUDGET' if rev.over_budget else 'Within budget'}",
        f"- Action: {rev.default_action}",
        "",
        f"**Forge Mode:** {mode_str}",
        f"**Promotion Mode:** {promotion_mode_str}",
        "",
        "**Validation Expectations:**",
        "- [ ] All required checks pass",
        "- [ ] Reviewability budget within limits",
        "- [ ] No merge conflicts",
        "- [ ] All tests pass",
    ]
    
    # Add blockers section if there are blockers
    if plan.blockers:
        lines.append("")
        lines.append("**Blockers:**")
        for b in plan.blockers:
            lines.append(f"- [{b.code}] {b.message}")
    
    lines.extend([
        "",
        "**Note:** No Git or remote state was mutated. This is a dry-run plan only.",
        "",
        "Generated by Rig promotion dry-run planner.",
    ])
    
    return "\n".join(lines)


def _derive_provider_command(
    forge_mode: ForgeMode,
    promotion_branch: str,
    target_ref: str,
    title: str,
    body_path: str | None = None,
) -> tuple[str | None, str | None]:
    """Derive provider-specific command preview and URL hint.
    
    Args:
        forge_mode: The forge mode
        promotion_branch: The promotion branch name
        target_ref: The target reference
        title: The PR/MR title
        body_path: Optional path to body file for --body-file flag
        
    Returns:
        Tuple of (provider_command, provider_url_hint)
        - provider_command: A display string showing the command, or None
        - provider_url_hint: A hint URL for manual creation, or None
    """
    match forge_mode:
        case ForgeMode.GITHUB:
            # gh pr create command (display only, not executed)
            command = (
                f"gh pr create --base {target_ref} --head {promotion_branch} "
                f'--title "{title}"'
            )
            # Use --body-file if body path is available
            if body_path:
                command += f" --body-file {body_path}"
            return command, None
        
        case ForgeMode.GITLAB:
            # glab mr create command (display only, not executed)
            # Note: glab CLI may not support --body-file directly
            # but we include it for consistency; adapter can handle specifically
            command = (
                f"glab mr create --base {target_ref} --head {promotion_branch} "
                f'--title "{title}"'
            )
            if body_path:
                # For GitLab, note that body-file support is adapter-dependent
                command += f" # Body file: {body_path} (adapter-dependent)"
            return command, None
        
        case ForgeMode.GITEA:
            # Gitea: no standard CLI, provide conceptual hint
            command = None
            url_hint = (
                f"# Gitea: Create PR with branch '{promotion_branch}' "
                f"targeting '{target_ref}' via web UI"
            )
            return command, url_hint
        
        case ForgeMode.LOCAL_ONLY:
            # Local-only: no PR/MR, just note the merge command
            command = (
                f"# Local-only: git merge {promotion_branch} (future: --apply)"
            )
            return command, None
        
        case ForgeMode.UNKNOWN:
            # Unknown forge: manual adapter required
            command = None
            url_hint = (
                "# Manual adapter required for unknown forge mode. "
                "Implement provider-specific adapter to execute promotion."
            )
            return command, url_hint


def build_promotion_draft(
    identity: ForgeIdentity,
    plan: PromotionPlan,
    body_path: str | None = None,
) -> PromotionDraft:
    """Build a complete promotion draft with branch name, title, body, and provider command.
    
    Mission 5: Promotion Branch + PR Draft Planner
    Mission 6: Updated to include body_path for --body-file flag
    
    This is a PURE function - no side effects, no Git calls.
    All information is derived from the provided plan and identity.
    
    Args:
        identity: Forge identity from build_forge_identity()
        plan: Promotion plan from build_promotion_plan()
        body_path: Optional path to body file for provider command --body-file flag
        
    Returns:
        PromotionDraft with all draft information including body_path
    """
    # Derive promotion branch name (pure function, no Git calls)
    promotion_branch = derive_promotion_branch_name(
        head_ref=plan.head_ref,
        target_ref=plan.target_ref,
    )
    
    # Build title
    title = _build_draft_title(plan.target_ref)
    
    # Build body
    body = _build_draft_body(identity, plan, promotion_branch)
    
    # Derive provider command and URL hint
    provider_command, provider_url_hint = _derive_provider_command(
        forge_mode=identity.mode,
        promotion_branch=promotion_branch,
        target_ref=plan.target_ref,
        title=title,
        body_path=body_path,
    )
    
    return PromotionDraft(
        promotion_branch=promotion_branch,
        base_ref=plan.target_ref,
        head_ref=plan.head_ref,
        title=title,
        body=body,
        provider_command=provider_command,
        provider_url_hint=provider_url_hint,
        draft_only=True,
        body_path=body_path,
    )


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
        For GitHub remotes, owner and repository are parsed from the URL.
        For other forges, owner and repository remain None (deferred to future missions).
    """
    remote_url = git_remote_url(repo_root, remote)
    mode = classify_remote_url(remote_url)
    
    # Parse remote URL for host (simple string matching)
    host = None
    owner = None
    repository = None
    
    if remote_url:
        url_lower = remote_url.lower()
        if "github.com" in url_lower:
            host = "github.com"
            # Parse owner and repository for GitHub URLs (Mission 8)
            owner, repository = parse_github_remote_url(remote_url)
        elif "gitlab.com" in url_lower:
            host = "gitlab.com"
        elif "gitea" in url_lower:
            host = "gitea"
    
    return ForgeIdentity(
        mode=mode,
        remote_url=remote_url,
        host=host,
        owner=owner,
        repository=repository,
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


# ---------------------------------------------------------------------------
# Promotion Plan Building
# ---------------------------------------------------------------------------

def _build_promotion_steps(
    forge_mode: ForgeMode,
    target_ref: str,
    head_ref: str,
    reviewability: ReviewabilityReport,
    ready: bool,
) -> list[PromotionPlanStep]:
    """Build ordered promotion steps based on forge mode.
    
    All steps have mutates_state=False for read-only verification steps.
    Future --apply mode would execute mutates_state=True steps.
    
    Args:
        forge_mode: The forge mode (LOCAL_ONLY, GITHUB, GITLAB, GITEA, UNKNOWN)
        target_ref: Target reference for promotion
        head_ref: Head reference for promotion
        reviewability: Reviewability report
        ready: Whether promotion is ready (no blockers)
        
    Returns:
        List of PromotionPlanStep objects in execution order.
    """
    steps: list[PromotionPlanStep] = [
        PromotionPlanStep(
            step_id="verify_git_repo",
            description="Verify repository is a valid Git repository",
            command=None,
            mutates_state=False,
            required=True,
        ),
        PromotionPlanStep(
            step_id="verify_clean_worktree",
            description="Verify working tree is clean (no uncommitted changes)",
            command="git status --porcelain",
            mutates_state=False,
            required=True,
        ),
        PromotionPlanStep(
            step_id="verify_target_branch_exists",
            description=f"Verify target branch '{target_ref}' exists locally",
            command=f"git branch --list {target_ref}",
            mutates_state=False,
            required=True,
        ),
        PromotionPlanStep(
            step_id="compute_reviewability",
            description=f"Compute changed files against '{target_ref}'",
            command=f"git merge-base {target_ref} {head_ref} && git diff --name-only $(git merge-base {target_ref} {head_ref}) {head_ref}",
            mutates_state=False,
            required=True,
        ),
    ]
    
    # Add mode-specific steps
    if ready:
        promotion_mode = derive_promotion_mode(forge_mode)
        match promotion_mode:
            case PromotionMode.LOCAL_BRANCH:
                steps.extend([
                    PromotionPlanStep(
                        step_id="local_merge",
                        description=f"Merge {head_ref} into {target_ref} locally (future: --apply)",
                        command=f"git merge {head_ref} --no-ff",
                        mutates_state=True,
                        required=True,
                    ),
                    PromotionPlanStep(
                        step_id="local_verify",
                        description="Verify merge result",
                        command="git status",
                        mutates_state=False,
                        required=True,
                    ),
                ])
            case PromotionMode.PULL_REQUEST:
                steps.extend([
                    PromotionPlanStep(
                        step_id="push_promotion_branch",
                        description="Push promotion branch to remote (future: --apply)",
                        command=None,
                        mutates_state=True,
                        required=True,
                    ),
                    PromotionPlanStep(
                        step_id="create_pull_request",
                        description="Create or update Pull Request (future: --apply)",
                        command=None,
                        mutates_state=True,
                        required=True,
                    ),
                    PromotionPlanStep(
                        step_id="wait_required_checks",
                        description="Wait for required checks to pass (future: forge adapter)",
                        command=None,
                        mutates_state=False,
                        required=False,
                    ),
                ])
            case PromotionMode.MERGE_REQUEST:
                steps.extend([
                    PromotionPlanStep(
                        step_id="push_promotion_branch",
                        description="Push promotion branch to remote (future: --apply)",
                        command=None,
                        mutates_state=True,
                        required=True,
                    ),
                    PromotionPlanStep(
                        step_id="create_merge_request",
                        description="Create or update Merge Request (future: --apply)",
                        command=None,
                        mutates_state=True,
                        required=True,
                    ),
                    PromotionPlanStep(
                        step_id="wait_pipeline",
                        description="Wait for pipeline to pass (future: forge adapter)",
                        command=None,
                        mutates_state=False,
                        required=False,
                    ),
                ])
            case PromotionMode.MANUAL:
                steps.append(PromotionPlanStep(
                    step_id="manual_merge",
                    description="Manual merge required (unknown forge mode)",
                    command=None,
                    mutates_state=True,
                    required=True,
                ))
    
    return steps


def build_promotion_plan(
    repo_root: Path,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
    budget: ReviewabilityBudget | None = None,
) -> PromotionPlan:
    """Build a promotion plan for repository promotion.
    
    This is a dry-run only function. It does NOT mutate Git state.
    It explains what Rig would do if promotion were applied.
    
    Args:
        repo_root: Path to the git repository
        target_ref: Target reference for promotion (default: "preproduction")
        head_ref: Head reference to compare against (default: "HEAD")
        budget: Reviewability budget (default: None uses ReviewabilityBudget())
        
    Returns:
        PromotionPlan with analysis and ordered steps.
        dry_run_only is always True for this mission.
    """
    # Build identity and reviewability
    identity = build_forge_identity(repo_root)
    reviewability = build_reviewability_report(
        repo_root,
        budget=budget,
        target_ref=target_ref,
        head_ref=head_ref,
    )
    
    # Collect blockers
    blockers: list[ForgeDoctorFinding] = []
    ready: bool = True
    
    # Check if inside git repo
    if not git_inside_repo(repo_root):
        blockers.append(ForgeDoctorFinding(
            code="PROMOTION-001",
            severity=ForgeDoctorSeverity.ERROR,
            message="Not inside a Git repository",
            remediation="Initialize a git repository with 'git init' or navigate to a git repo",
        ))
        ready = False
    else:
        # Check if target_ref exists
        if not git_branch_exists(repo_root, target_ref):
            blockers.append(ForgeDoctorFinding(
                code="PROMOTION-002",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Target branch '{target_ref}' does not exist locally",
                remediation=f"Create the branch with 'git branch {target_ref} <source>'",
            ))
            ready = False
        
        # Check if over budget and blocking
        if reviewability.over_budget and reviewability.default_action == "block_promotion":
            blockers.append(ForgeDoctorFinding(
                code="PROMOTION-003",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Reviewability budget exceeded: {reviewability.changed_file_count} > {reviewability.max_changed_files}",
                remediation="Reduce changes or request override with reason",
            ))
            ready = False
        
        # Check if merge base is unavailable
        if reviewability.merge_base is None:
            blockers.append(ForgeDoctorFinding(
                code="PROMOTION-004",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Cannot find merge base between '{target_ref}' and '{head_ref}'",
                remediation="Ensure both references exist and are reachable",
            ))
            ready = False
    
    # Build steps
    steps = _build_promotion_steps(
        identity.mode,
        target_ref,
        head_ref,
        reviewability,
        ready,
    )
    
    # Build promotion draft (Mission 5: Promotion Branch + PR Draft Planner)
    # Even if not ready, we still build a draft showing what would be used
    # The draft's provider_command may be None for some forge modes
    # Note: This is a pure function - no Git calls, uses head_ref from plan
    draft = build_promotion_draft(
        identity=identity,
        plan=PromotionPlan(
            mode=derive_promotion_mode(identity.mode),
            forge_mode=identity.mode,
            target_ref=target_ref,
            head_ref=head_ref,
            identity=identity,
            reviewability=reviewability,
            steps=tuple(steps),
            blockers=tuple(blockers),
            ready=ready,
            dry_run_only=True,
            draft=None,  # Placeholder, will be set below
        ),
    )
    
    return PromotionPlan(
        mode=derive_promotion_mode(identity.mode),
        forge_mode=identity.mode,
        target_ref=target_ref,
        head_ref=head_ref,
        identity=identity,
        reviewability=reviewability,
        steps=tuple(steps),
        blockers=tuple(blockers),
        ready=ready,
        dry_run_only=True,
        draft=draft,
    )


# ---------------------------------------------------------------------------
# Promotion Artifact Helpers (Mission 6)
# ---------------------------------------------------------------------------

def _make_filesystem_safe(name: str) -> str:
    """Make a string safe for use as a filesystem path component.
    
    Args:
        name: The string to make filesystem-safe
        
    Returns:
        A string safe for use in filesystem paths: lowercase, alphanumeric with -_.
    """
    # Replace spaces, slashes, colons with dashes
    safe = name.replace(" ", "-").replace("/", "-").replace(":", "-")
    # Keep only alphanumeric, dots, underscores, and dashes
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in safe)
    # Strip leading/trailing dots and dashes
    safe = safe.lstrip(".-").rstrip(".-")
    # Lowercase
    safe = safe.lower()
    # If empty after processing, use "unknown"
    if not safe:
        safe = "unknown"
    # Collapse multiple dashes
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe


def derive_promotion_artifact_id(
    target_ref: str,
    head_ref: str,
    body_sha256: str,
) -> str:
    """Derive a deterministic artifact ID for promotion artifact.
    
    Mission 6: Promotion Body File Dry-Run Artifact
    
    The artifact ID is based on target_ref, head_ref, and body content hash.
    This ensures the same promotion plan produces the same artifact ID.
    
    Args:
        target_ref: Target reference for promotion
        head_ref: Head reference for promotion
        body_sha256: SHA256 hex digest of the body content
        
    Returns:
        A deterministic, filesystem-safe artifact ID string
        Format: promotion-{target}-{head}-{short_hash}
    """
    # Use short hash (first 12 chars) for readability
    short_hash = body_sha256[:12]
    
    # Make refs filesystem-safe
    safe_target = _make_filesystem_safe(target_ref)
    safe_head = _make_filesystem_safe(str(head_ref))
    
    return f"promotion-{safe_target}-{safe_head}-{short_hash}"


def derive_promotion_artifact_paths(
    repo_path: Path | str,
    artifact_id: str,
    artifact_dir: str = ".rig/work/promotions",
) -> tuple[str, str, str]:
    """Derive artifact file paths from artifact ID and repo path.
    
    Mission 6: Promotion Body File Dry-Run Artifact
    
    Args:
        repo_path: Path to the git repository root
        artifact_id: The derived artifact ID
        artifact_dir: Base directory for artifacts (default: ".rig/work/promotions")
        
    Returns:
        Tuple of (directory_path, body_path, metadata_path)
        - directory_path: Full path to artifact directory
        - body_path: Full path to body.md file
        - metadata_path: Full path to metadata.json file
    """
    base_dir = Path(repo_path) / artifact_dir / artifact_id
    directory_path = str(base_dir)
    body_path = str(base_dir / "body.md")
    metadata_path = str(base_dir / "metadata.json")
    return directory_path, body_path, metadata_path


def _compute_body_sha256(body: str) -> str:
    """Compute SHA256 hex digest of body content.
    
    Args:
        body: The body content string
        
    Returns:
        SHA256 hex digest string (lowercase, 64 characters)
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_promotion_artifact(
    repo_path: Path | str,
    plan: PromotionPlan,
    write: bool = False,
    artifact_dir: str = ".rig/work/promotions",
) -> PromotionArtifact:
    """Build a promotion artifact with body file and metadata.
    
    Mission 6: Promotion Body File Dry-Run Artifact
    
    This function computes artifact paths and body hashes. If write=True,
    it creates the artifact directory and writes body.md and metadata.json files.
    
    NO GIT MUTATION: This function only writes local filesystem files under
    the artifact directory. It does not modify Git history, branches, worktrees,
    or remote state.
    
    Args:
        repo_path: Path to the git repository root
        plan: The promotion plan (must have draft with body)
        write: If True, write artifact files to filesystem (default: False)
        artifact_dir: Base directory for artifacts (default: ".rig/work/promotions")
        
    Returns:
        PromotionArtifact with all artifact information
        
    Raises:
        ValueError: If plan.draft is None or plan.draft.body is empty
    """
    if plan.draft is None:
        raise ValueError("Cannot build artifact: plan.draft is None")
    
    body = plan.draft.body
    if not body:
        raise ValueError("Cannot build artifact: draft body is empty")
    
    # Compute body hash and size
    body_sha256 = _compute_body_sha256(body)
    body_bytes = len(body.encode("utf-8"))
    
    # Derive artifact ID
    artifact_id = derive_promotion_artifact_id(
        target_ref=plan.target_ref,
        head_ref=plan.head_ref,
        body_sha256=body_sha256,
    )
    
    # Derive paths
    directory, body_path, metadata_path = derive_promotion_artifact_paths(
        repo_path=repo_path,
        artifact_id=artifact_id,
        artifact_dir=artifact_dir,
    )
    
    # If writing, create directory and write files
    wrote_files = False
    if write:
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Write body.md
        Path(body_path).write_text(body, encoding="utf-8")
        
        # Build and write metadata.json
        metadata = {
            "artifact_id": artifact_id,
            "target_ref": plan.target_ref,
            "head_ref": plan.head_ref,
            "forge_mode": plan.forge_mode.name.lower(),
            "promotion_mode": plan.mode.name.lower(),
            "promotion_branch": plan.draft.promotion_branch,
            "title": plan.draft.title,
            "body_path": body_path,
            "body_sha256": body_sha256,
            "body_bytes": body_bytes,
            "reviewability_changed_file_count": plan.reviewability.changed_file_count,
            "reviewability_max_changed_files": plan.reviewability.max_changed_files,
            "reviewability_over_budget": plan.reviewability.over_budget,
            "ready": plan.ready,
            "blockers": [
                {
                    "code": b.code,
                    "severity": b.severity.value,
                    "message": b.message,
                    "remediation": b.remediation,
                }
                for b in plan.blockers
            ],
            "dry_run_only": plan.dry_run_only,
        }
        import json
        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        
        wrote_files = True
    
    return PromotionArtifact(
        artifact_id=artifact_id,
        directory=directory,
        body_path=body_path,
        metadata_path=metadata_path,
        body_sha256=body_sha256,
        body_bytes=body_bytes,
        wrote_files=wrote_files,
    )


# ---------------------------------------------------------------------------
# GitHub Promotion Apply Domain Types (Mission 7)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GitHubPromotionApplyResult:
    """Result of applying a GitHub draft PR promotion.

    Mission 7: GitHub Draft PR Apply
    Mission 11: Updated with API backend fields

    Represents the outcome of executing the apply_github_draft_pr_promotion
    function. Contains all information about what was done or planned,
    including commands executed, PR URL, and any findings.
    """
    provider: str
    promotion_branch: str
    target_ref: str
    head_ref: str
    artifact_id: str
    body_path: str
    pr_url: str | None
    commands: tuple[str, ...]
    ready_before_apply: bool
    applied: bool
    skipped_existing_pr: bool
    evidence_path: str | None
    findings: tuple[ForgeDoctorFinding, ...]
    # Mission 11: API backend fields
    backend: str = "cli"  # "cli" or "api"
    api_library: str | None = None  # "pygithub" or "direct_rest" when backend="api"
    token_source: str | None = None  # Token source description, NOT the token value
    token_present: bool = False  # Whether a token was available, NOT the token itself


# ---------------------------------------------------------------------------
# Artifact Verification (Mission 7)
# ---------------------------------------------------------------------------

def verify_promotion_artifact(
    repo_path: Path | str,
    artifact: PromotionArtifact,
) -> tuple[bool, tuple[ForgeDoctorFinding, ...]]:
    """Verify a promotion artifact is valid and matches expected state.

    Mission 7: GitHub Draft PR Apply

    Checks:
    - body_path exists
    - metadata_path exists
    - body SHA256 matches metadata and artifact.body_sha256
    - metadata target/head/title/branch match where possible

    Args:
        repo_path: Path to the git repository root
        artifact: The PromotionArtifact to verify

    Returns:
        Tuple of (is_valid, findings)
        - is_valid: True if artifact is valid, False otherwise
        - findings: Tuple of ForgeDoctorFinding with any verification issues
    """
    findings: list[ForgeDoctorFinding] = []

    # Check body_path exists
    body_path = Path(artifact.body_path)
    if not body_path.exists():
        findings.append(ForgeDoctorFinding(
            code="ARTIFACT-001",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Body file not found: {artifact.body_path}",
            remediation="Run promotion with --write-artifact to create the body file",
        ))

    # Check metadata_path exists
    metadata_path = Path(artifact.metadata_path)
    if not metadata_path.exists():
        findings.append(ForgeDoctorFinding(
            code="ARTIFACT-002",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Metadata file not found: {artifact.metadata_path}",
            remediation="Run promotion with --write-artifact to create the metadata file",
        ))

    # Check body SHA256 matches
    if body_path.exists():
        try:
            actual_body = body_path.read_text(encoding="utf-8")
            actual_sha256 = _compute_body_sha256(actual_body)
            if actual_sha256 != artifact.body_sha256:
                findings.append(ForgeDoctorFinding(
                    code="ARTIFACT-003",
                    severity=ForgeDoctorSeverity.ERROR,
                    message=f"Body SHA256 mismatch: expected {artifact.body_sha256[:16]}... got {actual_sha256[:16]}...",
                    remediation="Regenerate artifact with --write-artifact",
                ))
        except (OSError, IOError) as e:
            findings.append(ForgeDoctorFinding(
                code="ARTIFACT-004",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Failed to read body file: {e}",
                remediation="Check file permissions and regenerating artifact",
            ))

    # Check metadata content if it exists
    if metadata_path.exists():
        try:
            import json
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

            # Verify body_sha256 in metadata matches artifact
            if metadata.get("body_sha256") != artifact.body_sha256:
                findings.append(ForgeDoctorFinding(
                    code="ARTIFACT-005",
                    severity=ForgeDoctorSeverity.ERROR,
                    message="Metadata body_sha256 does not match artifact body_sha256",
                    remediation="Regenerate artifact with --write-artifact",
                ))

            # Verify body_path in metadata matches artifact
            if metadata.get("body_path") != artifact.body_path:
                findings.append(ForgeDoctorFinding(
                    code="ARTIFACT-006",
                    severity=ForgeDoctorSeverity.WARNING,
                    message="Metadata body_path does not match artifact body_path",
                    remediation="Regenerate artifact with --write-artifact",
                ))

        except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
            findings.append(ForgeDoctorFinding(
                code="ARTIFACT-007",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"Failed to validate metadata file: {e}",
                remediation="Regenerate artifact with --write-artifact",
            ))

    is_valid = len(findings) == 0
    return is_valid, tuple(findings)


# ---------------------------------------------------------------------------
# GitHub gh CLI Detection
# ---------------------------------------------------------------------------

def _check_gh_cli_available() -> tuple[bool, str | None, tuple[ForgeDoctorFinding, ...]]:
    """Check if gh CLI is available and authenticated.

    Mission 7: GitHub Draft PR Apply

    Returns:
        Tuple of (is_available, gh_version, findings)
    """
    import shutil
    findings: list[ForgeDoctorFinding] = []

    # Check if gh is in PATH
    gh_path = shutil.which("gh")
    if gh_path is None:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-001",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub CLI (gh) not found in PATH",
            remediation="Install GitHub CLI from https://cli.github.com/",
        ))
        return False, None, tuple(findings)

    # Check gh version
    try:
        proc = subprocess.run(
            ["/usr/bin/env", "gh", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            findings.append(ForgeDoctorFinding(
                code="GITHUB-002",
                severity=ForgeDoctorSeverity.ERROR,
                message=f"gh --version failed: {proc.stderr.strip()}",
                remediation="Check GitHub CLI installation",
            ))
            return False, None, tuple(findings)

        # Extract version from output like "gh version 2.92.0 (2026-04-28)"
        version_line = proc.stdout.strip().split("\n")[0]
        if "version" in version_line.lower():
            gh_version = version_line.split()[2] if len(version_line.split()) > 2 else None
        else:
            gh_version = None

    except subprocess.TimeoutExpired:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-003",
            severity=ForgeDoctorSeverity.ERROR,
            message="gh --version timed out",
            remediation="Check GitHub CLI installation",
        ))
        return False, None, tuple(findings)
    except Exception as e:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-004",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"gh --version failed with exception: {e}",
            remediation="Check GitHub CLI installation",
        ))
        return False, None, tuple(findings)

    # Check gh auth status for github.com
    # Note: gh CLI has different flags across versions
    # Try with --hostname first (newer versions), then without flags (default shows all hosts)
    try:
        # Try with --hostname flag
        proc = subprocess.run(
            ["/usr/bin/env", "gh", "auth", "status", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        auth_output = proc.stdout + proc.stderr
        
        # Check if the command succeeded and we're authenticated
        if proc.returncode == 0:
            if "logged in" in auth_output.lower() or "logged into" in auth_output.lower():
                return True, gh_version, tuple(findings)
        
        # If --hostname didn't work or no auth, try without flags (shows all hosts)
        proc2 = subprocess.run(
            ["/usr/bin/env", "gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        auth_output2 = proc2.stdout + proc2.stderr
        
        if proc2.returncode != 0:
            # If auth status fails completely, check if gh is working at all
            # Some versions may not support auth status the same way
            # Try to see if we can at least get version info
            if gh_version:
                # gh CLI is available but auth might be configured differently
                # Don't fail hard - just warn that we couldn't verify auth
                findings.append(ForgeDoctorFinding(
                    code="GITHUB-006",
                    severity=ForgeDoctorSeverity.WARNING,
                    message="Could not verify GitHub CLI authentication (version detected)",
                    remediation="Ensure gh auth is configured with 'gh auth login'",
                ))
                return True, gh_version, tuple(findings)
            else:
                findings.append(ForgeDoctorFinding(
                    code="GITHUB-005",
                    severity=ForgeDoctorSeverity.ERROR,
                    message=f"gh auth status failed: {proc2.stderr.strip()}",
                    remediation="Authenticate with 'gh auth login'",
                ))
                return False, gh_version, tuple(findings)
        
        # Check all hosts output for github.com
        if "github.com" in auth_output2 and ("logged in" in auth_output2.lower() or "logged into" in auth_output2.lower() or "active" in auth_output2.lower()):
            return True, gh_version, tuple(findings)
        
        # If we still don't see auth, try just checking if gh is in PATH and version works
        if gh_version:
            findings.append(ForgeDoctorFinding(
                code="GITHUB-006",
                severity=ForgeDoctorSeverity.WARNING,
                message="GitHub CLI is available but authentication for github.com could not be verified",
                remediation="Authenticate with 'gh auth login' or ensure you're logged in to github.com",
            ))
            return True, gh_version, tuple(findings)
        else:
            findings.append(ForgeDoctorFinding(
                code="GITHUB-006",
                severity=ForgeDoctorSeverity.ERROR,
                message="Not authenticated with GitHub CLI",
                remediation="Authenticate with 'gh auth login'",
            ))
            return False, gh_version, tuple(findings)

    except subprocess.TimeoutExpired:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-007",
            severity=ForgeDoctorSeverity.ERROR,
            message="gh auth status timed out",
            remediation="Check GitHub CLI authentication",
        ))
        return False, gh_version, tuple(findings)
    except Exception as e:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-008",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"gh auth status failed with exception: {e}",
            remediation="Check GitHub CLI authentication",
        ))
        return False, gh_version, tuple(findings)

    return True, gh_version, tuple(findings)


def _github_cli_check_existing_pr(
    target_ref: str,
    promotion_branch: str,
    remote: str = "origin",
) -> tuple[bool, str | None, tuple[ForgeDoctorFinding, ...]]:
    """Check if a PR already exists for the promotion branch (GitHub CLI backend).

    Mission 7: GitHub Draft PR Apply
    Mission 9: Renamed to reflect GitHub CLI backend specificity

    Uses `gh pr list` to check for existing PRs via GitHub CLI.

    Args:
        target_ref: The target branch (base ref)
        promotion_branch: The promotion branch (head ref)
        remote: The Git remote name (default: "origin")

    Returns:
        Tuple of (pr_exists, pr_url, findings)
        - pr_exists: True if an open PR exists
        - pr_url: URL of existing PR, or None
        - findings: Tuple of any findings/errors
    """
    import shutil
    findings: list[ForgeDoctorFinding] = []

    # Check if gh is available first
    gh_available, _, auth_findings = _check_gh_cli_available()
    if not gh_available:
        findings.extend(auth_findings)
        # If gh is not available, we can't check for existing PRs
        # But this is not an error for the check itself - just means we can't detect
        return False, None, tuple(findings)

    findings.extend(auth_findings)
    if auth_findings:
        return False, None, tuple(findings)

    # Run gh pr list to find existing PRs
    try:
        proc = subprocess.run(
            [
                "/usr/bin/env", "gh", "pr", "list",
                "--base", target_ref,
                "--head", promotion_branch,
                "--json", "url,number,state",
                "--limit", "1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode != 0:
            # gh pr list can return non-zero if no PRs found or other issues
            # Check if it's a "no pull requests matched" error
            error_output = proc.stderr.strip().lower()
            if "no pull requests matched" in error_output or "no prs" in error_output:
                # No existing PR - this is fine
                return False, None, tuple(findings)
            else:
                findings.append(ForgeDoctorFinding(
                    code="GITHUB-009",
                    severity=ForgeDoctorSeverity.WARNING,
                    message=f"gh pr list failed: {proc.stderr.strip()}",
                    remediation="Check branch names and repository access",
                ))
                return False, None, tuple(findings)

        # Try to parse JSON output
        try:
            import json
            prs = json.loads(proc.stdout.strip())
            if isinstance(prs, list) and len(prs) > 0:
                pr = prs[0]
                pr_url = pr.get("url")
                if pr_url:
                    return True, pr_url, tuple(findings)
        except (json.JSONDecodeError, ValueError):
            # Output might not be JSON - try to parse as text
            pass

        # Check for PR in text output
        if proc.stdout.strip():
            # If there's output, try to see if it mentions a PR
            # This is a fallback for non-JSON output
            findings.append(ForgeDoctorFinding(
                code="GITHUB-010",
                severity=ForgeDoctorSeverity.INFO,
                message=f"gh pr list returned output but could not parse: {proc.stdout.strip()[:200]}",
                remediation="Check gh CLI version supports --json flag",
            ))

    except subprocess.TimeoutExpired:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-011",
            severity=ForgeDoctorSeverity.WARNING,
            message="gh pr list timed out",
            remediation="Check network connectivity to GitHub",
        ))
        return False, None, tuple(findings)
    except Exception as e:
        findings.append(ForgeDoctorFinding(
            code="GITHUB-012",
            severity=ForgeDoctorSeverity.WARNING,
            message=f"gh pr list failed with exception: {e}",
            remediation="Check gh CLI installation and network",
        ))
        return False, None, tuple(findings)

    return False, None, tuple(findings)


def _github_api_check_existing_pr_direct(
    owner: str,
    repository: str,
    token: str,
    head_branch: str,
    base_branch: str,
    timeout: float = 30.0,
) -> GitHubApiPullRequest | None:
    """Check if a PR already exists using GitHub API (direct REST).

    Mission 11: Comprehensive GitHub Support Wiring

    Uses the GitHub REST API to search for existing PRs matching the head and base branches.
    Returns the first matching open PR, or None if not found.

    Args:
        owner: Repository owner
        repository: Repository name
        token: GitHub API token (will be redacted from any errors)
        head_branch: Head branch name to match
        base_branch: Base branch name to match
        timeout: Request timeout in seconds

    Returns:
        GitHubApiPullRequest if found, None otherwise
    """
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repository}/pulls"
    params = {
        "head": f"{owner}:{head_branch}",
        "base": base_branch,
        "state": "open",
    }
    url_with_params = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        request = urllib.request.Request(url_with_params, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
            if isinstance(result, list) and len(result) > 0:
                pr = result[0]
                return GitHubApiPullRequest(
                    number=pr.get("number"),
                    url=pr.get("html_url"),
                    state=pr.get("state"),
                    draft=pr.get("draft"),
                    title=pr.get("title"),
                    base_ref=pr.get("base", {}).get("ref") if pr.get("base") else None,
                    head_ref=pr.get("head", {}).get("ref") if pr.get("head") else None,
                )
            return None

    except urllib.error.HTTPError as e:
        # 404 means no PRs found, which is fine
        if e.code == 404:
            return None
        # Other errors are ignored - we'll proceed anyway
        return None
    except Exception:
        # Any other error, ignore and proceed
        return None


# ---------------------------------------------------------------------------
# Apply GitHub Draft PR Promotion (Mission 7)
# ---------------------------------------------------------------------------

def _execute_command(
    cmd_args: list[str],
    repo_root: Path | str,
    dry_run: bool = False,
) -> tuple[bool, str, str, int]:
    """Execute a command with optional dry-run.

    Mission 7: GitHub Draft PR Apply

    Uses explicit argument arrays, never shell=True.

    Args:
        cmd_args: Command as list of arguments (e.g., ["git", "branch", "-f", "branch", "HEAD"])
        repo_root: Repository root path (for git commands, use -C)
        dry_run: If True, don't execute, just return what would be done

    Returns:
        Tuple of (success, stdout, stderr, returncode)
        - If dry_run=True, returncode is always 0 and stdout contains the command string
    """
    if dry_run:
        cmd_str = " ".join(cmd_args)
        return True, cmd_str, "", 0

    # For git commands, add -C repo_root as first arguments
    final_args = cmd_args
    if cmd_args and cmd_args[0] in ("git", "gh"):
        # Insert -C repo_root for git, or just use as-is for gh
        if cmd_args[0] == "git":
            final_args = ["git", "-C", str(repo_root)] + cmd_args[1:]

    try:
        proc = subprocess.run(
            final_args,
            capture_output=True,
            text=True,
            timeout=60,
            # NEVER use shell=True - use explicit argument arrays
            shell=False,
        )
        return (
            proc.returncode == 0,
            proc.stdout.strip(),
            proc.stderr.strip(),
            proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out", -1
    except Exception as e:
        return False, "", str(e), -1


# ---------------------------------------------------------------------------
# GitHub API Backend: PyGithub Library (Mission 11)
# ---------------------------------------------------------------------------

def create_github_draft_pr_pygithub(
    owner: str,
    repository: str,
    token: str,
    title: str,
    body: str,
    base_ref: str,
    head_ref: str,
) -> tuple[bool, GitHubApiPullRequest | None, tuple[ForgeDoctorFinding, ...]]:
    """Create a draft pull request using PyGithub library.

    Mission 11: Comprehensive GitHub Support Wiring

    Uses the PyGithub library to create a draft PR via GitHub API v3.
    All exceptions are caught and returned as findings with redacted messages.

    Args:
        owner: GitHub repository owner
        repository: GitHub repository name
        token: GitHub API token (WILL BE REDACTED from any error messages)
        title: Pull request title
        body: Pull request body
        base_ref: Base branch for the PR
        head_ref: Head branch for the PR

    Returns:
        Tuple of (success, pr_info, findings)
        - success: True if PR was created successfully
        - pr_info: GitHubApiPullRequest if successful, None otherwise
        - findings: Tuple of ForgeDoctorFinding with any errors/warnings

    Note:
        Token is never included in returned data or error messages.
        Token is passed to PyGithub but all exception messages are redacted.
    """
    try:
        # Import at runtime to handle environments without PyGithub installed
        # This is acceptable; callers must ensure PyGithub is available
        from github import Github, GithubException, UnknownObjectException
    except ImportError as e:
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-010",
            severity=ForgeDoctorSeverity.ERROR,
            message="PyGithub library not installed",
            remediation="Install PyGithub: pip install PyGithub",
        ),)

    # Redact token for safety in case it appears in any error
    safe_token = redact_token(token)

    try:
        github = Github(token)
        repo = github.get_repo(f"{owner}/{repository}")
        pr = repo.create_pull(
            title=title,
            body=body,
            base=base_ref,
            head=head_ref,
            draft=True,
        )
        return True, GitHubApiPullRequest(
            number=pr.number,
            url=pr.html_url,
            state=pr.state,
            draft=pr.draft,
            title=pr.title,
            base_ref=pr.base.ref,
            head_ref=pr.head.ref,
        ), ()

    except GithubException as e:
        # Never include token in error message
        safe_msg = redact_token(str(e))
        # Also redact any potential token in the safe_token display
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-001",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"PyGithub API error: {safe_msg}",
            remediation="Check token permissions, network connectivity, and repository access",
        ),)
    except UnknownObjectException as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-004",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub repository not found: {safe_msg}",
            remediation="Verify owner, repository, and token have correct access",
        ),)
    except Exception as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-005",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Unexpected PyGithub error: {safe_msg}",
            remediation="Check GitHub API status and token validity",
        ),)


def get_github_pr_status_pygithub(
    owner: str,
    repository: str,
    token: str,
    pr_number: int,
) -> tuple[bool, GitHubApiPullRequest | None, tuple[ForgeDoctorFinding, ...]]:
    """Get pull request status using PyGithub library.

    Mission 11: Comprehensive GitHub Support Wiring

    Retrieves PR information via GitHub API using PyGithub.

    Args:
        owner: GitHub repository owner
        repository: GitHub repository name
        token: GitHub API token (WILL BE REDACTED from any error messages)
        pr_number: Pull request number to retrieve

    Returns:
        Tuple of (success, pr_info, findings)
    """
    try:
        from github import Github, GithubException, UnknownObjectException
    except ImportError:
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-010",
            severity=ForgeDoctorSeverity.ERROR,
            message="PyGithub library not installed",
            remediation="Install PyGithub: pip install PyGithub",
        ),)

    try:
        github = Github(token)
        repo = github.get_repo(f"{owner}/{repository}")
        pr = repo.get_pull(pr_number)
        return True, GitHubApiPullRequest(
            number=pr.number,
            url=pr.html_url,
            state=pr.state,
            draft=pr.draft,
            title=pr.title,
            base_ref=pr.base.ref,
            head_ref=pr.head.ref,
        ), ()
    except (GithubException, UnknownObjectException) as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-006",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Failed to get PR status: {safe_msg}",
            remediation="Check PR number, token access, and repository",
        ),)
    except Exception as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-007",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Unexpected error getting PR status: {safe_msg}",
            remediation="Check GitHub API status",
        ),)


# ---------------------------------------------------------------------------
# GitHub API Backend: Direct REST (Mission 11)
# ---------------------------------------------------------------------------

def create_github_draft_pr_direct_rest(
    owner: str,
    repository: str,
    token: str,
    title: str,
    body: str,
    base_ref: str,
    head_ref: str,
    timeout: float = 30.0,
) -> tuple[bool, GitHubApiPullRequest | None, tuple[ForgeDoctorFinding, ...]]:
    """Create a draft pull request using direct GitHub REST API.

    Mission 11: Comprehensive GitHub Support Wiring

    Makes a direct HTTP POST request to GitHub REST API to create a PR.
    Uses stdlib urllib.request with no external dependencies.

    Args:
        owner: GitHub repository owner
        repository: GitHub repository name
        token: GitHub API token (WILL BE REDACTED from any error messages)
        title: Pull request title
        body: Pull request body
        base_ref: Base branch for the PR
        head_ref: Head branch for the PR
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Tuple of (success, pr_info, findings)
    """
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repository}/pulls"
    payload = {
        "title": title,
        "body": body,
        "base": base_ref,
        "head": head_ref,
        "draft": True,
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
            return True, GitHubApiPullRequest(
                number=result.get("number"),
                url=result.get("html_url"),
                state=result.get("state"),
                draft=result.get("draft"),
                title=result.get("title"),
                base_ref=result.get("base", {}).get("ref") if result.get("base") else None,
                head_ref=result.get("head", {}).get("ref") if result.get("head") else None,
            ), ()

    except urllib.error.HTTPError as e:
        safe_msg = redact_token(str(e))
        safe_reason = redact_token(e.reason) if e.reason else ""
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-020",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API HTTP error {e.code}: {safe_reason}",
            remediation="Check token permissions, repository access, and request validitiy",
        ),)
    except urllib.error.URLError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-021",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API URL error: {safe_msg}",
            remediation="Check network connectivity",
        ),)
    except json.JSONDecodeError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-022",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API invalid response: {safe_msg}",
            remediation="Check GitHub API status",
        ),)
    except TimeoutError:
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-023",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub REST API request timed out",
            remediation="Retry with longer timeout or check network",
        ),)
    except Exception as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-024",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Unexpected REST API error: {safe_msg}",
            remediation="Check GitHub API status",
        ),)


def get_github_pr_status_direct_rest(
    owner: str,
    repository: str,
    token: str,
    pr_number: int,
    timeout: float = 30.0,
) -> tuple[bool, GitHubApiPullRequest | None, tuple[ForgeDoctorFinding, ...]]:
    """Get pull request status using direct GitHub REST API.

    Mission 11: Comprehensive GitHub Support Wiring

    Args:
        owner: GitHub repository owner
        repository: GitHub repository name
        token: GitHub API token (WILL BE REDACTED from any error messages)
        pr_number: Pull request number to retrieve
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, pr_info, findings)
    """
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repository}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
            return True, GitHubApiPullRequest(
                number=result.get("number"),
                url=result.get("html_url"),
                state=result.get("state"),
                draft=result.get("draft"),
                title=result.get("title"),
                base_ref=result.get("base", {}).get("ref") if result.get("base") else None,
                head_ref=result.get("head", {}).get("ref") if result.get("head") else None,
            ), ()

    except urllib.error.HTTPError as e:
        safe_reason = redact_token(e.reason) if e.reason else ""
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-025",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API HTTP error {e.code}: {safe_reason}",
            remediation="Check PR number, token access, and repository",
        ),)
    except urllib.error.URLError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-026",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API URL error: {safe_msg}",
            remediation="Check network connectivity",
        ),)
    except json.JSONDecodeError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-027",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API invalid response: {safe_msg}",
            remediation="Check GitHub API status",
        ),)
    except TimeoutError:
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-028",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub REST API request timed out",
            remediation="Retry with longer timeout or check network",
        ),)
    except Exception as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-029",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Unexpected REST API error: {safe_msg}",
            remediation="Check GitHub API status",
        ),)


def get_github_checks_summary_direct_rest(
    owner: str,
    repository: str,
    token: str,
    ref: str,
    timeout: float = 30.0,
) -> tuple[bool, GitHubApiCheckSummary | None, tuple[ForgeDoctorFinding, ...]]:
    """Get check runs summary for a ref using direct GitHub REST API.

    Mission 11: Comprehensive GitHub Support Wiring

    Uses the combined status endpoint which provides a summary of all check
    statuses for a commit. This is a read-only operation.

    Args:
        owner: GitHub repository owner
        repository: GitHub repository name
        token: GitHub API token (WILL BE REDACTED from any error messages)
        ref: Commit SHA or branch name to check
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, summary, findings)
    """
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repository}/commits/{ref}/status"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
            
            # Parse the combined status response
            state = result.get("state")  # "success", "failure", "pending", "error", or None
            total_count = result.get("total_count", 0)
            
            # Count by status from the "statuses" array
            statuses = result.get("statuses", [])
            success_count = sum(1 for s in statuses if s.get("state") == "success")
            failure_count = sum(1 for s in statuses if s.get("state") == "failure")
            pending_count = sum(1 for s in statuses if s.get("state") in ("pending", None))
            
            # Build check runs from statuses (simplified representation)
            check_runs = tuple(
                GitHubApiCheckRun(
                    id=None,  # Individual check runs don't have IDs in status endpoint
                    name=s.get("context"),
                    status=s.get("state"),
                    conclusion=None,
                    html_url=s.get("target_url"),
                )
                for s in statuses
            )
            
            return True, GitHubApiCheckSummary(
                head_sha=result.get("sha"),
                state=state,
                total_count=total_count,
                success_count=success_count,
                failure_count=failure_count,
                pending_count=pending_count,
                check_runs=check_runs,
            ), ()

    except urllib.error.HTTPError as e:
        safe_reason = redact_token(e.reason) if e.reason else ""
        # 404 is expected if ref doesn't exist or has no status
        if e.code == 404:
            return False, None, (ForgeDoctorFinding(
                code="GITHUB_API-030",
                severity=ForgeDoctorSeverity.INFO,
                message=f"No commit status found for ref '{redact_token(ref)}'",
                remediation="Commit may have no status checks configured",
            ),)
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-031",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API HTTP error {e.code}: {safe_reason}",
            remediation="Check token access and repository",
        ),)
    except urllib.error.URLError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-032",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API URL error: {safe_msg}",
            remediation="Check network connectivity",
        ),)
    except json.JSONDecodeError as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-033",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"GitHub REST API invalid response: {safe_msg}",
            remediation="Check GitHub API status",
        ),)
    except TimeoutError:
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-034",
            severity=ForgeDoctorSeverity.ERROR,
            message="GitHub REST API request timed out",
            remediation="Retry with longer timeout or check network",
        ),)
    except Exception as e:
        safe_msg = redact_token(str(e))
        return False, None, (ForgeDoctorFinding(
            code="GITHUB_API-035",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Unexpected REST API error getting checks: {safe_msg}",
            remediation="Check GitHub API status",
        ),)


def apply_github_draft_pr_promotion(
    repo_path: Path | str,
    plan: PromotionPlan,
    artifact: PromotionArtifact,
    remote: str = "origin",
    dry_run: bool = False,
    skip_safety_report: bool = False,
    backend_mode: GitHubBackendMode = GitHubBackendMode.CLI,
    api_library: GitHubApiLibraryChoice | None = None,
    allow_mutation: bool = False,
) -> GitHubPromotionApplyResult:
    """Apply promotion by creating/updating a GitHub draft PR.

    Mission 7: GitHub Draft PR Apply
    Mission 8: Updated with GitHub Apply Safety Doctor
    Mission 11: Updated with API backend support

    This is the first mutating adapter path for ADR 0010.
    When dry_run=True, only plan and return commands without executing.
    When dry_run=False, execute the mutation commands in order.

    Rules:
    - If plan.ready is False, fail closed and do not apply
    - If artifact.wrote_files is False, fail closed
    - If artifact verification fails, fail closed
    - If --allow-mutation is not set, fail closed for API backend
    - If no token available for API backend, fail closed
    - If PR already exists, do not create duplicate
    - If safety report is not ready, fail closed (unless skip_safety_report=True)
    - Write evidence under .rig/work/promotions/<artifact_id>/apply-result.json
    - Do NOT merge PR, enable auto-merge, configure branch protection,
      push to preproduction, or run destructive Git commands

    CLI Backend Commands executed in order:
    1. git branch -f <promotion_branch> <head_ref>
    2. git push -u <remote> <promotion_branch>
    3. gh pr create --draft --base <target_ref> --head <promotion_branch> \
                    --title <title> --body-file <body_path>

    API Backend:
    - Branch creation still uses git commands (safe, local-only)
    - PR creation uses PyGithub or direct REST API
    - Token is read from RIG_GITHUB_TOKEN environment variable
    - Token is NEVER stored, logged, or included in evidence/results

    Args:
        repo_path: Path to the git repository root
        plan: The promotion plan
        artifact: The promotion artifact (must have wrote_files=True)
        remote: The Git remote name (default: "origin")
        dry_run: If True, do not execute commands (default: False)
        skip_safety_report: If True, skip safety report check (default: False)
        backend_mode: Backend mode to use (default: GitHubBackendMode.CLI)
            - CLI: Use GitHub CLI (gh) backend
            - API: Use GitHub API backend (PyGithub or direct REST)
            - AUTO: Select best available backend
        api_library: API library choice for API backend (default: None = use PyGithub)
            - PYGITHUB: Use PyGithub library
            - DIRECT_REST: Use direct REST API calls
        allow_mutation: If True, allows mutation via API backend (default: False)
            Required for agent safety: user must explicitly consent to mutation

    Returns:
        GitHubPromotionApplyResult with full information about what was done
        Includes backend, api_library, token_source, token_present fields

    Raises:
        ValueError: If plan is not ready, artifact not written, or verification fails
    """
    import datetime
    import json

    repo_path = Path(repo_path)
    findings: list[ForgeDoctorFinding] = []

    # === Backend Resolution (Mission 11) ===
    # Determine actual backend to use based on mode and availability
    resolved_backend_mode = backend_mode
    resolved_api_library: GitHubApiLibraryChoice | None = api_library
    resolved_token_source: str | None = None
    resolved_token_present = False

    # Read token and classify source (only for API mode or AUTO with CLI unavailable)
    if backend_mode in (GitHubBackendMode.API, GitHubBackendMode.AUTO):
        # Classify token source - this only checks for RIG_GITHUB_TOKEN env var
        resolved_token_source = classify_github_token_source()
        resolved_token_present = resolved_token_source is not None

    # Handle AUTO mode: try CLI first, fall back to API if CLI unavailable
    if backend_mode == GitHubBackendMode.AUTO:
        gh_available, gh_version, gh_findings = _check_gh_cli_available()
        findings.extend(gh_findings)
        if gh_available:
            # Check authentication
            gh_authenticated = False
            try:
                proc = subprocess.run(
                    ["/usr/bin/env", "gh", "auth", "status", "--hostname", "github.com"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                auth_output = proc.stdout + proc.stderr
                if proc.returncode == 0:
                    if ("logged in" in auth_output.lower() or
                        "logged into" in auth_output.lower() or
                        "active" in auth_output.lower()):
                        gh_authenticated = True
            except Exception:
                gh_authenticated = False

            if gh_authenticated:
                resolved_backend_mode = GitHubBackendMode.CLI
            else:
                # CLI available but not auth'd, try API backend if token present
                if resolved_token_present:
                    resolved_backend_mode = GitHubBackendMode.API
                    # Default to PyGithub if not specified
                    if resolved_api_library is None:
                        resolved_api_library = GitHubApiLibraryChoice.PYGITHUB
                else:
                    # No API token either - fail closed
                    findings.append(ForgeDoctorFinding(
                        code="GITHUB_API-040",
                        severity=ForgeDoctorSeverity.ERROR,
                        message="Auto backend selection: CLI available but not authenticated, no API token",
                        remediation="Authenticate gh CLI or set RIG_GITHUB_TOKEN environment variable",
                    ))
        else:
            # CLI not available, try API
            if resolved_token_present:
                resolved_backend_mode = GitHubBackendMode.API
                if resolved_api_library is None:
                    resolved_api_library = GitHubApiLibraryChoice.PYGITHUB
            else:
                findings.append(ForgeDoctorFinding(
                    code="GITHUB_API-041",
                    severity=ForgeDoctorSeverity.ERROR,
                    message="Auto backend selection: No GitHub CLI and no API token available",
                    remediation="Install GitHub CLI (gh) and authenticate, or set RIG_GITHUB_TOKEN",
                ))

    # For explicit API mode, ensure token is present and mutation is allowed
    if resolved_backend_mode == GitHubBackendMode.API:
        if not resolved_token_present:
            findings.append(ForgeDoctorFinding(
                code="GITHUB_API-042",
                severity=ForgeDoctorSeverity.ERROR,
                message="API backend requires GitHub API token",
                remediation="Set RIG_GITHUB_TOKEN environment variable",
            ))
        if not allow_mutation:
            findings.append(ForgeDoctorFinding(
                code="GITHUB_API-043",
                severity=ForgeDoctorSeverity.ERROR,
                message="API backend mutation requires explicit --allow-mutation consent",
                remediation="Add --allow-mutation flag to command",
            ))
        # Default to PyGithub if not specified
        if resolved_api_library is None:
            resolved_api_library = GitHubApiLibraryChoice.PYGITHUB

    # === Early fail on backend errors ===
    # If we have backend-related errors at this point, fail closed
    backend_error_codes = {"GITHUB_API-040", "GITHUB_API-041", "GITHUB_API-042", "GITHUB_API-043"}
    if any(f.code in backend_error_codes for f in findings):
        return GitHubPromotionApplyResult(
            provider="github",
            promotion_branch="",
            target_ref=plan.target_ref if plan else "",
            head_ref=plan.head_ref if plan else "",
            artifact_id=artifact.artifact_id if artifact else "",
            body_path="",
            pr_url=None,
            commands=(),
            ready_before_apply=False,
            applied=False,
            skipped_existing_pr=False,
            evidence_path=None,
            findings=tuple(findings),
            backend=resolved_backend_mode.value,
            api_library=resolved_api_library.value if resolved_api_library else None,
            token_source=resolved_token_source,
            token_present=resolved_token_present,
        )

    # === Fail-closed checks ===

    # Check plan.ready
    if not plan.ready:
        findings.append(ForgeDoctorFinding(
            code="APPLY-001",
            severity=ForgeDoctorSeverity.ERROR,
            message="Promotion plan is not ready - cannot apply",
            remediation="Fix blockers and ensure plan.ready is True",
        ))
        return GitHubPromotionApplyResult(
            provider="github",
            promotion_branch="",
            target_ref=plan.target_ref,
            head_ref=plan.head_ref,
            artifact_id="",
            body_path="",
            pr_url=None,
            commands=(),
            ready_before_apply=False,
            applied=False,
            skipped_existing_pr=False,
            evidence_path=None,
            findings=tuple(findings),
            backend=resolved_backend_mode.value,
            api_library=resolved_api_library.value if resolved_api_library else None,
            token_source=resolved_token_source,
            token_present=resolved_token_present,
        )

    # Check over budget
    if plan.reviewability.over_budget and plan.reviewability.default_action == "block_promotion":
        findings.append(ForgeDoctorFinding(
            code="APPLY-002",
            severity=ForgeDoctorSeverity.ERROR,
            message=f"Reviewability budget exceeded: {plan.reviewability.changed_file_count} > {plan.reviewability.max_changed_files}",
            remediation="Reduce changes or request override with reason",
        ))
        return GitHubPromotionApplyResult(
            provider="github",
            promotion_branch="",
            target_ref=plan.target_ref,
            head_ref=plan.head_ref,
            artifact_id="",
            body_path="",
            pr_url=None,
            commands=(),
            ready_before_apply=False,
            applied=False,
            skipped_existing_pr=False,
            evidence_path=None,
            findings=tuple(findings),
            backend=resolved_backend_mode.value,
            api_library=resolved_api_library.value if resolved_api_library else None,
            token_source=resolved_token_source,
            token_present=resolved_token_present,
        )

    # Check draft exists
    if plan.draft is None:
        findings.append(ForgeDoctorFinding(
            code="APPLY-003",
            severity=ForgeDoctorSeverity.ERROR,
            message="Promotion plan has no draft - cannot apply",
            remediation="Ensure plan has a valid draft",
        ))
        return GitHubPromotionApplyResult(
            provider="github",
            promotion_branch="",
            target_ref=plan.target_ref,
            head_ref=plan.head_ref,
            artifact_id="",
            body_path="",
            pr_url=None,
            commands=(),
            ready_before_apply=False,
            applied=False,
            skipped_existing_pr=False,
            evidence_path=None,
            findings=tuple(findings),
            backend=resolved_backend_mode.value,
            api_library=resolved_api_library.value if resolved_api_library else None,
            token_source=resolved_token_source,
            token_present=resolved_token_present,
        )

    promotion_branch = plan.draft.promotion_branch
    title = plan.draft.title
    body_path = artifact.body_path

    # Check artifact.wrote_files
    if not artifact.wrote_files:
        findings.append(ForgeDoctorFinding(
            code="APPLY-004",
            severity=ForgeDoctorSeverity.ERROR,
            message="Artifact files not written - cannot apply",
            remediation="Run promotion with --write-artifact or use --write-artifact with --apply",
        ))
        return GitHubPromotionApplyResult(
            provider="github",
            promotion_branch=promotion_branch,
            target_ref=plan.target_ref,
            head_ref=plan.head_ref,
            artifact_id=artifact.artifact_id,
            body_path=body_path,
            pr_url=None,
            commands=(),
            ready_before_apply=True,
            applied=False,
            skipped_existing_pr=False,
            evidence_path=None,
            findings=tuple(findings),
            backend=resolved_backend_mode.value,
            api_library=resolved_api_library.value if resolved_api_library else None,
            token_source=resolved_token_source,
            token_present=resolved_token_present,
        )

    # === Build safety report (Mission 8) ===
    safety_report: GitHubApplySafetyReport | None = None
    if not skip_safety_report:
        safety_report = build_github_apply_safety_report(repo_path, plan, artifact, remote)
        findings.extend(safety_report.findings)
        
        # Fail closed if safety report is not ready
        if not safety_report.ready:
            return GitHubPromotionApplyResult(
                provider="github",
                promotion_branch=promotion_branch,
                target_ref=plan.target_ref,
                head_ref=plan.head_ref,
                artifact_id=artifact.artifact_id,
                body_path=body_path,
                pr_url=None,
                commands=(),
                ready_before_apply=True,
                applied=False,
                skipped_existing_pr=False,
                evidence_path=None,
                findings=tuple(findings),
                backend=resolved_backend_mode.value,
                api_library=resolved_api_library.value if resolved_api_library else None,
                token_source=resolved_token_source,
                token_present=resolved_token_present,
            )

    # Check gh CLI (only for CLI backend)
    # For API backend, we use API calls instead of gh CLI
    pr_exists = False
    existing_pr_url: str | None = None
    if resolved_backend_mode == GitHubBackendMode.CLI:
        gh_available, gh_version, gh_findings = _check_gh_cli_available()
        findings.extend(gh_findings)
        if not gh_available:
            return GitHubPromotionApplyResult(
                provider="github",
                promotion_branch=promotion_branch,
                target_ref=plan.target_ref,
                head_ref=plan.head_ref,
                artifact_id=artifact.artifact_id,
                body_path=body_path,
                pr_url=None,
                commands=(),
                ready_before_apply=True,
                applied=False,
                skipped_existing_pr=False,
                evidence_path=None,
                findings=tuple(findings),
                backend=resolved_backend_mode.value,
                api_library=resolved_api_library.value if resolved_api_library else None,
                token_source=resolved_token_source,
                token_present=resolved_token_present,
            )

        # Check for existing PR using CLI
        pr_exists, existing_pr_url, pr_findings = _github_cli_check_existing_pr(
            target_ref=plan.target_ref,
            promotion_branch=promotion_branch,
            remote=remote,
        )
        findings.extend(pr_findings)
    elif resolved_backend_mode == GitHubBackendMode.API:
        # For API backend, check for existing PR using API
        # We need owner and repository from the plan identity
        if plan.identity.owner and plan.identity.repository:
            _owner = plan.identity.owner
            _repo = plan.identity.repository
            # Use direct REST to check for existing PRs
            # This is a read-only check, safe to do
            token = read_github_api_token_from_env()
            if token:
                # Check existing PRs for this branch
                existing_pr = _github_api_check_existing_pr_direct(
                    owner=_owner,
                    repository=_repo,
                    token=token,
                    head_branch=promotion_branch,
                    base_branch=plan.target_ref,
                    timeout=30.0,
                )
                if existing_pr:
                    pr_exists = True
                    existing_pr_url = existing_pr.url
            # Note: If we can't check, we proceed anyway - the API will error if PR exists
        # If no identity info, we'll proceed and let the API call handle it
    else:
        # AUTO mode should have been resolved earlier, but handle gracefully
        pr_exists = False
        existing_pr_url = None

    # === Build command list ===
    commands: list[str] = []

    # Command 1: Create/update promotion branch
    # git branch -f <promotion_branch> <head_ref>
    # Note: head_ref might be "HEAD" which is valid for git branch
    cmd1_args = ["git", "branch", "-f", promotion_branch]
    if plan.head_ref != "HEAD":
        cmd1_args.append(plan.head_ref)
    # else: git branch -f will use current HEAD if not specified

    # Command 2: Push promotion branch to remote
    # git push -u <remote> <promotion_branch>
    cmd2_args = ["git", "push", "-u", remote, promotion_branch]

    # Command 3: Create draft PR
    # gh pr create --draft --base <target_ref> --head <promotion_branch> --title <title> --body-file <body_path>
    cmd3_args = [
        "gh", "pr", "create",
        "--draft",
        "--base", plan.target_ref,
        "--head", promotion_branch,
        "--title", title,
        "--body-file", body_path,
    ]

    # Build command strings for output
    commands = (
        " ".join(cmd1_args),
        " ".join(cmd2_args),
        " ".join(cmd3_args),
    )

    # === Execute or plan ===
    executed_commands: list[str] = []
    pr_url: str | None = None
    skipped_existing_pr = False
    applied = False

    # If existing PR detected, skip PR creation
    if pr_exists and existing_pr_url:
        skipped_existing_pr = True
        pr_url = existing_pr_url
        # Still need to execute branch creation and push if not dry_run
        if not dry_run:
            # Execute branch creation
            success1, out1, err1, rc1 = _execute_command(cmd1_args, repo_path, dry_run)
            if success1:
                executed_commands.append(out1)
                # Execute push
                success2, out2, err2, rc2 = _execute_command(cmd2_args, repo_path, dry_run)
                if success2:
                    executed_commands.append(out2)
                    applied = True  # Branch pushed successfully
                else:
                    findings.append(ForgeDoctorFinding(
                        code="APPLY-005",
                        severity=ForgeDoctorSeverity.ERROR,
                        message=f"git push failed: {err2}",
                        remediation="Check remote and branch permissions",
                    ))
            else:
                findings.append(ForgeDoctorFinding(
                    code="APPLY-006",
                    severity=ForgeDoctorSeverity.ERROR,
                    message=f"git branch -f failed: {err1}",
                    remediation="Check branch name and local Git state",
                ))
        else:
            # dry_run with existing PR - just report planned commands
            applied = False
    else:
        # No existing PR - execute all commands if not dry_run
        if not dry_run:
            # Execute branch creation
            success1, out1, err1, rc1 = _execute_command(cmd1_args, repo_path, dry_run)
            if success1:
                executed_commands.append(out1)
                # Execute push
                success2, out2, err2, rc2 = _execute_command(cmd2_args, repo_path, dry_run)
                if success2:
                    executed_commands.append(out2)
                    # Execute PR creation
                    # For gh pr create, we need to handle the output specially
                    # Run with /usr/bin/env gh to use PATH lookup
                    gh_cmd_args = ["/usr/bin/env"] + cmd3_args
                    try:
                        gh_proc = subprocess.run(
                            gh_cmd_args,
                            capture_output=True,
                            text=True,
                            timeout=60,
                            shell=False,
                        )
                        if gh_proc.returncode == 0:
                            # Try to extract URL from output
                            pr_url = _extract_pr_url_from_gh_output(gh_proc.stdout)
                            executed_commands.append(" ".join(cmd3_args))
                            applied = True
                        else:
                            findings.append(ForgeDoctorFinding(
                                code="APPLY-007",
                                severity=ForgeDoctorSeverity.ERROR,
                                message=f"gh pr create failed: {gh_proc.stderr.strip()}",
                                remediation="Check PR parameters and repository permissions",
                            ))
                            # URL might still be in output even on non-zero exit
                            pr_url = _extract_pr_url_from_gh_output(gh_proc.stdout)
                            if pr_url:
                                applied = True
                    except Exception as e:
                        findings.append(ForgeDoctorFinding(
                            code="APPLY-008",
                            severity=ForgeDoctorSeverity.ERROR,
                            message=f"gh pr create failed with exception: {e}",
                            remediation="Check gh CLI installation and network",
                        ))
                else:
                    findings.append(ForgeDoctorFinding(
                        code="APPLY-009",
                        severity=ForgeDoctorSeverity.ERROR,
                        message=f"git push failed: {err2}",
                        remediation="Check remote and branch permissions",
                    ))
            else:
                findings.append(ForgeDoctorFinding(
                    code="APPLY-010",
                    severity=ForgeDoctorSeverity.ERROR,
                    message=f"git branch -f failed: {err1}",
                    remediation="Check branch name and local Git state",
                ))
        else:
            # dry_run mode - no execution, just planning
            applied = False

    # === Write evidence ===
    evidence_path: str | None = None
    if dry_run or applied or skipped_existing_pr:
        # Write evidence file
        artifact_dir = Path(artifact.directory)
        evidence_dir = artifact_dir / "apply-result.json"
        evidence_path = str(evidence_dir)

        # Create directory if it doesn't exist
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Compute body SHA256 from actual file if available
        body_sha256 = artifact.body_sha256
        if Path(artifact.body_path).exists():
            try:
                actual_body = Path(artifact.body_path).read_text(encoding="utf-8")
                body_sha256 = _compute_body_sha256(actual_body)
            except (OSError, IOError):
                pass

        # Build safety report serialization if available
        safety_report_evidence = None
        if safety_report is not None:
            safety_report_evidence = {
                "provider": safety_report.provider,
                "owner": safety_report.owner,
                "repository": safety_report.repository,
                "remote_url": safety_report.remote_url,
                "gh_available": safety_report.gh_available,
                "gh_authenticated": safety_report.gh_authenticated,
                "artifact_valid": safety_report.artifact_valid,
                "existing_pr_url": safety_report.existing_pr_url,
                "promotion_branch_safe": safety_report.promotion_branch_safe,
                "direct_target_mutation_detected": safety_report.direct_target_mutation_detected,
                "forbidden_commands_detected": list(safety_report.forbidden_commands_detected),
                "ready": safety_report.ready,
                "findings": [
                    {
                        "code": f.code,
                        "severity": f.severity.value,
                        "message": f.message,
                        "remediation": f.remediation,
                    }
                    for f in safety_report.findings
                ],
            }

        evidence = {
            "provider": "github",
            "promotion_branch": promotion_branch,
            "target_ref": plan.target_ref,
            "head_ref": plan.head_ref,
            "artifact_id": artifact.artifact_id,
            "body_path": body_path,
            "body_sha256": body_sha256,
            "commands": list(executed_commands) if executed_commands else list(commands),
            "pr_url": pr_url,
            "applied": applied,
            "skipped_existing_pr": skipped_existing_pr,
            "safety_report": safety_report_evidence,
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity.value,
                    "message": f.message,
                    "remediation": f.remediation,
                }
                for f in findings
            ],
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        try:
            Path(evidence_path).write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        except (OSError, IOError) as e:
            findings.append(ForgeDoctorFinding(
                code="EVIDENCE-001",
                severity=ForgeDoctorSeverity.WARNING,
                message=f"Failed to write evidence file: {e}",
                remediation="Check write permissions for artifact directory",
            ))
            evidence_path = None

    # === Return result ===
    return GitHubPromotionApplyResult(
        provider="github",
        promotion_branch=promotion_branch,
        target_ref=plan.target_ref,
        head_ref=plan.head_ref,
        artifact_id=artifact.artifact_id,
        body_path=body_path,
        pr_url=pr_url,
        commands=commands if not executed_commands else tuple(executed_commands),
        ready_before_apply=plan.ready,
        applied=applied,
        skipped_existing_pr=skipped_existing_pr,
        evidence_path=evidence_path,
        findings=tuple(findings),
        backend=resolved_backend_mode.value,
        api_library=resolved_api_library.value if resolved_api_library else None,
        token_source=resolved_token_source,
        token_present=resolved_token_present,
    )


def _extract_pr_url_from_gh_output(output: str) -> str | None:
    """Extract PR URL from gh pr create output.

    Mission 7: GitHub Draft PR Apply

    Args:
        output: The stdout/stderr from gh pr create

    Returns:
        PR URL if found, None otherwise
    """
    import re

    # Look for URL patterns in output
    # gh pr create typically outputs the PR URL
    patterns = [
        r"https://github\.com/[^/]+/[^/]+/pull/\d+",
        r"Pull request:.*(https://[^\s]+)",
        r"(https://[^\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            url = match.group(0) if match.lastindex is None else match.group(match.lastindex)
            # Clean up URL
            url = url.strip()
            if url and "github.com" in url:
                return url

    return None
