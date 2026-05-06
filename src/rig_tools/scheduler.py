from __future__ import annotations

import os
import sys
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rig_tools.settings_store import SettingsStore
from rig_tools.state_store import StateStore

class Scheduler:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.settings_store = SettingsStore(self.repo_root)
        self.state_store = StateStore(self.repo_root)
        self.settings = self.settings_store.get_effective_settings()
        
        self.scheduler_dir = self.repo_root / ".build" / "rig" / "scheduler"
        self.jobs_dir = self.scheduler_dir / "jobs"
        self.runs_dir = self.scheduler_dir / "runs"
        self.logs_dir = self.scheduler_dir / "logs"
        
        self.launch_agents_dir = Path("~/Library/LaunchAgents").expanduser()
        
        self.python_exec = sys.executable
        if not self.python_exec or "rig" not in self.python_exec.lower() and "venv" not in self.python_exec.lower():
            # Fallback to local venv if sys.executable is generic
            venv_path = self.repo_root / ".venv-rig" / "bin" / "python3"
            if venv_path.exists():
                self.python_exec = str(venv_path)

        self._define_default_jobs()

    def _define_default_jobs(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        
        # 1. morning-monitor
        self._register_job(
            job_id="morning-monitor",
            action_id="monitor_snapshot",
            argv=[self.python_exec, str(self.repo_root / "scripts" / "rig.py"), "monitor", "snapshot"],
            schedule_kind="calendar",
            calendar={"Hour": 9, "Minute": 0},
            risk="low"
        )
        
        # 2. projections-refresh
        self._register_job(
            job_id="projections-refresh",
            action_id="projections_rebuild",
            argv=[self.python_exec, str(self.repo_root / "scripts" / "rig.py"), "projections", "rebuild"],
            schedule_kind="interval",
            interval=1800,
            risk="medium"
        )
        
        # 3. gc-plan-nightly
        self._register_job(
            job_id="gc-plan-nightly",
            action_id="gc_plan",
            argv=[self.python_exec, str(self.repo_root / "scripts" / "rig.py"), "gc", "plan"],
            schedule_kind="calendar",
            calendar={"Hour": 2, "Minute": 0},
            risk="low"
        )
        
        # 4. queue-runner
        # Disabled by default
        queue_enabled = self.settings.get("scheduler", {}).get("enable_queue_runner", False)
        self._register_job(
            job_id="queue-runner",
            action_id="queue_run",
            argv=[self.python_exec, str(self.repo_root / "scripts" / "rig.py"), "queue", "run", "--max-jobs", "1"],
            schedule_kind="interval",
            interval=1800,
            risk="high",
            enabled=queue_enabled
        )
        
        # 5. anigma-sentinel-daily
        self._register_job(
            job_id="anigma-sentinel-daily",
            action_id="anigma_sentinel",
            argv=[self.python_exec, str(self.repo_root / "Scripts" / "anigma_architecture_sentinel.py"), "--format", "json"],
            schedule_kind="calendar",
            calendar={"Hour": 10, "Minute": 0},
            risk="low"
        )

    def _register_job(self, job_id: str, action_id: str, argv: List[str], schedule_kind: str, risk: str, interval: Optional[int] = None, calendar: Optional[Dict[str, int]] = None, enabled: bool = True):
        self.jobs[job_id] = {
            "schema_version": "rig.scheduler_job.v1",
            "job_id": job_id,
            "label": f"dev.rig.{job_id}",
            "enabled": enabled,
            "action_id": action_id,
            "command_argv": argv,
            "working_directory": str(self.repo_root),
            "schedule_kind": schedule_kind,
            "plist_path": str(self.jobs_dir / f"{job_id}.plist"),
            "stdout_path": str(self.logs_dir / f"{job_id}.out.log"),
            "stderr_path": str(self.logs_dir / f"{job_id}.err.log"),
            "risk": risk,
            "install_status": "unknown",
            "warnings": [],
            "authoritative": True
        }
        if interval is not None:
            self.jobs[job_id]["start_interval"] = interval
        if calendar is not None:
            self.jobs[job_id]["start_calendar_interval"] = calendar

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        return list(self.jobs.values())

    def validate_safety(self, job: Dict[str, Any]) -> List[str]:
        warnings = []
        argv = job["command_argv"]
        
        # Check arrays
        if not isinstance(argv, list):
            warnings.append("command_argv must be an array.")
            return warnings

        # Metacharacters and bad commands
        bad_words = {"sh", "-c", "bash", "zsh", "tui", "push", "pull", "rebase", "merge", "commit"}
        for arg in argv:
            if arg in bad_words:
                warnings.append(f"Forbidden argument found: {arg}")
            if any(meta in arg for meta in ["|", ">", "<", "&", ";", "`", "$("]):
                warnings.append(f"Shell metacharacter found: {arg}")
                
        # Path validation
        wd = job["working_directory"]
        if not os.path.isabs(wd):
            warnings.append("working_directory must be absolute.")
            
        for p in [job["plist_path"], job["stdout_path"], job["stderr_path"]]:
            if not os.path.isabs(p):
                warnings.append(f"Path must be absolute: {p}")
            if "~" in p:
                warnings.append(f"Path must not contain ~: {p}")
                
        return warnings

    def generate_plist(self, job_id: str) -> str:
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        safety_warnings = self.validate_safety(job)
        if safety_warnings:
            raise ValueError(f"Job failed safety validation: {safety_warnings}")

        plist = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            '<dict>',
            f'    <key>Label</key>',
            f'    <string>{job["label"]}</string>',
            f'    <key>ProgramArguments</key>',
            '    <array>'
        ]
        
        for arg in job["command_argv"]:
            plist.append(f'        <string>{arg}</string>')
            
        plist.extend([
            '    </array>',
            f'    <key>WorkingDirectory</key>',
            f'    <string>{job["working_directory"]}</string>',
            f'    <key>StandardOutPath</key>',
            f'    <string>{job["stdout_path"]}</string>',
            f'    <key>StandardErrorPath</key>',
            f'    <string>{job["stderr_path"]}</string>'
        ])
        
        if job["schedule_kind"] == "interval":
            plist.extend([
                '    <key>StartInterval</key>',
                f'    <integer>{job["start_interval"]}</integer>'
            ])
        elif job["schedule_kind"] == "calendar":
            plist.extend([
                '    <key>StartCalendarInterval</key>',
                '    <dict>',
                f'        <key>Hour</key>',
                f'        <integer>{job["start_calendar_interval"]["Hour"]}</integer>',
                f'        <key>Minute</key>',
                f'        <integer>{job["start_calendar_interval"]["Minute"]}</integer>',
                '    </dict>'
            ])
            
        plist.extend([
            '</dict>',
            '</plist>'
        ])
        
        return "\n".join(plist)

    def install(self, job_id: str, dry_run: bool = True) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            return {"status": "failed", "warnings": ["Job not found"]}
            
        if not job["enabled"]:
            return {"status": "blocked", "warnings": ["Job is disabled by settings"]}

        try:
            plist_content = self.generate_plist(job_id)
        except ValueError as e:
            return {"status": "failed", "warnings": [str(e)]}

        # In MVP, we write to .build/rig/scheduler/jobs first
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        local_plist_path = self.jobs_dir / f"{job_id}.plist"
        
        if not dry_run:
            local_plist_path.write_text(plist_content, encoding="utf-8")
            job["install_status"] = "installed"
            
            # Optional: write to ~/Library/LaunchAgents
            system_plist_path = self.launch_agents_dir / f"{job['label']}.plist"
            if self.launch_agents_dir.exists():
                system_plist_path.write_text(plist_content, encoding="utf-8")
        else:
            job["install_status"] = "dry_run"
            
        return {"status": "success", "job": job, "plist_content": plist_content if dry_run else None}

    def uninstall(self, job_id: str, dry_run: bool = True) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            return {"status": "failed", "warnings": ["Job not found"]}

        warnings = []
        system_plist_path = self.launch_agents_dir / f"{job['label']}.plist"
        local_plist_path = self.jobs_dir / f"{job_id}.plist"
        
        if not dry_run:
            if system_plist_path.exists():
                try:
                    system_plist_path.unlink()
                except Exception as e:
                    warnings.append(f"Failed to remove system plist: {e}")
                    
            if local_plist_path.exists():
                local_plist_path.unlink()
                
            job["install_status"] = "not_installed"
        else:
            job["install_status"] = "dry_run"

        return {"status": "success", "job": job, "warnings": warnings}

    def run_now(self, job_id: str, dry_run: bool = True) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            return {"status": "failed", "warnings": ["Job not found"]}

        safety_warnings = self.validate_safety(job)
        if safety_warnings:
            return {"status": "blocked", "warnings": safety_warnings}

        if job["risk"] == "high" and not dry_run:
            return {"status": "blocked", "warnings": ["High risk jobs cannot be run via run-now MVP"]}

        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc)
        
        run_record = {
            "schema_version": "rig.scheduler_run.v1",
            "run_id": run_id,
            "job_id": job_id,
            "mode": "run_now" if not dry_run else "dry_run",
            "started_at": started_at.isoformat(),
            "status": "dry_run",
            "warnings": [],
            "authoritative": True
        }

        if not dry_run:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # Use subprocess to run the argv safely
                with open(job["stdout_path"], "a") as out_f, open(job["stderr_path"], "a") as err_f:
                    proc = subprocess.run(
                        job["command_argv"],
                        cwd=job["working_directory"],
                        stdout=out_f,
                        stderr=err_f,
                        timeout=60
                    )
                run_record["status"] = "passed" if proc.returncode == 0 else "failed"
            except Exception as e:
                run_record["status"] = "failed"
                run_record["warnings"].append(str(e))
                
        run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        
        self._persist_run(run_record)
        return run_record

    def _persist_run(self, run: Dict[str, Any]):
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{run['run_id']}.json"
        path.write_text(json.dumps(run, indent=2), encoding="utf-8")
        
        try:
            with self.state_store.connect() as conn:
                conn.execute("""
                    INSERT INTO event_log (event_type, payload, created_at)
                    VALUES (?, ?, ?)
                """, ("scheduler_run", json.dumps({"run_id": run["run_id"], "job_id": run["job_id"], "status": run["status"]}), run["started_at"]))
                conn.commit()
        except Exception:
            pass
