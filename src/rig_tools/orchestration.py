from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig.config.loader import merge_config
from rig.logging.jsonl_logger import JsonlLogger
from rig_tools.agent_proposals import create_proposal, proposal_to_command_plan
from rig_tools.atomic_io import write_json_atomic
from rig_tools.file_lock import job_store_lock
from rig_tools.provider_registry import provider_for_id
from rig_tools.context_budget import build_context_packet
from rig.domain.workspace import WorkspaceDomain


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
JOB_STORE_NAME = ".build/rig/jobs"
LEGACY_QUEUE_PATH = Path(".build/rig/queue/queue.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def job_store_root(repo_root: Path) -> Path:
    out = repo_root / JOB_STORE_NAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def job_path(repo_root: Path, job_id: str) -> Path:
    return job_store_root(repo_root) / f"{job_id}.json"


def receipt_path(repo_root: Path, job_id: str) -> Path:
    return repo_root / ".build" / "rig" / "receipts" / f"{job_id}_orchestration.json"


def legacy_queue_path(repo_root: Path) -> Path:
    return repo_root / LEGACY_QUEUE_PATH


def _log(repo_root: Path) -> JsonlLogger:
    return JsonlLogger(repo_root / ".build" / "rig" / "logs")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class JobLoadResult:
    jobs: list[dict[str, Any]]
    malformed: list[dict[str, Any]]
    quarantined: list[str]


def _validate_job(job: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if job.get("schema_version") != JOB_SCHEMA_VERSION:
        problems.append("schema_version")
    if not job.get("job_id"):
        problems.append("job_id")
    if job.get("authoritative") is not True:
        problems.append("authoritative")
    return problems


def _job_scan(repo_root: Path) -> list[Path]:
    root = job_store_root(repo_root)
    return sorted(
        [p for p in root.glob("*.json") if p.is_file() and not p.name.endswith((".tmp", ".bad"))],
        key=lambda p: p.name,
    )


def load_all_jobs(repo_root: Path, *, repair: bool = False) -> JobLoadResult:
    jobs: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    quarantined: list[str] = []
    for path in _job_scan(repo_root):
        try:
            payload = _safe_json_load(path)
            if not isinstance(payload, dict):
                raise ValueError("job manifest must be an object")
            problems = _validate_job(payload)
            if problems:
                raise ValueError(f"job schema invalid: {', '.join(problems)}")
            jobs.append(payload)
        except Exception as exc:
            malformed.append({"path": str(path), "error": str(exc)})
            if repair:
                bad_path = path.with_suffix(path.suffix + ".bad")
                try:
                    path.replace(bad_path)
                    quarantined.append(str(bad_path))
                except Exception:
                    pass
    if repair:
        for tmp_path in sorted(job_store_root(repo_root).glob("*.tmp"), key=lambda p: p.name):
            try:
                tmp_path.unlink()
            except Exception:
                pass
    return JobLoadResult(jobs=jobs, malformed=malformed, quarantined=quarantined)


def list_jobs(repo_root: Path, *, repair: bool = False) -> list[dict[str, Any]]:
    return load_all_jobs(repo_root, repair=repair).jobs


def load_job(repo_root: Path, job_id: str) -> dict[str, Any] | None:
    path = job_path(repo_root, job_id)
    if not path.exists():
        return None
    try:
        payload = _safe_json_load(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _save_job(repo_root: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    with job_store_lock(repo_root):
        write_json_atomic(job_path(repo_root, job["job_id"]), job)


def _receipt_payload(job: dict[str, Any], *, status: str, failed_step: str | None = None, blocked_reason: str | None = None) -> dict[str, Any]:
    return {
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


def _write_receipt(repo_root: Path, job: dict[str, Any], *, status: str, failed_step: str | None = None, blocked_reason: str | None = None) -> dict[str, Any]:
    receipt = _receipt_payload(job, status=status, failed_step=failed_step, blocked_reason=blocked_reason)
    with job_store_lock(repo_root):
        write_json_atomic(receipt_path(repo_root, job["job_id"]), receipt)
    return receipt


def _read_legacy_queue(repo_root: Path) -> dict[str, Any] | None:
    path = legacy_queue_path(repo_root)
    if not path.exists():
        return None
    try:
        payload = _safe_json_load(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _default_job(task: str, provider_id: str, model_id: str | None, workspace_id: str | None, requested_steps: list[str] | None) -> dict[str, Any]:
    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": uuid.uuid4().hex[:12],
        "task": task,
        "repo_root": None,
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


def create_job(repo_root: Path, *, task: str, provider_id: str, model_id: str | None = None, workspace_id: str | None = None, requested_steps: list[str] | None = None) -> dict[str, Any]:
    job = _default_job(task, provider_id, model_id, workspace_id, requested_steps)
    job["repo_root"] = str(repo_root)
    with job_store_lock(repo_root):
        write_json_atomic(job_path(repo_root, job["job_id"]), job)
    _log(repo_root).write_event(job["job_id"], level="info", event="job_created", message="job created", metadata={"task": task, "provider_id": provider_id}, command_id=job["job_id"])
    return job


def inspect_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    job = load_job(repo_root, job_id)
    return job if job else {"status": "missing", "job_id": job_id}


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


def _proposal_seed_output() -> str:
    return json.dumps(
        {
            "intent": {"kind": "plan"},
            "decoded_actions": [{"type": "command", "argv": ["python", "-m", "pytest", "-q"]}],
            "files_referenced": [],
            "confidence": 0.8,
            "risk_level": "medium",
        }
    )


def _next_commands(reason: str, job: dict[str, Any]) -> list[str]:
    if reason == "proposal_acceptance_required":
        return [f"rig agent inspect {job.get('proposal_id')}", f"rig agent accept {job.get('proposal_id')}"]
    if reason == "execution_approval_required":
        return [f"rig job inspect {job.get('job_id')}", f"rig run --task {job.get('task')} --provider {job.get('provider_id')} --dry-run"]
    if reason == "apply_required":
        return [f"rig workspace review {job.get('workspace_id')}", f"rig workspace apply {job.get('workspace_id')}"]
    return [f"rig job inspect {job.get('job_id')}"]


def _blocked_result(job: dict[str, Any], *, reason: str, step: str | None) -> dict[str, Any]:
    receipt = _write_receipt(Path(job["repo_root"]), job, status="blocked", failed_step=step, blocked_reason=reason)
    return {
        "status": "blocked",
        "job": job,
        "receipt": receipt,
        "next": _next_commands(reason, job),
        "blocked_reason": reason,
    }


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
    ws = WorkspaceDomain(repo_root)
    provider = provider_for_id(repo_root, str(job["provider_id"]))

    job["status"] = "running"
    _save_job(repo_root, job)
    _log(repo_root).write_event(job_id, level="info", event="job_started", message="job started", command_id=job_id, metadata={"job_id": job_id})

    if not job.get("workspace_id"):
        created = ws.create_workspace(job["task"])
        job["workspace_id"] = created.payload["workspace_id"]
        job["completed_steps"].append("create_workspace")
        job["current_step"] = "create_workspace"
        _save_job(repo_root, job)
        if until == "create_workspace":
            job["status"] = "blocked"
            job["blocked_reason"] = "create_workspace_complete"
            return _blocked_result(job, reason="create_workspace_complete", step="create_workspace")

    try:
        context_packet = build_context_packet(repo_root, workspace_id=job["workspace_id"], provider_id=provider.id(), model_id=str(job.get("model_id") or "static"))
        provider_result = provider.invoke(
            {
                "workspace_id": job["workspace_id"],
                "model_id": job.get("model_id") or "static",
                "static_output": _proposal_seed_output(),
                "context_packet_id": context_packet["packet_id"],
                "context_packet_hash": hashlib.sha256(json.dumps(context_packet, sort_keys=True).encode("utf-8")).hexdigest(),
            }
        )
    except Exception:
        job["status"] = "blocked"
        job["blocked_reason"] = "provider_unavailable"
        job["current_step"] = "generate_proposal"
        _save_job(repo_root, job)
        return _blocked_result(job, reason="provider_unavailable", step="generate_proposal")

    proposal = create_proposal(
        repo_root,
        workspace_id=job["workspace_id"],
        provider_id=provider.id(),
        model_id=str(job.get("model_id") or "static"),
        raw_output=provider_result.raw_output,
        provider_manifest=provider.manifest(),
        context_packet_id=context_packet["packet_id"],
        context_packet_hash=hashlib.sha256(json.dumps(context_packet, sort_keys=True).encode("utf-8")).hexdigest(),
    )
    job["proposal_id"] = proposal["proposal_id"]
    job["completed_steps"].append("generate_proposal")
    job["current_step"] = "generate_proposal"
    _save_job(repo_root, job)
    if proposal.get("status") == "blocked":
        job["status"] = "blocked"
        job["blocked_reason"] = "provider_trust_tier_blocked"
        return _blocked_result(job, reason="provider_trust_tier_blocked", step="decode_proposal")

    job["completed_steps"].append("decode_proposal")
    job["current_step"] = "decode_proposal"
    _save_job(repo_root, job)
    if policy.get("allow_auto_accept_proposals", False) is not True:
        job["status"] = "blocked"
        job["blocked_reason"] = "proposal_acceptance_required"
        return _blocked_result(job, reason="proposal_acceptance_required", step="accept_proposal")

    plan = proposal_to_command_plan(repo_root, proposal)
    job["plan_id"] = plan.plan_id
    _save_job(repo_root, job)
    if policy.get("allow_auto_execute", False) is not True:
        job["status"] = "blocked"
        job["blocked_reason"] = "execution_approval_required"
        return _blocked_result(job, reason="execution_approval_required", step="execute_plan")

    job["status"] = "blocked"
    job["blocked_reason"] = "apply_required"
    return _blocked_result(job, reason="apply_required", step="generate_review")


def list_jobs_summary(repo_root: Path) -> list[dict[str, Any]]:
    load = load_all_jobs(repo_root)
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
        for job in load.jobs
    ]


def queue_health(repo_root: Path, *, repair: bool = False) -> dict[str, Any]:
    load = load_all_jobs(repo_root, repair=repair)
    legacy = legacy_queue_path(repo_root)
    tmp_count = len(list(job_store_root(repo_root).glob("*.tmp")))
    bad_count = len(list(job_store_root(repo_root).glob("*.bad")))
    receipt = None
    receipts = sorted((repo_root / ".build" / "rig" / "receipts").glob("*_legacy_queue_migration.json"))
    if receipts:
        receipt = str(receipts[-1].relative_to(repo_root))
    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "canonical_job_count": len(load.jobs),
        "malformed_job_count": len(load.malformed),
        "quarantined_bad_count": bad_count,
        "tmp_file_count": tmp_count,
        "lock_path": str((repo_root / ".build" / "rig" / "jobs" / ".lock").relative_to(repo_root)),
        "legacy_queue_detected": legacy.exists(),
        "last_migration_receipt": receipt,
        "using_canonical_jobs": True,
        "malformed": load.malformed,
        "quarantined": load.quarantined,
    }


def migrate_legacy_queue(repo_root: Path, *, force: bool = False) -> dict[str, Any]:
    legacy = _read_legacy_queue(repo_root)
    if not legacy:
        return {"status": "missing", "legacy_queue": str(legacy_queue_path(repo_root).relative_to(repo_root))}
    migrated: list[str] = []
    with job_store_lock(repo_root):
        for item in legacy.get("jobs", []):
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("job_id") or uuid.uuid4().hex[:12])
            target = job_path(repo_root, job_id)
            if target.exists() and not force:
                continue
            job = {
                "schema_version": JOB_SCHEMA_VERSION,
                "job_id": job_id,
                "task": item.get("task") or "legacy-task",
                "repo_root": str(repo_root),
                "workspace_id": item.get("workspace_id"),
                "provider_id": item.get("provider_id") or "custom-command",
                "model_id": item.get("model_id"),
                "requested_steps": item.get("requested_steps") or list(DEFAULT_REQUESTED_STEPS),
                "completed_steps": item.get("completed_steps") or [],
                "current_step": item.get("current_step"),
                "status": item.get("status") or "queued",
                "created_at": item.get("created_at") or utc_now(),
                "updated_at": utc_now(),
                "blocked_reason": item.get("blocked_reason"),
                "proposal_id": item.get("proposal_id"),
                "plan_id": item.get("plan_id"),
                "execution_receipt_id": item.get("execution_receipt_id"),
                "validation_receipt_ids": item.get("validation_receipt_ids") or [],
                "review_bundle_hash": item.get("review_bundle_hash"),
                "authoritative": True,
            }
            write_json_atomic(target, job)
            migrated.append(job_id)
    receipt = {
        "schema_version": "rig.legacy_queue_migration.v1",
        "receipt_id": uuid.uuid4().hex[:12],
        "status": "completed" if migrated else "noop",
        "legacy_queue": str(legacy_queue_path(repo_root).relative_to(repo_root)),
        "migrated_job_ids": migrated,
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "authoritative": True,
    }
    receipt_path_out = repo_root / ".build" / "rig" / "receipts" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_legacy_queue_migration.json"
    write_json_atomic(receipt_path_out, receipt)
    return {"status": receipt["status"], "receipt": str(receipt_path_out.relative_to(repo_root)), "migrated_job_ids": migrated}
