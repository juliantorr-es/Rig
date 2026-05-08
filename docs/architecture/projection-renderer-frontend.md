# Projection Renderer Frontend

## Purpose

Rig's static frontend is a browser-native projection renderer. It consumes backend-authored `UIProjection` payloads, renders them with ES modules, and emits backend-defined intentions. It is not authoritative.

## Doctrine

- Backend authors state.
- Frontend renders state.
- Frontend emits intentions only.
- Frontend does not infer governance.
- Frontend does not mutate Git.
- Frontend does not construct command strings.
- Frontend does not decide checkpointability.
- Frontend does not select files.
- Frontend does not compute branch-convention status.

## Module Layout

The frontend is split into static browser modules:

```text
src/rig_tools/static/
  index.html
  js/
    main.js
    app/
      boot.js
      runtime.js  # compatibility/orchestration shim only
      websocket.js
      projection-store.js
      progress-store.js
      intent-dispatch.js
      render-root.js
      logging.js
    widgets/
      registry.js
      empty-state-card.js
      validator-stack.js
      receipt-list.js
      backend-status.js
      log-stream.js
      command-progress-card.js
      workspace-header.js
      workspace-git-state.js
      workspace-lane-summary.js
      proposal-lifecycle-console.js
      integrity-status-card.js
    components/
      dom.js
      badges.js
      buttons.js
      cards.js
      lists.js
    utils/
      escape.js
    ...
  css/
    main.css
    layers.css
    tokens.css
    base.css
    layout.css
    widgets.css
    states.css
    utilities.css
```

`index.html` loads `js/main.js` with `type="module"` and links `css/main.css`.

`rig-ui.js` is retained only as a compatibility shim so older tests or callers can still import the legacy path.

`main.js` is the browser entrypoint. `runtime.js` now exists only as a tiny orchestration shim for legacy import paths.

## Widget Registry

Widget renderers are frontend plugins for backend-authored widget types.

Current workspace-oriented widget types:

- `WorkspaceHeader`
- `WorkspaceGitState`
- `WorkspaceLaneSummary`
- `ProposalLifecycleConsole` - renders enriched lifecycle data from `workspace.proposal_lifecycle` projection

Existing UI widget types remain supported:

- `EmptyStateCard`
- `ValidatorStack`
- `ReceiptList`
- `BackendStatus`
- `MetricStack`
- `GateBadge`
- `AppTitle`
- `CommandProgressCard`
- `LogStream`

Widget renderers must:

- read the backend payload as-is
- degrade gracefully when optional fields are missing
- render `disabled_reason` values exactly as authored by the backend
- avoid inventing command strings or safety decisions

## Proposal Lifecycle Console Widget

The `ProposalLifecycleConsole` widget (`proposal-lifecycle-console.js`) renders the enriched `workspace.proposal_lifecycle` projection.

### Contract

The widget expects a projection payload containing:

| Field | Type | Description |
|---|---|---|
| `lifecycle_id` | str | Always "workspace.proposal_lifecycle" |
| `stage` | str | State-aware stage: "workspace_unselected", "workspace_ready", "gate_a_active", "recommendation_available", "proposal_pending", "validation_pending", "validation_passed", "validation_failed", "review_ready", "apply_blocked" |
| `title` | str | "Proposal Lifecycle Console" |
| `summary` | str | Human-readable summary of current state |
| `workspace_path` | Optional[str] | Workspace path when available |
| `current_gate` | str | Always "A" (Dogfood Gate A) |
| `next_safe_action` | str | State-aware next safe action message |
| `recommendation_state` | dict | RecommendationSummary with status, title, summary, source_surface, files, last_updated, next_action |
| `proposal_state` | dict | ProposalSummary with status, title, summary, worktree_path, changed_files, next_action |
| `validation_state` | dict | ValidationSummary with status, title, summary, surface, command, passed_count, failed_count, last_run_at, proof_status, next_action |
| `progress_state` | dict | Always has transient=true, source="progress_event" |
| `auditability_state` | dict | Always has progress_receipts="not_created", progress_receipt_plan="advisory_only", receipt_candidate="inert", evidence_refs="inert" |
| `allowed_actions` | tuple | Gate A allowed actions |
| `blocked_actions` | tuple | Gate A blocked actions (including apply_patch) |
| `warnings` | tuple[str] | Includes "Progress telemetry is transient", "Apply remains blocked under Dogfood Gate A", etc. |

### Rendering

The widget renders:
- Title from payload
- Stage badge with state-aware severity
- Summary text
- Gate, workspace path, next safe action header line
- Blocked apply note: "Apply remains blocked under Dogfood Gate A."
- Recommendation state section with all fields
- Proposal state section with all fields
- Validation state section with all fields (including proof_status="not_proof")
- Progress/auditability note
- Allowed actions list
- Blocked actions list
- Warnings

### Dumb Widget Contract

The `ProposalLifecycleConsole` widget is **dumb**:
- Renders projection data only
- No fetching
- No authority logic
- No local persistence
- No inference from frontend progress-store
- Missing fields render empty or "Unknown"
- Empty arrays render boring empty states

## WebSocket and Progress

The frontend keeps the existing WebSocket-based projection/intent loop.

- projections are backend-authored snapshots
- `progress_event` messages are live telemetry
- receipts and refreshed projections are durable authority
- the frontend retains a bounded in-memory progress buffer
- progress events are grouped by `operation_id`
- progress events are ordered by `sequence` and `timestamp`
- `CommandProgressCard` renders backend-authored progress payloads only
- `workspace.command_progress` is the projection-declared lane for transient command telemetry
- progress cards remain transient UI and must not imply evidence, proof, or receipt authority
- `ProposalLifecycleConsole` is a backend-declared region for the proposal lifecycle skeleton, including Gate A, transient progress, recommendation state, and validation state

Future progress events can be added without changing the doctrine.

## Workspace and Lane UI

Workspace and Agent Lane widgets share the same renderer model. The backend may project workspace-level placeholders today and lane widgets later without changing the frontend authority model.

Current workspace placeholder widgets:

- `WorkspaceHeader`
- `WorkspaceGitState`
- `WorkspaceLaneSummary`

These placeholders are honest about the current state:

- the workspace control plane exists as a contract
- the full workspace runtime is future work
- lane data is not connected yet

## Styling

CSS is layered so tokens, layout, widget chrome, and state styling can evolve independently without a bundler.

The browser should load:

- `css/main.css`

which imports the layered CSS files.

## Future Work

- richer widget surfaces
- progress-card projections
- workspace/lane registry-backed projections
- receipts timeline widgets
- promotion planning cards

These remain future work until the backend actually emits them.
