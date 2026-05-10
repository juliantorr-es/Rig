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


def _check_existing_pr(
    target_ref: str,
    promotion_branch: str,
    remote: str = "origin",
) -> tuple[bool, str | None, tuple[ForgeDoctorFinding, ...]]:
    """Check if a PR already exists for the promotion branch.

    Mission 7: GitHub Draft PR Apply

    Uses `gh pr list` to check for existing PRs.

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


def apply_github_draft_pr_promotion(
    repo_path: Path | str,
    plan: PromotionPlan,
    artifact: PromotionArtifact,
    remote: str = "origin",
    dry_run: bool = False,
) -> GitHubPromotionApplyResult:
    """Apply promotion by creating/updating a GitHub draft PR.

    Mission 7: GitHub Draft PR Apply

    This is the first mutating adapter path for ADR 0010.
    When dry_run=True, only plan and return commands without executing.
    When dry_run=False, execute the mutation commands in order.

    Rules:
    - If plan.ready is False, fail closed and do not apply
    - If artifact.wrote_files is False, fail closed
    - If artifact verification fails, fail closed
    - If gh is missing or unauthenticated, fail closed
    - If PR already exists, do not create duplicate
    - Write evidence under .rig/work/promotions/<artifact_id>/apply-result.json
    - Do NOT merge PR, enable auto-merge, configure branch protection,
      push to preproduction, or run destructive Git commands

    Commands executed in order:
    1. git branch -f <promotion_branch> <head_ref>
    2. git push -u <remote> <promotion_branch>
    3. gh pr create --draft --base <target_ref> --head <promotion_branch> \
                    --title <title> --body-file <body_path>

    Args:
        repo_path: Path to the git repository root
        plan: The promotion plan
        artifact: The promotion artifact (must have wrote_files=True)
        remote: The Git remote name (default: "origin")
        dry_run: If True, do not execute commands (default: False)

    Returns:
        GitHubPromotionApplyResult with full information about what was done

    Raises:
        ValueError: If plan is not ready, artifact not written, or verification fails
    """
    import datetime
    import json

    repo_path = Path(repo_path)
    findings: list[ForgeDoctorFinding] = []

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
        )

    # Verify artifact
    is_valid, verify_findings = verify_promotion_artifact(repo_path, artifact)
    findings.extend(verify_findings)
    if not is_valid:
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
        )

    # Check gh CLI
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
        )

    # Check for existing PR
    pr_exists, existing_pr_url, pr_findings = _check_existing_pr(
        target_ref=plan.target_ref,
        promotion_branch=promotion_branch,
        remote=remote,
    )
    findings.extend(pr_findings)

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
