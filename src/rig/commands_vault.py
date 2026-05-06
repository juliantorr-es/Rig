"""Rig CLI - Vault Export Commands.

Vault is a projection, not source of truth.
Markdown notes are for human-operable memory.
JSON/JSONL receipts remain machine evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.vault_export import VaultExporter, GENERATED_HEADER
from rig_tools.settings_store import SettingsStore


def register(subparsers, helpers):
    """Registers the 'vault' command group."""
    parser = subparsers.add_parser(
        "vault", 
        help="Rig OS Vault Export: Obsidian-compatible Markdown projection"
    )
    sub = parser.add_subparsers(dest="vault_command")

    # Status
    status_parser = sub.add_parser("status", help="Show vault export subsystem status")
    status_parser.add_argument("--format", choices=["text", "json"], default="text")
    status_parser.set_defaults(handler=lambda args: run_status(helpers, args.format))

    # Export
    export_parser = sub.add_parser("export", help="Export vault notes from Rig state")
    export_parser.add_argument(
        "--out", 
        type=str, 
        default=None,
        help="Output vault path (default: from settings, then .build/rig/vault/Rig-vault)"
    )
    export_parser.add_argument(
        "--dry-run", 
        action="store_true", 
        default=False,
        help="Write dry-run preview receipts only, do not create vault notes"
    )
    export_parser.add_argument(
        "--copy-json", 
        action="store_true", 
        default=False,
        help="Copy selected JSON receipts to Attachments/json/"
    )
    export_parser.add_argument(
        "--copy-bundles", 
        action="store_true", 
        default=False,
        help="Copy selected bundle manifests to Attachments/bundles/"
    )
    export_parser.add_argument(
        "--format", 
        choices=["text", "json"], 
        default="text",
        help="Output format for summary"
    )
    export_parser.set_defaults(handler=lambda args: run_export(
        helpers, 
        dry_run=args.dry_run, 
        copy_json=args.copy_json, 
        copy_bundles=args.copy_bundles,
        out_path=args.out,
        output_format=args.format
    ))

    # Open-URI
    open_uri_parser = sub.add_parser(
        "open-uri", 
        help="Print Obsidian URI for a vault note (does not launch Obsidian)"
    )
    open_uri_parser.add_argument(
        "--note", 
        type=str, 
        default=None,
        help="Note path within vault (e.g., '00 Dashboard.md')"
    )
    open_uri_parser.add_argument(
        "--task", 
        type=str, 
        default=None,
        help="Task ID to open (will be translated to note path)"
    )
    open_uri_parser.add_argument(
        "--vault-name", 
        type=str, 
        default="Rig-vault",
        help="Obsidian vault name (default: Rig-vault)"
    )
    open_uri_parser.set_defaults(handler=lambda args: run_open_uri(
        helpers, 
        note=args.note, 
        task=args.task,
        vault_name=args.vault_name
    ))


def run_status(helpers, output_format: str = "text") -> int:
    """Show vault export subsystem status."""
    exporter = VaultExporter(helpers.repo_root)
    status = exporter.get_status()

    if output_format == "json":
        print(json.dumps(status, indent=2))
    else:
        print("Rig Vault Export Status:")
        print(f"  Status: {status['status']}")
        print(f"  Vault Path: {status['vault_path']}")
        if status['warnings']:
            print(f"  Warnings: {len(status['warnings'])}")
            for w in status['warnings']:
                print(f"    - {w}")

    return 0


def run_export(
    helpers,
    dry_run: bool = False,
    copy_json: bool = False,
    copy_bundles: bool = False,
    out_path: Optional[str] = None,
    output_format: str = "text"
) -> int:
    """Export vault notes from Rig state and projections."""
    vault_path = None
    if out_path:
        vault_path = helpers.repo_root / out_path

    exporter = VaultExporter(helpers.repo_root, vault_path=vault_path)
    manifest = exporter.export(
        dry_run=dry_run,
        copy_json=copy_json,
        copy_bundles=copy_bundles
    )

    if output_format == "json":
        print(json.dumps(manifest.to_dict(), indent=2))
    else:
        print(f"Vault Export: {manifest.export_id}")
        print(f"  Status: {manifest.status}")
        print(f"  Vault Path: {manifest.vault_path}")
        print(f"  Notes: {manifest.note_count}")
        print(f"  Task Notes: {manifest.task_note_count}")
        print(f"  Copied JSON: {manifest.copied_json_count}")
        print(f"  Copied Bundles: {manifest.copied_bundle_count}")

        if manifest.warnings:
            print(f"  Warnings: {len(manifest.warnings)}")
            for w in manifest.warnings:
                print(f"    - {w}")

        if dry_run:
            print("\n(Dry run - no vault notes were written; see preview in .build/rig/vault/dry-run/)")
        else:
            print(f"\nVault notes written to: {helpers.repo_root / manifest.vault_path}")

    return 0


def run_open_uri(helpers, note: Optional[str] = None, task: Optional[str] = None, vault_name: str = "Rig-vault") -> int:
    """Print Obsidian URI for a vault note."""
    vault_path = None

    # Determine vault path from settings
    settings = SettingsStore(helpers.repo_root)
    effective = settings.get_effective_settings()
    vault_path_str = effective.get("vault_path", ".build/rig/vault/Rig-vault")
    vault_root = helpers.repo_root / vault_path_str

    exporter = VaultExporter(helpers.repo_root, vault_path=vault_root)

    if task:
        # Translate task ID to note path
        note_path = f"01 Tasks/{task}.md"
    elif note:
        note_path = note
    else:
        print("Error: Must specify either --note or --task", file=__import__('sys').stderr)
        return 1

    uri = exporter.get_obsidian_uri(note_path, vault_name=vault_name)
    print(uri)

    return 0
