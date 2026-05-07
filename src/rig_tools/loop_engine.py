from __future__ import annotations

import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal

from rig_tools.contracts import CommandPlan, ActionResult, CommandSafety
from rig_tools.runtime_executor import RuntimeExecutor
from rig_tools.state_store import StateStore
try:
    from rig_tools.tui_actions import ActionRegistry
except ImportError:
    ActionRegistry = None

@dataclass
class LoopPolicy:
    policy_id: str
    task: str
    goal: str
    mode: Literal["read_only", "bounded", "review"]
    max_steps: int
    allowed_actions: List[str]
    stop_conditions: List[str]
    requires_human_approval: bool
    max_actions: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    forbidden_actions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "rig.loop_policy.v1"
    authoritative: bool = True

@dataclass
class LoopStep:
    step_id: str
    run_id: str
    step_index: int
    phase: Literal["observe", "decide", "act", "validate", "checkpoint", "stop"]
    status: Literal["planned", "running", "passed", "failed", "blocked", "skipped"]
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    selected_action: Optional[str] = None
    command_plan_path: Optional[str] = None
    action_result_path: Optional[str] = None
    stop_reason: Optional[str] = None
    events: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = "rig.loop_step.v1"
    authoritative: bool = True

@dataclass
class LoopRun:
    run_id: str
    policy_id: str
    task: str
    goal: str
    mode: str
    status: Literal["planned", "running", "passed", "failed", "blocked", "needs_approval", "stopped"]
    current_step: int
    max_steps: int
    started_at: str
    finished_at: Optional[str] = None
    projection_snapshot_path: Optional[str] = None
    steps: List[str] = field(default_factory=list) # List of step IDs
    stop_reason: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = "rig.loop_run.v1"
    authoritative: bool = True

class LoopEngine:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.loops_dir = self.repo_root / ".build" / "rig" / "loops"
        self.executor = RuntimeExecutor(repo_root)
        self.state_store = StateStore(repo_root)
        self.action_registry = ActionRegistry(repo_root)
        
        self.default_allowed_actions = [
            "monitor_snapshot",
            "projections_rebuild",
            "context_build",
            "loop_plan",
            "schema_validate_results",
            "textual_validate",
            "bundle_session_dry_run",
            "agent_plan"
        ]
        
        self.default_stop_conditions = [
            "max_steps_reached",
            "validator_failed",
            "action_failed",
            "needs_human_approval",
            "dirty_git",
            "command_unavailable",
            "budget_exceeded",
            "no_next_action",
            "unsafe_action_requested"
        ]
        self.default_forbidden_actions = [
            "git push",
            "git pull",
            "git rebase",
            "git merge",
            "git commit",
            "patch_apply_main",
            "arbitrary_shell",
        ]

    def create_policy(self, task: str, mode: str = "read_only", max_steps: int = 3) -> LoopPolicy:
        """Creates a default loop policy for a task."""
        policy_id = f"policy-{task}-{uuid.uuid4().hex[:4]}"
        return LoopPolicy(
            policy_id=policy_id,
            task=task,
            goal=f"Automated supervision of task {task}",
            mode=mode, # type: ignore
            max_steps=max_steps,
            allowed_actions=self.default_allowed_actions,
            stop_conditions=self.default_stop_conditions,
            forbidden_actions=list(self.default_forbidden_actions),
            requires_human_approval=mode != "read_only"
        )

    def run(self, policy: LoopPolicy, dry_run: bool = False) -> LoopRun:
        """Executes the bounded supervisor loop."""
        run_id = uuid.uuid4().hex[:12]
        run_dir = self.loops_dir / run_id
        if not dry_run:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "steps").mkdir(parents=True, exist_ok=True)
            (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

        run = LoopRun(
            run_id=run_id,
            policy_id=policy.policy_id,
            task=policy.task,
            goal=policy.goal,
            mode=policy.mode,
            status="running",
            current_step=0,
            max_steps=policy.max_steps,
            started_at=datetime.now(timezone.utc).isoformat()
        )

        events_log = []
        def emit_event(msg: str):
            events_log.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")

        emit_event(f"Loop started: {run_id} for task {policy.task}")

        try:
            while run.current_step < run.max_steps:
                run.current_step += 1
                step_id = f"step-{run.current_step}"
                emit_event(f"Starting step {run.current_step}")
                
                # 1. Observe
                projection = self._load_projection(emit_event)
                if not projection and not dry_run:
                    # Attempt rebuild if allowed
                    if "projections_rebuild" in policy.allowed_actions:
                        emit_event("Projection missing, rebuilding...")
                        from rig_tools.projections import ProjectionsBuilder
                        ProjectionsBuilder(self.repo_root).rebuild()
                        projection = self._load_projection(emit_event)
                
                if not projection:
                    run.status = "stopped"
                    run.stop_reason = "no_projection_snapshot"
                    break

                # 2. Decide
                action_id = self._decide_action(projection, policy, emit_event)
                if not action_id:
                    run.status = "passed"
                    run.stop_reason = "no_next_action"
                    break
                
                if action_id in policy.forbidden_actions:
                    run.status = "blocked"
                    run.stop_reason = "unsafe_action_requested"
                    break

                # 3. Act
                step = LoopStep(
                    step_id=step_id,
                    run_id=run_id,
                    step_index=run.current_step,
                    phase="act",
                    status="running",
                    selected_action=action_id
                )
                
                if dry_run:
                    step.status = "passed"
                    step.events.append("Dry run: subprocess skipped.")
                    run.steps.append(step_id)
                    continue

                # Build Plan
                plan = self.action_registry.build_plan(action_id, policy.task, "safe" if policy.mode == "read_only" else "action")
                plan_path = run_dir / "steps" / f"{step_id}-plan.json"
                plan_path.write_text(json.dumps(asdict(plan), indent=2))
                step.command_plan_path = str(plan_path.relative_to(self.repo_root))

                # Execute
                result = self.executor.execute_plan(plan)
                result_path = run_dir / "steps" / f"{step_id}-result.json"
                result_path.write_text(json.dumps(asdict(result), indent=2))
                step.action_result_path = str(result_path.relative_to(self.repo_root))

                # 4. Validate
                if result.status != "passed":
                    step.status = "failed"
                    step.stop_reason = f"Action failed: {result.status}"
                    run.status = "failed"
                    run.stop_reason = "action_failed"
                    self._write_step(step, run_dir)
                    break
                
                step.status = "passed"
                run.steps.append(step_id)
                
                # 5. Checkpoint
                self._write_checkpoint(run, step, run_dir)
                self._write_step(step, run_dir)
                
                emit_event(f"Step {run.current_step} passed: {action_id}")

            if run.current_step >= run.max_steps and run.status == "running":
                run.status = "stopped"
                run.stop_reason = "max_steps_reached"

        except Exception as e:
            run.status = "failed"
            run.stop_reason = f"Internal error: {str(e)}"
            emit_event(f"CRITICAL ERROR: {str(e)}")

        run.finished_at = datetime.now(timezone.utc).isoformat()
        
        if not dry_run:
            self._write_run(run, run_dir)
            (run_dir / "events.jsonl").write_text("\n".join(events_log))
            
            # Latest
            latest_json = self.loops_dir / "latest.json"
            latest_json.write_text(json.dumps(asdict(run), indent=2))
            
            # Markdown
            md = self._generate_markdown_run(run, events_log)
            (run_dir / "loop-run.md").write_text(md)
            (self.loops_dir / "latest.md").write_text(md)

            # State store
            self._record_to_state_store(run, events_log)

        return run

    def _load_projection(self, emit: Any) -> Optional[Dict[str, Any]]:
        path = self.repo_root / ".build" / "rig" / "projections" / "tui-snapshot.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _decide_action(self, projection: Dict[str, Any], policy: LoopPolicy, emit: Any) -> Optional[str]:
        """Simple deterministic decision logic for MVP."""
        board = projection.get("board_counts", {})
        
        # If task has a specific status in Kanban
        # Note: we need to find OUR task in the kanban projection or just use counts
        # Since tui-snapshot currently only has counts, we use that or monitor.
        
        if board.get("ready", 0) > 0:
            return "monitor_snapshot" # Default safe observation
            
        if board.get("running", 0) > 0:
            return "monitor_snapshot"

        if board.get("review", 0) > 0:
            return "bundle_session_dry_run"
            
        return "monitor_snapshot" # Fallback

    def _write_run(self, run: LoopRun, run_dir: Path):
        (run_dir / "loop-run.json").write_text(json.dumps(asdict(run), indent=2))

    def _write_step(self, step: LoopStep, run_dir: Path):
        path = run_dir / "steps" / f"{step.step_id}.json"
        path.write_text(json.dumps(asdict(step), indent=2))

    def _write_checkpoint(self, run: LoopRun, step: LoopStep, run_dir: Path):
        path = run_dir / "checkpoints" / f"{step.step_index}.json"
        checkpoint = {
            "run_id": run.run_id,
            "step_index": step.step_index,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": run.status
        }
        path.write_text(json.dumps(checkpoint, indent=2))

    def _generate_markdown_run(self, run: LoopRun, events: List[str]) -> str:
        md = [f"# Rig Loop Run: {run.status.upper()}"]
        md.append(f"- Run ID: `{run.run_id}`")
        md.append(f"- Task: `{run.task}`")
        md.append(f"- Mode: `{run.mode}`")
        md.append(f"- Steps: {run.current_step} / {run.max_steps}")
        md.append(f"- Started: {run.started_at}")
        md.append(f"- Finished: {run.finished_at}")
        if run.stop_reason:
            md.append(f"- Stop Reason: **{run.stop_reason}**")
            
        md.append("\n## Events")
        for e in events:
            md.append(f"- {e}")
            
        return "\n".join(md)

    def _record_to_state_store(self, run: LoopRun, events: List[str]):
        try:
            with self.state_store.connect() as conn:
                # Loop Run
                conn.execute("""
                    INSERT INTO loop_runs (loop_run_id, task, status, data, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (run.run_id, run.task, run.status, json.dumps(asdict(run)), run.started_at))
                
                # Events (normalized)
                for e in events:
                    conn.execute("""
                        INSERT INTO events (run_id, event_type, data, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (run.run_id, "loop_event", e, datetime.now(timezone.utc).isoformat()))
                    
                conn.commit()
        except Exception:
            # Degrade gracefully if state store fails
            pass
