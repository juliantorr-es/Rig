from __future__ import annotations

import json
import importlib
import platform
import sys
from pathlib import Path

from rig_tools.doctor import run_doctor
from rig_tools import orchestration
from rig_tools import system_benchmark, llama_cpp_local, mlx_local, provider_registry
from rig_tools.provider_credentials import keychain_available
from rig.domain.integrity import (
    validate_repository_integrity,
    IntegritySummary,
)


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _queue(repo_root: Path) -> dict[str, object]:
    return orchestration.queue_health(repo_root)


def _integrity_workspace(repo_root: Path, *, json_output: bool = False) -> dict[str, object] | int:
    """Validate workspace integrity."""
    summary = validate_repository_integrity(repo_root)
    
    # Filter to workspace findings only
    workspace_findings = [
        f.to_dict() for f in summary.all_findings if f.subject_type == "workspace"
    ]
    
    result = {
        "check": "workspace_integrity",
        "total_findings": len(workspace_findings),
        "findings": workspace_findings,
        "findings_by_severity": {
            k: v for k, v in summary.findings_by_severity.items() if k in ("info", "warning", "error", "critical")
        },
        "integrity_score": summary.integrity_score,
        "overall_status": summary.overall_status,
    }
    
    if json_output:
        _emit(result)
        return 0
    
    # Human-readable output
    print(f"Workspace Integrity Check")
    print(f"  Status: {summary.overall_status}")
    print(f"  Score: {summary.integrity_score:.2f}")
    print(f"  Total workspace findings: {len(workspace_findings)}")
    
    if summary.findings_by_severity:
        print(f"  Severity breakdown:")
        for severity, count in sorted(summary.findings_by_severity.items()):
            if count > 0:
                print(f"    {severity}: {count}")
    
    if workspace_findings:
        print(f"\nFindings:")
        for finding in workspace_findings:
            print(f"  [{finding['severity'].upper()}] {finding['title']}: {finding['message']}")
    else:
        print("  All workspace integrity checks passed!")
    
    return 0


def _integrity_receipts(repo_root: Path, *, json_output: bool = False) -> dict[str, object] | int:
    """Validate receipt integrity."""
    summary = validate_repository_integrity(repo_root)
    
    # Filter to receipt findings only
    receipt_findings = [
        f.to_dict() for f in summary.all_findings if f.subject_type == "receipt"
    ]
    
    result = {
        "check": "receipt_integrity",
        "total_findings": len(receipt_findings),
        "findings": receipt_findings,
        "findings_by_severity": {
            k: v for k, v in summary.findings_by_severity.items() if k in ("info", "warning", "error", "critical")
        },
        "integrity_score": summary.integrity_score,
        "overall_status": summary.overall_status,
    }
    
    if json_output:
        _emit(result)
        return 0
    
    # Human-readable output
    print(f"Receipt Integrity Check")
    print(f"  Status: {summary.overall_status}")
    print(f"  Score: {summary.integrity_score:.2f}")
    print(f"  Total receipt findings: {len(receipt_findings)}")
    
    if summary.findings_by_severity:
        print(f"  Severity breakdown:")
        for severity, count in sorted(summary.findings_by_severity.items()):
            if count > 0:
                print(f"    {severity}: {count}")
    
    if receipt_findings:
        print(f"\nFindings:")
        for finding in receipt_findings:
            print(f"  [{finding['severity'].upper()}] {finding['title']}: {finding['message']}")
    else:
        print("  All receipt integrity checks passed!")
    
    return 0


def _integrity_audit(repo_root: Path, *, json_output: bool = False) -> dict[str, object] | int:
    """Validate audit event integrity."""
    summary = validate_repository_integrity(repo_root)
    
    # Filter to audit_event findings only
    audit_findings = [
        f.to_dict() for f in summary.all_findings if f.subject_type == "audit_event"
    ]
    
    result = {
        "check": "audit_integrity",
        "total_findings": len(audit_findings),
        "findings": audit_findings,
        "findings_by_severity": {
            k: v for k, v in summary.findings_by_severity.items() if k in ("info", "warning", "error", "critical")
        },
        "integrity_score": summary.integrity_score,
        "overall_status": summary.overall_status,
    }
    
    if json_output:
        _emit(result)
        return 0
    
    # Human-readable output
    print(f"Audit Event Integrity Check")
    print(f"  Status: {summary.overall_status}")
    print(f"  Score: {summary.integrity_score:.2f}")
    print(f"  Total audit findings: {len(audit_findings)}")
    
    if summary.findings_by_severity:
        print(f"  Severity breakdown:")
        for severity, count in sorted(summary.findings_by_severity.items()):
            if count > 0:
                print(f"    {severity}: {count}")
    
    if audit_findings:
        print(f"\nFindings:")
        for finding in audit_findings:
            print(f"  [{finding['severity'].upper()}] {finding['title']}: {finding['message']}")
    else:
        print("  All audit integrity checks passed!")
    
    return 0


def _integrity_projections(repo_root: Path, *, json_output: bool = False) -> dict[str, object] | int:
    """Validate projection integrity including contract validation."""
    from rig.domain.projection_builder import build_projection
    from rig.domain.integrity import validate_projection_integrity
    
    try:
        projection = build_projection(repo_root)
        
        # Convert projection to dict for validation
        projection_data = projection.to_dict() if hasattr(projection, 'to_dict') else {
            "revision": projection.revision,
            "widgets": {k: {"type": v.type, "data": v.data} for k, v in projection.widgets.items()},
        }
        
        # Validate projection using integrity checks (includes contract validation)
        result = validate_projection_integrity(projection_data, repo_root)
        
        # Build findings list
        findings_list = [f.to_dict() for f in result.findings]
        
        # Calculate severity breakdown
        findings_by_severity = {
            "info": result.info,
            "warning": result.warnings,
            "error": result.errors,
            "critical": result.critical,
        }
        
        # Calculate integrity score
        if result.passed:
            integrity_score = 1.0
            overall_status = "clean"
        elif result.critical > 0:
            integrity_score = 0.0
            overall_status = "critical"
        elif result.errors > 0:
            integrity_score = 0.5
            overall_status = "errors"
        elif result.warnings > 0:
            integrity_score = 0.75
            overall_status = "warnings"
        else:
            integrity_score = 1.0
            overall_status = "clean"
        
        # Check for integrity_status widget (Phase 4 feature)
        has_integrity_status = (
            hasattr(projection, 'integrity_status') 
            or 'integrity_status' in getattr(projection, '__dict__', {})
            or 'integrity.status' in (projection.widgets if hasattr(projection, 'widgets') else {})
        )
        if not has_integrity_status:
            findings_list.append({
                "severity": "info",
                "title": "Projection missing integrity_status",
                "message": "Projection does not yet expose integrity_status field (Phase 4 feature)",
                "subject_type": "projection",
                "subject_id": str(projection.revision),
                "violation_code": "PC-001",
            })
            if overall_status == "clean":
                overall_status = "info"
                integrity_score = 0.9
        
        output = {
            "check": "projection_integrity",
            "total_findings": len(findings_list),
            "findings": findings_list,
            "findings_by_severity": findings_by_severity,
            "integrity_score": integrity_score,
            "overall_status": overall_status,
            "contract_count": len(findings_list),  # Will be enhanced in Phase 4
        }
        
        # Add contract-specific info if available
        try:
            from rig.domain.projection_contracts import build_projection_contract_summary
            contract_summary = build_projection_contract_summary(projection_data, repo_root)
            output["projection_contract_summary"] = {
                "total_contracts": contract_summary.total_contracts,
                "contracts_checked": contract_summary.contracts_checked,
                "total_violations": contract_summary.total_violations,
                "violations_by_contract": contract_summary.violations_by_contract,
                "violations_by_severity": contract_summary.violations_by_severity,
                "violations_by_widget_type": contract_summary.violations_by_widget_type,
                "authority_binding_failures": contract_summary.authority_binding_failures,
                "receipt_backing_failures": contract_summary.receipt_backing_failures,
                "audit_backing_failures": contract_summary.audit_backing_failures,
                "placeholder_violations": contract_summary.placeholder_violations,
            }
        except Exception:
            pass
        
        if json_output:
            _emit(output)
            # Non-zero exit on critical
            if findings_by_severity.get("critical", 0) > 0:
                return 1
            return 0
        
        # Human-readable output
        print(f"Projection Integrity Check")
        print(f"  Status: {overall_status}")
        print(f"  Score: {integrity_score:.2f}")
        
        # Show contract summary if available
        try:
            from rig.domain.projection_contracts import build_projection_contract_summary
            contract_summary = build_projection_contract_summary(projection_data, repo_root)
            print(f"  Contracts checked: {contract_summary.contracts_checked}/{contract_summary.total_contracts}")
            print(f"  Projection violations: {contract_summary.total_violations}")
            if contract_summary.authority_binding_failures > 0:
                print(f"  Authority binding failures: {contract_summary.authority_binding_failures}")
            if contract_summary.receipt_backing_failures > 0:
                print(f"  Receipt backing failures: {contract_summary.receipt_backing_failures}")
            if contract_summary.audit_backing_failures > 0:
                print(f"  Audit backing failures: {contract_summary.audit_backing_failures}")
            if contract_summary.placeholder_violations > 0:
                print(f"  Placeholder violations: {contract_summary.placeholder_violations}")
        except Exception:
            pass
        
        if findings_list:
            print(f"\nFindings:")
            for finding in findings_list:
                severity = finding.get('severity', 'info').upper()
                title = finding.get('title', 'Unknown')
                message = finding.get('message', '')
                widget_type = finding.get('subject_id', '')
                print(f"  [{severity}] {title} ({widget_type}): {message}")
        else:
            print("  All projection integrity checks passed!")
        
        # Non-zero exit on critical
        if findings_by_severity.get("critical", 0) > 0:
            return 1
        
        return 0
    except Exception as e:
        if json_output:
            _emit({"check": "projection_integrity", "status": "error", "error": str(e)})
        else:
            print(f"Error validating projection: {e}")
        return 1


def _integrity_all(repo_root: Path, *, json_output: bool = False, strict: bool = False) -> dict[str, object] | int:
    """Validate all integrity aspects of the repository."""
    summary = validate_repository_integrity(repo_root)
    
    if json_output:
        _emit(summary.to_dict())
        # Non-zero exit on critical
        if summary.findings_by_severity.get("critical", 0) > 0:
            return 1
        return 0
    
    # Human-readable output
    print(f"Rig Integrity Check - All")
    print(f"=" * 40)
    print(f"Overall Status: {summary.overall_status}")
    print(f"Integrity Score: {summary.integrity_score:.2f}")
    print(f"Total Checks: {summary.total_checks}")
    print(f"Total Findings: {summary.total_findings}")
    
    if summary.findings_by_severity:
        print(f"\nSeverity Breakdown:")
        for severity, count in sorted(summary.findings_by_severity.items()):
            if count > 0:
                print(f"  {severity.capitalize()}: {count}")
    
    if summary.findings_by_subject_type:
        print(f"\nBy Subject Type:")
        for subject_type, count in sorted(summary.findings_by_subject_type.items()):
            if count > 0:
                print(f"  {subject_type}: {count}")
    
    if summary.all_findings:
        print(f"\nFindings:")
        for finding in summary.all_findings:
            severity = finding.severity.value.upper()
            print(f"  [{severity}] {finding.title} ({finding.subject_type}/{finding.subject_id})")
            print(f"       {finding.message}")
    else:
        print("\nAll integrity checks passed!")
    
    # Non-zero exit on critical or error if strict
    if summary.findings_by_severity.get("critical", 0) > 0:
        return 1
    if strict and summary.findings_by_severity.get("error", 0) > 0:
        return 1
    
    return 0


def _repair_queue(repo_root: Path, *, migrate_legacy_queue: bool = False) -> dict[str, object]:
    result = orchestration.queue_health(repo_root, repair=True)
    repaired = dict(result)
    repaired["repair"] = {
        "quarantined": result.get("quarantined", []),
        "migrated": None,
    }
    if migrate_legacy_queue:
        repaired["repair"]["migrated"] = orchestration.migrate_legacy_queue(repo_root)
    return repaired


def _deps(repo_root: Path) -> dict[str, object]:
    checks: dict[str, object] = {}
    for name, module_name in [("textual", "textual"), ("pywebview", "webview"), ("mlx", "mlx"), ("llama_cpp", "llama_cpp"), ("psutil", "psutil")]:
        try:
            module = importlib.import_module(module_name)
            checks[name] = {"available": True, "version": getattr(module, "__version__", None)}
        except Exception as exc:
            checks[name] = {"available": False, "error": str(exc)}
    checks["llama_cpp_capability"] = llama_cpp_local.detect_llama_cpp_environment()
    checks["mlx_capability"] = mlx_local.detect_mlx_environment()
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "python_ge_314": sys.version_info >= (3, 14),
        "platform": platform.platform(),
        "deps": checks,
        "benchmark_prerequisites": {
            "psutil": checks["psutil"]["available"],
            "mlx": checks["mlx"]["available"],
            "llama_cpp": checks["llama_cpp"]["available"],
        },
    }


def _safe_run_doctor(repo_root: Path, *, format_type: str) -> int:
    try:
        return run_doctor(repo_root, format_type=format_type)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc), "message": "Rig doctor encountered an internal error. Re-run with --debug for a traceback."}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def register(subparsers, helpers):
    parser = subparsers.add_parser("doctor", help="Integrated Rig OS health checks", description="Integrated runtime and subsystem health checks.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    sub = parser.add_subparsers(dest="doctor_command")
    sub.add_parser("queue", help="Inspect queue health").set_defaults(handler=lambda args: _emit(_queue(helpers.repo_root)))
    sub.add_parser("deps", help="Inspect dependency health").set_defaults(handler=lambda args: _emit(_deps(helpers.repo_root)))
    sub.add_parser("providers", help="Inspect provider health").set_defaults(handler=lambda args: _emit({"providers": provider_registry.list_providers(helpers.repo_root), "keychain_available": keychain_available()}))
    repair = sub.add_parser("repair", help="Repair queue health")
    repair.add_argument("--queue", action="store_true")
    repair.add_argument("--migrate-legacy-queue", action="store_true")
    repair.set_defaults(handler=lambda args: _emit(_repair_queue(helpers.repo_root, migrate_legacy_queue=args.migrate_legacy_queue)) if args.queue or args.migrate_legacy_queue else _emit(_queue(helpers.repo_root)))
    
    # Integrity validation subcommands (direct under doctor)
    # rig doctor workspace, rig doctor receipts, rig doctor audit, rig doctor projections, rig doctor all
    
    # workspace
    workspace_parser = sub.add_parser("workspace", help="Validate workspace integrity")
    workspace_parser.add_argument("--json", action="store_true", help="Output JSON")
    workspace_parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors (not just critical)")
    workspace_parser.set_defaults(handler=lambda args: _integrity_workspace(helpers.repo_root, json_output=args.json))
    
    # receipts
    receipts_parser = sub.add_parser("receipts", help="Validate receipt integrity")
    receipts_parser.add_argument("--json", action="store_true", help="Output JSON")
    receipts_parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors (not just critical)")
    receipts_parser.set_defaults(handler=lambda args: _integrity_receipts(helpers.repo_root, json_output=args.json))
    
    # audit
    audit_parser = sub.add_parser("audit", help="Validate audit event integrity")
    audit_parser.add_argument("--json", action="store_true", help="Output JSON")
    audit_parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors (not just critical)")
    audit_parser.set_defaults(handler=lambda args: _integrity_audit(helpers.repo_root, json_output=args.json))
    
    # projections
    projections_parser = sub.add_parser("projections", help="Validate projection integrity")
    projections_parser.add_argument("--json", action="store_true", help="Output JSON")
    projections_parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors (not just critical)")
    projections_parser.set_defaults(handler=lambda args: _integrity_projections(helpers.repo_root, json_output=args.json))
    
    # all
    all_parser = sub.add_parser("all", help="Validate all integrity aspects")
    all_parser.add_argument("--json", action="store_true", help="Output JSON")
    all_parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors (not just critical)")
    all_parser.set_defaults(handler=lambda args: _integrity_all(helpers.repo_root, json_output=args.json, strict=args.strict))
    
    parser.set_defaults(handler=lambda args: _safe_run_doctor(helpers.repo_root, format_type=args.format))
