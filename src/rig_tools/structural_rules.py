from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

class StructuralRule:
    def __init__(self, rule_id: str, language: str, severity: str, message: str):
        self.rule_id = rule_id
        self.language = language
        self.severity = severity
        self.message = message

    def scan(self, path: Path, content: str) -> List[Dict[str, Any]]:
        return []

# --- Python AST Rules ---

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.findings: List[Dict[str, Any]] = []

    def _add_finding(self, node: ast.AST, rule_id: str, severity: str, message: str, confidence: str = "high"):
        self.findings.append({
            "schema_version": "1.0.0",
            "finding_id": f"find-{self.path.name}-{node.lineno}",
            "engine": "python_ast",
            "language": "python",
            "rule_id": rule_id,
            "severity": severity,
            "path": str(self.path),
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "start_column": node.col_offset,
            "end_column": getattr(node, "end_col_offset", node.col_offset),
            "message": message,
            "confidence": confidence,
            "authoritative": False
        })

class PythonShellTrueRule(PythonASTVisitor):
    def visit_Call(self, node: ast.Call):
        # Detect subprocess.*(..., shell=True)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self._add_finding(node, "python.no_shell_true", "error", "subprocess call with shell=True detected")
        self.generic_visit(node)

class PythonEvalExecRule(PythonASTVisitor):
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            self._add_finding(node, "python.no_eval_exec", "critical", f"Use of {node.func.id}(...) detected")
        self.generic_visit(node)

class PythonBroadExceptPassRule(PythonASTVisitor):
    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Detect except Exception: pass or except: pass
        is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
        if is_broad:
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self._add_finding(node, "python.broad_except_pass", "warning", "Broad except block with 'pass' detected")
        self.generic_visit(node)

# --- Swift Line-based Rules ---

class SwiftImportScanner:
    FORBIDDEN_CONTRACT_IMPORTS = {
        "AVFoundation", "CoreVideo", "CoreMedia", "CoreImage", "Metal", "MetalKit", 
        "VideoToolbox", "AudioToolbox", "Security", "UniformTypeIdentifiers", "AppKit", "SwiftUI"
    }

    def __init__(self, path: Path):
        self.path = path
        self.findings: List[Dict[str, Any]] = []

    def scan(self, content: str):
        lines = content.splitlines()
        is_contract_tier = "Contract" in str(self.path) or "Protocol" in str(self.path)
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            # 1. Forbidden imports in contract tier
            if is_contract_tier and line.startswith("import "):
                module = line.split("import ")[1].split()[0].strip(";")
                if module in self.FORBIDDEN_CONTRACT_IMPORTS:
                    self._add_finding(i, "swift.forbidden_native_import_in_contract_tier", "error", f"Forbidden native import '{module}' in contract tier")

            # 2. @_exported import guard
            if "@_exported import" in line:
                self._add_finding(i, "swift.exported_import_guard", "warning", "@_exported import detected; ensure it follows governance allowlist")

    def _add_finding(self, line_no: int, rule_id: str, severity: str, message: str):
        self.findings.append({
            "schema_version": "1.0.0",
            "finding_id": f"find-{self.path.name}-{line_no}",
            "engine": "textual_import_scan",
            "language": "swift",
            "rule_id": rule_id,
            "severity": severity,
            "path": str(self.path),
            "start_line": line_no,
            "message": message,
            "confidence": "high",
            "authoritative": False
        })

# --- Rust Line-based Rules ---

class RustInventoryScanner:
    def __init__(self, path: Path):
        self.path = path
        self.findings: List[Dict[str, Any]] = []

    def scan(self, content: str):
        lines = content.splitlines()
        in_test = "test" in self.path.name.lower()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if "unsafe {" in line:
                self._add_finding(i, "rust.unsafe_block_inventory", "info", "Unsafe block detected")
            
            if not in_test:
                if ".unwrap()" in line or ".expect(" in line:
                    self._add_finding(i, "rust.unwrap_expect_inventory", "warning", ".unwrap() or .expect() detected outside tests")

    def _add_finding(self, line_no: int, rule_id: str, severity: str, message: str):
        self.findings.append({
            "schema_version": "1.0.0",
            "finding_id": f"find-{self.path.name}-{line_no}",
            "engine": "textual_inventory_scan",
            "language": "rust",
            "rule_id": rule_id,
            "severity": severity,
            "path": str(self.path),
            "start_line": line_no,
            "message": message,
            "confidence": "medium",
            "authoritative": False
        })
