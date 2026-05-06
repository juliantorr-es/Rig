#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rig.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def last_nonempty_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def first_run_dir(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(".build/anigma-pipeline/runs/"):
            return line
    return ""


def first_zip_path(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.endswith(".zip") and line.startswith(".build/"):
            return line
    return ""


def main() -> int:
    help_result = run("--help")
    assert help_result.returncode == 0, help_result.stderr
    assert "atlas" in help_result.stdout
    assert "affected" in help_result.stdout
    assert "audit" in help_result.stdout
    assert "brief" in help_result.stdout
    assert "swift" in help_result.stdout
    assert "schema" in help_result.stdout
    assert "monitor" in help_result.stdout
    assert "notify" in help_result.stdout
    assert "agent" in help_result.stdout
    assert "db" in help_result.stdout
    assert "pipeline" in help_result.stdout
    assert "docs" in help_result.stdout
    assert "git" in help_result.stdout
    assert "doctor" in help_result.stdout

    atlas_result = run("atlas", "query", "--target", "AnigmaDaemonCore", "--limit", "3")
    assert atlas_result.returncode == 0, atlas_result.stderr
    assert "AnigmaDaemonCore" in atlas_result.stdout

    brief_result = run("brief", "list-templates")
    assert brief_result.returncode == 0, brief_result.stderr
    assert "cleanup_singleton_triage" in brief_result.stdout

    generate_result = run(
        "brief",
        "generate",
        "--task",
        "td-cleanup-005",
        "--template",
        "cleanup_singleton_triage",
        "--risk",
        "singleton_global_state",
        "--target",
        "AnigmaDaemonCore",
        "--limit",
        "3",
    )
    assert generate_result.returncode == 0, generate_result.stderr
    assert "Task ID: td-cleanup-005" in generate_result.stdout
    assert "{{" not in generate_result.stdout

    zero_copy_help = run("audit", "zero-copy", "--help")
    assert zero_copy_help.returncode == 0, zero_copy_help.stderr
    assert "not implemented yet" in zero_copy_help.stdout.lower() or "planned only" in zero_copy_help.stdout.lower()

    zero_copy_run = run("audit", "zero-copy")
    assert zero_copy_run.returncode == 2
    assert "not implemented yet" in zero_copy_run.stderr.lower()

    git_status = run("git", "status")
    assert git_status.returncode == 0, git_status.stderr
    assert "branch:" in git_status.stdout

    pipeline_run = run("pipeline", "run", "--profile", "local-fast", "--task", "rig-cli-bootstrap")
    assert pipeline_run.returncode == 0, pipeline_run.stderr
    run_dir = first_run_dir(pipeline_run.stdout)
    assert run_dir, pipeline_run.stdout
    assert (REPO_ROOT / run_dir / "manifest.json").exists()

    pipeline_bundle = run("pipeline", "bundle", "--task", "rig-cli-bootstrap", "--latest-run")
    assert pipeline_bundle.returncode == 0, pipeline_bundle.stderr
    bundle_path = first_zip_path(pipeline_bundle.stdout)
    assert bundle_path, pipeline_bundle.stdout
    assert (REPO_ROOT / bundle_path).exists()

    docs_index = run("docs", "index-rig-results")
    assert docs_index.returncode == 0, docs_index.stderr
    assert "Docs/indexes/rig-run-index.json" in docs_index.stdout or "Docs/indexes/rig-run-index.csv" in docs_index.stdout

    docs_table = run("docs", "table", "rig-run-index")
    assert docs_table.returncode == 0, docs_table.stderr
    assert "Docs/indexes/rig-run-index.csv" in docs_table.stdout

    docs_context = run("docs", "context-pack", "--task", "rig-cli-bootstrap", "--budget", "small")
    assert docs_context.returncode == 0, docs_context.stderr
    assert ".build/rig/context-packs/rig-cli-bootstrap-small.md" in docs_context.stdout

    schema_list = run("schema", "list")
    assert schema_list.returncode == 0, schema_list.stderr
    assert "rig.result.v1" in schema_list.stdout

    schema_validate = run("schema", "validate", "--artifact", ".build/rig/results/latest.json")
    assert schema_validate.returncode == 0, schema_validate.stderr
    assert '"status": "passed"' in schema_validate.stdout
    assert "validation_report" in schema_validate.stdout

    latest_run = run("pipeline", "latest-run", "--task", "rig-cli-bootstrap")
    assert latest_run.returncode == 0, latest_run.stderr
    assert latest_run.stdout.strip().startswith(".build/anigma-pipeline/runs/rig-cli-bootstrap/")

    doctor_result = run("doctor", "local-fast", "--task", "rig-cli-bootstrap")
    assert doctor_result.returncode == 0, doctor_result.stderr
    assert "rig-cli-bootstrap" in doctor_result.stdout or "rig-cli-bootstrap" in doctor_result.stderr

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
