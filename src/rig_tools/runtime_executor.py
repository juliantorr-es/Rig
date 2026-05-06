from __future__ import annotations

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Optional

from rig_tools.contracts import CommandPlan, ActionResult

class RuntimeExecutor:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.actions_dir = self.repo_root / ".build" / "rig" / "actions"
        self.actions_dir.mkdir(parents=True, exist_ok=True)

    def execute_plan(self, plan: CommandPlan) -> ActionResult:
        """Executes a CommandPlan and returns an ActionResult receipt."""
        plan.validate()
        
        result_dir = self.actions_dir / plan.plan_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        stdout_path = result_dir / "stdout.txt"
        stderr_path = result_dir / "stderr.txt"
        
        if not plan.allowed:
            return self._create_blocked_result(plan, stdout_path, stderr_path)

        start_time = datetime.now(timezone.utc)
        start_ts = time.time()
        
        status = "passed"
        exit_code = 0
        
        try:
            # We use sys.executable if it's a python script (handled by caller usually)
            # but here we just run the argv as provided in the plan.
            # MANDATORY: No shell=True.
            proc = subprocess.Popen(
                plan.argv,
                cwd=plan.working_directory,
                stdout=stdout_path.open("w"),
                stderr=stderr_path.open("w"),
                text=True
            )
            
            try:
                proc.wait(timeout=plan.timeout_seconds)
                exit_code = proc.returncode
                status = "passed" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                proc.kill()
                status = "timeout"
                exit_code = -1
                with stderr_path.open("a") as f:
                    f.write(f"\n[Rig OS] Execution timed out after {plan.timeout_seconds}s\n")
                    
        except Exception as e:
            status = "failed"
            exit_code = -1
            with stderr_path.open("a") as f:
                f.write(f"\n[Rig OS] Execution error: {str(e)}\n")

        end_time = datetime.now(timezone.utc)
        duration_ms = int((time.time() - start_ts) * 1000)

        result = ActionResult(
            result_id=plan.plan_id, # Simplified for MVP
            plan_id=plan.plan_id,
            action_id=plan.action_id,
            task=plan.task,
            status=status,
            exit_code=exit_code,
            started_at=start_time.isoformat(),
            finished_at=end_time.isoformat(),
            duration_ms=duration_ms,
            stdout_path=str(stdout_path.relative_to(self.repo_root)),
            stderr_path=str(stderr_path.relative_to(self.repo_root)),
            human_summary=f"Action {plan.action_id} {status} with exit code {exit_code}"
        )
        
        self._write_receipts(result, result_dir)
        return result

    def _create_blocked_result(self, plan: CommandPlan, stdout_path: Path, stderr_path: Path) -> ActionResult:
        now = datetime.now(timezone.utc).isoformat()
        
        # Ensure files exist even if empty
        stdout_path.touch()
        stderr_path.write_text(f"Action blocked: {plan.disabled_reason or 'No reason provided'}\n")
        
        result = ActionResult(
            result_id=plan.plan_id,
            plan_id=plan.plan_id,
            action_id=plan.action_id,
            task=plan.task,
            status="blocked",
            exit_code=-1,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            stdout_path=str(stdout_path.relative_to(self.repo_root)),
            stderr_path=str(stderr_path.relative_to(self.repo_root)),
            human_summary=f"Action {plan.action_id} BLOCKED: {plan.disabled_reason}"
        )
        self._write_receipts(result, stdout_path.parent)
        return result

    def _write_receipts(self, result: ActionResult, result_dir: Path):
        # JSON receipt
        receipt_path = result_dir / "result.json"
        receipt_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        
        # Markdown receipt
        md_path = result_dir / "result.md"
        md = [
            f"# Action Result: {result.status.upper()}",
            f"- Action: `{result.action_id}`",
            f"- Task: `{result.task or 'N/A'}`",
            f"- Exit Code: `{result.exit_code}`",
            f"- Duration: {result.duration_ms}ms",
            f"- Started: {result.started_at}",
            f"- Finished: {result.finished_at}",
            f"- Stdout: `{result.stdout_path}`",
            f"- Stderr: `{result.stderr_path}`",
            "\n## Summary",
            result.human_summary
        ]
        md_path.write_text("\n".join(md), encoding="utf-8")
        
        # Latest symlink-like update
        latest_dir = self.actions_dir / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / "result.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
