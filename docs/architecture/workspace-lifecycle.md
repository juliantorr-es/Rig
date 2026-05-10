# Workspace Lifecycle Governance

> **Deterministic Workspace State Management: Initialization, Persistence, Restoration, Lifecycle**

## Core Principle

Rig workspace lifecycle is **deterministic, replay-safe, and bounded**. Every workspace operation - from initialization to teardown - must produce **reproducible, predictable** results. Workspace state is **never ambiguous, never chaotic, never unrestorable**. The lifecycle enforces **stable widget identity, deterministic workspace restore, bounded workspace memory, and replay-safe workspace state**.

---

## Workspace States

### State Machine
```
                    +----------+
                    |   NULL   |
                    +----+-----+
                         |
                         v
                    +----+-----+     +------------------+
          +---------| UNINITIALIZED |<----| External Request |
          |         +----+-----+     +------------------+
          |              |
          |              v
          |         +----+-----+
          |         |           |
+---------+------+ | INITIALIZING | +--------+--------+
| External Request | +----+-----+          | user action |
+---------+------+       |            +--------+--------+
                          |
                          v
                    +----+-----+
      +-------------|   READY   |----------+
      |              +----+-----+           |
      |                   |              |
      v                   v              v
+---------+      +---------+      +-----------+
| SUSPEND |      | ACTIVE  |      | DEGRADED  |
+----+----+      +----+----+      +-----+-----+
     |                 |               |
     +-----------------+---------------+
                       |
                       v
                    +----+-----+
                    | TEARDOWN |
                    +----------+
```

### State Definitions
| State | Description | User Interaction | Visual State |
|-------|-------------|------------------|--------------|
| NULL | No workspace allocated | None | Empty/loading |
| UNINITIALIZED | Workspace object exists, no state | Limited | Minimal UI |
| INITIALIZING | Loading layout and topology | None (loading) | Loading indicators |
| READY | Fully loaded, ready for use | Full | Complete UI |
| ACTIVE | Runtime is active, processing | Full | Streaming visualization |
| SUSPENDED | Runtime paused, workspace preserved | Limited | Static visualization |
| DEGRADED | Partial failure, limited function | Partial | Error indicators |
| TEARDOWN | Workspace being destroyed | None | Teardown UI |

---

## Workspace Initialization

### Initialization Phases
1. **Pre-initialization** (0-100ms)
   - Allocate workspace object
   - Parse workspace path
   - Validate git worktree
   - Create workspace identifier

2. **Layout Loading** (100-500ms)
   - Find workspace persistence file (`.rig/workspace.json`)
   - Parse and validate layout JSON
   - Apply migrations if needed
   - Create grid structure

3. **Widget Restoration** (500ms-1s)
   - Instantiate all widgets from layout
   - Restore widget positions, sizes, visibility
   - Restore widget-specific state
   - Register widgets with visualization system

4. **Topology Restoration** (1-2s)
   - Load topology configuration
   - Initialize lane configurations
   - Loading topology plugin model
   - Populate topology systems

5. **Disclosure Restoration** (2-2.5s)
   - Restore disclosure layer states
   - Expand/collapse layers per saved state
   - Restore widget scales
   - Hide widgets in collapsed layers

6. **Projection Initialization** (2.5-3s)
   - Start projection contracts
   - Begin projection flow to widgets
   - Initialize visualization bindings
   - Subscribe widgets to projection updates

7. **Runtime Connection** (3-4s)
   - Connect to runtime backend
   - Stream initialization
   - Initialize websocket
   - Begin real-time updates

8. **Ready Signal** (4s)
   - Workspace marked as READY
   - UI enabled for interaction
   - First projections arrive

---

## Deterministic Workspace Restore

### Restore Guarantees
1. **Identical Layout**: Same layout JSON produces identical pixel-perfect render
2. **Deterministic Widget Order**: Widgets render in deterministic order (grid order, then ID)
3. **Projection Consistency**: Widgets display same projections at same positions
4. **State Fidelity**: All widget state restored identically
5. **Topology Fidelity**: Topology visualization identical on restore
6. **Replay Fidelity**: Replay state restored identically

### Restore Determinism Factors
| Factor | How Ensured | Verification |
|--------|-------------|--------------|
| Widget positions | Integer grid coordinates | JSON equality |
| Widget sizes | Integer grid cells | JSON equality |
| Widget IDs | Deterministic hash from type + position | ID regeneration |
| Widget order | Sorted by position then ID | Order comparison |
| Disclosure state | Boolean layer states | State comparison |
| Widget scale | Persisted per-widget | Scale comparison |
| Topology config | Deterministic serialization | Topology diff |
| Projection state | Derived from runtime | Projection equality |

### Restore Management
```javascript
class WorkspaceRestoration {
  constructor(layoutJson, runtimeState) {
    this.layout = this.parseLayout(layoutJson);
    this.runtime = runtimeState;
    this.restoredState = null;
  }

  restore() {
    // Phase 1: Validate
    this.validateLayout();
    
    // Phase 2: Migrate (if needed)
    this.layout = this.migrateIfNeeded(this.layout);
    
    // Phase 3: Initialize grid
    this.grid = this.createGrid(this.layout.grid);
    
    // Phase 4: Place widgets
    this.widgets = this.placeWidgets(this.layout.widgets, this.grid);
    
    // Phase 5: Restore state
    this.restoreWidgetStates(this.widgets, this.layout.widgetStates);
    
    // Phase 6: Restore topology
    this.topology = this.restoreTopology(this.layout.topology);
    
    // Phase 7: Restore disclosure
    this.restoreDisclosure(this.layout.disclosureState);
    
    // Phase 8: Initialize projections
    this.initProjections(this.widgets, this.runtime);
    
    // Phase 9: Verify
    this.verifyRestoration();
    
    this.restoredState = this.captureState();
    return this.restoredState;
  }

  verifyRestoration() {
    // Verify deterministic ID generation
    this.widgets.forEach(w => {
      const expectedId = widgetId(w.type, w.position);
      assert(w.id === expectedId, `Widget ID mismatch: ${w.id} != ${expectedId}`);
    });
    
    // Verify no overlaps
    this.verifyNoOverlaps(this.widgets);
    
    // Verify region constraints
    this.verifyRegionConstraints(this.widgets);
    
    // Verify disclosure consistency
    this.verifyDisclosureConsistency(this.widgets, this.layout.disclosureState);
  }
}
```

---

## Replay-Safe Workspace State

### Replay Guarantees
Workspace state during replay is **identical** to state during original session:
- Same widget positions
- Same disclosure states
- Same widget scales
- Same topology visualization
- Same projection display
- Same interaction possibilities (limited to replay mode)

### Replay Constraints
- Layout version must match (or be backwards compatible)
- Missing widget types show as empty placeholder
- Incompatible layouts trigger migration before restore
- Replay always uses **current runtime's** projection data (not historical data)

### Replay State Override
During replay, these aspects may differ from original:
| Aspect | Original | Replay | Reason |
|--------|----------|--------|--------|
| Runtime data | Live | Historical | Replay uses recorded data |
| Timestamps | Live | Historical | Replay uses recorded times |
| User input | Enabled | Limited | Replay restricts changes |
| External state | Live | Simulated | Replay simulates external changes |

All other aspects (layout, widget state, disclosure, topology) are **identical**.

---

## Stable Widget Identity

### Widget Identity Rules
Every widget has a **stable, deterministic identity** across sessions and restores:

```javascript
// Widget identity is determined by type and position
function getWidgetIdentity(type, position) {
  return {
    id: widgetId(type, position),  // Deterministic hash
    type: type,                    // Widget type identifier
    position: { ...position },     // Grid position
    region: getRegion(position),   // Region (header, sidebar, main, footer)
    disclosureLayer: getLayer(type) // Disclosure layer (1-4)
  };
}
```

### Identity Invariants
Widget identity **never changes** unless:
1. widget type changes (user replaces widget)
2. widget position changes (user moves widget)

Widget identity **is preserved** across:
- Workspace save/restore cycles
- Runtime restarts
- Replay sessions
- Layout migrations

### Widget Identity Verification
```javascript
function verifyWidgetIdentity(widget, expectedType, expectedPosition) {
  const expectedId = widgetId(expectedType, expectedPosition);
  assert(widget.id === expectedId, `Widget ID mismatch`);
  assert(widget.type === expectedType, `Widget type mismatch`);
  assert 比较widget.position === expectedPosition, `Widget position mismatch`);
}
```

---

## Workspace Memory Bounds

### Memory Limits
| Category | Hard Limit | Soft Limit | Enforcement |
|----------|------------|------------|-------------|
| Total workspace memory | 50MB | 40MB | GC + warning |
| Per-widget memory | 5MB | 3MB | Widget GC |
| Layout JSON size | 64KB | 32KB | Compression |
| Widget state cache | 10MB | 5MB | LRU eviction |
| Projection buffer | 20MB | 15MB | FIFO eviction |
| Topology cache | 15MB | 10MB | LRU eviction |
| DOM nodes | 5000 | 3000 | Virtualization |
| Event listeners | 500 | 400 | Cleanup |

### Memory Management Strategies
| Strategy | When Applied | Effect |
|----------|--------------|--------|
| FIFO eviction | Projection buffer full | Oldest projections removed |
| LRU eviction | Cache full | Least recently used removed |
| Compression | Layout JSON > 32KB | JSON compressed before save |
| Virtualization | DOM nodes > 3000 | Non-visible nodes unmounted |
| Throttling | Memory > 40MB | Reduce update frequency |
| Garbage collection | Memory > 45MB | Force GC, clean caches |

### Memory Monitoring
```javascript
class WorkspaceMemoryMonitor {
  constructor(workspace) {
    this.workspace = workspace;
    this.limits = WORKSPACE_MEMORY_LIMITS;
    this.metrics = this.measureMemory();
  }

  measureMemory() {
    return {
      total: this.measureTotalMemory(),
      layouts: this.measureLayoutMemory(),
      widgets: this.measureWidgetMemory(),
      projections: this.measureProjectionMemory(),
      topology: this.measureTopologyMemory(),
      dom: this.measureDOMMemory()
    };
  }

  checkLimits() {
    const violations = [];
    for (const [category, value] of Object.entries(this.metrics)) {
      if (value > this.limits[category].hard) {
        violations.push({ category, type: 'hard', value, limit: this.limits[category].hard });
      } else if (value > this.limits[category].soft) {
        violations.push({ category, type: 'soft', value, limit: this.limits[category].soft });
      }
    }
    return violations;
  }

  enforceLimits() {
    const violations = this.checkLimits();
    for (const violation of violations) {
      this.applyEnforcement(violation);
    }
  }

  applyEnforcement(violation) {
    switch (violation.category) {
      case 'projections':
        this.evictOldestProjections();
        break;
      case 'widgets':
        this.evictLeastUsedWidgets();
        break;
      case 'dom':
        this.virtualizeDOM();
        break;
      case 'total':
        this.forceGarbageCollection();
        break;
    }
  }
}
```

---

## Widget Restoration

### Widget State Persistence
Each widget persists:
1. **Layout state**: position, size, visibility
2. **Disclosure state**: current scale
3. **Configuration**: user preferences, filters, settings
4. **Runtime state**: last-known projection data (for restore)

### Widget Restoration Order
Widgets restore in **deterministic order**:
1. Sorted by grid position (row-major)
2. Then by widget type (alphabetical)
3. Then by widget ID (deterministic hash)

### Widget Lifecycle During Restore
```
1. Widget construction (from layout JSON)
2. Position assignment (from layout)
3. Size assignment (from layout)
4. Region assignment (from position)
5. Disclosure layer assignment (from type)
6. Scale restoration (from persisted state)
7. Configuration restoration (from persisted config)
8. Projection subscription (to runtime)
9. Visual rendering (to DOM)
10. Ready notification
```

### Widget Restoration Verification
After all widgets restored, verify:
- All widgets have valid positions
- No widget overlaps
- All widgets in correct regions
- All widgets respect disclosure layers
- All widgets subscribed to correct projections
- All widgets rendered correctly

---

## Disclosure Restoration

### Disclosure State Structure
```json
{
  "disclosureState": {
    "version": "1.0",
    "layers": {
      "1": {"isExpanded": true, "canCollapse": false},
      "2": {"isExpanded": true, "canCollapse": true},
      "3": {"isExpanded": false, "canCollapse": true},
      "4": {"isExpanded": false, "canCollapse": true}
    },
    "widgetScales": {
      "runtime-overview-001": "MEDIUM",
      "topology-panel-001": "LARGE"
    }
  }
}
```

### Disclosure Restoration Process
1. Load disclosure state from layout JSON
2. Apply layer expansion states
3. Hide widgets in collapsed layers
4. Restore widget scales
5. Verify disclosure consistency
6. Map widgets to their layers

### Disclosure Consistency Rules
- Layer 1 (Critical) **cannot** be collapsed
- Widgets in collapsed layers are **hidden but not destroyed**
- Expanding a layer **restores** all widgets in that layer
- Widget scale is **independent** of layer expansion
- Disclosure state persists **across save/restore cycles**

---

## Topology Restoration

### Topology State Structure
```json
{
  "topology": {
    "version": "1.0",
    "lanes": [
      {
        "id": "lane-001",
        "label": "Execution Lane 1",
        "trustTier": "STANDARD",
        "capabilities": ["default"],
        "isVisible": true
      }
    ],
    "connectors": [],
    "plugins": [
      {
        "id": "topology-plugin-model",
        "version": "1.0",
        "enabled": true
      }
    ]
  }
}
```

### Topology Restoration Process
1. Load lane configurations
2. Initialize topology plugin model
3. Register all plugins
4. Apply lane visibility
5. Validate topology integrity
6. Connect to runtime topology
7. Begin topology updates

### Topology Integrity Verification
After restoration, verify:
- All lanes have valid IDs
- All lane IDs are deterministic
- No duplicate lane IDs
- All plugins registered successfully
- Topology visualization initialized
- Lane boundaries rendered correctly

---

## Replay Restoration

### Replay State Structure
```json
{
  "replay": {
    "version": "1.0",
    "isReplaying": false,
    "position": 0,
    "total": 100,
    "speed": 1.0,
    "mode": "normal",
    "history": []
  }
}
```

### Replay Restoration Process
1. Load replay state from workspace
2. Initialize replay controls
3. Restore replay position
4. Load replay history
5. Verify replay capability
6. Enable replay mode if active

### Replay Verification
After replay restoration, verify:
- Replay position is valid (0 <= position <= total)
- Replay speed is valid (0.1 <= speed <= 20)
- Replay mode is supported
- Replay history is consistent (if exists)
- Workspace state compatible with replay

---

## Onboarding Lifecycle

### Onboarding State Integration
Onboarding state is part of workspace persistence:
```json
{
  "onboarding": {
    "version": "1.0",
    "stageProgress": {"1": 0.5, "2": 0.0, "3": 0.0, "4": 0.0},
    "completedLessons": ["workspace.welcome"],
    "dismissedLessons": ["workspace.layout"]
  }
}
```

### Onboarding Lifecycle
1. **Initial**: Onboarding state created with defaults
2. **Active**: Onboarding lessons shown based on triggers
3. **Dismissed**: Lessons hidden, progress saved
4. **Completed**: Stage or all lessons completed
5. **Reset**: User resets onboarding state

### Onboarding Restoration
- Onboarding state persists across workspace sessions
- Completed lessons **never re-shown** unless user resets
- Dismissed lessons **remembered** between sessions
- Stage progress **saved** and restored

---

## Tutorial Lifecycle

### Tutorial as Specialized Workspace
Tutorials are **specialized workspace states** with:
- Pre-configured layout
- Pre-configured topology
- Guided onboarding flow
- Step-by-step progression
- Completion tracking

### Tutorial Lifecycle
1. **Launch**: User selects tutorial from menu
2. **Initialize**: Create tutorial workspace (separate from main)
3. **Load**: Load tutorial-specific layout and topology
4. **Start**: Begin guided onboarding flow
5. **Progress**: User completes tutorial steps
6. **Complete**: Tutorial marked complete
7. **Cleanup**: Tutorial workspace destroyed
8. **Return**: User returns to main workspace

### Tutorial Workspace Rules
- Tutorial workspace **isolated** from main workspace
- Tutorial changes **do not** affect main workspace
- Tutorial state **persisted** separately
- Tutorial can be **resumed** later
- Tutorial can be **reset** to beginning

---

## Workspace Teardown

### Teardown Phases
1. **Suspend**: Pause all runtime updates
2. **Unsubscribe**: Widgets unsubscribe from projections
3. **Destroy Widgets**: Clean up widget resources
4. **Save State**: Persist final workspace state
5. **Cleanup Topology**: Clean up topology resources
6. **Destroy Grid**: Clean up grid and region structures
7. **Release Resources**: Free all memory
8. **Nullify**: Set workspace reference to null

### Teardown Guarantees
- All subscriptions cancelled
- All DOM elements removed
- All event listeners removed
- All memory released
- No dangling references
- Clean shutdown

### Teardown Verification
```javascript
function verifyTeardown(workspace) {
  // Verify all widgets destroyed
  assert(workspace.widgets.length === 0, 'Widgets still exist');
  
  // Verify all subscriptions cancelled
  assert(workspace.projectionSubscriptions.size === 0, 'Subscriptions still active');
  
  // Verify DOM clean
  assert(workspace.domElements.length === 0, 'DOM elements still exist');
  
  // Verify event listeners removed
  assert(workspace.eventListeners.length === 0, 'Event listeners still active');
  
  // Verify memory released
  assert(workspace.memoryMonitor.measure().total < 1000, 'Memory not released');
}
```

---

## Compliance Checklist

- [ ] Workspace initialization is deterministic
- [ ] Workspace restore produces identical state
- [ ] Widget identities are stable and deterministic
- [ ] Workspace memory is bounded
- [ ] Replay-safe workspace state maintained
- [ ] Deterministic workspace restore verified
- [ ] Disclosure restoration is deterministic
- [ ] Topology restoration is deterministic
- [ ] Replay restoration is deterministic
- [ ] Onboarding lifecycle is managed
- [ ] Tutorial lifecycle is managed
- [ ] Workspace teardown is clean
- [ ] All workspace state persists correctly
- [ ] Layout migrations are backwards compatible
- [ ] Resource cleanup is complete

---

## See Also

- [Startup Experience Doctrine](./startup-experience.md) - Initial workspace loading
- [Workspace Composition System](./workspace-composition.md) - Layout and widgets
- [Widget Disclosure Scaling](./widget-disclosure-scaling.md) - Widget states
- [Guided Onboarding System](./guided-onboarding.md) - Onboarding management
- [Calm Dashboard Governance](./calm-dashboard-governance.md) - State management under load
- [Progressive Disclosure Doctrine](../progressive-disclosure-doctrine.md) - Layer hierarchy
- [Visualization Lifecycle](./visualization-lifecycle.md) - Component lifecycle
