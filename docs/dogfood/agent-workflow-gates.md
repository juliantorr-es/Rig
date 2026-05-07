# Agent Workflow Gates

## Purpose

Rig can dogfood itself as a governed local coding control plane, but the allowed surface is intentionally narrow at Gate A.

Gate A means:

- read-only workspace status, projection, and progress
- isolated proposal-shaped workflows when they already exist
- read-only inspections and validation checks
- explicit stopping on Rig gate failure

Gate A does not mean autonomous apply, durable proof, or treating transient telemetry as authority.

## Maturity Gates

### Gate A

Allowed:

- check Rig workspace status
- read the workspace projection
- observe `progress_event` telemetry
- create or use isolated worktree/proposal lanes when those surfaces already exist
- run read-only inspections and smoke checks
- report progress summaries and validation output
- stop on failed Rig gates

Blocked:

- direct writes to `main`
- autonomous apply
- bypassing failed Rig gates
- claiming transient progress as proof
- creating receipts from progress
- persisting progress events
- treating `receipt_candidate` as authority
- treating `evidence_refs` as resolved evidence
- treating the frontend progress-store as a source of truth

### Gate B

Future gate for validated proposal handoff with deterministic validation summary.

### Gate C

Future gate for receipt-backed apply/reject workflow.

### Gate D

Future default agent control plane.

## Machine-Readable Policy

Gate A is described in [`src/rig/domain/agent_workflow_gates.py`](/Users/user/Developer/GitHub/Rig/src/rig/domain/agent_workflow_gates.py) as an advisory policy object:

- `allowed_operations`
- `blocked_operations`
- `blocked_practices`
- `workflow_prompt`
- `notes`

The policy is descriptive only. It does not enforce command authorization by itself.

## Agent Prompt Snippet

Use Rig as the workflow control plane when available. Start with Rig workspace status and projection, then report:

- Rig status
- projection and progress summary
- files changed
- validations run
- blockers

Do not mutate `main` directly. Stop when a Rig gate fails. Do not treat transient progress as evidence or receipts.

## Authority Boundary

- Progress telemetry is transient.
- Progress receipts are not implemented yet.
- Existing receipts remain the durable evidence boundary.
- `receipt_candidate` is a hint only.
- `evidence_refs` are inert until receipt-backed progress exists.
- The frontend progress-store is not authority.

