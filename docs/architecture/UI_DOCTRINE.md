# Rig UI Doctrine

## Overview

Rig is a repository-local developer control plane. It provides two primary user surfaces designed for different workflows:

1. **CLI (Command Line Interface)**: Scriptable, deterministic, and automation-friendly terminal interface for standard dev-ops and repo management.
2. **Windowed WebSocket UI**: A rich, streaming, inspectable interface for complex control-plane operations including agent chat, streaming logs, validator inspection, and governance gates.

## Core Decisions

- **CLI-First Automation**: The terminal is reserved for deterministic CLI commands. It should not be forced into a complex "dashboard" mode.
- **WebSocket Window for Rich Interaction**: Rich inspection and interactive governance belong in the windowed UI, which uses a local webview to render a consistent experience across platforms.
- **Textual TUI Deprecation**: The legacy Textual-based terminal TUI is retired. It is no longer a primary product surface.

## Architectural Doctrine

- **Backend-Authoritative**: Rig's frontend is not authoritative. It is a renderer for domain-driven state.
- **Projections as Truth**: The backend authors `UIProjection` snapshots. The frontend renders these snapshots. Streams are for progress narration only; the full projection remains the source of truth.
- **Intention-Driven Action**: The frontend submits user intentions (e.g., `intent.apply_patch`) over WebSocket. The backend explicitly accepts or rejects these based on the **Governance Engine**.
- **Explicit Legality**: All action states (enabled/disabled) are authored by the backend. The frontend must not infer safety, gate readiness, or apply legality. Disabled actions must include a `disabled_reason` authored by the backend.

## Design Doctrine

- **Consistency over Native Imitation**: Rig does not imitate platform-native UI controls (macOS/Windows/Linux). It uses a consistent, cross-platform design language rendered via HTML/CSS/JS.
- **Operational Aesthetics**: The interface is text-first, evidence-first, and grid-based. Visual richness comes from semantic widgets, progressive disclosure, and live evidence, not decorative elements.
- **Precision and Trust**: The UI should feel like a cockpit for repository governance—precise, operational, and trustworthy.

## Implementation Contract

- **pywebview Shell**: Used only as the native window container.
- **WebSocket Transport**: Carries structured Projection and Intention messages.
- **Frontend Independence**: The frontend must remain a "dumb" renderer of projections and a solicitor of intentions.
