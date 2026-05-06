from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig_tools.loop_engine import LoopEngine
from rig_tools.gc import GarbageCollector
from rig_tools import proposal_swarm
from rig_tools.projections import ProjectionsBuilder
from rig_tools.memory_contracts import evaluate_memory_contracts
from rig_tools.system_pressure import sample_system_pressure
from rig_tools.runtime_executor import RuntimeExecutor
from rig_tools.scheduler import Scheduler
from rig_tools.settings_store import SettingsStore
from rig_tools.state_store import StateStore
from rig_tools.vault_export import VaultExporter
from rig_tools.tui_actions import ActionRegistry


SCHEMA_VERSION = "rig.doctor_report.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _excerpt(text: str, limit: int = 800) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _command_text(argv: list[str]) -> str:
    return " ".join(argv)


@dataclass
class CheckResult:
    check_id: str
    subsystem: str
    command: str
    status: str
    exit_code: int | None
    stdout_excerpt: str
    stderr_excerpt: str
    artifact_path: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "subsystem": self.subsystem,
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "artifact_path": self.artifact_path,
            "recommendation": self.recommendation,
        }


class RigDoctor:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.python_exec = sys.executable
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.recommendations: list[str] = []

    def _run(self, check_id: str, subsystem: str, argv: list[str], *, cwd: Path | None = None, timeout: int = 30) -> CheckResult:
        try:
            proc = subprocess.run(argv, cwd=cwd or self.repo_root, text=True, capture_output=True, timeout=timeout, check=False)
            status = "pass" if proc.returncode == 0 else "fail"
            return CheckResult(
                check_id=check_id,
                subsystem=subsystem,
                command=_command_text(argv),
                status=status,
                exit_code=proc.returncode,
                stdout_excerpt=_excerpt(proc.stdout or ""),
                stderr_excerpt=_excerpt(proc.stderr or ""),
                artifact_path="",
                recommendation="",
            )
        except subprocess.TimeoutExpired as exc:
            return CheckResult(
                check_id=check_id,
                subsystem=subsystem,
                command=_command_text(argv),
                status="fail",
                exit_code=-1,
                stdout_excerpt=_excerpt(getattr(exc, "stdout", "") or ""),
                stderr_excerpt="Command timed out",
                artifact_path="",
                recommendation="Inspect the command for deadlocks or long-running work",
            )
        except FileNotFoundError as exc:
            return CheckResult(
                check_id=check_id,
                subsystem=subsystem,
                command=_command_text(argv),
                status="warn",
                exit_code=127,
                stdout_excerpt="",
                stderr_excerpt=str(exc),
                artifact_path="",
                recommendation="Optional tool missing; install or configure the subsystem",
            )
        except Exception as exc:
            return CheckResult(
                check_id=check_id,
                subsystem=subsystem,
                command=_command_text(argv),
                status="fail",
                exit_code=-1,
                stdout_excerpt="",
                stderr_excerpt=str(exc),
                artifact_path="",
                recommendation="Inspect the subsystem implementation",
            )

    def _record(self, result: CheckResult) -> dict[str, Any]:
        payload = result.to_dict()
        self.checks.append(payload)
        if payload["status"] == "fail":
            self.failures.append(f"{payload['subsystem']}:{payload['check_id']}")
        elif payload["status"] == "warn":
            if payload["subsystem"] == "proposal_swarm":
                self.warnings.append("Proposal Swarm limited: llama-server unavailable; MLX fallback only.")
            else:
                self.warnings.append(f"{payload['subsystem']}:{payload['check_id']}")
        if payload["recommendation"]:
            self.recommendations.append(payload["recommendation"])
        return payload

    def _state_store_check(self) -> dict[str, Any]:
        store = StateStore(self.repo_root)
        db_path = store.db_path
        if not db_path.exists():
            self.warnings.append("state_store_missing")
            return self._record(CheckResult(
                check_id="state_store",
                subsystem="state_store",
                command=str(db_path),
                status="fail",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt="State SQLite database is missing",
                artifact_path=str(db_path.relative_to(self.repo_root)) if db_path.exists() else str(db_path),
                recommendation="Run state-store initialization or a Rig command that materializes the DB",
            ))

        missing_tables: list[str] = []
        tables_info: dict[str, int] = {}
        migrations_present = False
        with store.connect() as conn:
            for table in store.required_tables + ["schema_migrations"]:
                row = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                exists = bool(row and row[0] > 0)
                tables_info[table] = 1 if exists else 0
                if not exists:
                    missing_tables.append(table)
            if tables_info.get("schema_migrations"):
                migrations_present = True
                settings_row = conn.execute("SELECT value FROM settings WHERE key='effective'").fetchone()
            else:
                settings_row = None

        status = "pass" if not missing_tables else "fail"
        stderr = "" if not missing_tables else f"Missing required tables: {', '.join(missing_tables)}"
        recommendation = "" if not missing_tables else "Run the state-store migration/materialization lane"
        if settings_row is None:
            self.warnings.append("settings_snapshot_missing")
        return self._record(CheckResult(
            check_id="state_store",
            subsystem="state_store",
            command=f"sqlite3 {db_path}",
            status=status,
            exit_code=0 if status == "pass" else 1,
            stdout_excerpt=json.dumps({"tables": tables_info, "migrations_present": migrations_present})[:800],
            stderr_excerpt=stderr,
            artifact_path=str(db_path.relative_to(self.repo_root)),
            recommendation=recommendation,
        ))

    def _settings_check(self) -> dict[str, Any]:
        show = self._run("settings_show", "settings_store", [self.python_exec, "scripts/rig.py", "settings", "show", "--format", "json"])
        self._record(show)
        validate = self._run("settings_validate", "settings_store", [self.python_exec, "scripts/rig.py", "settings", "validate"])
        self._record(validate)

        store = SettingsStore(self.repo_root)
        effective = store.get_effective_settings()
        safety = effective.get("safety", {}) if isinstance(effective, dict) else {}
        dangerous_defaults = {
            "allow_git_mutation": bool(safety.get("allow_git_mutation", False)),
            "allow_main_worktree_patch": bool(safety.get("allow_main_worktree_patch", False)),
            "allow_confirmed_external_agent_launch": bool(safety.get("allow_confirmed_external_agent_launch", False)),
        }
        bad = [k for k, v in dangerous_defaults.items() if v]
        if bad:
            self.failures.append("settings_store:dangerous_defaults_enabled")
        return self._record(CheckResult(
            check_id="settings_store",
            subsystem="settings_store",
            command="settings show + settings validate",
            status="fail" if bad or show.status == "fail" or validate.status == "fail" else "pass",
            exit_code=0 if not bad and show.exit_code == 0 and validate.exit_code == 0 else 1,
            stdout_excerpt=json.dumps({"dangerous_defaults": dangerous_defaults, "paths": store.get_paths()})[:800],
            stderr_excerpt="" if not bad else f"Dangerous defaults enabled: {', '.join(bad)}",
            artifact_path=str(store.project_settings_path.relative_to(self.repo_root)) if store.project_settings_path.exists() else "",
            recommendation="Reset dangerous settings to false" if bad else "",
        ))

    def _runtime_executor_check(self) -> dict[str, Any]:
        registry = ActionRegistry(self.repo_root)
        action = registry.actions.get("refresh_status")
        if action is None:
            return self._record(CheckResult(
                check_id="runtime_executor",
                subsystem="runtime_executor",
                command="ActionRegistry.refresh_status",
                status="fail",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt="refresh_status action missing",
                artifact_path="",
                recommendation="Define the refresh_status action in the registry",
            ))

        plan = registry.build_plan("refresh_status", None, "safe")
        plan.allowed = False
        plan.safety.shell = False
        if plan.safety.shell:
            return self._record(CheckResult(
                check_id="runtime_executor",
                subsystem="runtime_executor",
                command="build_plan(refresh_status)",
                status="fail",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt="shell=True would be used",
                artifact_path="",
                recommendation="Fix command plan generation",
            ))

        executor = RuntimeExecutor(self.repo_root)
        result = executor.execute_plan(plan)
        result_path = executor.actions_dir / plan.plan_id / "result.json"
        blocked_ok = result.status == "blocked" and result_path.exists()
        if not blocked_ok:
            self.failures.append("runtime_executor:blocked_plan_failed")
        return self._record(CheckResult(
            check_id="runtime_executor",
            subsystem="runtime_executor",
            command="execute blocked CommandPlan",
            status="pass" if blocked_ok else "fail",
            exit_code=0 if blocked_ok else 1,
            stdout_excerpt=json.dumps({"status": result.status, "stdout_path": result.stdout_path, "stderr_path": result.stderr_path})[:800],
            stderr_excerpt="" if blocked_ok else "Blocked plan did not produce a receipt",
            artifact_path=str(result_path.relative_to(self.repo_root)) if result_path.exists() else "",
            recommendation="Inspect runtime executor receipts" if not blocked_ok else "",
        ))

    def _projections_check(self) -> dict[str, Any]:
        status = self._run("projections_status", "projections", [self.python_exec, "scripts/rig.py", "projections", "status"])
        self._record(status)
        dry = self._run("projections_rebuild_dry", "projections", [self.python_exec, "scripts/rig.py", "projections", "rebuild", "--dry-run"])
        self._record(dry)

        builder = ProjectionsBuilder(self.repo_root)
        manifest = builder.rebuild(dry_run=True)
        kinds = {p.get("kind") for p in manifest.get("projections", []) if isinstance(p, dict)}
        required = {"kanban", "task_graph", "monitor", "tui_snapshot"}
        missing = sorted(required - kinds)
        if missing:
            self.failures.append(f"projections_missing:{','.join(missing)}")
        return self._record(CheckResult(
            check_id="projections",
            subsystem="projections",
            command="projections status + rebuild --dry-run",
            status="pass" if not missing and status.exit_code == 0 and dry.exit_code == 0 else "fail",
            exit_code=0 if not missing and status.exit_code == 0 and dry.exit_code == 0 else 1,
            stdout_excerpt=json.dumps({"kinds": sorted(kinds), "missing": missing})[:800],
            stderr_excerpt="" if not missing else f"Missing projection kinds: {', '.join(missing)}",
            artifact_path=str(builder.projections_dir / "latest.json"),
            recommendation="Rebuild projections until required kinds exist" if missing else "",
        ))

    def _memory_contracts_check(self) -> dict[str, Any]:
        settings = SettingsStore(self.repo_root).get_effective_settings()
        pressure = sample_system_pressure(self.repo_root)
        report = evaluate_memory_contracts(self.repo_root, settings, pressure)
        checks = report.get("checks", [])
        warn_details = [c.get("detail", "") for c in checks if c.get("status") == "warn"]
        fail_details = [c.get("detail", "") for c in checks if c.get("status") == "fail"]
        for detail in warn_details:
            self.warnings.append(f"memory_contracts:{detail}")
        for detail in fail_details:
            self.failures.append(f"memory_contracts:{detail}")
        return self._record(CheckResult(
            check_id="memory_contracts",
            subsystem="memory_contracts",
            command="evaluate memory contracts",
            status="fail" if fail_details else ("warn" if warn_details else "pass"),
            exit_code=0 if not fail_details else 1,
            stdout_excerpt=json.dumps(report)[:800],
            stderr_excerpt="" if not fail_details else "; ".join(fail_details),
            artifact_path=str(self.repo_root / ".build" / "rig" / "projections" / "latest.json"),
            recommendation="Trim projections and keep raw logs file-backed" if (warn_details or fail_details) else "",
        ))

    def _swarm_check(self) -> dict[str, Any]:
        report = proposal_swarm.status(self.repo_root)
        warning_items = list(report.get("warnings", []) or [])
        warning_items = [
            "Proposal Swarm limited: llama-server unavailable; MLX fallback only." if warning == "proposal_swarm" else warning
            for warning in warning_items
        ]
        warning_text = "; ".join(warning_items)
        status = "pass"
        recommendation = ""
        if report.get("status") == "blocked":
            status = "warn"
            recommendation = "Configure llama.cpp backend or use a non-blocked swarm profile before running proposal swarms"
        elif report.get("status") == "warn":
            status = "warn"
        return self._record(CheckResult(
            check_id="proposal_swarm",
            subsystem="proposal_swarm",
            command="swarm status",
            status=status,
            exit_code=0,
            stdout_excerpt=json.dumps({
                "active_backend": report.get("active_backend"),
                "latest_swarm": report.get("latest_swarm"),
                "profile_count": len(report.get("profiles", [])) if isinstance(report.get("profiles"), list) else None,
            })[:800],
            stderr_excerpt=warning_text,
            artifact_path=str((self.repo_root / ".build" / "rig" / "swarm" / "latest.json").relative_to(self.repo_root)) if (self.repo_root / ".build" / "rig" / "swarm" / "latest.json").exists() else "",
            recommendation=recommendation,
        ))

    def _loop_check(self) -> dict[str, Any]:
        policy = self._run("loop_policy_show", "loop_engine", [self.python_exec, "scripts/rig.py", "loop", "policy", "show", "--task", "audit-smoke"])
        self._record(policy)
        dry = self._run("loop_run_dry", "loop_engine", [self.python_exec, "scripts/rig.py", "loop", "run", "--task", "audit-smoke", "--mode", "read_only", "--max-steps", "1", "--dry-run"])
        self._record(dry)

        run_ok = dry.exit_code == 0 and "dry run" in (dry.stdout_excerpt.lower() + dry.stderr_excerpt.lower() + "dry run")
        return self._record(CheckResult(
            check_id="loop_engine",
            subsystem="loop_engine",
            command="loop policy show + loop run --dry-run",
            status="pass" if run_ok else "fail",
            exit_code=0 if run_ok else 1,
            stdout_excerpt=dry.stdout_excerpt,
            stderr_excerpt=dry.stderr_excerpt,
            artifact_path=str(self.repo_root / ".build" / "rig" / "loops"),
            recommendation="" if run_ok else "Verify dry-run suppresses subprocess execution",
        ))

    def _gc_check(self) -> dict[str, Any]:
        plan = self._run("gc_plan", "garbage_collection", [self.python_exec, "scripts/rig.py", "gc", "plan"])
        self._record(plan)
        dry = self._run("gc_run_dry", "garbage_collection", [self.python_exec, "scripts/rig.py", "gc", "run"])
        self._record(dry)

        gc = GarbageCollector(self.repo_root)
        plan_data = gc.create_plan()
        dry_run_data = gc.run(plan_data, mode="dry_run")
        gc_dir = self.repo_root / ".build" / "rig" / "gc"
        plan_file = gc_dir / "latest-plan.json"
        status = "pass" if plan.exit_code == 0 and dry.exit_code == 0 and dry_run_data.get("status") == "dry_run" and not dry_run_data.get("deleted_paths") else "fail"
        return self._record(CheckResult(
            check_id="garbage_collection",
            subsystem="garbage_collection",
            command="gc plan + gc run",
            status=status,
            exit_code=0 if status == "pass" else 1,
            stdout_excerpt=dry.stdout_excerpt,
            stderr_excerpt=dry.stderr_excerpt,
            artifact_path=str(plan_file.relative_to(self.repo_root)) if plan_file.exists() else str(gc_dir),
            recommendation="" if status == "pass" else "Confirm dry-run GC produces a stable plan and no deletes",
        ))

    def _scheduler_check(self) -> dict[str, Any]:
        scheduler = Scheduler(self.repo_root)
        status = self._run("scheduler_status", "scheduler", [self.python_exec, "scripts/rig.py", "scheduler", "status"])
        self._record(status)
        jobs = scheduler.get_all_jobs()
        issues: list[str] = []
        for job in jobs:
            if "tui" in job.get("job_id", "").lower() or "tui" in job.get("label", "").lower():
                issues.append(f"tui_job:{job['job_id']}")
            if job.get("job_id") == "queue-runner" and job.get("enabled", False):
                issues.append("queue_runner_enabled")
            if not isinstance(job.get("command_argv"), list):
                issues.append(f"argv_not_list:{job.get('job_id')}")
            if not Path(job.get("working_directory", "")).is_absolute():
                issues.append(f"working_directory_not_absolute:{job.get('job_id')}")
        install = self._run("scheduler_install_dry", "scheduler", [self.python_exec, "scripts/rig.py", "scheduler", "install", "--job", "morning-monitor", "--dry-run"])
        self._record(install)
        status_ok = not issues and status.exit_code == 0 and install.exit_code == 0
        return self._record(CheckResult(
            check_id="scheduler",
            subsystem="scheduler",
            command="scheduler status + install --dry-run",
            status="pass" if status_ok else "fail",
            exit_code=0 if status_ok else 1,
            stdout_excerpt=json.dumps({"jobs": len(jobs), "issues": issues})[:800],
            stderr_excerpt="" if status_ok else f"Scheduler issues: {', '.join(issues)}",
            artifact_path=str(self.repo_root / ".build" / "rig" / "scheduler"),
            recommendation="" if status_ok else "Disable queue-runner by default and remove any TUI jobs",
        ))

    def _vault_check(self) -> dict[str, Any]:
        status = self._run("vault_status", "vault_export", [self.python_exec, "scripts/rig.py", "vault", "status", "--format", "json"])
        self._record(status)
        export = self._run("vault_export_dry", "vault_export", [self.python_exec, "scripts/rig.py", "vault", "export", "--dry-run", "--format", "json"])
        self._record(export)
        vault_root = self.repo_root / ".build" / "rig" / "vault"
        parsed_export: dict[str, Any] = {}
        try:
            parsed_export = json.loads(export.stdout_excerpt or "{}")
        except Exception:
            parsed_export = {}
        notes_ok = (
            status.exit_code == 0
            and export.exit_code == 0
            and str(parsed_export.get("status") or "").lower() in {"dry_run", "pass"}
            and ".build/rig/vault" in str(parsed_export.get("vault_path") or status.stdout_excerpt or "")
        )
        return self._record(CheckResult(
            check_id="vault_export",
            subsystem="vault_export",
            command="vault status + export --dry-run",
            status="pass" if status.exit_code == 0 and export.exit_code == 0 and notes_ok else "fail",
            exit_code=0 if status.exit_code == 0 and export.exit_code == 0 and notes_ok else 1,
            stdout_excerpt=export.stdout_excerpt,
            stderr_excerpt=export.stderr_excerpt,
            artifact_path=str(vault_root),
            recommendation="" if notes_ok else "Confirm vault export emits a dry-run preview under .build only",
        ))

    def _anigma_checks(self) -> dict[str, Any]:
        sentinel_path = self.repo_root / "Scripts" / "rig_os_sentinel.py"
        if not sentinel_path.exists():
            result = self._record(CheckResult(
                check_id="sentinel",
                subsystem="rig_os_sentinel",
                command=f"{self.python_exec} {sentinel_path} --format json",
                status="warn",
                exit_code=127,
                stdout_excerpt="",
                stderr_excerpt="Sentinel missing",
                artifact_path=str(sentinel_path),
                recommendation="Restore the Rig OS sentinel script",
            ))
            return result

        env = dict(os.environ)
        env["RIG_SKIP_DOCTOR_CHECK"] = "1"
        proc = subprocess.run([self.python_exec, str(sentinel_path), "--format", "json"], cwd=self.repo_root, text=True, capture_output=True, check=False, env=env)
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(proc.stdout or "{}")
        except Exception:
            payload = {}
        sentinel_status = str(payload.get("status") or ("pass" if proc.returncode == 0 else "fail"))
        status = "pass" if sentinel_status == "pass" else "warn" if sentinel_status in {"warn", "fail"} else "warn"
        if sentinel_status == "fail":
            self.warnings.append("rig_os_sentinel:fail")
        elif sentinel_status == "warn":
            self.warnings.append("rig_os_sentinel:warn")
        sentinel = self._record(CheckResult(
            check_id="sentinel",
            subsystem="rig_os_sentinel",
            command=f"{self.python_exec} {sentinel_path} --format json",
            status=status,
            exit_code=proc.returncode,
            stdout_excerpt=_excerpt(proc.stdout or ""),
            stderr_excerpt=_excerpt(proc.stderr or ""),
            artifact_path=str(sentinel_path),
            recommendation="Follow the failing subsystem list if sentinel reports fail" if sentinel_status == "fail" else "",
        ))
        adapter = self._run("anigma_loop_status", "anigma_adapter", [self.python_exec, "scripts/rig.py", "anigma", "loop", "status"])
        if adapter.status != "pass":
            adapter.status = "warn"
            adapter.recommendation = "Anigma adapter warnings are informational unless strict mode is enabled"
            self.warnings.append("anigma_loop_status_warn")
        self._record(adapter)
        return sentinel

    def _tui_checks(self) -> None:
        textual_bin = shutil.which("textual")
        if textual_bin:
            result = self._run("textual_validate", "textual", [textual_bin, "validate", "--agent"])
            self._record(result)
        else:
            self._record(CheckResult(
                check_id="textual_validate",
                subsystem="textual",
                command="textual validate --agent",
                status="skipped",
                exit_code=127,
                stdout_excerpt="",
                stderr_excerpt="textual not installed",
                artifact_path="",
                recommendation="Install textual if TUI validation should run locally",
            ))

        help_res = self._run("rig_tui_help", "textual", [self.python_exec, "scripts/rig.py", "tui", "--help"])
        self._record(help_res)

    def _package_hygiene(self) -> None:
        compile_cmd = [self.python_exec, "-m", "py_compile", "scripts/rig.py", "scripts/rig/main.py", "scripts/rig/commands_doctor.py", "scripts/rig/commands_audit.py", "scripts/rig_tools/doctor.py", "scripts/rig_tools/contract_audit.py"]
        pyc = self._run("py_compile", "python_hygiene", compile_cmd)
        self._record(pyc)
        if pyc.exit_code != 0:
            self.failures.append("python_hygiene:py_compile_failed")

        public_doc_roots = [
            self.repo_root / "Docs" / "dev",
            self.repo_root / "Docs" / "README.md",
        ]
        public_docs: list[Path] = []
        for root in public_doc_roots:
            if root.is_dir():
                public_docs.extend(root.rglob("*.md"))
            elif root.is_file():
                public_docs.append(root)
        hardcoded = [
            str(p.relative_to(self.repo_root))
            for p in public_docs
            if "/Users/user/" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        if hardcoded:
            self.warnings.append("hardcoded_local_paths_in_docs")

        no_shell_true = True
        for path in (self.repo_root / "scripts" / "rig_tools").rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "shell" and isinstance(node.value, ast.Constant) and node.value.value is True:
                    no_shell_true = False
                    break
            if not no_shell_true:
                break
        if not no_shell_true:
            self.failures.append("shell_true_detected_in_rig_tools")

    def _window_checks(self) -> None:
        import shutil
        textual_bin = shutil.which("textual") or shutil.which("textual-serve")
        if textual_bin:
            self._record(CheckResult(
                check_id="window_textual_serve",
                subsystem="window",
                command="which textual-serve",
                status="passed",
                exit_code=0,
                stdout_excerpt=f"Found at {textual_bin}",
                stderr_excerpt="",
                artifact_path="",
                recommendation="",
            ))
        else:
            self._record(CheckResult(
                check_id="window_textual_serve",
                subsystem="window",
                command="which textual-serve",
                status="skipped",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt="textual serve not found",
                artifact_path="",
                recommendation="Install the tui extra or textual directly",
            ))

        try:
            import webview
            self._record(CheckResult(
                check_id="window_pywebview",
                subsystem="window",
                command="import webview",
                status="passed",
                exit_code=0,
                stdout_excerpt="pywebview available",
                stderr_excerpt="",
                artifact_path="",
                recommendation="",
            ))
        except ImportError:
            self._record(CheckResult(
                check_id="window_pywebview",
                subsystem="window",
                command="import webview",
                status="skipped",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt="pywebview not found",
                artifact_path="",
                recommendation="Install pywebview for native window support",
            ))

    def _project_checks(self) -> None:
        digest_path = self.repo_root / ".build" / "rig" / "project" / "latest-digest.json"
        if not digest_path.exists():
            self._record(CheckResult(
                check_id="project_digest_present",
                subsystem="project_management",
                command="project digest --dry-run",
                status="warn",
                exit_code=0,
                stdout_excerpt="",
                stderr_excerpt="Project digest missing",
                artifact_path="",
                recommendation="Run 'rig project digest' to map the codebase",
            ))
            self.warnings.append("missing_project_digest")
        else:
            self._record(CheckResult(
                check_id="project_digest_present",
                subsystem="project_management",
                command="project digest",
                status="pass",
                exit_code=0,
                stdout_excerpt="Project digest present",
                stderr_excerpt="",
                artifact_path=str(digest_path),
                recommendation="",
            ))

        profile_path = self.repo_root / ".rig" / "project.json"
        if not profile_path.exists():
            self._record(CheckResult(
                check_id="project_profile_present",
                subsystem="project_management",
                command="project profile show",
                status="warn",
                exit_code=0,
                stdout_excerpt="",
                stderr_excerpt="Project profile missing",
                artifact_path="",
                recommendation="Run 'rig project profile apply' to initialize Rig for this repo",
            ))
            self.warnings.append("uninitialized_project")
        else:
            self._record(CheckResult(
                check_id="project_profile_present",
                subsystem="project_management",
                command="project profile show",
                status="pass",
                exit_code=0,
                stdout_excerpt="Project profile present",
                stderr_excerpt="",
                artifact_path=str(profile_path),
                recommendation="",
            ))

    def _structural_checks(self) -> None:
        report_path = self.repo_root / ".build" / "rig" / "structural" / "latest.json"
        if not report_path.exists():
            self._record(CheckResult(
                check_id="structural_report_present",
                subsystem="structural_validators",
                command="structural scan --dry-run",
                status="warn",
                exit_code=0,
                stdout_excerpt="",
                stderr_excerpt="Structural report missing",
                artifact_path="",
                recommendation="Run 'rig structural scan' to detect code risk",
            ))
            self.warnings.append("missing_structural_report")
        else:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                status = "passed" if report["status"] == "pass" else report["status"]
                self._record(CheckResult(
                    check_id="structural_report_present",
                    subsystem="structural_validators",
                    command="structural scan",
                    status=status,
                    exit_code=0,
                    stdout_excerpt=f"Latest report: {report['status'].upper()} ({len(report['findings'])} findings)",
                    stderr_excerpt="",
                    artifact_path=str(report_path),
                    recommendation="Review findings in .build/rig/structural/latest.md",
                ))
            except Exception:
                self.warnings.append("invalid_structural_report")

    def _bootstrap_checks(self) -> None:
        from rig_tools import bootstrap_walkthrough
        state = bootstrap_walkthrough.detect_folder_state(self.repo_root)
        status = "pass" if state == "existing_project" else "warn"
        rec = "Run 'rig bootstrap walkthrough' to initialize project" if state != "existing_project" else ""
        
        self._record(CheckResult(
            check_id="bootstrap_status",
            subsystem="bootstrap",
            command="bootstrap status",
            status=status,
            exit_code=0,
            stdout_excerpt=f"Folder state: {state}",
            stderr_excerpt="",
            artifact_path="",
            recommendation=rec,
        ))

    def _bench_checks(self) -> None:
        from rig_tools import system_benchmark
        latest = system_benchmark.get_latest_benchmark(self.repo_root)
        status = "pass" if latest else "warn"
        rec = "Run 'rig bench run --quick' to profile system" if not latest else ""
        
        self._record(CheckResult(
            check_id="system_benchmark_status",
            subsystem="benchmark",
            command="bench status",
            status=status,
            exit_code=0,
            stdout_excerpt=f"Profile: {latest['recommended_profile']['profile_id']}" if latest else "Not profiled",
            stderr_excerpt="",
            artifact_path="",
            recommendation=rec,
        ))

    def _model_checks(self) -> None:
        from rig_tools import model_manager
        catalog = model_manager.load_catalog(self.repo_root)
        registered = model_manager.list_registered_models(self.repo_root)
        
        self._record(CheckResult(
            check_id="model_manager_status",
            subsystem="models",
            command="models list",
            status="pass" if catalog.get("models") else "warn",
            exit_code=0,
            stdout_excerpt=f"Catalog models: {len(catalog.get('models', []))}, Registered: {len(registered)}",
            stderr_excerpt="",
            artifact_path="",
            recommendation="",
        ))

    def _product_checks(self) -> None:
        from rig_tools import productization_check
        pc = productization_check.ProductizationChecker(self.repo_root)
        # We run in dry-run to avoid writing artifacts during doctor check
        report = pc.run_check(dry_run=True)
        
        self._record(CheckResult(
            check_id="product_readiness",
            subsystem="product",
            command="product check",
            status=report["status"],
            exit_code=0 if report["status"] != "fail" else 1,
            stdout_excerpt=f"Product status: {report['status'].upper()}, failures: {len(report['failures'])}",
            stderr_excerpt="",
            artifact_path="",
            recommendation="Run 'rig product check' for details",
        ))

    def _workspace_checks(self) -> None:
        from rig_tools import workspace_manager
        wm = workspace_manager.WorkspaceManager(self.repo_root)
        workspaces = wm.list_workspaces()
        
        self._record(CheckResult(
            check_id="workspace_status",
            subsystem="workspaces",
            command="workspace list",
            status="pass" if workspaces else "warn",
            exit_code=0,
            stdout_excerpt=f"Total workspaces: {len(workspaces)}",
            stderr_excerpt="",
            artifact_path="",
            recommendation="Run 'rig workspace create' to start work" if not workspaces else "",
        ))

    def _intent_checks(self) -> None:
        from rig_tools import intent_decoder
        self._record(CheckResult(
            check_id="intent_decoder_status",
            subsystem="intent_decoder",
            command="intent status",
            status="pass",
            exit_code=0,
            stdout_excerpt=f"Supported intents: {len(intent_decoder.SAFE_ALIASES)}",
            stderr_excerpt="",
            artifact_path="",
            recommendation="",
        ))

    def _bias_checks(self) -> None:
        from rig_tools import solution_bias
        report = solution_bias.validate_profiles(self.repo_root)
        if report["status"] == "pass":
            self._record(CheckResult(
                check_id="solution_bias_profiles",
                subsystem="solution_bias",
                command="bias validate",
                status="passed",
                exit_code=0,
                stdout_excerpt=f"Validated {len(report['profiles'])} profiles",
                stderr_excerpt="",
                artifact_path="",
                recommendation="",
            ))
        else:
            invalid = [p["profile_id"] for p in report["profiles"] if p["status"] == "fail"]
            self._record(CheckResult(
                check_id="solution_bias_profiles",
                subsystem="solution_bias",
                command="bias validate",
                status="fail",
                exit_code=1,
                stdout_excerpt="",
                stderr_excerpt=f"Invalid profiles: {', '.join(invalid)}",
                artifact_path="",
                recommendation="Fix bias profile JSON files in Docs/dev/rig/bias-profiles/",
            ))
            self.failures.append("invalid_bias_profiles")

    def run_all(self) -> dict[str, Any]:
        self._state_store_check()
        self._settings_check()
        self._runtime_executor_check()
        self._projections_check()
        self._memory_contracts_check()
        self._loop_check()
        self._gc_check()
        self._swarm_check()
        self._scheduler_check()
        self._vault_check()
        self._project_checks()
        self._structural_checks()
        self._bootstrap_checks()
        self._bench_checks()
        self._model_checks()
        self._product_checks()
        self._workspace_checks()
        self._intent_checks()
        self._bias_checks()
        self._anigma_checks()
        self._tui_checks()
        self._window_checks()
        self._package_hygiene()

        status = "pass"
        if self.failures:
            status = "fail"
        elif self.warnings:
            status = "warn"

        report = {
            "schema_version": SCHEMA_VERSION,
            "report_id": f"doc-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "created_at": _utc_now(),
            "status": status,
            "checks": self.checks,
            "failures": self.failures,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "artifact_paths": [],
            "authoritative": True,
        }
        self._write_report(report)
        return report

    def _write_report(self, report: dict[str, Any]) -> None:
        out_dir = self.repo_root / ".build" / "rig" / "doctor"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "latest.json"
        md_path = out_dir / "latest.md"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_lines = [
            "# Rig Doctor Report",
            f"- Status: {report['status']}",
            f"- Created: {report['created_at']}",
            "",
            "## Checks",
        ]
        for check in report["checks"]:
            md_lines.append(f"- [{check['status']}] {check['subsystem']} / {check['check_id']} :: {check['command']}")
            if check.get("stderr_excerpt"):
                md_lines.append(f"  - stderr: {check['stderr_excerpt']}")
        if report["warnings"]:
            md_lines.extend(["", "## Warnings"])
            md_lines.extend(f"- {w}" for w in report["warnings"])
        if report["failures"]:
            md_lines.extend(["", "## Failures"])
            md_lines.extend(f"- {f}" for f in report["failures"])
        if report["recommendations"]:
            md_lines.extend(["", "## Recommendations"])
            md_lines.extend(f"- {r}" for r in report["recommendations"] if r)
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        report["artifact_paths"] = [str(json_path.relative_to(self.repo_root)), str(md_path.relative_to(self.repo_root))]
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_doctor(repo_root: Path, format_type: str = "text") -> int:
    report = RigDoctor(repo_root).run_all()
    if format_type == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Rig Doctor: {report['status'].upper()}")
        for check in report["checks"]:
            print(f"- [{check['status'].upper()}] {check['subsystem']} / {check['check_id']}")
        if report["warnings"]:
            print("\nWarnings:")
            for warning in report["warnings"]:
                print(f"- {warning}")
        if report["failures"]:
            print("\nFailures:")
            for failure in report["failures"]:
                print(f"- {failure}")
    return 0 if report["status"] != "fail" else 1
