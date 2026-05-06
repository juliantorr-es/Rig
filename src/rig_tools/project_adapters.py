from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BUILTIN_ADAPTERS = [
    {
        "schema_version": "1.0.0",
        "adapter_id": "generic",
        "display_name": "Generic Project",
        "description": "Safe default adapter for any project repo.",
        "detectors": [".git", "README.md"],
        "source_patterns": ["src/**", "lib/**"],
        "test_patterns": ["tests/**", "test/**"],
        "docs_patterns": ["Docs/**", "docs/**", "README.md", "*.md"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "docs",
        "display_name": "Documentation Focus",
        "description": "Specialized adapter for documentation-heavy repositories.",
        "detectors": ["Docs/", "docs/", "README.md", "*.md"],
        "docs_patterns": ["Docs/**", "docs/**", "README.md", "*.md"],
        "validator_rules": ["duplicate_docs", "archive_plan", "generated_markers", "broken_links"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "python-cli",
        "display_name": "Python CLI",
        "description": "Standard Python project with CLI focus.",
        "detectors": ["pyproject.toml", "setup.py", "requirements.txt", "*.py"],
        "source_patterns": ["src/**", "scripts/**", "*.py"],
        "test_patterns": ["tests/**", "test_*.py"],
        "build_commands": [["python", "-m", "build"]],
        "test_commands": [["pytest"], ["python", "-m", "unittest"]],
        "lint_commands": [["ruff", "check", "."], ["flake8"]],
        "validator_rules": ["entry_points", "shell_true_scan", "hardcoded_paths", "python.no_shell_true", "python.no_eval_exec", "python.broad_except_pass"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "swift",
        "display_name": "Swift/macOS",
        "description": "Specialized adapter for Swift packages and Xcode projects.",
        "detectors": ["Package.swift", "*.xcodeproj", "*.xcworkspace", "Sources/", "*.swift"],
        "source_patterns": ["Sources/**", "*.swift"],
        "test_patterns": ["Tests/**", "*Tests.swift"],
        "build_commands": [["swift", "build"]],
        "test_commands": [["swift", "test"]],
        "validator_rules": ["package_graph", "import_boundaries", "native_framework_leakage", "swift.forbidden_native_import_in_contract_tier", "swift.exported_import_guard"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "rust",
        "display_name": "Rust",
        "description": "Standard Rust project using Cargo.",
        "detectors": ["Cargo.toml", "Cargo.lock", "src/", "*.rs"],
        "source_patterns": ["src/**", "*.rs"],
        "test_patterns": ["tests/**"],
        "build_commands": [["cargo", "check"], ["cargo", "build"]],
        "test_commands": [["cargo", "test"]],
        "lint_commands": [["cargo", "clippy"]],
        "validator_rules": ["crate_graph", "unsafe_scan", "feature_flags", "rust.unsafe_block_inventory", "rust.unwrap_expect_inventory"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "cpp",
        "display_name": "C++",
        "description": "C++ project using CMake or Make.",
        "detectors": ["CMakeLists.txt", "Makefile", "meson.build", "*.cpp", "*.cc", "*.hpp"],
        "source_patterns": ["src/**", "include/**", "*.cpp", "*.cc", "*.hpp"],
        "test_patterns": ["tests/**", "test/**"],
        "build_commands": [["cmake", "--build", "."], ["make"]],
        "test_commands": [["ctest"], ["make", "test"]],
        "validator_rules": ["compile_commands_presence", "include_graph"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "c",
        "display_name": "C",
        "description": "C project using CMake or Make.",
        "detectors": ["Makefile", "CMakeLists.txt", "*.c", "*.h"],
        "source_patterns": ["src/**", "include/**", "*.c", "*.h"],
        "test_patterns": ["tests/**", "test/**"],
        "build_commands": [["make"], ["cmake", "--build", "."]],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "web",
        "display_name": "Web/Node.js",
        "description": "Web project using npm, yarn, or pnpm.",
        "detectors": ["package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock"],
        "source_patterns": ["src/**", "app/**", "pages/**"],
        "test_patterns": ["tests/**", "*.test.ts", "*.test.js"],
        "build_commands": [["npm", "run", "build"], ["pnpm", "build"], ["yarn", "build"]],
        "test_commands": [["npm", "test"], ["pnpm", "test"], ["yarn", "test"]],
        "lint_commands": [["npm", "run", "lint"], ["pnpm", "lint"], ["yarn", "lint"]],
        "validator_rules": ["lockfile_consistency", "secrets_scan", "build_dir_protection"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "java",
        "display_name": "Java",
        "description": "Java project using Maven or Gradle.",
        "detectors": ["pom.xml", "build.gradle", "src/main/java"],
        "source_patterns": ["src/main/java/**"],
        "test_patterns": ["src/test/java/**"],
        "build_commands": [["mvn", "compile"], ["./gradlew", "classes"]],
        "test_commands": [["mvn", "test"], ["./gradlew", "test"]],
        "validator_rules": ["dependency_scope", "test_roots"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "kotlin",
        "display_name": "Kotlin",
        "description": "Kotlin project using Gradle.",
        "detectors": ["build.gradle.kts", "src/main/kotlin"],
        "source_patterns": ["src/main/kotlin/**"],
        "test_patterns": ["src/test/kotlin/**"],
        "build_commands": [["./gradlew", "classes"]],
        "test_commands": [["./gradlew", "test"]],
        "validator_rules": ["module_summary"],
        "authoritative": True
    },
    {
        "schema_version": "1.0.0",
        "adapter_id": "anigma",
        "display_name": "Anigma",
        "description": "Full Anigma governance and Swift/Python specialized adapter.",
        "detectors": ["Scripts/anigma_architecture_sentinel.py", "Docs/dev/anigma/"],
        "validator_rules": ["anigma_sentinel", "governance_audit", "tier_discipline"],
        "authoritative": True,
        "inherits": ["swift", "python-cli", "docs"]
    }
]

def list_adapters() -> List[Dict[str, Any]]:
    return BUILTIN_ADAPTERS

def get_adapter(adapter_id: str) -> Optional[Dict[str, Any]]:
    return next((a for a in BUILTIN_ADAPTERS if a["adapter_id"] == adapter_id), None)

def get_effective_adapter(adapter_id: str) -> Dict[str, Any]:
    base = get_adapter(adapter_id)
    if not base:
        return {}
    
    effective = base.copy()
    if "inherits" in base:
        for parent_id in base["inherits"]:
            parent = get_effective_adapter(parent_id)
            # Merge patterns
            for key in ["source_patterns", "test_patterns", "docs_patterns", "validator_rules", "doctor_checks"]:
                if key in parent:
                    effective[key] = sorted(list(set(effective.get(key, []) + parent[key])))
            # Merge commands
            for key in ["build_commands", "test_commands", "lint_commands"]:
                if key in parent:
                    effective[key] = effective.get(key, []) + parent[key]
    
    return effective
