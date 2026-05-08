# Proposal Lifecycle Console Sprint

## Sprint Status

**COMPLETE**: Lifecycle enrichment slice implemented on top of `WorkspaceStatusSummary` substrate.

Workspace substrate layer: `WorkspaceStatusSummary` provides canonical read-only workspace identity/path/state.
Lifecycle enrichment layer: `ProposalLifecycleProjection` with normalized `RecommendationSummary`, `ProposalSummary`, `ValidationSummary` models built from `WorkspaceStatusSummary`.
The workspace projection includes a backend-authored `ProposalLifecycleConsole` region with Gate A, transient progress, auditability notes, and enriched state-aware rendering.

## Sprint Name

Proposal Lifecycle Console

## Sprint Goal

Make Rig UI usable enough that a human can understand an agent handoff from the workspace surface without leaving the control plane. The workspace substrate comes first: workspace selection and status, Dogfood Gate A, progress, recommendation/proposal context, validation summary, and next safe action all need to be visible in one coherent console.

## Product Increment

At the end of the sprint, the operator should be able to:

1. select a workspace
2. see workspace status and Gate A
3. see the workspace substrate reflected truthfully in the proposal lifecycle console
4. see transient progress
5. see a recommendation/proposal summary
6. see a validation summary
7. see the next safe action

This increment remains UI/projection-led. Auditability is future-compatible, not fully complete.

## Definition of Done

The sprint is done when:

- the workspace control plane is the obvious entry point
- workspace substrate is canonical and visible
- Gate A is visible in CLI, projection, and UI
- progress is visible but still transient
- recommendation/proposal context is visible
- validation summary is visible
- the next safe action is visible
- docs explain the control-plane and dogfood flow
- the frontend remains dumb and backend-authored
- no durable progress storage is introduced
- no receipt authority is invented for progress

## In Scope

- WorkspaceStatusSummary canonical read-only substrate (implemented in baseline)
- ProposalLifecycleProjection domain model with normalized summary models
- State-aware stage resolution (workspace_unselected, gate_a_active, recommendation_available, proposal_pending, validation_pending, validation_passed, validation_failed, review_ready, apply_blocked)
- State-aware next_safe_action resolution
- projection builder integration
- ProposalLifecycleConsole UI widget with enriched rendering
- Dogfood Gate A visible in CLI, projection, and UI
- validation summary projection
- proposal/recommendation lifecycle surface
- progress timeline usability
- frontend usability pass
- docs and handoff guidance

## Out of Scope

- durable progress receipts
- progress persistence
- replay
- event store or queue machinery
- apply-to-main execution
- automatic PR creation
- provider/OAuth sync
- GitHub/Google provider integrations
- full workspace runtime implementation

## Implementation Summary (Lifecycle Enrichment Slice)

### Backend/Domain (`src/rig/domain/proposal_lifecycle.py`)

Added normalized lifecycle summary models:

**`RecommendationSummary`** dataclass:
- `status`: "unknown", "unavailable", "available"
- `title`, `summary`: human-readable state
- `source_surface`: surface identifier (e.g., "workspace.recommend")
- `files`: tuple of related files
- `last_updated`: timestamp
- `next_action`: state-specific next action

**`ProposalSummary`** dataclass:
- `status`: "not_created", "unknown", "review_ready", etc.
- `title`, `summary`: human-readable state
- `worktree_path`: workspace path
- `changed_files`: tuple of changed files
- `next_action`: state-specific next action

**`ValidationSummary`** dataclass:
- `status`: "not_run", "unknown", "passed", "failed"
- `title`, `summary`: human-readable state
- `surface`: surface identifier (e.g., "workspace.validation_result")
- `command`: validation command that was run
- `passed_count`, `failed_count`: test counts
- `last_run_at`: timestamp
- `proof_status`: always "not_proof" (no proof authority)
- `next_action`: state-specific next action

State-aware resolution functions:
- `_resolve_stage()`: Determines lifecycle stage from canonical workspace/proposal/validation state
- `_resolve_next_safe_action()`: Determines next safe action message from state

Enriched `build_proposal_lifecycle_projection()`:
- Consumes `WorkspaceStatusSummary` canonical data
- Builds normalized summaries with explicit placeholders
- Resolves state-aware stage and next_safe_action
- Preserves all auditability/progress boundaries (transient, inert, advisory_only)

### Frontend (`src/rig_tools/static/js/widgets/proposal-lifecycle-console.js`)

Enhanced rendering:
- Render title: "Proposal Lifecycle Console"
- Render stage badge with state-aware severity
- Render workspace path when available
- Render next safe action
- Render blocked apply note under Gate A
- Render recommendation state/title/summary/source_surface/files/last_updated/next_action
- Render proposal state/summary/worktree_path/changed_files/next_action
- Render validation state/proof_status/summary/command/counts/last_run_at/next_action
- Render allowed actions and blocked actions
- Render progress/auditability note
- Safe fallback: missing fields render empty or "Unknown"
- Dumb widget: renders projection data only, no fetching, no authority logic

### Projection Builder (`src/rig/domain/projection_builder.py`)

The `_workspace_proposal_lifecycle_widget()` function already wires `workspace_summary` to `build_proposal_lifecycle_projection()`, so enrichment flows automatically to the frontend.

## Task Sequencing

1. **DONE** (baseline): Harden the canonical workspace substrate and status summary.
2. **DONE** (this slice): Define and implement normalized lifecycle summary models.
3. **DONE** (this slice): Wire `build_proposal_lifecycle_projection` to consume `WorkspaceStatusSummary`.
4. **DONE** (this slice): Make stage and next_safe_action state-aware.
5. **DONE** (this slice): Preserve auditability/progress boundaries.
6. **DONE** (baseline): Projection builder already emits the proposal lifecycle widget.
7. **DONE** (this slice): Update ProposalLifecycleConsole widget for enriched rendering.
8. **DONE**: Progress timeline remains transient.
9. **DONE**: Frontend usability incorporated into widget.
10. **DONE**: Docs updated.

## Acceptance Gates

- [x] workspace status shows the control plane and Gate A note
- [x] workspace projection shows proposal lifecycle widgets with enriched data
- [x] UI renders progress as transient telemetry
- [x] recommendation surfaces lead to the next safe action
- [x] validation summary is visible without implying durable proof
- [x] docs state what is allowed, blocked, and still future work
- [x] no main mutation is implied by the sprint itself
- [x] Stage is state-aware (workspace_unselected, gate_a_active, recommendation_available, validation_passed, validation_failed, review_ready)
- [x] next_safe_action is state-aware
- [x] Apply remains blocked under Gate A with clear note
- [x] No receipts are created
- [x] No progress events are persisted
- [x] Empty/placeholder projections do not fake active workspace state

## Validation Commands

- `python3.14 -m compileall -q src tests`
- `python3.14 -m pyright --project pyrightconfig.json`
- `python3.14 -m pytest tests/test_workspace_control_plane.py -v`
- `python3.14 -m pytest tests/test_ui_frontend_logic.py -v`
- `python3.14 -m rig workspace status`
- `python3.14 -m rig workspace projection`
- `python3.14 -m rig ui --help`

## Risks

- Projection scope may grow faster than the UI can stay simple.
- Progress can be mistaken for authority if docs and widgets drift.
- Validation summary may drift into receipt semantics if not kept explicit.
- Proposal lifecycle UI can become cluttered if progress and recommendation data are not separated clearly.

## Non-goals

- No durable progress storage
- No receipt-backed progress
- No main-worktree apply path
- No enforcement system overhaul
- No provider sync
- No full workspace runtime

## Recommended First Implementation Task

Harden the canonical workspace status summary and then wire `ProposalLifecycleProjection` to consume it before adding any richer recommendation or validation UX.

## Notes for this Enrichment Slice

This implementation is the **lifecycle enrichment slice** that was lost and is being re-implemented from scratch on top of the committed `WorkspaceStatusSummary` substrate (`23b81a0`) and Gate A enforcement (`17d7dbf`).

Key design decisions:
- All enrichment comes from `WorkspaceStatusSummary` canonical data
- State-aware stage and next_safe_action use explicit, deterministic logic
- Placeholders are explicit: "unknown", "unavailable", "not_created", "not_run", "not_proof"
- No state is faked or inferred from non-canonical sources
- Frontend remains dumb: it only renders what the backend projects
- All auditability/progress boundaries are explicitly preserved
- Gate A apply block is explicit with a clear note
