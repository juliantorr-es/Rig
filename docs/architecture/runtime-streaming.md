# Runtime Streaming Architecture

**Phase 2: Runtime & Agent Execution Plane**

> **Core Doctrine:** Runtime output is **advisory evidence only**. Only receipts/proposals become **authoritative evidence**. UI streams **projections**, NOT raw subprocesses. All runtime execution remains **advisory-only**.

---

## Overview

The Runtime Streaming Architecture implements a **deterministic, replay-safe, projection-only** pipeline for processing runtime stream events from AI providers and agent execution environments. It is designed to safely handle streaming output while strictly enforcing Rig's governance principles.

### Core Principles

1. **Advisory-Only**: All runtime output is advisory evidence; it never becomes authoritative without explicit receipt generation
2. **Projection-First**: UI consumes only structured projections, never raw subprocess output
3. **Replay-Safe**: All events are designed for deterministic replay and integrity verification
4. **Bounded**: All buffers, chunks, and projections have explicit size limits
5. **Deterministic**: Event IDs and sequence numbers are deterministically generated
6. **Isolated**: Runtime execution never directly mutates workspace state

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │  Console    │  │   Stream     │  │    Status    │  │ Proposal│ │
│  │   Card      │  │    Card      │  │    Card      │  │   Card  │ │
│  └─────────────┘  └──────────────┘  └──────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Projection Updates (JSON)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Runtime Projection Layer                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  RuntimeProjectionBuilder                               (builder) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeStreamProjection                                (output) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeStreamProjectionBuffer                        (storage) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeProjectionContract                             (rules) ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Stream Events
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Runtime Stream Layer                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  RuntimeStreamChunk                                   (content) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeStatusEvent                                    (status)  ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeHeartbeatEvent                                (heartbeat)││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeToolProposalEvent                          (proposals) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimePatchProposalEvent                         (proposals) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeWarningEvent                                   (warnings) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeCompletionEvent                              (completion)││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeFailureEvent                                    (errors)  ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeStreamBuffer                                    (buffer)  ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeSequenceState                                (tracking) ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Raw Stream Data
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Runtime Execution Layer                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  RuntimeSupervisor                               (supervision) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeProcessHandle                                (handle)  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Process Execution
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WebSocket Integration                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  WebSocketStreamIntegrator                         (integrator)││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  WebSocketStreamMessage                              (message) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  WebSocketStreamState                               (state)   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ WebSocket Messages
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Replay & Integrity Layer                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  RuntimeReplayEngine                               (engine)   ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeReplayBuffer                                   (buffer)  ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeReplayVerifier                                (verifier) ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  RuntimeReplayReference                                (reference)││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Stream Event Models (`runtime_stream.py`)

The foundation of the streaming architecture. All stream events are **frozen, deterministic dataclasses** with explicit sequence numbers and integrity markers.

#### Event Types

| Event | Purpose | Key Fields |
|-------|---------|------------|
| `RuntimeStreamChunk` | Text content from the stream | `content`, `channel`, `sequence` |
| `RuntimeStatusEvent` | Stream lifecycle status changes | `status`, `message` |
| `RuntimeHeartbeatEvent` | Keep-alive indicators | `interval_ms`, `timestamp` |
| `RuntimeToolProposalEvent` | Tool call proposals | `tool_name`, `arguments`, `blocked` |
| `RuntimePatchProposalEvent` | Code patch proposals | `path`, `diff`, `language` |
| `RuntimeWarningEvent` | Non-fatal warnings | `code`, `message`, `severity_code` |
| `RuntimeCompletionEvent` | Stream completion | `reason`, `summary` |
| `RuntimeFailureEvent` | Stream failures | `category`, `error_code`, `message` |

#### Key Features

- **Deterministic IDs**: SHA-256 hash of key components
- **Sequence Tracking**: Monotonically increasing sequence numbers
- **Content Truncation**: Bounded at 1MB per chunk
- **Buffer Management**: Bounded at 10MB total
- **Replay References**: Links to original stream for verification

### 2. Projection Pipeline (`runtime_projection.py`)

Transforms raw stream events into **UI-ready projections**.

#### Pipeline Stages

1. **Buffer**: Collect stream events (`RuntimeStreamProjectionBuffer`)
2. **Transform**: Convert to projection data (`RuntimeProjectionBuilder`)
3. **Validate**: Enforce rules (`RuntimeProjectionContract`)
4. **Output**: Generate projection (`RuntimeStreamProjection`)

#### Projection Types

- **Stream**: Live token/chunk rendering
- **Status**: Runtime status updates
- **Proposal**: Tool/patch proposal summaries
- **Console**: Console-style output display
- **Diagnostic**: Streaming diagnostics
- **Summary**: Aggregated statistics
- **Chart**: Visual data representations
- **Timeline**: Temporal event sequencing

#### Safety Guarantees

- **textContent-only**: All projections render using `textContent`, never `innerHTML`
- **Bounded Size**: Max 100KB per projection, 100 chunks
- **Safe Truncation**: Content truncated with integrity flags
- **No Authority**: All projections are `advisory_only=True`

### 3. Process Supervision (`runtime_supervisor.py`)

Manage and supervise runtime subprocesses with **strict safety controls**.

#### Components

| Component | Purpose |
|-----------|---------|
| `RuntimeProcessHandle` | Tracks a single process (command, PID, status) |
| `RuntimeSupervisorDecision` | Records decision (allow/block/terminate) |
| `RuntimeSupervisorReceipt` | Summarizes supervision activity |
| `RuntimeSupervisor` | Manages all supervised processes |

#### Forbidden Commands

The supervisor **blocks** dangerous commands including:

```python
FORBIDDEN_COMMANDS = [
    "git reset --hard",
    "git push --force",
    "git clean -fd",
    "rm -rf",
    "rm -r",
    "chmod -R 777",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    ":(){ :|:& };:",  # Fork bomb
    "exec",
    "> /dev/sda",
    "/dev/null",
]
```

#### Safety Features

- **Command Validation**: All commands checked against forbidden list
- **Output Bounds**: Max 10MB stdout/stderr
- **Timeout Enforcement**: Default 300 second timeout
- **Graceful Shutdown**: 5 second shutdown period
- **Isolation**: No direct workspace access

### 4. WebSocket Integration (`runtime_websocket.py`)

Real-time streaming over WebSocket connections.

#### Components

| Component | Purpose |
|-----------|---------|
| `WebSocketStreamMessage` |Individual WebSocket message with sequence tracking |
| `WebSocketStreamState` |Connection state tracking |
| `WebSocketStreamIntegrator` |Manages WebSocket connections and message routing |
| `WebSocketMessageNormalizer` |Normalizes messages to consistent format |

#### Features

- **Deterministic Ordering**: Sequence numbers for all messages
- **Backpressure Protection**: Bounded queue (max 100 messages)
- **Duplicate Detection**: Prevents duplicate message processing
- **Reconnect-Safe**: Session recovery with sequence validation
- **Rate Limiting**: Max 100 messages/second per connection

### 5. Replay & Integrity (`runtime_replay.py`)

Deterministic replay and integrity verification for stream events.

#### Components

| Component | Purpose |
|-----------|---------|
| `RuntimeReplayReference` |Reference to replayable stream |
| `RuntimeReplayChunk` |Batch of events for replay |
| `RuntimeReplayIntegrityFinding` |Single integrity check result |
| `RuntimeReplayIntegrityReport` |Complete verification report |
| `RuntimeReplayStateSnapshot` |State capture for persistence |
| `RuntimeReplayBuffer` |Storage for replay events |
| `RuntimeReplayVerifier` |Verifies replay integrity |
| `RuntimeReplayEngine` |Executes replay operations |

#### Verification Levels

- **NONE**: No verification
- **BASIC**: Sequence and timing checks
- **STANDARD**: Includes content checksums
- **STRICT**: Full cryptographic verification

#### Integrity Checks

- Sequence gap detection
- Duplicate sequence detection
- Out-of-order detection
- Checksum mismatch detection
- Hash mismatch detection
- Timestamp validation

### 6. Doctor & Diagnostics (`runtime_doctor.py`)

Health checking and diagnostic capabilities.

#### Check Categories

- **SYSTEM**: CPU, memory, disk usage
- **RUNTIME**: Runtime infrastructure health
- **STREAM**: Stream pipeline integrity
- **PROJECTION**: Projection pipeline status
- **WEBSOCKET**: WebSocket connection health
- **REPLAY**: Replay system verification
- **SUPERVISOR**: Process supervision status
- **NETWORK**: Network connectivity
- **SECURITY**: Security posture validation
- **CONFIGURATION**: Configuration validation

#### Severity Levels

- **INFO**: Informational findings
- **OK**: Passed checks
- **WARNING**: Potential issues
- **ERROR**: Detected problems
- **CRITICAL**: Serious issues requiring attention

### 7. Benchmarking & Telemetry (`runtime_benchmark.py`)

Performance monitoring and benchmarking.

#### Metric Types

- **COUNTER**: Monotonically increasing values
- **GAUGE**: Point-in-time values
- **HISTOGRAM**: Distribution of values
- **SUMMARY**: Statistics over observations
- **TIMING**: Latency measurements
- **RATE**: Events per time unit
- **RESOURCE**: Resource usage (CPU, memory)

#### Benchmark Types

- **THROUGHPUT**: Events/second processing
- **LATENCY**: End-to-end latency
- **MEMORY**: Memory usage
- **CPU**: CPU usage
- **STARTUP**: Startup time
- **SHUTDOWN**: Shutdown time
- **SERIALIZATION**: Serialization performance
- **PROJECTION**: Projection generation performance
- **REPLAY**: Replay performance
- **WEBSOCKET**: WebSocket performance

---

## Frontend Widgets

Four JavaScript widgets render runtime stream data to the UI:

### 1. `runtime-console-card.js`

Console-style display for runtime stream output.

**Features:**
- Monospace font rendering
- Channel prefixes (`[ASSISTANT]`, `[USER]`, etc.)
- Timestamp display
- Color-coded by severity
- Scrollable output with line limits
- Metadata footer (provider, model, invocation)
- Advisory notice

### 2. `runtime-stream-card.js`

Live token/chunk rendering.

**Features:**
- Sequence number display
- Channel labels with short prefixes
- Token/chunk statistics
- Metadata display (provider, model, stream, invocation)
- Truncation indicator
- Integrity flags
- Advisory notice
- Replay reference

### 3. `runtime-status-card.js`

Runtime status display.

**Features:**
- Status badge (active, completed, failed, etc.)
- Progress indicators
- Capability usage list
- Diagnostics grid
- Token usage statistics
- Metadata footer
- Integrity flags
- Advisory notice
- Replay reference

### 4. `runtime-proposal-card.js`

Proposal summary display.

**Features:**
- Proposal title and description
- Proposal details grid (ID, kind, capability, command, tool, etc.)
- Risk assessment with severity badges
- Capability usage display
- Diagnostics section
- Code preview for patch proposals
- Blocked reason display
- Integrity flags
- Advisory notice
- Replay reference

---

## Data Flow

### Stream Flow

```
AI Provider / Runtime
        │
        ▼
┌─────────────────────┐
│  Stream Events       │  (runtime_stream.py)
│  - Chunks           │
│  - Status           │
│  - Proposals        │
│  - Warnings         │
│  - Completion       │
│  - Failure          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Stream Buffer       │  ( runtime_stream.py )
│  - Sequence tracking │
│  - Bounded size      │
│  - Deterministic    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Projection Builder  │  (runtime_projection.py)
│  - Transform events  │
│  - Apply contracts   │
│  - Generate output   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Projections         │  (runtime_projection.py)
│  - Stream            │
│  - Status            │
│  - Proposal          │
│  - Console           │
└──────────┬──────────┘
           │ JSON
           ▼
┌─────────────────────┐
│  WebSocket           │  (runtime_websocket.py)
│  - Message framing   │
│  - Sequence tracking │
│  - Connection mgmt   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Frontend Widgets    │  (widgets/*.js)
│  - Console Card      │
│  - Stream Card       │
│  - Status Card       │
│  - Proposal Card     │
└─────────────────────┘
```

### Replay Flow

```
┌─────────────────────┐
│  Original Stream     │
│  Events              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Replay Buffer       │  (runtime_replay.py)
│  - Store original    │
│  - Checksum          │
│  - Hash              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Replay Engine       │  (runtime_replay.py)
│  - Verify integrity  │
│  - Replay events     │
│  - Generate report   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Integrity Report    │  (runtime_replay.py)
│  - Findings          │
│  - Statistics        │
│  - Hash comparison   │
└─────────────────────┘
```

---

## Safety & Security

### Non-Negotiable Constraints

1. **NO Autonomous Apply**: Runtime never applies changes without explicit user intent
2. **NO Direct Workspace Mutation**: Runtime does not write to workspace
3. **NO Hidden Execution**: All execution is visible and logged
4. **NO Background Daemons**: No persistent background processes
5. **NO Cloud Orchestration**: No external service coordination
6. **NO Production Networking**: No external network access
7. **NO Real API Keys**: All API keys are placeholders
8. **NO Destructive Git Commands**: Git commands that destroy history are blocked

### Enforcement Mechanisms

| Constraint | Enforcement |
|------------|--------------|
| Advisory-Only | All models have `advisory_only=True`, `authoritative=False` |
| No Mutation | All models are `frozen=True` dataclasses |
| No Execution | No `execute`, `run`, `start` methods on data models |
| Forbidden Commands | Explicit block list in supervisor |
| Bounded Memory | Max sizes on all buffers and chunks |
| Deterministic | SHA-256 IDs, sequence numbers |
| Replay-Safe | Immutable events, checksums |
| Projection-Safe | textContent-only rendering |

### Forbidden Command Detection

The supervisor checks commands against:

1. **Exact Matches**: Full command strings
2. **Prefix Matches**: Command prefixes (e.g., `git reset`, `rm -rf`)
3. **Substring Matches**: Dangerous patterns anywhere in command

Match is case-sensitive but command arguments are checked as strings.

---

## Performance Characteristics

### Throughput

- **Max Messages/Second**: 100 (rate limited)
- **Max Queue Size**: 100 messages
- **Processing**: Synchronous, non-blocking where possible

### Memory

- **Max Chunk Size**: 1MB
- **Max Buffer Size**: 10MB (streams), 50MB (replay)
- **Max Projection Size**: 100KB
- **Max Projection Chunks**: 100

### Latency

- **Stream Processing**: < 1ms per event (typical)
- **Projection Build**: < 10ms per projection (typical)
- **WebSocket Delivery**: < 100ms end-to-end (typical)

---

## Configuration References

### Default Values

| Configuration | Default | Description |
|---------------|---------|-------------|
| `max_chunk_bytes` | 1MB | Maximum chunk content size |
| `max_buffer_bytes` | 10MB | Maximum stream buffer size |
| `stream_timeout_seconds` | 300 | Stream timeout |
| `heartbeat_interval_seconds` | 5 | Heartbeat frequency |
| `stalled_threshold_seconds` | 30 | Stalled detection threshold |
| `max_projection_bytes` | 100KB | Maximum projection size |
| `max_projection_chunks` | 100 | Maximum chunks per projection |
| `process_timeout_seconds` | 300 | Process timeout |
| `graceful_shutdown_seconds` | 5 | Graceful shutdown period |
| `max_stdout_bytes` | 10MB | Maximum stdout capture |
| `max_stderr_bytes` | 10MB | Maximum stderr capture |

### Bounds

| Bound | Value | Purpose |
|-------|-------|---------|
| Max Event Queue | 100 | WebSocket backpressure |
| Max Message Rate | 100/s | Rate limiting |
| Max Connections | 100 | Connection limit |
| Max Replay Buffer | 50MB | Replay storage |
| Max Metrics | 1000 | Telemetry cardinality |
| Max Replay Events | 10000 | Replay history |

---

## Error Handling

### Error Classifications

| Category | Severity | Description | Handling |
|----------|----------|-------------|----------|
| Stream Event | WARNING | Content truncated | Continue, flag as truncated |
| Stream Event | ERROR | Stream failed | Stop stream, report error |
| Proposal | WARNING | Proposal blocked | Skip, log reason |
| Supervision | CRITICAL | Forbidden command | Block immediately |
| Integrity | ERROR | Checksum mismatch | Flag, continue with warning |
| Resource | WARNING | Limit approaching | Log, continue |
| Resource | ERROR | Limit exceeded | Stop, report error |

### Error Recovery

1. **Stream Errors**: Stream is stopped, error event generated
2. **Supervision Errors**: Process is terminated, decision logged
3. **Projection Errors**: Projection marked as error, UI shows error state
4. **Integrity Errors**: Replay flagged, user notified

---

## Testing Strategy

Each component has comprehensive test coverage:

- **Unit Tests**: Individual model behavior
- **Integration Tests**: Component interactions
- **Doctrine Tests**: Compliance with core principles
- **Edge Case Tests**: Boundary conditions
- **Serialization Tests**: JSON roundtrip consistency

### Test Files

1. `tests/test_runtime_stream.py` - Stream event models
2. `tests/test_runtime_supervisor.py` - Process supervision
3. `tests/test_runtime_projection.py` - Projection pipeline

Each test file validates:
- Default values
- Constructor behavior
- Serialization/deserialization
- Method behavior
- Frozen/slots enforcement
- Advisory-only invariant
- Doctrinal compliance

---

## Future Enhancements

The architecture is designed to support future capabilities:

1. **Additional Projection Types**: Charts, graphs, custom visualizations
2. **Enhanced Integrity**: Cryptographic signing of stream events
3. **Distributed Streaming**: Multi-connection stream aggregation
4. **Advanced Metrics**: More detailed telemetry collection
5. **Machine Learning**: Anomaly detection on stream patterns
6. **Custom Widgets**: User-defined projection types

All future enhancements must maintain the core doctrine: **advisory-only, projection-first, replay-safe, bounded, deterministic**.

---

## See Also

- [Runtime Execution Phase 2 Sprint Document](runtime-execution-phase-2.md)
- [Workspace Integrity Rules](../workspace-integrity-rules.md)
- [Governance & Replay Architecture](../governance-replay.md)

---

*Document generated for Phase 2: Runtime & Agent Execution Plane*
*Last updated: [DATE]*
