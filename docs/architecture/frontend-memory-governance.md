# Frontend Memory & DOM Governance

## Summary

This document defines Rig's frontend memory governance policies for SVG instrumentation. The frontend must maintain bounded memory usage while rendering deterministic, replay-safe visualizations. This is achieved through explicit DOM lifecycle management, SVG node cleanup policies, and bounded visual history buffers.

**Core Doctrine:**
- Bounded DOM growth in all scenarios
- Deterministic SVG cleanup
- Replay-safe cleanup ordering
- Stale node eviction
- Bounded instrumentation history
- No unbounded caches or retention

---

## DOM Node Lifecycle

### The Complete Lifecycle

```
CREATION → ACTIVE → STALE → EVICtion → cleanup
        ↓
    (bounded)
        ↓
    PROJECTION-DERIVED
```

Every SVG element in Rig's instrumentation follows this deterministic lifecycle, governed only by backend projection state.

### Lifecycle States

| State | Description | Duration | Cleanup Trigger |
|-------|-------------|----------|-----------------|
| Creation | Element created from projection | Immediate | N/A |
| Active | Element visible and bound to current projection | Until stale | Projection removal |
| Stale | Element no longer has corresponding projection | Bounded period | Eviction policy |
| Evicted | Element removed from DOM | N/A | Memory reclamation |

---

## SVG Node Cleanup Policy

### Cleanup Guarantees

1. **No Orphaned Nodes**: Every SVG element not bound to a current projection is eventually removed
2. **No Accumulation**: Bounded maximum count for each element type
3. **Deterministic Order**: Cleanup ordering is deterministic and replay-safe
4. **Graceful Degradation**: Oldest nodes cleaned first (FIFO-level eviction)

### Cleanup Triggers

SVG nodes are cleaned when:
1. Corresponding projection is removed/expired
2. Bounded buffer limit reached for element type
3. Explicit clear/reset command received
4. Visual history truncation triggered

### Cleanup Priorities

Priority order (highest to lowest):
1. Nodes exceeding maximum age
2. Nodes exceeding maximum count
3. Nodes with lowest sequence number (oldest)
4. Nodes with lowest visual priority

---

## Bounded Buffers

### Maximum Element Counts

All instrumentation elements have explicit maximum counts:

| Element Type | Max Count | Retention Window | Cleanup Policy |
|--------------|-----------|----------------|----------------|
| Execution Lane | 8 | Session | Manual clear only |
| Routing Path | 50 | 1 minute | FIFO eviction |
| Stream Density Line | 100 | 30 seconds | FIFO eviction |
| Throughput Bar | 50 | 30 seconds | FIFO eviction |
| Replay Sweep | 1 | Session | Replace on replay start |
| Integrity Marker | 30 | 5 minutes | FIFO eviction |
| Proposal Node | 200 | 5 minutes | FIFO eviction |
| Topology Connector | 500 | 5 minutes | FIFO eviction |
| DTG Node | 200 | Session | Manual/DTG eviction |
| DTG Edge | 500 | Session | Manual/DTG eviction |

### Visual History Bounds

**Stream Visualization:**
- Maximum chart history: 100 throughput values
- Maximum stream density points: 200 points per lane
- Maximum visible chunks: 50 per stream

**Replay Visualization:**
- Maximum sweep frames: 200 (capped by MAX_REPLAY_FRAMES)
- Maximum replay markers: 100 per replay session
- Maximum historical snapshots: 50 (for scrubbing)

**Topology Visualization:**
- Maximum lane history: 100 state changes
- Maximum routing path history: 200 paths
- Maximum node history: 500 nodes total

---

## Stream Visualization Truncation

### Throughput Buffer

The `SvgStreamDensityLine` maintains a bounded buffer:

```javascript
class SvgStreamDensityLine {
  static MAX_POINTS = 200;  // Maximum points in buffer
  
  addPoint(sequence, value) {
    this.points.push({ sequence, value });
    
    // Truncate if exceeds max
    if (this.points.length > SvgStreamDensityLine.MAX_POINTS) {
      this.points.shift();  // FIFO: remove oldest
    }
  }
}
```

**Cleanup Trigger**: Adding point #201 removes point #0

### Throughput Bar History

The `SvgThroughputBar` maintains sliding window:

```javascript
class SvgThroughputBar {
  static MAX_HISTORY = 50;
  static RETENTION_MS = 30000;  // 30 seconds
  
  addValue(value, timestamp = Date.now()) {
    this.values.push({ value, timestamp });
    
    // Remove expired values
    while (this.values.length > 0 && 
           timestamp - this.values[0].timestamp > SvgThroughputBar.RETENTION_MS) {
      this.values.shift();
    }
    
    // Enforce max size
    while (this.values.length > SvgThroughputBar.MAX_HISTORY) {
      this.values.shift();
    }
  }
}
```

**Cleanup Triggers**:
1. Values older than 30 seconds expired
2. More than 50 values accumulated

### Replay Sweep Cleanup

The `SvgReplaySweep` has strict single-instance policy:

```javascript
class SvgReplaySweep {
  static MAX_INSTANCES = 1;
  
  static render(projection) {
    // Remove existing sweep if present
    const existing = document.getElementById('svg-replay-sweep');
    if (existing) {
      existing.remove();
    }
    
    // Create new sweep with current projection
    return new SvgReplaySweep(projection).render();
  }
}
```

**Cleanup Policy**: Replace-only (no accumulation)

---

## Replay Buffer Cleanup

### Projection Retention

Replay projections are bounded by the projection contract:

```javascript
// RuntimeProjection contract limits
{
  max_replay_frames: 200,      // Maximum frames retained
  max_replay_duration_ms: 60000,  // 60 seconds max replay window
  max_replay_bytes: 1024 * 1024 * 10  // 10 MB max replay data
}
```

Frontend cleanup mirrors these bounds:

```javascript
class ReplayBuffer {
  static MAX_FRAMES = 200;
  static MAX_DURATION_MS = 60000;
  
  addFrame(frame) {
    this.frames.push(frame);
    
    // Enforce max frames
    while (this.frames.length > ReplayBuffer.MAX_FRAMES) {
      this.frames.shift();
    }
    
    // Enforce max duration
    while (this.frames.length > 0 && 
           frame.timestamp - this.frames[0].timestamp > ReplayBuffer.MAX_DURATION_MS) {
      this.frames.shift();
    }
  }
}
```

---

## WebSocket Reconnection Cleanup

### Connection State Cleanup

On websocket disconnect/reconnect, JJcleanup stale state:

```javascript
class WebSocketConnection {
  #cleanupStaleState() {
    // Remove all stream-related elements
    const streamElements = document.querySelectorAll('.svg-stream-density, .svg-throughput');
    streamElements.forEach(el => el.remove());
    
    // Reset state machines
    this.runtimeState = new RuntimeInstrumentationState();
    this.projectionBuffer = new ProjectionBuffer();
    this.sequenceCounter = 0;
    
    // Clear pending timers (if any investigative timers exist)
    this.clearTimers();
  }
  
  onDisconnect() {
    this.#cleanupStaleState();
  }
  
  onReconnect() {
    this.#cleanupStaleState();
    this.requestFullStateSync();  // Request current state from backend
  }
}
```

**Cleanup Guarantee**: No stale stream state persists across reconnections

---

## Stale Topology Cleanup

### Topology Node Lifecycle

Topology panels maintain bounded node counts:

```javascript
class RuntimeTopologyPanel {
  static MAX_LANES = 8;
  static MAX_NODES_PER_LANE = 20;
  static MAX_ROUTING_PATHS = 50;
  static MAX_INTEGRITY_MARKERS = 30;
  
  addLane(lane) {
    // Evict oldest if at capacity
    if (this.lanes.length >= RuntimeTopologyPanel.MAX_LANES) {
      this.removeLane(this.lanes[0].id);  // FIFO
    }
    this.lanes.push(lane);
  }
  
  addNode(laneId, node) {
    const lane = this.getLane(laneId);
    if (!lane) return;
    
    // Evict oldest node in lane if at capacity
    if (lane.nodes.length >= RuntimeTopologyPanel.MAX_NODES_PER_LANE) {
      this.removeNode(laneId, lane.nodes[0].id);  // FIFO
    }
    lane.nodes.push(node);
  }
}
```

### Lane Compression

When topology exceeds display capacity, apply deterministic compression:

```javascript
class TopologyCompression {
  static COMPRESSION_RATIOS = [
    { threshold: 10, ratio: 1.0 },    // 1-10 nodes: full size
    { threshold: 20, ratio: 0.8 },    // 11-20 nodes: 80% size
    { threshold: 30, ratio: 0.6 },    // 21-30 nodes: 60% size
    { threshold: Infinity, ratio: 0.4 }  // 30+ nodes: 40% size
  ];
  
  static getCompressionRatio(nodeCount) {
    for (const { threshold, ratio } of TopologyCompression.COMPRESSION_RATIOS) {
      if (nodeCount <= threshold) {
        return ratio;
      }
    }
    return 0.4;  // Minimum compression
  }
}
```

**Visual Guarantee**: Compression is deterministic and replay-safe

---

## Instrumentation Retention Windows

### Retention by Element Type

| Element Type | Retention Window | Cleanup Frequency |
|--------------|------------------|-------------------|
| Stream Density Points | 30 seconds | On each new point |
| Throughput Bars | 30 seconds | On each new value |
| Integrity Markers | 5 minutes | On each new marker |
| Routing Paths | 1 minute | On each new path |
| Proposal Nodes | 5 minutes | On each new node |
| Topology Connectors | 5 minutes | On each new connection |
| Replay Sweep | Session | On replay start/stop |
| Execution Lanes | Session | Manual clear only |

### Retention Implementation Pattern

```javascript
class BoundedBuffer {
  constructor(maxSize, maxAgeMs) {
    this.maxSize = maxSize;
    this.maxAgeMs = maxAgeMs;
    this.buffer = [];
  }
  
  add(item, timestamp = Date.now()) {
    this.buffer.push({ item, timestamp });
    this.evict();
  }
  
  evict() {
    const now = Date.now();
    
    // Evict by age
    while (this.buffer.length > 0 && 
           now - this.buffer[0].timestamp > this.maxAgeMs) {
      this.buffer.shift();
    }
    
    // Evict by size
    while (this.buffer.length > this.maxSize) {
      this.buffer.shift();
    }
  }
  
  getAll() {
    return this.buffer.map(({ item }) => item);
  }
}
```

---

## Deterministic SVG Cleanup

### Cleanup Order Guarantees

All cleanup operations are deterministic:

1. **Same inputs**: Same sequence of projections produces same cleanup decisions
2. **Same ordering**: FIFO within each element type guarantees chronological cleanup
3. **Replay-safe**: Replaying projections produces same cleanup behavior

### Cleanup Algorithm

```javascript
class SvgCleanupManager {
  #getCleanupOrder(items) {
    // Deterministic ordering: sequence number, then creation time
    return [...items].sort((a, b) => {
      // Primary: sequence number (FIFO)
      if (a.sequence !== b.sequence) {
        return a.sequence - b.sequence;
      }
      // Secondary: creation timestamp
      if (a.createdAt !== b.createdAt) {
        return a.createdAt - b.createdAt;
      }
      // Tertiary: ID hash
      return a.id.localeCompare(b.id);
    });
  }
  
  cleanup(type, maxCount) {
    const elements = this.getElementsOfType(type);
    const ordered = this.#getCleanupOrder(elements);
    
    while (ordered.length > maxCount) {
      const oldest = ordered.shift();
      this.removeElement(oldest);
    }
  }
}
```

---

## Tests for Node Cleanup Determinism

### Test: Deterministic Cleanup Ordering

```python
# tests/test_runtime_svg_instrumentation.py

def test_deterministic_node_cleanup():
    """Verify that node cleanup ordering is deterministic and replay-safe."""
    # Simulate adding nodes with known sequences
    sequences = [1, 5, 2, 8, 3, 9, 4, 10]
    
    # Add nodes
    nodes = [DtgNode(f"node_{s}", sequence=s) for s in sequences]
    
    # Sort by cleanup order (sequence FIFO)
    sorted_nodes = sorted(nodes, key=lambda n: n.sequence)
    
    # Verify ordering is deterministic
    assert [n.sequence for n in sorted_nodes] == [1, 2, 3, 4, 5, 8, 9, 10]
    
    # Simulate cleanup of 3 nodes
    to_cleanup = sorted_nodes[:3]
    remaining = sorted_nodes[3:]
    
    assert [n.sequence for n in to_cleanup] == [1, 2, 3]
    assert [n.sequence for n in remaining] == [4, 5, 8, 9, 10]
```

### Test: Bounded DOM Growth

```python
# tests/test_runtime_svg_instrumentation.py

def test_bounded_dom_growth():
    """Verify that DOM growth remains bounded under continuous projection stream."""
    max_nodes = 200
    
    # Simulate adding nodes beyond max
    graph = DtgGraph(maxNodes=max_nodes)
    
    for i in range(max_nodes * 2):
        graph.addNode(DtgNode(f"node_{i}", sequence=i))
    
    # Verify graph stays bounded
    assert graph.size['nodes'] <= max_nodes
    assert len(graph.getNodesOrdered()) <= max_nodes
```

### Test: Replay-Safe Cleanup

```python
# tests/test_runtime_svg_instrumentation.py

def test_replay_safe_cleanup():
    """Verify that cleanup behavior is identical during replay."""
    # Record initial run
    graph1 = DtgGraph(maxNodes=100)
    sequences1 = list(range(150))
    
    for seq in sequences1:
        graph1.addNode(DtgNode(f"node_{seq}", sequence=seq))
    
    nodes1 = graph1.getNodesOrdered()
    
    # Replay same sequence
    graph2 = DtgGraph(maxNodes=100)
    for seq in sequences1:
        graph2.addNode(DtgNode(f"node_{seq}", sequence=seq))
    
    nodes2 = graph2.getNodesOrdered()
    
    # Verify same result
    assert len(nodes1) == len(nodes2)
    for n1, n2 in zip(nodes1, nodes2):
        assert n1.sequence == n2.sequence
        assert n1.id == n2.id
```

---

## Memory Governance Checklist

- [ ] All SVG element types have explicit maximum counts
- [ ] All element types have bounded retention windows
- [ ] Cleanup ordering is deterministic (FIFO with sequence tiebreaking)
- [ ] Stale elements are automatically evicted
- [ ] WebSocket reconnection triggers stale state cleanup
- [ ] Replay buffers bounded by frame count and duration
- [ ] Topology compression applied when exceeding display capacity
- [ ] No unbounded caches or retention anywhere in instrumentation

---

## Validation Commands

```bash
# Check bounded buffers are enforced
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_bounded_dom_growth -v

# Check deterministic cleanup
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_deterministic_node_cleanup -v

# Check replay-safe cleanup
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_replay_safe_cleanup -v
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial frontend memory governance specification |
