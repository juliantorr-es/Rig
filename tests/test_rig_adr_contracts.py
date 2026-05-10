"""Tests for Rig ADR JSON contracts and schema validation.

These tests validate that:
1. The ADR JSON schema exists and is valid
2. ADR 0009 JSON exists and validates against the schema
3. ADR JSON workflow fields match naming helper output
4. The markdown_path exists
5. All required fields are present

DO NOT make tests depend on Markdown prose. Only check:
- JSON file existence
- JSON schema validation
- Naming consistency with helpers
- Required field presence
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._work_lib import (
    canonical_slug,
    derive_adr_directory_slug,
    get_adr_worktree_path,
    get_sprint_branch_name,
    get_mission_branch_name,
    get_promotion_branch_name,
    WORKTREES_ROOT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adr_schema_path():
    """Path to the ADR schema."""
    return REPO_ROOT / "docs" / "schemas" / "rig-adr.schema.json"


@pytest.fixture
def adr_0009_json_path():
    """Path to ADR 0009 JSON."""
    return REPO_ROOT / "docs" / "adr" / "0009-agentic-workflow-refinement.json"


@pytest.fixture
def adr_0009_markdown_path():
    """Path to ADR 0009 Markdown."""
    return REPO_ROOT / "docs" / "adr" / "0009-agentic-workflow-refinement.md"


@pytest.fixture
def adr_0010_json_path():
    """Path to ADR 0010 JSON."""
    return REPO_ROOT / "docs" / "adr" / "0010-repository-forge-bootstrap-and-promotion-abstraction.json"


@pytest.fixture
def adr_0010_markdown_path():
    """Path to ADR 0010 Markdown."""
    return REPO_ROOT / "docs" / "adr" / "0010-repository-forge-bootstrap-and-promotion-abstraction.md"


@pytest.fixture
def adr_0010_contract(adr_0010_json_path):
    """Load and return ADR 0010 contract."""
    with open(adr_0010_json_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def adr_schema(adr_schema_path):
    """Load and return the ADR schema."""
    with open(adr_schema_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def adr_0009_contract(adr_0009_json_path):
    """Load and return ADR 0009 contract."""
    with open(adr_0009_json_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestAdrSchema:
    """Tests for the ADR JSON schema."""

    def test_schema_exists(self, adr_schema_path):
        """Schema file must exist."""
        assert adr_schema_path.exists()
        assert adr_schema_path.is_file()

    def test_schema_is_valid_json(self, adr_schema_path):
        """Schema must be valid JSON."""
        with open(adr_schema_path, encoding="utf-8") as f:
            json.load(f)  # Will raise if invalid

    def test_schema_has_required_fields(self, adr_schema):
        """Schema must have required top-level fields."""
        required = ["$schema", "$id", "title", "description", "type", "required", "properties"]
        for field in required:
            assert field in adr_schema, f"Missing required field in schema: {field}"

    def test_schema_requires_contract_fields(self, adr_schema):
        """Schema must require all ADR contract fields."""
        required_fields = [
            "schema_version",
            "adr_id",
            "number",
            "title",
            "slug",
            "status",
            "markdown_path",
            "workflow",
        ]
        for field in required_fields:
            assert field in adr_schema["required"], f"Schema must require: {field}"

    def test_schema_defines_workflow(self, adr_schema):
        """Schema must define workflow object with required fields."""
        workflow = adr_schema["properties"]["workflow"]
        assert workflow["type"] == "object"
        assert "required" in workflow
        workflow_required = ["worktree_name", "ledger_path", "sprint_branch", "promotion_branch"]
        for field in workflow_required:
            assert field in workflow["required"], f"Workflow must require: {field}"

    def test_schema_defines_validation_gates(self, adr_schema):
        """Schema must define validation_gates array."""
        gates = adr_schema["properties"]["validation_gates"]
        assert gates["type"] == "array"
        assert "items" in gates
        assert "minItems" in gates
        assert gates["minItems"] >= 1

    def test_schema_defines_authority_boundaries(self, adr_schema):
        """Schema must define authority_boundaries array."""
        boundaries = adr_schema["properties"]["authority_boundaries"]
        assert boundaries["type"] == "array"
        assert "items" in boundaries
        assert "minItems" in boundaries
        assert boundaries["minItems"] >= 1

    def test_schema_defines_sprints(self, adr_schema):
        """Schema must define sprints array."""
        sprints = adr_schema["properties"]["sprints"]
        assert sprints["type"] == "array"

    def test_schema_additional_properties_false(self, adr_schema):
        """Schema must forbid additional properties."""
        assert adr_schema.get("additionalProperties") is False

    def test_schema_defines_reviewability_budget(self, adr_schema):
        """Schema must define reviewability_budget object."""
        budget_schema = adr_schema["properties"].get("reviewability_budget")
        assert budget_schema is not None, "Schema must define reviewability_budget"
        assert budget_schema["type"] == "object"
        assert "required" in budget_schema
        assert "properties" in budget_schema

    def test_schema_reviewability_budget_required_fields(self, adr_schema):
        """Schema must require all reviewability_budget fields."""
        budget_schema = adr_schema["properties"]["reviewability_budget"]
        required_fields = [
            "max_changed_files",
            "default_action",
            "override_allowed",
            "override_requires_reason",
            "applies_to",
            "rationale"
        ]
        for field in required_fields:
            assert field in budget_schema["required"], f"Schema must require {field} in reviewability_budget"


# ---------------------------------------------------------------------------
# ADR 0010 Contract Tests
# ---------------------------------------------------------------------------

class TestAdr0010Contract:
    """Tests for ADR 0010 JSON contract."""

    def test_contract_exists(self, adr_0010_json_path):
        """ADR 0010 JSON contract must exist."""
        assert adr_0010_json_path.exists()
        assert adr_0010_json_path.is_file()

    def test_contract_is_valid_json(self, adr_0010_json_path):
        """ADR 0010 contract must be valid JSON."""
        with open(adr_0010_json_path, encoding="utf-8") as f:
            json.load(f)  # Will raise if invalid

    def test_contract_validates_against_schema(self, adr_0010_contract, adr_schema):
        """ADR 0010 contract must validate against the schema."""
        from jsonschema import validate, ValidationError
        try:
            validate(instance=adr_0010_contract, schema=adr_schema)
        except ValidationError as e:
            pytest.fail(f"ADR 0010 contract validation failed: {e}")

    def test_contract_has_all_required_fields(self, adr_0010_contract):
        """ADR 0010 contract must have all required fields."""
        required_fields = [
            "schema_version",
            "adr_id",
            "number",
            "title",
            "slug",
            "status",
            "markdown_path",
            "workflow",
        ]
        for field in required_fields:
            assert field in adr_0010_contract, f"Missing required field: {field}"

    def test_schema_version(self, adr_0010_contract):
        """Contract must use schema version rig.adr.v1."""
        assert adr_0010_contract["schema_version"] == "rig.adr.v1"

    def test_adr_id(self, adr_0010_contract):
        """Contract must have correct adr_id."""
        assert adr_0010_contract["adr_id"] == "adr0010"

    def test_number(self, adr_0010_contract):
        """Contract must have correct number."""
        assert adr_0010_contract["number"] == "0010"

    def test_title(self, adr_0010_contract):
        """Contract must have correct title."""
        assert adr_0010_contract["title"] == "Repository Forge Bootstrap and Promotion Abstraction"

    def test_slug(self, adr_0010_contract):
        """Contract slug must match canonical_slug of title."""
        expected = canonical_slug("Repository Forge Bootstrap and Promotion Abstraction")
        assert adr_0010_contract["slug"] == expected

    def test_markdown_path_exists(self, adr_0010_contract, adr_0010_markdown_path):
        """Markdown path in contract must exist."""
        assert adr_0010_markdown_path.exists()
        assert str(adr_0010_markdown_path).endswith(adr_0010_contract["markdown_path"])

    def test_workflow_fields(self, adr_0010_contract):
        """Contract must have required workflow fields."""
        workflow = adr_0010_contract["workflow"]
        required = ["worktree_name", "ledger_path", "sprint_branch", "promotion_branch"]
        for field in required:
            assert field in workflow, f"Missing workflow field: {field}"

    def test_worktree_name_matches_naming_helper(self, adr_0010_contract):
        """worktree_name must match derive_adr_directory_slug output."""
        adr_path = adr_0010_contract["markdown_path"]
        expected = derive_adr_directory_slug(adr_path=adr_path)
        assert adr_0010_contract["workflow"]["worktree_name"] == expected

    def test_sprint_branch_matches_naming_helper(self, adr_0010_contract):
        """sprint_branch must match get_sprint_branch_name output."""
        adr_path = adr_0010_contract["markdown_path"]
        expected = get_sprint_branch_name(adr_path=adr_path)
        assert adr_0010_contract["workflow"]["sprint_branch"] == expected

    def test_promotion_branch_matches_naming_helper(self, adr_0010_contract):
        """promotion_branch must match get_promotion_branch_name output."""
        adr_path = adr_0010_contract["markdown_path"]
        expected = get_promotion_branch_name(adr_path=adr_path)
        assert adr_0010_contract["workflow"]["promotion_branch"] == expected

    def test_authority_boundaries_exist(self, adr_0010_contract):
        """Contract must have authority_boundaries."""
        assert "authority_boundaries" in adr_0010_contract
        assert isinstance(adr_0010_contract["authority_boundaries"], list)
        assert len(adr_0010_contract["authority_boundaries"]) > 0

    def test_authority_boundaries_structure(self, adr_0010_contract):
        """Each authority boundary must have required fields."""
        for boundary in adr_0010_contract["authority_boundaries"]:
            assert "id" in boundary
            assert "description" in boundary
            assert "must_not" in boundary
            assert isinstance(boundary["must_not"], list)
            assert len(boundary["must_not"]) > 0

    def test_validation_gates_exist(self, adr_0010_contract):
        """Contract must have validation_gates."""
        assert "validation_gates" in adr_0010_contract
        assert isinstance(adr_0010_contract["validation_gates"], list)
        # Must have all 13 core gates plus optional forge-specific gates
        assert len(adr_0010_contract["validation_gates"]) >= 13

    def test_validation_gates_include_13_core(self, adr_0010_contract):
        """Validation gates must include all 13 Rite of Deterministic Passage gates."""
        gate_ids = {g["id"] for g in adr_0010_contract["validation_gates"]}
        expected_gates = {
            "gate-1", "gate-2", "gate-3", "gate-4",
            "gate-5", "gate-6", "gate-7", "gate-8",
            "gate-9", "gate-10", "gate-11", "gate-12", "gate-13"
        }
        assert expected_gates.issubset(gate_ids), f"Missing gates: {expected_gates - gate_ids}"

    def test_validation_gates_include_forge_specific(self, adr_0010_contract):
        """Validation gates must include optional forge-specific gates."""
        gate_ids = {g["id"] for g in adr_0010_contract["validation_gates"]}
        # Should have forge-specific gates beyond the 13 core gates
        assert len(gate_ids) > 13
        # Check for at least one forge-specific gate
        forge_gates = {"gate-14-github", "gate-14-gitlab", "gate-14-gitea", "gate-15", "gate-16"}
        assert gate_ids.intersection(forge_gates), "Missing forge-specific gates"

    def test_sprints_exist(self, adr_0010_contract):
        """Contract must have sprints."""
        assert "sprints" in adr_0010_contract
        assert isinstance(adr_0010_contract["sprints"], list)
        assert len(adr_0010_contract["sprints"]) > 0

    def test_sprint_structure(self, adr_0010_contract):
        """Each sprint must have required fields."""
        for sprint in adr_0010_contract["sprints"]:
            assert "id" in sprint
            assert "title" in sprint
            assert "research_required" in sprint
            assert isinstance(sprint["research_required"], bool)

    def test_missions_in_sprints(self, adr_0010_contract):
        """Sprints must contain missions with required fields."""
        for sprint in adr_0010_contract["sprints"]:
            missions = sprint.get("missions", [])
            for mission in missions:
                assert "id" in mission
                assert "title" in mission
                assert "intent" in mission
                # branch_name is optional in schema but should be present
                if "branch_name" in mission:
                    assert mission["branch_name"].startswith("agent/adr0010-")

    def test_mission_branch_names_valid(self, adr_0010_contract):
        """Mission branch names must match get_mission_branch_name output."""
        adr_id = adr_0010_contract["adr_id"]
        for sprint in adr_0010_contract["sprints"]:
            for mission in sprint.get("missions", []):
                if "branch_name" in mission:
                    mission_slug = mission["id"]
                    expected = get_mission_branch_name(adr_id, mission_slug)
                    assert mission["branch_name"] == expected, \
                        f"Mission {mission['id']} branch mismatch: expected {expected}, got {mission['branch_name']}"

    def test_non_goals_exist(self, adr_0010_contract):
        """Contract must have non_goals."""
        assert "non_goals" in adr_0010_contract
        assert isinstance(adr_0010_contract["non_goals"], list)
        assert len(adr_0010_contract["non_goals"]) > 0

    def test_related_adrs_exist(self, adr_0010_contract):
        """Contract must have related_adrs."""
        assert "related_adrs" in adr_0010_contract
        assert isinstance(adr_0010_contract["related_adrs"], list)
        assert len(adr_0010_contract["related_adrs"]) > 0

    def test_related_adrs_include_dependencies(self, adr_0010_contract):
        """Related ADRs must include dependencies on ADR 0007 and ADR 0009."""
        related_ids = {r["id"] for r in adr_0010_contract["related_adrs"]}
        assert "adr0007" in related_ids, "Must depend on ADR 0007 (Workspace Domain Authority)"
        assert "adr0009" in related_ids, "Must depend on ADR 0009 (Agentic Workflow Refinement)"

    def test_related_adrs_structure(self, adr_0010_contract):
        """Each related ADR must have required fields."""
        for related in adr_0010_contract["related_adrs"]:
            assert "id" in related
            assert "path" in related
            assert related["id"].startswith("adr")
            assert related["path"].endswith(".md")

    def test_files_involved_exist(self, adr_0010_contract):
        """Contract must have files_involved."""
        assert "files_involved" in adr_0010_contract
        assert isinstance(adr_0010_contract["files_involved"], dict)
        assert len(adr_0010_contract["files_involved"]) > 0

    def test_files_involved_has_sprint_keys(self, adr_0010_contract):
        """files_involved must have sprint keys."""
        files = adr_0010_contract["files_involved"]
        # Should have sprint_1 through sprint_6
        for i in range(1, 7):
            assert f"sprint_{i}" in files, f"Missing sprint_{i} in files_involved"

    def test_created_updated_timestamps(self, adr_0010_contract):
        """Contract must have timestamps."""
        assert "created_at" in adr_0010_contract
        assert "updated_at" in adr_0010_contract
        # Validate datetime format
        for ts_field in ["created_at", "updated_at"]:
            ts = adr_0010_contract[ts_field]
            # Should be ISO 8601 format
            assert "T" in ts and "Z" in ts

    def test_reviewability_budget_exists(self, adr_0010_contract):
        """Contract must have reviewability_budget."""
        assert "reviewability_budget" in adr_0010_contract
        assert isinstance(adr_0010_contract["reviewability_budget"], dict)

    def test_reviewability_budget_max_changed_files(self, adr_0010_contract):
        """reviewability_budget must have max_changed_files == 300."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "max_changed_files" in budget
        assert budget["max_changed_files"] == 300

    def test_reviewability_budget_default_action(self, adr_0010_contract):
        """reviewability_budget must have default_action == block_promotion."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "default_action" in budget
        assert budget["default_action"] == "block_promotion"

    def test_reviewability_budget_override_requires_reason(self, adr_0010_contract):
        """reviewability_budget must have override_requires_reason == true."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "override_requires_reason" in budget
        assert budget["override_requires_reason"] is True

    def test_reviewability_budget_applies_to(self, adr_0010_contract):
        """reviewability_budget applies_to must include all forge modes."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "applies_to" in budget
        applies_to = budget["applies_to"]
        assert isinstance(applies_to, list)
        for mode in ["local_only", "github", "gitlab", "gitea", "future_adapter"]:
            assert mode in applies_to, f"Missing {mode} in applies_to"

    def test_reviewability_budget_rationale(self, adr_0010_contract):
        """reviewability_budget must have rationale."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "rationale" in budget
        assert isinstance(budget["rationale"], str)
        assert len(budget["rationale"]) > 0

    def test_reviewability_budget_override_allowed(self, adr_0010_contract):
        """reviewability_budget must have override_allowed == true."""
        budget = adr_0010_contract["reviewability_budget"]
        assert "override_allowed" in budget
        assert budget["override_allowed"] is True

    # --- Mission 10: GitHub API Backend Credential Model ---

    def test_github_api_backend_exists(self, adr_0010_contract):
        """ADR 0010 must have github_api_backend section."""
        assert "github_api_backend" in adr_0010_contract

    def test_github_api_backend_is_dict(self, adr_0010_contract):
        """github_api_backend must be a dictionary."""
        assert isinstance(adr_0010_contract["github_api_backend"], dict)

    def test_github_api_backend_default_backend_is_cli(self, adr_0010_contract):
        """github_api_backend default_backend must be 'cli'."""
        backend = adr_0010_contract["github_api_backend"]
        assert backend["default_backend"] == "cli"

    def test_github_api_backend_allowed_libraries(self, adr_0010_contract):
        """github_api_backend allowed_libraries must include pygithub and direct_rest."""
        backend = adr_0010_contract["github_api_backend"]
        assert "allowed_libraries" in backend
        libraries = backend["allowed_libraries"]
        assert "pygithub" in libraries
        assert "direct_rest" in libraries

    def test_github_api_backend_redaction_required(self, adr_0010_contract):
        """github_api_backend redaction_required must be true."""
        backend = adr_0010_contract["github_api_backend"]
        assert backend["redaction_required"] is True

    def test_github_api_backend_fail_closed_on_missing_credentials(
        self, adr_0010_contract
    ):
        """github_api_backend fail_closed_on_missing_credentials must be true."""
        backend = adr_0010_contract["github_api_backend"]
        assert backend["fail_closed_on_missing_credentials"] is True

    def test_github_api_backend_token_sources_allowed(self, adr_0010_contract):
        """github_api_backend must have token_sources_allowed array."""
        backend = adr_0010_contract["github_api_backend"]
        assert "token_sources_allowed" in backend
        allowed = backend["token_sources_allowed"]
        assert isinstance(allowed, list)
        assert "environment_variable" in allowed
        assert "os_credential_store" in allowed
        assert "github_app_installation_token" in allowed
        assert "explicit_untracked_token_path" in allowed

    def test_github_api_backend_token_sources_forbidden(self, adr_0010_contract):
        """github_api_backend must have token_sources_forbidden array."""
        backend = adr_0010_contract["github_api_backend"]
        assert "token_sources_forbidden" in backend
        forbidden = backend["token_sources_forbidden"]
        assert isinstance(forbidden, list)
        assert "logs" in forbidden
        assert "promotion_artifact_metadata" in forbidden

    def test_github_api_backend_minimum_permissions(self, adr_0010_contract):
        """github_api_backend must have minimum_permissions array."""
        backend = adr_0010_contract["github_api_backend"]
        assert "minimum_permissions" in backend
        perms = backend["minimum_permissions"]
        assert isinstance(perms, list)
        assert len(perms) > 0
        # Check structure of each permission
        for perm in perms:
            assert "capability" in perm
            assert "github_permission" in perm
            assert "access" in perm
        # Check specific required permissions exist
        capabilities = {p["capability"] for p in perms}
        assert "create_pull_request" in capabilities
        assert "repository_contents_read" in capabilities
        assert "repository_metadata_read" in capabilities

    def test_github_api_backend_no_token_literals(self, adr_0010_contract):
        """github_api_backend must not contain real-looking token strings."""
        import json
        backend = adr_0010_contract["github_api_backend"]
        backend_json = json.dumps(backend)
        # Check for patterns that look like GitHub tokens
        forbidden_patterns = [
            "ghp_",  # GitHub fine-grained PAT prefix
            "gho_",  # GitHub OAuth token prefix
            "ghu_",  # GitHub user-to-server token prefix
            "ghs_",  # GitHub server-to-server token prefix
            "ghr_",  # GitHub refresh token prefix
        ]
        for pattern in forbidden_patterns:
            assert pattern not in backend_json.lower(), (
                f"Token literal detected: {pattern}"
            )


# ---------------------------------------------------------------------------
# ADR 0009 Contract Tests
# ---------------------------------------------------------------------------

class TestAdr0009Contract:
    """Tests for ADR 0009 JSON contract."""

    def test_contract_exists(self, adr_0009_json_path):
        """ADR 0009 JSON contract must exist."""
        assert adr_0009_json_path.exists()
        assert adr_0009_json_path.is_file()

    def test_contract_is_valid_json(self, adr_0009_json_path):
        """ADR 0009 contract must be valid JSON."""
        with open(adr_0009_json_path, encoding="utf-8") as f:
            json.load(f)  # Will raise if invalid

    def test_contract_validates_against_schema(self, adr_0009_contract, adr_schema):
        """ADR 0009 contract must validate against the schema."""
        from jsonschema import validate, ValidationError
        try:
            validate(instance=adr_0009_contract, schema=adr_schema)
        except ValidationError as e:
            pytest.fail(f"ADR 0009 contract validation failed: {e}")

    def test_contract_has_all_required_fields(self, adr_0009_contract):
        """ADR 0009 contract must have all required fields."""
        required_fields = [
            "schema_version",
            "adr_id",
            "number",
            "title",
            "slug",
            "status",
            "markdown_path",
            "workflow",
        ]
        for field in required_fields:
            assert field in adr_0009_contract, f"Missing required field: {field}"

    def test_schema_version(self, adr_0009_contract):
        """Contract must use schema version rig.adr.v1."""
        assert adr_0009_contract["schema_version"] == "rig.adr.v1"

    def test_adr_id(self, adr_0009_contract):
        """Contract must have correct adr_id."""
        assert adr_0009_contract["adr_id"] == "adr0009"

    def test_number(self, adr_0009_contract):
        """Contract must have correct number."""
        assert adr_0009_contract["number"] == "0009"

    def test_title(self, adr_0009_contract):
        """Contract must have correct title."""
        assert adr_0009_contract["title"] == "Agentic Workflow Refinement"

    def test_slug(self, adr_0009_contract):
        """Contract slug must match canonical_slug of title."""
        expected = canonical_slug("Agentic Workflow Refinement")
        assert adr_0009_contract["slug"] == expected

    def test_markdown_path_exists(self, adr_0009_contract, adr_0009_markdown_path):
        """Markdown path in contract must exist."""
        assert adr_0009_markdown_path.exists()
        assert str(adr_0009_markdown_path).endswith(adr_0009_contract["markdown_path"])

    def test_workflow_fields(self, adr_0009_contract):
        """Contract must have required workflow fields."""
        workflow = adr_0009_contract["workflow"]
        required = ["worktree_name", "ledger_path", "sprint_branch", "promotion_branch"]
        for field in required:
            assert field in workflow, f"Missing workflow field: {field}"

    def test_worktree_name_matches_naming_helper(self, adr_0009_contract):
        """worktree_name must match derive_adr_directory_slug output."""
        adr_path = adr_0009_contract["markdown_path"]
        expected = derive_adr_directory_slug(adr_path=adr_path)
        assert adr_0009_contract["workflow"]["worktree_name"] == expected

    def test_sprint_branch_matches_naming_helper(self, adr_0009_contract):
        """sprint_branch must match get_sprint_branch_name output."""
        adr_path = adr_0009_contract["markdown_path"]
        expected = get_sprint_branch_name(adr_path=adr_path)
        assert adr_0009_contract["workflow"]["sprint_branch"] == expected

    def test_promotion_branch_matches_naming_helper(self, adr_0009_contract):
        """promotion_branch must match get_promotion_branch_name output."""
        adr_path = adr_0009_contract["markdown_path"]
        expected = get_promotion_branch_name(adr_path=adr_path)
        assert adr_0009_contract["workflow"]["promotion_branch"] == expected

    def test_authority_boundaries_exist(self, adr_0009_contract):
        """Contract must have authority_boundaries."""
        assert "authority_boundaries" in adr_0009_contract
        assert isinstance(adr_0009_contract["authority_boundaries"], list)
        assert len(adr_0009_contract["authority_boundaries"]) > 0

    def test_authority_boundaries_structure(self, adr_0009_contract):
        """Each authority boundary must have required fields."""
        for boundary in adr_0009_contract["authority_boundaries"]:
            assert "id" in boundary
            assert "description" in boundary
            assert "must_not" in boundary
            assert isinstance(boundary["must_not"], list)
            assert len(boundary["must_not"]) > 0

    def test_validation_gates_exist(self, adr_0009_contract):
        """Contract must have validation_gates."""
        assert "validation_gates" in adr_0009_contract
        assert isinstance(adr_0009_contract["validation_gates"], list)
        # Must have all 13 gates
        assert len(adr_0009_contract["validation_gates"]) >= 13

    def test_validation_gates_structure(self, adr_0009_contract):
        """Each validation gate must have required fields."""
        for gate in adr_0009_contract["validation_gates"]:
            assert "id" in gate
            assert "description" in gate
            assert "blocking" in gate
            assert isinstance(gate["blocking"], bool)

    def test_rite_of_deterministic_passage(self, adr_0009_contract):
        """Validation gates must include all 13 Rite of Deterministic Passage gates."""
        gate_ids = {g["id"] for g in adr_0009_contract["validation_gates"]}
        expected_gates = {
            "gate-1", "gate-2", "gate-3", "gate-4",
            "gate-5", "gate-6", "gate-7", "gate-8",
            "gate-9", "gate-10", "gate-11", "gate-12", "gate-13"
        }
        assert expected_gates.issubset(gate_ids), f"Missing gates: {expected_gates - gate_ids}"

    def test_sprints_exist(self, adr_0009_contract):
        """Contract must have sprints."""
        assert "sprints" in adr_0009_contract
        assert isinstance(adr_0009_contract["sprints"], list)
        assert len(adr_0009_contract["sprints"]) > 0

    def test_sprint_structure(self, adr_0009_contract):
        """Each sprint must have required fields."""
        for sprint in adr_0009_contract["sprints"]:
            assert "id" in sprint
            assert "title" in sprint
            assert "research_required" in sprint
            assert isinstance(sprint["research_required"], bool)

    def test_missions_in_sprints(self, adr_0009_contract):
        """Sprints must contain missions with required fields."""
        for sprint in adr_0009_contract["sprints"]:
            missions = sprint.get("missions", [])
            for mission in missions:
                assert "id" in mission
                assert "title" in mission
                assert "intent" in mission
                # branch_name is optional
                if "branch_name" in mission:
                    assert mission["branch_name"].startswith("agent/adr0009-")

    def test_mission_branch_name_matches_helper(self, adr_0009_contract):
        """Mission branch names must match get_mission_branch_name output."""
        for sprint in adr_0009_contract["sprints"]:
            for mission in sprint.get("missions", []):
                if "branch_name" in mission:
                    adr_id = adr_0009_contract["adr_id"]
                    mission_slug = mission["id"]
                    expected = get_mission_branch_name(adr_id, mission_slug)
                    assert mission["branch_name"] == expected, \
                        f"Mission {mission['id']} branch mismatch: expected {expected}, got {mission['branch_name']}"

    def test_non_goals_exist(self, adr_0009_contract):
        """Contract must have non_goals."""
        assert "non_goals" in adr_0009_contract
        assert isinstance(adr_0009_contract["non_goals"], list)
        assert len(adr_0009_contract["non_goals"]) > 0

    def test_related_adrs_exist(self, adr_0009_contract):
        """Contract must have related_adrs."""
        assert "related_adrs" in adr_0009_contract
        assert isinstance(adr_0009_contract["related_adrs"], list)
        assert len(adr_0009_contract["related_adrs"]) > 0

    def test_related_adrs_structure(self, adr_0009_contract):
        """Each related ADR must have required fields."""
        for related in adr_0009_contract["related_adrs"]:
            assert "id" in related
            assert "path" in related
            assert related["id"].startswith("adr")
            assert related["path"].endswith(".md")

    def test_files_involved_exist(self, adr_0009_contract):
        """Contract must have files_involved."""
        assert "files_involved" in adr_0009_contract
        assert isinstance(adr_0009_contract["files_involved"], dict)
        assert len(adr_0009_contract["files_involved"]) > 0

    def test_created_updated_timestamps(self, adr_0009_contract):
        """Contract must have timestamps."""
        assert "created_at" in adr_0009_contract
        assert "updated_at" in adr_0009_contract
        # Validate datetime format
        for ts_field in ["created_at", "updated_at"]:
            ts = adr_0009_contract[ts_field]
            # Should be ISO 8601 format
            assert "T" in ts and "Z" in ts


# ---------------------------------------------------------------------------
# Naming Helper Agreement Tests
# ---------------------------------------------------------------------------

class TestNamingHelperAgreement:
    """Tests that naming helpers produce values matching ADR contracts."""

    def test_canonical_slug_adr_0009_title(self):
        """canonical_slug must produce expected slug for ADR 0009 title."""
        result = canonical_slug("Agentic Workflow Refinement")
        assert result == "agentic-workflow-refinement"

    def test_canonical_slug_adr_0010_title(self):
        """canonical_slug must produce expected slug for ADR 0010 title."""
        result = canonical_slug("Repository Forge Bootstrap and Promotion Abstraction")
        assert result == "repository-forge-bootstrap-and-promotion-abstraction"

    def test_derive_adr_directory_slug_from_path_0009(self):
        """derive_adr_directory_slug must work from ADR 0009 file path."""
        adr_path = "docs/adr/0009-agentic-workflow-refinement.md"
        result = derive_adr_directory_slug(adr_path=adr_path)
        assert result == "adr0009-agentic-workflow-refinement"

    def test_derive_adr_directory_slug_from_path_0010(self):
        """derive_adr_directory_slug must work from ADR 0010 file path."""
        adr_path = "docs/adr/0010-repository-forge-bootstrap-and-promotion-abstraction.md"
        result = derive_adr_directory_slug(adr_path=adr_path)
        assert result == "adr0010-repository-forge-bootstrap-and-promotion-abstraction"

    def test_derive_adr_directory_slug_from_id_and_title_0009(self):
        """derive_adr_directory_slug must work from ADR 0009 ID and title."""
        result = derive_adr_directory_slug(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "adr0009-agentic-workflow-refinement"

    def test_derive_adr_directory_slug_from_id_and_title_0010(self):
        """derive_adr_directory_slug must work from ADR 0010 ID and title."""
        result = derive_adr_directory_slug(adr_id="adr0010", adr_title="Repository Forge Bootstrap and Promotion Abstraction")
        assert result == "adr0010-repository-forge-bootstrap-and-promotion-abstraction"

    def test_get_adr_worktree_path_0009(self):
        """get_adr_worktree_path must produce expected path for ADR 0009."""
        result = get_adr_worktree_path(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        expected = WORKTREES_ROOT / "adr0009-agentic-workflow-refinement"
        assert result == expected

    def test_get_adr_worktree_path_0010(self):
        """get_adr_worktree_path must produce expected path for ADR 0010."""
        result = get_adr_worktree_path(adr_id="adr0010", adr_title="Repository Forge Bootstrap and Promotion Abstraction")
        expected = WORKTREES_ROOT / "adr0010-repository-forge-bootstrap-and-promotion-abstraction"
        assert result == expected

    def test_get_sprint_branch_name_0009(self):
        """get_sprint_branch_name must produce expected branch for ADR 0009."""
        result = get_sprint_branch_name(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "sprint/adr0009-agentic-workflow-refinement"

    def test_get_sprint_branch_name_0010(self):
        """get_sprint_branch_name must produce expected branch for ADR 0010."""
        result = get_sprint_branch_name(adr_id="adr0010", adr_title="Repository Forge Bootstrap and Promotion Abstraction")
        assert result == "sprint/adr0010-repository-forge-bootstrap-and-promotion-abstraction"

    def test_get_promotion_branch_name_0009(self):
        """get_promotion_branch_name must produce expected branch for ADR 0009."""
        result = get_promotion_branch_name(adr_id="adr0009", adr_title="Agentic Workflow Refinement")
        assert result == "promotion/adr0009-agentic-workflow-refinement"

    def test_get_promotion_branch_name_0010(self):
        """get_promotion_branch_name must produce expected branch for ADR 0010."""
        result = get_promotion_branch_name(adr_id="adr0010", adr_title="Repository Forge Bootstrap and Promotion Abstraction")
        assert result == "promotion/adr0010-repository-forge-bootstrap-and-promotion-abstraction"

    def test_get_mission_branch_name_0009(self):
        """get_mission_branch_name must produce expected branch for ADR 0009."""
        result = get_mission_branch_name("adr0009", "sprint-worktree-naming")
        assert result == "agent/adr0009-sprint-worktree-naming"

    def test_get_mission_branch_name_0010(self):
        """get_mission_branch_name must produce expected branch for ADR 0010."""
        result = get_mission_branch_name("adr0010", "sprint-adapter-interface")
        assert result == "agent/adr0010-sprint-adapter-interface"


# ---------------------------------------------------------------------------
# Integration Test
# ---------------------------------------------------------------------------

class TestIntegration:
    """Integration tests for ADR contract loading and validation."""

    def test_load_and_validate_all(self, adr_schema_path, adr_0009_json_path, adr_0010_json_path):
        """Load schema and contracts from disk and validate."""
        from jsonschema import validate, ValidationError
        import json

        # Load from disk (not fixtures) to test actual files
        with open(adr_schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        # Validate ADR 0009
        with open(adr_0009_json_path, encoding="utf-8") as f:
            contract_0009 = json.load(f)
        validate(instance=contract_0009, schema=schema)

        # Validate ADR 0010
        with open(adr_0010_json_path, encoding="utf-8") as f:
            contract_0010 = json.load(f)
        validate(instance=contract_0010, schema=schema)

    def test_contract_and_markers_match_0009(self, adr_0009_contract):
        """Verify ADR 0009 contract values match naming helpers and naming policy."""
        self._verify_adr_contract_naming_consistency(adr_0009_contract)

    def test_contract_and_markers_match_0010(self, adr_0010_contract):
        """Verify ADR 0010 contract values match naming helpers and naming policy."""
        self._verify_adr_contract_naming_consistency(adr_0010_contract)

    def _verify_adr_contract_naming_consistency(self, contract):
        """Verify contract values match naming helpers and naming policy."""
        # All these should be derivable from the ADR identity
        adr_id = contract["adr_id"]
        title = contract["title"]
        slug = contract["slug"]
        workflow = contract["workflow"]

        # Check slug
        assert slug == canonical_slug(title)

        # Check workflow fields
        assert workflow["worktree_name"] == f"{adr_id}-{slug}"
        assert workflow["ledger_path"] == f".rig/work/adr/{adr_id}-{slug}"
        assert workflow["sprint_branch"] == f"sprint/{adr_id}-{slug}"
        assert workflow["promotion_branch"] == f"promotion/{adr_id}-{slug}"
        assert workflow.get("mission_branch_prefix") == f"agent/{adr_id}-"


def main() -> int:
    """Run all tests and return exit code."""
    return pytest.main([__file__, "-v"])


if __name__ == "__main__":
    sys.exit(main())
