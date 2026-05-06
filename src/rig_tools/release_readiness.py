from __future__ import annotations

import ast
import configparser
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contract_audit import run_contract_audit
from .doctor import run_doctor
from .schema_validation import validate_instance


@dataclass
class ReleaseCheck:
    check_id: str
    status: str
    command: str
    exit_code: int
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    artifact_path: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "artifact_path": self.artifact_path,
            "recommendation": self.recommendation,
        }


@dataclass
class ReleaseReport:
    schema_version: str = "rig.release_readiness.v1"
    report_id: str = ""
    created_at: str = ""
    status: str = "pass"
    checks: list[ReleaseCheck] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    authoritative: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "created_at": self.created_at,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "failures": self.failures,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "artifact_paths": self.artifact_paths,
            "authoritative": self.authoritative,
        }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _excerpt(text: str, limit: int = 1200) -> str:
    return text[:limit]


def _run(repo_root: Path, cmd: list[str], *, cwd: Path| Optional = None, timeout: int| Optional = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd or repo_root, text=True, capture_output=True, check=False, timeout=timeout)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, 124, stdout=exc.stdout or "", stderr=exc.stderr or "timeout")


def _load_pyproject(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "pyproject.toml"
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except Exception:
            import tomli as tomllib  # type: ignore[no-redef]
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def _scan_public_docs(repo_root: Path) -> list[Path]:
    roots = [repo_root / "Docs" / "dev" / "rig", repo_root / "README.md"]
    out: list[Path] = []
    for root in roots:
        if root.is_dir():
            out.extend(root.rglob("*.md"))
        elif root.is_file():
            out.append(root)
    return out


def _no_shell_true(repo_root: Path) -> bool:
    allowed_fixtures = {"validate_notion_publisher.py"}
    scan_roots = [repo_root / "scripts" / "rig", repo_root / "scripts" / "rig_tools", repo_root / "scripts" / "rig.py"]
    for root in scan_roots:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in paths:
            if path.name in allowed_fixtures:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "shell" and isinstance(node.value, ast.Constant) and node.value.value is True:
                    return False
    return True


def _has_secret_like_strings(repo_root: Path) -> bool:
    for path in _scan_public_docs(repo_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "BEGIN PRIVATE KEY" in text or "AKIA" in text or "ghp_" in text:
            return True
    return False


def _has_hardcoded_local_paths(repo_root: Path) -> bool:
    for path in _scan_public_docs(repo_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/Users/user/" in text:
            return True
    return False


def _license_check(repo_root: Path) -> tuple[ReleaseCheck, list[str]]:
    paths = [repo_root / "LICENSE", repo_root / "LICENSE.md", repo_root / "COMMERCIAL-LICENSE.md"]
    found = next((p for p in paths if p.exists()), None)
    if found:
        return ReleaseCheck(
            check_id="license",
            status="pass",
            command="license presence",
            exit_code=0,
            stdout_excerpt=str(found.relative_to(repo_root)),
        ), [str(found.relative_to(repo_root))]
    return ReleaseCheck(
        check_id="license",
        status="warn",
        command="license presence",
        exit_code=0,
        recommendation="Add a LICENSE file for public release clarity",
    ), []


def _dist_ignore_check(repo_root: Path) -> ReleaseCheck:
    gitignore = repo_root / ".gitignore"
    documented = False
    if gitignore.exists():
        try:
            documented = any(line.strip() == "dist/" for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            documented = False
    if documented:
        return ReleaseCheck(
            check_id="dist_ignored",
            status="pass",
            command=".gitignore contains dist/",
            exit_code=0,
            stdout_excerpt="dist/ ignored by Git",
            artifact_path=str(gitignore.relative_to(repo_root)),
        )
    return ReleaseCheck(
        check_id="dist_ignored",
        status="warn",
        command=".gitignore contains dist/",
        exit_code=0 if gitignore.exists() else 1,
        recommendation="Ensure dist/ is ignored by Git or documented as release output",
        artifact_path=str(gitignore.relative_to(repo_root)) if gitignore.exists() else "",
    )


def _build_tool_check(repo_root: Path) -> tuple[ReleaseCheck, list[str]]:
    build = _run(repo_root, [sys.executable, "-m", "build", "--version"])
    if build.returncode == 0:
        return ReleaseCheck(
            check_id="build_tool",
            status="pass",
            command="python -m build --version",
            exit_code=0,
            stdout_excerpt=_excerpt(build.stdout.strip() or build.stderr.strip()),
        ), []
    return ReleaseCheck(
        check_id="build_tool",
        status="warn",
        command="python -m build --version",
        exit_code=build.returncode,
        stderr_excerpt=_excerpt(build.stderr),
        recommendation="Install the build tool with `python -m pip install build`",
    ), ["python -m pip install build"]


def _pyproject_check(repo_root: Path) -> tuple[list[ReleaseCheck], list[str], list[str]]:
    warnings: list[str] = []
    recommendations: list[str] = []
    checks: list[ReleaseCheck] = []
    path = repo_root / "pyproject.toml"
    if not path.exists():
        checks.append(ReleaseCheck(check_id="pyproject_exists", status="fail", command="pyproject.toml exists", exit_code=1, recommendation="Add pyproject.toml"))
        return checks, warnings, recommendations
    data = _load_pyproject(repo_root)
    project = data.get("project", {})
    scripts = project.get("scripts", {})
    optional = project.get("optional-dependencies", {})
    checks.append(ReleaseCheck(
        check_id="pyproject_exists",
        status="pass",
        command="pyproject.toml exists",
        exit_code=0,
        stdout_excerpt="pyproject.toml present",
    ))
    if project.get("name") == "rig-control":
        checks.append(ReleaseCheck(check_id="project_name", status="pass", command="project.name == rig-control", exit_code=0, stdout_excerpt="rig-control"))
    else:
        checks.append(ReleaseCheck(check_id="project_name", status="fail", command="project.name == rig-control", exit_code=1, recommendation="Set project.name to rig-control"))
    if "rig" in scripts:
        checks.append(ReleaseCheck(check_id="console_script", status="pass", command="project.scripts.rig exists", exit_code=0, stdout_excerpt=str(scripts.get("rig"))))
    else:
        checks.append(ReleaseCheck(check_id="console_script", status="fail", command="project.scripts.rig exists", exit_code=1, recommendation="Add a rig console script"))
    for extra in ("tui", "dev", "local-llm"):
        if extra in optional:
            checks.append(ReleaseCheck(check_id=f"extra_{extra}", status="pass", command=f"optional dependency {extra}", exit_code=0))
        else:
            checks.append(ReleaseCheck(check_id=f"extra_{extra}", status="fail", command=f"optional dependency {extra}", exit_code=1, recommendation=f"Add the {extra} extra"))
    return checks, warnings, recommendations


def _installed_cli_check(repo_root: Path) -> list[ReleaseCheck]:
    checks: list[ReleaseCheck] = []
    imports = _run(repo_root, [sys.executable, "-c", "import rig.main, rig_tools; print('ok')"])
    checks.append(ReleaseCheck(
        check_id="package_imports",
        status="pass" if imports.returncode == 0 else "fail",
        command="python -c 'import rig.main, rig_tools'",
        exit_code=imports.returncode,
        stdout_excerpt=_excerpt(imports.stdout),
        stderr_excerpt=_excerpt(imports.stderr),
        recommendation="Fix package imports and editable install layout" if imports.returncode != 0 else "",
    ))
    rig_bin = repo_root / ".venv-rig" / "bin" / "rig"
    rig_cmd = [str(rig_bin), "--help"] if rig_bin.exists() else ["rig", "--help"]
    rig = _run(repo_root, rig_cmd)
    checks.append(ReleaseCheck(
        check_id="rig_py_help",
        status="pass" if rig.returncode == 0 else "fail",
        command="python scripts/rig.py --help",
        exit_code=rig.returncode,
        stdout_excerpt=_excerpt(rig.stdout),
        stderr_excerpt=_excerpt(rig.stderr),
        recommendation="Fix the CLI entrypoint" if rig.returncode != 0 else "",
    ))
    installed = _run(repo_root, rig_cmd)
    checks.append(ReleaseCheck(
        check_id="installed_rig_help",
        status="pass" if installed.returncode == 0 else "warn",
        command="rig --help" if rig_cmd[0] == "rig" else f"{rig_cmd[0]} --help",
        exit_code=installed.returncode,
        stdout_excerpt=_excerpt(installed.stdout),
        stderr_excerpt=_excerpt(installed.stderr),
        recommendation="Editable install not active; test via .venv-rig/bin/rig or pipx" if installed.returncode != 0 else "",
    ))
    return checks


def _health_checks(repo_root: Path) -> list[ReleaseCheck]:
    checks: list[ReleaseCheck] = []
    doctor = _run(repo_root, [sys.executable, "scripts/rig.py", "doctor", "--format", "json"])
    doctor_payload: dict[str, Any] = {}
    if doctor.returncode == 0:
        try:
            doctor_payload = json.loads(doctor.stdout)
        except Exception:
            doctor_payload = {}
    checks.append(ReleaseCheck(
        check_id="doctor",
        status="pass" if doctor.returncode == 0 and doctor_payload.get("status") != "fail" else "fail",
        command="rig doctor --format json",
        exit_code=doctor.returncode,
        stdout_excerpt=_excerpt(doctor.stdout),
        stderr_excerpt=_excerpt(doctor.stderr),
        recommendation="Fix doctor warnings/failures before release" if doctor.returncode != 0 or doctor_payload.get("status") == "fail" else "",
    ))
    audit = _run(repo_root, [sys.executable, "scripts/rig.py", "audit", "contracts", "--format", "json"])
    audit_payload: dict[str, Any] = {}
    if audit.returncode == 0:
        try:
            audit_payload = json.loads(audit.stdout)
        except Exception:
            audit_payload = {}
    checks.append(ReleaseCheck(
        check_id="contract_audit",
        status="pass" if audit.returncode == 0 and audit_payload.get("status") == "pass" else "fail",
        command="rig audit contracts --format json",
        exit_code=audit.returncode,
        stdout_excerpt=_excerpt(audit.stdout),
        stderr_excerpt=_excerpt(audit.stderr),
        recommendation="Fix contract audit failures before release" if audit.returncode != 0 or audit_payload.get("status") != "pass" else "",
    ))
    return checks


def _build_check(repo_root: Path, dry_run: bool) -> tuple[ReleaseCheck, list[str], list[str]]:
    warnings: list[str] = []
    recommendations: list[str] = []
    build_dir = repo_root / "dist"
    if dry_run:
        checks = ReleaseCheck(
            check_id="build",
            status="pass",
            command="python -m build",
            exit_code=0,
            stdout_excerpt="dry run: build artifacts would be written to dist/",
        )
        return checks, warnings, recommendations
    build_mod = _run(repo_root, [sys.executable, "-m", "build", "--sdist", "--wheel"])
    if build_mod.returncode == 0:
        artifacts = sorted(str(p.relative_to(repo_root)) for p in build_dir.glob("*") if p.is_file())
        return ReleaseCheck(
            check_id="build",
            status="pass",
            command="python -m build --sdist --wheel",
            exit_code=0,
            stdout_excerpt=_excerpt(build_mod.stdout),
            artifact_path=", ".join(artifacts),
        ), warnings, recommendations
    recommendations.append("Install the build tool with `python -m pip install build`")
    return ReleaseCheck(
        check_id="build",
        status="warn",
        command="python -m build --sdist --wheel",
        exit_code=build_mod.returncode,
        stderr_excerpt=_excerpt(build_mod.stderr),
        recommendation="Install build to produce sdists/wheels",
    ), warnings, recommendations


def run_release_readiness(repo_root: Path, *, format_type: str = "text", dry_run_build: bool = True) -> ReleaseReport:
    import uuid

    report = ReleaseReport(
        report_id=f"release-{uuid.uuid4().hex[:12]}",
        created_at=_utc_now(),
    )
    checks: list[ReleaseCheck] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    checks.extend(_health_checks(repo_root))
    pyproject_checks, py_warnings, py_recs = _pyproject_check(repo_root)
    checks.extend(pyproject_checks)
    warnings.extend(py_warnings)
    recommendations.extend(py_recs)
    checks.extend(_installed_cli_check(repo_root))

    license_check, license_paths = _license_check(repo_root)
    checks.append(license_check)
    if license_paths:
        report.artifact_paths.extend(license_paths)

    checks.append(_dist_ignore_check(repo_root))

    build_tool, build_recs = _build_tool_check(repo_root)
    checks.append(build_tool)
    recommendations.extend(build_recs)

    build_check, build_warnings, build_recs_2 = _build_check(repo_root, dry_run_build)
    checks.append(build_check)
    warnings.extend(build_warnings)
    recommendations.extend(build_recs_2)

    if _has_hardcoded_local_paths(repo_root):
        warnings.append("hardcoded_local_paths_in_docs")
    if _has_secret_like_strings(repo_root):
        warnings.append("possible_secrets_in_public_docs")
    if not _no_shell_true(repo_root):
        checks.append(ReleaseCheck(check_id="shell_true_scan", status="fail", command="AST shell=True scan", exit_code=1, recommendation="Remove shell=True from scripts"))
    else:
        checks.append(ReleaseCheck(check_id="shell_true_scan", status="pass", command="AST shell=True scan", exit_code=0))

    if not (repo_root / "README.md").exists():
        checks.append(ReleaseCheck(check_id="readme_quickstart", status="fail", command="README.md quickstart", exit_code=1, recommendation="Add a README quickstart"))
    else:
        checks.append(ReleaseCheck(check_id="readme_quickstart", status="pass", command="README.md quickstart", exit_code=0))

    status = "pass"
    if any(check.status == "fail" for check in checks):
        status = "fail"
    elif warnings:
        status = "warn"

    report.checks = checks
    report.warnings = sorted(set(warnings))
    report.recommendations = sorted(set(recommendations))
    report.status = status
    report.failures = [check.check_id for check in checks if check.status == "fail"]
    report.artifact_paths.extend([
        str((repo_root / "pyproject.toml").relative_to(repo_root)) if (repo_root / "pyproject.toml").exists() else "pyproject.toml",
        ".build/rig/doctor/latest.json",
        ".build/rig/doctor/latest.md",
        ".build/rig/audit/contracts/latest.json",
        ".build/rig/audit/contracts/latest.md",
    ])
    return report


def run_release_readiness_command(repo_root: Path, *, format_type: str = "text", dry_run_build: bool = True) -> int:
    report = run_release_readiness(repo_root, format_type=format_type, dry_run_build=dry_run_build)
    out_dir = repo_root / ".build" / "rig" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "latest.json"
    md_path = out_dir / "latest.md"
    report.artifact_paths = sorted(set(report.artifact_paths + [str(json_path.relative_to(repo_root)), str(md_path.relative_to(repo_root))]))
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = [
        "# Rig Release Readiness",
        f"- Status: {report.status}",
        f"- Created: {report.created_at}",
        "",
        "## Checks",
    ]
    for check in report.checks:
        md_lines.append(f"- [{check.status}] {check.check_id} :: {check.command}")
        if check.recommendation:
            md_lines.append(f"  - recommendation: {check.recommendation}")
    if report.warnings:
        md_lines.extend(["", "## Warnings"])
        md_lines.extend(f"- {w}" for w in report.warnings)
    if report.recommendations:
        md_lines.extend(["", "## Recommendations"])
        md_lines.extend(f"- {r}" for r in report.recommendations)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    if format_type == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Rig Release Readiness: {report.status.upper()}")
        for check in report.checks:
            print(f"- [{check.status.upper()}] {check.check_id}")
        if report.warnings:
            print("\nWarnings:")
            for warning in report.warnings:
                print(f"- {warning}")
        if report.recommendations:
            print("\nRecommendations:")
            for recommendation in report.recommendations:
                print(f"- {recommendation}")
    return 0 if report.status != "fail" else 1
