"""
Base VCS Backend implementation for rig_tools.

This is the implementation-layer abstract base that concrete VCS backends
inherits from. It provides common functionality and enforces the interface
that all VCS backends must implement.
"""

from __future__ import annotations

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rig_tools.core import get_tracer, trace_context, add_breadcrumbs, run_check, TimeoutError
from rig_tools.core.errors import RigError, RigNotFoundError, RigProcessError

logger = logging.getLogger(__name__)


class VCSBackendError(RigError):
    """Base error for VCS backend operations."""
    pass


class VCSNotFoundError(RigNotFoundError):
    """Raised when a VCS repository is not found."""
    def __init__(self, repo_path: str | Path):
        path_str = str(repo_path) if isinstance(repo_path, Path) else repo_path
        super().__init__(
            f"VCS repository not found at '{path_str}'",
            code="VCS_NOT_FOUND",
            resource_type="VCS repository",
            resource_id=path_str,
        )


class VCSCommandError(RigProcessError):
    """Raised when a VCS command fails."""
    pass


class VCSBackend(ABC):
    """
    Abstract base class for VCS backend implementations.
    
    All concrete VCS backends (Git, etc.) must inherit from
    this class and implement the required methods.
    
    This is the implementation-layer contract, while VCSBackend (Protocol)
    in the domain layer would be the public interface.
    """
    
    backend_id: str = ""  # e.g., "git"
    display_name: str = ""  # Human-readable name
    command_name: str = ""  # CLI command name (e.g., "git")
    
    def __init__(self, repo_path: Path | str | None = None):
        """
        Initialize the VCS backend.
        
        Args:
            repo_path: Path to the repository (defaults to current directory)
        """
        if repo_path is None:
            repo_path = Path.cwd()
        
        self._repo_path = Path(repo_path).resolve()
        self._tracer = get_tracer("vcs_backend")
    
    @property
    def repo_path(self) -> Path:
        """Get the repository path."""
        return self._repo_path
    
    @property
    def is_available(self) -> bool:
        """Check if this VCS backend is available."""
        return self._check_command_available()
    
    def _check_command_available(self) -> bool:
        """Check if the VCS command is available on the PATH."""
        import shutil
        return shutil.which(self.command_name) is not None
    
    def _run_cmd(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str] | str:
        """
        Run a VCS command with tracing and error handling.
        
        Args:
            args: Command arguments (not including the VCS command itself)
            cwd: Working directory (defaults to repo_path)
            capture: Whether to capture output
            check: Whether to raise on non-zero exit
            timeout: Command timeout in seconds
            **kwargs: Additional subprocess arguments
            
        Returns:
            CompletedProcess or output string
            
        Raises:
            VCSCommandError: If the command fails and check=True
            TimeoutError: If the command times out
        """
        cmd = [self.command_name] + args
        cwd = cwd or self._repo_path
        
        span_name = f"vcs.{self.backend_id}.{'_'.join(args[:2])}"
        
        with trace_context(span_name, category="vcs", cwd=str(cwd)) as span:
            try:
                result = run_check(
                    cmd,
                    cwd=cwd,
                    timeout=timeout,
                    capture=capture,
                    text=True,
                )
                
                if capture:
                    output = result.stdout
                    if result.stderr:
                        span.add_breadcrumb("stderr", content=result.stderr[:500])
                    return output if capture else result
                return result
                
            except TimeoutError as e:
                span.add_error(e)
                raise VCSCommandError(
                    f"VCS command timed out: {' '.join(cmd)}",
                    code="VCS_TIMEOUT",
                    context={"command": cmd, "cwd": str(cwd)},
                ) from e
            except subprocess.CalledProcessError as e:
                span.add_error(e)
                raise VCSCommandError(
                    f"VCS command failed: {' '.join(cmd)}",
                    code="VCS_COMMAND_FAILED",
                    context={"command": cmd, "cwd": str(cwd)},
                    stdout=e.stdout if e.stdout else None,
                    stderr=e.stderr if e.stderr else None,
                    returncode=e.returncode,
                ) from e
    
    def _run_git_cmd(self, *args: Any, **kwargs: Any) -> Any:
        """Shorthand for running git commands."""
        return self._run_cmd(list(args), **kwargs)
    
    # =========================================================================
    # Repository Operations
    # =========================================================================
    
    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Get repository status."""
        pass
    
    @abstractmethod
    def is_repo(self, path: Path | None = None) -> bool:
        """Check if a path is a VCS repository."""
        pass
    
    @abstractmethod
    def init(self, path: Path | None = None, bare: bool = False) -> None:
        """Initialize a new repository."""
        pass
    
    @abstractmethod
    def clone(
        self,
        url: str,
        to_path: Path | str | None = None,
        *,
        depth: int | None = None,
        branch: str | None = None,
    ) -> Path:
        """Clone a repository."""
        pass
    
    # =========================================================================
    # Branch Operations
    # =========================================================================
    
    @abstractmethod
    def get_current_branch(self) -> str:
        """Get the current branch name."""
        pass
    
    @abstractmethod
    def list_branches(self, remote: bool = False) -> list[str]:
        """List branches in the repository."""
        pass
    
    @abstractmethod
    def create_branch(self, name: str, from_branch: str | None = None) -> None:
        """Create a new branch."""
        pass
    
    @abstractmethod
    def checkout(self, ref: str, create: bool = False) -> None:
        """Checkout a branch or tag."""
        pass
    
    # =========================================================================
    # Commit Operations
    # =========================================================================
    
    @abstractmethod
    def get_head_commit(self) -> dict[str, Any]:
        """Get the current HEAD commit."""
        pass
    
    @abstractmethod
    def log(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get commit log."""
        pass
    
    @abstractmethod
    def diff(
        self,
        ref1: str | None = None,
        ref2: str | None = None,
        *,
        staged: bool = False,
    ) -> str:
        """Get diff between references."""
        pass
    
    @abstractmethod
    def add(self, paths: list[str | Path], all: bool = False) -> None:
        """Stage files for commit."""
        pass
    
    @abstractmethod
    def commit(
        self,
        message: str,
        *,
        all: bool = False,
        amend: bool = False,
        no_verify: bool = False,
    ) -> str:
        """Commit staged changes."""
        pass
    
    # =========================================================================
    # Remote Operations
    # =========================================================================
    
    @abstractmethod
    def list_remotes(self) -> list[dict[str, Any]]:
        """List configured remotes."""
        pass
    
    @abstractmethod
    def add_remote(self, name: str, url: str) -> None:
        """Add a remote."""
        pass
    
    @abstractmethod
    def fetch(
        self,
        *,
        remote: str | None = None,
        all: bool = False,
        prune: bool = False,
    ) -> None:
        """Fetch from remote(s)."""
        pass
    
    @abstractmethod
    def pull(
        self,
        *,
        remote: str | None = None,
        branch: str | None = None,
        rebase: bool = False,
    ) -> None:
        """Pull from remote."""
        pass
    
    @abstractmethod
    def push(
        self,
        *,
        remote: str | None = None,
        branch: str | None = None,
        force: bool = False,
    ) -> None:
        """Push to remote."""
        pass
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def resolve_ref(self, ref: str) -> str:
        """Resolve a reference to its actual commit hash."""
        try:
            result = self._run_cmd(["rev-parse", ref])
            return result.strip()
        except Exception:
            return ref
    
    def get_file_content(self, ref: str, path: str) -> str:
        """Get the content of a file at a specific reference."""
        return self._run_cmd(["show", f"{ref}:{path}"])
    
    def list_files(
        self,
        ref: str | None = None,
        path: str | Path | None = None,
        recursive: bool = True,
    ) -> list[str]:
        """List files in the repository at a specific reference."""
        args = ["ls-tree"].copy()
        if recursive:
            args.append("-r")
        if ref:
            args.extend(["--name-only", ref])
        else:
            args.append("--name-only")
        if path:
            args.append(str(path))
        
        try:
            result = self._run_cmd(args)
            return [line.strip() for line in result.splitlines() if line.strip()]
        except Exception:
            return []
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(backend={self.backend_id!r}, repo={self._repo_path!r})>"


class GitBackend(VCSBackend):
    """
    Git VCS backend implementation.
    
    This is the primary VCS backend for rig_tools, implementing Git operations.
    """
    
    backend_id = "git"
    display_name = "Git"
    command_name = "git"
    
    def __init__(self, repo_path: Path | str | None = None):
        """
        Initialize Git backend.
        
        Args:
            repo_path: Path to the Git repository
        """
        super().__init__(repo_path)
        
        # Verify repository exists
        if not self.is_repo():
            raise VCSNotFoundError(self._repo_path)
    
    def status(self) -> dict[str, Any]:
        """Get repository status."""
        try:
            # Get current branch
            current_branch = self.get_current_branch()
            
            # Get HEAD commit
            head_commit = self.get_head_commit()
            
            # Get status (modified files)
            status_output = self._run_git_cmd("status", "--porcelain")
            
            # Parse status output
            modified = []
            staged = []
            untracked = []
            
            for line in status_output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    status_code = parts[0]
                    file_path = parts[1]
                    
                    if status_code.startswith("M"):
                        modified.append(file_path)
                    elif status_code.startswith("A"):
                        staged.append(file_path)
                    elif status_code.startswith("?"):
                        untracked.append(file_path)
            
            return {
                "backend": self.backend_id,
                "repository": str(self._repo_path),
                "current_branch": current_branch,
                "head_commit": head_commit.get("hash", ""),
                "modified": modified,
                "staged": staged,
                "untracked": untracked,
                "is_clean": len(modified) == 0 and len(staged) == 0 and len(untracked) == 0,
            }
        except Exception as e:
            return {
                "backend": self.backend_id,
                "repository": str(self._repo_path),
                "error": str(e),
            }
    
    def is_repo(self, path: Path | None = None) -> bool:
        """Check if a path is a Git repository."""
        check_path = path or self._repo_path
        git_dir = check_path / ".git"
        
        # Check for .git directory
        if git_dir.exists() and git_dir.is_dir():
            return True
        
        # Also check for git worktree
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=check_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False
    
    def init(self, path: Path | None = None, bare: bool = False) -> None:
        """Initialize a new Git repository."""
        target_path = path or self._repo_path
        args = ["init"]
        if bare:
            args.append("--bare")
        
        self._run_cmd(args, cwd=target_path.parent if bare else target_path)
    
    def clone(
        self,
        url: str,
        to_path: Path | str | None = None,
        *,
        depth: int | None = None,
        branch: str | None = None,
    ) -> Path:
        """Clone a Git repository."""
        target_path = to_path or (self._repo_path / Path(url).name)
        target_path = Path(target_path)
        
        args = ["clone", url, str(target_path)]
        if depth:
            args.extend(["--depth", str(depth)])
        if branch:
            args.extend(["--branch", branch])
        
        self._run_cmd(args, cwd=None)
        return target_path
    
    def get_current_branch(self) -> str:
        """Get the current branch name."""
        return self._run_cmd(["branch", "--show-current"]).strip()
    
    def list_branches(self, remote: bool = False) -> list[str]:
        """List branches in the repository."""
        if remote:
            result = self._run_cmd(["branch", "-r"])
        else:
            result = self._run_cmd(["branch"])
        
        # Parse branch output - lines start with * for current branch
        branches = []
        for line in result.strip().splitlines():
            line = line.strip()
            if line:
                # Remove leading * and spaces
                branch_name = line.lstrip("* ")
                branches.append(branch_name)
        
        return branches
    
    def create_branch(self, name: str, from_branch: str | None = None) -> None:
        """Create a new branch."""
        args = ["branch", name]
        if from_branch:
            args.extend([from_branch])
        self._run_cmd(args)
    
    def checkout(self, ref: str, create: bool = False) -> None:
        """Checkout a branch or tag."""
        if create:
            # Create and checkout new branch
            self._run_cmd(["checkout", "-b", ref])
        else:
            self._run_cmd(["checkout", ref])
    
    def get_head_commit(self) -> dict[str, Any]:
        """Get the current HEAD commit."""
        # Get commit hash
        commit_hash = self._run_cmd(["rev-parse", "HEAD"]).strip()
        
        # Get author
        author = self._run_cmd(["show", "-s", "--format=%an <%ae>", "HEAD"]).strip()
        
        # Get commit message (first line)
        message = self._run_cmd(["show", "-s", "--format=%s", "HEAD"]).strip()
        
        # Get commit date
        date = self._run_cmd(["show", "-s", "--format=%ci", "HEAD"]).strip()
        
        return {
            "hash": commit_hash,
            "short_hash": commit_hash[:7],
            "author": author,
            "date": date,
            "message": message,
        }
    
    def log(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get commit log."""
        args = ["log"]
        if limit:
            args.extend([f"-n{limit}"])
        if since:
            args.extend([f"--since={since}"])
        if until:
            args.extend([f"--until={until}"])
        
        # Use custom format for machine parsing
        args.extend([
            "--format=%H|%h|%an|%ae|%ci|%s",
        ])
        
        result = self._run_cmd(args)
        
        commits = []
        for line in result.strip().splitlines():
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 6:
                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "author_name": parts[2],
                    "author_email": parts[3],
                    "date": parts[4],
                    "message": parts[5],
                })
        
        return commits
    
    def diff(
        self,
        ref1: str | None = None,
        ref2: str | None = None,
        *,
        staged: bool = False,
    ) -> str:
        """Get diff between references."""
        if ref1 and ref2:
            return self._run_cmd(["diff", ref1, ref2])
        elif ref1:
            return self._run_cmd(["diff", ref1])
        elif staged:
            return self._run_cmd(["diff", "--cached"])
        else:
            return self._run_cmd(["diff"])
    
    def add(self, paths: list[str | Path], all: bool = False) -> None:
        """Stage files for commit."""
        if all:
            self._run_cmd(["add", "--all"])
        else:
            path_strs = [str(p) for p in paths]
            self._run_cmd(["add"] + path_strs)
    
    def commit(
        self,
        message: str,
        *,
        all: bool = False,
        amend: bool = False,
        no_verify: bool = False,
    ) -> str:
        """Commit staged changes."""
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        if no_verify:
            args.append("--no-verify")
        if all:
            args.append("--all")
        
        self._run_cmd(args)
        return self._run_cmd(["rev-parse", "HEAD"]).strip()
    
    def list_remotes(self) -> list[dict[str, Any]]:
        """List configured remotes."""
        result = self._run_cmd(["remote", "-v"])
        
        remotes = []
        for line in result.strip().splitlines():
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                url = parts[1]
                direction = parts[2] if len(parts) > 2 else ""
                
                # Filter out fetch/push markers
                if direction in ("(fetch)", "(push)"):
                    continue
                
                remotes.append({
                    "name": name,
                    "url": url,
                })
        
        return remotes
    
    def add_remote(self, name: str, url: str) -> None:
        """Add a remote."""
        self._run_cmd(["remote", "add", name, url])
    
    def fetch(
        self,
        *,
        remote: str | None = None,
        all: bool = False,
        prune: bool = False,
    ) -> None:
        """Fetch from remote(s)."""
        args = ["fetch"]
        if all:
            args.append("--all")
        if prune:
            args.append("--prune")
        if remote:
            args.append(remote)
        
        self._run_cmd(args)
    
    def pull(
        self,
        *,
        remote: str | None = None,
        branch: str | None = None,
        rebase: bool = False,
    ) -> None:
        """Pull from remote."""
        args = ["pull"]
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        if rebase:
            args.append("--rebase")
        
        self._run_cmd(args)
    
    def push(
        self,
        *,
        remote: str | None = None,
        branch: str | None = None,
        force: bool = False,
    ) -> None:
        """Push to remote."""
        args = ["push"]
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        if force:
            args.append("--force")
        
        self._run_cmd(args)
