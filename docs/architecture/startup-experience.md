# Startup Experience Doctrine

> **Canonical Rig Startup Philosophy: Operational, Calm, Precise**

## Core Principle

**Startup visualization must derive exclusively from actual runtime initialization.** No fake loading, no synthetic progress, no decorative motion. Every visual element during startup represents real subsystem readiness, real topology availability, or real websocket/runtime state.

---

## What Startup Must Feel Like

| MUST | MUST NOT |
|------|----------|
| Operational | Cinematic |
| Calm | Flashy |
| Precise | Chaotic |
| Instrumented | "AI magic" |
| Trustworthy | Cyberpunk |
| Deterministic | Decorative |

---

## Startup Sequencing

### 1. Pre-Initialization (0-500ms)
**Visual: None / Minimal**
- Show workspace path validation
- Display static Rig identity banner
- No motion, no progress bars
- Single static text: "Rig: Initializing Runtime Workspace"

**State:**
- Git guard checking
- Workspace path resolution
- Static asset loading (synchronous)

### 2. Runtime Subsystem Wake-Up (500ms-2s)
**Visual: Static Status Text Only**
- List subsystems being initialized (text-only, no animation)
- Each subsystem appears as text line when its initialization begins
- No progress bars - subsystem is either "initializing" or "ready"

**Subsystems (in deterministic order):**
1. `runtime.core` - Core execution engine
2. `runtime.projection` - Projection contract system
3. `runtime.stream` - Stream chunk buffer
4. `runtime.integrity` - Integrity validation
5. `runtime.topology` - Topology systems
6. `runtime.replay` - Replay infrastructure
7. `runtime.visualization` - Visual instrumentation
8. `runtime.websocket` - WebSocket communication

### 3. Topology Wake-Up (2-4s)
**Visual: Static Topology Skeleton**
- Lane boundaries appear as static lines (no fade-in)
- Lane labels appear instantly at their final positions
- No node animation - nodes appear at final positions
- If lanes are already defined in workspace state, render them immediately

**State:**
- Lane configurations loaded
- Topology plugin model initialized
- SVG primitive registry populated
- DTG visualization systems ready

### 4. Runtime Initialization Visibility (4-6s)
**Visual: Deterministic State Snapshot**
- Current workspace state rendered once, completely
- No transition animation
- If previous workspace exists, render it as-is
- If new workspace, render empty runtime with lane structure

**State:**
- Workspace persistence loaded
- Previous layout restored (if applicable)
- All widgets initialized to their saved positions
- Disclosure states restored

### 5. Progressive Reveal During Startup
**Rule: NO progressive reveal animation during initial startup.**

All elements must appear at their final state instantly. Progressive reveal is for user-driven disclosure, not for startup theatricality.

---

## Startup Pacing

### Timing Bounds
| Phase | Min Duration | Max Duration | Visual Behavior |
|-------|--------------|--------------|-----------------|
| Pre-init | 0ms | 500ms | Static text only |
| Subsystem init | 500ms | 2s | Text status, no motion |
| Topology wake-up | 2s | 4s | Static geometry only |
| Runtime visibility | 4s | 6s | Complete render, no animation |
| **Total** | **~2s** | **~6s** | All static, deterministic |

### Pacing Governance
- No subsystems may start before their dependencies are ready
- No visual element may appear before its backing state is available
- All startup text must be final, never "Loading..."
- If a subsystem takes longer than expected, show its name with "initializing" status, not a spinner

---

## Startup Motion Governance

### FORBIDDEN During Startup
- `-webkit-animation`
- `@keyframes`
- `transition:` properties
- `requestAnimationFrame` for decorative purposes
- Any opacity fade-in on critical elements
- Any transform scale/translate on layout elements

### ALLOWED During Startup
- Single static render of complete state
- Instant appearance of all elements at final positions
- Deterministic layout from saved workspace state
- Immediate visibility of runtime topology

### Reduced Motion Compliance
Startup must be identical with `prefers-reduced-motion: reduce`:
- No difference in timing
- No difference in visual elements
- No fallback animations
- Exactly the same as normal startup

---

## Visualization Derivation Rules

### Canonical Rule
**Every startup visual element MUST have a direct 1:1 mapping to runtime state.**

| Visual Element | Runtime State Source |
|----------------|----------------------|
| Lane boundaries | `workspace.lanes` configuration |
| Lane labels | `lane.id` and `lane.label` |
| Node positions | `topology.nodes` with deterministic coordinate mapping |
| Connector paths | `topology.connectors` with `source` and `target` |
| Runtime state indicator | `runtime.status` enum |
| Stream count | `stream_buffer.count` |
| Projection count | `projection_registry.count` |

### Explicitly Forbidden
- `setTimeout` for fake progress
- Random delay generation
- Synthetic loading states
- Placeholder "skeleton" UI that doesn't represent real state
- Shimmer effects
- Pulsing loading indicators
- Spinners that don't map to actual async operations

---

## Deterministic ID Generation

All SVG elements created during startup must use the `svgId` utility:

```javascript
function svgId(prefix, ...components) {
  const parts = [String(prefix), ...components.map(c => String(c))];
  const combined = parts.join('|');
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `svg-${prefix}-${Math.abs(hash).toString(16).padStart(8, '0')}`;
}
```

This ensures:
1. Same inputs always produce same ID
2. IDs are bounded in length (max 20 chars)
3. IDs are valid CSS selectors
4. Replay produces identical DOM structure

---

## Workspace State Restoration

### Startup State Sources (in priority order)
1. **Explicit saved workspace** - From `workspace.json` in `.rig/`
2. **Git worktree state** - From git status and worktree configuration
3. **Default empty workspace** - Fresh runtime with default lane configuration

### Restoration Determinism
- Same workspace path always restores to same visual state
- Same Git state always produces same topology
- Widget positions are restored exactly
- Disclosure states are restored exactly
- No "welcome tour" on restore - workspace picks up where it left off

### First-Time Startup
If no saved workspace exists:
1. Create default lane configuration (8 lanes max)
2. Show runtime overview widget at top-left
3. Show topology panel at center
4. Show status card at bottom-left
5. Do NOT show onboarding automatically - user must invoke it

---

## Instrumentation Initialization

### SVG Primitive Registry
- Loaded first, before any visualization code
- All primitives registered with deterministic IDs
- Maximum 500 primitives (bounded)
- Primitive order is deterministic (sorted by sequence, then priority)

### Topology Plugin Model
- Initialized after primitive registry
- Plugins registered in deterministic order
- Each plugin has lane scope, disclosure layer, density priority
- No plugin may modify startup sequencing

### DTG Visualization
- DTG nodes and edges use deterministic ID generation
- Initial DTG state is empty
- DTG populates as projections arrive
- No startup animation for DTG elements

---

## Error Handling During Startup

### Subsystem Failure
If a subsystem fails to initialize:
1. Show its name with "failed" status (red text, no color animation)
2. Show error code and message as static text
3. Continue with remaining subsystems
4. Do NOT block on any single subsystem
5. Do NOT show retry animation

### Partial Startup
If some subsystems fail:
- Render what IS available
- Missing subsystems show as "unavailable" in status
- User can still interact with available features
- No degraded visual state (half-opacity, etc.) - either it works or it doesn't

### Complete Failure
If core runtime fails:
- Show single static error message
- Include error code, message, and timestamp
- Provide manual restart option
- Do NOT auto-retry
- Do NOT show animated error state

---

## Startup Telemetry

### What IS Instrumented
- Subsystem initialization duration
- Topology wake-up duration
- Workspace restoration duration
- Primitive registry population count
- Plugin registration count

### What is NOT Instrumented
- No "startup performance score"
- No user-facing progress percentages
- No "optimizing" messages
- No synthetic benchmarks

### Telemetry Display
- Telemetry appears in debug mode only
- Format: static text, `[SUBYSTEM] ready in XXms`
- No animation, no fade
- Appended to debug log, not shown in UI

---

## Compliance Checklist

- [ ] No fake loading indicators
- [ ] No synthetic progress bars
- [ ] No decorative animation during startup
- [ ] All visual elements map to real runtime state
- [ ] Subsystem initialization is reported textually, not visually
- [ ] Startup is identical with reduced motion
- [ ] All IDs are deterministic
- [ ] Workspace restoration is deterministic
- [ ] First-time startup has no automatic onboarding
- [ ] Error states are static, not animated

---

## See Also

- [Workspace Composition System](./workspace-composition.md) - Layout and widget system
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Information hierarchy
- [Governed Motion Doctrine](./governed-motion.md) - Motion constraints
- [Visualization Lifecycle](./visualization-lifecycle.md) - Component lifecycle
- [Replay-Safe Extension Model](./replay-safe-extension-model.md) - Replay guarantees
