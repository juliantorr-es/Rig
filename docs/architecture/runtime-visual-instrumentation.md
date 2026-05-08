# Runtime Visual Instrumentation Architecture

> **PHASE 8: Truthful Runtime VisualInstrumentation Doctrine**
> SVG-Based Runtime Observability Layer

---

## Table of Contents

1. [Overview](#overview)
2. [Core Doctrine](#core-doctrine)
3. [Architecture Principles](#architecture-principles)
4. [SVG Instrumentation Substrate](#svg-instrumentation-substrate)
5. [Runtime Topology Visualization](#runtime-topology-visualization)
6. [Truthful Stream Visualization](#truthful-stream-visualization)
7. [Replayable SVG Motion Semantics](#replayable-svg-motion-semantics)
8. [Integrity Instrumentation](#integrity-instrumentation)
9. [Capability Routing Visualization](#capability-routing-visualization)
10. [Stateful SVG Loading System](#stateful-svg-loading-system)
11. [Projection-to-Geometry Mapping](#projection-to-geometry-mapping)
12. [Visual Design Language](#visual-design-language)
13. [Animation Doctrine](#animation-doctrine)
14. [Deterministic Rendering](#deterministic-rendering)
15. [Replay-Safety Guarantees](#replay-safety-guarantees)
16. [Implementation Details](#implementation-details)
17. [Validation & Testing](#validation--testing)
18. [Non-Goals](#non-goals)

---

## Overview

This document describes **Phase 8: Runtime Visual Instrumentation** of Rig's Runtime & Agent Execution Plane.

The frontend evolves from a projection-based display into a **deterministic SVG instrumentation layer** that faithfully represents runtime state through geometric, operational visualizations.

### Key Transformation

| Prior State | Current State |
|-------------|---------------|
| Text-based projections only | Text + SVG instrumentation |
| Generic progress indicators | Stateful SVG loaders |
| Implicit sequence ordering | Explicit geometry mapping |
| Decorative styling | Operational visual language |
| Hidden state | DOM-addressable elements |

### Vision Statement

> **Every pixel of visualization must be traceable to a deterministic, observable runtime event.**
> <br>
> SVG geometry derives ONLY from backend/replay state via projection contracts.

---

## Core Doctrine

### The Five Pillars

1. **TRUTHFUL**: All visualizations derive from real, observable runtime state
2. **DETERMINISTIC**: Same backend state = same visualization (replay-safe)
3. **BOUNDED**: All buffers, states, and visualizations have explicit size limits
4. **PROJECTION-ONLY**: Frontend consumes only projections, never raw subprocess state
5. **DOMAIN-ADDRESSABLE**: Every SVG element is queryable via deterministic IDs

### Non-Negotiable Invariant

> **Animations derive ONLY from:**
> - websocket events
> - projection state
> - sequence progression
> - runtime throughput
> - replay state
> - capability routing state
> - integrity state

**NOT from:**
- Timers
- Arbitrary motion loops
- Synthetic "AI vibes"
- Decorative particle systems
- CSS animations without state basis

### Authority Principle

- **Backend is the source of truth**: All state originates from runtime events
- **Frontend is a faithful mirror**: UI reflects, never infers or predicts
- **Projections are authoritative contracts**: Only projection-backed data is rendered
- **Receipts define authority**: Only receipts become authoritative evidence

---

## Architecture Principles

### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (Authority)                            │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │
│  │   Streams    │   │ Projections  │   │  Registry    │          │
│  │ (Raw Events) │──▶│ (Contracts)  │──▶│ (Receipts)   │          │
│  └──────────────┘   └──────────────┘   └──────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ WebSocket (Normalized)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND (Projection-Only)                       │
│  ┌─────────────────────┐   ┌─────────────────────┐                │
│  │   SVG Primitive     │   │   Widget Layer       │                │
│  │   Substrate         │   │ (Semantic Rendering)│                │
│  │ - Execution Lanes   │───▶│ - Topology Panel    │                │
│  │ - Routing Paths     │   │ - Stream Card       │                │
│  │ - Stream Density    │   │ - Status Card       │                │
│  │ - Throughput Bars   │   │ - Proposal Card     │                │
│  │ - Replay Sweeps     │   │ - Console Panel     │                │
│  │ - Integrity Markers  │   │ - Execution Panel    │                │
│  │ - Proposal Nodes    │   │                    │                │
│  │ - Topology Connect. │   │                    │                │
│  └─────────────────────┘   └─────────────────────┘                │
│                                                                     │
│  ┌─────────────────────┐   ┌─────────────────────┐                │
│  │ Geometry Mapper      │   │ Instrumentation      │                │
│  │ (Deterministic)      │   │ Layer Manager        │                │
│  └─────────────────────┘   └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Constraints

| Constraint | Purpose |
|-----------|---------|
| No timers as authority | Prevents fake motion disconnected from runtime |
| No setInterval/setTimeout for state | State must derive from events |
| No CSS animations without state basis | Motion must be truthful |
| No canvas for core visualization | Ensures accessibility and determinism |
| No hidden frontend state | All state must be observable from projections |
| No authority inference | UI never assumes runtime intent |
| No direct backend mutation | Widgets never trigger actions |
| SVG-only for instrumentation | DOM-addressable, deterministic rendering |

---

## SVG Instrumentation Substrate

### Module: `svg-runtime-instrumentation.js`

The core substrate providing deterministic SVG primitives for runtime visualization.

#### SVG Primitive Classes

| Class | Purpose | Geometry |
|-------|---------|----------|
| `SvgExecutionLane` | Visualizes execution channels | Horizontal lanes with throughput |
| `SvgRoutingPath` | Shows capability routing | Bezier curves with direction arrows |
| `SvgStreamDensityLine` | Visualizes chunk flow | Variable-width paths |
| `SvgThroughputBar` | Shows throughput as bar chart | Rectangular fills |
| `SvgReplaySweep` | Replay progression indicator | Circular progress arcs |
| `SvgIntegrityMarker` | Integrity state markers | Shapes (circle, triangle, square) with severity colors |
| `SvgProposalNode` | Proposal lifecycle visualization | Geometric shapes (circle, diamond, polygon) |
| `SvgTopologyConnector` | Node-to-node connections | Lines with state indicators and arrows |
| `SvgStatefulLoader` | Stateful loading indicators | Radial progress with state shapes |

#### Geometry Helpers

| Function | Purpose |
|----------|---------|
| `point(x, y)` | Create deterministic coordinate |
| `rect(x, y, w, h)` | Create bounding rectangle |
| `size(w, h)` | Create size object |
| `centerOf(rect)` | Calculate rect center |
| `mapRange()` | Map value between ranges |
| `clamp()` | Clamp value to bounds |

#### Color Palette

```javascript
SVG_COLORS = {
  // Execution states
  EXECUTING: '#4CAF50',
  STREAMING: '#2196F3',
  PROPOSING: '#FF9800',
  VALIDATING: '#9C27B0',
  REPLAYING: '#00BCD4',
  STALLED: '#795548',
  COMPLETE: '#8BC34A',
  FAILURE: '#F44336',
  IDLE: '#9E9E9E',
  
  // Integrity states
  INTEGRITY_OK: '#4CAF50',
  INTEGRITY_WARNING: '#FFC107',
  INTEGRITY_ERROR: '#F44336',
  
  // Capability routing
  CAPABILITY_DEFAULT: '#607D8B',
  CAPABILITY_ELEVATED: '#FF5722',
  CAPABILITY_RESTRICTED: '#E91E63'
}
```

#### Bounded State

All SVG primitives are bounded:
- Maximum 500 elements per instrumentation group
- Maximum 200 path segments per path
- Maximum 100 replay sweep frames
- All buffers evict oldest entries when full

---

## Runtime Topology Visualization

### Module: `runtime-topology-panel.js`

Provides a complete visualization of runtime execution topology.

#### Component Model

**TopologyNode**: Represents a runtime component
```javascript
{
  id: string,
  kind: 'runtime' | 'capability' | 'sandbox' | 'executor' | 'validator' | 'supervisor' | 'registry',
  label: string,
  state: RuntimeInstrumentationState,
  capability: string,
  x: number, y: number,
  width: number, height: number,
  connected: boolean,
  runtimeId: string,
  provider: string,
  trustTier: string,
  sequence: number,
  selected: boolean,
  violationCount: number,
  lastActivity: number
}
```

**TopologyEdge**: Represents a connection between nodes
```javascript
{
  id: string,
  sourceId: string,
  targetId: string,
  kind: 'stream' | 'control' | 'data' | 'event',
  state: string,
  capability: string,
  sequence: number,
  bytesTransferred: number,
  tokensTransferred: number,
  active: boolean,
  bidirectional: boolean
}
```

**RuntimeTopologyState**: Manages complete topology state

#### Visualization Layers (Render Order)

1. **Execution Lanes** (Background): Horizontal bands representing logical execution channels
2. **Routing Paths**: Curved paths showing capability routing between nodes
3. **Topology Connectors**: Direct connections between specific nodes
4. **Nodes**: Runtime components with state-based colors
5. **Proposals**: Proposal nodes positioned by sequence
6. **Integrity Markers**: Warning/error indicators at specific sequence positions
7. **Replay Sweep** (if active): Progress indicator for replay visualization
8. **Stream Density Lines**: Visual representation of chunk flow density
9. **Throughput Bars**: Bar chart showing current throughput per lane

---

## Truthful Stream Visualization

### Enhanced `runtime-stream-card.js`

Stream card now includes SVG-based truthful visualization.

#### SVG Visualization Components

1. **Stream Density Line**: Shows the flow of chunks across the sequence space
   - Intensity derived from token count relative to expected maximum
   - Color derived from channel type
   - Sequence labels at endpoints

2. **Throughput Bar**: Real-time throughput visualization
   - Width derived from current tokens/second
   - Color derived from channel
   - Always bounded by max expected throughput

3. **Sequence Progress Sweep**: Shows progression through expected sequence
   - Arc progress derived from current sequence / max sequence
   - Color changes based on state (streaming, replaying, stalled)
   - Reconstructed marker for replay scenarios

4. **Integrity Markers**: Violation/warning indicators at specific sequence positions
   - Position derived from violation sequence number
   - Shape and color derived from severity

---

## Replayable SVG Motion Semantics

### State-to-Motion Mapping

All animation derives from projection state, NOT from timers.

| Runtime State | SVG Motion | Visual Metaphor |
|---------------|------------|-----------------|
| `streaming` | Flow density line, throughput bar growth | Flowing water |
| `proposing` | Proposal node pulse, diamond shape | Decision point |
| `validating` | Checkmark shape, rotating/validating indicator | Validation in progress |
| `replaying` | Replay sweep arc progression | Clockwise sweep |
| `stalled` | Dashed/low-opacity elements, horizontal bar | Paused/stopped |
| `complete` | Complete checkmark, full progress | Success |
| `failure` | X mark, error color | Failure |
| `idle` | Empty/minimal indicator | Waiting |

### Animation Timing

All timing is derived from state transitions, NOT arbitrary:

```javascript
ANIMATION = {
  STREAM_FLOW_DURATION: '200ms',    // Derived from chunk arrival rate
  PROPOSAL_PULSE_DURATION: '300ms', // Derived from proposal lifecycle
  REPLAY_SWEEP_DURATION: '150ms',   // Derived from replay frame rate
  INTEGRITY_FLASH_DURATION: '200ms',// Derived from warning state
  STATE_TRANSITION_DURATION: '150ms' // Derived from state change
}
```

### Replay Determinism

Replay visualization is guaranteed to be deterministic:

1. **Same projection state → Same geometry**
   - All coordinates derived from projection via ProjectionGeometryMapper
   - Deterministic ID generation using svgId()
   - Bounded buffers ensure consistent ordering

2. **Replay-safe ordering**
   - Sequence numbers preserve order
   - Replay sweep progress is reconstructable from sequence
   - Integrity markers positioned by sequence

3. **Reconstructed state visualization**
   - Tilde (~) prefix on reconstructed sequence numbers
   - "reconstructed" label on replay indicators
   - Visual distinction from live data

---

## Integrity Instrumentation

### Visualization Types

| Integrity State | Shape | Color | Indicator |
|----------------|-------|-------|-----------|
| OK | Circle | Green | None (implicit) |
| Warning | Triangle | Yellow/Orange | Outer ring |
| Error | Square | Red | Outer ring + X |
| Fracture | Circle + diagonal line | Red | Discontinuity marker |
| Discontinuity | Circle + diagonal line | Red | Path break |

### Marker Placement

Integrity markers are positioned deterministically based on:
- Sequence number of the violation
- Lane assignment via hash of violation code
- Geometry mapper translation to coordinates

### Severity Levels

- **Critical**: Red fill, high opacity, large size
- **Error**: Red fill, medium opacity, medium size
- **Warning**: Yellow fill, medium opacity, medium size
- **Info**: Neutral color, low opacity, small size

---

## Capability Routing Visualization

### Routing Path State

| State | Color | Line Style | Arrow |
|-------|-------|------------|-------|
| Connected | Capability color | Solid | Active |
| Active | Highlighted | Solid, thick | Animated |
| Disconnected | Red | Dashed | None |
| Degraded | Yellow | Dashed | Warning |
| Reconnecting | Cyan | Dotted | Reconnecting |

### Capability Colors

| Capability Tier | Color | Usage |
|-----------------|-------|-------|
| Default | #607D8B | Standard runtime |
| Elevated | #FF5722 | Elevated trust/risk |
| Restricted | #E91E63 | Restricted capability |

### Trust Level Indicators

Trust level is visualized through:
- Line thickness (higher trust = thicker, more prominent)
- Arrow size (higher trust = larger arrow)
- Color intensity (higher trust = more saturated)

---

## Stateful SVG Loading System

### SvgStatefulLoader

Replaces generic spinning loaders with stateful indicators.

#### States

| State | Shape | Motion | Color |
|-------|-------|--------|-------|
| idle | Empty circle | None | Gray |
| streaming | Triangle (flow) | Pulsing dot | Blue |
| proposing | Diamond | None (static) | Orange |
| validating | Checkmark path | None | Purple |
| replaying | Double arrow | Sweep progression | Cyan |
| stalled | Horizontal line | None | Brown |
| error/failure | X mark | None | Red |
| complete | Checkmark | None | Green |

#### Deterministic Progress

For determinate loading (known total):
- Progress arc fills clockwise from top
- Percentage label in center
- Sequence counter (current/total)

For indeterminate loading (unknown total):
- Pulsing dot indicator
- State-based shape
- No progress arc

---

## Projection-to-Geometry Mapping

### ProjectionGeometryMapper

Maps projection state to SVG coordinates deterministically.

#### Mapping Functions

```javascript
// Map sequence number to X coordinate
sequenceToX(sequence, maxSequence) -> x

// Map lane index to Y coordinate
laneToY(laneIndex) -> y

// Map lane index to full bounds
laneToBounds(laneIndex) -> {x, y, width, height}

// Map throughput to bar width
throughputToWidth(throughput, maxThroughput) -> width

// Get deterministic position for proposal
getProposalPosition(proposalOrId, laneIndex, sequence) -> {x, y}

// Get deterministic position for integrity marker
getIntegrityPosition(markerOrId, laneIndex, sequence) -> {x, y}

// Get density line points
getDensityPoints(startSeq, endSeq, laneIndex, maxSequences) -> Point[]

// Map replay progress to position
progressToSweepPosition(progress) -> {x, y}
```

#### Deterministic Hashing

```javascript
// Used for deterministic positioning when explicit coordinates not provided
_hashString(str) -> number {
  let hash = 0;
  for (char of str) {
    hash = ((hash << 5) - hash) + char.charCodeAt(0);
    hash = hash & hash;
  }
  return Math.abs(hash);
}
```

---

## Visual Design Language

### Aesthetic Foundations

**Inspirations:**
- IBM Systems Manuals (geometric clarity)
- Braun Industrial Instrumentation (functional beauty)
- Bauhaus (geometry-first)
- Terminal-era operational systems (dense, readable)
- Observability dashboards (information density)
- Distributed systems telemetry (state clarity)
- Control-room instrumentation (critical visibility)

**Design Principles:**
- **Geometric**: All shapes are simple, regular polygons
- **Restrained**: No unnecessary decoration
- **Operational**: Designed for readability at a glance
- **Instrumentation-oriented**: Every element has a purpose
- **Vector-first**: SVG ensures crisp rendering at any scale
- **Terminal-era**: Monospace integration, high contrast

### Color Semantics

| Category | Colors | Meaning |
|----------|--------|---------|
| Execution | Blue, Green, Orange, Purple | Active runtime states |
| Integrity | Green, Yellow, Red | Health/violation states |
| Capability | Gray, Orange-Red, Pink | Trust/risk levels |
| Neutral | Gray, White, Black | Background/framing |

### Line Semantics

| Line Type | Weight | Style | Meaning |
|-----------|--------|-------|---------|
| Grid | 1px | Dashed | Visual guides, boundaries |
| Connection | 1.5px | Solid | Standard connections |
| Active Connection | 2px | Solid | Active data flow |
| Emphasis | 3px | Solid | High importance |

### Shape Semantics

| Shape | Meaning | Context |
|-------|---------|---------|
| Circle | Neutral/ready state | Nodes, indicators |
| Triangle | Directional/flow | Streaming, direction |
| Square | Stable/established | Error states, nodes |
| Diamond | Decision/choice | Proposals, routing |
| Line | Connection/flow | Edges, connectors |
| Polygon | Multi-faceted state | Complex status |

---

## Animation Doctrine

### Core Principle

> **Animation must derive from real runtime state, never from synthetic sources.**

### Derivation Rules

1. **Motion is state-derived**: Animation parameters (speed, direction, intensity) come from projection data
2. **No timer authority**: `setTimeout` and `setInterval` must NEVER be the primary source of motion
3. **Replay-safe**: Same state sequence = same animation sequence
4. **Bounded**: All animations have explicit duration limits
5. **Deterministic**: Animation state is function of (runtime_state, timestamp, sequence)

### Animation State Derivation

```javascript
class SvgAnimationState {
  deriveFromProjection(projection): {motion, intensity, direction} {
    switch (projection.state) {
      case 'streaming':
        return {
          motion: 'stream',
          intensity: clamp(delta / 200, 0, 1),  // Based on time since last event
          direction: 'forward'
        };
      case 'proposing':
        return {
          motion: 'pulse',
          intensity: 0.7,
          direction: 'none'
        };
      // ... etc
    }
  }
}
```

---

## Deterministic Rendering

### Guarantees

1. **Deterministic IDs**: All SVG elements have IDs generated from content via `svgId(prefix, ...components)`
2. **Deterministic Geometry**: All positions calculated from projection state via ProjectionGeometryMapper
3. **Deterministic Coloring**: All colors derived from state, not random or time-based
4. **Deterministic Ordering**: Render order follows specific priority (lanes → paths → nodes → markers)

### ID Generation

```javascript
function svgId(prefix, ...components) {
  const combined = [prefix, ...components].join('|');
  // Hash function
  let hash = 0;
  for (char of combined) {
    hash = ((hash << 5) - hash) + char.charCodeAt(0);
    hash = hash & hash;
  }
  return `svg-${prefix}-${Math.abs(hash).toString(16).substring(0, 8)}`;
}
```

### DESYNC Rendering

To ensure replay-safety:
1. Always clear and re-render from scratch on state updates
2. Never incrementally update geometry (avoids drift)
3. Recalculate all positions from current projection state
4. Use bounded buffers to prevent memory issues

---

## Replay-Safety Guarantees

### Contract

> **Given the same sequence of projection states, the SVG visualization will be pixel-perfect identical.**

### mechanisms

1. **Pure Functions**: All geometry calculation are pure functions of projection state
2. **No Hidden State**: No internal state that isn't derived from projections
3. **Deterministic ID Generation**: Element IDs based on content hashes
4. **Bounded Buffers**: Fixed-size buffers evict oldest entries predictably
5. **Stateless Rendering**: Each render is a pure function of current projection

### Validation

Replay-safety is validated by:
- Rendering same projection twice produces identical SVG (byte-for-byte)
- Replaying stored projections produces identical visual output
- Sequence numbers map deterministically to coordinates

---

## Implementation Details

### File Structure

```
src/rig_tools/static/js/
├── svg-runtime-instrumentation.js   # SVG primitives, geometry mapping
└── widgets/
    ├── runtime-topology-panel.js    # Topology visualization
    ├── runtime-stream-card.js        # Stream with SVG visualization
    ├── runtime-console-card.js       # Console with SVG markers
    ├── runtime-status-card.js        # Status with SVG indicators
    ├── runtime-proposal-card.js      # Proposals with SVG nodes
    └── runtime-execution-panel.js    # Execution with SVG lanes
```

### Module Dependencies

```javascript
// svg-runtime-instrumentation.js (core)
- No external dependencies
- Pure JavaScript ES6 modules
- Uses document.createElementNS() for SVG

// runtime-topology-panel.js
- Imports: SvgExecutionLane, SvgRoutingPath, SvgProposalNode, etc.
- From: '../svg-runtime-instrumentation.js'
- Also imports: RuntimeInstrumentationState from '../runtime-instrumentation.js'

// runtime-stream-card.js
- Imports: SvgThroughputBar, SvgStreamDensityLine, SvgReplaySweep, etc.
- From: '../svg-runtime-instrumentation.js'
- Enhanced with SVG container and _renderSvgStreamVisualization()
```

### Styling

SVG elements use CSS custom properties for colors:

```css
:root {
  /* Execution states */
  --color-executing: #4CAF50;
  --color-streaming: #2196F3;
  --color-proposing: #FF9800;
  --color-validating: #9C27B0;
  --color-replaying: #00BCD4;
  --color-stalled: #795548;
  --color-complete: #8BC34A;
  --color-failure: #F44336;
  --color-idle: #9E9E9E;
  
  /* Integrity states */
  --color-integrity-ok: #4CAF50;
  --color-integrity-warning: #FFC107;
  --color-integrity-error: #F44336;
  
  /* Neutral */
  --color-background: #1E1E1E;
  --color-foreground: #E0E0E0;
  --color-grid: #424242;
  --color-text: #CCCCCC;
  --color-text-muted: #757575;
  --color-stroke: #616161;
}
```

---

## Validation & Testing

### Test File: `tests/test_runtime_svg_instrumentation.py`

Validates:
- Deterministic geometry generation
- Replay-safe ordering
- Bounded SVG state
- Instrumentation normalization
- Runtime topology stability
- Visual sequencing determinism
- Stalled stream handling
- Integrity visualization semantics

### Test Categories

1. **Determinism Tests**: Same input produces same output
2. **Bounds Tests**: Verify element count limits
3. **Geometry Tests**: Verify coordinate calculations
4. **Projection Tests**: Verify projection → geometry mapping
5. **Replay Tests**: Verify replay produces identical visualization
6. **State Tests**: Verify state → color/shape mapping
7. **Integrity Tests**: Verify integrity marker placement

---

## Non-Goals

### Explicitly NOT Doing

| Non-Goal | Why |
|----------|-----|
| React migration | SVG + vanilla JS is sufficient, React adds complexity |
| Canvas-heavy rendering | SVG is deterministic, accessible, DOM-addressable |
| WebGL spectacle | Overkill for instrumentation, not deterministic |
| Particle systems | Synthetic motion, not state-derived |
| Random CSS motion | Cannot be replay-safe |
| Hidden frontend state | All state must be projection-derived |
| Direct runtime authority | UI never makes decisions |
| Frontend fetching | All data via WebSocket projections |
| Destructive Git commands | Never in frontend |
| Staging/committing | Never in frontend |
| Fake AI visuals | All motion must be truthful |

### Specifically Rejected Patterns

```javascript
// BAD: Timer as authority
setInterval(() => { this.progress += 0.01; }, 50);

// BAD: Arbitrary motion
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360); } }

// BAD: Random values
const color = Math.random() > 0.5 ? 'blue' : 'red';

// BAD: State inferred from DOM
data.value = element.getAttribute('data-value');

// GOOD: State from projection
const progress = projection.sequence / projection.maxSequence;
```

---

## Conclusion

Rig's Runtime Visual Instrumentation provides a **truthful, deterministic, replay-safe** SVG-based visualization layer for runtime observability. Every visual element is:

1. **Authored by backend projections**
2. **Mapped deterministically to geometry**
3. **Rendered via accessible SVG**
4. **Bounded and replay-safe**
5. **Semantically meaningful**

This ensures Rig's frontend serves as a **faithful mirror** of runtime state, never inferring, predicting, or synthesizing behavior that doesn't exist in the actual runtime.
