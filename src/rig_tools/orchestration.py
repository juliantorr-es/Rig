from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig.config.loader import merge_config
from rig_tools.agent_proposals import create_proposal, proposal_to_command_plan
from rig.logging.jsonl_logger import JsonlLogger
from rig_tools.runtime_registry import provider_for_id
from rig_tools.workspace_governance import WorkspaceGovernance


JOB_SCHEMA_VERSION = "rig.orchestration_job.v1"
RECEIPT_SCHEMA_VERSION = "rig.orchestration_receipt.v1"
DEFAULT_REQUESTED_STEPS = [
    "create_workspace",
    "generate_proposal",
    "decode_proposal",
    "accept_proposal",
    "execute_plan",
    "run_validators",
    "generate_review",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _root(repo_root: Path) -> Path:
    out = repo_root / ".build" / "rig" / "jobs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _job_path(repo_root: Path, job_id: str) -> Path:
    return _root(repo_root) / f"{job_id}.json"


def _receipt_path(repo_root: Path, job_id: str) -> Path:
    return repo_root / ".build" / "rig" / "receipts" / f"{job_id}_orchestration.json"


def _log(repo_root: Path) -> JsonlLogger:
    return JsonlLogger(repo_root / ".build" / "rig" / "logs")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def list_jobs(repo_root: Path) -> list[dict[str, Any]]:
    out = []
    for path in sorted(_root(repo_root).glob("*.json"), key=lambda p: p.name):
        item = _load_json(path, None)
        if isinstance(item, dict):
            out.append(item)
    return out


def load_job(repo_root: Path, job_id: str) -> dict[str, Any] | None:
    path = _job_path(repo_root, job_id)
    payload = _load_json(path, None)
    return payload if isinstance(payload, dict) else None


def _save_job(repo_root: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    _write_json(_job_path(repo_root, job["job_id"]), job)


def create_job(repo_root: Path, *, task: str, provider_id: str, model_id: str | None = None, workspace_id: str | None = None, requested_steps: list[str] | None = None) -> dict[str, Any]:
    job = {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": uuid.uuid4().hex[:12],
        "task": task,
        "repo_root": str(repo_root),
        "workspace_id": workspace_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "requested_steps": requested_steps or list(DEFAULT_REQUESTED_STEPS),
        "completed_steps": [],
        "current_step": None,
        "status": "queued",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "blocked_reason": None,
        "proposal_id": None,
        "plan_id": None,
        "execution_receipt_id": None,
        "validation_receipt_ids": [],
        "review_bundle_hash": None,
        "authoritative": True,
    }
    _save_job(repo_root, job)
    _log(repo_root).write_event(job["job_id"], level="info", event="job_created", message="job created", metadata={"task": task, "provider_id": provider_id}, command_id=job["job_id"])
    return job


def inspect_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    job = load_job(repo_root, job_id)
    if not job:
        return {"status": "missing", "job_id": job_id}
    return job


def cancel_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    job = load_job(repo_root, job_id)
    if not job:
        return {"status": "missing", "job_id": job_id}
    job["status"] = "cancelled"
    job["blocked_reason"] = "cancelled"
    _save_job(repo_root, job)
    _write_receipt(repo_root, job, status="cancelled", failed_step=job.get("current_step"), blocked_reason="cancelled")
    _log(repo_root).write_event(job_id, level="warning", event="job_cancelled", message="job cancelled", command_id=job_id, metadata={"job_id": job_id})
    return job


def retry_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    job = load_job(repo_root, job_id)
    if not job:
        return {"status": "missing", "job_id": job_id}
    if job.get("status") == "cancelled":
        return {"status": "blocked", "blocked_reason": "cancelled"}
    job["status"] = "queued"
    job["blocked_reason"] = None
    _save_job(repo_root, job)
    return job


def _write_receipt(repo_root: Path, job: dict[str, Any], *, status: str, failed_step: str | None = None, blocked_reason: str | None = None) -> dict[str, Any]:
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": uuid.uuid4().hex[:12],
        "job_id": job["job_id"],
        "workspace_id": job.get("workspace_id"),
        "proposal_id": job.get("proposal_id"),
        "plan_id": job.get("plan_id"),
        "execution_receipt_id": job.get("execution_receipt_id"),
        "validation_receipt_ids": job.get("validation_receipt_ids") or [],
        "review_bundle_hash": job.get("review_bundle_hash"),
        "status": status,
        "started_at": job.get("created_at"),
        "finished_at": utc_now(),
        "failed_step": failed_step,
        "blocked_reason": blocked_reason,
        "authoritative": True,
    }
    _write_json(_receipt_path(repo_root, job["job_id"]), receipt)
    return receipt


def run_job(repo_root: Path, job_id: str, *, until: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    job = load_job(repo_root, job_id)
    if not job:
        return {"status": "missing", "job_id": job_id}
    if job.get("status") == "cancelled":
        return {"status": "cancelled", "job_id": job_id}
    if dry_run:
        preview = dict(job)
        preview["status"] = "blocked"
        preview["blocked_reason"] = "dry_run"
        return preview
    policy = merge_config(repo_root).get("policy") or {}
    ws = WorkspaceGovernance(repo_root)
    provider = provider_for_id(repo_root, str(job["provider_id"]))
    job["status"] = "running"
    _save_job(repo_root, job)
    _log(repo_root).write_event(job_id, level="info", event="job_started", message="job started", command_id=job_id, metadata={"job_id": job_id})

    def stop(reason: str, step: str | None = None) -> dict[str, Any]:
        job["status"] = "blocked"
        job["blocked_reason"] = reason
        job["current_step"] = step
        _save_job(repo_root, job)
        receipt = _write_receipt(repo_root, job, status="blocked", failed_step=step, blocked_reason=reason)
        _log(repo_root).write_event(job_id, level="warning", event="job_blocked", message=reason, command_id=job_id, metadata={"job_id": job_id, "step": step})
        return {
            "status": "blocked",
            "job": job,
            "receipt": receipt,
            "next": _next_commands(reason, job),
            "blocked_reason": reason,
        }

    if not job.get("workspace_id"):
        created = ws.create_workspace(job["task"])
        job["workspace_id"] = created.payload["workspace_id"]
        job["completed_steps"].append("create_workspace")
        job["current_step"] = "create_workspace"
        _save_job(repo_root, job)
        if until == "create_workspace":
            return stop("create_workspace_complete", "create_workspace")

    try:
        proposal_result = provider.invoke({"workspace_id": job["workspace_id"], "model_id": job.get("model_id") or "static", "static_output": json.dumps({"intent": {"kind": "plan"}, "decoded_actions": [{"type": "command", "argv": ["python", "-m", "pytest", "-q"]}], "files_referenced": [], "confidence": 0.8, "risk_level": "medium"})})
    except Exception as exc:
        return stop("provider_unavailable", "generate_proposal")
    proposal = create_proposal(repo_root, workspace_id=job["workspace_id"], provider_id=provider.id(), model_id=str(job.get("model_id") or "static"), raw_output=proposal_result.raw_output, provider_manifest=provider.manifest())
    job["proposal_id"] = proposal["proposal_id"]
    job["completed_steps"].append("generate_proposal")
    job["current_step"] = "generate_proposal"
    _save_job(repo_root, job)
    if proposal.get("status") == "blocked":
        return stop("provider_trust_tier_blocked", "decode_proposal")

    job["completed_steps"].append("decode_proposal")
    job["current_step"] = "decode_proposal"
    _save_job(repo_root, job)
    if policy.get("allow_auto_accept_proposals", False) is not True:
        return stop("proposal_acceptance_required", "accept_proposal")

    plan = proposal_to_command_plan(repo_root, proposal)
    job["plan_id"] = plan.plan_id
    _save_job(repo_root, job)
    if policy.get("allow_auto_execute", False) is not True:
        return stop("execution_approval_required", "execute_plan")

    return stop("apply_required", "generate_review")


def _next_commands(reason: str, job: dict[str, Any]) -> list[str]:
    if reason == "proposal_acceptance_required":
        return [f"rig agent inspect {job.get('proposal_id')}", f"rig agent accept {job.get('proposal_id')}"]
    if reason == "execution_approval_required":
        return [f"rig job inspect {job.get('job_id')}", f"rig run --task {job.get('task')} --provider {job.get('provider_id')} --dry-run"]
    if reason == "apply_required":
        return [f"rig workspace review {job.get('workspace_id')}", f"rig workspace apply {job.get('workspace_id')}"]
    return [f"rig job inspect {job.get('job_id')}"]


def list_jobs_summary(repo_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "job_id": job.get("job_id"),
            "task": job.get("task"),
            "status": job.get("status"),
            "current_step": job.get("current_step"),
            "provider_id": job.get("provider_id"),
            "workspace_id": job.get("workspace_id"),
            "blocked_reason": job.get("blocked_reason"),
        }
        for job in list_jobs(repo_root)
    ]
