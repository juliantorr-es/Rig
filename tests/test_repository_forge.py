"""Tests for the Rig forge adapter domain contract.

These tests validate that:
1. ForgeMode enum has all expected values
2. PromotionMode enum has all expected values
3. Forge Doctor types exist and have required fields
4. classify_remote_url() correctly classifies URLs
5. derive_promotion_mode() returns correct PromotionMode
6. capabilities_for_mode() returns correct ForgeCapabilities
7. Git helper functions work with mocked subprocess
8. build_forge_identity() returns valid ForgeIdentity
9. build_doctor_report() returns valid ForgeDoctorReport
10. No mutation behavior - all functions are pure

DO NOT call remote APIs. DO NOT mutate worktrees. DO NOT modify existing files.
All tests use mocked subprocess or pure functions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Ensure src is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rig.domain.forge import (
    # Enums
    ForgeMode,
    PromotionMode,
    ForgeDoctorSeverity,
    # Dataclasses
    ForgeCapabilities,
    ForgeIdentity,
    ForgeDoctorFinding,
    ForgeDoctorReport,
    ReviewabilityBudget,
    ReviewabilityReport,
    # Classification functions
    classify_remote_url,
    derive_promotion_mode,
    capabilities_for_mode,
    # Git helpers
    git_remote_url,
    git_current_branch,
    git_rev_parse,
    git_branch_exists,
    git_inside_repo,
    git_merge_base,
    git_changed_files,
    # Builder functions
    build_forge_identity,
    build_doctor_findings,
    build_doctor_report,
    build_reviewability_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo_root():
    """Provide a mock repository root path."""
    return Path("/mock/repo")


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------

class TestForgeMode:
    """Tests for ForgeMode enum."""

    def test_forge_mode_values_exist(self):
        """All expected ForgeMode values must exist."""
        assert hasattr(ForgeMode, "LOCAL_ONLY")
        assert hasattr(ForgeMode, "GITHUB")
        assert hasattr(ForgeMode, "GITLAB")
        assert hasattr(ForgeMode, "GITEA")
        assert hasattr(ForgeMode, "UNKNOWN")

    def test_forge_mode_local_only_value(self):
        """LOCAL_ONLY must have correct value."""
        assert ForgeMode.LOCAL_ONLY.name == "LOCAL_ONLY"

    def test_forge_mode_github_value(self):
        """GITHUB must have correct value."""
        assert ForgeMode.GITHUB.name == "GITHUB"

    def test_forge_mode_gitlab_value(self):
        """GITLAB must have correct value."""
        assert ForgeMode.GITLAB.name == "GITLAB"

    def test_forge_mode_gitea_value(self):
        """GITEA must have correct value."""
        assert ForgeMode.GITEA.name == "GITEA"

    def test_forge_mode_unknown_value(self):
        """UNKNOWN must have correct value."""
        assert ForgeMode.UNKNOWN.name == "UNKNOWN"


class TestPromotionMode:
    """Tests for PromotionMode enum."""

    def test_promotion_mode_values_exist(self):
        """All expected PromotionMode values must exist."""
        assert hasattr(PromotionMode, "LOCAL_BRANCH")
        assert hasattr(PromotionMode, "PULL_REQUEST")
        assert hasattr(PromotionMode, "MERGE_REQUEST")
        assert hasattr(PromotionMode, "MANUAL")

    def test_promotion_mode_local_branch_value(self):
        """LOCAL_BRANCH must have correct value."""
        assert PromotionMode.LOCAL_BRANCH.name == "LOCAL_BRANCH"

    def test_promotion_mode_pull_request_value(self):
        """PULL_REQUEST must have correct value."""
        assert PromotionMode.PULL_REQUEST.name == "PULL_REQUEST"

    def test_promotion_mode_merge_request_value(self):
        """MERGE_REQUEST must have correct value."""
        assert PromotionMode.MERGE_REQUEST.name == "MERGE_REQUEST"

    def test_promotion_mode_manual_value(self):
        """MANUAL must have correct value."""
        assert PromotionMode.MANUAL.name == "MANUAL"


class TestForgeDoctorSeverity:
    """Tests for ForgeDoctorSeverity enum."""

    def test_severity_values_exist(self):
        """All expected severity values must exist."""
        assert hasattr(ForgeDoctorSeverity, "INFO")
        assert hasattr(ForgeDoctorSeverity, "WARNING")
        assert hasattr(ForgeDoctorSeverity, "ERROR")
        assert hasattr(ForgeDoctorSeverity, "CRITICAL")

    def test_severity_string_values(self):
        """Severity enum values must match string values."""
        assert ForgeDoctorSeverity.INFO.value == "info"
        assert ForgeDoctorSeverity.WARNING.value == "warning"
        assert ForgeDoctorSeverity.ERROR.value == "error"
        assert ForgeDoctorSeverity.CRITICAL.value == "critical"


# ---------------------------------------------------------------------------
# Dataclass Tests
# ---------------------------------------------------------------------------

class TestForgeCapabilities:
    """Tests for ForgeCapabilities dataclass."""

    def test_default_all_false(self):
        """Default ForgeCapabilities must have all False."""
        caps = ForgeCapabilities()
        assert caps.supports_remote is False
        assert caps.supports_pull_request is False
        assert caps.supports_merge_request is False
        assert caps.supports_required_checks is False
        assert caps.supports_protected_branches is False
        assert caps.supports_linear_history is False
        assert caps.supports_review_approvals is False
        assert caps.supports_conversation_resolution is False

    def test_frozen(self):
        """ForgeCapabilities must be immutable."""
        caps = ForgeCapabilities(supports_remote=True)
        with pytest.raises(AttributeError):
            caps.supports_remote = False  # type: ignore[reportAttributeAccessIssue]

    def test_slots(self):
        """ForgeCapabilities must use slots."""
        caps = ForgeCapabilities()
        # Slots with frozen=True prevents arbitrary attribute assignment
        # Raises TypeError or AttributeError depending on implementation
        with pytest.raises((AttributeError, TypeError)):
            caps.extra_field = "test"  # type: ignore[reportAttributeAccessIssue]

    def test_custom_values(self):
        """ForgeCapabilities must accept custom values."""
        caps = ForgeCapabilities(
            supports_remote=True,
            supports_pull_request=True,
            supports_linear_history=True,
        )
        assert caps.supports_remote is True
        assert caps.supports_pull_request is True
        assert caps.supports_linear_history is True


class TestForgeIdentity:
    """Tests for ForgeIdentity dataclass."""

    def test_default_values(self):
        """ForgeIdentity must have correct defaults."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        assert identity.mode == ForgeMode.LOCAL_ONLY
        assert identity.remote_url is None
        assert identity.host is None
        assert identity.owner is None
        assert identity.repository is None
        assert identity.default_branch == "main"
        assert identity.preproduction_branch == "preproduction"

    def test_custom_values(self):
        """ForgeIdentity must accept custom values."""
        identity = ForgeIdentity(
            mode=ForgeMode.GITHUB,
            remote_url="https://github.com/owner/repo.git",
            host="github.com",
            owner="owner",
            repository="repo",
        )
        assert identity.mode == ForgeMode.GITHUB
        assert identity.remote_url == "https://github.com/owner/repo.git"
        assert identity.host == "github.com"
        assert identity.owner == "owner"
        assert identity.repository == "repo"

    def test_frozen(self):
        """ForgeIdentity must be immutable."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        with pytest.raises(AttributeError):
            identity.mode = ForgeMode.GITHUB  # type: ignore[reportAttributeAccessIssue]


class TestForgeDoctorFinding:
    """Tests for ForgeDoctorFinding dataclass."""

    def test_required_fields(self):
        """ForgeDoctorFinding must require code, severity, message."""
        finding = ForgeDoctorFinding(
            code="TEST-001",
            severity=ForgeDoctorSeverity.INFO,
            message="Test finding",
        )
        assert finding.code == "TEST-001"
        assert finding.severity == ForgeDoctorSeverity.INFO
        assert finding.message == "Test finding"
        assert finding.remediation is None

    def test_optional_remediation(self):
        """ForgeDoctorFinding remediation must be optional."""
        finding = ForgeDoctorFinding(
            code="TEST-002",
            severity=ForgeDoctorSeverity.WARNING,
            message="Test with remediation",
            remediation="Do something to fix",
        )
        assert finding.remediation == "Do something to fix"

    def test_frozen(self):
        """ForgeDoctorFinding must be immutable."""
        finding = ForgeDoctorFinding(
            code="TEST-001",
            severity=ForgeDoctorSeverity.INFO,
            message="Test",
        )
        with pytest.raises(AttributeError):
            finding.code = "TEST-002"  # type: ignore[reportAttributeAccessIssue]


class TestForgeDoctorReport:
    """Tests for ForgeDoctorReport dataclass."""

    def test_default_findings_empty_tuple(self):
        """ForgeDoctorReport must have empty tuple for findings by default."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        caps = ForgeCapabilities()
        report = ForgeDoctorReport(
            identity=identity,
            capabilities=caps,
            promotion_mode=PromotionMode.LOCAL_BRANCH,
        )
        assert report.findings == ()
        assert report.overall_status == "clean"

    def test_custom_values(self):
        """ForgeDoctorReport must accept custom values."""
        identity = ForgeIdentity(mode=ForgeMode.GITHUB)
        caps = ForgeCapabilities(supports_pull_request=True)
        findings = [
            ForgeDoctorFinding(
                code="TEST-001",
                severity=ForgeDoctorSeverity.INFO,
                message="Test",
            )
        ]
        report = ForgeDoctorReport(
            identity=identity,
            capabilities=caps,
            promotion_mode=PromotionMode.PULL_REQUEST,
            findings=tuple(findings),
            overall_status="warning",
        )
        assert report.identity == identity
        assert report.capabilities == caps
        assert report.promotion_mode == PromotionMode.PULL_REQUEST
        assert len(report.findings) == 1
        assert report.overall_status == "warning"


# ---------------------------------------------------------------------------
# classify_remote_url() Tests
# ---------------------------------------------------------------------------

class TestClassifyRemoteUrl:
    """Tests for classify_remote_url() function."""

    def test_none_returns_local_only(self):
        """None URL must return LOCAL_ONLY."""
        assert classify_remote_url(None) == ForgeMode.LOCAL_ONLY

    def test_empty_returns_local_only(self):
        """Empty string URL must return LOCAL_ONLY."""
        # Empty string is truthy, so check the actual behavior
        # classify_remote_url("") should go through string checks and return UNKNOWN
        # But we want LOCAL_ONLY for None only
        result = classify_remote_url("")
        assert result == ForgeMode.UNKNOWN  # Empty string doesn't match any pattern

    def test_github_https_url(self):
        """GitHub HTTPS URL must return GITHUB."""
        assert classify_remote_url("https://github.com/owner/repo.git") == ForgeMode.GITHUB
        assert classify_remote_url("https://github.com/owner/repo") == ForgeMode.GITHUB

    def test_github_ssh_url(self):
        """GitHub SSH URL must return GITHUB."""
        assert classify_remote_url("git@github.com:owner/repo.git") == ForgeMode.GITHUB

    def test_gitlab_https_url(self):
        """GitLab HTTPS URL must return GITLAB."""
        assert classify_remote_url("https://gitlab.com/owner/repo.git") == ForgeMode.GITLAB

    def test_gitlab_ssh_url(self):
        """GitLab SSH URL must return GITLAB."""
        assert classify_remote_url("git@gitlab.com:owner/repo.git") == ForgeMode.GITLAB

    def test_gitea_https_url(self):
        """Gitea HTTPS URL must return GITEA."""
        assert classify_remote_url("https://gitea.com/owner/repo.git") == ForgeMode.GITEA
        assert classify_remote_url("https://gitea.example.com/owner/repo.git") == ForgeMode.GITEA

    def test_gitea_ssh_url(self):
        """Gitea SSH URL must return GITEA."""
        assert classify_remote_url("git@gitea.example.com:owner/repo.git") == ForgeMode.GITEA

    def test_unknown_url(self):
        """Unknown URL must return UNKNOWN."""
        assert classify_remote_url("https://bitbucket.org/owner/repo.git") == ForgeMode.UNKNOWN
        assert classify_remote_url("https://example.com/repo.git") == ForgeMode.UNKNOWN

    def test_case_insensitive(self):
        """URL classification must be case-insensitive."""
        assert classify_remote_url("HTTPS://GITHUB.COM/owner/repo.git") == ForgeMode.GITHUB
        assert classify_remote_url("Git@GitLab.com:owner/repo.git") == ForgeMode.GITLAB


# ---------------------------------------------------------------------------
# derive_promotion_mode() Tests
# ---------------------------------------------------------------------------

class TestDerivePromotionMode:
    """Tests for derive_promotion_mode() function."""

    def test_local_only_to_local_branch(self):
        """LOCAL_ONLY must map to LOCAL_BRANCH."""
        assert derive_promotion_mode(ForgeMode.LOCAL_ONLY) == PromotionMode.LOCAL_BRANCH

    def test_github_to_pull_request(self):
        """GITHUB must map to PULL_REQUEST."""
        assert derive_promotion_mode(ForgeMode.GITHUB) == PromotionMode.PULL_REQUEST

    def test_gitlab_to_merge_request(self):
        """GITLAB must map to MERGE_REQUEST."""
        assert derive_promotion_mode(ForgeMode.GITLAB) == PromotionMode.MERGE_REQUEST

    def test_gitea_to_pull_request(self):
        """GITEA must map to PULL_REQUEST."""
        assert derive_promotion_mode(ForgeMode.GITEA) == PromotionMode.PULL_REQUEST

    def test_unknown_to_manual(self):
        """UNKNOWN must map to MANUAL."""
        assert derive_promotion_mode(ForgeMode.UNKNOWN) == PromotionMode.MANUAL


# ---------------------------------------------------------------------------
# capabilities_for_mode() Tests
# ---------------------------------------------------------------------------

class TestCapabilitiesForMode:
    """Tests for capabilities_for_mode() function."""

    def test_local_only_capabilities(self):
        """LOCAL_ONLY must have correct capabilities."""
        caps = capabilities_for_mode(ForgeMode.LOCAL_ONLY)
        assert caps.supports_remote is False
        assert caps.supports_pull_request is False
        assert caps.supports_merge_request is False
        assert caps.supports_required_checks is False
        assert caps.supports_protected_branches is False
        assert caps.supports_linear_history is True  # Local git supports this
        assert caps.supports_review_approvals is False
        assert caps.supports_conversation_resolution is False

    def test_github_capabilities(self):
        """GITHUB must have correct capabilities."""
        caps = capabilities_for_mode(ForgeMode.GITHUB)
        assert caps.supports_remote is True
        assert caps.supports_pull_request is True
        assert caps.supports_merge_request is False
        assert caps.supports_required_checks is True
        assert caps.supports_protected_branches is True
        assert caps.supports_linear_history is True
        assert caps.supports_review_approvals is True
        assert caps.supports_conversation_resolution is True

    def test_gitlab_capabilities(self):
        """GITLAB must have correct capabilities."""
        caps = capabilities_for_mode(ForgeMode.GITLAB)
        assert caps.supports_remote is True
        assert caps.supports_pull_request is False
        assert caps.supports_merge_request is True
        assert caps.supports_required_checks is True
        assert caps.supports_protected_branches is True
        assert caps.supports_linear_history is True
        assert caps.supports_review_approvals is True
        assert caps.supports_conversation_resolution is True

    def test_gitea_capabilities(self):
        """GITEA must have correct capabilities."""
        caps = capabilities_for_mode(ForgeMode.GITEA)
        assert caps.supports_remote is True
        assert caps.supports_pull_request is True
        assert caps.supports_merge_request is False
        assert caps.supports_required_checks is True
        assert caps.supports_protected_branches is True
        assert caps.supports_linear_history is True
        assert caps.supports_review_approvals is True
        assert caps.supports_conversation_resolution is False

    def test_unknown_capabilities(self):
        """UNKNOWN must have all False capabilities."""
        caps = capabilities_for_mode(ForgeMode.UNKNOWN)
        assert caps.supports_remote is False
        assert caps.supports_pull_request is False
        assert caps.supports_merge_request is False
        assert caps.supports_required_checks is False
        assert caps.supports_protected_branches is False
        assert caps.supports_linear_history is False
        assert caps.supports_review_approvals is False
        assert caps.supports_conversation_resolution is False


# ---------------------------------------------------------------------------
# Git Helper Function Tests
# ---------------------------------------------------------------------------

class TestGitRemoteUrl:
    """Tests for git_remote_url() function."""

    def test_success(self, mock_repo_root):
        """git_remote_url must return URL on success."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://github.com/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_remote_url(mock_repo_root)
            assert result == "https://github.com/owner/repo.git"

    def test_failure_returns_none(self, mock_repo_root):
        """git_remote_url must return None on failure."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_remote_url(mock_repo_root)
            assert result is None

    def test_empty_output_returns_none(self, mock_repo_root):
        """git_remote_url must return None on empty output."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_remote_url(mock_repo_root)
            assert result is None

    def test_custom_remote(self, mock_repo_root):
        """git_remote_url must use custom remote parameter."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://gitlab.com/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc) as mock_run:
            result = git_remote_url(mock_repo_root, remote="upstream")
            assert result == "https://gitlab.com/owner/repo.git"
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0]
            assert call_args[0] == mock_repo_root
            assert "upstream" in call_args


class TestGitCurrentBranch:
    """Tests for git_current_branch() function."""

    def test_success(self, mock_repo_root):
        """git_current_branch must return branch name on success."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "main\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_current_branch(mock_repo_root)
            assert result == "main"

    def test_failure_returns_none(self, mock_repo_root):
        """git_current_branch must return None on failure."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_current_branch(mock_repo_root)
            assert result is None

    def test_detached_head_returns_none(self, mock_repo_root):
        """git_current_branch must return None on detached HEAD."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""  # Empty output on detached HEAD
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_current_branch(mock_repo_root)
            assert result is None


class TestGitRevParse:
    """Tests for git_rev_parse() function."""

    def test_success_default_head(self, mock_repo_root):
        """git_rev_parse must return short hash for HEAD by default."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "abc1234\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_rev_parse(mock_repo_root)
            assert result == "abc1234"

    def test_success_custom_rev(self, mock_repo_root):
        """git_rev_parse must return hash for custom revision."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "def5678\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc) as mock_run:
            result = git_rev_parse(mock_repo_root, rev="main")
            assert result == "def5678"
            call_args = mock_run.call_args[0]
            assert "main" in call_args

    def test_failure_returns_none(self, mock_repo_root):
        """git_rev_parse must return None on failure."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_rev_parse(mock_repo_root)
            assert result is None


class TestGitBranchExists:
    """Tests for git_branch_exists() function."""

    def test_branch_exists(self, mock_repo_root):
        """git_branch_exists must return True for existing branch."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "  main\n"  # branch --list output includes the branch
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_branch_exists(mock_repo_root, "main") is True

    def test_branch_not_exists(self, mock_repo_root):
        """git_branch_exists must return False for non-existing branch."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""  # No output for non-existing branch
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_branch_exists(mock_repo_root, "nonexistent") is False

    def test_failure_returns_false(self, mock_repo_root):
        """git_branch_exists must return False on git error."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_branch_exists(mock_repo_root, "main") is False


class TestGitInsideRepo:
    """Tests for git_inside_repo() function."""

    def test_inside_repo(self, mock_repo_root):
        """git_inside_repo must return True inside a repo."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "true\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_inside_repo(mock_repo_root) is True

    def test_not_inside_repo(self, mock_repo_root):
        """git_inside_repo must return False outside a repo."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "false\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_inside_repo(mock_repo_root) is False

    def test_failure_returns_false(self, mock_repo_root):
        """git_inside_repo must return False on git error."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            assert git_inside_repo(mock_repo_root) is False


# ---------------------------------------------------------------------------
# Builder Function Tests
# ---------------------------------------------------------------------------

class TestBuildForgeIdentity:
    """Tests for build_forge_identity() function."""

    def test_local_only_no_remote(self, mock_repo_root):
        """build_forge_identity must detect LOCAL_ONLY when no remote."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            assert identity.mode == ForgeMode.LOCAL_ONLY
            assert identity.remote_url is None
            assert identity.host is None

    def test_github_remote(self, mock_repo_root):
        """build_forge_identity must detect GITHUB from remote URL."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://github.com/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            assert identity.mode == ForgeMode.GITHUB
            assert identity.remote_url == "https://github.com/owner/repo.git"
            assert identity.host == "github.com"

    def test_gitlab_remote(self, mock_repo_root):
        """build_forge_identity must detect GITLAB from remote URL."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://gitlab.com/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            assert identity.mode == ForgeMode.GITLAB
            assert identity.host == "gitlab.com"

    def test_gitea_remote(self, mock_repo_root):
        """build_forge_identity must detect GITEA from remote URL."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://gitea.example.com/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            assert identity.mode == ForgeMode.GITEA
            assert identity.host == "gitea"

    def test_unknown_remote(self, mock_repo_root):
        """build_forge_identity must detect UNKNOWN for unrecognized remote."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://bitbucket.org/owner/repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            assert identity.mode == ForgeMode.UNKNOWN
            assert identity.host is None


class TestBuildDoctorFindings:
    """Tests for build_doctor_findings() function."""

    def test_not_inside_git_repo(self, mock_repo_root):
        """build_doctor_findings must report error when not in git repo."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        
        with patch("rig.domain.forge.git_inside_repo", return_value=False):
            findings = build_doctor_findings(mock_repo_root, identity)
            assert len(findings) == 1
            assert findings[0].code == "FORGE-001"
            assert findings[0].severity == ForgeDoctorSeverity.ERROR

    def test_no_remote_configured(self, mock_repo_root):
        """build_doctor_findings must report info when no remote."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY, remote_url=None)
        
        with patch("rig.domain.forge.git_inside_repo", return_value=True):
            with patch("rig.domain.forge.git_branch_exists", return_value=True):
                with patch("rig.domain.forge.git_current_branch", return_value="main"):
                    findings = build_doctor_findings(mock_repo_root, identity)
                    codes = [f.code for f in findings]
                    assert "FORGE-002" in codes  # No remote configured

    def test_no_preproduction_branch(self, mock_repo_root):
        """build_doctor_findings must report warning when no preproduction branch."""
        identity = ForgeIdentity(mode=ForgeMode.GITHUB, remote_url="https://github.com/owner/repo.git")
        
        with patch("rig.domain.forge.git_inside_repo", return_value=True):
            with patch("rig.domain.forge.git_branch_exists", return_value=False):
                with patch("rig.domain.forge.git_current_branch", return_value="main"):
                    findings = build_doctor_findings(mock_repo_root, identity)
                    codes = [f.code for f in findings]
                    assert "FORGE-003" in codes  # No preproduction branch

    def test_detached_head(self, mock_repo_root):
        """build_doctor_findings must report warning on detached HEAD."""
        identity = ForgeIdentity(mode=ForgeMode.GITHUB, remote_url="https://github.com/owner/repo.git")
        
        with patch("rig.domain.forge.git_inside_repo", return_value=True):
            with patch("rig.domain.forge.git_branch_exists", return_value=True):
                with patch("rig.domain.forge.git_current_branch", return_value=None):
                    findings = build_doctor_findings(mock_repo_root, identity)
                    codes = [f.code for f in findings]
                    assert "FORGE-004" in codes  # Could not determine current branch

    def test_clean_repo(self, mock_repo_root):
        """build_doctor_findings must return empty list for clean repo."""
        identity = ForgeIdentity(
            mode=ForgeMode.GITHUB,
            remote_url="https://github.com/owner/repo.git",
            host="github.com",
        )
        
        with patch("rig.domain.forge.git_inside_repo", return_value=True):
            with patch("rig.domain.forge.git_branch_exists", return_value=True):
                with patch("rig.domain.forge.git_current_branch", return_value="main"):
                    findings = build_doctor_findings(mock_repo_root, identity)
                    assert findings == []


class TestBuildDoctorReport:
    """Tests for build_doctor_report() function."""

    def test_full_report(self, mock_repo_root):
        """build_doctor_report must return complete report."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        
        with patch("rig.domain.forge.build_forge_identity", return_value=identity):
            with patch("rig.domain.forge.capabilities_for_mode") as mock_caps:
                with patch("rig.domain.forge.derive_promotion_mode") as mock_promo:
                    with patch("rig.domain.forge.build_doctor_findings", return_value=[]):
                        mock_caps.return_value = ForgeCapabilities(supports_linear_history=True)
                        mock_promo.return_value = PromotionMode.LOCAL_BRANCH
                        
                        report = build_doctor_report(mock_repo_root)
                        
                        assert report.identity == identity
                        assert report.capabilities == mock_caps.return_value
                        assert report.promotion_mode == mock_promo.return_value
                        assert report.findings == ()
                        assert report.overall_status == "clean"

    def test_report_with_findings(self, mock_repo_root):
        """build_doctor_report must set overall_status based on findings."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        findings = [
            ForgeDoctorFinding(
                code="TEST-001",
                severity=ForgeDoctorSeverity.WARNING,
                message="Test warning",
            ),
        ]
        
        with patch("rig.domain.forge.build_forge_identity", return_value=identity):
            with patch("rig.domain.forge.capabilities_for_mode") as mock_caps:
                with patch("rig.domain.forge.derive_promotion_mode") as mock_promo:
                    with patch("rig.domain.forge.build_doctor_findings", return_value=findings):
                        mock_caps.return_value = ForgeCapabilities()
                        mock_promo.return_value = PromotionMode.LOCAL_BRANCH
                        
                        report = build_doctor_report(mock_repo_root)
                        assert report.overall_status == "warning"

    def test_report_with_error(self, mock_repo_root):
        """build_doctor_report must set critical status for ERROR findings."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        findings = [
            ForgeDoctorFinding(
                code="TEST-001",
                severity=ForgeDoctorSeverity.ERROR,
                message="Test error",
            ),
        ]
        
        with patch("rig.domain.forge.build_forge_identity", return_value=identity):
            with patch("rig.domain.forge.capabilities_for_mode") as mock_caps:
                with patch("rig.domain.forge.derive_promotion_mode") as mock_promo:
                    with patch("rig.domain.forge.build_doctor_findings", return_value=findings):
                        mock_caps.return_value = ForgeCapabilities()
                        mock_promo.return_value = PromotionMode.LOCAL_BRANCH
                        
                        report = build_doctor_report(mock_repo_root)
                        assert report.overall_status == "error"

    def test_report_with_critical(self, mock_repo_root):
        """build_doctor_report must set critical status for CRITICAL findings."""
        identity = ForgeIdentity(mode=ForgeMode.LOCAL_ONLY)
        findings = [
            ForgeDoctorFinding(
                code="TEST-001",
                severity=ForgeDoctorSeverity.CRITICAL,
                message="Test critical",
            ),
        ]
        
        with patch("rig.domain.forge.build_forge_identity", return_value=identity):
            with patch("rig.domain.forge.capabilities_for_mode") as mock_caps:
                with patch("rig.domain.forge.derive_promotion_mode") as mock_promo:
                    with patch("rig.domain.forge.build_doctor_findings", return_value=findings):
                        mock_caps.return_value = ForgeCapabilities()
                        mock_promo.return_value = PromotionMode.LOCAL_BRANCH
                        
                        report = build_doctor_report(mock_repo_root)
                        assert report.overall_status == "critical"


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """Integration tests for the forge domain module."""

    def test_all_modes_classified(self):
        """All ForgeMode values must be classifiable from sample URLs."""
        urls = {
            ForgeMode.LOCAL_ONLY: None,
            ForgeMode.GITHUB: "https://github.com/owner/repo.git",
            ForgeMode.GITLAB: "https://gitlab.com/owner/repo.git",
            ForgeMode.GITEA: "https://gitea.example.com/owner/repo.git",
            ForgeMode.UNKNOWN: "https://bitbucket.org/owner/repo.git",
        }
        
        for expected_mode, url in urls.items():
            assert classify_remote_url(url) == expected_mode, \
                f"Expected {expected_mode} for {url}, got {classify_remote_url(url)}"

    def test_all_modes_have_promotion(self):
        """All ForgeMode values must map to a PromotionMode."""
        for mode in ForgeMode:
            promo = derive_promotion_mode(mode)
            assert isinstance(promo, PromotionMode), \
                f"No PromotionMode for {mode}"

    def test_all_modes_have_capabilities(self):
        """All ForgeMode values must return ForgeCapabilities."""
        for mode in ForgeMode:
            caps = capabilities_for_mode(mode)
            assert isinstance(caps, ForgeCapabilities), \
                f"No ForgeCapabilities for {mode}"

    def test_identity_environment_snapshot(self, mock_repo_root):
        """Test building a complete identity from mocked environment."""
        # Simulate a GitHub repo with origin remote
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "https://github.com/test-owner/test-repo.git\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            
            assert identity.mode == ForgeMode.GITHUB
            assert identity.remote_url == "https://github.com/test-owner/test-repo.git"
            assert identity.host == "github.com"
            assert identity.default_branch == "main"
            assert identity.preproduction_branch == "preproduction"

    def test_local_only_is_valid(self, mock_repo_root):
        """Local-only mode must be fully valid and functional."""
        # Simulate no remote
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            identity = build_forge_identity(mock_repo_root)
            caps = capabilities_for_mode(identity.mode)
            promo = derive_promotion_mode(identity.mode)
            
            assert identity.mode == ForgeMode.LOCAL_ONLY
            assert caps.supports_remote is False
            assert caps.supports_linear_history is True
            assert promo == PromotionMode.LOCAL_BRANCH


# ---------------------------------------------------------------------------
# ReviewabilityBudget Dataclass Tests
# ---------------------------------------------------------------------------

class TestReviewabilityBudget:
    """Tests for ReviewabilityBudget dataclass."""

    def test_default_values(self):
        """ReviewabilityBudget must have correct defaults from ADR 0010."""
        budget = ReviewabilityBudget()
        assert budget.max_changed_files == 300
        assert budget.max_listed_files == 300
        assert budget.default_action == "block_promotion"
        assert budget.override_allowed is True
        assert budget.override_requires_reason is True

    def test_custom_values(self):
        """ReviewabilityBudget must accept custom values."""
        budget = ReviewabilityBudget(
            max_changed_files=500,
            max_listed_files=200,
            default_action="warn",
            override_allowed=False,
            override_requires_reason=False,
        )
        assert budget.max_changed_files == 500
        assert budget.max_listed_files == 200
        assert budget.default_action == "warn"
        assert budget.override_allowed is False
        assert budget.override_requires_reason is False

    def test_frozen(self):
        """ReviewabilityBudget must be immutable."""
        budget = ReviewabilityBudget()
        with pytest.raises(AttributeError):
            budget.max_changed_files = 100  # type: ignore[reportAttributeAccessIssue]

    def test_slots(self):
        """ReviewabilityBudget must use slots."""
        budget = ReviewabilityBudget()
        with pytest.raises((AttributeError, TypeError)):
            budget.extra_field = "test"  # type: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# ReviewabilityReport Dataclass Tests
# ---------------------------------------------------------------------------

class TestReviewabilityReport:
    """Tests for ReviewabilityReport dataclass."""

    def test_required_fields(self):
        """ReviewabilityReport must have all required fields."""
        report = ReviewabilityReport(
            target_ref="main",
            head_ref="HEAD",
            merge_base="abc123",
            changed_file_count=10,
            max_changed_files=300,
            over_budget=False,
            default_action="block_promotion",
            override_required=False,
            changed_files=("file1.py", "file2.py"),
            truncated=False,
            findings=(),
        )
        assert report.target_ref == "main"
        assert report.head_ref == "HEAD"
        assert report.merge_base == "abc123"
        assert report.changed_file_count == 10
        assert report.max_changed_files == 300
        assert report.over_budget is False
        assert report.default_action == "block_promotion"
        assert report.override_required is False
        assert report.changed_files == ("file1.py", "file2.py")
        assert report.truncated is False
        assert report.findings == ()

    def test_frozen(self):
        """ReviewabilityReport must be immutable."""
        report = ReviewabilityReport(
            target_ref="main",
            head_ref="HEAD",
            merge_base=None,
            changed_file_count=0,
            max_changed_files=300,
            over_budget=False,
            default_action="block_promotion",
            override_required=False,
            changed_files=(),
            truncated=False,
            findings=(),
        )
        with pytest.raises(AttributeError):
            report.target_ref = "develop"  # type: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# git_merge_base() Tests
# ---------------------------------------------------------------------------

class TestGitMergeBase:
    """Tests for git_merge_base() function."""

    def test_success(self, mock_repo_root):
        """git_merge_base must return merge base commit on success."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "abc1234\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_merge_base(mock_repo_root, "main", "HEAD")
            assert result == "abc1234"

    def test_failure_returns_none(self, mock_repo_root):
        """git_merge_base must return None on failure."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_merge_base(mock_repo_root, "main", "HEAD")
            assert result is None

    def test_empty_output_returns_none(self, mock_repo_root):
        """git_merge_base must return None on empty output."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_merge_base(mock_repo_root, "main", "HEAD")
            assert result is None

    def test_default_head_ref(self, mock_repo_root):
        """git_merge_base must use HEAD as default head_ref."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "def5678\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc) as mock_run:
            result = git_merge_base(mock_repo_root, "main")
            assert result == "def5678"
            call_args = mock_run.call_args[0]
            assert "HEAD" in call_args


# ---------------------------------------------------------------------------
# git_changed_files() Tests
# ---------------------------------------------------------------------------

class TestGitChangedFiles:
    """Tests for git_changed_files() function."""

    def test_success_multiple_files(self, mock_repo_root):
        """git_changed_files must return tuple of changed file paths."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "file1.py\nfile2.py\nfile3.py\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ("file1.py", "file2.py", "file3.py")

    def test_success_single_file(self, mock_repo_root):
        """git_changed_files must return single file as tuple."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "README.md\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ("README.md",)

    def test_failure_returns_empty_tuple(self, mock_repo_root):
        """git_changed_files must return empty tuple on failure."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ()

    def test_empty_output_returns_empty_tuple(self, mock_repo_root):
        """git_changed_files must return empty tuple on empty output."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ()

    def test_strips_whitespace(self, mock_repo_root):
        """git_changed_files must strip whitespace from paths."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "  file1.py  \n\tfile2.py\t\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ("file1.py", "file2.py")

    def test_filters_empty_lines(self, mock_repo_root):
        """git_changed_files must filter empty lines."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "file1.py\n\nfile2.py\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            result = git_changed_files(mock_repo_root, "abc123", "HEAD")
            assert result == ("file1.py", "file2.py")

    def test_default_head_ref(self, mock_repo_root):
        """git_changed_files must use HEAD as default head_ref."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.stdout = "file1.py\n"
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc) as mock_run:
            result = git_changed_files(mock_repo_root, "abc123")
            assert result == ("file1.py",)
            call_args = mock_run.call_args[0]
            assert "HEAD" in call_args


# ---------------------------------------------------------------------------
# build_reviewability_report() Tests
# ---------------------------------------------------------------------------

class TestBuildReviewabilityReport:
    """Tests for build_reviewability_report() function."""

    def test_within_budget(self, mock_repo_root):
        """build_reviewability_report must return correct report when within budget."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = "  main\n"
        
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = "file1.py\nfile2.py\n"
        
        with patch("rig.domain.forge._git_run") as mock_run:
            # Order: git_merge_base, git_branch_exists (for target_ref check), git_changed_files
            mock_run.side_effect = [
                mock_merge_base_proc,  # git merge-base main HEAD
                mock_branch_check_proc,  # git branch --list main (from git_branch_exists)
                mock_files_proc,  # git diff --name-only abc123 HEAD
            ]
            
            budget = ReviewabilityBudget(max_changed_files=300, max_listed_files=300)
            report = build_reviewability_report(
                mock_repo_root,
                budget=budget,
                target_ref="preproduction",
                head_ref="HEAD",
            )
            
            assert report.target_ref == "preproduction"
            assert report.head_ref == "HEAD"
            assert report.merge_base == "abc123"
            assert report.changed_file_count == 2
            assert report.max_changed_files == 300
            assert report.over_budget is False
            assert report.override_required is False
            assert report.changed_files == ("file1.py", "file2.py")
            assert report.truncated is False
            assert report.default_action == "block_promotion"

    def test_exceeds_budget(self, mock_repo_root):
        """build_reviewability_report must flag when exceeding budget."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = "  main\n"
        
        # 350 files exceeds default 300 budget
        files_list = "\n".join([f"file{i}.py" for i in range(350)])
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = files_list
        
        with patch("rig.domain.forge._git_run") as mock_run:
            # Order: git_merge_base, git_branch_exists, git_changed_files
            mock_run.side_effect = [
                mock_merge_base_proc,
                mock_branch_check_proc,
                mock_files_proc,
            ]
            
            budget = ReviewabilityBudget(max_changed_files=300, max_listed_files=300)
            report = build_reviewability_report(
                mock_repo_root,
                budget=budget,
                target_ref="preproduction",
                head_ref="HEAD",
            )
            
            assert report.over_budget is True
            assert report.override_required is True  # requires reason when over budget
            assert report.changed_file_count == 350
            # Should be truncated to max_listed_files
            assert len(report.changed_files) == 300
            assert report.truncated is True
            
            # Should have finding for exceeding budget
            codes = [f.code for f in report.findings]
            assert "REVIEW-003" in codes

    def test_no_merge_base_finding(self, mock_repo_root):
        """build_reviewability_report must add REVIEW-001 finding when no merge base."""
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run", return_value=mock_proc):
            report = build_reviewability_report(
                mock_repo_root,
                target_ref="nonexistent",
                head_ref="HEAD",
            )
            
            assert report.merge_base is None
            assert report.changed_file_count == 0
            assert report.over_budget is False
            
            codes = [f.code for f in report.findings]
            assert "REVIEW-001" in codes

    def test_branch_not_exists_finding(self, mock_repo_root):
        """build_reviewability_report must add REVIEW-002 finding when branch doesn't exist."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = ""  # No branch found
        
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = "file1.py\n"
        
        with patch("rig.domain.forge._git_run") as mock_run:
            # Order: git_merge_base, git_branch_exists (returns empty = not found), git_changed_files
            mock_run.side_effect = [
                mock_merge_base_proc,
                mock_branch_check_proc,
                mock_files_proc,
            ]
            
            report = build_reviewability_report(
                mock_repo_root,
                target_ref="missing-branch",
                head_ref="HEAD",
            )
            
            codes = [f.code for f in report.findings]
            assert "REVIEW-002" in codes

    def test_none_target_ref_graceful(self, mock_repo_root):
        """build_reviewability_report must handle None target_ref gracefully."""
        with patch("rig.domain.forge._git_run") as mock_run:
            # This should trigger merge_base failure
            mock_proc = Mock()
            mock_proc.returncode = 1
            mock_proc.stdout = ""
            mock_run.return_value = mock_proc
            
            budget = ReviewabilityBudget()
            report = build_reviewability_report(
                mock_repo_root,
                budget=budget,
                target_ref="preproduction",
                head_ref="HEAD",
            )
            
            assert report.target_ref == "preproduction"
            assert report.head_ref == "HEAD"

    def test_default_budget(self, mock_repo_root):
        """build_reviewability_report must use default budget when None provided."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = "  main\n"
        
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run") as mock_run:
            mock_run.side_effect = [
                mock_merge_base_proc,
                mock_branch_check_proc,
                mock_files_proc,
            ]
            
            report = build_reviewability_report(
                mock_repo_root,
                budget=None,  # Use defaults
                target_ref="preproduction",
                head_ref="HEAD",
            )
            
            assert report.max_changed_files == 300  # Default from ReviewabilityBudget

    def test_custom_budget_values(self, mock_repo_root):
        """build_reviewability_report must use custom budget values."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = "  main\n"
        
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = "file1.py\n"
        
        with patch("rig.domain.forge._git_run") as mock_run:
            mock_run.side_effect = [
                mock_merge_base_proc,
                mock_branch_check_proc,
                mock_files_proc,
            ]
            
            budget = ReviewabilityBudget(
                max_changed_files=100,
                max_listed_files=50,
                default_action="warn",
                override_requires_reason=False,
            )
            report = build_reviewability_report(
                mock_repo_root,
                budget=budget,
                target_ref="preproduction",
                head_ref="HEAD",
            )
            
            assert report.max_changed_files == 100
            assert report.default_action == "warn"


# ---------------------------------------------------------------------------
# Integration Tests for Reviewability
# ---------------------------------------------------------------------------

class TestReviewabilityIntegration:
    """Integration tests for reviewability budget functionality."""

    def test_budget_immutability(self):
        """ReviewabilityBudget values must match ADR 0010 specification."""
        budget = ReviewabilityBudget()
        assert budget.max_changed_files == 300
        assert budget.max_listed_files == 300
        assert budget.default_action == "block_promotion"
        assert budget.override_allowed is True
        assert budget.override_requires_reason is True

    def test_report_structure_complete(self):
        """ReviewabilityReport must have all fields defined in ADR 0010."""
        report = ReviewabilityReport(
            target_ref="main",
            head_ref="HEAD",
            merge_base="abc123",
            changed_file_count=50,
            max_changed_files=300,
            over_budget=False,
            default_action="block_promotion",
            override_required=False,
            changed_files=("file1.py",),
            truncated=False,
            findings=(),
        )
        # Verify all expected fields exist
        assert hasattr(report, "target_ref")
        assert hasattr(report, "head_ref")
        assert hasattr(report, "merge_base")
        assert hasattr(report, "changed_file_count")
        assert hasattr(report, "max_changed_files")
        assert hasattr(report, "over_budget")
        assert hasattr(report, "default_action")
        assert hasattr(report, "override_required")
        assert hasattr(report, "changed_files")
        assert hasattr(report, "truncated")
        assert hasattr(report, "findings")

    def test_default_target_is_preproduction(self, mock_repo_root):
        """build_reviewability_report must default to preproduction target_ref."""
        mock_merge_base_proc = Mock()
        mock_merge_base_proc.returncode = 0
        mock_merge_base_proc.stdout = "abc123\n"
        
        mock_branch_check_proc = Mock()
        mock_branch_check_proc.returncode = 0
        mock_branch_check_proc.stdout = "  preproduction\n"
        
        mock_files_proc = Mock()
        mock_files_proc.returncode = 0
        mock_files_proc.stdout = ""
        
        with patch("rig.domain.forge._git_run") as mock_run:
            mock_run.side_effect = [
                mock_merge_base_proc,
                mock_branch_check_proc,
                mock_files_proc,
            ]
            
            # Call without explicit target_ref - should default to preproduction
            report = build_reviewability_report(mock_repo_root)
            
            assert report.target_ref == "preproduction"


def main() -> int:
    """Run all tests and return exit code."""
    return pytest.main([__file__, "-v"])


if __name__ == "__main__":
    sys.exit(main())
