# Workspace Composition System

> **Composable Runtime Workspace Architecture for Rig**

## Core Principle

Rig workspaces are **constrained, deterministic, and replay-safe**. Users have bounded freedom to arrange their operational environment, but all freedom operates within governance that prevents chaos, preserves replay fidelity, and respects disclosure hierarchy.

---

## Constrained Grid Layout

### Grid Fundamentals
- **Type**: Strict CSS Grid, not freeform drag-and-drop
- **Regions**: Fixed set of bounded workspace regions
- **Snap**: All widgets snap to grid cells, never free-floating
- **Overlap**: Widgets NEVER overlap - grid enforces non-overlapping placement

### Grid Structure
```
+-----------------------------------------------------+
|  HEADER (fixed, top)    1 row, 12 columns            |
+----------------------+----------------------------------+
|  SIDEBAR (left)      |  MAIN WORKSPACE                  |
|  3 columns (fixed)   |  9 columns (fluid)              |
|  Widgets:            |  Widgets:                        |
|  - Runtime Overview  |  - Topology Panel               |
|  - Status Card       |  - DTG Viewer                   |
|  - Intent Console    |  - Stream Cards                 |
|  - Onboarding Panel  |  - Replay Controls              |
+----------------------+----------------------------------+
|  FOOTER (fixed, bottom)  1 row, 12 columns          |
+-----------------------------------------------------+
```

### Region Constraints
| Region | Columns | Rows | Max Widgets | Purpose |
|--------|---------|------|-------------|---------|
| Header | 1-12 | 1 | 3 | Global state, identity, controls |
| Sidebar | 1-3 | 2-11 | 8 | Runtime monitors, utility widgets |
| Main | 4-12 | 2-11 | 6 | Primary visualization, topology |
| Footer | 1-12 | 12 | 3 | Status, alerts, action bar |

---

## Deterministic Layout Serialization

### Serialization Format
```json
{
  "version": "1.0",
  "grid": {
    "columns": 12,
    "rows": 12,
    "cellWidth": 80,
    "cellHeight": 64,
    "gutter": 8
  },
  "widgets": [
    {
      "id": "runtime-overview-001",
      "type": "runtime-overview",
      "region": "sidebar",
      "position": {"x": 0, "y": 0},
      "size": {"width": 3, "height": 2},
      "disclosureLayer": 1,
      "isMinimized": false,
      "isVisible": true
    }
  ],
  "topology": {
    "lanes": [/* lane configuration */],
    "connectors": [/* connector configuration */]
  },
  "disclosureState": {
    "layer1": {"isExpanded": true},
    "layer2": {"isExpanded": true},
    "layer3": {"isExpanded": false},
    "layer4": {"isExpanded": false}
  }
}
```

### Serialization Guarantees
1. **Deterministic Order**: Widgets serialized in grid order (row-major), then by ID
2. **Bounded Size**: Maximum 20 widgets total across all regions
3. **Versioned**: Format version for forward/backward compatibility
4. **Validation**: All serialized layouts pass schema validation
5. **Replay-Safe**: Same layout JSON produces identical visual result

### ID Generation
All widget instance IDs use deterministic hash:
```javascript
function widgetId(type, position) {
  return `widget-${type}-${svgId(type, position.x, position.y)}`;
}
```

---

## Bounded Workspace Regions

### Region Capacity Limits
| Region | Max Widgets | Max Total Cells | Min Widget Size |
|--------|-------------|-----------------|-----------------|
| Header | 3 | 12 | 4x1 |
| Sidebar | 8 | 24 | 3x1 |
| Main | 6 | 54 | 3x3 |
| Footer | 3 | 12 | 4x1 |

### Widget Size Matrix
| Widget Type | Min Size | Max Size | Default Size |
|-------------|----------|----------|--------------|
| Runtime Overview | 3x1 | 3x3 | 3x2 |
| Status Card | 3x1 | 3x2 | 3x1 |
| Topology Panel | 6x4 | 9x8 | 9x6 |
| DTG Viewer | 6x4 | 9x8 | 9x6 |
| Stream Card | 3x2 | 6x4 | 4x3 |
| Replay Controls | 4x1 | 6x2 | 4x1 |
| Intent Console | 3x2 | 6x4 | 3x3 |
| Integrity Panel | 3x2 | 6x4 | 3x3 |
| Onboarding Panel | 4x3 | 6x5 | 4x4 |
| Proposal Console | 6x4 | 9x6 | 6x4 |

---

## Widget Placement Rules

### Placement Validity
A widget placement is **valid** if and only if:

1. **Region Fit**: Widget fits entirely within its designated region
2. **Grid Alignment**: Position (x, y) aligns with grid cells
3. **Size Alignment**: Size (width, height) is integer number of grid cells
4. **No Overlap**: Widget bounding box does not intersect any other widget
5. **Capacity**: Region has not reached its max widget count
6. **Disclosure**: Widget's disclosure layer is currently expanded

### Placement Algorithm
```
1. Validate widget type and size constraints
2. Check region capacity
3. Check disclosure layer availability
4. Snap to nearest grid cell (if not already aligned)
5. Check for overlap with existing widgets
6. If overlap: find nearest non-overlapping position
7. If no valid position: reject placement
```

### Placement Rejection
Placement is rejected if:
- Widget exceeds region bounds
- Widget overlaps existing widget
- Region at capacity
- Disclosure layer not expanded
- Widget size exceeds maximum for type
- Widget size below minimum for type

---

## Disclosure-Aware Placement

### Disclosure Layer Hierarchy
| Layer | Priority | Widgets | Auto-Expand |
|-------|----------|---------|-------------|
| 1 | Critical | Runtime Overview, Status Card, Topology Panel | Always |
| 2 | Primary | Stream Cards, DTG Viewer, Replay Controls | Default |
| 3 | Secondary | Integrity Panel, Proposal Console, Intent Console | Manual |
| 4 | Advanced | Debug Panel, Telemetry Viewer, Plugin Inspector | Manual |

### Disclosure Rules
1. **Layer 1**: Always visible, cannot be collapsed
2. **Layer 2**: Collapsible but defaults to expanded
3. **Layer 3**: Collapsible, defaults to collapsed
4. **Layer 4**: Collapsible, defaults to collapsed, requires explicit enable

### Placement and Disclosure Interaction
- Widgets can only be placed in expanded layers
- Collapsing a layer hides all widgets in that layer
- Widget positions are preserved when layer is collapsed
- Expanding a layer restores widget positions
- Placement in collapsed layer is rejected

---

## Topology-Safe Placement

### Topology Awareness
Widgets that visualize topology must respect:

1. **Lane Scope**: Widget shows only topology within its lane scope
2. **Plugin Model**: Widget uses topology plugin model for data
3. **Projection Contract**: Widget renders only from projections, never fetches data
4. **Integrity Visibility**: Widget shows integrity state from projections

### Topology-Constrained Widgets
| Widget | Lane Scope | Plugin Dependency | Projection Requirement |
|--------|------------|-------------------|------------------------|
| Topology Panel | All lanes | topology-plugin-model | stream, topology |
| DTG Viewer | All lanes | dtg-svg-bindings | dtg |
| Stream Card | Single lane | none | stream |
| Runtime Overview | All lanes | none | runtime |
| Integrity Panel | All lanes | topology-plugin-model | integrity |
| Replay Controls | All lanes | replay-safe-extension | replay |

### Topology Placement Rules
1. **Lane-Aligned**: Stream Cards must be placed in sidebar aligned with their lane
2. **No Data Fetching**: Widgets must NOT make network requests for topology data
3. **Projection-Only**: All topology data comes from projection contracts
4. **Replay-Safe**: Topology visualization must be identical on replay

---

## Workspace Persistence

### Persistence Layers
1. **Workspace Layout**: Widget positions, sizes, visibility
2. **Disclosure State**: Which layers are expanded/collapsed
3. **Widget State**: Individual widget configuration (density, filters)
4. **Topology State**: Lane configuration, plugin registration
5. **Replay State**: Current replay position, speed, mode

### Persistence Format
```json
{
  "workspace": {
    "layout": { /* layout serialization */ },
    "disclosure": { /* disclosure state */ },
    "widgets": { /* widget-specific state */ }
  },
  "topology": { /* topology configuration */ },
  "replay": { /* replay state */ },
  "version": "1.0"
}
```

### Persistence Triggers
| Event | Persist | Debounce |
|-------|---------|----------|
| Widget move | Yes | 500ms |
| Widget resize | Yes | 500ms |
| Widget visibility change | Yes | Immediate |
| Disclosure layer change | Yes | Immediate |
| Widget state change | Yes | 100ms |
| Topology configuration change | Yes | Immediate |
| Replay state change | Yes | 100ms |

### Persistence Bounds
- Maximum file size: 64KB
- Maximum history: 10 saved states
- Maximum debounce queue: 20 pending writes
- Write timeout: 5 seconds (fallback to sync)

---

## Layout Replay Compatibility

### Replay Guarantees
1. **Identical Layout**: Same layout JSON produces identical pixel-perfect render
2. **Deterministic Widget Order**: Widgets render in deterministic order
3. **Projection Consistency**: Widgets display same projections at same positions
4. **State Fidelity**: All widget state restored identically
5. **Topology Fidelity**: Topology visualization identical on replay

### Replay Constraints
- Layout version must match runtime version
- Missing widget types show as empty placeholder
- Incompatible layouts trigger migration or rejection
- Replay always uses runtime's current projection data

### Migration Strategy
When layout version mismatch detected:
1. Parse old format with backwards-compatible parser
2. Validate against current schema
3. Migrate to current version
4. Save migrated layout
5. Log migration event
6. Never auto-migrate without user confirmation for major version changes

---

## Workspace Loading Lifecycle

### Loading Phases
1. **Parse**: Read and parse workspace JSON
2. **Validate**: Validate schema, bounds, versions
3. **Migrate**: Apply migrations if needed (with confirmation for major versions)
4. **Initialize**: Create grid and region structures
5. **Place Widgets**: Position all widgets in their regions
6. **Restore State**: Restore widget-specific state
7. **Restore Topology**: Load topology configuration
8. **Restore Disclosure**: Expand/collapse layers
9. **Initialize Projections**: Start projection flow to widgets
10. **Signal Ready**: Workspace is fully loaded

### Lifecycle Events
| Phase | Event | Data | Cancelable |
|-------|-------|------|------------|
| Parse | `workspace:parse` | raw JSON | No |
| Validate | `workspace:validate` | validation result | Yes |
| Migrate | `workspace:migrate` | old format, new format | Yes |
| Initialize | `workspace:init` | grid config | No |
| Place | `workspace:place` | widget placements | No |
| Restore | `workspace:restore` | restoration result | No |
| Ready | `workspace:ready` | complete workspace | No |

---

## Workspace Density Governance

### Density Metrics
| Metric | Threshold | Action |
|--------|-----------|--------|
| Total widgets | > 15 | Warn on new widget placement |
| Widgets in region | > region max | Reject new widget |
| Total grid cells used | > 80% | Suggest simplification |
| Overlapping widgets | > 0 | Reject |
| Widgets in collapsed layer | Any | Hide until expanded |

### Density Calculation
```javascript
function calculateWorkspaceDensity(workspace) {
  const totalCells = workspace.grid.columns * workspace.grid.rows;
  const usedCells = workspace.widgets.reduce((sum, w) => 
    sum + (w.size.width * w.size.height), 0);
  const widgetCount = workspace.widgets.length;
  
  return {
    cellDensity: usedCells / totalCells,
    widgetDensity: widgetCount / Object.keys(REGION_LIMITS).length,
    shouldWarn: usedCells / totalCells > 0.8 || widgetCount > 15,
    shouldSuggest: usedCells / totalCells > 0.6 || widgetCount > 10
  };
}
```

### Density Actions
| Density Level | Action | User Control |
|---------------|--------|--------------|
| Low (< 0.4) | Normal operation | Full |
| Medium (0.4-0.6) | Warn on complex additions | Full |
| High (0.6-0.8) | Suggest simplification | Full |
| Critical (> 0.8) | Block new widgets | Limited |

---

## Compliance Checklist

- [ ] Grid layout is strictly CSS Grid, not freeform
- [ ] Widgets snap to grid cells, never free-floating
- [ ] Widgets never overlap
- [ ] Layout serialization is deterministic
- [ ] Widget IDs are deterministic and replay-safe
- [ ] Region capacity limits are enforced
- [ ] Widget size constraints are enforced
- [ ] Disclosure-aware placement is enforced
- [ ] Topology-safe placement is enforced
- [ ] Workspace persistence is bounded
- [ ] Layout replay compatibility is maintained
- [ ] Density governance is active

---

## See Also

- [Startup Experience Doctrine](./startup-experience.md) - Startup sequencing
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Layer hierarchy
- [Visualization Composition](./visualization-composition.md) - Component system
- [Visualization Lifecycle](./visualization-lifecycle.md) - Widget lifecycle
- [Replay-Safe Extension Model](./replay-safe-extension-model.md) - Replay guarantees
