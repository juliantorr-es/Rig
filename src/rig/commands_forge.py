"""Rig forge adapter CLI command.

This module provides the `rig forge` command for forge configuration inspection.
Currently implements `rig forge doctor` for validating forge configuration.

Core principles:
- Git is the canonical substrate
- No remote API calls (CLI-only module)
- No mutation: all commands are read-only
- Local-only mode is first-class and valid
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from rig.domain.forge import (
    ForgeMode,
    PromotionMode,
    ForgeCapabilities,
    ForgeIdentity,
    ForgeDoctorSeverity,
    ForgeDoctorFinding,
    ForgeDoctorReport,
    ReviewabilityBudget,
    ReviewabilityReport,
    build_forge_identity,
    capabilities_for_mode,
    derive_promotion_mode,
    build_doctor_findings,
    build_doctor_report,
    build_reviewability_report,
)


def _emit(payload: dict[str, object]) -> None:
    """Emit JSON payload to stdout."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _forge_doctor_handler(
    repo_root: Path,
    json_output: bool = False,
    target_ref: str = "main",
    head_ref: str = "HEAD",
    max_changed_files: int | None = None,
    max_listed_files: int | None = None,
) -> int:
    """Handler for `rig forge doctor` command.
    
    Inspects forge configuration and emits a report.
    
    Args:
        repo_root: Path to the git repository
        json_output: If True, emit JSON; otherwise human-readable text
        target_ref: Target reference for reviewability check (default: "main")
        head_ref: Head reference for reviewability check (default: "HEAD")
        max_changed_files: Override max changed files budget (default: None = use budget default)
        max_listed_files: Override max listed files (default: None = use budget default)
        
    Returns:
        Exit code (0 for success, 1 for errors)
    """
    try:
        report = build_doctor_report(repo_root)
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e)})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1
    
    # Build reviewability report if target_ref is provided
    reviewability_report: ReviewabilityReport | None = None
    if target_ref:
        budget = ReviewabilityBudget(
            max_changed_files=max_changed_files if max_changed_files is not None else 300,
            max_listed_files=max_listed_files if max_listed_files is not None else 300,
        )
        try:
            reviewability_report = build_reviewability_report(
                repo_root,
                budget=budget,
                target_ref=target_ref,
                head_ref=head_ref,
            )
        except Exception as e:
            # Add reviewability error as finding to main report
            pass
    
    if json_output:
        # Convert report to dict for JSON serialization
        result: dict[str, object] = {
            "identity": dataclasses.asdict(report.identity),
            "capabilities": dataclasses.asdict(report.capabilities),
            "promotion_mode": report.promotion_mode.name,
            "findings": [dataclasses.asdict(f) for f in report.findings],
            "overall_status": report.overall_status,
        }
        # Convert enum values to strings
        result["identity"]["mode"] = report.identity.mode.name  # type: ignore[typeddict-unknown-key]
        for finding in result["findings"]:
            finding["severity"] = finding["severity"].value  # type: ignore[typeddict-unknown-key]
        
        # Include reviewability report if available
        if reviewability_report is not None:
            rev_dict: dict[str, Any] = {
                "target_ref": reviewability_report.target_ref,
                "head_ref": reviewability_report.head_ref,
                "merge_base": reviewability_report.merge_base,
                "changed_file_count": reviewability_report.changed_file_count,
                "max_changed_files": reviewability_report.max_changed_files,
                "over_budget": reviewability_report.over_budget,
                "default_action": reviewability_report.default_action,
                "override_required": reviewability_report.override_required,
                "changed_files": list(reviewability_report.changed_files),
                "truncated": reviewability_report.truncated,
                "findings": [dataclasses.asdict(f) for f in reviewability_report.findings],
            }
            for finding in rev_dict["findings"]:
                finding["severity"] = finding["severity"].value  # type: ignore[typeddict-unknown-key]
            result["reviewability"] = rev_dict
        
        _emit(result)
        
        # Non-zero exit on error or critical
        if report.overall_status in ("error", "critical"):
            return 1
        return 0
    
    # Human-readable output
    print("Forge Doctor")
    print("+" * 40)
    print(f"  Mode: {report.identity.mode.name.lower().replace('_', '-')}")
    print(f"  Remote URL: {report.identity.remote_url or 'None'}")
    print(f"  Host: {report.identity.host or 'None'}")
    print(f"  Promotion Mode: {report.promotion_mode.name.lower().replace('_', '-')}")
    print(f"  Overall Status: {report.overall_status}")
    
    # Count capabilities
    caps_dict = dataclasses.asdict(report.capabilities)
    enabled = sum(1 for v in caps_dict.values() if v)
    total = len(caps_dict)
    print(f"  Capabilities: {enabled}/{total} enabled")
    
    # Show all capability flags
    print(f"\n  Capability Flags:")
    for cap_name, cap_value in caps_dict.items():
        status = "✓" if cap_value else "✗"
        print(f"    {status} {cap_name.replace('_', '-')}: {cap_value}")
    
    if report.findings:
        print(f"\n  Findings ({len(report.findings)}):")
        for f in report.findings:
            severity = f.severity.value.upper()
            print(f"    [{severity}] {f.code}: {f.message}")
            if f.remediation:
                print(f"         → {f.remediation}")
    else:
        print("\n  All forge checks passed!")
    
    # Show reviewability report if available
    if reviewability_report is not None:
        print(f"\n  Reviewability Budget:")
        print(f"    Changed files: {reviewability_report.changed_file_count} / {reviewability_report.max_changed_files}")
        if reviewability_report.over_budget:
            print(f"    Status: OVER BUDGET ({reviewability_report.default_action})")
            if reviewability_report.override_required:
                print(f"    Override required: Yes (reason needed)")
        else:
            print(f"    Status: Within budget")
        if reviewability_report.truncated:
            print(f"    Files listing: TRUNCATED ({len(reviewability_report.changed_files)} / {reviewability_report.changed_file_count} shown)")
        elif reviewability_report.changed_files:
            print(f"    Changed files: {', '.join(reviewability_report.changed_files[:10])}"
                  f"{'...' if len(reviewability_report.changed_files) > 10 else ''}")
        
        for f in reviewability_report.findings:
            severity = f.severity.value.upper()
            print(f"    [{severity}] {f.code}: {f.message}")
            if f.remediation:
                print(f"         → {f.remediation}")
    
    # Non-zero exit on error or critical
    if report.overall_status in ("error", "critical"):
        return 1
    
    # Also non-zero if reviewability is over budget with block action
    if reviewability_report is not None:
        if reviewability_report.over_budget and reviewability_report.default_action == "block_promotion":
            return 1
    
    return 0


def register(subparsers, helpers):
    """Register forge command with CLI.
    
    Args:
        subparsers: argparse subparsers object from main CLI
        helpers: Object with repo_root attribute
    """
    parser = subparsers.add_parser(
        "forge",
        help="Forge adapter management and inspection",
        description="Forge-neutral repository bootstrap and promotion abstraction (ADR 0010). Git is the substrate; remote forges are adapters.",
    )
    sub = parser.add_subparsers(dest="forge_command", required=False)
    
    # forge doctor subcommand
    doctor_parser = sub.add_parser(
        "doctor",
        help="Validate forge configuration",
        description="Inspect forge configuration and report on local-only, GitHub, GitLab, or Gitea setup. Checks for remote URL, preproduction branch, current branch, and reviewability budget.",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    doctor_parser.add_argument(
        "--target-ref",
        default="main",
        help="Target reference for reviewability check (default: main)",
    )
    doctor_parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Head reference for reviewability check (default: HEAD)",
    )
    doctor_parser.add_argument(
        "--max-changed-files",
        type=int,
        default=None,
        help="Maximum changed files budget (default: 300 from ADR 0010)",
    )
    doctor_parser.add_argument(
        "--max-listed-files",
        type=int,
        default=None,
        help="Maximum files to list in report (default: 300)",
    )
    doctor_parser.set_defaults(
        handler=lambda args: _forge_doctor_handler(
            helpers.repo_root,
            json_output=args.json,
            target_ref=args.target_ref,
            head_ref=args.head_ref,
            max_changed_files=args.max_changed_files,
            max_listed_files=args.max_listed_files,
        )
    )
    
    # Set default handler to show help if no subcommand
    parser.set_defaults(handler=lambda args: parser.print_help())
