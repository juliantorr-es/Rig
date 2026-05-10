# Demo Workspace Guide

> **Understand what Rig does, see governance in action.**

This document provides a complete demo workflow for new users. It walks through Rig's core capabilities using concrete examples that you can run yourself.

## Goal

After completing this demo, you will understand:
- What Rig actually does
- What "governance" means in practice
- Why receipts and replay matter
- How projections work
- What the trust boundaries are

## Prerequisites

Before starting the demo:

1. **Install Rig** (see [Install Guide](install.md)):
   ```bash
   python3.14 -m venv .venv
   source .venv/bin/activate
   python -m pip install -e ".[ui,dev]"
   ```

2. **Verify installation:**
   ```bash
   python -m rig doctor all
   # Should output: Integrity score: 1.00
   ```

3. **Initialize a test repo** (or use an existing one):
   ```bash
   mkdir ~/rig-demo
   cd ~/rig-demo
   git init
   git config user.email "demo@example.com"
   git config user.name "Demo User"
   ```

## Demo 1: First Successful Commands

These are the commands that should work immediately in a new Rig installation.

### Command: `rig doctor all`

```bash
# Navigate to your repo
cd ~/rig-demo

# Run the full doctor command
python -m rig doctor all
```

**Expected output:**
```
Rig Doctor - Full System Integrity Check
==========================================

[PASS] Workspace substrate                 score: 1.00
[PASS] Receipt store                       score: 1.00
[PASS] Audit event store                   score: 1.00
[PASS] Projection registry                 score: 1.00
[PASS] Governance engine                   score: 1.00

Integrity score: 1.00
All checks passed.
```

**What this means:**
- Rig's core components are functioning
- The workspace substrate (read-only Git worktree info) is available
- Receipt and audit storage is ready
- Projection system is registered
- Governance engine is loaded

### Command: `rig doctor projections`

```bash
python -m rig doctor projections
```

**Expected output:**
```
Rig Doctor - Projection Contract Validation
=============================================

[PASS] workspace_status_projection        contract: v1
[PASS] receipt_timeline_projection          contract: v1
[PASS] intent_status_projection           contract: v1
[PASS] validation_findings_projection      contract: v1
[PASS] audit_trail_projection              contract: v1

Projection contract validation: PASSED
All projection contracts comply with lock-down rules.
```

**What this means:**
- All projections are properly defined
- They follow the projection contract (derived, not authoritative)
- No projection invents state
- All projections are frozen dataclasses

### Command: `rig replay timeline --json`

```bash
python -m rig replay timeline --json
```

**Expected output (empty workspace):**
```json
{
  "workspace_id": "default",
  "replay_status": "empty",
  "timeline": [],
  "continuity_validation": {
    "status": "passed",
    "findings": []
  },
  "integrity_score": 1.0
}
```

**What this means:**
- You have an empty timeline (no receipts yet)
- Continuity validation passes (trivially, with no receipts)
- The replay system is working

## Demo 2: Create a Workspace

Now let's create a workspace for a sample task.

### Command: `rig workspace create demo-task`

```bash
python -m rig workspace create demo-task --task "Implement user authentication"
```

**Expected output:**
```
Workspace 'demo-task' created successfully.
Workspace ID: demo-task_<uuid>
Status: planned
Authority: user

Next steps:
  1. Run: rig run --workspace demo-task --task "Implement user authentication" --provider custom-command
  2. Or: rig workspace status demo-task
```

**What just happened:**
1. A new Git worktree was created (isolated from main)
2. A `workspace_create` receipt was generated
3. An audit event was recorded
4. The workspace status is `planned`

### Verify: Check Workspace Status

```bash
python -m rig workspace status demo-task
```

**Expected output:**
```
Workspace: demo-task
==================
ID:     demo-task_<uuid>
Status: planned
Lane:   demo-task
Path:   .rig/worktrees/demo-task

Receipts:    1
Intents:     0
Findings:    0

Authority: user
Created:   2025-01-XXTXX:XX:XXZ
```

### Verify: Check Receipts

```bash
python -m rig workspace receipts demo-task --json
```

**Expected output:**
```json
{
  "workspace_id": "demo-task_<uuid>",
  "receipts": [
    {
      "receipt_id": "rcpt_<uuid>",
      "receipt_type": "workspace_create",
      "schema_version": "1.0",
      "created_at": "2025-01-XXTXX:XX:XXZ",
      "actor": {
        "type": "user",
        "id": "cli"
      },
      "subject": {
        "type": "workspace",
        "workspace_id": "demo-task_<uuid>"
      },
      "decision": {
        "type": "allow",
        "reason": "Workspace creation approved"
      },
      "authoritative": true,
      "advisory_only": false
    }
  ],
  "total_receipts": 1
}
```

**Key observation:**
- `authoritative: true` — This receipt affects workspace state
- `advisory_only: false` — This is not just a suggestion
- The receipt is **immutable** — it cannot be modified

## Demo 3: Run a Task

Let's run a simple task in the workspace.

### Command: `rig run`

```bash
python -m rig run \
  --workspace demo-task \
  --task "Implement user authentication" \
  --provider custom-command \
  --command "echo 'User auth implementation' > auth.py"
```

**Expected output:**
```
Intent created: intent_<uuid>
Status: executed
Receipt: exec_<uuid>

Workspace: demo-task
Intent command: echo 'User auth implementation' > auth.py
Exit code: 0

Next steps:
  1. Validate: rig workspace review demo-task
  2. Or:     rig doctor workspace demo-task
```

**What just happened:**
1. An intent was created with the task description and command
2. The command was executed in the isolated worktree
3. An `exec_receipt` was created recording the execution
4. The workspace status changed to `executed`

### Command: Verify Execution in Worktree

```bash
# Check what's in the worktree
ls .rig/worktrees/demo-task/

# View the file that was created
cat .rig/worktrees/demo-task/auth.py
```

**Expected output:**
```
User auth implementation
```

**Important:** The file was created in the **isolated worktree**, not in your main branch!

### Check the Receipt Chain

```bash
python -m rig replay timeline --json | python -m json.tool
```

**Expected output:**
```json
{
  "workspace_id": "default",
  "replay_status": "ok",
  "timeline": [
    {
      "receipt_id": "rcpt_<uuid>",
      "receipt_type": "workspace_create",
      "created_at": "2025-01-XXTXX:XX:XXZ",
      "summary": "Workspace created: demo-task"
    },
    {
      "receipt_id": "exec_<uuid>",
      "receipt_type": "exec_receipt",
      "created_at": "2025-01-XXTXX:XX:XXZ",
      "summary": "Intent executed: Implement user authentication"
    }
  ],
  "continuity_validation": {
    "status": "passed",
    "findings": []
  },
  "integrity_score": 1.0
}
```

**Key observation:**
- You now have 2 receipts in the chain
- The timeline shows the sequence of events
- Continuity validation still passes

## Demo 4: Doctor Commands

Let's check the integrity of our demo workspace.

### Command: `rig doctor workspace demo-task`

```bash
python -m rig doctor workspace demo-task
```

**Expected output:**
```
Rig Doctor - Workspace Integrity Check
========================================
Workspace: demo-task

[PASS] Workspace substrate         score: 1.00
[PASS] Receipt chain continuity    score: 1.00
[PASS] Intent state                score: 1.00
[PASS] Authority flags             score: 1.00
[PASS] Projection consistency      score: 1.00

Workspace integrity score: 1.00
All checks passed.
```

### Command: `rig doctor all`

```bash
python -m rig doctor all
```

**Expected output:**
```
... (includes all workspaces)
Integrity score: 1.00
All checks passed.
```

## Demo 5: Replay Determinism

Let's demonstrate Rig's replay capability.

### Command: Replay from Scratch

```bash
# Get the full timeline
python -m rig replay timeline --json > /tmp/timeline.json

# Clear local state (simulate fresh start)
# In reality, Rig doesn't need this - it replays from receipts

# Replay and verify
python -m rig replay timeline --json | python -m json.tool
```

**Expected:** The output should be **identical** to what you got before.

**What this means:**
- Rig can reconstruct the entire timeline from receipts alone
- The replay is deterministic — same inputs always produce same outputs
- No state is invented — if data is missing, replay reports it as missing

## Demo 6: Projection Example

Projections are the UI's view of the world. Let's see them in action.

### Command: `rig workspace projection demo-task --json`

```bash
python -m rig workspace projection demo-task --json | python -m json.tool
```

**Expected output:**
```json
{
  "workspace_id": "demo-task_<uuid>",
  "status": "executed",
  "lane": "demo-task",
  "receipt_count": 2,
  "intent_count": 1,
  "last_activity": "2025-01-XXTXX:XX:XXZ",
  "authority": {
    "current": "user",
    "can_apply": false,
    "can_review": true,
    "can_execute": true,
    "disabled_reason": null
  },
  "projection_type": "workspace_status",
  "schema_version": "1.0",
  "authoritative": false,
  "advisory_only": true
}
```

**Key observations:**
- `authoritative: false` — Projections never affect state
- `advisory_only: true` — Projections are for display only
- `can_apply: false` — Can't apply until review
- `disabled_reason: null` — No reason to disable controls

## Demo 7: Integrity Failure Example

Let's see what happens when something goes wrong. We'll simulate a problem.

### Simulation: Missing Receipt Reference

This is a thought experiment — don't actually do this:

```bash
# DON'T ACTUALLY RUN THIS - it's just for illustration
# If receipts were deleted or corrupted:
rm .rig/receipts/*.json  # This would be bad!

# Then replay would show:
python -m rig replay timeline --json
```

**Expected error output:**
```json
{
  "workspace_id": "default",
  "replay_status": "error",
  "error": "continuity_break",
  "missing_receipts": ["exec_<uuid>"],
  "findings": [
    {
      "type": "missing_receipt",
      "severity": "error",
      "receipt_id": "exec_<uuid>",
      "message": "Receipt referenced but not found"
    }
  ],
  "continuity_validation": {
    "status": "failed",
    "findings": [...]
  },
  "integrity_score": 0.0
}
```

**What this means:**
- Rig **detects** missing receipts
- Replay **fails explicitly** rather than inventing state
- The integrity score drops to 0.0
- The issue is clearly identified

### Command: Validation Tests

Run the actual validation tests:

```bash
python -m pytest tests/test_replay.py -v -k "continuity"
```

**Expected:** All continuity tests should pass.

## Demo 8: Understanding Trust Boundaries

Let's visualize the trust boundaries in action.

### Trust Level 0: Canonical Evidence

```bash
# View the raw receipts (L0 - highest trust)
python -m rig workspace receipts demo-task --json
```

This shows the **immutable, cryptographically signed** receipts.

### Trust Level 1: Replay Results

```bash
# Replay and get derived state (L1 - derived from L0)
python -m rig replay timeline --json
```

This shows **deterministic** results derived from L0 evidence.

### Trust Level 2: Projections

```bash
# Get UI-optimized projections (L2 - derived from L1)
python -m rig workspace projection demo-task --json
```

This shows **backend-authored** display data.

### Trust Level 3: Frontend

```bash
# In the UI, widgets consume L2 projections only
# The frontend never infers authority
# It only displays what the backend provides
```

**The Invariant:** `Trust(L0) > Trust(L1) > Trust(L2) > Trust(L3)`

## Demo 9: Cleanup

Now let's clean up our demo workspace.

### Command: Delete Workspace

```bash
# Switch to main branch
cd ~/rig-demo
git checkout main

# Delete the demo workspace
python -m rig workspace delete demo-task
```

**Expected output:**
```
Workspace 'demo-task' deleted.
Receipts archived to: .rig/archive/demo-task_<uuid>_
```

**What happened:**
- The Git worktree was deleted
- Receipts were archived (not deleted)
- The workspace is gone, but the audit trail remains

### Verify Cleanup

```bash
# Check workspace list
python -m rig workspace list

# Check that receipts are still available
python -m rig replay timeline --json
```

## Summary of What You Learned

### What Rig Does

| Capability | What It Means |
|------------|---------------|
| **Workspaces** | Isolated Git worktrees for each task |
| **Receipts** | Immutable, signed records of every action |
| **Replay** | Deterministic state reconstruction from receipts |
| **Doctor** | Integrity and continuity validation |
| **Projections** | UI-safe derived state (never authoritative) |
| **Governance** | Deny-by-default action legality checks |

### Governance in Practice

1. **No silent mutation of main** — Everything goes through worktrees
2. **No auto-apply** — You must explicitly review and approve
3. **No state invention** — If data is missing, Rig says so
4. **Full audit trail** — Every action has a receipt
5. **Replayable history** — You can always see what happened
6. **Projection-only UI** — The frontend doesn't guess, it displays

### Why This Matters

| Problem | Rig's Solution |
|---------|----------------|
| AI tools silently change your code | Requires explicit review and apply |
| You don't know what the AI did | Immutable receipt chain |
| You can't verify AI actions | Deterministic replay |
| AI might have hidden state | All state derived from receipts |
| UI might lie about state | Projections are backend-authored |

## Next Steps

Now that you've completed the demo:

1. **Read the Architecture Docs:**
   - [Workspace Control Plane](architecture/workspace-control-plane.md)
   - [Governance Engine](architecture/governance-engine.md)
   - [Governance Replay](architecture/governance-replay.md)

2. **Try Real Workflows:**
   - Create a workspace for an actual task
   - Run commands through Rig's governance
   - Practice the review and apply flow

3. **Explore Advanced Features:**
   - Multiple workspaces
   - Projection contracts
   - Replay validation

## Troubleshooting the Demo

If something didn't work:

| Issue | Solution |
|-------|----------|
| Command not found | Use `python -m rig` instead of `rig` |
| Python version error | Install Python 3.14+ |
| Doctor checks fail | Run `bash scripts/check.sh` for details |
| Workspace not found | Check workspace list with `python -m rig workspace list` |

See [Troubleshooting Guide](troubleshooting.md) for more help.

## Quick Reference

| Goal | Command |
|------|---------|
| Check system | `python -m rig doctor all` |
| Create workspace | `python -m rig workspace create NAME` |
| Run task | `python -m rig run --workspace NAME --task TASK --provider PROVIDER` |
| View receipts | `python -m rig workspace receipts NAME --json` |
| Replay timeline | `python -m rig replay timeline --json` |
| Check workspace | `python -m rig doctor workspace NAME` |
| View projection | `python -m rig workspace projection NAME --json` |
| Full validation | `bash scripts/check.sh` |

---

**Demo Complete!** You now understand Rig's core concepts and can use it for governed AI coding workflows.
