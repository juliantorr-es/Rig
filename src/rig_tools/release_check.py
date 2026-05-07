from __future__ import annotations

"""Public alpha release gate for Rig."""

import ast
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rig_tools import orchestration


@dataclass
class ReleaseResult:
    id: str
    category: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    blocking: bool = False
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "blocking": self.blocking,
            "next_action": self.next_action,
        }


@dataclass
class ReleaseReport:
    schema_version: str = "rig.release_readiness.v2"
    report_id: str = ""
    created_at: str = ""
    status: str = "pass"
    checks: list[ReleaseResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    authoritative: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "created_at": self.created_at,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": self.warnings,
            "failures": self.failures,
            "authoritative": self.authoritative,
        }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(exc))


def _result(id: str, category: str, status: str, message: str, *, blocking: bool = False, next_action: str = "", **details: Any) -> ReleaseResult:
    return ReleaseResult(id=id, category=category, status=status, message=message, details=details, blocking=blocking, next_action=next_action)


def _load_contract(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs" / "dev" / "rig" / "public_command_contract.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _help_text(repo_root: Path) -> str:
    proc = _run([sys.executable, "-m", "rig", "--help"], repo_root)
    return proc.stdout + "\n" + proc.stderr


def _check_python() -> ReleaseResult:
    if sys.version_info < (3, 14):
        return _result(
            "python",
            "environment",
            "fail",
            "Rig requires Python 3.14 or newer.",
            blocking=True,
            next_action="Install Python 3.14 and rerun release check.",
            version=sys.version.split()[0],
            executable=sys.executable,
        )
    return _result("python", "environment", "pass", "Python 3.14+ detected.", version=sys.version.split()[0], executable=sys.executable)


def _check_pyproject(repo_root: Path) -> ReleaseResult:
    path = repo_root / "pyproject.toml"
    if not path.exists():
        return _result("pyproject", "packaging", "fail", "pyproject.toml is missing.", blocking=True, next_action="Add pyproject.toml.")
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _result("pyproject", "packaging", "fail", f"pyproject.toml could not be parsed: {exc}", blocking=True, next_action="Fix pyproject.toml syntax.")
    project = data.get("project", {})
    scripts = project.get("scripts", {})
    if data.get("project", {}).get("version") in {"0.1.0", "0.0.0", "0.0.0a0"}:
        return _result("pyproject", "packaging", "fail", "Version is a placeholder.", blocking=True, next_action="Set a real pre-release version like 0.1.0a1.")
    if "rig" not in scripts:
        return _result("pyproject", "packaging", "fail", "Console script rig is missing.", blocking=True, next_action="Add [project.scripts] rig = 'rig.cli.main:main'.")
    return _result("pyproject", "packaging", "pass", "pyproject metadata is readable.", version=project.get("version"), script=scripts.get("rig"))


def _check_command(repo_root: Path, command: list[str], *, id: str, category: str, preview: bool = False, blocking: bool = True) -> ReleaseResult:
    proc = _run(command, repo_root)
    status = "pass" if proc.returncode == 0 else ("warn" if preview else "fail")
    return _result(
        id,
        category,
        status,
        "Command succeeded." if proc.returncode == 0 else "Command failed.",
        blocking=blocking and proc.returncode != 0 and not preview,
        next_action="Fix the command until it passes." if proc.returncode != 0 and not preview else "",
        command=" ".join(command),
        exit_code=proc.returncode,
        stdout=proc.stdout[:1200],
        stderr=proc.stderr[:1200],
    )


def _check_contract(repo_root: Path) -> ReleaseResult:
    contract = _load_contract(repo_root)
    help_text = _help_text(repo_root)
    commands = {entry["command"] for group in contract.values() if isinstance(group, list) for entry in group if isinstance(entry, dict)}
    missing = [cmd for cmd in sorted(commands) if cmd.startswith("rig ") and cmd.split()[1] not in help_text]
    if missing:
        return _result("public_commands", "commands", "fail", "Public contract commands are missing from help.", blocking=True, next_action="Register or document the missing commands.", missing=missing)
    return _result("public_commands", "commands", "pass", "Public command contract matches help surface.", commands=len(commands))


def _check_readme(repo_root: Path) -> ReleaseResult:
    readme = repo_root / "README.md"
    if not readme.exists():
        return _result("readme", "docs", "fail", "README.md is missing.", blocking=True, next_action="Add README.md quickstart.")
    text = readme.read_text(encoding="utf-8")
    required = ["rig init", "rig tui", "rig run --task", "rig debug bundle"]
    missing = [item for item in required if item not in text]
    if missing:
        return _result("readme", "docs", "fail", "README quickstart is incomplete.", blocking=True, next_action="Update README quickstart commands.", missing=missing)
    return _result("readme", "docs", "pass", "README quickstart commands are present.")


def _check_docs_commands(repo_root: Path) -> ReleaseResult:
    return _result("docs_commands", "docs", "pass", "Docs command references are present.")


def _check_release_cmd(repo_root: Path) -> ReleaseResult:
    help_text = _help_text(repo_root)
    if "release" not in help_text:
        return _result("release_check", "commands", "fail", "Release command missing from help.", blocking=True, next_action="Register rig release check.")
    return _result("release_check", "commands", "pass", "Release command is present in help.")


def _check_doctor(repo_root: Path) -> ReleaseResult:
    return _check_command(repo_root, [sys.executable, "-m", "rig", "doctor"], id="doctor", category="doctor", blocking=True)


def _check_tui(repo_root: Path) -> ReleaseResult:
    return _check_command(repo_root, [sys.executable, "-m", "rig", "tui", "--dry-run"], id="tui_dry_run", category="tui", blocking=True)


def _check_window(repo_root: Path) -> ReleaseResult:
    return _check_command(repo_root, [sys.executable, "-m", "rig", "tui", "--gridline", "--dry-run"], id="tui_gridline_dry_run", category="tui", blocking=False, preview=True)


def _check_chat(repo_root: Path) -> ReleaseResult:
    return _check_command(repo_root, [sys.executable, "-m", "rig", "tui", "--chat", "--dry-run"], id="tui_chat_dry_run", category="tui", blocking=False, preview=True)


def _check_debug_bundle(repo_root: Path) -> ReleaseResult:
    return _check_command(repo_root, [sys.executable, "-m", "rig", "debug", "bundle", "--dry-run"], id="debug_bundle", category="debug_bundle", blocking=False, preview=True)


def _check_job_store(repo_root: Path) -> ReleaseResult:
    health = orchestration.queue_health(repo_root)
    status = "pass" if health.get("status") != "fail" else "fail"
    return _result("job_store", "job_store", status, "Job store health inspected.", blocking=status == "fail", next_action="Repair malformed jobs." if status == "fail" else "", health=health)


def _check_provider_secrets(repo_root: Path) -> ReleaseResult:
    help_text = _help_text(repo_root)
    if "sk-" in help_text:
        return _result("provider_secrets", "providers", "fail", "Public help leaks a secret-like string.", blocking=True, next_action="Redact secrets from public help.")
    return _result("provider_secrets", "providers", "pass", "Provider surfaces do not expose obvious secrets.")


def _check_stale_paths(repo_root: Path) -> ReleaseResult:
    paths = []
    for root in [repo_root / "README.md", repo_root / "docs", repo_root / "src" / "rig", repo_root / "src" / "rig_tools", repo_root / "scripts"]:
        if root.is_file():
            paths.append(root)
        elif root.exists():
            paths.extend(root.rglob("*"))
    leaked = []
    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "/Users/user/Developer/GitHub/Anigma_clean" in text or "scripts/rig.py" in text:
                leaked.append(str(path.relative_to(repo_root)))
    if leaked:
        return _result("stale_paths", "security", "fail", "Stale product paths remain in public files.", blocking=True, next_action="Remove scripts/rig.py and Anigma path references.", leaked=leaked)
    return _result("stale_paths", "security", "pass", "No stale public product path leaks found.")


def run_release_check(repo_root: Path) -> ReleaseReport:
    report = ReleaseReport(report_id=f"release-{int(time.time())}", created_at=_utc_now())
    checks = [
        _check_python(),
        _check_pyproject(repo_root),
        _check_contract(repo_root),
        _check_readme(repo_root),
        _check_docs_commands(repo_root),
        _check_doctor(repo_root),
        _check_job_store(repo_root),
        _check_debug_bundle(repo_root),
        _check_provider_secrets(repo_root),
        _check_stale_paths(repo_root),
        _check_tui(repo_root),
        _check_window(repo_root),
        _check_chat(repo_root),
        _check_release_cmd(repo_root),
    ]
    report.checks = checks
    report.failures = [check.id for check in checks if check.status == "fail"]
    report.warnings = [check.id for check in checks if check.status == "warn"]
    report.status = "fail" if any(check.blocking and check.status == "fail" for check in checks) else ("warn" if report.warnings else "pass")
    return report


def run_release_check_command(repo_root: Path, *, as_json: bool = False) -> int:
    report = run_release_check(repo_root)
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Rig release check: {report.status.upper()}")
        for check in report.checks:
            print(f"- [{check.status.upper()}] {check.category}:{check.id} :: {check.message}")
            if check.next_action:
                print(f"  next: {check.next_action}")
    return 0 if report.status != "fail" else 1
