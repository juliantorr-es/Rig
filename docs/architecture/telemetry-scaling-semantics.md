# Telemetry Scaling Semantics

## Summary

This document canonically defines how runtime metrics map to visual semantics in Rig's SVG instrumentation layer. Every visual element's size, position, color, and motion must derive from deterministic formulas that transform backend telemetry into bounded, replay-safe visual representations.

**Core Doctrine:**
- Deterministic formulas only
- Bounded scaling in all dimensions
- Replay-safe semantics
- Operational readability
- No arbitrary animation scaling
- No nonlinear "dramatic" effects
- No fake urgency amplification

---

## Mapping Principles

### The Telemetry → Visual Pipeline

```
Runtime Telemetry → Normalization → Mapping Function → Bounded Visual Property
```

1. **Runtime Telemetry**: Raw metrics from execution (throughput bytes, stream density, replay velocity, etc.)
2. **Normalization**: Scale to 0-1 range using known bounds (min/max from projection contract)
3. **Mapping Function**: Apply deterministic formula (linear, logarithmic, stepwise)
4. **Bounded Visual Property**: Clamped result applied to SVG attribute

### Formula Requirements

All mapping formulas must satisfy:
- **Deterministic**: Same input always produces same output
- **Bounded**: Output clamped to visual range (e.g., 0-100% opacity, 0-1000px width)
- **Reversible**: Visual inspection allows inverse mapping to approximate telemetry
- **Monotonic**: Input increase never causes visual decrease (for positive metrics)

---

## Canonical Scaling Formulas

### 1. Throughput → Pulse Cadence

**Telemetry**: Bytes or tokens per second flowing through the runtime stream.

**Visual Property**: Pulse frequency (SVG circle/rect opacity oscillation)

**Formula**:
```
pulse_frequency_hz = MIN_PULSE + (throughput_bps / max_throughput) * (MAX_PULSE - MIN_PULSE)

Where:
- MIN_PULSE = 0.5 Hz (minimum visible pulse for idle state)
- MAX_PULSE = 4.0 Hz (maximum pulse for saturated throughput)
- throughput_bps = current bytes/tokens per second
- max_throughput = projection-provided maximum (default: 10000 bps)
```

**SVG Mapping**:
```javascript
// Pulse implementation using CSS opacity animation
// Duration derived from frequency
opacity_animation_duration = 1000 / pulse_frequency_hz + 'ms'
```

**Visual Bounds**:
- Minimum pulse visibility: 0.3 opacity
- Maximum pulse visibility: 1.0 opacity
- Pulse shape: 4px radius circle at stream endpoint

**Replay Behavior**: When replaying at Nx speed, pulse frequency scales by N (not clamped to real-time)

---

### 2. Stream Density → Line Density

**Telemetry**: Number of concurrent/active stream chunks in flight.

**Visual Property**: SVG path line width (thickness of stream line)

**Formula**:
```
line_width_px = BASE_WIDTH + (stream_density / max_density) * (MAX_WIDTH - BASE_WIDTH)

Where:
- BASE_WIDTH = 1.0px (minimum visible line)
- MAX_WIDTH = 6.0px (maximum line for saturated streams)
- stream_density = current active chunk count
- max_density = projection-provided maximum (default: 20 chunks)
```

**Clamping**:
```javascript
line_width_px = clamp(line_width_px, BASE_WIDTH, MAX_WIDTH)
```

**SVG Mapping**:
```xml
<path d="..." stroke="var(--stream-color)" 
      stroke-width="[line_width_px]" 
      stroke-linecap="round" />
```

**Visual Bounds**:
- Line color: Always derived from channel type (assistant, tool, user)
- Line spacing: Minimum 2px between parallel streams
- Line opacity: 0.8 for active, 0.3 for inactive

---

### 3. Replay Velocity → Sweep Velocity

**Telemetry**: Replay playback speed multiplier (1x = real-time, 10x = ten times faster).

**Visual Property**: SVG sweep arc angular velocity

**Formula**:
```
angular_velocity_deg_per_ms = (replay_speed_multiplier / MAX_REPLAY_SPEED) * MAX_ANGULAR_VELOCITY

Where:
- MAX_REPLAY_SPEED = 20x
- MAX_ANGULAR_VELOCITY = 0.5 deg/ms (180 deg/sec at 1x)
- replay_speed_multiplier = current playback speed (1.0 for real-time)
```

**SVG Mapping**:
```javascript
// Replay sweep uses SVG arc path with time-derived angle
// NOT CSS animation - arc angle computed per frame from sequence
const angle = (replay_sequence % total_sequences) / total_sequences * 360
```

**Visual Bounds**:
- Minimum arc visibility: 5% of circle (at 1x, full circle takes 20 seconds)
- Maximum arc visibility: 100% of circle (at 20x, full circle takes 1 second)
- Arc color: #00BCD4 (replay-specific color)

**Replay-Safe Guarantee**: Arc position is function of replay sequence, not wall-clock time

---

### 4. Buffer Pressure → Geometric Compression

**Telemetry**: Queue depth or backpressure indicator (0 = empty, 1 = full).

**Visual Property**: SVG node horizontal compression (width reduction)

**Formula**:
```
compression_ratio = 1.0 - (buffer_pressure / max_pressure) * MAX_COMPRESSION

Where:
- MAX_COMPRESSION = 0.7 (maximum 70% width reduction)
- buffer_pressure = current queue depth (0.0 to 1.0 normalized)
- max_pressure = projection-provided maximum (default: 1.0)
```

**SVG Mapping**:
```xml
<rect x="[x]" y="[y]" 
      width="[base_width * compression_ratio]" 
      height="[height]" 
      fill="var(--buffer-color)" />
```

**Visual Bounds**:
- Minimum node width: 20px (never disappears completely)
- Background: Dashed outline shows uncompressed bounds
- Color shift: Green (0-0.3 pressure) → Yellow (0.3-0.7) → Red (0.7-1.0)

---

### 5. Integrity Severity → Interruption Density

**Telemetry**: Number of integrity violations or warnings per time window.

**Visual Property**: SVG interruption marker frequency along execution path

**Formula**:
```
marker_spacing_px = MAX_SPACING - (violation_count / max_violations) * (MAX_SPACING - MIN_SPACING)

Where:
- MIN_SPACING = 20px (dense markers at high violation count)
- MAX_SPACING = 200px (sparse markers at low violation count)
- violation_count = current integrity warning count
- max_violations = projection-provided maximum (default: 50)
```

**Clamping**:
```javascript
marker_spacing_px = clamp(marker_spacing_px, MIN_SPACING, MAX_SPACING)
```

**SVG Mapping**:
```javascript
// Place warning triangle markers along execution path
for (let pos = 0; pos < path_length_px; pos += marker_spacing_px) {
  const marker = createSvgElement('polygon', {
    points: trianglePointsAt(pos, path_y),
    fill: integrityColor,
    class: 'integrity-marker'
  })
}
```

**Visual Bounds**:
- Marker size: 8px triangle
- Marker colors:
  - Warning: #FFC107 (amber)
  - Error: #F44336 (red)
  - Critical: #E91E63 (deep red with pulse)
- Maximum markers per path: 50 (bounded)

---

### 6. Runtime Load → Lane Saturation

**Telemetry**: Computational load of runtime lane (0.0 to 1.0 CPU utilization, or equivalent).

**Visual Property**: SVG lane fill level (vertical fill in lane bounding box)

**Formula**:
```
fill_height_px = (runtime_load / max_load) * lane_height_px

Where:
- runtime_load = current lane CPU/memory utilization (0.0 to 1.0)
- max_load = projection-provided maximum (default: 1.0)
- lane_height_px = visual lane height in pixels
```

**SVG Mapping**:
```xml
<rect x="[lane_x]" 
      y="[lane_y + lane_height - fill_height]"
      width="[lane_width]"
      height="[fill_height]"
      fill="var(--load-color)"
      opacity="0.3" />
```

**Visual Bounds**:
- Fill color: Gradient from green (#4CAF50 at 0-0.5) to red (#F44336 at 0.8-1.0)
- Fill opacity: 0.3 (allows background grid to show through)
- Outline: Lane border always visible at full opacity

**Lane States**:
| Load Range | Color | State |
|-----------|-------|-------|
| 0.0-0.3 | #4CAF50 | Idle |
| 0.3-0.6 | #8BC34A | Active |
| 0.6-0.8 | #FF9800 | Busy |
| 0.8-0.9 | #FF5722 | Saturated |
| 0.9-1.0 | #F44336 | Overloaded |

---

### 7. Routing Complexity → Topology Branching

**Telemetry**: Number of concurrent capability routes or branches in execution.

**Visual Property**: SVG branch angle spread (horizontal spread of routing paths)

**Formula**:
```
branch_angle_deg = (branch_count / max_branches) * MAX_SPREAD_ANGLE

Where:
- MAX_SPREAD_ANGLE = 60 degrees (30 degrees each side from center)
- branch_count = current active branching factor
- max_branches = projection-provided maximum (default: 10)
```

**Clamping**:
```javascript
branch_count = clamp(branch_count, 1, max_branches)
```

**SVG Mapping**:
```javascript
// Calculate branch target positions
const centerX = sourceNode.x + sourceNode.width / 2
const centerY = sourceNode.y + sourceNode.height / 2
const branchAngle = branch_angle_deg / (branch_count - 1)

for (let i = 0; i < branch_count; i++) {
  const branchAngle = ((i - (branch_count - 1) / 2) * spread_per_branch)
  const targetX = centerX + branch_length * Math.cos(branchAngle * PI / 180)
  const targetY = centerY + branch_length * Math.sin(branchAngle * PI / 180)
}
```

**Visual Bounds**:
- Minimum branch separation: 10px at target endpoints
- Branch curves: Bezier with 30% control point offset
- Branch colors: Derived from capability type, not position

---

## Deterministic Color Mapping

### Color Formula Rules

All color mappings use piecewise linear interpolation between defined stops:

```
color_value = interpolate(telemetry_normalized, stops)

Where stops is an array of [normalized_value, color_hex] pairs
```

### Canonical Color Stops

#### Execution State Colors

| State | Hex | Normalized Range |
|-------|-----|------------------|
| Idle | #9E9E9E | -inf to 0.0 |
| Planning | #2196F3 | 0.0 to 0.1 |
| Streaming | #2196F3 | 0.1 to 0.4 |
| Proposing | #FF9800 | 0.4 to 0.6 |
| Validating | #9C27B0 | 0.6 to 0.7 |
| Executing | #FF9800 | 0.7 to 0.9 |
| Complete | #8BC34A | 0.9 to 1.0 |
| Failed | #F44336 | error state |

#### Throughput Colors

| Range | Hex | Description |
|-------|-----|-------------|
| 0-25% | #4CAF50 | Low throughput, normal operation |
| 25-50% | #8BC34A | Moderate throughput |
| 50-75% | #FF9800 | High throughput |
| 75-100% | #FF5722 | Near saturation |
| 100%+ | #F44336 | Saturated/backpressured |

#### Integrity Colors

| State | Hex | Severity |
|-------|-----|----------|
| OK | #4CAF50 | None |
| Advisory | #FFC107 | Low |
| Warning | #FF9800 | Medium |
| Error | #F44336 | High |
| Critical | #E91E63 | Critical |

#### lanes

| Trust Tier | Hex | Description |
|-----------|-----|-------------|
| Restricted | #F44336 | Highest risk |
| Standard | #FF9800 | Normal capability |
| Elevated | #FF5722 | Enhanced access |
| Trusted | #4CAF50 | Full trust |

---

## Bounded Motion Formulas

### Motion Derivation Rules

**ALL motion must derive from state transitions, not timers.**

### State Transition Motion

When state changes from A to B, visual transition:
1. old_state_snapshot = capture current visual properties
2. new_state_properties = compute from new projection
3. Assign new properties immediately (NO tweening between states)

**Rationale**: Replay-safe visualization requires that state X always renders as visual Y, regardless of transition path.

### Throughput-Derived Pulsing

Pulsing animation on throughput indicators:

```javascript
// Compute pulse phase from sequence, not time
const phase = (throughput_sequence % PULSE_CYCLE_LENGTH) / PULSE_CYCLE_LENGTH
const opacity = BASE_OPACITY + Math.sin(phase * 2 * PI) * OPACITY_AMPLITUDE
```

Where:
- PULSE_CYCLE_LENGTH = 20 sequences (one full pulse cycle)
- BASE_OPACITY = 0.5
- OPACITY_AMPLITUDE = 0.5

### Replay-Sweep Motion

Sweep arc during replay:

```javascript
// Arc angle is direct function of replay sequence
const sweep_angle = (replay_sequence / total_sequences) * 360
// No easing, no tweening - direct mapping
```

---

## Projection Contract Integration

### Telemetry Fields

All telemetry values come from the projection contract:

```javascript
// RuntimeProjection contract fields used for scaling
{
  // Throughput
  bytes_per_second: number,
  tokens_per_second: number,
  max_throughput: number,
  
  // Stream density
  active_chunk_count: number,
  max_chunk_count: number,
  
  // Replay
  replay_speed: number,        // 1.0 = real-time
  replay_sequence: number,
  total_sequences: number,
  
  // Buffer/load
  buffer_pressure: number,     // 0.0 to 1.0
  cpu_utilization: number,    // 0.0 to 1.0
  memory_pressure: number,    // 0.0 to 1.0
  
  // Integrity
  violation_count: number,
  max_violations: number,
  integrity_state: string,
  
  // Routing
  branch_count: number,
  max_branches: number,
  routing_complexity: number
}
```

### Normalization in Projection

The backend projection contract provides normalized values:

```javascript
// Each metric includes its normalization bounds
{
  throughput: 5000,
  throughput_normalized: 0.5,  // relative to max_throughput = 10000
  throughput_min: 0,
  throughput_max: 10000
}
```

This allows the frontend to use normalized values directly without knowing domain-specific bounds.

---

## Forbidden Patterns

### ❌ Arbitrary Animation Scaling

```javascript
// FORBIDDEN: Easing disconnected from state
@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1.0; }  // No relationship to throughput!
}
```

```javascript
// CORRECT: State-derived pulsing
const opacity = 0.5 + (throughput_normalized * 0.5)
```

### ❌ Nonlinear "Dramatic" Effects

```javascript
// FORBIDDEN: Exponential scaling
const width = Math.pow(throughput, 2)  // Explodes at high values
```

```javascript
// CORRECT: Linear or logarithmic scaling
const width = BASE + (throughput_normalized * (MAX - BASE))
```

### ❌ Fake Urgency Amplification

```javascript
// FORBIDDEN: Artificial urgency
if (any_error) {
  flashEverythingRed()  // No proportional scaling
}
```

```javascript
// CORRECT: Proportional severity response
const color = getSeverityColor(violation_count, max_violations)
```

---

## Implementation Checklist

- [ ] All telemetry → visual mappings use deterministic formulas
- [ ] All outputs are clamped to visual bounds
- [ ] Formulas are reversible (visual allows inverse lookup)
- [ ] Monotonic relationships maintained
- [ ] No timers/browser clocks used for motion
- [ ] All motion derives from sequence/state, not time
- [ ] Replay produces identical visuals at same sequence

---

## Validation Tests

 see `tests/test_runtime_svg_instrumentation.py` for:
- `test_telemetry_scaling_determinism`
- `test_bounded_scaling`
- `test_replay_safe_scaling`
- `test_color_mapping_consistency`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial canonical telemetry scaling semantics |
