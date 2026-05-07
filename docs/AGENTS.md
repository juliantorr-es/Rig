# Agent Rules & Architectural Doctrine

This document provides the mandatory ground rules for all Rig contributors and AI agents.

## UI Strategy

- **CLI-First**: Terminal is for scriptable, deterministic tasks (`rig status`, `rig run`). It is NOT for rich dashboards.
- **Windowed UI**: A rich, WebSocket-backed control plane for inspection, chat, and governance.
- **Textual TUI**: **DEPRECATED**. Use `rig ui` for rich interfaces.
- **Frontend Independence**: The frontend is a "dumb" renderer. It MUST NOT infer repo safety, gate readiness, or validator success.
- **Truth is backend-authored**:
    - **Projections** are the source of truth for the UI.
    - **Intentions** are the UI's requested actions, authorized by the backend **Governance Engine**.
    - If the backend blocks an action, the UI must display the backend-authored `disabled_reason`.

## Governance & Security

- **Governance Engine**: All action legality checks (e.g., "Can I apply this?") must go through the Governance Engine.
- **Deny-by-default**: All intents are blocked unless explicitly allowed.
- **Execution Safety**: Execution occurs in isolated Git worktrees. Treat every execution as a transaction; emit a persistent receipt.
- **Threat Model**: Malicious repository content, untrusted model output, and compromised local clients are assumed. Never execute anything without a durable receipt and policy gate.

## Packaging & Dependencies

- **Base Install**: Must remain lightweight.
- **Optional Extras**: Heavy dependencies (ML, legacy TUI) must be moved to `[project.optional-dependencies]`.
- **Static Assets**: Frontend assets are part of the Python package data.

## Coding Standards

- **Do Not Duplicate**: Logic should exist only in the domain layer. UI transport modules should not contain business logic.
- **Asyncio**: Use strict `aiohttp` WebSocket patterns with graceful `on_shutdown` connection tracking.
- **Thread Safety**: Use `loop.call_soon_threadsafe()` when interacting with async UI loops from background tasks.
- **CLI Conventions**: Use `--json` output for automation, stable command naming, and proper exit codes (0=Success, 1=Error/Blocked).
- **Hardening**: New interfaces must pass hardening tests (e.g., origin checks, intent validation, token authorization).
