"""Migration Import Visibility for ADR 0004.

This module provides tooling to:
- Identify current import sites of legacy Cluster 2 modules
- Track migration progress
- Prevent new consumers from depending on legacy internals

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

# Legacy Cluster 2 modules being migrated
LEGACY_MODULES = frozenset({
    "rig.domain.runtime_stream",
    "rig.domain.runtime_supervisor",
    "rig.domain.runtime_websocket",
    "rig.domain.runtime_projection",
})

# New streaming domain module
NEW_MODULE = "rig.domain.runtime_streaming"

class ImportSite:
    """Represents an import site in the codebase."""

    def __init__(
        self,
        file_path: Path,
        line_number: int,
        import_statement: str,
        imported_names: list[str],
    ) -> None:
        self.file_path = file_path
        self.line_number = line_number
        self.import_statement = import_statement
        self.imported_names = imported_names

    def __repr__(self) -> str:
        return (
            f"ImportSite({self.file_path}:{self.line_number}, "
            f"imports={self.imported_names})"
        )

def find_imports_in_file(file_path: Path) -> list[ImportSite]:
    """Find all imports from legacy Cluster 2 modules in a file."""
    try:
        source = file_path.read_text()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    import_sites: list[ImportSite] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in LEGACY_MODULES:
                imported_names = [alias.name for alias in node.names]
                import_sites.append(ImportSite(
                    file_path=file_path,
                    line_number=node.lineno,
                    import_statement=f"from {module} import {', '.join(imported_names)}",
                    imported_names=imported_names,
                ))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # Handle "import rig.domain.runtime_stream" style
                module_parts = alias.name.split(".")
                import_module = ".".join(module_parts[:4])  # Get first 4 parts
                if import_module in LEGACY_MODULES:
                    import_sites.append(ImportSite(
                        file_path=file_path,
                        line_number=node.lineno,
                        import_statement=f"import {alias.name}",
                        imported_names=[alias.name],
                    ))

    return import_sites

def scan_directory(root_path: Path) -> dict[str, list[ImportSite]]:
    """Scan a directory tree for legacy imports.

    Returns dict mapping legacy module name to list of ImportSite objects.
    """
    results: dict[str, list[ImportSite]] = {module: [] for module in LEGACY_MODULES}

    for py_file in root_path.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue
        for import_site in find_imports_in_file(py_file):
            results[import_site.import_statement.split(" ")[1]].append(import_site)

    return results

def get_migration_summary(root_path: Path) -> dict[str, Any]:
    """Get a summary of migration progress.

    Returns dict with:
    - total_legacy_imports: total number of imports from legacy modules
    - by_module: breakdown by legacy module
    - by_file: files with the most legacy imports
    """
    results = scan_directory(root_path)

    total = sum(len(sites) for sites in results.values())
    by_module = {module: len(sites) for module, sites in results.items()}

    # Find files with most legacy imports
    file_counts: dict[Path, int] = {}
    for sites in results.values():
        for site in sites:
            file_counts[site.file_path] = file_counts.get(site.file_path, 0) + 1

    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_legacy_imports": total,
        "by_module": by_module,
        "by_file": [{"file": str(f), "count": c} for f, c in sorted_files[:20]],
    }

def check_new_imports(file_path: Path) -> list[ImportSite]:
    """Check if a file contains imports from legacy Cluster 2 modules.

    Used for CI gating: new files should not import from legacy modules.
    """
    return find_imports_in_file(file_path)

def validate_no_legacy_imports(file_paths: list[Path]) -> tuple[bool, list[ImportSite]]:
    """Validate that none of the given files import from legacy modules.

    Returns (is_valid, list_of_violations).
    """
    violations: list[ImportSite] = []
    for file_path in file_paths:
        violations.extend(check_new_imports(file_path))

    return len(violations) == 0, violations

if __name__ == "__main__":
    # CLI entry point for migration visibility
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="ADR 0004 Migration Import Visibility Tool"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--check",
        type=Path,
        nargs="*",
        help="Check specific files for legacy imports",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print migration summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.check:
        # Check specific files
        violations, _ = validate_no_legacy_imports(args.check)
        if args.json:
            print(json.dumps(
                {"valid": violations == [], "violations": str(violations)},
                indent=2,
            ))
        else:
            if violations:
                print("VIOLATIONS FOUND:")
                for v in violations:
                    print(f"  {v}")
                sys.exit(1)
            else:
                print("No legacy imports found.")
                sys.exit(0)

    if args.summary:
        summary = get_migration_summary(args.root)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("ADR 0004 Migration Summary")
            print("=" * 50)
            print(f"Total legacy imports: {summary['total_legacy_imports']}")
            print("\nBy module:")
            for module, count in summary['by_module'].items():
                print(f"  {module}: {count}")
            print("\nTop files by import count:")
            for item in summary['by_file'][:10]:
                print(f"  {item['file']}: {item['count']}")

    # Default: print summary
    summary = get_migration_summary(args.root)
    print(json.dumps(summary, indent=2))
