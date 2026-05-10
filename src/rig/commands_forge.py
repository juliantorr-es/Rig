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
    PromotionPlan,
    PromotionPlanStep,
    PromotionDraft,
    PromotionArtifact,
    GitHubPromotionApplyResult,
    GitHubApplySafetyReport,
    parse_github_remote_url,
    build_forge_identity,
    capabilities_for_mode,
    derive_promotion_mode,
    derive_promotion_branch_name,
    _derive_provider_command,
    build_doctor_findings,
    build_doctor_report,
    build_reviewability_report,
    build_promotion_plan,
    build_promotion_draft,
    build_promotion_artifact,
    build_github_apply_safety_report,
    apply_github_draft_pr_promotion,
    verify_promotion_artifact,
)


def _emit(payload: dict[str, object]) -> None:
    """Emit JSON payload to stdout."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _forge_doctor_handler(
    repo_root: Path,
    json_output: bool = False,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
    max_changed_files: int | None = None,
    max_listed_files: int | None = None,
) -> int:
    """Handler for `rig forge doctor` command.
    
    Inspects forge configuration and emits a report.
    
    Args:
        repo_root: Path to the git repository
        json_output: If True, emit JSON; otherwise human-readable text
        target_ref: Target reference for reviewability check (default: "preproduction")
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


def _serialize_reviewability_report_for_plan(report: ReviewabilityReport) -> dict[str, Any]:
    """Serialize ReviewabilityReport to JSON-compatible dict for plan output."""
    result: dict[str, Any] = {
        "target_ref": report.target_ref,
        "head_ref": report.head_ref,
        "merge_base": report.merge_base,
        "changed_file_count": report.changed_file_count,
        "max_changed_files": report.max_changed_files,
        "over_budget": report.over_budget,
        "default_action": report.default_action,
        "override_required": report.override_required,
        "changed_files": list(report.changed_files),
        "truncated": report.truncated,
        "findings": [dataclasses.asdict(f) for f in report.findings],
    }
    for finding in result["findings"]:
        finding["severity"] = finding["severity"].value  # type: ignore[typeddict-unknown-key]
    return result


def _serialize_promotion_plan_step(step: PromotionPlanStep) -> dict[str, Any]:
    """Serialize PromotionPlanStep to JSON-compatible dict."""
    return {
        "step_id": step.step_id,
        "description": step.description,
        "command": step.command,
        "mutates_state": step.mutates_state,
        "required": step.required,
    }


def _serialize_promotion_draft(draft: PromotionDraft) -> dict[str, Any]:
    """Serialize PromotionDraft to JSON-compatible dict.
    
    Mission 6: Includes body_path field
    """
    result: dict[str, Any] = {
        "promotion_branch": draft.promotion_branch,
        "base_ref": draft.base_ref,
        "head_ref": draft.head_ref,
        "title": draft.title,
        "body": draft.body,
        "provider_command": draft.provider_command,
        "provider_url_hint": draft.provider_url_hint,
        "draft_only": draft.draft_only,
        "body_path": draft.body_path,
    }
    return result


def _serialize_promotion_artifact(artifact: PromotionArtifact) -> dict[str, Any]:
    """Serialize PromotionArtifact to JSON-compatible dict.
    
    Mission 6: Promotion Body File Dry-Run Artifact
    """
    return {
        "artifact_id": artifact.artifact_id,
        "directory": artifact.directory,
        "body_path": artifact.body_path,
        "metadata_path": artifact.metadata_path,
        "body_sha256": artifact.body_sha256,
        "body_bytes": artifact.body_bytes,
        "wrote_files": artifact.wrote_files,
    }


def _serialize_promotion_plan(plan: PromotionPlan) -> dict[str, Any]:
    """Serialize PromotionPlan to JSON-compatible dict."""
    result: dict[str, Any] = {
        "mode": plan.mode.name.lower(),
        "forge_mode": plan.forge_mode.name.lower(),
        "target_ref": plan.target_ref,
        "head_ref": plan.head_ref,
        "identity": dataclasses.asdict(plan.identity),
        "reviewability": _serialize_reviewability_report_for_plan(plan.reviewability),
        "steps": [_serialize_promotion_plan_step(s) for s in plan.steps],
        "blockers": [dataclasses.asdict(b) for b in plan.blockers],
        "ready": plan.ready,
        "dry_run_only": plan.dry_run_only,
    }
    # Convert identity mode enum
    result["identity"]["mode"] = plan.identity.mode.name  # type: ignore[typeddict-unknown-key]
    # Convert blockers severity enums
    for blocker in result["blockers"]:
        blocker["severity"] = blocker["severity"].value  # type: ignore[typeddict-unknown-key]
    # Include draft if available (Mission 5)
    if plan.draft is not None:
        result["draft"] = _serialize_promotion_draft(plan.draft)
    return result


def _emit_human_promotion_plan(
    plan: PromotionPlan,
    artifact: PromotionArtifact | None = None,
) -> None:
    """Emit human-readable promotion plan to stdout.
    
    Mission 6: Added artifact parameter to show body file info
    """
    print("Promotion Plan (Dry-Run)")
    print("+" * 40)
    print(f"  Forge Mode: {plan.forge_mode.name.lower().replace('_', '-')}")
    print(f"  Promotion Mode: {plan.mode.name.lower().replace('_', '-')}")
    print(f"  Target: {plan.target_ref}")
    print(f"  Head: {plan.head_ref}")
    print(f"  Ready: {'Yes' if plan.ready else 'No'}")
    print(f"  Dry-run only: Yes - No Git or remote state was mutated.")
    
    # Reviewability summary
    rev = plan.reviewability
    print(f"\n  Reviewability:")
    print(f"    Changed files: {rev.changed_file_count} / {rev.max_changed_files}")
    if rev.over_budget:
        print(f"    Status: OVER BUDGET ({rev.default_action})")
    else:
        print(f"    Status: Within budget")
    
    # Draft information (Mission 5)
    if plan.draft is not None:
        draft = plan.draft
        print(f"\n  Promotion Draft:")
        print(f"    Promotion Branch: {draft.promotion_branch}")
        print(f"    PR/MR Title: {draft.title}")
        if draft.provider_command:
            print(f"    Provider Command: {draft.provider_command}")
        if draft.provider_url_hint:
            print(f"    Provider URL Hint: {draft.provider_url_hint}")
        print(f"    Draft Only: {'Yes' if draft.draft_only else 'No'}")
    
    # Artifact information (Mission 6)
    if artifact is not None:
        print(f"\n  Artifact:")
        print(f"    Body SHA256: {artifact.body_sha256}")
        print(f"    Body Bytes: {artifact.body_bytes}")
        print(f"    Body Path: {artifact.body_path}")
        print(f"    Files Written: {'Yes' if artifact.wrote_files else 'No'}")
        if not artifact.wrote_files:
            print(f"    (Use --write-artifact to write files)")
    
    # Blockers
    if plan.blockers:
        print(f"\n  Blockers ({len(plan.blockers)}):")
        for b in plan.blockers:
            severity = b.severity.value.upper()
            print(f"    [{severity}] {b.code}: {b.message}")
            if b.remediation:
                print(f"         -> {b.remediation}")
    else:
        print(f"\n  No blockers.")
    
    # Steps
    print(f"\n  Action Plan ({len(plan.steps)} steps):")
    for i, step in enumerate(plan.steps, 1):
        status = "Y" if step.required else "N"
        mutate_marker = " [would mutate]" if step.mutates_state else ""
        print(f"    [{status}] {i}. {step.description}{mutate_marker}")
        if step.command:
            print(f"        -> {step.command}")
    
    print(f"\n  No Git or remote state was mutated.")


def _promote_handler(
    repo_root: Path,
    dry_run: bool = True,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
    max_changed_files: int | None = None,
    json_output: bool = False,
    write_artifact: bool = False,
    artifact_dir: str = ".rig/work/promotions",
    apply: bool = False,
    provider: str | None = None,
    remote: str = "origin",
    safety_report: bool = False,
) -> int:
    """Handler for `rig forge promote` command.
    
    Builds a promotion plan and emits it. Can also apply promotion
    with --apply and --provider flags.
    
    Mission 6: Added --write-artifact and --artifact-dir support for local
    body file artifact generation.
    Mission 7: Added --apply and --provider support for GitHub draft PR apply.
    Mission 8: Added --safety-report for read-only safety verification.
    
    Args:
        repo_root: Path to the git repository
        dry_run: If True, only plan (default: True). Only dry-run is implemented
            for non-apply mode. When apply=True, dry_run controls execution.
        target_ref: Target reference for promotion (default: "preproduction")
        head_ref: Head reference for promotion (default: "HEAD")
        max_changed_files: Override max changed files budget (default: None = use 300)
        json_output: If True, emit JSON; otherwise human-readable text
        write_artifact: If True, write artifact files to filesystem (default: False)
        artifact_dir: Base directory for artifacts (default: ".rig/work/promotions")
        apply: If True, apply the promotion (requires --provider) (default: False)
        provider: Provider for apply (e.g., "github") (default: None)
        remote: Git remote name for apply (default: "origin")
        safety_report: If True, emit safety report and exit without mutation (default: False)
        
    Returns:
        Exit code (0 for success/ready, 1 for errors/not ready)
    """
    # Validate apply parameters
    if apply:
        if provider is None:
            if json_output:
                _emit({"status": "error", "error": "--apply requires --provider to be specified"})
            else:
                print("--apply requires --provider to be specified", file=sys.stderr)
            return 1
        
        if provider != "github":
            if json_output:
                _emit({"status": "error", "error": f"Provider {provider} not yet implemented. Only 'github' is supported."})
            else:
                print(f"Provider {provider} not yet implemented. Only 'github' is supported.", file=sys.stderr)
            return 1
        
        if not dry_run:
            # When apply=True and dry_run=False, we actually want to execute
            # This is the only case where dry_run=False is meaningful
            pass
    else:
        # Legacy behavior: only dry-run mode without --apply
        if not dry_run:
            print("Only --dry-run is implemented for now.", file=sys.stderr)
            print("No Git or remote state was mutated.", file=sys.stderr)
            return 1
    
    try:
        budget = ReviewabilityBudget(
            max_changed_files=max_changed_files if max_changed_files is not None else 300,
        )
        plan = build_promotion_plan(
            repo_root,
            target_ref=target_ref,
            head_ref=head_ref,
            budget=budget,
        )
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e)})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    # Handle --safety-report mode (Mission 8)
    if safety_report and provider == "github":
        if not write_artifact:
            write_artifact = True
        
        # Build artifact with write=True for safety report
        if plan.draft is not None:
            try:
                artifact = build_promotion_artifact(
                    repo_path=repo_root,
                    plan=plan,
                    write=True,
                    artifact_dir=artifact_dir,
                )
                
                # Build safety report
                safety_report_obj = build_github_apply_safety_report(
                    repo_path=repo_root,
                    plan=plan,
                    artifact=artifact,
                    remote=remote,
                )
                
                if json_output:
                    result = _serialize_promotion_plan(plan)
                    result["artifact"] = _serialize_promotion_artifact(artifact)
                    result["safety_report"] = _serialize_safety_report(safety_report_obj)
                    _emit(result)
                    # Return 0 if safety report is ready, 1 otherwise
                    if safety_report_obj.ready:
                        return 0
                    return 1
                else:
                    _emit_human_safety_report(safety_report_obj, plan)
                    if safety_report_obj.ready:
                        return 0
                    return 1
            except Exception as e:
                if json_output:
                    _emit({"status": "error", "error": f"Failed to build safety report: {e}"})
                else:
                    print(f"Error: Failed to build safety report: {e}", file=sys.stderr)
                return 1
        else:
            if json_output:
                _emit({"status": "error", "error": "Plan has no draft - cannot build safety report"})
            else:
                print("Error: Plan has no draft - cannot build safety report", file=sys.stderr)
            return 1
    
    # Handle --apply mode (Mission 7 + 8)
    if apply and provider == "github":
        # For apply mode, we need artifact files written
        # If write_artifact is False, automatically write artifact
        if not write_artifact:
            write_artifact = True
        
        # Build artifact with write=True for apply mode
        artifact: PromotionArtifact | None = None
        if plan.draft is not None:
            try:
                artifact = build_promotion_artifact(
                    repo_path=repo_root,
                    plan=plan,
                    write=True,
                    artifact_dir=artifact_dir,
                )
                # Rebuild draft with artifact info and updated provider command
                if artifact is not None:
                    body_path_to_use = artifact.body_path
                    new_provider_command, new_provider_url_hint = _derive_provider_command(
                        forge_mode=plan.forge_mode,
                        promotion_branch=plan.draft.promotion_branch,
                        target_ref=plan.target_ref,
                        title=plan.draft.title,
                        body_path=body_path_to_use,
                    )
                    
                    # Update the plan with the new draft
                    updated_draft = PromotionDraft(
                        promotion_branch=plan.draft.promotion_branch,
                        base_ref=plan.draft.base_ref,
                        head_ref=plan.draft.head_ref,
                        title=plan.draft.title,
                        body=plan.draft.body,
                        provider_command=new_provider_command,
                        provider_url_hint=new_provider_url_hint,
                        draft_only=plan.draft.draft_only,
                        body_path=body_path_to_use,
                    )
                    plan = PromotionPlan(
                        mode=plan.mode,
                        forge_mode=plan.forge_mode,
                        target_ref=plan.target_ref,
                        head_ref=plan.head_ref,
                        identity=plan.identity,
                        reviewability=plan.reviewability,
                        steps=plan.steps,
                        blockers=plan.blockers,
                        ready=plan.ready,
                        dry_run_only=plan.dry_run_only,
                        draft=updated_draft,
                    )
            except (ValueError, OSError) as e:
                if json_output:
                    _emit({"status": "error", "error": f"Failed to build artifact for apply: {e}"})
                else:
                    print(f"Error: Failed to build artifact for apply: {e}", file=sys.stderr)
                return 1
        else:
            if json_output:
                _emit({"status": "error", "error": "Plan has no draft - cannot apply"})
            else:
                print("Error: Plan has no draft - cannot apply", file=sys.stderr)
            return 1
        
        # Execute apply for GitHub
        if artifact is not None:
            try:
                apply_result = apply_github_draft_pr_promotion(
                    repo_path=repo_root,
                    plan=plan,
                    artifact=artifact,
                    remote=remote,
                    dry_run=dry_run,
                )
                
                if json_output:
                    result = _serialize_promotion_plan(plan)
                    if artifact is not None:
                        result["artifact"] = _serialize_promotion_artifact(artifact)
                    # Add apply_result to JSON output
                    result["apply_result"] = dataclasses.asdict(apply_result)
                    # Convert findings severity enums
                    if "findings" in result["apply_result"]:
                        for finding in result["apply_result"]["findings"]:
                            if isinstance(finding, dict) and "severity" in finding:
                                finding["severity"] = finding["severity"].value if hasattr(finding["severity"], "value") else finding["severity"]
                    _emit(result)
                    # Return 0 if applied or dry_run with no errors, 1 otherwise
                    if not apply_result.applied and not dry_run and not apply_result.findings:
                        return 1
                    if apply_result.findings and any(f.severity.value == "error" for f in apply_result.findings):
                        return 1
                    return 0
                else:
                    # Human-readable output for apply
                    _emit_human_apply_result(apply_result, plan)
                    # Return 0 if applied successfully, 1 otherwise
                    if apply_result.applied:
                        return 0
                    elif dry_run and not apply_result.findings:
                        return 0
                    elif apply_result.findings and any(f.severity.value == "error" for f in apply_result.findings):
                        return 1
                    return 0
            except Exception as e:
                if json_output:
                    _emit({"status": "error", "error": str(e)})
                else:
                    print(f"Error during apply: {e}", file=sys.stderr)
                return 1
        else:
            if json_output:
                _emit({"status": "error", "error": "No artifact available for apply"})
            else:
                print("Error: No artifact available for apply", file=sys.stderr)
            return 1
    
    # Non-apply mode: Build artifact if requested (Mission 6)
    artifact: PromotionArtifact | None = None
    if plan.draft is not None:
        try:
            # Build artifact always to compute paths (even if not writing)
            artifact = build_promotion_artifact(
                repo_path=repo_root,
                plan=plan,
                write=write_artifact,
                artifact_dir=artifact_dir,
            )
            # Rebuild draft with artifact info and updated provider command
            if artifact is not None:
                # Rebuild provider command with body_path if writing
                body_path_to_use = artifact.body_path if write_artifact else None
                new_provider_command, new_provider_url_hint = _derive_provider_command(
                    forge_mode=plan.forge_mode,
                    promotion_branch=plan.draft.promotion_branch,
                    target_ref=plan.target_ref,
                    title=plan.draft.title,
                    body_path=body_path_to_use,
                )
                
                # Update the plan with the new draft that has body_path and updated command
                updated_draft = PromotionDraft(
                    promotion_branch=plan.draft.promotion_branch,
                    base_ref=plan.draft.base_ref,
                    head_ref=plan.draft.head_ref,
                    title=plan.draft.title,
                    body=plan.draft.body,
                    provider_command=new_provider_command,
                    provider_url_hint=new_provider_url_hint,
                    draft_only=plan.draft.draft_only,
                    body_path=body_path_to_use,
                )
                plan = PromotionPlan(
                    mode=plan.mode,
                    forge_mode=plan.forge_mode,
                    target_ref=plan.target_ref,
                    head_ref=plan.head_ref,
                    identity=plan.identity,
                    reviewability=plan.reviewability,
                    steps=plan.steps,
                    blockers=plan.blockers,
                    ready=plan.ready,
                    dry_run_only=plan.dry_run_only,
                    draft=updated_draft,
                )
        except (ValueError, OSError) as e:
            # Artifact building failed - log but don't fail the command
            # This can happen if draft body is empty or write fails
            if write_artifact:
                print(f"Warning: Could not build artifact: {e}", file=sys.stderr)
            artifact = None
    
    if json_output:
        result = _serialize_promotion_plan(plan)
        # Include artifact in JSON output (Mission 6)
        if artifact is not None:
            result["artifact"] = _serialize_promotion_artifact(artifact)
        _emit(result)
        return 0
    
    _emit_human_promotion_plan(plan, artifact)
    return 0 if plan.ready else 1


def _serialize_apply_result(apply_result: GitHubPromotionApplyResult) -> dict[str, Any]:
    """Serialize GitHubPromotionApplyResult to JSON-compatible dict.

    Mission 7: GitHub Draft PR Apply
    """
    result: dict[str, Any] = {
        "provider": apply_result.provider,
        "promotion_branch": apply_result.promotion_branch,
        "target_ref": apply_result.target_ref,
        "head_ref": apply_result.head_ref,
        "artifact_id": apply_result.artifact_id,
        "body_path": apply_result.body_path,
        "pr_url": apply_result.pr_url,
        "commands": list(apply_result.commands),
        "ready_before_apply": apply_result.ready_before_apply,
        "applied": apply_result.applied,
        "skipped_existing_pr": apply_result.skipped_existing_pr,
        "evidence_path": apply_result.evidence_path,
        "findings": [dataclasses.asdict(f) for f in apply_result.findings],
    }
    # Convert findings severity enums
    for finding in result["findings"]:
        finding["severity"] = finding["severity"].value  # type: ignore[typeddict-unknown-key]
    return result


def _serialize_safety_report(safety_report: GitHubApplySafetyReport) -> dict[str, Any]:
    """Serialize GitHubApplySafetyReport to JSON-compatible dict.

    Mission 8: GitHub Apply Safety Doctor
    """
    result: dict[str, Any] = {
        "provider": safety_report.provider,
        "owner": safety_report.owner,
        "repository": safety_report.repository,
        "remote_url": safety_report.remote_url,
        "gh_available": safety_report.gh_available,
        "gh_authenticated": safety_report.gh_authenticated,
        "artifact_valid": safety_report.artifact_valid,
        "existing_pr_url": safety_report.existing_pr_url,
        "promotion_branch_safe": safety_report.promotion_branch_safe,
        "direct_target_mutation_detected": safety_report.direct_target_mutation_detected,
        "forbidden_commands_detected": list(safety_report.forbidden_commands_detected),
        "ready": safety_report.ready,
        "findings": [dataclasses.asdict(f) for f in safety_report.findings],
    }
    # Convert findings severity enums
    for finding in result["findings"]:
        finding["severity"] = finding["severity"].value  # type: ignore[typeddict-unknown-key]
    return result


def _emit_human_safety_report(
    safety_report: GitHubApplySafetyReport,
    plan: PromotionPlan,
) -> None:
    """Emit human-readable safety report to stdout.

    Mission 8: GitHub Apply Safety Doctor
    """
    print("GitHub Apply Safety Report")
    print("+" * 40)
    print(f"  Provider: {safety_report.provider}")
    print(f"  Ready: {'Yes' if safety_report.ready else 'No'}")
    print()
    
    # GitHub identity
    print(f"  GitHub Identity:")
    print(f"    Owner: {safety_report.owner or 'N/A'}")
    print(f"    Repository: {safety_report.repository or 'N/A'}")
    print(f"    Remote URL: {safety_report.remote_url or 'N/A'}")
    print()
    
    # gh CLI status
    print(f"  GitHub CLI:")
    print(f"    Available: {'Yes' if safety_report.gh_available else 'No'}")
    print(f"    Authenticated: {'Yes' if safety_report.gh_authenticated else 'No'}")
    print()
    
    # Artifact status
    print(f"  Artifact Valid: {'Yes' if safety_report.artifact_valid else 'No'}")
    print()
    
    # PR status
    if safety_report.existing_pr_url:
        print(f"  Existing PR URL: {safety_report.existing_pr_url}")
    else:
        print(f"  Existing PR: None detected")
    print()
    
    # Branch safety
    print(f"  Promotion Branch Safe: {'Yes' if safety_report.promotion_branch_safe else 'No'}")
    print(f"  Direct Target Mutation Detected: {'Yes' if safety_report.direct_target_mutation_detected else 'No'}")
    
    # Forbidden commands
    if safety_report.forbidden_commands_detected:
        print(f"  Forbidden Commands Detected: {', '.join(safety_report.forbidden_commands_detected)}")
    else:
        print(f"  Forbidden Commands Detected: None")
    print()
    
    # Safety confirmation
    print(f"  SAFETY: No mutations were performed (read-only report).")
    print()
    
    # Findings
    if safety_report.findings:
        print(f"  Findings ({len(safety_report.findings)}):")
        for f in safety_report.findings:
            severity_icon = {"error": " ERROR ", "warning": " WARN ", "info": " INFO ", "critical": " CRIT "}.get(f.severity.value, " ? ")
            print(f"    [{f.code}] {severity_icon} {f.message}")
            if f.remediation:
                print(f"            -> {f.remediation}")
    else:
        print(f"  Findings: All checks passed.")
    print()


def _emit_human_apply_result(
    apply_result: GitHubPromotionApplyResult,
    plan: PromotionPlan,
) -> None:
    """Emit human-readable apply result to stdout.

    Mission 7: GitHub Draft PR Apply
    """
    print("Promotion Apply Result")
    print("+" * 40)
    print(f"  Provider: {apply_result.provider}")
    print(f"  Applied: {'Yes' if apply_result.applied else 'No'}")
    print(f"  Dry-run: {'Yes' if not apply_result.applied else 'No'}")
    print(f"  Ready before apply: {'Yes' if apply_result.ready_before_apply else 'No'}")
    print()
    print(f"  Promotion Branch: {apply_result.promotion_branch}")
    print(f"  Target: {apply_result.target_ref}")
    print(f"  Head: {apply_result.head_ref}")
    print(f"  Artifact ID: {apply_result.artifact_id}")
    print()
    print(f"  Body Path: {apply_result.body_path}")
    if apply_result.evidence_path:
        print(f"  Evidence Path: {apply_result.evidence_path}")
    print()
    
    # PR URL
    if apply_result.pr_url:
        print(f"  PR URL: {apply_result.pr_url}")
    elif apply_result.skipped_existing_pr:
        print(f"  PR: Skipped existing PR")
    else:
        print(f"  PR: Not created")
    print()
    
    # Commands
    if apply_result.commands:
        print(f"  Commands:")
        for cmd in apply_result.commands:
            print(f"    - {cmd}")
    print()
    
    # Safety confirmation
    print(f"  SAFETY: No direct mutation of preproduction was performed.")
    print(f"  SAFETY: No PR merge was attempted.")
    print(f"  SAFETY: No auto-merge was enabled.")
    print()
    
    # Findings
    if apply_result.findings:
        print(f"  Findings ({len(apply_result.findings)}):")
        for f in apply_result.findings:
            severity = f.severity.value.upper()
            print(f"    [{severity}] {f.code}: {f.message}")
            if f.remediation:
                print(f"         -> {f.remediation}")
    else:
        print(f"  No findings.")


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
        default="preproduction",
        help="Target reference for reviewability check (default: preproduction)",
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
    
    # forge promote subcommand
    promote_parser = sub.add_parser(
        "promote",
        help="Plan promotion to target branch",
        description="Plan and validate promotion, or apply promotion with --apply. Default is dry-run only. No Git mutation is performed without --apply.",
    )
    promote_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run only, do not mutate state (default: True). Note: --apply with --dry-run will plan apply without executing.",
    )
    promote_parser.add_argument(
        "--target-ref",
        default="preproduction",
        help="Target reference for promotion (default: preproduction)",
    )
    promote_parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Head reference for promotion (default: HEAD)",
    )
    promote_parser.add_argument(
        "--max-changed-files",
        type=int,
        default=None,
        help="Maximum changed files budget (default: 300)",
    )
    promote_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    # Mission 6: Artifact writing flags
    promote_parser.add_argument(
        "--write-artifact",
        action="store_true",
        default=False,
        help="Write promotion artifact files (body.md, metadata.json) to filesystem (default: False)",
    )
    promote_parser.add_argument(
        "--artifact-dir",
        default=".rig/work/promotions",
        help="Base directory for promotion artifacts (default: .rig/work/promotions)",
    )
    # Mission 7: Apply flags
    promote_parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply the promotion (creates draft PR). Requires --provider. Fails closed if not ready.",
    )
    promote_parser.add_argument(
        "--provider",
        default=None,
        help="Provider for --apply: 'github' (default: None, only 'github' is currently implemented)",
    )
    promote_parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote name for --apply (default: origin)",
    )
    # Mission 8: Safety report
    promote_parser.add_argument(
        "--safety-report",
        action="store_true",
        default=False,
        help="Emit GitHub apply safety report and exit without mutation. Requires --provider github. Read-only verification of preconditions.",
    )
    promote_parser.set_defaults(
        handler=lambda args: _promote_handler(
            helpers.repo_root,
            dry_run=args.dry_run,
            target_ref=args.target_ref,
            head_ref=args.head_ref,
            max_changed_files=args.max_changed_files,
            json_output=args.json,
            write_artifact=args.write_artifact,
            artifact_dir=args.artifact_dir,
            apply=args.apply,
            provider=args.provider,
            remote=args.remote,
            safety_report=args.safety_report,
        )
    )
    
    # Set default handler to show help if no subcommand
    parser.set_defaults(handler=lambda args: parser.print_help())
