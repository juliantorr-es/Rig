#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import hashlib
import subprocess
import time
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

# Constants
SCHEMA_VERSION = "rig.os_sentinel.v1"
REPO_ROOT = Path(__file__).parent.parent.resolve()
SENTINEL_PATH = Path(__file__).resolve()
HASH_PATH = REPO_ROOT / "Docs" / "governance" / "rig_os_sentinel.sha256"
BUILD_DIR = REPO_ROOT / ".build" / "rig" / "os-sentinel"

REQUIRED_SUBSYSTEMS = [
    "contracts",
    "runtime_executor",
    "tui_actions",
    "state_store",
    "event_log",
    "projections",
    "loop_engine",
    "garbage_collection",
    "settings_store",
    "scheduler",
    "vault_export",
    "textual_validator",
    "contract_audit",
    "doctor"
]

def get_self_hash() -> str:
    """Computes SHA-256 hash of this script."""
    content = SENTINEL_PATH.read_bytes()
    return hashlib.sha256(content).hexdigest()

def check_hash() -> Dict[str, str]:
    """Checks the sentinel script's hash against the expected value."""
    actual = get_self_hash()
    expected = ""
    status = "missing"
    
    if HASH_PATH.exists():
        expected = HASH_PATH.read_text(encoding="utf-8").strip()
        status = "match" if actual == expected else "mismatch"
    
    return {
        "path": str(SENTINEL_PATH.relative_to(REPO_ROOT)),
        "hash": actual,
        "expected_hash": expected,
        "hash_status": status
    }

def run_command(argv: List[str], timeout: int = 10) -> Dict[str, Any]:
    """Runs a non-destructive command and returns results."""
    if os.environ.get("RIG_SKIP_DOCTOR_CHECK") == "1" and "doctor" in argv:
        return {
            "exit_code": 0,
            "stdout": json.dumps({"status": "skipped", "reason": "doctor check suppressed while validating doctor"}) + "\n",
            "stderr": "",
            "status": "success",
        }
    try:
        proc = subprocess.Popen(
            argv,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "status": "success" if proc.returncode == 0 else "fail"
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "status": "error"
        }

def validate_subsystems() -> List[Dict[str, Any]]:
    """Validates all required Rig OS subsystems."""
    results = []
    
    # 1. Contracts
    results.append(check_subsystem(
        "contracts",
        required_files=[
            "scripts/rig_tools/contracts.py",
            "scripts/test_contracts.py",
            "Docs/dev/rig/CONTRACTS.md",
            "Docs/schemas/rig.action_definition.v1.schema.json",
            "Docs/schemas/rig.command_plan.v1.schema.json",
            "Docs/schemas/rig.action_result.v1.schema.json"
        ],
        required_tests=["python scripts/test_contracts.py"],
        why_it_matters="Rig requires typed ActionDefinition, CommandPlan, and ActionResult to prevent command drift.",
        fix="Implement contracts in scripts/rig_tools/contracts.py and matching schemas.",
        agent_instruction="Implement the contracts subsystem. Ensure ActionDefinition exists and no shell=True is used."
    ))

    # 2. Runtime Executor
    results.append(check_subsystem(
        "runtime_executor",
        required_files=[
            "scripts/rig_tools/runtime_executor.py",
            "scripts/test_runtime_executor.py",
            "Docs/dev/rig/RUNTIME.md"
        ],
        why_it_matters="Executor must run argv lists only, capture output, and write results to prevent unsafe execution.",
        fix="Refactor execution logic into scripts/rig_tools/runtime_executor.py.",
        agent_instruction="Implement the runtime executor. Ensure it uses sys.executable and no shell=True."
    ))

    # 3. TUI Actions
    results.append(check_subsystem(
        "tui_actions",
        required_files=[
            "scripts/rig_tools/tui_actions.py",
            "scripts/test_tui_actions.py"
        ],
        why_it_matters="TUI must use a typed ActionRegistry instead of improvised command dicts.",
        fix="Migrate TUI action logic into scripts/rig_tools/tui_actions.py.",
        agent_instruction="Refactor TUI actions to use the central ActionRegistry."
    ))

    # 4. State Store
    results.append(check_subsystem(
        "state_store",
        required_files=[
            "scripts/rig_tools/state_store.py",
            "scripts/rig/commands_state.py",
            "scripts/test_state_store.py",
            "Docs/dev/rig/STATE_STORE.md"
        ],
        required_commands=[[sys.executable, "scripts/rig.py", "state", "status"]],
        why_it_matters="Rig has no durable operational state for actions, events, and settings.",
        acceptance=[".build/rig/state/rig.sqlite can be opened", "schema_migrations table exists"],
        fix="Implement SQLite state store in scripts/rig_tools/state_store.py.",
        agent_instruction="Implement the state store subsystem using SQLite."
    ))

    # 5. Event Log
    results.append(check_subsystem(
        "event_log",
        required_schema_families=["rig.event.v1"],
        why_it_matters="Append-only JSONL event log is required for operational auditability.",
        fix="Implement unified event logging using rig.event.v1 schema.",
        agent_instruction="Ensure every subsystem writes normalized events to .build/rig/events/latest.jsonl."
    ))

    # 6. Projections
    results.append(check_subsystem(
        "projections",
        required_files=[
            "scripts/rig_tools/projections.py",
            "Docs/dev/rig/PROJECTIONS.md"
        ],
        why_it_matters="Views like Kanban and task graph must be explicit projections of state.",
        fix="Implement projection builder in scripts/rig_tools/projections.py.",
        agent_instruction="Refactor Kanban and graph logic into the projections subsystem."
    ))

    # 7. Loop Engine
    results.append(check_subsystem(
        "loop_engine",
        required_files=[
            "scripts/rig_tools/loop_engine.py",
            "scripts/test_loop_engine.py",
            "Docs/dev/rig/LOOP_ENGINE.md",
            "Docs/schemas/rig.loop_policy.v1.schema.json"
        ],
        required_commands=[[sys.executable, "scripts/rig.py", "loop", "policy", "show"]],
        why_it_matters="Agent loops must be governed by explicit policies and stop conditions.",
        fix="Implement loop engine in scripts/rig_tools/loop_engine.py.",
        agent_instruction="Implement the loop engine and define loop policy schema."
    ))

    # 8. Garbage Collection
    results.append(check_subsystem(
        "garbage_collection",
        required_files=[
            "scripts/rig_tools/gc.py",
            "scripts/rig/commands_gc.py",
            "scripts/test_gc.py",
            "Docs/dev/rig/GARBAGE_COLLECTION.md"
        ],
        required_commands=[[sys.executable, "scripts/rig.py", "gc", "plan"]],
        why_it_matters="Unmanaged build artifacts will lead to resource exhaustion.",
        fix="Implement garbage collection in scripts/rig_tools/gc.py.",
        agent_instruction="Implement GC with ephemeral/cache/receipt classes."
    ))

    # 9. Settings Store
    results.append(check_subsystem(
        "settings_store",
        required_files=[
            "scripts/rig_tools/settings_store.py",
            "scripts/rig/commands_settings.py",
            "Docs/dev/rig/SETTINGS.md"
        ],
        required_commands=[[sys.executable, "scripts/rig.py", "settings", "show"]],
        why_it_matters="Rig settings are currently scattered and lack a central authority.",
        fix="Implement layered settings in scripts/rig_tools/settings_store.py.",
        agent_instruction="Implement centralized settings store with JSON schema validation."
    ))

    # 10. Scheduler
    results.append(check_subsystem(
        "scheduler",
        required_files=[
            "scripts/rig_tools/scheduler.py",
            "Docs/dev/rig/SCHEDULER.md"
        ],
        why_it_matters="Rig needs a reliable way to schedule background monitor and maintenance jobs.",
        fix="Implement macOS LaunchAgent generation in scripts/rig_tools/scheduler.py.",
        agent_instruction="Implement the scheduler subsystem. Ensure it is dry-run safe."
    ))

    # 11. Vault Export
    results.append(check_subsystem(
        "vault_export",
        required_files=[
            "scripts/rig_tools/vault_export.py",
            "Docs/dev/rig/VAULT.md"
        ],
        why_it_matters="Human-readable memory in Obsidian is a core product requirement.",
        fix="Implement Markdown vault export in scripts/rig_tools/vault_export.py.",
        agent_instruction="Implement vault export. Document vault as derived, not source-of-truth."
    ))

    # 12. Textual Validator
    results.append(check_subsystem(
        "textual_validator",
        required_commands=[[sys.executable, "scripts/rig.py", "textual", "validate", "--agent"]],
        why_it_matters="Textual API misuse and browser CSS leads to TUI crashes.",
        fix="Harden textual validator to catch RichLog and align errors.",
        agent_instruction="Ensure the textual validator is installed and authoritative."
    ))

    # 13. Contract Audit
    results.append(check_subsystem(
        "contract_audit",
        required_commands=[[sys.executable, "scripts/rig.py", "audit", "contracts", "--format", "json"]],
        why_it_matters="Rot detection is required to ensure CLI surfaces match TUI assumptions.",
        fix="Implement contract auditor in scripts/rig_tools/contract_audit.py.",
        agent_instruction="Implement the contract audit subsystem to detect surface drift."
    ))

    # 14. Doctor
    results.append(check_subsystem(
        "doctor",
        required_commands=[[sys.executable, "scripts/rig.py", "doctor"]],
        why_it_matters="A high-level health check is required for operator confidence.",
        fix="Implement the rig doctor command.",
        agent_instruction="Implement the doctor command to check all OS subsystems."
    ))

    return results

def check_subsystem(
    subsystem_id: str,
    required_files: List[str] = [],
    required_commands: List[List[str]] = [],
    required_schema_families: List[str] = [],
    required_tests: List[str] = [],
    why_it_matters: str = "",
    acceptance: List[str] = [],
    fix: str = "",
    agent_instruction: str = ""
) -> Dict[str, Any]:
    """Performs validation checks for a single subsystem."""
    issues = []
    status = "pass"
    
    # Check files
    missing_files = [f for f in required_files if not (REPO_ROOT / f).exists()]
    if missing_files:
        status = "fail"
        issues.append({
            "code": f"missing_{subsystem_id}_files",
            "severity": "error",
            "subsystem": subsystem_id,
            "message": f"Required files missing: {', '.join(missing_files)}",
            "why_it_matters": why_it_matters,
            "required_files": missing_files,
            "acceptance": acceptance,
            "fix": fix,
            "agent_instruction": agent_instruction
        })
        
    # Check commands (smoke test)
    missing_commands = []
    for cmd in required_commands:
        res = run_command(cmd)
        if res["status"] != "success":
            status = "fail"
            cmd_str = " ".join(cmd)
            missing_commands.append(cmd_str)
            issues.append({
                "code": f"failed_{subsystem_id}_command",
                "severity": "error",
                "subsystem": subsystem_id,
                "message": f"Command failed or missing: {cmd_str}",
                "why_it_matters": why_it_matters,
                "required_commands": [cmd_str],
                "acceptance": acceptance,
                "fix": fix,
                "agent_instruction": agent_instruction
            })

    return {
        "subsystem_id": subsystem_id,
        "required": True,
        "status": status,
        "required_files": required_files,
        "required_commands": [" ".join(c) for c in required_commands],
        "required_schema_families": required_schema_families,
        "required_tests": required_tests,
        "issues": issues
    }

def generate_markdown(result: Dict[str, Any]) -> str:
    """Generates a human-readable Markdown summary of the sentinel result."""
    md = [f"# Rig OS Sentinel Summary - {result['status'].upper()}"]
    md.append(f"Generated at: {result['created_at']}")
    md.append(f"Status: {result['status']}")
    md.append(f"Exit Code: {result['exit_code']}\n")
    
    md.append("## Sentinel Governance")
    s = result["sentinel"]
    md.append(f"- Path: `{s['path']}`")
    md.append(f"- Hash Status: **{s['hash_status'].upper()}**")
    md.append(f"- Actual Hash: `{s['hash']}`")
    if s['hash_status'] == "mismatch":
        md.append(f"- Expected Hash: `{s['expected_hash']}`")
    md.append("")
    
    md.append("## Subsystems Status")
    for sub in result["subsystems"]:
        marker = "▬" if sub["status"] == "pass" else "▲"
        md.append(f"- {marker} **{sub['subsystem_id'].upper()}**: {sub['status'].upper()}")
    md.append("")
    
    if result["issues"]:
        md.append("## Open Issues")
        for issue in result["issues"]:
            md.append(f"### {issue['code']}")
            md.append(f"- **Severity**: {issue['severity']}")
            md.append(f"- **Message**: {issue['message']}")
            md.append(f"- **Fix**: {issue['fix']}")
            md.append(f"- **Agent Instruction**: {issue['agent_instruction']}")
            md.append("")

    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(description="Rig OS Sentinel Governance Validator")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--explain", action="store_true", help="Explain the role of the sentinel")
    parser.add_argument("--write-hash", action="store_true", help="Write the current hash to governance docs (manual only)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write receipts")
    args = parser.parse_args()

    if args.explain:
        print("Rig OS Sentinel: The non-negotiable validator for Rig's core architecture.")
        print("It ensures that all required subsystems exist and pass health checks.")
        sys.exit(0)

    if args.write_hash:
        actual = get_self_hash()
        if args.dry_run:
            print(f"DRY RUN: Would write hash {actual} to {HASH_PATH}")
        else:
            HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
            HASH_PATH.write_text(actual, encoding="utf-8")
            print(f"Updated governance hash: {actual}")
        sys.exit(0)

    start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hash_info = check_hash()
    subsystem_results = validate_subsystems()
    
    issues = []
    for s in subsystem_results:
        issues.extend(s["issues"])
    
    # Critical issue: Tamper check
    if hash_info["hash_status"] == "mismatch":
        issues.append({
            "code": "sentinel_tampered",
            "severity": "critical",
            "subsystem": "governance",
            "message": "Rig OS sentinel hash does not match governance hash.",
            "fix": "Restore Scripts/rig_os_sentinel.py or update hash with --write-hash.",
            "agent_instruction": "STOP. Sentinel modification detected. Revert changes to Scripts/rig_os_sentinel.py."
        })

    status = "pass"
    exit_code = 0
    
    if any(i["severity"] in ("critical", "error") for i in issues):
        status = "fail"
        exit_code = 1
        
    if hash_info["hash_status"] == "mismatch":
        exit_code = 2

    missing_required = [s for s in REQUIRED_SUBSYSTEMS if not any(r["subsystem_id"] == s and r["status"] == "pass" for r in subsystem_results)]

    result = {
        "schema_version": SCHEMA_VERSION,
        "created_at": start_time,
        "status": status,
        "exit_code": exit_code,
        "sentinel": hash_info,
        "subsystems": subsystem_results,
        "issues": issues,
        "missing_required_subsystems": missing_required,
        "warnings": [],
        "agent_repair_prompt": "Implement the missing subsystems listed in issues. Do not modify, delete, skip, or weaken Scripts/rig_os_sentinel.py. Re-run python Scripts/rig_os_sentinel.py --format json until status is pass." if status == "fail" else "",
        "authoritative": True
    }

    # Write receipts
    if not args.dry_run:
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        latest_json = BUILD_DIR / "latest.json"
        latest_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        
        run_id = time.strftime("%Y%m%d-%H%M%S")
        run_json = BUILD_DIR / f"{run_id}.json"
        run_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        
        latest_md = BUILD_DIR / "latest.md"
        latest_md.write_text(generate_markdown(result), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(generate_markdown(result))

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
