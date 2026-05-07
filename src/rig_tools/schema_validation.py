from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_FAMILIES = {
    "rig.result.v1": "Docs/schemas/rig.result.v1.schema.json",
    "rig.event.v1": "Docs/schemas/rig.event.v1.schema.json",
    "rig.action.v1": "Docs/schemas/rig.action.v1.schema.json",
    "rig.agent_plan.v1": "Docs/schemas/rig.agent_plan.v1.schema.json",
    "rig.agent_run.v1": "Docs/schemas/rig.agent_run.v1.schema.json",
    "rig.loop_plan.v1": "Docs/schemas/rig.loop_plan.v1.schema.json",
    "rig.loop_run.v1": "Docs/schemas/rig.loop_run.v1.schema.json",
    "rig.context_pack.v1": "Docs/schemas/rig.context_pack.v1.schema.json",
    "rig.queue.v1": "Docs/schemas/rig.queue.v1.schema.json",
    "rig.checkpoint.v1": "Docs/schemas/rig.checkpoint.v1.schema.json",
    "rig.policy_decision.v1": "Docs/schemas/rig.policy_decision.v1.schema.json",
    "rig.memory_contract.v1": "Docs/schemas/rig.memory_contract.v1.schema.json",
    "rig.affected.v1": "Docs/schemas/rig.affected.v1.schema.json",
    "rig.swift_diagnostics.v1": "Docs/schemas/rig.swift_diagnostics.v1.schema.json",
    "rig.cache_metadata.v1": "Docs/schemas/rig.cache_metadata.v1.schema.json",
    "rig.git_commit_plan.v1": "Docs/schemas/rig.git_commit_plan.v1.schema.json",
    "rig.session_review_bundle.v1": "Docs/schemas/rig.session_review_bundle.v1.schema.json",
    "rig.local_patch.v1": "Docs/schemas/rig.local_patch.v1.schema.json",
    "rig.patch_validation.v1": "Docs/schemas/rig.patch_validation.v1.schema.json",
    "rig.duckdb_manifest.v1": "Docs/schemas/rig.duckdb_manifest.v1.schema.json",
    "rig.architecture_projection.v1": "Docs/schemas/rig.architecture_projection.v1.schema.json",
    "rig.textual_validation.v1": "Docs/schemas/rig.textual_validation.v1.schema.json",
    "rig.coupling_index.v1": "Docs/schemas/rig.coupling_index.v1.schema.json",
    "rig.architecture_projection_summary.v1": "Docs/schemas/rig.architecture_projection_summary.v1.schema.json",
    "rig.local_llm_summary.v1": "Docs/schemas/rig.local_llm_summary.v1.schema.json",
    "rig.embedding_index.v1": "Docs/schemas/rig.embedding_index.v1.schema.json",
    "rig.prompt_trace.v1": "Docs/schemas/rig.prompt_trace.v1.schema.json",
    "rig.prompt_regression_case.v1": "Docs/schemas/rig.prompt_regression_case.v1.schema.json",
    "rig.prompt_experiment.v1": "Docs/schemas/rig.prompt_experiment.v1.schema.json",
    "rig.proposal_swarm.v1": "Docs/schemas/rig.proposal_swarm.v1.schema.json",
    "rig.proposal_candidate.v1": "Docs/schemas/rig.proposal_candidate.v1.schema.json",
    "rig.os_sentinel.v1": "Docs/schemas/rig.os_sentinel.v1.schema.json",
    "rig.action_definition.v1": "Docs/schemas/rig.action_definition.v1.schema.json",
    "rig.command_plan.v1": "Docs/schemas/rig.command_plan.v1.schema.json",
    "rig.action_result.v1": "Docs/schemas/rig.action_result.v1.schema.json",
    "rig.state_store.v1": "Docs/schemas/rig.state_store.v1.schema.json",
    "rig.projection_manifest.v1": "Docs/schemas/rig.projection_manifest.v1.schema.json",
    "rig.loop_policy.v1": "Docs/schemas/rig.loop_policy.v1.schema.json",
    "rig.loop_run.v1": "Docs/schemas/rig.loop_run.v1.schema.json",
    "rig.loop_step.v1": "Docs/schemas/rig.loop_step.v1.schema.json",
    "rig.settings.v1": "Docs/schemas/rig.settings.v1.schema.json",
    "rig.gc_plan.v1": "Docs/schemas/rig.gc_plan.v1.schema.json",
    "rig.gc_run.v1": "Docs/schemas/rig.gc_run.v1.schema.json",
    "rig.docs_normalization_plan.v1": "Docs/schemas/rig.docs_normalization_plan.v1.schema.json",
    "rig.archive_manifest.v1": "Docs/schemas/rig.archive_manifest.v1.schema.json",
    "rig.scheduler_job.v1": "Docs/schemas/rig.scheduler_job.v1.schema.json",
    "rig.scheduler_run.v1": "Docs/schemas/rig.scheduler_run.v1.schema.json",
    "rig.vault_export.v1": "Docs/schemas/rig.vault_export.v1.schema.json",
    "rig.vault_note.v1": "Docs/schemas/rig.vault_note.v1.schema.json",
    "rig.doctor_report.v1": "Docs/schemas/rig.doctor_report.v1.schema.json",
    "rig.contract_audit.v1": "Docs/schemas/rig.contract_audit.v1.schema.json",
    "rig.release_readiness.v1": "Docs/schemas/rig.release_readiness.v1.schema.json",
    "rig.window_session.v1": "Docs/schemas/rig.window_session.v1.schema.json",
    "rig.solution_bias_profile.v1": "Docs/schemas/rig.solution_bias_profile.v1.schema.json",
    "rig.solution_ranking.v1": "Docs/schemas/rig.solution_ranking.v1.schema.json",
    "rig.model_behavior_observation.v1": "Docs/schemas/rig.model_behavior_observation.v1.schema.json",
    "rig.project_digest.v1": "Docs/schemas/rig.project_digest.v1.schema.json",
    "rig.project_adapter.v1": "Docs/schemas/rig.project_adapter.v1.schema.json",
    "rig.project_profile.v1": "Docs/schemas/rig.project_profile.v1.schema.json",
    "rig.structural_finding.v1": "Docs/schemas/rig.structural_finding.v1.schema.json",
    "rig.structural_report.v1": "Docs/schemas/rig.structural_report.v1.schema.json",
    "rig.tool_intent.v1": "Docs/schemas/rig.tool_intent.v1.schema.json",
    "rig.intent_decode_result.v1": "Docs/schemas/rig.intent_decode_result.v1.schema.json",
    "rig.project_blueprint.v1": "Docs/schemas/rig.project_blueprint.v1.schema.json",
    "rig.bootstrap_walkthrough.v1": "Docs/schemas/rig.bootstrap_walkthrough.v1.schema.json",
    "rig.system_benchmark.v1": "Docs/schemas/rig.system_benchmark.v1.schema.json",
    "rig.model_catalog.v1": "Docs/schemas/rig.model_catalog.v1.schema.json",
    "rig.model_download.v1": "Docs/schemas/rig.model_download.v1.schema.json",
    "rig.workspace.v1": "Docs/schemas/rig.workspace.v1.schema.json",
    "rig.diff_review.v1": "Docs/schemas/rig.diff_review.v1.schema.json",
    "rig.productization_report.v1": "Docs/schemas/rig.productization_report.v1.schema.json",
    "rig.validation_result.v1": "Docs/schemas/rig.validation_result.v1.schema.json",
    "rig.apply_receipt.v1": "Docs/schemas/rig.apply_receipt.v1.schema.json",
    "rig.review_bundle.v1": "Docs/schemas/rig.review_bundle.v1.schema.json",
    "rig.runtime_manifest.v1": "Docs/schemas/rig.runtime_manifest.v1.schema.json",
    "rig.agent_proposal.v1": "Docs/schemas/rig.agent_proposal.v1.schema.json",
    "rig.orchestration_job.v1": "Docs/schemas/rig.orchestration_job.v1.schema.json",
    "rig.orchestration_receipt.v1": "Docs/schemas/rig.orchestration_receipt.v1.schema.json",
}


@dataclass
class ValidationErrorInfo:
    path: str
    message: str


@dataclass
class ValidationResult:
    artifact_path: str
    schema_family: str
    status: str
    error_count: int
    errors: list[ValidationErrorInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "schema_family": self.schema_family,
            "status": self.status,
            "error_count": self.error_count,
            "errors": [error.__dict__ for error in self.errors],
        }


@dataclass
class ValidationSummary:
    schema_version: str
    status: str
    validated_artifact_count: int
    passed_count: int
    failed_count: int
    skipped_count: int
    validator: str
    results: list[ValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "validated_artifact_count": self.validated_artifact_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "validator": self.validator,
            "results": [result.to_dict() for result in self.results],
        }


def repo_rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except Exception:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(repo_root: Path, family: str) -> dict[str, Any]:
    schema_path = repo_root / SCHEMA_FAMILIES[family]
    return load_json(schema_path)


def list_families() -> list[str]:
    return sorted(SCHEMA_FAMILIES)


def _jsonschema_available() -> bool:
    try:
        import jsonschema  # noqa: F401
    except Exception:
        return False
    return True


def validator_name() -> str:
    return "jsonschema" if _jsonschema_available() else "builtin"


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    if isinstance(expected, str):
        return _type_ok(value, expected)
    return True


def _simple_validate(instance: Any, schema: dict[str, Any]) -> list[ValidationErrorInfo]:
    errors: list[ValidationErrorInfo] = []

    def walk(value: Any, subschema: dict[str, Any], path: str) -> None:
        expected_type = subschema.get("type")
        if expected_type and not _matches_type(value, expected_type):
            errors.append(ValidationErrorInfo(path=path or "$", message=f"expected {expected_type}"))
            return
        if "enum" in subschema and value not in subschema["enum"]:
            errors.append(ValidationErrorInfo(path=path or "$", message=f"expected one of {subschema['enum']}"))
        if expected_type == "object" and isinstance(value, dict):
            required = subschema.get("required", [])
            props = subschema.get("properties", {})
            for key in required:
                if key not in value:
                    errors.append(ValidationErrorInfo(path=f"{path}.{key}" if path else key, message="missing required field"))
            for key, prop_schema in props.items():
                if key in value:
                    walk(value[key], prop_schema, f"{path}.{key}" if path else key)
        if expected_type == "array" and isinstance(value, list):
            item_schema = subschema.get("items")
            if item_schema:
                for idx, item in enumerate(value):
                    walk(item, item_schema, f"{path}[{idx}]")

    walk(instance, schema, "")
    return errors


def validate_instance(instance: Any, schema: dict[str, Any], repo_root: Path| Optional = None) -> list[ValidationErrorInfo]:
    try:
        import jsonschema
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012
    except Exception:
        return _simple_validate(instance, schema)
    
    # Build a registry of all known schemas
    registry: Registry = Registry()
    if repo_root:
        for family, rel_path in SCHEMA_FAMILIES.items():
            s_path = repo_root / rel_path
            if s_path.exists():
                try:
                    s_data = json.loads(s_path.read_text(encoding="utf-8"))
                    if "$id" in s_data:
                        registry = Resource.from_contents(s_data) @ registry
                except Exception:
                    continue

    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    errors: list[ValidationErrorInfo] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = ".".join(str(part) for part in error.path) if error.path else "$"
        errors.append(ValidationErrorInfo(path=path, message=error.message))
    return errors


def _coerce_artifact_paths(repo_root: Path, artifact: Path) -> list[Path]:
    if artifact.is_dir():
        return sorted([p for p in artifact.glob("*.json") if p.is_file()], key=lambda p: p.name)
    return [artifact]


def _family_for_path(repo_root: Path, artifact: Path) -> str| Optional:
    name = artifact.name
    if name.startswith("commit-plan-") and artifact.parent.name == "git":
        return "rig.git_commit_plan.v1"
    if name == "latest.json" and artifact.parent.name == "os-sentinel":
        return "rig.os_sentinel.v1"
    if name.endswith(".json") and artifact.parent.name == "os-sentinel":
        return "rig.os_sentinel.v1"
    if name == "latest.json" and artifact.parent.name == "results":
        return "rig.result.v1"
    if name == "latest.json" and artifact.parent.name == "window":
        return "rig.window_session.v1"
    if name == "rig-duckdb-manifest.json":
        return "rig.duckdb_manifest.v1"
    if name == "patch.json" and artifact.parent.parent.name == "patches":
        return "rig.local_patch.v1"
    if name == "validation.json" and artifact.parent.parent.name == "patches":
        return "rig.patch_validation.v1"
    if name == "latest-summary.json" and artifact.parent.name == "llm":
        return "rig.local_llm_summary.v1"
    if name == "index.json" and artifact.parent.name == "embeddings":
        return "rig.embedding_index.v1"
    if name == "trace.json" and artifact.parent.parent.name == "traces" and artifact.parent.parent.parent.name == "prompts":
        return "rig.prompt_trace.v1"
    if name == "trace.json" and artifact.parent.parent.name == "quarantine" and artifact.parent.parent.parent.name == "prompts":
        return "rig.prompt_trace.v1"
    if name.endswith(".json") and artifact.parent.name == "cases" and artifact.parent.parent.parent.parent.name == "prompts":
        return "rig.prompt_regression_case.v1"
    if name == "latest.json" and artifact.parent.parent.name == "experiments" and artifact.parent.parent.parent.name == "prompts":
        return "rig.prompt_experiment.v1"
    if name == "query-results.json" and artifact.parent.name == "embeddings":
        return "rig.embedding_index.v1"
    if name == "latest.json" and artifact.parent.name == "context":
        return "rig.context_pack.v1"
    if name == "latest.json" and artifact.parent.name == "actions":
        return "rig.action.v1"
    if name == "latest.json" and artifact.parent.name == "loop":
        return "rig.loop_run.v1"
    if name == "latest.json" and artifact.parent.name == "policy":
        return "rig.policy_decision.v1"
    if name == "queue.json" and artifact.parent.name == "queue":
        return "rig.queue.v1"
    if name.endswith(".json") and artifact.parent.name == "checkpoints":
        return "rig.checkpoint.v1"
    if name == "agent-run.json" and artifact.parent.name == "runs":
        return "rig.agent_run.v1"
    if name.endswith(".json") and artifact.parent.name == "plans" and artifact.parent.parent.name == "agents":
        return "rig.agent_plan.v1"
    if name == "loop-run.json" and artifact.parent.name == "runs":
        return "rig.loop_run.v1"
    if name.endswith(".json") and artifact.parent.name == "plans" and artifact.parent.parent.name == "loop":
        return "rig.loop_plan.v1"
    if name in {"architecture-projections.json", "desired-state-index.json", "module-move-candidates.json", "overlap-index.json"}:
        return "rig.architecture_projection.v1"
    if name == "coupling-index.json":
        return "rig.coupling_index.v1"
    if name == "latest.json" and artifact.parent.name == "projections":
        return "rig.architecture_projection_summary.v1"
    if artifact.parent.name == "swift-diagnostics":
        return "rig.swift_diagnostics.v1"
    if artifact.parent.name == "cache-metadata":
        return "rig.cache_metadata.v1"
    if name == "rig-vault-export-manifest.json":
        return "rig.vault_export.v1"
    if name.startswith("vault-export-") and artifact.parent.name == "dry-run":
        return "rig.vault_export.v1"
    if artifact.parent.name == "affected":
        return "rig.affected.v1"
    if artifact.suffix == ".json" and "rig" in artifact.as_posix():
        stem = artifact.stem
        if artifact.parent.name == "memory":
            return "rig.memory_contract.v1"
        if artifact.parent.name == "swarm" and artifact.name == "latest.json":
            return "rig.proposal_swarm.v1"
        if artifact.parent.name == "swarm" and artifact.name == "swarm-run.json":
            return "rig.proposal_swarm.v1"
        if "candidates" in artifact.parts and artifact.name == "validation.json":
            return "rig.proposal_candidate.v1"
        if stem == "rig-session-review-bundle-bootstrap-session-review" or stem.endswith(".manifest"):
            return "rig.session_review_bundle.v1"
        if stem == "latest":
            return "rig.result.v1"
    return None


def _discover_family_paths(repo_root: Path, family: str) -> list[Path]:
    if family == "rig.os_sentinel.v1":
        out = repo_root / ".build" / "rig" / "os-sentinel"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.window_session.v1":
        out = repo_root / ".build" / "rig" / "window" / "sessions"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.projection_manifest.v1":
        out = repo_root / ".build" / "rig" / "projections"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("latest.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.settings.v1":
        out = repo_root / ".build" / "rig" / "settings"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("effective.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.loop_policy.v1":
        # Policies are currently not persisted as standalone files in .build by default
        return []
    if family == "rig.loop_run.v1":
        out = repo_root / ".build" / "rig" / "loops"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("**/loop-run.json") if p.is_file()], key=lambda p: p.parent.name)
    if family == "rig.loop_step.v1":
        out = repo_root / ".build" / "rig" / "loops"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("**/steps/*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.state_store.v1":
        out = repo_root / ".build" / "rig" / "state"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("status.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.action_definition.v1":
        # Action definitions are not currently written to .build by default
        return []
    if family == "rig.command_plan.v1":
        # Plans are currently ephemeral in MVP or written into action results
        return []
    if family == "rig.action_result.v1":
        out = repo_root / ".build" / "rig" / "actions"
        if not out.exists():
            return []
        # Find result.json in subdirectories
        return sorted([p for p in out.glob("**/result.json") if p.is_file()], key=lambda p: p.parent.name)
    if family == "rig.result.v1":
        return [repo_root / ".build" / "rig" / "results" / "latest.json"]
    if family == "rig.validation_result.v1":
        out = repo_root / ".build" / "rig" / "validation"
        return sorted([p for p in out.glob("**/validation.json") if p.is_file()], key=lambda p: p.as_posix()) if out.exists() else []
    if family == "rig.apply_receipt.v1":
        out = repo_root / ".build" / "rig" / "receipts"
        return sorted([p for p in out.glob("*_apply.json") if p.is_file()], key=lambda p: p.name) if out.exists() else []
    if family == "rig.review_bundle.v1":
        out = repo_root / ".build" / "rig" / "reviews"
        return sorted([p for p in out.glob("*/review.json") if p.is_file()], key=lambda p: p.as_posix()) if out.exists() else []
    if family == "rig.runtime_manifest.v1":
        return []
    if family == "rig.agent_proposal.v1":
        out = repo_root / ".build" / "rig" / "agent-proposals"
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name) if out.exists() else []
    if family == "rig.orchestration_job.v1":
        out = repo_root / ".build" / "rig" / "jobs"
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name) if out.exists() else []
    if family == "rig.orchestration_receipt.v1":
        out = repo_root / ".build" / "rig" / "receipts"
        return sorted([p for p in out.glob("*_orchestration.json") if p.is_file()], key=lambda p: p.name) if out.exists() else []
    if family == "rig.event.v1":
        out = repo_root / ".build" / "rig" / "events"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.jsonl") if p.is_file()], key=lambda p: p.name)
    if family == "rig.affected.v1":
        out = repo_root / ".build" / "rig" / "affected"
        if not out.exists():
            return []
        wanted = {"files.json", "targets.json", "risks.json", "profiles.json"}
        return sorted([p for p in out.glob("*.json") if p.is_file() and p.name in wanted], key=lambda p: p.name)
    if family == "rig.swift_diagnostics.v1":
        return [repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.json"]
    if family == "rig.cache_metadata.v1":
        out = repo_root / ".build" / "rig" / "cache-metadata"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.git_commit_plan.v1":
        out = repo_root / ".build" / "rig" / "git"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("commit-plan-*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.session_review_bundle.v1":
        out = repo_root / "Session-bundles"
        if not out.exists():
            out = repo_root / ".build" / "rig" / "session-bundles"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.manifest.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.duckdb_manifest.v1":
        path = repo_root / ".build" / "rig" / "rig-duckdb-manifest.json"
        return [path] if path.exists() else []
    if family in {"rig.architecture_projection.v1", "rig.coupling_index.v1"}:
        out = repo_root / "Docs" / "atlas"
        if not out.exists():
            return []
        if family == "rig.coupling_index.v1":
            path = out / "coupling-index.json"
            return [path] if path.exists() else []
        return [p for p in [out / "architecture-projections.json", out / "desired-state-index.json", out / "module-move-candidates.json", out / "overlap-index.json"] if p.exists()]
    if family == "rig.architecture_projection_summary.v1":
        path = repo_root / ".build" / "rig" / "projections" / "latest.json"
        return [path] if path.exists() else []
    if family == "rig.local_llm_summary.v1":
        out = repo_root / ".build" / "rig" / "llm"
        if not out.exists():
            return []
        paths = [p for p in out.glob("*summary.json") if p.is_file()]
        return sorted(paths, key=lambda p: p.name)
    if family == "rig.agent_plan.v1":
        out = repo_root / ".build" / "rig" / "agents" / "plans"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.agent_run.v1":
        out = repo_root / ".build" / "rig" / "agents" / "runs"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*/agent-run.json") if p.is_file()], key=lambda p: p.parent.name)
    if family == "rig.loop_plan.v1":
        out = repo_root / ".build" / "rig" / "loop" / "plans"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family == "rig.context_pack.v1":
        out = repo_root / ".build" / "rig" / "context"
        if not out.exists():
            return []
        paths = [out / "latest.json"]
        paths.extend(sorted([p for p in out.glob("*-context-pack.json") if p.is_file()], key=lambda p: p.name))
        return [p for p in paths if p.exists()]
    if family == "rig.action.v1":
        out = repo_root / ".build" / "rig" / "actions"
        if not out.exists():
            return []
        paths = [out / "latest.json"]
        paths.extend(sorted([p for p in out.glob("*.json") if p.is_file() and p.name != "latest.json"], key=lambda p: p.name))
        return [p for p in paths if p.exists()]
    if family == "rig.policy_decision.v1":
        out = repo_root / ".build" / "rig" / "policy"
        if not out.exists():
            return []
        paths = [out / "latest.json"]
        paths.extend(sorted([p for p in out.glob("*.json") if p.is_file() and p.name != "latest.json"], key=lambda p: p.name))
        return [p for p in paths if p.exists()]
    if family == "rig.queue.v1":
        path = repo_root / ".build" / "rig" / "queue" / "queue.json"
        return [path] if path.exists() else []
    if family == "rig.checkpoint.v1":
        out = repo_root / ".build" / "rig" / "queue" / "checkpoints"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*.json") if p.is_file()], key=lambda p: p.name)
    if family in {"rig.local_patch.v1", "rig.patch_validation.v1"}:
        out = repo_root / ".build" / "rig" / "patches"
        if not out.exists():
            return []
        if family == "rig.local_patch.v1":
            return sorted([p for p in out.glob("*/patch.json") if p.is_file()], key=lambda p: p.parent.name)
        return sorted([p for p in out.glob("*/validation.json") if p.is_file()], key=lambda p: p.parent.name)
    if family == "rig.loop_run.v1":
        out = repo_root / ".build" / "rig" / "loop" / "runs"
        if not out.exists():
            return [repo_root / ".build" / "rig" / "loop" / "latest.json"] if (repo_root / ".build" / "rig" / "loop" / "latest.json").exists() else []
        paths = [repo_root / ".build" / "rig" / "loop" / "latest.json"]
        paths.extend(sorted([p for p in out.glob("*/loop-run.json") if p.is_file()], key=lambda p: p.parent.name))
        return [p for p in paths if p.exists()]
    if family == "rig.embedding_index.v1":
        out = repo_root / ".build" / "rig" / "embeddings"
        if not out.exists():
            return []
        paths = [p for p in [out / "index.json", out / "query-results.json"] if p.exists()]
        return paths
    if family == "rig.prompt_trace.v1":
        out = repo_root / ".build" / "rig" / "prompts"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("**/trace.json") if p.is_file()], key=lambda p: p.as_posix())
    if family == "rig.prompt_regression_case.v1":
        out = repo_root / ".build" / "rig" / "prompts" / "regression"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("**/cases/*.json") if p.is_file()], key=lambda p: p.as_posix())
    if family == "rig.prompt_experiment.v1":
        out = repo_root / ".build" / "rig" / "prompts" / "experiments"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*/latest.json") if p.is_file()], key=lambda p: p.as_posix())
    if family == "rig.vault_export.v1":
        out = repo_root / ".build" / "rig" / "vault"
        if not out.exists():
            return []
        # Find vault export manifests
        paths = [p for p in out.glob("**/rig-vault-export-manifest.json") if p.is_file()]
        paths.extend([p for p in out.glob("**/*.manifest.json") if p.is_file() and "vault" in str(p)])
        return sorted(paths, key=lambda p: p.as_posix())
    if family == "rig.vault_note.v1":
        # Vault notes are markdown files, but we validate their JSON structure in tests
        # For schema validation purposes, we don't need to discover these files
        return []
    if family == "rig.memory_contract.v1":
        out = repo_root / ".build" / "rig" / "memory"
        if not out.exists():
            return []
        return [p for p in [out / "latest.json"] if p.exists()]
    if family == "rig.proposal_swarm.v1":
        out = repo_root / ".build" / "rig" / "swarm"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*/swarm-run.json") if p.is_file()], key=lambda p: p.parent.name)
    if family == "rig.proposal_candidate.v1":
        out = repo_root / ".build" / "rig" / "swarm"
        if not out.exists():
            return []
        return sorted([p for p in out.glob("*/candidates/*/validation.json") if p.is_file()], key=lambda p: p.as_posix())
    return []


def validate_artifacts(repo_root: Path, *, artifact_path: str| Optional = None, family: str| Optional = None) -> ValidationSummary:
    paths: list[Path] = []
    if artifact_path:
        path = (repo_root / artifact_path).resolve() if not Path(artifact_path).is_absolute() else Path(artifact_path)
        paths = _coerce_artifact_paths(repo_root, path)
    elif family:
        paths = _discover_family_paths(repo_root, family)
    else:
        paths = [repo_root / ".build" / "rig" / "results" / "latest.json"]

    results: list[ValidationResult] = []
    for path in paths:
        detected = family or _family_for_path(repo_root, path)
        if detected is None:
            results.append(ValidationResult(repo_rel(repo_root, path), "unknown", "skipped", 0, []))
            continue
        if detected == "rig.affected.v1":
            schema = {
                "files.json": {
                    "type": "object",
                    "required": ["mode", "changed_files"],
                    "properties": {
                        "schema_version": {"type": ["string", "null"]},
                        "mode": {"type": "string"},
                        "base": {"type": ["string", "null"]},
                        "head": {"type": ["string", "null"]},
                        "task": {"type": ["string", "null"]},
                        "changed_files": {"type": "array", "items": {"type": "string"}},
                        "unknown_files": {"type": "array", "items": {"type": "string"}},
                        "changed_file_count": {"type": ["integer", "null"]},
                    },
                },
                "targets.json": {
                    "type": "object",
                    "required": ["mode", "directly_affected_targets"],
                    "properties": {
                        "schema_version": {"type": ["string", "null"]},
                        "mode": {"type": "string"},
                        "base": {"type": ["string", "null"]},
                        "head": {"type": ["string", "null"]},
                        "task": {"type": ["string", "null"]},
                        "directly_affected_targets": {"type": "array", "items": {"type": "string"}},
                        "upstream_or_dependent_targets": {"type": "array", "items": {"type": "string"}},
                        "unknown_files": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "risks.json": {
                    "type": "object",
                    "required": ["mode", "affected_risk_count"],
                    "properties": {
                        "schema_version": {"type": ["string", "null"]},
                        "mode": {"type": "string"},
                        "base": {"type": ["string", "null"]},
                        "head": {"type": ["string", "null"]},
                        "task": {"type": ["string", "null"]},
                        "affected_risk_count": {"type": "integer"},
                        "affected_risks": {"type": "array"},
                        "grouped_by_category": {"type": "object"},
                        "grouped_by_severity": {"type": "object"},
                        "grouped_by_confidence": {"type": "object"},
                        "grouped_by_target": {"type": "object"},
                    },
                },
                "profiles.json": {
                    "type": "object",
                    "required": ["mode", "recommended_profiles"],
                    "properties": {
                        "schema_version": {"type": ["string", "null"]},
                        "mode": {"type": "string"},
                        "base": {"type": ["string", "null"]},
                        "head": {"type": ["string", "null"]},
                        "task": {"type": ["string", "null"]},
                        "recommended_profiles": {"type": "array", "items": {"type": "string"}},
                        "recommended_validation_commands": {"type": "array", "items": {"type": "string"}},
                        "target_notes": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }[path.name]
        else:
            schema = _load_schema(repo_root, detected)
        if detected == "rig.event.v1":
            total_errors: list[ValidationErrorInfo] = []
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception as exc:
                results.append(ValidationResult(repo_rel(repo_root, path), detected, "failed", 1, [ValidationErrorInfo(path="$", message=f"invalid JSONL: {exc}")]))
                continue
            for idx, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    instance = json.loads(line)
                except Exception as exc:
                    total_errors.append(ValidationErrorInfo(path=f"[{idx}]", message=f"invalid JSON: {exc}"))
                    continue
                total_errors.extend(validate_instance(instance, schema, repo_root=repo_root))
            status = "passed" if not total_errors else "failed"
            results.append(ValidationResult(repo_rel(repo_root, path), detected, status, len(total_errors), total_errors))
        else:
            try:
                instance = load_json(path)
            except Exception as exc:
                results.append(ValidationResult(repo_rel(repo_root, path), detected, "failed", 1, [ValidationErrorInfo(path="$", message=f"invalid JSON: {exc}")]))
                continue
            if detected == "rig.session_review_bundle.v1":
                schema = _load_schema(repo_root, "rig.session_review_bundle.v1")
            errors = validate_instance(instance, schema, repo_root=repo_root)
            status = "passed" if not errors else "failed"
            results.append(ValidationResult(repo_rel(repo_root, path), detected, status, len(errors), errors))

    passed = sum(1 for result in results if result.status == "passed")
    failed = sum(1 for result in results if result.status == "failed")
    skipped = sum(1 for result in results if result.status == "skipped")
    status = "passed" if failed == 0 else "failed"
    return ValidationSummary(
        schema_version="rig.schema-validation.v1",
        status=status,
        validated_artifact_count=len(results),
        passed_count=passed,
        failed_count=failed,
        skipped_count=skipped,
        validator=validator_name(),
        results=results,
    )
