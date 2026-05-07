# Projection-backed UI Architecture

## Overview

Rig follows a **Unidirectional Data Flow** pattern for its user interfaces (both the Textual TUI and the WebSocket-based Web UI). The goal is to move complex state orchestration and governance logic out of the UI components and into the domain layer.

The UI should be a **renderer/transport adapter** that consumes **Projections** and emits **Intentions**.

## Core Concepts

### 1. Projection
A `UIProjection` is a read-only, point-in-time snapshot of the domain state, transformed specifically for UI display. It includes:
- **Widgets:** Specialized views (e.g., `ValidatorStack`, `AppTitle`) containing pre-processed data.
- **Intents:** Available actions the user can perform (e.g., `intent.run_validators`), including their `enabled` status and `disabled_reason` (authored by the **Governance Engine**).
- **Layout:** Instructions on how to arrange widgets in regions (Header, Sidebar, Main, etc.).

### 2. Intention
An intention is a structured request from the UI to perform an action.
- The UI does not execute logic; it "intends" to perform an operation.
- The backend receives the intention, validates it against the **Governance Engine**, and dispatches it to the appropriate domain service.

## Architectural Benefits

### 1. Single Authority
By authoring intent states (enabled/disabled) in the backend via the Governance Engine, we ensure that UI buttons are only enabled when the action is legally permissible.

### 2. Shared State
Both the Textual TUI and the Web UI consume the same projections. This ensures visual and behavioral consistency across all interfaces.

### 3. Decoupling
The UI components (e.g., `tui_app.py`) become "dumb" renderers. They don't need to know about the filesystem, Git worktrees, or complex validator logic. They simply render the widgets and intents provided in the projection.

## Implementation Pattern

### Backend: Projection Builder
The `ProjectionBuilder` is responsible for:
- Loading domain state (Workspaces, Proposals, Evidence).
- Calling the `GovernanceEngine` to determine action legality.
- Assembling the `UIProjection` object.

### Frontend: Renderer
The UI (Textual or Web) is responsible for:
- Connecting to the WebSocket/Server.
- Receiving the `UIProjection`.
- Mapping widget types to UI components.
- Mapping UI events (clicks, keypresses) to intentions.

## Future Evolution

As the system matures, the `tui_app.py` module (currently ~1,700 lines) will be refactored into a **Projection-backed TUI Adapter**. Its primary role will be to translate the generic `UIProjection` into Textual-specific widgets and layouts, drastically reducing its internal complexity and improving **locality** of UI rendering logic.
