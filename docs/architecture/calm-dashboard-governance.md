# Calm Dashboard Governance

> **Dashboard Calmness Doctrine: Stable Geometry, Restrained Motion, Bounded Density, Progressive Reveal**

## Core Principle

Rig dashboards **become calmer as they become more complex**. This is the **inverse** of traditional dashboard design where complexity leads to chaos. In Rig, complexity leads to **abstraction, aggregation, and motion reduction**. The dashboard remains operationally readable at all scales. This is non-negotiable.

**The Rule:** As dashboard complexity increases:
- Abstraction increases
- Aggregation increases
- Motion decreases
- Hierarchy strengthens

---

## What Calm Means in Rig

### NOT Calm (FORBIDDEN)
- More flashing
- More motion
- More simultaneous telemetry
- More chaos
- More visual noise
- More overlapping elements
- More animation on state changes
- More decorative elements
- More color variation
- More attention-grabbing

### IS Calm (REQUIRED)
- Stable geometry
- Restrained motion
- Bounded density
- Progressive reveal
- Operational hierarchy
- Low-noise instrumentation
- Predictable layout
- Deterministic rendering
- Moving towards summary, not towards spectacle
- Respecting user's cognitive capacity

---

## Dashboard Density Ceilings

### Hard Limits
| Element Type | Maximum Count | Memory Limit |
|--------------|---------------|--------------|
| Widgets | 20 | Each: 1MB |
| lanes | 8 | Total: 2MB |
| Topology nodes | 500 (visual), unbounded (data) | 10MB |
| Topology connectors | 1000 (visual), unbounded (data) | 5MB |
| DTG nodes | 200 | 5MB |
| DTG edges | 500 | 3MB |
| Integrity markers | 50 | 1MB |
| Replay sweep frames | 200 | 2MB |
| Throughput bars | 100 | 1MB |
| Stream density lines | 100 | 1MB |

### Soft Limits (with Warnings)
| Metric | Warning Threshold | Suggestion |
|--------|-------------------|------------|
| Cell density | > 60% | "Consider simplifying your layout" |
| Widget count | > 15 | "You have many widgets. Some may be hidden." |
| Topology nodes | > 300 | "Complex topology. Consider filtering." |
| Concurrent motion | > 3 | "Multiple animations. Consider reducing." |
| Opacity layers | > 5 | "Many overlays. Consider simplification." |

---

## Instrumentation Suppression

### Automatic Suppression Rules
As complexity increases, Rig **automatically suppresses** non-critical instrumentation:

| Complexity Level | Suppression Applied |
|-----------------|---------------------|
| Low (density < 0.4) | None - full instrumentation |
| Medium (0.4-0.6) | Hide secondary metrics |
| High (0.6-0.8) | Hide secondary + show summaries |
| Critical (> 0.8) | Minimal instrumentation, summaries only |

### Suppression Priority
What gets hidden first when suppresses:
1. **Historical data** - Past values, trends, history
2. **Secondary metrics** - Less critical measurements
3. **Detailed labels** - Full text labels shortened
4. **Decorative elements** - Visual enhancements removed
5. **Preview content** - Content previews truncated
6. **Debug information** - Diagnostic data hidden
7. **Replay markers** - Historical annotations simplified
8. **Throughput detail** - Aggregated to summaries

### What NEVER Gets Suppressed
These elements are **always visible**:
- Current runtime state
- Current sequence number
- Integrity violation indicators
- Lane boundaries
- Primary state indicators
- Critical error indicators
- Current time/timestamp
- Workspace identity

---

## Topology Simplification

### Topology Abstraction Levels
As topology complexity increases, Rig applies **deterministic abstraction**:

| Mode | Node Count | Abstraction Applied |
|------|-------------|---------------------|
| Full | < 50 | All nodes visible |
| Condensed | 50-100 | Root + children visible, grandchildren abstracted |
| Summary | 100-300 | Root + high-level groups, details on hover |
| Extreme | > 300 | Lane-level summary only, details on demand |

### Abstraction Rules
1. **Deterministic**: Same topology at same complexity always abstracts identically
2. **Hierarchy-Preserving**: Parent-child relationships always visible
3. **Lane-Respecting**: Abstraction never crosses lane boundaries
4. **Replay-Safe**: Abstraction identical on replay
5. **User-Overridable**: User can force full detail if needed
6. **Density-Aware**: Abstraction level automatically selected

### Visual Abstraction
| Element | Full | Condensed | Summary | Extreme |
|---------|------|-----------|---------|---------|
| Nodes | All | Root + children | Group indicators | Lane indicators |
| Connectors | All | Direct only | Grouped | Lane boundaries |
| Labels | Full | Abbreviated | Grouped | Lane only |
| Flow | Animated | Static | None | None |
| Integrity | All | Critical only | Critical only | Lane summary |

---

## Overload Aggregation

### Aggregation Strategies
When visual load exceeds thresholds, Rig **aggregates** information:

| Overload Type | Aggregation Strategy |
|---------------|---------------------|
| Too many widgets | Hide lowest-priority, aggregate by function |
| Too many topology nodes | Group by lane, show counts |
| Too many streams | Aggregate by lane, show totals |
| Too many metrics | Show primary, aggregate secondary |
| Too many events | Show recent, aggregate historical |
| Too many violations | Show critical, aggregate warnings |

### Aggregation Visualization
| Aggregated | Visual | Hover |
|-----------|--------|-------|
| Hidden widgets | Badge with count | List of hidden widgets |
| Grouped nodes | Circle with count | List of nodes in group |
| Aggregated metrics | Summary value | Full breakdown |
| Combined events | Count indicator | Recent events list |
| Summarized violations | Severity summary | Full violation list |

---

## Operational Hierarchy

### Visual Hierarchy Rules
Rig enforces a **strict visual hierarchy** that strengthens as complexity increases:

1. **Foreground**: Current state, active elements, user focus
2. **Midground**: Recent context, secondary information
3. **Background**: Historical data, reference information

As complexity increases:
- Foreground becomes **more prominent**
- Midground becomes **more aggregated**
- Background becomes **less visible**

### Hierarchy Strengthening
| Complexity | Foreground | Midground | Background |
|------------|-----------|----------|------------|
| Low | Normal | Normal | Normal |
| Medium | Slight emphasis | Slight reduction | Slight hiding |
| High | Strong emphasis | Significant reduction | Mostly hidden |
| Critical | Maximum emphasis | Minimal | Hidden |

### Hierarchy Visual Cues
| Layer | Color | Opacity | Size | Interaction |
|-------|-------|---------|------|-------------|
| Foreground | Full saturation | 1.0 | Large | Full |
| Midground | Medium saturation | 0.7 | Medium | Hover |
| Background | Low saturation | 0.4 | Small | Click to reveal |

---

## Stable Geometry

### Geometry Rules
All dashboard geometry is **stable**:
- Widgets maintain their positions
- Topology elements maintain their relative positions
- No layout shifts when content changes
- No reflow when elements appear/disappear
- Reserved space for hidden elements

### Layout Stability
1. **Grid Stability**: CSS Grid never reflows
2. **Widget Stability**: Widgets never resize unexpectedly
3. **Topology Stability**: Nodes never jump to new positions
4. **Label Stability**: Labels never cause layout shifts
5. **Animation Stability**: Animations never cause outer layout changes

### Geometry Bounds
| Property | Minimum | Maximum | Unit |
|----------|---------|---------|------|
| Widget width | 3 cells | 9 cells | Grid cells |
| Widget height | 1 cell | 8 cells | Grid cells |
| Node size | 8px | 32px | Pixels |
| Connector width | 1px | 4px | Pixels |
| Label size | 10px | 16px | Pixels |
| Padding | 4px | 16px | Pixels |
| Margin | 0 | 8px | Pixels |

---

## Restrained Motion

### Motion Ceilings
As complexity increases, motion **decreases proportionally**:

| Complexity Level | Max Concurrent Animations | Animation Speed | Animation Scale |
|-----------------|----------------------------|-----------------|----------------|
| Low | 3 | Normal | Normal |
| Medium | 2 | 0.8x | 0.9x |
| High | 1 | 0.6x | 0.8x |
| Critical | 0 | N/A | N/A |

### Motion Types by Complexity
| Motion Type | Low | Medium | High | Critical |
|-------------|-----|--------|------|----------|
| Flow animation | Yes | Yes | Reduced | No |
| State transitions | Yes | Yes | Minimal | No |
| Pulse indicators | Yes | Yes | No | No |
| Replay sweep | Yes | Reduced | No | No |
| Hover effects | Yes | Yes | Minimal | No |
| Loading indicators | Yes | Reduced | No | No |

### Motion Governance Functions
```javascript
// Calculate motion scale based on complexity
function getMotionScale(complexity) {
  // complexity: 0-1
  // Returns: 0-1 (0 = no motion, 1 = full motion)
  return Math.max(0, 1 - complexity);
}

// Calculate animation duration based on complexity
function getAnimationDuration(baseDuration, complexity) {
  const scale = getMotionScale(complexity);
  return baseDuration * (0.5 + scale * 0.5); // 50-100% of base
}

// Check if animation is allowed
function isAnimationAllowed(complexity) {
  return complexity < 0.9; // No animation above 90% complexity
}
```

---

## Progressive Reveal

### Reveal Rules
Information reveals **progressively** based on:
1. **User Action**: Click, hover, focus
2. **Disclosure Level**: Currently expanded layers
3. **Density**: Current workspace density
4. **Relevance**: Whether information is currently relevant

### Reveal Priority
What reveals first when user requests more detail:
1. **Critical State**: Current runtime state, errors, violations
2. **Active Context**: Currently active streams, recent events
3. **User Focus**: Elements user is interacting with
4. **Related Information**: Context for user's current action
5. **Historical Data**: Past values, trends
6. **Debug Information**: Internal state, diagnostics

### Reveal Methods
| Method | Trigger | Content | Persistence |
|--------|---------|---------|-------------|
| Hover | Mouse hover | Tooltip, hint | While hover |
| Click | Click on element | Detail panel | Until dismissed |
| Expand | Expand disclosure | Full detail | Until collapsed |
| Scroll | Scroll in widget | More history | Until scrolled back |
| Pin | Pin detail | Pinned panel | Until unpinned |

---

## Calm Dashboard Formulas

### Density Collapse Formula
```javascript
function calculateDashboardDensity() {
  const widgetCount = countWidgets();
  const topologyNodes = countVisibleTopologyNodes();
  const activeStreams = countActiveStreams();
  const violations = countIntegrityViolations();
  
  // Each contributes to density
  const density = (
    (widgetCount / 20) * 0.25 +
    (Math.min(topologyNodes, 500) / 500) * 0.4 +
    (Math.min(activeStreams, 50) / 50) * 0.2 +
    (Math.min(violations, 50) / 50) * 0.15
  );
  
  return Math.min(density, 1.0);
}
```

### Abstraction Level Formula
```javascript
function getAbstractionLevel(density) {
  if (density < 0.4) return 'none';
  if (density < 0.6) return 'condensed';
  if (density < 0.8) return 'summary';
  return 'extreme';
}
```

### Motion Reduction Formula
```javascript
function getMotionReduction(density) {
  // Linear reduction from 1.0 to 0.0 as density goes from 0.4 to 1.0
  if (density < 0.4) return 0.0;
  return Math.min(1.0, (density - 0.4) / 0.6);
}
```

### Low-Stimulation Mode
Activates when ANY of:
- `prefers-reduced-motion: reduce`
- Density > 0.6
- Runtime overload > 0.5
- User explicitly enabled
- Workspace has > 15 widgets

Low-stimulation mode applies:
- `getMotionScale()` returns 0 (no motion)
- All animations disabled
- All transitions disabled
- Static positioning only
- Plain styling (minimal shadows, borders)

---

## Compliance Checklist

- [ ] Dashboard density ceilings enforced
- [ ] Instrumentation suppression active
- [ ] Topology simplification working
- [ ] Overload aggregation functioning
- [ ] Operational hierarchy visible
- [ ] Stable geometry maintained
- [ ] Restrained motion applied
- [ ] Progressive reveal functional
- [ ] As complexity increases: abstraction increases, aggregation increases, motion decreases, hierarchy strengthens
- [ ] NO: more flashing, more motion, more chaos as complexity increases
- [ ] Low-stimulation mode functional
- [ ] All dashboard state replay-safe
- [ ] Visual noise bounded

---

## See Also

- [Startup Experience Doctrine](./startup-experience.md) - Calm startup
- [Workspace Composition System](./workspace-composition.md) - Constrained layout
- [Widget Disclosure Scaling](./widget-disclosure-scaling.md) - Progressive detail
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Information hierarchy
- [Governed Motion Doctrine](./governed-motion.md) - Motion constraints
- [Density Collapse](../density-collapse.md) - Abstraction rules
- [Spatial Stability](./spatial-stability.md) - Layout consistency
