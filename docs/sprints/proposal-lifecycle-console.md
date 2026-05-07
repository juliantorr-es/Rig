# Proposal Lifecycle Console Sprint

## Sprint Name

Proposal Lifecycle Console

## Sprint Goal

Make Rig UI usable enough that a human can understand an agent handoff from the workspace surface without leaving the control plane. The sprint is projection-first: workspace selection, status, Dogfood Gate A, progress, recommendation/proposal context, validation summary, and next safe action all need to be visible in one coherent console.

## Product Increment

At the end of the sprint, the operator should be able to:

1. select a workspace
2. see workspace status and Gate A
3. see transient progress
4. see a recommendation/proposal summary
5. see a validation summary
6. see the next safe action

This increment remains UI/projection-led. Auditability is future-compatible, not fully complete.

## Definition of Done

The sprint is done when:

- the workspace control plane is the obvious entry point
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

- ProposalLifecycleProjection domain model
- projection builder integration
- ProposalLifecycleConsole UI widget/region
- Dogfood Gate A visible in CLI/projection/UI
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

## Task Sequencing

1. Define the ProposalLifecycleProjection domain model.
2. Wire the projection builder to emit the proposal/recommendation/validation surface.
3. Add the ProposalLifecycleConsole region to the UI projection.
4. Surface Dogfood Gate A in CLI, projection, and UI.
5. Add the validation summary projection.
6. Add the recommendation/proposal lifecycle surface.
7. Tighten progress timeline usability.
8. Run the frontend usability pass.
9. Update docs and handoff guidance.

## Sprint Backlog

| Order | Workstream | Outcome |
|---|---|---|
| 1 | ProposalLifecycleProjection domain model | Canonical projection shape for proposal/recommendation/validation state |
| 2 | Projection builder integration | Backend-authored proposal lifecycle widgets appear in workspace projection |
| 3 | ProposalLifecycleConsole UI widget/region | Browser renders the new proposal lifecycle console region |
| 4 | Dogfood Gate A visible in CLI/projection/UI | Read-only gate note is obvious in operator surfaces |
| 5 | Validation summary projection | Validation state is visible and readable |
| 6 | Proposal/recommendation lifecycle surface | Next safe action and recommendation context are obvious |
| 7 | Progress timeline usability | Progress stays transient but understandable |
| 8 | Frontend usability pass | The console is readable, navigable, and not overbuilt |
| 9 | Docs and handoff guidance | The sprint and its operating rules are documented |

## Acceptance Gates

- workspace status shows the control plane and Gate A note
- workspace projection shows proposal lifecycle placeholders or widgets
- UI renders progress as transient telemetry
- recommendation surfaces lead to the next safe action
- validation summary is visible without implying durable proof
- docs state what is allowed, blocked, and still future work
- no main mutation is implied by the sprint itself

## Validation Commands

- `python3.14 -m compileall -q src scripts tests`
- `python3.14 -m pytest tests/test_workspace_control_plane.py -v`
- `python3.14 -m pytest tests/test_ui_intent_contract.py -v`
- `python3.14 -m pytest tests/test_ui_frontend_logic.py -v`
- `python3.14 -m pytest tests/test_ui_repo_selection.py -v`
- `python3.14 -m pytest tests/test_rig_agent_worktree.py -v`
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

Define `ProposalLifecycleProjection` and wire the projection builder to emit a minimal proposal lifecycle console region with a validation summary placeholder and Gate A note.

