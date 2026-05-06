from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.scheduler import Scheduler

def register(subparsers, helpers):
    """Registers the 'scheduler' command group."""
    parser = subparsers.add_parser("scheduler", help="Rig OS background job scheduler")
    sub = parser.add_subparsers(dest="scheduler_command")
    
    # Status
    status_parser = sub.add_parser("status", help="Show scheduler subsystem status")
    status_parser.set_defaults(handler=lambda args: run_status(helpers))
    
    # Jobs
    jobs_parser = sub.add_parser("jobs", help="List all defined jobs")
    jobs_parser.set_defaults(handler=lambda args: run_jobs(helpers))
    
    # Show
    show_parser = sub.add_parser("show", help="Show details for a specific job")
    show_parser.add_argument("--job", required=True, help="Job ID")
    show_parser.set_defaults(handler=lambda args: run_show(helpers, args.job))
    
    # Plist
    plist_parser = sub.add_parser("plist", help="Generate LaunchAgent plist for a job")
    plist_parser.add_argument("--job", required=True, help="Job ID")
    plist_parser.add_argument("--print", action="store_true", help="Print plist to stdout")
    plist_parser.set_defaults(handler=lambda args: run_plist(helpers, args.job, args.print))
    
    # Install
    install_parser = sub.add_parser("install", help="Install a job plist")
    install_parser.add_argument("--job", required=True, help="Job ID")
    install_parser.add_argument("--apply", action="store_true", help="Actually install (default is dry-run)")
    install_parser.add_argument("--dry-run", action="store_true", help="Simulate installation (default)")
    install_parser.set_defaults(handler=lambda args: run_install(helpers, args.job, not args.apply))
    
    # Uninstall
    uninstall_parser = sub.add_parser("uninstall", help="Uninstall a job plist")
    uninstall_parser.add_argument("--job", required=True, help="Job ID")
    uninstall_parser.add_argument("--apply", action="store_true", help="Actually uninstall (default is dry-run)")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Simulate uninstallation (default)")
    uninstall_parser.set_defaults(handler=lambda args: run_uninstall(helpers, args.job, not args.apply))
    
    # Run Now
    run_now_parser = sub.add_parser("run-now", help="Run a job immediately")
    run_now_parser.add_argument("--job", required=True, help="Job ID")
    run_now_parser.add_argument("--apply", action="store_true", help="Actually run (default is dry-run)")
    run_now_parser.add_argument("--dry-run", action="store_true", help="Simulate run (default)")
    run_now_parser.set_defaults(handler=lambda args: run_run_now(helpers, args.job, not args.apply))

def run_status(helpers):
    sched = Scheduler(helpers.repo_root)
    print("Rig Scheduler Status:")
    print(f"- Enabled: {sched.settings.get('scheduler_enabled', False)}")
    print(f"- Jobs Defined: {len(sched.get_all_jobs())}")
    print(f"- Local Jobs Dir: {sched.jobs_dir}")
    print(f"- Local Runs Dir: {sched.runs_dir}")
    return 0

def run_jobs(helpers):
    sched = Scheduler(helpers.repo_root)
    print("Defined Jobs:")
    for job in sched.get_all_jobs():
        status = "[ENABLED]" if job["enabled"] else "[DISABLED]"
        print(f"- {status} {job['job_id']} (Risk: {job['risk']})")
    return 0

def run_show(helpers, job_id: str):
    sched = Scheduler(helpers.repo_root)
    job = sched.get_job(job_id)
    if not job:
        print(f"Error: Job not found: {job_id}")
        return 1
    print(json.dumps(job, indent=2))
    return 0

def run_plist(helpers, job_id: str, print_out: bool):
    sched = Scheduler(helpers.repo_root)
    try:
        content = sched.generate_plist(job_id)
        if print_out:
            print(content)
        else:
            print(f"Plist generated successfully for {job_id}.")
        return 0
    except ValueError as e:
        print(f"Error generating plist: {e}")
        return 1

def run_install(helpers, job_id: str, dry_run: bool):
    sched = Scheduler(helpers.repo_root)
    res = sched.install(job_id, dry_run=dry_run)
    if res["status"] != "success":
        print(f"Failed to install: {res.get('warnings', [])}")
        return 1
        
    mode = "dry_run" if dry_run else "installed"
    print(f"Installed {job_id} (Mode: {mode})")
    return 0

def run_uninstall(helpers, job_id: str, dry_run: bool):
    sched = Scheduler(helpers.repo_root)
    res = sched.uninstall(job_id, dry_run=dry_run)
    if res["status"] != "success":
        print(f"Failed to uninstall: {res.get('warnings', [])}")
        return 1
        
    mode = "dry_run" if dry_run else "uninstalled"
    print(f"Uninstalled {job_id} (Mode: {mode})")
    return 0

def run_run_now(helpers, job_id: str, dry_run: bool):
    sched = Scheduler(helpers.repo_root)
    res = sched.run_now(job_id, dry_run=dry_run)
    if res["status"] == "blocked":
        print(f"Blocked: {res.get('warnings', [])}")
        return 1
        
    print(f"Run {job_id} (Mode: {res['mode']})")
    print(f"Status: {res['status']}")
    if res.get('warnings'):
        print(f"Warnings: {res['warnings']}")
        
    return 0 if res["status"] in {"passed", "dry_run"} else 1
