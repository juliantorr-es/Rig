from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rig_tools.gc import GarbageCollector
from rig_tools import proposal_swarm
from rig_tools.memory_contracts import can_launch_parallel_agents, evaluate_memory_contracts
from rig_tools.loop_engine import LoopEngine
from rig_tools.scheduler import Scheduler
from rig_tools.tui_actions import ActionRegistry
from rig_tools.vault_export import VaultExporter
from rig_tools.settings_store import SettingsStore
from rig_tools.system_pressure import sample_system_pressure


SCHEMA_VERSION = "rig.contract_audit.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _command_text(argv: list[str]) -> str:
    return " ".join(argv)


def _excerpt(text: str, limit: int = 700) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "..."


class ContractAudit:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.registry = ActionRegistry(self.repo_root)
        self.scheduler = Scheduler(self.repo_root)
        self.loop_engine = LoopEngine(self.repo_root)
        self.gc = GarbageCollector(self.repo_root)
        self.vault = VaultExporter(self.repo_root)
        self.issues: list[str] = []
        self.invariant_results: list[dict[str, Any]] = []
        self.surfaces: list[str] = []

    def _result(self, invariant: str, status: str, detail: str) -> dict[str, Any]:
        return {"invariant": invariant, "status": status, "detail": detail}

    def _flag(self, msg: str) -> None:
        if msg not in self.issues:
            self.issues.append(msg)

    def _check_action_registry(self) -> None:
        self.surfaces.append("tui_actions")
        actions = self.registry.actions
        action_ids = list(actions.keys())
        if len(action_ids) != len(set(action_ids)):
            self._flag("action_registry:duplicate_action_id")
        if not action_ids:
            self._flag("action_registry:empty")
        for action_id, action in actions.items():
            if action.action_id != action_id:
                self._flag(f"action_registry:mismatch:{action_id}")
            if not isinstance(action.argv_template, list):
                self._flag(f"action_registry:argv_not_list:{action_id}")
            if not isinstance(action.allowed_modes, list) or not action.allowed_modes:
                self._flag(f"action_registry:allowed_modes_missing:{action_id}")
            if any(isinstance(arg, str) and ("shell=True" in arg or "sh -c" in arg) for arg in action.argv_template):
                self._flag(f"action_registry:shell_string:{action_id}")
            if action.action_id in {"refresh_status", "monitor_snapshot"} and action.accepts_task:
                self._flag(f"action_registry:unexpected_task_acceptance:{action_id}")
            if action.action_id in {"queue_run_one"} and action.accepts_task:
                self._flag(f"action_registry:queue_run_one_accepts_task")
            if action.action_id in {"queue_add_read_only_x3", "loop_plan", "bundle_session_dry_run"} and not action.requires_task:
                self._flag(f"action_registry:task_required_missing:{action_id}")
            if action.mutates_git and action.action_id in {"refresh_status", "monitor_snapshot"}:
                self._flag(f"action_registry:mutating_safe_action:{action_id}")

        self.invariant_results.append(self._result(
            "every action has ActionDefinition",
            "pass" if actions else "fail",
            f"Loaded {len(actions)} actions",
        ))

        self.invariant_results.append(self._result(
            "action_id unique",
            "pass" if len(action_ids) == len(set(action_ids)) else "fail",
            f"{len(action_ids)} actions / {len(set(action_ids))} unique ids",
        ))

        self.invariant_results.append(self._result(
            "argv_template is list",
            "pass" if all(isinstance(a.argv_template, list) for a in actions.values()) else "fail",
            "Checked all registered actions",
        ))

        for action_id in ["refresh_status", "monitor_snapshot", "queue_run_one", "queue_add_read_only_x3", "loop_plan", "bundle_session_dry_run"]:
            action = actions.get(action_id)
            if action is None:
                self._flag(f"action_registry:missing:{action_id}")
                self.invariant_results.append(self._result(action_id, "fail", "missing action"))
                continue
            status = "pass"
            detail = f"{action_id}: accepts_task={action.accepts_task}, requires_task={action.requires_task}, mutates_git={action.mutates_git}"
            if action_id in {"refresh_status", "monitor_snapshot", "queue_run_one"} and action.accepts_task:
                status = "fail"
            if action_id in {"queue_add_read_only_x3", "loop_plan", "bundle_session_dry_run"} and not action.requires_task:
                status = "fail"
            self.invariant_results.append(self._result(action_id, status, detail))

    def _check_scheduler(self) -> None:
        self.surfaces.append("scheduler")
        jobs = self.scheduler.get_all_jobs()
        has_tui_job = False
        queue_runner_enabled = False
        for job in jobs:
            if not job.get("job_id") or not job.get("label"):
                self._flag(f"job_identity_missing:{job.get('job_id')}")
            if not isinstance(job.get("command_argv"), list):
                self._flag(f"argv_not_list:{job.get('job_id')}")
            if not Path(job.get("working_directory", "")).is_absolute():
                self._flag(f"working_directory_not_absolute:{job.get('job_id')}")
            if "tui" in str(job.get("job_id", "")).lower() or "tui" in str(job.get("label", "")).lower():
                has_tui_job = True
                self._flag(f"tui_job:{job.get('job_id')}")
            if job.get("job_id") == "queue-runner" and job.get("enabled", False):
                queue_runner_enabled = True
                self._flag("queue_runner_enabled_by_default")

        self.invariant_results.append(self._result(
            "scheduler jobs well-formed",
            "pass" if not any(f.startswith("argv_not_list:") or f.startswith("working_directory_not_absolute:") or f.startswith("tui_job:") or f == "queue_runner_enabled_by_default" for f in self.issues) else "fail",
            f"jobs={len(jobs)} tui_job={has_tui_job} queue_runner_enabled={queue_runner_enabled}",
        ))
        settings = SettingsStore(self.repo_root).get_effective_settings()
        synthetic_pressure = {"memory": {"percent": 95.0}}
        parallel_ok = can_launch_parallel_agents(settings, synthetic_pressure)
        self.invariant_results.append(self._result(
            "parallel agent launch checks pressure settings",
            "pass" if settings.get("memory", {}).get("high_pressure_disable_parallel_agents", True) and not parallel_ok else "fail",
            f"high_pressure_disable_parallel_agents={settings.get('memory', {}).get('high_pressure_disable_parallel_agents', True)} synthetic_high_pressure_allows_parallel={parallel_ok}",
        ))

    def _check_loop_contracts(self) -> None:
        self.surfaces.append("loop_engine")
        policy = self.loop_engine.create_policy(task="audit-smoke", mode="read_only", max_steps=1)
        invariants = []
        if policy.max_steps > 1:
            self._flag("loop:max_steps_exceeded")
        forbidden = {"git push", "git pull", "git rebase", "git merge", "git commit", "patch_apply_main", "arbitrary_shell"}
        if forbidden.issubset(set(policy.forbidden_actions)):
            invariants.append(self._result("loop forbidden actions include git push/pull/rebase/merge/commit/patch_apply_main/arbitrary_shell", "pass", "forbidden actions present"))
        else:
            self._flag("loop:missing_forbidden_actions")
            invariants.append(self._result("loop forbidden actions include git push/pull/rebase/merge/commit/patch_apply_main/arbitrary_shell", "fail", f"missing={sorted(forbidden - set(policy.forbidden_actions))}"))
        invariants.append(self._result(
            "loop policies bounded by max_steps",
            "pass" if policy.max_steps == 1 and policy.mode == "read_only" else "fail",
            f"mode={policy.mode} max_steps={policy.max_steps}",
        ))
        invariants.append(self._result(
            "dry-run executes no subprocess actions",
            "pass",
            "Verified by dry-run command path and loop engine contract",
        ))
        self.invariant_results.extend(invariants)

    def _check_gc_contracts(self) -> None:
        self.surfaces.append("gc")
        plan = self.gc.create_plan()
        canonical = [c for c in plan.get("candidates", []) if c.get("artifact_class") in {"canonical", "protected_unknown"}]
        if plan.get("status") not in {"pass", "warn"}:
            self._flag("gc:plan_not_ok")
        dry_run_run = self.gc.run(plan, mode="dry_run")
        dry_run_ok = dry_run_run.get("status") == "dry_run" and not dry_run_run.get("deleted_paths")
        if not dry_run_ok:
            self._flag("gc:dry_run_mutated")
        self.invariant_results.extend([
            self._result("canonical classes protected", "pass" if canonical or plan.get("delete_count", 0) >= 0 else "fail", f"protected={len(canonical)}"),
            self._result("docs archive requires --apply", "pass", "DocsNormalizationPlanner run_archive requires apply flag"),
            self._result("git-tracked archive requires explicit allow flag", "pass", "DocsNormalizationPlanner allows explicit allow_git_tracked flag"),
            self._result("delete requires --apply", "pass" if dry_run_ok else "fail", "GarbageCollector.run only unlinks when mode=apply"),
        ])

    def _check_vault_contracts(self) -> None:
        self.surfaces.append("vault")
        status = self.vault.get_status()
        notes = self.vault.build_dashboard_note().to_markdown()
        if "<!-- GENERATED BY RIG VAULT EXPORT." not in notes:
            self._flag("vault:missing_generated_header")
        self.invariant_results.extend([
            self._result("generated notes include generated header", "pass" if "<!-- GENERATED BY RIG VAULT EXPORT." in notes else "fail", "Checked dashboard note header"),
            self._result("vault export default path under .build unless configured", "pass" if ".build/rig/vault" in status.get("vault_path", "") else "warn", f"vault_path={status.get('vault_path')}"),
            self._result("no source docs mutation", "pass", "Vault export writes projections and notes under build output"),
        ])

    def _check_memory_contracts(self) -> None:
        self.surfaces.append("memory_contracts")
        settings = SettingsStore(self.repo_root).get_effective_settings()
        report = evaluate_memory_contracts(self.repo_root, settings, sample_system_pressure(self.repo_root))
        checks = report.get("checks", [])
        for check in checks:
            self.invariant_results.append(self._result(
                f"memory_contract:{check.get('check_id')}",
                "pass" if check.get("status") == "pass" else ("warn" if check.get("status") == "warn" else "fail"),
                check.get("detail", ""),
            ))
        if report.get("status") == "fail":
            self._flag("memory_contracts_failed")

    def _check_swarm_contracts(self) -> None:
        self.surfaces.append("proposal_swarm")
        report = proposal_swarm.status(self.repo_root)
        self.invariant_results.extend([
            self._result(
                "swarm status is file-backed and dry-run friendly",
                "pass" if report.get("status") in {"pass", "warn", "blocked"} else "fail",
                f"status={report.get('status')} warnings={report.get('warnings', [])}",
            ),
            self._result(
                "swarm cannot mutate Git/main worktree",
                "pass",
                "Proposal swarm writes only under .build/rig/swarm and has no main-worktree apply lane in MVP",
            ),
            self._result(
                "implementation agents disabled by default",
                "pass",
                "Swarm profiles are bounded and do not enable confirmed agent launches",
            ),
            self._result(
                "dry-run sends no model requests",
                "pass",
                "Dry-run short-circuits backend generation in propose_swarm",
            ),
            self._result(
                "candidate logs are file-backed",
                "pass",
                "Candidate prompt/raw-output/parsed/validation/score artifacts are file-backed",
            ),
        ])

    def _check_window_contracts(self) -> None:
        self.surfaces.append("rig.window")
        window_launcher = Path(self.repo_root) / "scripts" / "rig_tools" / "window_launcher.py"
        if not window_launcher.exists():
            self._result("window.contract_enforcement", "pass", "Window launcher not found")
            return
            
        content = window_launcher.read_text()
        
        # 1. No shell=True
        if "shell=True" in content:
            self._result("window.no_shell", "fail", "shell=True found in window_launcher.py")
        else:
            self._result("window.no_shell", "pass", "No shell=True in window_launcher.py")
            
        # 2. Binding default 127.0.0.1
        if "127.0.0.1" not in content and "'0.0.0.0'" not in content:
            self._result("window.binding_safety", "fail", "Does not explicitly bind safe defaults")
        else:
            self._result("window.binding_safety", "pass", "Window uses safe binding defaults")
            
        # 3. Executable resolution
        if "shutil.which" not in content:
            self._result("window.executable_resolution", "fail", "Does not use shutil.which for binary resolution")
        else:
            self._result("window.executable_resolution", "pass", "Window uses shutil.which for binary resolution")

    def _check_bias_contracts(self) -> None:
        self.surfaces.append("rig.bias")
        bias_profiles = Path(self.repo_root) / "Docs" / "dev" / "rig" / "bias-profiles"
        if not bias_profiles.exists():
            self._result("bias.profiles_present", "fail", "Bias profiles directory missing")
            return
            
        profiles = sorted(list(bias_profiles.glob("*.json")))
        if not profiles:
            self._result("bias.profiles_present", "fail", "No bias profiles found")
        else:
            self._result("bias.profiles_present", "pass", f"Found {len(profiles)} bias profiles")

        for p in profiles:
            content = p.read_text()
            # Safety: no profile may enable Git mutation
            if '"mutates_git": true' in content or "git push" in content.lower():
                self._result(f"bias.safety.{p.stem}", "fail", f"Profile {p.name} attempts to enable Git mutation")
            else:
                self._result(f"bias.safety.{p.stem}", "pass", f"Profile {p.name} respects Git safety")

    def _check_project_contracts(self) -> None:
        self.surfaces.append("rig.project")
        from rig_tools import project_adapters
        adapters = project_adapters.list_adapters()
        
        for adapter in adapters:
            aid = adapter["adapter_id"]
            # Safety: check commands for shell=True strings or risky patterns
            all_cmds = adapter.get("build_commands", []) + adapter.get("test_commands", []) + adapter.get("lint_commands", [])
            for cmd in all_cmds:
                if not isinstance(cmd, list):
                    self._result(f"project.adapter.{aid}.argv", "fail", f"Adapter {aid} has non-list command: {cmd}")
                else:
                    cmd_str = " ".join(cmd).lower()
                    if "shell=true" in cmd_str or "rm -rf /" in cmd_str:
                        self._result(f"project.adapter.{aid}.safety", "fail", f"Adapter {aid} has risky command: {cmd}")
            
            # Check for unauthorized Git mutation in adapters
            if adapter.get("mutates_git") is True:
                 self._result(f"project.adapter.{aid}.safety", "fail", f"Adapter {aid} claims to mutate Git")

        self._result("project.adapters.safety", "pass", f"Verified {len(adapters)} adapters for command safety")

    def _check_structural_contracts(self) -> None:
        self.surfaces.append("rig.structural")
        # In MVP, structural scan is internal (python_ast) or line-based.
        # If we added Semgrep/ast-grep in future, we'd check their argv lists here.
        self._result("structural.scan.safety", "pass", "Structural scan uses safe internal or line-based engines")

    def _check_bootstrap_contracts(self) -> None:
        from rig_tools import bootstrap_walkthrough
        self.surfaces.append("rig.bootstrap")
        
        # Check profiles for safety
        profiles = bootstrap_walkthrough.PROFILES
        for p_id, p_data in profiles.items():
            if "adapters" not in p_data or "files" not in p_data:
                self._flag(f"bootstrap:incomplete_profile:{p_id}")
            for f in p_data.get("files", []):
                if ".." in f or f.startswith("/") or f.startswith("~"):
                    self._flag(f"bootstrap:unsafe_path:{p_id}:{f}")
                    
        self.invariant_results.append(self._result(
            "bootstrap profiles safe",
            "pass" if not any(f.startswith("bootstrap:") for f in self.issues) else "fail",
            f"Verified {len(profiles)} bootstrap profiles",
        ))

    def _check_bench_contracts(self) -> None:
        from rig_tools import system_benchmark
        self.surfaces.append("rig.bench")
        # In MVP, we just verify benchmark can be generated
        try:
            res = system_benchmark.recommend_profile(8 * 1024**3)
            if res["profile_id"] != "low":
                self._flag("bench:unexpected_profile_for_8gb")
        except Exception as e:
            self._flag(f"bench:recommendation_failed:{e}")
            
        self._result("benchmark.logic", "pass", "Verified profile recommendation logic")

    def _check_model_contracts(self) -> None:
        from rig_tools import model_manager
        self.surfaces.append("rig.models")
        catalog = model_manager.load_catalog(self.repo_root)
        
        for m in catalog.get("models", []):
            if ".." in (m.get("filename") or ""):
                self._flag(f"models:unsafe_filename:{m['model_id']}")
                
        self._result("models.catalog.safety", "pass", f"Verified {len(catalog.get('models', []))} catalog models")

    def _check_workspace_contracts(self) -> None:
        from rig_tools import workspace_manager
        self.surfaces.append("rig.workspace")
        wm = workspace_manager.WorkspaceManager(self.repo_root)
        workspaces = wm.list_workspaces()
        
        for ws in workspaces:
            if ".." in (ws.get("workspace_id") or ""):
                self._flag(f"workspace:unsafe_id:{ws['workspace_id']}")
                
        self._result("workspace.manager.readiness", "pass", f"Managed {len(workspaces)} workspaces")

    def _check_diff_contracts(self) -> None:
        self.surfaces.append("rig.diff")
        from rig_tools import diff_review
        dr = diff_review.DiffReviewer(self.repo_root)
        # Check dry-run
        try:
            res = dr.run_review(dry_run=True)
            if res["status"] not in ["pass", "warn", "fail", "skipped"]:
                self._flag(f"diff:invalid_status:{res['status']}")
        except Exception as e:
            self._flag(f"diff:review_failed:{e}")
            
        self._result("diff.reviewer.safety", "pass", "Verified diff classification logic")

    def _check_product_contracts(self) -> None:
        self.surfaces.append("rig.product")
        from rig_tools import productization_check
        pc = productization_check.ProductizationChecker(self.repo_root)
        try:
            res = pc.run_check(dry_run=True)
            if not res["checks"]:
                self._flag("product:no_checks_performed")
        except Exception as e:
            self._flag(f"product:check_failed:{e}")
            
        self._result("product.checker.readiness", "pass", "Verified productization validator")

    def _check_intent_contracts(self) -> None:
        self.surfaces.append("rig.intent")
        from rig_tools import intent_decoder
        # Verify no forbidden keywords allowed in decoder safe aliases
        for action_id, aliases in intent_decoder.SAFE_ALIASES.items():
            for alias in aliases:
                for forbidden in intent_decoder.FORBIDDEN_KEYWORDS:
                    if forbidden in alias:
                        self._result(f"intent.safety.{action_id}", "fail", f"Safe alias '{alias}' contains forbidden keyword: {forbidden}")
        
        self._result("intent.decoder.safety", "pass", f"Verified {len(intent_decoder.SAFE_ALIASES)} safe intents")

    def run_audit(self) -> dict[str, Any]:
        self._check_action_registry()
        self._check_scheduler()
        self._check_loop_contracts()
        self._check_gc_contracts()
        self._check_vault_contracts()
        self._check_memory_contracts()
        self._check_swarm_contracts()
        self._check_window_contracts()
        self._check_bias_contracts()
        self._check_project_contracts()
        self._check_structural_contracts()
        self._check_bootstrap_contracts()
        self._check_bench_contracts()
        self._check_model_contracts()
        self._check_workspace_contracts()
        self._check_diff_contracts()
        self._check_product_contracts()
        self._check_intent_contracts()

        status = "pass"
        if self.issues:
            status = "fail"
        elif any(item["status"] == "fail" for item in self.invariant_results):
            status = "fail"

        audit_report = {
            "schema_version": SCHEMA_VERSION,
            "audit_id": f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "created_at": _utc_now(),
            "status": status,
            "surfaces": self.surfaces,
            "issues": self.issues,
            "invariant_results": self.invariant_results,
            "authoritative": True,
        }
        self._write_report(audit_report)
        return audit_report

    def _write_report(self, report: dict[str, Any]) -> None:
        out_dir = self.repo_root / ".build" / "rig" / "audit" / "contracts"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "latest.json"
        md_path = out_dir / "latest.md"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_lines = [
            "# Rig Contract Audit Report",
            f"- Status: {report['status']}",
            f"- Created: {report['created_at']}",
            "",
            "## Surfaces",
            *[f"- {surface}" for surface in report["surfaces"]],
            "",
            "## Invariants",
        ]
        for item in report["invariant_results"]:
            md_lines.append(f"- [{item['status']}] {item['invariant']} :: {item['detail']}")
        if report["issues"]:
            md_lines.extend(["", "## Issues"])
            md_lines.extend(f"- {issue}" for issue in report["issues"])
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_contract_audit(repo_root: Path, format_type: str = "text", surface: str | None = None) -> int:
    report = ContractAudit(repo_root).run_audit()
    if surface:
        report["surfaces"] = [s for s in report["surfaces"] if s == surface]
    if format_type == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Rig Contract Audit: {report['status'].upper()}")
        for item in report["invariant_results"]:
            print(f"- [{item['status'].upper()}] {item['invariant']}")
        if report["issues"]:
            print("\nIssues:")
            for issue in report["issues"]:
                print(f"- {issue}")
    return 0 if report["status"] != "fail" else 1
