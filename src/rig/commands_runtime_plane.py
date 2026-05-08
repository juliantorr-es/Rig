"""Runtime Execution Plane CLI Commands for Rig.

This module provides CLI commands for the new Runtime & Agent Execution Plane
(introduced in Phase 1-9). These commands provide:
- Provider listing and inspection
- Capability registry operations
- Benchmark display
- Doctor/health checks
- Dry-run execution

Core doctrine:
- Deterministic output
- JSON mode support
- Replay-safe
- No hidden execution
- Dry-run support
- No direct workspace mutation

file: src/rig/commands_runtime_plane.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from rig.domain.runtime import (
    RuntimeProvider,
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
    RuntimeCapabilityKind,
    RuntimeCapabilityScope,
    RuntimeExecutionReceipt,
    RuntimeBenchmark,
    RuntimeBenchmarkKind,
    RuntimeConstraint,
    RuntimeConstraintKind,
    RuntimeState,
    RuntimeStateKind,
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_NO_PROVIDER,
)
from rig.domain.runtime_registry import (
    CapabilityRegistry,
    RuntimeRegistry,
    get_capability_registry,
    get_runtime_registry,
    reset_default_registries,
)


def register(subparsers, helpers):
    """Register runtime plane subcommands."""
    parser = subparsers.add_parser("runtime-plane", help="Runtime Execution Plane management")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    
    # List providers
    list_parsers = sub.add_parser("list", help="List runtime providers")
    list_parsers.add_argument("--json", action="store_true", help="Output in JSON format")
    list_parsers.add_argument("--detailed", action="store_true", help="Show detailed provider information")
    list_parsers.set_defaults(handler=lambda args: _list(helpers, args.json, args.detailed))
    
    # Capabilities commands
    caps_parser = sub.add_parser("capabilities", help="Manage runtime capabilities")
    caps_sub = caps_parser.add_subparsers(dest="caps_subcommand", required=True)
    caps_list = caps_sub.add_parser("list", help="List all capabilities")
    caps_list.add_argument("--json", action="store_true", help="Output in JSON format")
    caps_list.add_argument("--kind", help="Filter by capability kind")
    caps_list.add_argument("--workspace", help="Filter by workspace ID")
    caps_list.set_defaults(handler=lambda args: _capabilities_list(helpers, args.json, args.kind, args.workspace))
    
    caps_check = caps_sub.add_parser("check", help="Check provider capabilities")
    caps_check.add_argument("provider_id", help="Provider ID to check")
    caps_check.add_argument("capability_id", nargs="?", help="Specific capability to check")
    caps_check.add_argument("--json", action="store_true", help="Output in JSON format")
    caps_check.set_defaults(handler=lambda args: _capabilities_check(helpers, args.provider_id, args.capability_id, args.json))
    
    # Constraints commands
    constraints_parser = sub.add_parser("constraints", help="Manage runtime constraints")
    constraints_sub = constraints_parser.add_subparsers(dest="constraints_subcommand", required=True)
    constraints_list = constraints_sub.add_parser("list", help="List all constraints")
    constraints_list.add_argument("--json", action="store_true", help="Output in JSON format")
    constraints_list.add_argument("--workspace", help="Filter by workspace ID")
    constraints_list.set_defaults(handler=lambda args: _constraints_list(helpers, args.json, args.workspace))
    
    # Validate command
    validate_parser = sub.add_parser("validate", help="Validate runtime configuration")
    validate_parser.add_argument("provider_id", nargs="?", help="Specific provider to validate")
    validate_parser.add_argument("--workspace", help="Workspace context for validation")
    validate_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    validate_parser.set_defaults(handler=lambda args: _validate(helpers, args.provider_id, args.workspace, args.json))
    
    # Benchmark commands
    bench_parser = sub.add_parser("benchmark", help="Runtime benchmarking")
    bench_sub = bench_parser.add_subparsers(dest="bench_subcommand", required=True)
    bench_list = bench_sub.add_parser("list", help="List runtime benchmarks")
    bench_list.add_argument("--json", action="store_true", help="Output in JSON format")
    bench_list.add_argument("--provider", help="Filter by provider ID")
    bench_list.add_argument("--kind", help="Filter by benchmark kind")
    bench_list.set_defaults(handler=lambda args: _benchmark_list(helpers, args.json, args.provider, args.kind))
    
    # Doctor/health check
    doctor_parser = sub.add_parser("doctor", help="Runtime plane health check")
    doctor_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    doctor_parser.add_argument("--all", action="store_true", help="Run all checks")
    doctor_parser.set_defaults(handler=lambda args: _doctor(helpers, args.json, args.all))
    
    # Dry-run execution
    dryrun_parser = sub.add_parser("dry-run", help="Dry-run a runtime execution")
    dryrun_parser.add_argument("provider_id", help="Provider ID to dry-run")
    dryrun_parser.add_argument("model_id", nargs="?", default="test-model", help="Model ID")
    dryrun_parser.add_argument("--task", help="Task to dry-run")
    dryrun_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    dryrun_parser.set_defaults(handler=lambda args: _dry_run(helpers, args.provider_id, args.model_id, args.task, args.json))
    
    # State command
    state_parser = sub.add_parser("state", help="Show runtime state")
    state_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    state_parser.set_defaults(handler=lambda args: _state(helpers, args.json))


def _list(helpers, use_json: bool, detailed: bool) -> int:
    """List runtime providers."""
    registry = get_capability_registry()
    providers = registry.providers
    
    if use_json:
        provider_dicts = {k: v.to_dict() for k, v in providers.items()}
        if detailed:
            provider_dicts["registry_summary"] = {
                "total_providers": len(providers),
                "total_capabilities": len(registry.capabilities),
                "total_constraints": len(registry.constraints),
            }
        print(json.dumps(provider_dicts, indent=2, sort_keys=True))
        return 0
    
    print("Runtime Providers:")
    print("=" * 40)
    for provider_id, provider in sorted(providers.items()):
        status = f"[{provider.status.value}]"
        trust = f"(tier: {provider.trust_tier.value})"
        if detailed:
            print(f"  {provider_id}")
            print(f"    Status: {status}")
            print(f"    Kind: {provider.kind.value}")
            print(f"    Trust Tier: {provider.trust_tier.value}")
            print(f"    Executable: {provider.executable}")
            print(f"    Offline Capable: {provider.offline_capable}")
            print(f"    Supported Tasks: {provider.supported_tasks}")
            print()
        else:
            print(f"  {provider_id}: {provider.kind.value} {status} {trust}")
    
    return 0


def _capabilities_list(helpers, use_json: bool, kind_filter: Optional[str], workspace_filter: Optional[str]) -> int:
    """List runtime capabilities."""
    registry = get_capability_registry()
    
    # Filter capabilities
    capabilities = []
    for cap_id, cap in registry.capabilities.items():
        if kind_filter and cap.kind.value != kind_filter:
            continue
        if workspace_filter and cap.workspace_id != workspace_filter:
            continue
        capabilities.append(cap)
    
    if use_json:
        result = {
            "capabilities": [c.to_dict() for c in capabilities],
            "total": len(capabilities),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    
    print("Runtime Capabilities:")
    print("=" * 40)
    for cap in sorted(capabilities, key=lambda c: c.capability_id):
        scope = f"[{cap.scope.value}]"
        if cap.workspace_id:
            scope = f"[{cap.scope.value}:{cap.workspace_id}]"
        print(f"  {cap.capability_id}: {cap.kind.value} {scope}")
        print(f"    Description: {cap.description}")
        if cap.requires_validation:
            print(f"    Requires Validation: Yes")
        if cap.requires_review:
            print(f"    Requires Review: Yes")
        print()
    
    return 0


def _capabilities_check(helpers, provider_id: str, capability_id: Optional[str], use_json: bool) -> int:
    """Check provider capabilities."""
    registry = get_capability_registry()
    provider = registry.get_provider(provider_id)
    
    if provider is None:
        if use_json:
            print(json.dumps({"error": f"Provider not found: {provider_id}", "success": False}, indent=2))
        else:
            print(f"Error: Provider not found: {provider_id}")
        return 1
    
    results = {}
    all_caps = registry.get_provider_capabilities(provider_id)
    
    if capability_id:
        # Check specific capability
        validated, errors = registry.validate_capability(provider_id, capability_id)
        if use_json:
            print(json.dumps({
                "provider_id": provider_id,
                "capability_id": capability_id,
                "validated": validated,
                "errors": errors,
            }, indent=2))
        else:
            print(f"Capability: {capability_id}")
            print(f"  Provider: {provider_id}")
            print(f"  Validated: {validated}")
            if errors:
                print(f"  Errors: {errors}")
        return 0 if validated else 1
    else:
        # List all capabilities for provider
        cap_details = []
        for cap_id in all_caps:
            cap = registry.get_capability(cap_id)
            if cap:
                validated, errors = registry.validate_capability(provider_id, cap_id)
                cap_details.append({
                    "capability_id": cap_id,
                    "kind": cap.kind.value,
                    "validated": validated,
                    "errors": errors,
                })
        
        if use_json:
            print(json.dumps({
                "provider_id": provider_id,
                "total_capabilities": len(cap_details),
                "capabilities": cap_details,
            }, indent=2))
        else:
            print(f"Provider: {provider_id}")
            print(f"  Total Capabilities: {len(cap_details)}")
            for detail in cap_details:
                status = "OK" if detail["validated"] else "FAILED"
                print(f"  - {detail['capability_id']}: {detail['kind']} [{status}]")
        
        return 0


def _constraints_list(helpers, use_json: bool, workspace_filter: Optional[str]) -> int:
    """List runtime constraints."""
    registry = get_capability_registry()
    
    # Filter constraints
    constraints = []
    for constraint_id, constraint in registry.constraints.items():
        if workspace_filter and constraint.workspace_id != workspace_filter:
            continue
        constraints.append(constraint)
    
    if use_json:
        result = {
            "constraints": [c.to_dict() for c in constraints],
            "total": len(constraints),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    
    print("Runtime Constraints:")
    print("=" * 40)
    for constraint in sorted(constraints, key=lambda c: c.constraint_id):
        scope = f"[{constraint.scope.value}]"
        if constraint.workspace_id:
            scope = f"[{constraint.scope.value}:{constraint.workspace_id}]"
        print(f"  {constraint.constraint_id}: {constraint.kind.value} {scope}")
        print(f"    Mode: {constraint.mode.value}")
        print(f"    Description: {constraint.description}")
        applies_to = [k.value for k in constraint.applies_to]
        if applies_to:
            print(f"    Applies to: {', '.join(applies_to)}")
        print()
    
    return 0


def _validate(helpers, provider_id: Optional[str], workspace_id: Optional[str], use_json: bool) -> int:
    """Validate runtime configuration."""
    registry = get_capability_registry()
    providers = list(registry.providers.keys())
    
    if provider_id:
        providers = [provider_id]
    
    results = []
    for pid in providers:
        provider = registry.get_provider(pid)
        if provider is None:
            results.append({
                "provider_id": pid,
                "status": "error",
                "message": f"Provider not found: {pid}",
            })
            continue
        
        # Validate all capabilities for this provider
        all_caps = registry.get_provider_capabilities(pid)
        valid_count = 0
        invalid_count = 0
        errors = []
        
        for cap_id in all_caps:
            validated, cap_errors = registry.validate_capability(pid, cap_id, workspace_id)
            if validated:
                valid_count += 1
            else:
                invalid_count += 1
                errors.append({
                    "capability_id": cap_id,
                    "errors": cap_errors,
                })
        
        results.append({
            "provider_id": pid,
            "total_capabilities": len(all_caps),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "errors": errors,
        })
    
    if use_json:
        print(json.dumps({
            "validation": results,
            "summary": {
                "total_providers": len(results),
                "total_validated": sum(r["valid_count"] for r in results),
                "total_errors": sum(r["invalid_count"] for r in results),
            },
        }, indent=2))
        return 0 if all(r["invalid_count"] == 0 for r in results) else 1
    
    print("Runtime Validation Report:")
    print("=" * 40)
    for result in results:
        pid = result["provider_id"]
        print(f"Provider: {pid}")
        print(f"  Valid: {result['valid_count']}/{result['total_capabilities']}")
        if result["invalid_count"] > 0:
            print(f"  Errors:")
            for error in result["errors"]:
                print(f"    - {error['capability_id']}: {error['errors']}")
        print()
    
    return 0 if all(r["invalid_count"] == 0 for r in results) else 1


def _benchmark_list(helpers, use_json: bool, provider_filter: Optional[str], kind_filter: Optional[str]) -> int:
    """List runtime benchmarks."""
    runtime_registry = get_runtime_registry(helpers.repo_root)
    benchmarks = runtime_registry.list_benchmarks(provider_filter, kind_filter)
    
    if use_json:
        result = {
            "benchmarks": [b.to_dict() for b in benchmarks],
            "total": len(benchmarks),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    
    print("Runtime Benchmarks:")
    print("=" * 40)
    if not benchmarks:
        print("  No benchmarks recorded yet.")
        print("  Run runtime executions to generate benchmarks.")
        return 0
    
    for benchmark in sorted(benchmarks, key=lambda b: b.recorded_at):
        kind = f"[{benchmark.kind.value}]"
        print(f"  {benchmark.benchmark_id}: {benchmark.provider_id}/{benchmark.model_id} {kind}")
        print(f"    Value: {benchmark.value} {benchmark.unit}")
        print(f"    Recorded: {benchmark.recorded_at}")
        print()
    
    return 0


def _doctor(helpers, use_json: bool, all_checks: bool) -> int:
    """Run runtime plane health check."""
    registry = get_capability_registry()
    runtime_registry = get_runtime_registry(helpers.repo_root)
    
    # Get runtime state
    state = runtime_registry.get_runtime_state()
    
    checks = []
    
    # Check providers
    providers = list(registry.providers.keys())
    checks.append({
        "name": "providers_available",
        "status": "pass" if providers else "fail",
        "value": len(providers),
        "required": True,
    })
    
    # Check capabilities
    capabilities = list(registry.capabilities.keys())
    checks.append({
        "name": "capabilities_loaded",
        "status": "pass" if capabilities else "warn",
        "value": len(capabilities),
        "required": True,
    })
    
    # Check constraints
    constraints = list(registry.constraints.keys())
    checks.append({
        "name": "constraints_loaded",
        "status": "pass" if constraints else "warn",
        "value": len(constraints),
        "required": False,
    })
    
    # Check runtime state
    checks.append({
        "name": "runtime_state",
        "status": "pass" if state.overall_status == "healthy" else "warn",
        "value": state.kind.value,
        "required": True,
    })
    
    # Check benchmarks
    benchmarks = runtime_registry.list_benchmarks()
    checks.append({
        "name": "benchmarks_recorded",
        "status": "pass" if benchmarks else "info",
        "value": len(benchmarks),
        "required": False,
    })
    
    if use_json:
        print(json.dumps({
            "checks": checks,
            "summary": {
                "passed": sum(1 for c in checks if c["status"] == "pass"),
                "failed": sum(1 for c in checks if c["status"] == "fail"),
                "warnings": sum(1 for c in checks if c["status"] == "warn"),
                "info": sum(1 for c in checks if c["status"] == "info"),
            },
            "state": state.to_dict(),
        }, indent=2))
        return 0 if not any(c["status"] == "fail" for c in checks) else 1
    
    print("Runtime Plane Doctor:")
    print("=" * 40)
    for check in checks:
        status_icon = {"pass": "OK", "fail": "FAIL", "warn": "WARN", "info": "INFO"}[check["status"]]
        required = " [REQUIRED]" if check["required"] else ""
        print(f"  [{status_icon}] {check['name']}: {check['value']}{required}")
    
    print()
    print(f"Runtime State: {state.kind.value}")
    print(f"  Active Invocations: {len(state.active_invocations)}")
    print(f"  Total Invocations: {state.total_invocations}")
    print(f"  Total Proposals: {state.total_proposals}")
    print(f"  Overall Status: {state.overall_status}")
    
    has_failures = any(c["status"] == "fail" for c in checks)
    return 0 if not has_failures else 1


def _dry_run(helpers, provider_id: str, model_id: str, task: Optional[str], use_json: bool) -> int:
    """Dry-run a runtime execution."""
    from rig.domain.runtimes import get_adapter
    
    # Create or get the adapter
    try:
        adapter = get_adapter(provider_id)
    except ValueError:
        if use_json:
            print(json.dumps({"error": f"Unknown adapter: {provider_id}", "success": False}, indent=2))
        else:
            print(f"Error: Unknown adapter: {provider_id}")
        return 1
    
    # Create a dry-run request
    request: Dict[str, Any] = {
        "task": task or "dry_run",
        "dry_run": True,
        "provider_id": provider_id,
        "model_id": model_id,
    }
    
    # Invoke the adapter
    result = adapter.invoke(
        request=request,
        workspace_id=None,
        actor_id="cli",
    )
    
    if use_json:
        print(json.dumps({
            "success": result.success,
            "invocation": result.invocation.to_dict(),
            "proposals": [p.to_dict() for p in result.proposals],
            "execution_receipt": result.execution_receipt.to_dict() if result.execution_receipt else None,
        }, indent=2))
        return 0 if result.success else 1
    
    print("Dry-Run Execution:")
    print("=" * 40)
    print(f"  Adapter: {adapter.adapter_id}")
    print(f"  Provider: {adapter.provider_id}")
    print(f"  Model: {adapter.model_id}")
    print(f"  Task: {task or 'default'}")
    print(f"  Success: {result.success}")
    print()
    
    print("Invocation:")
    print(f"  ID: {result.invocation.invocation_id}")
    print(f"  Status: {result.invocation.status.value}")
    print(f"  Provider: {result.invocation.provider_id}")
    print()
    
    print("Proposals:")
    for i, proposal in enumerate(result.proposals, 1):
        print(f"  {i}. {proposal.proposal_id}: {proposal.proposal_kind}")
    
    print()
    print("Receipt:")
    if result.execution_receipt:
        print(f"  ID: {result.execution_receipt.receipt_id}")
        print(f"  Kind: {result.execution_receipt.kind}")
        print(f"  Advisory Only: {result.execution_receipt.advisory_only}")
        print(f"  Authoritative: {result.execution_receipt.authoritative}")
    
    return 0 if result.success else 1


def _state(helpers, use_json: bool) -> int:
    """Show runtime state."""
    runtime_registry = get_runtime_registry(helpers.repo_root)
    state = runtime_registry.get_runtime_state()
    
    if use_json:
        print(json.dumps(state.to_dict(), indent=2))
        return 0
    
    print("Runtime State:")
    print("=" * 40)
    print(f"  State ID: {state.state_id}")
    print(f"  Kind: {state.kind.value}")
    print(f"  Overall Status: {state.overall_status}")
    print()
    print(f"  Active Providers: {len(state.active_providers)} - {', '.join(sorted(state.active_providers)) if state.active_providers else 'none'}")
    print(f"  Active Invocations: {len(state.active_invocations)}")
    print()
    print(f"  Total Invocations: {state.total_invocations}")
    print(f"  Total Proposals: {state.total_proposals}")
    print(f"  Total Execution Receipts: {state.total_execution_receipts}")
    print(f"  Blocked Count: {state.blocked_count}")
    print(f"  Failed Count: {state.failed_count}")
    
    return 0
