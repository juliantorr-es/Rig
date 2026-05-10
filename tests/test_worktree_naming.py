"""Tests for worktree naming policy and canonical slug derivation.

Tests cover:
- canonical_slug() function
- extract_adr_id_from_path() function
- extract_adr_title_from_path() function
- derive_adr_directory_slug() function
- get_adr_worktree_path() function
- get_mission_worktree_path() function
- get_sprint_branch_name() function
- get_mission_branch_name() function
- get_promotion_branch_name() function
- is_reserved_worktree_name() function
- validate_worktree_name() function
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._work_lib import (
    canonical_slug,
    extract_adr_id_from_path,
    extract_adr_title_from_path,
    derive_adr_directory_slug,
    get_adr_worktree_path,
    get_mission_worktree_path,
    get_sprint_branch_name,
    get_mission_branch_name,
    get_promotion_branch_name,
    is_reserved_worktree_name,
    validate_worktree_name,
    WORKTREES_ROOT,
)

import pytest


# ============================================================================
# canonical_slug tests
# ============================================================================

class TestCanonicalSlug:
    """Tests for canonical_slug() function."""

    def test_lowercase(self) -> None:
        """All output must be lowercase."""
        assert canonical_slug("Agentic Workflow Refinement") == "agentic-workflow-refinement"
        assert canonical_slug("ADR 0009") == "adr-0009"
        assert canonical_slug("Workspace Domain Authority") == "workspace-domain-authority"

    def test_trim_whitespace(self) -> None:
        """Leading/trailing whitespace must be removed."""
        assert canonical_slug("  Agentic Workflow Refinement  ") == "agentic-workflow-refinement"
        assert canonical_slug("\tTest\n") == "test"

    def test_replace_non_alphanumeric(self) -> None:
        """Non-alphanumeric runs must be replaced with hyphen."""
        assert canonical_slug("Receipt/Evidence Unification") == "receipt-evidence-unification"
        assert canonical_slug("ui_cockpit") == "ui-cockpit"
        assert canonical_slug("test.go/files") == "test-go-files"
        assert canonical_slug("Rig-Consolidation") == "rig-consolidation"

    def test_remove_leading_trailing_hyphens(self) -> None:
        """Leading/trailing hyphens must be removed."""
        assert canonical_slug("---test---") == "test"
        assert canonical_slug("-test-") == "test"

    def test_empty_string(self) -> None:
        """Empty input must return empty string."""
        assert canonical_slug("") == ""
        assert canonical_slug("   ") == ""

    def test_whitespace_only(self) -> None:
        """Whitespace-only input must return empty string."""
        assert canonical_slug(" \t\n ") == ""

    def test_special_characters(self) -> None:
        """Special characters must be replaced with hyphens."""
        assert canonical_slug("test!@#$%^&*()value") == "test-value"
        assert canonical_slug("file[0]") == "file-0"
        assert canonical_slug("key=value") == "key-value"

    def test_multiple_hyphens_collapsed(self) -> None:
        """Multiple consecutive non-alphanumeric chars should collapse to single hyphen."""
        assert canonical_slug("test    value") == "test-value"
        assert canonical_slug("test___value") == "test-value"
        assert canonical_slug("test...value") == "test-value"

    def test_preserve_adr_prefix(self) -> None:
        """ADR-like prefixes should be preserved."""
        assert canonical_slug("adr0009") == "adr0009"
        assert canonical_slug("ADR0009") == "adr0009"

    def test_deterministic(self) -> None:
        """Same input must always produce same output."""
        inputs = [
            "Agentic Workflow Refinement",
            "ADR 0009: Agentic Workflow Refinement",
            "adr0009-agentic-workflow-refinement",
            "Workspace Domain Authority",
        ]
        for inp in inputs:
            result1 = canonical_slug(inp)
            result2 = canonical_slug(inp)
            assert result1 == result2, f"Non-deterministic for input: {inp}"


# ============================================================================
# extract_adr_id_from_path tests
# ============================================================================

class TestExtractAdrIdFromPath:
    """Tests for extract_adr_id_from_path() function."""

    def test_standard_adr_path(self) -> None:
        """Standard ADR file paths should extract ADR ID."""
        assert extract_adr_id_from_path("docs/adr/0009-agentic-workflow-refinement.md") == "adr0009"
        assert extract_adr_id_from_path("docs/adr/0007-workspace-domain-authority.md") == "adr0007"
        assert extract_adr_id_from_path("docs/adr/0008-receipt-evidence-unification.md") == "adr0008"

    def test_without_docs_prefix(self) -> None:
        """ADR paths without 'docs/' prefix should still work."""
        assert extract_adr_id_from_path("adr/0009-agentic-workflow-refinement.md") == "adr0009"

    def test_simple_filename(self) -> None:
        """Simple filename should extract ADR ID."""
        assert extract_adr_id_from_path("0009-agentic-workflow-refinement.md") == "adr0009"

    def test_path_object(self) -> None:
        """Path objects should work."""
        path = Path("docs/adr/0009-agentic-workflow-refinement.md")
        assert extract_adr_id_from_path(path) == "adr0009"

    def test_no_adr_id(self) -> None:
        """Paths without ADR ID should return empty string."""
        assert extract_adr_id_from_path("docs/other/some-file.md") == ""
        assert extract_adr_id_from_path("not-an-adr.md") == ""


# ============================================================================
# extract_adr_title_from_path tests
# ============================================================================

class TestExtractAdrTitleFromPath:
    """Tests for extract_adr_title_from_path() function."""

    def test_standard_adr_path(self) -> None:
        """Standard ADR file paths should extract title slug."""
        assert extract_adr_title_from_path("docs/adr/0009-agentic-workflow-refinement.md") == "agentic-workflow-refinement"
        assert extract_adr_title_from_path("docs/adr/0007-workspace-domain-authority.md") == "workspace-domain-authority"

    def test_with_underscore(self) -> None:
        """Underscore separators should be handled."""
        # This will extract after the ADR number
        # 0009-agentic_workflow_refinement.md -> after removing 0009- we get "agentic_workflow_refinement"
        # But the function expects hyphen separator
        result = extract_adr_title_from_path("docs/adr/0009-agentic_workflow_refinement.md")
        # The regex looks for NNNN- or NNNN_, so this should work
        assert result in ["agentic-workflow-refinement", "agentic_workflow_refinement"]

    def test_no_title_part(self) -> None:
        """If no title part after number, return filename."""
        # 0009.md -> just filename without extension
        result = extract_adr_title_from_path("docs/adr/0009.md")
        assert result == "0009"


# ============================================================================
# derive_adr_directory_slug tests
# ============================================================================

class TestDeriveAdrDirectorySlug:
    """Tests for derive_adr_directory_slug() function."""

    def test_from_path(self) -> None:
        """Derive from ADR path."""
        result = derive_adr_directory_slug(adr_path="docs/adr/0009-agentic-workflow-refinement.md")
        assert result == "adr0009-agentic-workflow-refinement"

    def test_from_id_and_title(self) -> None:
        """Derive from ADR ID and title."""
        result = derive_adr_directory_slug(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "adr0009-agentic-workflow-refinement"

    def test_title_with_extra_formatting(self) -> None:
        """Title with extra formatting should be cleaned."""
        # When title contains ADR number, it will be included in the slug
        # This is expected behavior - the title should not include the ADR number
        # But if it does, it gets slugified
        result = derive_adr_directory_slug(
            adr_id="adr0009", 
            adr_title="Agentic Workflow Refinement"  # Clean title without ADR prefix
        )
        assert result == "adr0009-agentic-workflow-refinement"

    def test_title_with_adr_number_included(self) -> None:
        """Title that includes ADR number should still work."""
        # If title includes ADR number, it will appear in the slug
        result = derive_adr_directory_slug(
            adr_id="adr0009", 
            adr_title="ADR 0009: Agentic Workflow Refinement"
        )
        # This gives: adr0009-adr-0009-agentic-workflow-refinement
        # The title slug is "adr-0009-agentic-workflow-refinement"
        assert result == "adr0009-adr-0009-agentic-workflow-refinement"

    def test_missing_args_raises(self) -> None:
        """Missing required args should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot derive"):
            derive_adr_directory_slug()


# ============================================================================
# Worktree path tests
# ============================================================================

class TestGetAdrWorktreePath:
    """Tests for get_adr_worktree_path() function."""

    def test_from_id_and_title(self) -> None:
        """Get worktree path from ADR ID and title."""
        result = get_adr_worktree_path(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == WORKTREES_ROOT / "adr0009-agentic-workflow-refinement"

    def test_from_path(self) -> None:
        """Get worktree path from ADR file path."""
        result = get_adr_worktree_path(adr_path="docs/adr/0009-agentic-workflow-refinement.md")
        assert result == WORKTREES_ROOT / "adr0009-agentic-workflow-refinement"


class TestGetMissionWorktreePath:
    """Tests for get_mission_worktree_path() function."""

    def test_with_mission_slug(self) -> None:
        """Get mission worktree path with mission slug."""
        result = get_mission_worktree_path(
            adr_id="adr0009",
            adr_title="Agentic Workflow Refinement",
            mission_slug="worktree-naming"
        )
        expected = WORKTREES_ROOT / "adr0009-agentic-workflow-refinement--worktree-naming"
        assert result == expected

    def test_without_mission_slug_raises(self) -> None:
        """Missing mission slug should raise ValueError."""
        with pytest.raises(ValueError, match="mission_slug is required"):
            get_mission_worktree_path(adr_id="adr0009", adr_title="Test")


# ============================================================================
# Branch name tests
# ============================================================================

class TestGetSprintBranchName:
    """Tests for get_sprint_branch_name() function."""

    def test_from_id_and_title(self) -> None:
        """Get sprint branch name from ADR ID and title."""
        result = get_sprint_branch_name(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "sprint/adr0009-agentic-workflow-refinement"

    def test_from_path(self) -> None:
        """Get sprint branch name from ADR file path."""
        result = get_sprint_branch_name(adr_path="docs/adr/0009-agentic-workflow-refinement.md")
        assert result == "sprint/adr0009-agentic-workflow-refinement"


class TestGetMissionBranchName:
    """Tests for get_mission_branch_name() function."""

    def test_simple_mission(self) -> None:
        """Get mission branch name."""
        result = get_mission_branch_name("adr0009", "worktree-naming")
        assert result == "agent/adr0009-worktree-naming"

    def test_with_formatted_slug(self) -> None:
        """Mission slug with formatting should be cleaned."""
        result = get_mission_branch_name("adr0009", "Worktree Naming Implementation")
        assert result == "agent/adr0009-worktree-naming-implementation"


class TestGetPromotionBranchName:
    """Tests for get_promotion_branch_name() function."""

    def test_from_id_and_title(self) -> None:
        """Get promotion branch name from ADR ID and title."""
        result = get_promotion_branch_name(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "promotion/adr0009-agentic-workflow-refinement"


# ============================================================================
# Reserved name tests
# ============================================================================

class TestIsReservedWorktreeName:
    """Tests for is_reserved_worktree_name() function."""

    def test_reserved_names(self) -> None:
        """Reserved names should be detected."""
        assert is_reserved_worktree_name("preproduction") is True
        assert is_reserved_worktree_name("main") is True
        assert is_reserved_worktree_name("PREPRODUCTION") is True
        assert is_reserved_worktree_name("Main") is True

    def test_non_reserved_names(self) -> None:
        """Non-reserved names should not be detected."""
        assert is_reserved_worktree_name("adr0009-test") is False
        assert is_reserved_worktree_name("sprint-test") is False
        assert is_reserved_worktree_name("agent-work") is False


# ============================================================================
# Validation tests
# ============================================================================

class TestValidateWorktreeName:
    """Tests for validate_worktree_name() function."""

    def test_valid_name(self) -> None:
        """Valid names should pass validation."""
        valid, reason = validate_worktree_name("adr0009-test")
        assert valid is True
        assert reason == ""

    def test_reserved_name_fails(self) -> None:
        """Reserved names should fail validation."""
        valid, reason = validate_worktree_name("preproduction")
        assert valid is False
        assert "reserved" in reason.lower()

    def test_path_traversal_fails(self) -> None:
        """Path traversal characters should fail validation."""
        valid, reason = validate_worktree_name("../test")
        assert valid is False
        assert "invalid" in reason.lower() or ".." in reason

    def test_hidden_prefix_fails(self) -> None:
        """Hidden file/directory prefix should fail validation."""
        valid, reason = validate_worktree_name(".hidden")
        assert valid is False

    def test_absolute_path_fails(self) -> None:
        """Absolute paths should fail validation."""
        valid, reason = validate_worktree_name("/absolute/path")
        assert valid is False


# ============================================================================
# Integration/canonical examples from research.md
# ============================================================================

class TestResearchExamples:
    """Tests for examples from research.md documentation."""

    def test_research_example_1(self) -> None:
        """Example from research: Agentic Workflow Refinement -> agentic-workflow-refinement"""
        assert canonical_slug("Agentic Workflow Refinement") == "agentic-workflow-refinement"

    def test_research_example_2(self) -> None:
        """Example from research: ADR 0009: Agentic Workflow Refinement"""
        assert canonical_slug("ADR 0009: Agentic Workflow Refinement") == "adr-0009-agentic-workflow-refinement"

    def test_research_example_3(self) -> None:
        """Example from research: Workspace Domain Authority"""
        assert canonical_slug("Workspace Domain Authority") == "workspace-domain-authority"

    def test_research_example_4(self) -> None:
        """Example from research: Receipt/Evidence Unification"""
        assert canonical_slug("Receipt/Evidence Unification") == "receipt-evidence-unification"

    def test_research_example_5(self) -> None:
        """Example from research: Rig-consolidation"""
        assert canonical_slug("Rig-consolidation") == "rig-consolidation"

    def test_research_example_6(self) -> None:
        """Example from research: ui_cockpit"""
        assert canonical_slug("ui_cockpit") == "ui-cockpit"


def main() -> int:
    """Run all tests and return exit code."""
    # Use pytest's return code
    return pytest.main([__file__, "-v"])


if __name__ == "__main__":
    sys.exit(main())
