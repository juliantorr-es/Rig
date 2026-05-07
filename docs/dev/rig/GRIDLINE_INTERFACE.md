# Gridline Interface

Gridline Interface is Rig's grid-based TUI language for governed local AI control planes.

## Principles

- CSS grid owns the macro dashboard geometry.
- Typed Python containers own semantic regions.
- Reactive widgets own local display state.
- Native `BINDINGS` and `Footer` expose shortcuts.
- Color is semantic, not decorative.
- The TUI is a projection and control surface, not a mutation engine.

## Layout Model

Use a hybrid model:

- `layout: grid`
- named regions for sidebar, main column, evidence rail, and chat
- typed containers for semantic composition
- no anonymous layout soup

## Status Rules

- Red is for blocked, failed, or dangerous states.
- Green is for safe success or eligibility.
- Yellow is for pending, warning, or review-needed states.
- Blue and gray are informational.
- Labels and markers must carry meaning independent of color.

## Boundaries

- The TUI must not mutate jobs, workspaces, providers, or receipts during render.
- Chat captures intent.
- Slash commands map to canonical CLI commands.
- Natural language creates governed proposals, not direct execution.

## Naming

- Canonical product naming is `Gridline Interface`.
- Do not use "Bauhaus Macintosh Console" as product naming.
