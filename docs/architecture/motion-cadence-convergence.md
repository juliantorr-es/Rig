# Motion Cadence Convergence

## Summary

This document normalizes all motion timing semantics across Rig's SVG instrumentation. Every animation, transition, and motion effect must derive from real runtime state, not arbitrary timers or decorative choices. Motion cadence is bound to runtime sequencing, throughput, replay progression, websocket event timing, and supervision cadence.

**Core Doctrine:**
- Cadence derives ONLY from runtime state
- NO arbitrary easing
- NO random animation duration
- NO decorative timing
- All motion is bounded and replay-safe
- Deterministic timing guarantees

---

## Motion Source Hierarchy

Motion in Rig is NEVER initiated by:
- setTimeout/setInterval timers
- requestAnimationFrame loops (unordered)
- CSS animations without state binding
- User hover/focus events (except UI feedback)

Motion in Rig is ALWAYS initiated by:
1. WebSocket events (primary source)
2. Projection state changes
3. Sequence progression
4. Runtime throughput changes
5. Replay scrubbing
6. Supervision cadence ticks

---

## Cadence Semantics

### Runtime Sequencing Cadence

**Source**: Discrete mechanical steps of the execution engine

**Motion**: Geometry transitions between execution states

**Timing**: Directly tied to backend state transition duration

**Formula**:
```
state_transition_duration_ms = BASEერ_TRANSITION + (state_complexity * COMPLEXITY_FACTOR)

Where:
- BASE_TRANSITION = 100ms (minimum for visibility)
- COMPLEXITY_FACTOR = 50ms (per additional complexity unit)
- state_complexity = number of concurrent state changes
```

**Example**: A single state transition (streaming → proposing) takes 100ms. Five concurrent transitions take 100 + (4 * 50) = 300ms.

**Constraints**:
- Maximum transition duration: 500ms
- Minimum transition duration: 50ms (instant for critical state changes)
- Always easing: ease-in-out (for visibility, not decoration)

### Throughput-Derived Cadence

**Source**: Volume/velocity of data traversing the system

**Motion**: Throughput visualization updates (bars, lines, pulses)

**Timing**: Derived from byte/token rate

**Formula**:
```
update_interval_ms = clamp(1000 / (throughput_bps / bytes_per_update), MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL)

Where:
- bytes_per_update = 1024 (target bytes per visual update)
- MIN_UPDATE_INTERVAL = 16ms (60fps max)
- MAX_UPDATE_INTERVAL = 250ms (4fps min for visibility)
```

**Example**:
- 1000 bps → 1000ms interval (1 update/sec)
- 10000 bps → 100ms interval (10 updates/sec)
- 100000 bps → 16ms interval (60 updates/sec max)

### Replay Progression Cadence

**Source**: Scrubbing through temporal execution trace

**Motion**: Deterministic frame-by-frame reconstruction

**Timing**: Derived from replay speed multiplier

**Formula**:
```
frame_interval_ms = BASE_FRAME_INTERVAL / replay_speed_multiplier

Where:
- BASE_FRAME_INTERVAL = 100ms (10fps at 1x speed)
- replay_speed_multiplier = current playback speed (1.0 = real-time, 10.0 = 10x)
```

**Constraints**:
- Minimum frame interval: 16ms (60fps max)
- Maximum frame interval: 1000ms (1fps min)
- Frame count always deterministic from sequence

**Replay-Safe Guarantee**: Each frame corresponds to exactly one sequence. Frame N always shows sequence N.

### WebSocket Event Cadence

**Source**: WebSocket message arrival rate

**Motion**: Real-time visualization updates

**Timing**: Event-driven (no synthetic timing)

**Implementation**:
```javascript
websocket.onmessage = (event) => {
  const projection = parseProjection(event.data);
  
  // Immediately update visualization (no buffering delay)
  updateVisualization(projection);
  
  // Debounce rapid updates
  if (Date.now() - lastUpdate < MIN_UPDATE_INTERVAL_MS) {
    queueUpdate(projection); // Schedule for next frame
  } else {
    applyUpdate(immediate); // Apply immediately
  }
};
```

**Constraints**:
- Maximum event queue: 10 messages (prevents update storm)
- Message processing order: Strictly FIFO
- Update batching: Yes, but bounded

### Supervision Cadence

**Source**: Background governance polling ticks

**Motion**: Integrity monitoring visualization (pulse, sweep)

**Timing**: Derived from supervision interval

**Formula**:
```
supervision_interval_ms = BASE_SUPERVISION_INTERVAL * trust_level_multiplier

Where:
- BASE_SUPERVISION_INTERVAL = 5000ms (5 second default)
- trust_level_multiplier:
  - RESTRICTED: 0.5 (2.5 second interval - frequent)
  - STANDARD: 1.0 (5 second interval)
  - ELEVATED: 1.5 (7.5 second interval)
  - TRUSTED: 2.0 (10 second interval)
```

**Resulting Intervals**:
| Trust Level | Interval | Supervision Frequency |
|------------|---------|----------------------|
| Restricted | 2500ms | 24 checks/minute |
| Standard | 5000ms | 12 checks/minute |
| Elevated | 7500ms | 8 checks/minute |
| Trusted | 10000ms | 6 checks/minute |

---

## Timing Doctrine

### NO Arbitrary Easing

**Forbidden**:
```javascript
// ❌ Arbitrary easing disconnected from state
transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);

// ❌ Random animation duration
animation-duration: 500ms; // Why 500ms?
```

**Allowed**:
```javascript
// ✅ State-derived timing
transition-duration: ${getStateTransitionDuration(state)}ms;

// ✅ Deterministic easing (always ease-in-out for visibility)
transition-timing-function: ease-in-out;
```

### NO Decorative Timing

Timing values must always be deriveable from runtime state:

| Scenario | Derivation | Example |
|----------|------------|---------|
| State transition | State complexity | 100-500ms |
| Throughput update | Byte rate | 16-250ms |
| Replay frame | Replay speed | 16-1000ms |
| WebSocket update | Event rate | Immediate |
| Supervision pulse | Trust level | 2500-10000ms |

### No Random Animation Duration

All animation durations are calculated from state, never hardcoded:

```javascript
// ❌ Hardcoded duration
const DURATION = 300; // 300ms - WHY?

// ✅ Derived from state
const DURATION = getTimingFromState(currentState);

function getTimingFromState(state) {
  const timings = {
    idle: 50,      // Instant for idle
    streaming: 100, // Fast for streaming
    proposing: 200, // Slightly longer for proposals
    validating: 300, // Longer for validation
    complete: 500,  // Longest for completion (impression)
    failure: 50    // Instant for failures (urgency)
  };
  return timings[state] || 100;
}
```

---

## Cadence Normalization

### Normalized Timing Constants

```javascript
const CADENCE = {
  // Base timings (minimum for visibility)
  BASE_TRANSITION: 50,
  BASE_UPDATE: 16,
  BASE_FRAME: 100,
  BASE_SUPERVISION: 5000,
  
  // Maximum timings (for performance)
  MAX_TRANSITION: 500,
  MAX_UPDATE: 250,
  MAX_FRAME: 1000,
  
  // Complexity factors
  COMPLEXITY_UNIT: 50,
  THROUGHPUT_THRESHOLD: 1024,
  
  // Replay multipliers
  MIN_REPLAY_SPEED: 0.1,
  MAX_REPLAY_SPEED: 20,
  
  // Supervision trust multipliers
  TRUST_MULTIPLIERS: {
    RESTRICTED: 0.5,
    STANDARD: 1.0,
    ELEVATED: 1.5,
    TRUSTED: 2.0
  }
};
```

### Timing Functions

```javascript
class CadenceManager {
  static getStateTransitionDuration(state, complexity = 1) {
    const baseDuration = this.getBaseDuration(state);
    const complexityFactor = Math.min(complexity, 4) * CADENCE.COMPLEXITY_UNIT;
    return Math.min(
      baseDuration + complexityFactor,
      CADENCE.MAX_TRANSITION
    );
  }
  
  static getBaseDuration(state) {
    const durations = {
      idle: CADENCE.BASE_TRANSITION,
      planning: CADENCE.BASE_TRANSITION,
      streaming: CADENCE.BASE_TRANSITION * 1.5,
      proposing: CADENCE.BASE_TRANSITION * 2,
      validating: CADENCE.BASE_TRANSITION * 3,
      replaying: CADENCE.BASE_TRANSITION,
      stalled: CADENCE.BASE_TRANSITION,
      complete: CADENCE.BASE_TRANSITION * 4,
      failure: CADENCE.BASE_TRANSITION
    };
    return durations[state?.toLowerCase()] || CADENCE.BASE_TRANSITION;
  }
  
  static getUpdateDuration(throughput_bps) {
    if (throughput_bps <= 0) return CADENCE.MAX_UPDATE;
    
    const interval = 1000 / (throughput_bps / CADENCE.THROUGHPUT_THRESHOLD);
    return Math.min(
      Math.max(interval, CADENCE.BASE_UPDATE),
      CADENCE.MAX_UPDATE
    );
  }
  
  static getReplayFrameDuration(replaySpeed) {
    const interval = CADENCE.BASE_FRAME / Math.min(replaySpeed, CADENCE.MAX_REPLAY_SPEED);
    return Math.min(
      Math.max(interval, CADENCE.BASE_UPDATE),
      CADENCE.MAX_FRAME
    );
  }
  
  static getSupervisionInterval(trustLevel) {
    const multiplier = CADENCE.TRUST_MULTIPLIERS[trustLevel?.toUpperCase()] || 1.0;
    return CADENCE.BASE_SUPERVISION * multiplier;
  }
}
```

---

## Replay Timing Guarantees

### Deterministic Playback

When replaying at any speed, the following are guaranteed:

1. **Frame Accuracy**: Each visual frame corresponds to exactly one sequence number
2. **Timing Consistency**: Same sequence always takes same time at same speed
3. **Speed Scaling**: Playback speed scales timing linearly
4. **No Skipped Frames**: No frames skipped, even at high speed (content aggregated, not dropped)

### Replay Timing Formulas

```
playback_duration_ms = total_sequences * frame_interval_ms

Where:
- frame_interval_ms = BASE_FRAME_INTERVAL / replay_speed
- BASE_FRAME_INTERVAL = 100ms
- replay_speed = playback speed multiplier
```

**Examples**:
| Sequences | Speed | Duration |
|-----------|-------|----------|
| 100 | 1x | 10 seconds |
| 100 | 2x | 5 seconds |
| 100 | 10x | 1 second |
| 1000 | 1x | 100 seconds |
| 1000 | 10x | 10 seconds |

### Scrubbing Timing

When user scrubs (not plays):

1. **Instant**: Jump to target frame instantly
2. **No Animation**: No tweening, no transition
3. **Snap**: DOM updates immediately to target state
4. **No intermediate states**: Only target state is rendered

**Implementation**:
```javascript
function scrubToSequence(targetSequence) {
  // Immediately remove all active animations
  cancelAllAnimations();
  
  // Load the exact state for target sequence
  const state = getReplayState(targetSequence);
  
  // Immediately render (no transition)
  renderState(state, { immediate: true, noAnimation: true });
  
  // Update position indicator
  updatePositionIndicator(targetSequence);
}
```

---

## Replay-Safe Animation

### Animation Practices

Animation in Rig must be:

1. **Bounded**: Maximum duration always enforced
2. **Interruptible**: Can be instantly cancelled
3. **Deterministic**: Same conditions = same animation
4. **Reversible**: Can be played forward or backward

### Animation Implementation Pattern

```javascript
class SvgAnimation {
  constructor(target, properties, options = {}) {
    this.target = target;
    this.properties = properties;
    this.duration = options.duration || CADENCE.BASE_TRANSITION;
    this.easing = options.easing || 'ease-in-out';
    this.onComplete = options.onComplete;
    this.animation = null;
    this.startTime = null;
    this.isPlaying = false;
  }
  
  start() {
    // Cancel any existing animation on this target
    this.cancel();
    
    this.startTime = Date.now();
    this.isPlaying = true;
    
    // Store original values for replay
    this.originalValues = this._getCurrentValues();
    
    // Start animation frame
    this._animate();
  }
  
  _animate() {
    if (!this.isPlaying) return;
    
    const elapsed = Date.now() - this.startTime;
    const progress = Math.min(elapsed / this.duration, 1);
    
    // Apply easing
    const easedProgress = this.applyEasing(progress, this.easing);
    
    // Apply values
    this._applyValues(easedProgress);
    
    if (progress < 1) {
      this.animation = requestAnimationFrame(() => this._animate());
    } else {
      this.isPlaying = false;
      if (this.onComplete) this.onComplete();
    }
  }
  
  cancel() {
    this.isPlaying = false;
    if (this.animation) {
      cancelAnimationFrame(this.animation);
      this.animation = null;
    }
  }
  
  applyEasing(progress, easing) {
    // Only ease-in-out is allowed (for visibility, not decoration)
    switch (easing) {
      case 'ease-in-out':
        return progress < 0.5 
          ? 2 * progress * progress 
          : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      case 'linear':
      default:
        return progress;
    }
  }
  
  _getCurrentValues() {
    const values = {};
    for (const prop in this.properties) {
      values[prop] = this.target.style[prop] || this.target.getAttribute(prop);
    }
    return values;
  }
  
  _applyValues(progress) {
    for (const [prop, targetValue] of Object.entries(this.properties)) {
      if (typeof targetValue === 'number') {
        const start = parseFloat(this.originalValues[prop]) || 0;
        const current = start + (targetValue - start) * progress;
        this.target.setAttribute(prop, String(current));
      } else {
        // For non-numeric, only apply at completion
        if (progress >= 1) {
          this.target.setAttribute(prop, targetValue);
        }
      }
    }
  }
  
  snapToEnd() {
    // Immediately jump to final state
    this._applyValues(1);
    this.cancel();
  }
}
```

---

## Cadence Normalization Checklist

All motion timing has been normalized:

- [ ] State transitions use state-derived durations
- [ ] Throughput updates use throughput-derived intervals
- [ ] Replay frames use replay-speed-derived timing
- [ ] WebSocket updates are event-driven (no synthetic timing)
- [ ] Supervision uses trust-level-derived intervals
- [ ] No arbitrary easing functions
- [ ] No hardcoded animation durations
- [ ] No decorative timing
- [ ] All animations are interruptible
- [ ] All animations are replay-safe

---

## Known Cadence Issues

The following have been identified and will be addressed:

1. **Fixed Animation Durations**: Some widgets use hardcoded animation durations - migrate to state-derived
2. **CSS Transition Timing**: Some CSS files have fixed transition durations - migrate to CADENCE constants
3. **RequestAnimationFrame Usage**: Some code uses rAF without proper state binding - audit and fix

---

## Validation Tests

```python
# tests/test_runtime_svg_instrumentation.py

def test_cadence_determinism():
    """Same state produces same timing."""
    timing1 = get_state_transition_duration('streaming', complexity=1)
    timing2 = get_state_transition_duration('streaming', complexity=1)
    assert timing1 == timing2

def test_throughput_cadence_scaling():
    """Cadence scales with throughput."""
    low = get_update_duration(100)
    high = get_update_duration(10000)
    assert low > high  # Higher throughput = faster updates

def test_replay_speed_scaling():
    """Replay frame duration scales with speed."""
    speed1x = get_replay_frame_duration(1.0)
    speed10x = get_replay_frame_duration(10.0)
    assert speed1x > speed10x  # Higher speed = faster frames

def test_supervision_interval_by_trust():
    """Supervision interval scales with trust level."""
    restricted = get_supervision_interval('RESTRICTED')
    trusted = get_supervision_interval('TRUSTED')
    assert restricted < trusted  # Lower trust = more frequent supervision
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial motion cadence convergence specification |
