from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommandSpec:
    name: str
    aliases: tuple[str, ...]
    usage: str
    description: str
    action_type: str
    canonical_command: tuple[str, ...]
    confirmation_policy: str
    safety_notes: str


def build_registry() -> dict[str, SlashCommandSpec]:
    specs = [
        SlashCommandSpec(
            name="help",
            aliases=(),
            usage="/help",
            description="Show chat and command help.",
            action_type="read_only",
            canonical_command=("rig", "tui", "--help"),
            confirmation_policy="none",
            safety_notes="No mutation.",
        ),
        SlashCommandSpec("status", (), "/status", "Show current Rig status.", "read_only", ("rig", "status"), "none", "No mutation."),
        SlashCommandSpec("run", (), "/run", "Create a governed run.", "governed_mutation", ("rig", "run"), "confirm", "Routes through governed workspace flow."),
        SlashCommandSpec("jobs", (), "/jobs", "Inspect jobs.", "read_only", ("rig", "job", "list"), "none", "No mutation."),
        SlashCommandSpec("job", (), "/job", "Inspect a job.", "read_only", ("rig", "job", "inspect"), "none", "No mutation."),
        SlashCommandSpec("workspaces", (), "/workspaces", "List workspaces.", "read_only", ("rig", "workspace", "list"), "none", "No mutation."),
        SlashCommandSpec("workspace", (), "/workspace", "Inspect a workspace.", "read_only", ("rig", "workspace", "inspect"), "none", "No mutation."),
        SlashCommandSpec("providers", (), "/providers", "List providers.", "read_only", ("rig", "provider", "list"), "none", "No mutation."),
        SlashCommandSpec("provider", (), "/provider", "Inspect a provider.", "read_only", ("rig", "provider", "inspect"), "none", "No mutation."),
        SlashCommandSpec("models", (), "/models", "List models.", "read_only", ("rig", "model", "list"), "none", "No mutation."),
        SlashCommandSpec("model", (), "/model", "Inspect a model.", "read_only", ("rig", "model", "inspect"), "none", "No mutation."),
        SlashCommandSpec("doctor", (), "/doctor", "Run diagnostics.", "read_only", ("rig", "doctor"), "none", "No mutation."),
        SlashCommandSpec("logs", ("log",), "/logs", "Show logs.", "read_only", ("rig", "log", "list"), "none", "No mutation."),
        SlashCommandSpec("clear", (), "/clear", "Clear transient chat state.", "read_only", (), "none", "Clears UI state only."),
        SlashCommandSpec("apply", (), "/apply", "Apply a workspace.", "blocked_in_mvp", ("rig", "workspace", "apply"), "blocked", "Blocked in MVP."),
        SlashCommandSpec("shell", (), "/shell", "Open a shell.", "blocked_in_mvp", (), "blocked", "Blocked in MVP."),
        SlashCommandSpec("execute", (), "/execute", "Execute directly.", "blocked_in_mvp", (), "blocked", "Blocked in MVP."),
        SlashCommandSpec("delete", (), "/delete", "Delete state.", "blocked_in_mvp", (), "blocked", "Blocked in MVP."),
        SlashCommandSpec("reset", (), "/reset", "Reset UI state.", "blocked_in_mvp", (), "blocked", "Blocked in MVP."),
        SlashCommandSpec("migrate", (), "/migrate", "Migrate legacy queue.", "repair_requires_confirmation", ("rig", "doctor", "repair"), "confirm", "Repair is deliberate."),
    ]
    registry: dict[str, SlashCommandSpec] = {}
    for spec in specs:
        registry[spec.name] = spec
        for alias in spec.aliases:
            registry[alias] = spec
    return registry

