from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shlex
import re

DIAG_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+)(?::(?P<column>\d+))?: (?P<kind>error|warning|note): (?P<message>.*)$"
)
FILE_HINT_RE = re.compile(r"'([^']+)'")

SUGGESTIONS = {
    "ambiguous_init": "Check initializer overloads and module imports before changing the call site.",
    "missing_type": "Verify target dependencies and imports before adding a broader fix.",
    "missing_import": "Add the narrowest import or dependency that resolves the symbol without widening the tier boundary.",
    "access_control": "Check the symbol's visibility and avoid widening access unless the contract requires it.",
    "concurrency_sendable": "Prefer immutable value types, actor isolation, or explicit synchronization before silencing Sendable warnings.",
    "actor_isolation": "Keep the access within the correct actor boundary or move the operation to the owning actor.",
    "mainactor_misuse": "Keep daemon/runtime services off MainActor unless the code is truly UI-bound.",
    "deprecated_api": "Prefer the documented replacement and verify availability constraints.",
    "unused_import": "Remove the import unless it exists for a documented conditional or side-effect reason.",
    "unused_variable": "Remove the variable or prefix intentionally unused bindings with an underscore.",
    "type_mismatch": "Check the expected type boundary before inserting a coercion.",
    "package_manifest": "Inspect Package.swift and product membership before changing dependencies.",
    "module_cycle": "Break the cycle by extracting a contract or moving the dependency direction downward.",
    "linker_error": "Check product membership, library availability, and native sidecar linkage.",
    "native_dependency_missing": "Verify the missing file or framework exists and is included in the correct target.",
    "test_failure": "Inspect the failing assertion and its setup before changing production code.",
    "unknown": "Inspect the source and compiler context before patching.",
}


@dataclass
class SwiftDiagnostic:
    severity: str
    category: str
    file: str
    line: int
    column: int
    message: str
    symbol: str| Optional = None
    target: str| Optional = None
    known_blocker_id: str| Optional = None
    suggested_review: str| Optional = None
    raw_line: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_known_blockers(path: Path) -> list[dict]:
    blockers: list[dict] = []
    current: dict| Optional = None
    current_list_key: str| Optional = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "blockers:":
            continue
        if stripped.startswith("- id:"):
            if current is not None:
                blockers.append(current)
            current = {"signature": [], "unrelated_to": []}
            current["id"] = stripped.split(":", 1)[1].strip()
            current_list_key = None
            continue
        if current is None:
            continue
        if stripped.startswith("- ") and current_list_key:
            current.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                current[key] = value
                current_list_key = None
            else:
                current.setdefault(key, [])
                current_list_key = key

    if current is not None:
        blockers.append(current)
    return blockers


def match_known_blocker(command_text: str, text: str, blockers: list[dict]) -> dict| Optional:
    command_lower = command_text.lower()
    text_lower = text.lower()
    command_tokens = shlex.split(command_lower)
    for blocker in blockers:
        status = str(blocker.get("status", "")).lower()
        if status and status not in {"open", "active"}:
            continue
        blocker_command = str(blocker.get("command", "")).lower()
        blocker_tokens = shlex.split(blocker_command)
        signatures = [str(item).lower() for item in blocker.get("signature", [])]
        if blocker_command and blocker_command in command_lower:
            return blocker
        if blocker_tokens and _is_subsequence(blocker_tokens, command_tokens):
            return blocker
        if signatures and all(sig in text_lower for sig in signatures):
            return blocker
    return None


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    if not needle:
        return False
    it = iter(haystack)
    for token in needle:
        for current in it:
            if current == token:
                break
        else:
            return False
    return True


def infer_symbol(message: str) -> str| Optional:
    for match in FILE_HINT_RE.finditer(message):
        value = match.group(1)
        if value and value[0].isupper() or value in {"init", "self", "actor", "MainActor"}:
            return value
    return None


def classify_message(severity: str, message: str) -> str:
    msg = message.lower()
    if "ambiguous use" in msg or ("ambiguous" in msg and "init" in msg):
        return "ambiguous_init"
    if "package.swift" in msg or "package manifest" in msg or "manifest" in msg:
        return "package_manifest"
    if "cannot find type" in msg or "type '" in msg and "not found in scope" in msg:
        return "missing_type"
    if "no such module" in msg or "could not build module" in msg and "no such module" in msg:
        return "missing_import"
    if "missing required module" in msg or "could not find module" in msg:
        return "missing_import"
    if "inaccessible due to" in msg or "private protection level" in msg or "internal protection level" in msg:
        return "access_control"
    if "sendable" in msg:
        return "concurrency_sendable"
    if "main actor" in msg or "mainactor" in msg:
        return "mainactor_misuse"
    if "actor-isolated" in msg or "actor isolation" in msg:
        return "actor_isolation"
    if "deprecated" in msg or "obsoleted" in msg:
        return "deprecated_api"
    if "unused import" in msg:
        return "unused_import"
    if "unused variable" in msg or "unused immutable value" in msg or "was never used" in msg or "defined but never used" in msg or "will never be executed" in msg:
        return "unused_variable"
    if "cannot convert" in msg or "cannot assign value of type" in msg:
        return "type_mismatch"
    if "cyclic dependency" in msg or "module cycle" in msg or "circular dependency" in msg:
        return "module_cycle"
    if "undefined symbols" in msg or "symbol(s) not found" in msg or "ld: library not found" in msg or "linker command failed" in msg:
        return "linker_error"
    if "framework not found" in msg or "library not found" in msg or "no such file or directory" in msg:
        return "native_dependency_missing"
    if "test failed" in msg or "xctest" in msg or "no tests found" in msg:
        return "test_failure"
    return "unknown"


def suggestion_for(category: str) -> str:
    return SUGGESTIONS.get(category, SUGGESTIONS["unknown"])


def parse_diagnostic_line(line: str, target: str| Optional = None) -> SwiftDiagnostic| Optional:
    stripped = line.rstrip()
    if not stripped:
        return None

    match = DIAG_RE.match(stripped)
    if match:
        file = match.group("file")
        line_no = int(match.group("line"))
        column = int(match.group("column") or 0)
        severity = match.group("kind")
        message = match.group("message")
        category = classify_message(severity, message)
        return SwiftDiagnostic(
            severity=severity,
            category=category,
            file=file,
            line=line_no,
            column=column,
            message=message,
            symbol=infer_symbol(message),
            target=target,
            suggested_review=suggestion_for(category),
            raw_line=stripped,
        )

    lower = stripped.lower()
    if stripped.startswith("error: ") or stripped.startswith("warning: ") or stripped.startswith("note: "):
        severity = stripped.split(":", 1)[0]
        message = stripped.split(": ", 1)[1] if ": " in stripped else stripped
        category = classify_message(severity, message)
        return SwiftDiagnostic(
            severity=severity,
            category=category,
            file="unknown",
            line=0,
            column=0,
            message=message,
            symbol=infer_symbol(message),
            target=target,
            suggested_review=suggestion_for(category),
            raw_line=stripped,
        )
    if "undefined symbols" in lower or "symbol(s) not found" in lower or lower.startswith("ld: library not found"):
        category = "linker_error" if "symbol" in lower else "native_dependency_missing"
        return SwiftDiagnostic(
            severity="error",
            category=category,
            file="unknown",
            line=0,
            column=0,
            message=stripped,
            symbol=infer_symbol(stripped),
            target=target,
            suggested_review=suggestion_for(category),
            raw_line=stripped,
        )
    if "test case" in lower and "failed" in lower:
        category = "test_failure"
        return SwiftDiagnostic(
            severity="error",
            category=category,
            file="unknown",
            line=0,
            column=0,
            message=stripped,
            symbol=infer_symbol(stripped),
            target=target,
            suggested_review=suggestion_for(category),
            raw_line=stripped,
        )
    if "package.swift" in lower and ("error" in lower or "manifest" in lower):
        category = "package_manifest"
        return SwiftDiagnostic(
            severity="error",
            category=category,
            file="Package.swift",
            line=0,
            column=0,
            message=stripped,
            symbol=infer_symbol(stripped),
            target=target,
            suggested_review=suggestion_for(category),
            raw_line=stripped,
        )
    return None


def parse_swift_log_text(
    text: str,
    *,
    command: str| Optional = None,
    target: str| Optional = None,
    known_blockers: list[dict]| Optional = None,
) -> list[dict]:
    diagnostics: list[SwiftDiagnostic] = []
    blockers = known_blockers or []
    seen: set[tuple] = set()
    for raw_line in text.splitlines():
        diag = parse_diagnostic_line(raw_line, target=target)
        if diag is None:
            continue
        blocker = match_known_blocker(command or "", text, blockers) if blockers else None
        if blocker is not None:
            diag.known_blocker_id = str(blocker.get("id"))
        key = (diag.severity, diag.category, diag.file, diag.line, diag.column, diag.message, diag.known_blocker_id, diag.target)
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(diag)
    diagnostics.sort(key=lambda item: (item.file, item.line, item.column, item.category, item.message))
    return [item.to_dict() for item in diagnostics]


def summarize_diagnostics(diagnostics: list[dict]) -> dict:
    summary = {
        "total": len(diagnostics),
        "errors": 0,
        "warnings": 0,
        "notes": 0,
        "categories": {},
        "known_blockers": sorted(
            {diag["known_blocker_id"] for diag in diagnostics if diag.get("known_blocker_id")}
        ),
    }
    for diag in diagnostics:
        severity = diag.get("severity", "unknown")
        summary[severity + "s" if not severity.endswith("s") else severity] = summary.get(severity + "s", 0) + 1
        category = diag.get("category", "unknown")
        summary["categories"][category] = summary["categories"].get(category, 0) + 1
    return summary


def render_markdown_report(payload: dict) -> str:
    diagnostics = payload.get("diagnostics", [])
    summary = payload.get("summary", {})
    lines = [
        "# Rig Swift Diagnostics",
        "",
        f"- Run label: `{payload.get('run_label', 'swift-diagnostics')}`",
        f"- Command: `{ ' '.join(payload.get('command', [])) }`",
        f"- Target: `{payload.get('target') or 'n/a'}`",
        f"- Exit code: `{payload.get('exit_code')}`",
        f"- Status: `{payload.get('status')}`",
    ]
    if payload.get("tool_missing"):
        lines.append(f"- Tool missing: `{payload['tool_missing']}`")
    if payload.get("recommendation"):
        lines.append(f"- Recommendation: {payload['recommendation']}")
    lines.extend(
        [
            "",
            "## Summary",
            f"- Total diagnostics: `{summary.get('total', 0)}`",
            f"- Errors: `{summary.get('errors', 0)}`",
            f"- Warnings: `{summary.get('warnings', 0)}`",
            f"- Notes: `{summary.get('notes', 0)}`",
        ]
    )
    if summary.get("known_blockers"):
        lines.append(f"- Known blockers: `{', '.join(summary['known_blockers'])}`")
    if summary.get("categories"):
        lines.extend(["", "## Categories"])
        for category, count in sorted(summary["categories"].items()):
            lines.append(f"- `{category}`: `{count}`")
    if diagnostics:
        lines.extend(["", "## Diagnostics", "", "| Severity | Category | File | Line | Column | Message | Known Blocker |", "| --- | --- | --- | ---: | ---: | --- | --- |"])
        for diag in diagnostics:
            lines.append(
                "| {severity} | {category} | {file} | {line} | {column} | {message} | {known_blocker} |".format(
                    severity=diag.get("severity", ""),
                    category=diag.get("category", ""),
                    file=diag.get("file", ""),
                    line=diag.get("line", 0),
                    column=diag.get("column", 0),
                    message=diag.get("message", "").replace("|", "\\|"),
                    known_blocker=diag.get("known_blocker_id") or "",
                )
            )
    return "\n".join(lines) + "\n"
