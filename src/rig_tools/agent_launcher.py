from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from rig_tools.agent_plan import load_plan, validate_plan
from rig_tools.action_manifest import write_action_manifest
from rig_tools.events import make_event, write_event_stream


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _load_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "Docs" / "dev" / "rig" / "agent-registry.yaml"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {"agents": []}
    agents = data.get("agents") if isinstance(data, dict) else []
    return {agent.get("agent_id"): agent for agent in agents if isinstance(agent, dict)}


def available_agents(repo_root: Path) -> list[dict[str, Any]]:
    registry = _load_registry(repo_root)
    out = []
    from shutil import which

    for agent_id, agent in registry.items():
        exe_name = agent.get("executable") or agent_id
        exe = which(str(exe_name))
        out.append({
            **agent,
            "available": exe is not None,
            "executable": exe,
            "enabled": bool(agent.get("enabled")) and exe is not None,
        })
    return sorted(out, key=lambda item: str(item.get("agent_id") or ""))


def probe_agents(repo_root: Path) -> list[dict[str, Any]]:
    probes = []
    for agent in available_agents(repo_root):
        exe = agent.get("executable")
        info = dict(agent)
        if not exe:
            info.update({"probe_status": "missing_executable", "supports_json": bool(agent.get("supports_json")), "supports_jsonl": bool(agent.get("supports_jsonl"))})
            probes.append(info)
            continue
        try:
            proc = subprocess.run([str(exe), "--help"], cwd=repo_root, text=True, capture_output=True, check=False, timeout=5, shell=False)
            help_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
            info.update({
                "probe_status": "probed",
                "help_exit_code": proc.returncode,
                "supports_json": ("--output-format" in help_text) or ("stream-json" in help_text),
                "supports_jsonl": ("jsonl" in help_text.lower()) or ("stream-json" in help_text),
                "supports_dry_run": bool(agent.get("supports_dry_run")),
                "danger_level": agent.get("danger_level"),
                "warning": None,
            })
        except Exception as exc:
            info.update({"probe_status": "probe_failed", "error": str(exc)})
        probes.append(info)
    return probes


def plan_path(repo_root: Path, plan_id: str) -> Path:
    return repo_root / ".build" / "rig" / "agents" / "plans" / f"{plan_id}.json"


def run_dir(repo_root: Path, run_id: str) -> Path:
    return repo_root / ".build" / "rig" / "agents" / "runs" / run_id


def _write_run_manifest(repo_root: Path, payload: dict[str, Any]) -> Path:
    out_dir = run_dir(repo_root, payload["run_id"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "agent-run.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _command_for_plan(plan: dict[str, Any], prompt_file: Path, prompt_text: str) -> list[str]:
    agent_id = plan.get("agent_id")
    if agent_id == "codex":
        return ["codex", "exec", str(prompt_file)]
    if agent_id == "gemini":
        return ["gemini", "-p", prompt_text, "--output-format", "stream-json"]
    if agent_id == "claude":
        return ["claude", "-p", prompt_text]
    if agent_id == "vibe":
        return ["vibe", "--prompt", prompt_text]
    raise ValueError("unknown agent")


def launch_from_plan(repo_root: Path, plan_path_: Path, *, dry_run: bool = False, confirm: bool = False, allow_vibe: bool = False, timeout_seconds: int| Optional = None) -> dict[str, Any]:
    plan = load_plan(plan_path_)
    validation = validate_plan(repo_root, plan, allow_vibe=allow_vibe)
    if validation["status"] != "passed":
        return {"status": "failed", "reason": "invalid_plan", "validation": validation}
    run_id = uuid.uuid4().hex[:12]
    run_root = run_dir(repo_root, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    prompt_file = run_root / "prompt.md"
    prompt_file.write_text(plan["prompt"], encoding="utf-8")
    cmd = _command_for_plan(plan, prompt_file, plan["prompt"])
    stdout_path = run_root / "stdout.log"
    stderr_path = run_root / "stderr.log"
    events_path = run_root / "events.jsonl"
    if dry_run:
        started = time.time()
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
        dry_events = [
            make_event("run_started", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"agent_id": plan.get("agent_id"), "plan_id": plan.get("plan_id"), "milestone": "agent_launch_dry_run"}),
            make_event("artifact", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"path": _repo_rel(repo_root, prompt_file), "artifact_type": "prompt", "milestone": "agent_artifact_written"}),
            make_event("run_finished", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"status": "dry_run", "exit_code": 0, "milestone": "agent_launch_finished"}),
        ]
        write_event_stream(events_path, dry_events)
        manifest = {
            "schema_version": "rig.agent_run.v1",
            "run_id": run_id,
            "plan_id": plan.get("plan_id"),
            "task": plan.get("task"),
            "agent_id": plan.get("agent_id"),
            "status": "dry_run",
            "exit_code": 0,
            "started_at": started_at,
            "finished_at": started_at,
            "duration_seconds": 0.0,
            "command_template_id": plan.get("agent_id"),
            "prompt_path": _repo_rel(repo_root, prompt_file),
            "stdout_path": _repo_rel(repo_root, stdout_path),
            "stderr_path": _repo_rel(repo_root, stderr_path),
            "event_path": _repo_rel(repo_root, events_path),
            "artifacts": [_repo_rel(repo_root, prompt_file)],
            "warnings": ["dry_run"],
            "authoritative": False,
        }
        _write_run_manifest(repo_root, manifest)
        write_action_manifest(
            repo_root,
            task=str(plan.get("task") or ""),
            action_kind="agent.launch.dry_run",
            command_group="agent",
            command=cmd,
            inputs=[{"path": str(prompt_file), "kind": "prompt"}],
            outputs=[{"path": str(prompt_file), "kind": "prompt", "status": "produced"}, {"path": str(events_path), "kind": "events", "status": "produced"}],
            status="passed",
            exit_code=0,
            result_path=run_dir(repo_root, run_id) / "agent-run.json",
            event_path=events_path,
        )
        return {"status": "dry_run", "command": cmd, "command_template_id": plan["agent_id"], "plan_path": _repo_rel(repo_root, plan_path_), "run_id": run_id, "manifest": _repo_rel(repo_root, run_dir(repo_root, run_id) / "agent-run.json")}
    if not confirm:
        return {"status": "failed", "reason": "confirm_required"}
    if plan.get("agent_id") == "vibe" and not allow_vibe:
        return {"status": "failed", "reason": "vibe_disabled"}
    started = time.time()
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    events = [
        make_event("run_started", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"agent_id": plan.get("agent_id"), "plan_id": plan.get("plan_id"), "milestone": "agent_launch_started"}),
        make_event("step_started", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"step_id": "launch", "agent_id": plan.get("agent_id"), "milestone": "agent_launch_started"}),
    ]
    write_event_stream(events_path, events)
    try:
        proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False, timeout=timeout_seconds or int(plan.get("timeout_seconds") or 1800), shell=False)
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")
        status = "passed" if proc.returncode == 0 else "failed"
        finished = time.time()
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
        final_events = [
            make_event("artifact", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"path": _repo_rel(repo_root, stdout_path), "artifact_type": "stdout", "milestone": "agent_artifact_written"}),
            make_event("artifact", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"path": _repo_rel(repo_root, stderr_path), "artifact_type": "stderr", "milestone": "agent_artifact_written"}),
            make_event("run_finished", run_id=run_id, command_group="agent", command=" ".join(cmd), task=plan.get("task"), attributes={"status": status, "exit_code": proc.returncode, "milestone": "agent_launch_finished"}),
        ]
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(event, sort_keys=True) for event in final_events) + "\n")
        manifest = {
            "schema_version": "rig.agent_run.v1",
            "run_id": run_id,
            "plan_id": plan.get("plan_id"),
            "task": plan.get("task"),
            "agent_id": plan.get("agent_id"),
            "status": status,
            "exit_code": proc.returncode,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(finished - started, 3),
            "command_template_id": plan.get("agent_id"),
            "prompt_path": _repo_rel(repo_root, prompt_file),
            "stdout_path": _repo_rel(repo_root, stdout_path),
            "stderr_path": _repo_rel(repo_root, stderr_path),
            "event_path": _repo_rel(repo_root, events_path),
            "artifacts": [_repo_rel(repo_root, prompt_file), _repo_rel(repo_root, stdout_path), _repo_rel(repo_root, stderr_path), _repo_rel(repo_root, events_path)],
            "warnings": [],
            "authoritative": False,
        }
        _write_run_manifest(repo_root, manifest)
        write_action_manifest(
            repo_root,
            task=str(plan.get("task") or ""),
            action_kind="agent.launch",
            command_group="agent",
            command=cmd,
            inputs=[{"path": str(prompt_file), "kind": "prompt"}],
            outputs=[{"path": str(stdout_path), "kind": "stdout", "status": "produced"}, {"path": str(stderr_path), "kind": "stderr", "status": "produced"}, {"path": str(events_path), "kind": "events", "status": "produced"}],
            status=status,
            exit_code=proc.returncode,
            result_path=run_dir(repo_root, run_id) / "agent-run.json",
            event_path=events_path,
        )
        return manifest
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(exc), encoding="utf-8")
        finished = time.time()
        manifest = {
            "schema_version": "rig.agent_run.v1",
            "run_id": run_id,
            "plan_id": plan.get("plan_id"),
            "task": plan.get("task"),
            "agent_id": plan.get("agent_id"),
            "status": "failed",
            "exit_code": 124,
            "started_at": started_at,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished)),
            "duration_seconds": round(finished - started, 3),
            "command_template_id": plan.get("agent_id"),
            "prompt_path": _repo_rel(repo_root, prompt_file),
            "stdout_path": _repo_rel(repo_root, stdout_path),
            "stderr_path": _repo_rel(repo_root, stderr_path),
            "event_path": _repo_rel(repo_root, events_path),
            "artifacts": [_repo_rel(repo_root, prompt_file), _repo_rel(repo_root, stdout_path), _repo_rel(repo_root, stderr_path), _repo_rel(repo_root, events_path)],
            "warnings": ["timeout"],
            "authoritative": False,
        }
        _write_run_manifest(repo_root, manifest)
        write_action_manifest(
            repo_root,
            task=str(plan.get("task") or ""),
            action_kind="agent.launch",
            command_group="agent",
            command=cmd,
            inputs=[{"path": str(prompt_file), "kind": "prompt"}],
            outputs=[{"path": str(stdout_path), "kind": "stdout", "status": "produced"}, {"path": str(stderr_path), "kind": "stderr", "status": "produced"}, {"path": str(events_path), "kind": "events", "status": "produced"}],
            status="failed",
            exit_code=124,
            result_path=run_dir(repo_root, run_id) / "agent-run.json",
            event_path=events_path,
            warnings=["timeout"],
        )
        return manifest


def list_runs(repo_root: Path) -> list[dict[str, Any]]:
    runs_root = repo_root / ".build" / "rig" / "agents" / "runs"
    if not runs_root.exists():
        return []
    rows = []
    for path in sorted(runs_root.glob("*/agent-run.json"), key=lambda p: p.parent.name):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            rows.append(data)
    return rows


def tail_run(repo_root: Path, run_id: str) -> list[dict[str, Any]]:
    path = run_dir(repo_root, run_id) / "events.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"schema_version": "rig.event.v1", "event_type": "parse_error", "raw": line})
    return out
