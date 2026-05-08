# Visual Semantic Normalization

## Summary

This document audits and canonically normalizes all visual semantics across Rig's SVG instrumentation. The goal is to ensure that a contributor can infer runtime meaning from visual structure alone, without needing to consult documentation or inspect code.

**Core Doctrine:**
- One meaning per visual property
- One visual property per meaning
- Consistent mapping across all widgets
- Deterministic and replay-safe
- Derived from projection state only

---

## Visual Property Taxonomy

Every visual element in Rig maps to exactly one runtime meaning through a well-defined, bounded transformation.

### Property Categories

| Category | Properties | Source | Bounds |
|----------|------------|--------|--------|
| Color | fill, stroke | execution state, capability, integrity | Fixed palette |
| Size | width, height, radius | throughput, buffer pressure, load | Min/max clamped |
| Position | x, y | sequence, depth, lane | Viewport clamped |
| Opacity | opacity | activity level, importance | 0.1 to 1.0 |
| Shape | path, polygon | node kind, state | Fixed shapes |
| Stroke | width, dash | connections, routing | Fixed widths |
| Motion | transform | sequence progression | Bound to state change |

---

## Canonical Color Palette

### Normalized Color Mapping

All color meanings use a single, consistent palette. Colors MUST NOT vary between widgets for the same semantic meaning.

#### Execution State Colors

| State | Hex | CSS Variable | Usage |
|-------|-----|--------------|-------|
| Idle | #9E9E9E | `--color-idle` | Inactive execution |
| Planning | #2196F3 | `--color-planning` | Planning phase |
| Streaming | #2196F3 | `--color-streaming` | Active stream reception |
| Proposing | #FF9800 | `--color-proposing` | Proposal generation |
| Validating | #9C27B0 | `--color-validating` | Validation phase |
| Executing | #4CAF50 | `--color-executing` | Active execution |
| Complete | #8BC34A | `--color-complete` | Successful completion |
| Stalled | #795548 | `--color-stalled` | Blocked/waiting |
| Failed | #F44336 | `--color-failure` | Execution failure |

**Enforcement**: All SVG fill/stroke using state colors MUST use CSS variables, not hardcoded hex values.

#### Integrity State Colors

| State | Hex | CSS Variable | Usage |
|-------|-----|--------------|-------|
| Integrity OK | #4CAF50 | `--color-integrity-ok` | No violations |
| Advisory | #FFC107 | `--color-integrity-advisory` | Low severity |
| Warning | #FF9800 | `--color-integrity-warning` | Medium severity |
| Error | #F44336 | `--color-integrity-error` | High severity |
| Critical | #E91E63 | `--color-integrity-critical` | Critical violation |

#### Capability Routing Colors

| Trust Tier | Hex | CSS Variable | Usage |
|-----------|-----|--------------|-------|
| Restricted | #E91E63 | `--color-capability-restricted` | Highest risk |
| Standard | #607D8B | `--color-capability-standard` | Normal capability |
| Elevated | #FF5722 | `--color-capability-elevated` | Enhanced access |
| Trusted | #4CAF50 | `--color-capability-trusted` | Full trust |

#### Channel Colors

| Channel | Hex | CSS Variable | Usage |
|---------|-----|--------------|-------|
| Assistant | #2196F3 | `--color-channel-assistant` | Model output |
| User | #8BC34A | `--color-channel-user` | User input |
| System | #9C27B0 | `--color-channel-system` | System messages |
| Tool | #FF9800 | `--color-channel-tool` | Tool execution |
| Proposal | #FFC107 | `--color-channel-proposal` | Proposal Activity |

---

## Stroke Width Normalization

### Normalized Stroke Widths

All line widths use one of four canonical values:

| Width | Value | Usage |
|-------|-------|-------|
| Thin | 1px | Grid lines, secondary connections |
| Normal | 1.5px | Primary connections, default edges |
| Thick | 2px | Emphasized connections, active paths |
| Heavy | 3px | Sandbox boundaries, critical separators |

**Constants** (from `svg-runtime-instrumentation.js`):
```javascript
const STROKE_WIDTH_THIN = 1;
const STROKE_WIDTH_NORMAL = 1.5;
const STROKE_WIDTH_THICK = 2;
const STROKE_WIDTH_HEAVY = 3;
```

### Stroke Width by Semantic

| Semantic | Width | Rationale |
|----------|-------|-----------|
| Grid lines | Thin | Background visualization |
| Stream density lines | Thin | Lightweight data flow |
| Throughput bar outlines | Thin | Boundary definition |
| Routing paths (inactive) | Normal | Standard connection |
| Routing paths (active) | Thick | Emphasize active flow |
| Execution lane boundaries | Thick | Separate execution contexts |
| Sandbox isolation boundaries | Heavy | Critical safety separation |
| Integrity violation markers | Thick | High visibility for errors |

---

## Line Weight Semantics

### Line Weight = Authority + Trust

In Rig, line weight (stroke-width) encodes authority boundaries and trust levels:

| Weight | Authority | Trust | Color | Usage |
|--------|-----------|-------|-------|-------|
| 1px | Advisory | Low | Channel color | Candidate connections |
| 1.5px | Normal | Medium | Channel color | Standard routing |
| 2px | Strong | High | Trust tier color | Active capability routes |
| 3px | Hard | Critical | Boundary color | Sandbox isolation |

**Rule**: Thicker lines = stronger boundaries, higher authority.

### Line Style Semantics

| Style | Meaning | Usage |
|-------|---------|-------|
| Solid | Active/confirmed | Established connections |
| Dashed | Planned/proposed | Pending routing |
| Dotted | Historical | Replay paths |
| Dash-dot | Advisory | Suggested connections |

---

## Spacing Scale Normalization

### Spacing Constants

```javascript
const SPACING = {
  XS: 4,      // Tight grouping
  SM: 8,      // Standard gap
  MD: 16,     // Section separation
  LG: 24,     // Major grouping
  XL: 32,     // Panel-level spacing
  XXL: 48     // Top-level layout
};
```

### Spacing by Context

| Context | Spacing | Usage |
|---------|---------|-------|
| Node internal padding | 4px | Between elements within a node |
| Node-to-node gap | 8px | Within a lane |
| Lane-to-lane gap | 12px | Between execution lanes |
| Widget internal | 16px | Within widget cards |
| Widget-to-widget | 24px | Between dashboard widgets |
| Section-level | 32px | Between major UI sections |
| Page-level | 48px | Around main content areas |

---

## Pulse Cadence Semantics

### Pulse = Throughput Activity

Pulsing animations represent data flowing through the system. The pulse cadence is directly tied to throughput.

**Formula** (from `telemetry-scaling-semantics.md`):
```
pulse_frequency_hz = 0.5 + (throughput_normalized * 3.5)
// Range: 0.5 Hz (idle) to 4.0 Hz (saturated)
```

### Pulse Visual Properties

| Throughput | Frequency | Opacity Range | Shape |
|------------|-----------|---------------|-------|
| 0-25% | 0.5-1.25 Hz | 0.3-0.7 | Circle |
| 25-50% | 1.25-2.0 Hz | 0.3-0.8 | Circle |
| 50-75% | 2.0-3.0 Hz | 0.3-0.9 | Circle |
| 75-100% | 3.0-4.0 Hz | 0.3-1.0 | Circle |

**Implementation**: CSS opacity animation with duration derived from frequency:
```css
@keyframes svg-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: [calculated_max]; }
}

.pulse-indicator {
  animation: svg-pulse [duration]ms ease-in-out infinite;
}
```

---

## Replay Sweep Semantics

### Sweep = Replay Progression

The replay sweep arc shows progress through a replay session.

**Formula**:
```
angle_degrees = (current_sequence / total_sequences) * 360
```

### Sweep Visual Properties

| Property | Value | Rationale |
|----------|-------|-----------|
| Color | #00BCD4 | Replay-specific, distinct from execution |
| Width | 2px | Visible but not overwhelming |
| Cap | Round | Smooth appearance |
| Start angle | -90° (top) | Conventional clock-like sweep |
| Direction | Clockwise | Consistent with scrub direction |

---

## Routing Line Semantics

### Routing Lines = Capability Flow

Routing lines show the path of context as it flows through capability lanes.

### Line Properties by State

| State | Width | Style | Color | Opacity |
|-------|-------|-------|-------|--------|
| Idle | 1px | Dashed | Capability color | 0.4 |
| Active | 2px | Solid | Capability color | 0.8 |
| Complete | 1.5px | Solid | Capability color | 0.6 |
| Failed | 2px | Solid | #F44336 | 1.0 |
| Stalled | 1.5px | Dotted | Capability color | 0.5 |

### Arrow Semantics

All routing lines end with directional arrows:

| Arrow Type | Usage | Size | Color |
|------------|-------|------|-------|
| Forward | Source → Target | 10x10 | Inherits line color |
| Reverse | Target ← Source | 10x10 | Inherits line color |
| Bidirectional | Two-way flow | 10x10 each | Inherits line color |

**SVG Marker Definition**:
```xml
<marker id="svg-arrowhead" viewBox="0 0 10 10" refX="9" refY="5"
        markerWidth="10" markerHeight="10" orient="auto-start-reverse">
  <path d="M 0 0 L 10 5 L 0 10 Z" fill="context-stroke" />
</marker>
```

---

## Integrity Interruption Semantics

### Interruption = Violation Detected

Integrity violations are visualized as interruptions (gaps, markers) in the execution flow.

### Interruption Types

| Severity | Shape | Size | Color | Animation |
|----------|-------|------|-------|-----------|
| Advisory | Triangle (up) | 6px | #FFC107 | None |
| Warning | Triangle (down) | 8px | #FF9800 | None |
| Error | Circle | 10px | #F44336 | None |
| Critical | Circle with pulse | 12px | #E91E63 | Pulse at 2Hz |

### Interruption Placement

Interruption markers are placed along the execution path at the exact position corresponding to the violation sequence:

```javascript
const markerX = sequenceToX(violation.sequence, maxSequence);
const markerY = laneToY(violation.laneIndex);
```

---

## Topology Hierarchy

### Hierarchy = Authority Nesting

Topology visualizes the hierarchical structure of execution authority:

```
Root (Runtime)
├── Lane (Capability Group)
│   ├── Node (Execution Step)
│   │   ├── Proposal (Candidate Action)
│   │   └── Decision (Committed Action)
│   └── Router (Context Gateway)
└── Supervisor (Governance)
```

### Visual Hierarchy Encoding

| Level | Depth | Y Position | Shape | Size |
|-------|-------|------------|-------|------|
| Root | 0 | Top | Circle | 48px |
| Lane | 1 | Down | Rounded Rect | 100% width |
| Node | 2 | Down | Diamond | 44px |
| Proposal | 3 | Down | Square | 40px |
| Decision | 4 | Down | Hexagon | 44px |
| Supervisor | Any | Above | Star | 40px |

---

## Visual Priority Ordering

### Priority Determines Rendering Order

SVG elements are rendered in layers, with higher priority elements painted last (on top):

| Priority | Layer | Z-Index | Elements |
|----------|-------|---------|-------|
| 1 (Lowest) | Background | -100 | Lanes, grid |
| 2 | Connections | 0 | Routing paths, edges |
| 3 | Nodes | 100 | Execution nodes, proposals |
| 4 | Markers | 200 | Integrity markers, replay anchors |
| 5 | Labels | 300 | Text labels, sequence numbers |
| 6 | Overlays | 400 | State indicators, boundaries |

**Implementation**: SVG `<g>` elements with z-index via DOM order:
```xml
<svg>
  <g class="layer-background"> ... </g>
  <g class="layer-connections"> ... </g>
  <g class="layer-nodes"> ... </g>
  <g class="layer-markers"> ... </g>
  <g class="layer-labels"> ... </g>
  <g class="layer-overlays"> ... </g>
</svg>
```

---

## Normalization Checklist

All existing instrumentation has been audited and normalized:

- [ ] All color mappings use canonical CSS variables
- [ ] All stroke widths use one of four canonical values
- [ ] All line styles (solid/dashed/dotted) have defined semantics
- [ ] All spacing uses canonical spacing constants
- [ ] All pulse cadences derive from throughput formula
- [ ] All replay sweep angles derive from sequence formula
- [ ] All routing line properties derive from connection state
- [ ] All integrity interruptions derive from violation severity
- [ ] All hierarchy levels have defined visual properties
- [ ] All rendering uses consistent layer ordering

---

## Known Incoherencies (to be resolved in Phase 10)

The following have been identified and will be addressed in the final convergence audit:

1. **Color Consistency**: Some hardcoded hex values remain in widget files - migrate to CSS variables
2. **Animation Timing**: Some fixed animation durations exist - migrate to state-derived timing
3. **Padding Inconsistencies**: Some widgets use inline padding values - migrate to SPACING constants
4. **Label Font Sizes**: Font sizes vary slightly between widgets - normalize to canonical sizes

---

## Convergence Target

**Goal**: A contributor can open any SVG instrumentation file and understand the runtime meaning of any visual element by reading only this document and the visual element itself.

**Test**: Show any SVG element to a new contributor. They should be able to:
1. Identify the visual properties (color, size, position, shape, etc.)
2. Map those properties to runtime meaning using this document
3. Verify that meaning by inspecting the projection data

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial visual semantic normalization specification |
