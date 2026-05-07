# Projection Renderer Frontend

## Purpose

Rig’s static frontend is a browser-native projection renderer. It consumes backend-authored `UIProjection` payloads, renders them with ES modules, and emits backend-defined intentions. It is not authoritative.

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
      workspace-header.js
      workspace-git-state.js
      workspace-lane-summary.js
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

Existing UI widget types remain supported:

- `EmptyStateCard`
- `ValidatorStack`
- `ReceiptList`
- `BackendStatus`
- `MetricStack`
- `GateBadge`
- `AppTitle`

Widget renderers must:

- read the backend payload as-is
- degrade gracefully when optional fields are missing
- render `disabled_reason` values exactly as authored by the backend
- avoid inventing command strings or safety decisions

## WebSocket and Progress

The frontend keeps the existing WebSocket-based projection/intent loop.

- projections are backend-authored snapshots
- stream events are live telemetry
- receipts and refreshed projections are durable authority

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
