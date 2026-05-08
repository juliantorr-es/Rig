# Execution Sandbox Architecture (Managed Execution)

> **Status: IMPLEMENTED (Git Worktrees) / RESEARCH (Hardened Sandboxing)**
> This document describes the managed execution layer. Current isolation uses Git worktrees. Hardened sandboxing (gVisor, Firecracker) remains research.

## Overview

The **Execution Sandbox** provides a high-leverage interface for running untrusted or isolated commands within the Rig ecosystem. It abstracts away the complexity of worktree management, environment setup, and evidence capture.

In Rig's evidence-based architecture, execution is not just about running a process; it is about obtaining an **Execution Lease** and capturing a durable **Receipt** of what occurred.

## Core Concepts

### 1. Execution Lease
An `ExecutionLease` represents a temporary, isolated environment (typically a Git worktree) where a command can safely execute. The lifecycle of a lease includes:
- **Acquisition:** Setting up the worktree and environment.
- **Execution:** Running the command and capturing output.
- **Release:** Tearing down the environment and persisting the results.

### 2. Execution Request
A structured request that defines:
- **Command:** The executable and arguments.
- **Context:** The workspace and files required.
- **Purpose:** Why the execution is happening (e.g., `validator.run`, `patch.test`).
- **Constraints:** Timeouts, resource limits, and environment variables.

### 3. Execution Result (Receipt)
The output of an execution, including:
- Exit code, stdout, and stderr.
- Timestamps (started at, completed at).
- Cryptographic hashes of the state and output.
- A unique `ReceiptID` for governance tracking.

## Components

Located in `src/rig_tools/` (transitioning to `src/rig/domain/execution/` in future):

- **`WorktreeExecutor`**: Manages the physical creation and deletion of Git worktrees used for isolation.
- **`ManagedExecution`**: Orchestrates the setup, run, and cleanup phases, ensuring that results are always persisted as evidence.

## Interface Design

A high-leverage interface allows callers to focus on *what* to run, not *how* to isolate it:

```python
result = sandbox.execute(
    request=ExecutionRequest(
        workspace_id="ws-123",
        command=["python", "-m", "pytest"],
        purpose="validator.run",
        timeout_seconds=120
    )
)
```

## Security Boundaries

While the current implementation uses isolated Git worktrees and controlled processes, the "Sandbox" name is a commitment to future hardening. Future backends could include:
- **Docker/Containerized execution.**
- **Remote execution in ephemeral VMs.**
- **Firejail or other OS-level sandboxing.**

By using the `ExecutionSandbox` interface today, we ensure that the rest of the system remains agnostic to the specific isolation technology used.

## Benefits

- **Safety:** Prevents untrusted model output from mutating the main branch directly.
- **Reproducibility:** Every execution is captured as a durable receipt.
- **Portability:** The execution backend can be swapped without changing governance or UI logic.
