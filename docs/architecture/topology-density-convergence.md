# Topology Density Convergence

## Summary

This document defines how Rig maintains operational readability of topology visualization under high-density conditions. When dealing with high throughput, long replay sessions, high proposal density, multiple runtime lanes, integrity divergence storms, or routing escalation bursts, topology must remain clear and actionable.

**Core Doctrine:**
- Preserve operational clarity under all conditions
- Preserve replay fidelity during convergence
- Preserve determinism in all density management
- Bounded topology complexity
- Density-aware rendering
- Deterministic lane collapsing
- Replay-safe condensation

---

## Density Conditions

### Condition Categories

Rig topology must handle the following high-stress conditions without losing operational clarity:

| Condition | Description | Metrics |
|-----------|-------------|---------|
| High Throughput | Rapid stream of chunks/tokens | >100 chunks/sec |
| Long Replay | Extended historical playback | >1000 sequences |
| High Proposal Density | Many simultaneous proposals | >50 active proposals |
| Multiple Lanes | Parallel execution contexts | >4 concurrent lanes |
| Integrity Divergence Storm | Many integrity violations | >20 simultaneous warnings |
| Routing Escalation Burst | Rapid capability routing | >10 concurrent escalations |

### Combined Stress Testing

The most challenging scenarios combine multiple conditions:

| Scenario | Throughput | Proposals | Lanes | Violations | Duration |
|----------|------------|-----------|-------|------------|----------|
| Normal | 1-10 | 1-5 | 1-2 | 0-2 | <100 seq |
| Elevated | 10-50 | 5-20 | 2-4 | 2-5 | 100-500 seq |
| Stress | 50-100 | 20-50 | 4-6 | 5-10 | 500-1000 seq |
| Extreme | 100+ | 50+ | 6-8 | 10-20 | 1000+ seq |

---

## Bounded Topology Compression

### Compression Levels

Topology compression applies deterministically based on node count per lane:

| Node Count | Compression Level | Ratio | Visual Effect |
|------------|------------------|-------|---------------|
| 1-10 | None | 1.0 | Full size, full labels |
| 11-20 | Light | 0.8 | 80% size, abbreviated labels |
| 21-30 | Moderate | 0.6 | 60% size, icon-only labels |
| 31-50 | Heavy | 0.5 | 50% size, no labels |
| 51+ | Extreme | 0.4 | 40% size, collapsed view |

### Compression Formula

```javascript
class TopologyCompression {
  static COMPRESSION_LEVELS = [
    { maxNodes: 10, ratio: 1.0, showLabels: true, labelMode: 'full' },
    { maxNodes: 20, ratio: 0.8, showLabels: true, labelMode: 'abbreviated' },
    { maxNodes: 30, ratio: 0.6, showLabels: true, labelMode: 'icon' },
    { maxNodes: 50, ratio: 0.5, showLabels: false, labelMode: 'none' },
    { maxNodes: Infinity, ratio: 0.4, showLabels: false, labelMode: 'none' }
  ];

  static getCompressionLevel(nodeCount) {
    for (const level of TopologyCompression.COMPRESSION_LEVELS) {
      if (nodeCount <= level.maxNodes) {
        return level;
      }
    }
    return TopologyCompression.COMPRESSION_LEVELS[TopologyCompression.COMPRESSION_LEVELS.length - 1];
  }

  static applyCompression(element, nodeCount) {
    const level = this.getCompressionLevel(nodeCount);
    
    // Apply size scaling
    if (element.hasAttribute('width')) {
      const originalWidth = parseFloat(element.getAttribute('width'));
      element.setAttribute('width', String(originalWidth * level.ratio));
    }
    if (element.hasAttribute('height')) {
      const originalHeight = parseFloat(element.getAttribute('height'));
      element.setAttribute('height', String(originalHeight * level.ratio));
    }
    if (element.hasAttribute('r')) {
      const originalRadius = parseFloat(element.getAttribute('r'));
      element.setAttribute('r', String(originalRadius * level.ratio));
    }
    
    // Apply label visibility
    const label = element.querySelector('.dtg-node-label');
    if (label) {
      label.style.display = level.showLabels ? 'block' : 'none';
    }
    
    return level;
  }
}
```

---

## Density-Aware Rendering

### Rendering Strategies by Density

| Density | Strategy | When Applied |
|---------|----------|-------------|
| Low | Full detail | <20 nodes/lane |
| Medium | Simplified | 20-40 nodes/lane |
| High | Aggregated | 40-80 nodes/lane |
| Extreme | Collapsed | 80+ nodes/lane |

### Density Detection

```javascript
class TopologyDensityManager {
  constructor() {
    this.nodeCounts = new Map(); // laneId -> nodeCount
    this.violationCounts = new Map(); // laneId -> violationCount
    this.activeProposals = new Map(); // laneId -> activeProposalCount
    this.curreny = new Map dishes(); // laneId -> currentState
  }

  updateLaneMetrics(laneId, metrics) {
    this.nodeCounts.set(laneId, metrics.nodeCount);
    this.violationCounts.set(laneId, metrics.violationCount);
    this.activeProposals.set(laneId, metrics.activeProposalCount);
    
    this._recalculateDensity(laneId);
  }

  _recalculateDensity(laneId) {
    const nodeCount = this.nodeCounts.get(laneId) || 0;
    const violationCount = this.violationCounts.get(laneId) || 0;
    const proposalCount = this.activeProposals.get(laneId) || 0;
    
    // Combined density score
    const densityScore = Math.sqrt(
      nodeCount * nodeCount +
      violationCount * violationCount * 2 +
      proposalCount * proposalCount * 1.5
    );
    
    return this._classifyDensity(densityScore);
  }

  _classifyDensity(score) {
    if (score < 20) return 'low';
    if (score < 40) return 'medium';
    if (score < 80) return 'high';
    return 'extreme';
  }

  getDensity(laneId) {
    return this._recalculateDensity(laneId);
  }

  needsCompression(laneId) {
    return this.getDensity(laneId) !== 'low';
  }
}
```

---

## Deterministic Lane Collapsing

### Lane Collapse Rules

When total lane count exceeds display capacity, lanes collapse deterministically:

| Total Lanes | Visible Lanes | Collapse Strategy |
|-------------|---------------|-------------------|
| 1-4 | All | None |
| 5-8 | 4 | Fold inactive into "Other" |
| 9-12 | 4 | Fold by activity level |
| 13+ | 4 | Fold by priority, then activity |

### Collapse Priority

Lanes are collapsed based on deterministic priority:

1. **Priority** (highest first):
   - Trusted lanes (never collapsed)
   - Active streaming lanes
   - Lanes with violations
   - Idle lanes

2. **Activity** (among equal priority):
   - Most recent activity first
   - Most proposals first
   - Highest throughput first

3. **Creation** (final tiebreaker):
   - Oldest first

### Collapse Implementation

```javascript
class LaneCollapser {
  static MAX_VISIBLE_LANES = 4;
  
  static collapseLanes(lanes) {
    if (lanes.length <= LaneCollapser.MAX_VISIBLE_LANES) {
      return { visible: lanes, collapsed: [] };
    }
    
    // Sort by priority (deterministic)
    const sorted = [...lanes].sort((a, b) => {
      // Priority 1: Trust tier (trusted never collapsed)
      if (a.trustTier !== b.trustTier) {
        const tierOrder = { trusted: 0, elevated: 1, standard: 2, restricted: 3 };
        return tierOrder[a.trustTier] - tierOrder[b.trustTier];
      }
      
      // Priority 2: Activity state
      const stateOrder = { active: 0, streaming: 0, stalled: 1, idle: 2 };
      const aState = stateOrder[a.state] ?? 999;
      const bState = stateOrder[b.state] ?? 999;
      if (aState !== bState) return aState - bState;
      
      // Priority 3: Most recent activity
      if (a.lastActivity !== b.lastActivity) {
        return b.lastActivity - a.lastActivity; // Newer first
      }
      
      // Priority 4: Most proposals
      if (a.proposalCount !== b.proposalCount) {
        return b.proposalCount - a.proposalCount;
      }
      
      // Priority 5: Highest throughput
      if (a.throughput !== b.throughput) {
        return b.throughput - a.throughput;
      }
      
      // Priority 6: Creation time (oldest first)
      return a.createdAt - b.createdAt;
    });
    
    const visible = sorted.slice(0, LaneCollapser.MAX_VISIBLE_LANES);
    const collapsed = sorted.slice(LaneCollapser.MAX_VISIBLE_LANES);
    
    return { visible, collapsed };
  }

  static createCollapsedLane(collapsedLanes) {
    // Aggregate metrics from collapsed lanes
    const totalNodes = collapsedLanes.reduce((sum, l) => sum + l.nodeCount, 0);
    const totalProposals = collapsedLanes.reduce((sum, l) => sum + l.proposalCount, 0);
    const totalViolations = collapsedLanes.reduce((sum, l) => sum + l.violationCount, 0);
    const highestPriority = Math.min(...collapsedLanes.map(l => 
      { trusted: 0, elevated: 1, standard: 2, restricted: 3 }[l.trustTier]
    ));
    
    const tier = ['trusted', 'elevated', 'standard', 'restricted'][highestPriority];
    
    return {
      id: 'collapsed_other';
      label: `+${collapsedLanes.length} Other Lanes`;
      kind: 'collapsed';
      nodeCount: totalNodes;
      proposalCount: totalProposals;
      violationCount: totalViolations;
      trustTier: tier;
      state: collapsedLanes.some(l => l.state === 'active') ? 'active' : 'idle';
      isCollapsed: true;
      collapsedLaneIds: collapsedLanes.map(l => l.id)
    };
  }
}
```

---

## Replay-Safe Condensation

### Condensation Requirements

Replay condensation must satisfy:
1. **Deterministic**: Same sequence produces same condensation
2. **Reversible**: Can unchanged expanded for detail view
3. **Truthful**: Condensed representation doesn't hide critical state
4. **Bounded**: Maximum complexity always limited

### Condensation Levels for Replay

| Replay Speed | Condensation Level | Detail |
|--------------|--------------------|--------|
| 0.1x-0.5x | None | Full detail |
| 0.5x-1.0x | Light | All primary nodes visible |
| 1.0x-2.0x | Medium | Aggregated nodes |
| 2.0x-5.0x | Heavy | Lane-level summary |
| 5.0x+ | Extreme | Runtime-level summary |

### Replay Condensation Implementation

```javascript
class ReplayCondenser {
  static CONDENSATION_LEVELS = [
    { maxSpeed: 0.5, level: 'none', nodeLimit: Infinity, aggregation: 'none' },
    { maxSpeed: 1.0, level: 'light', nodeLimit: 100, aggregation: 'nodes' },
    { maxSpeed: 2.0, level: 'medium', nodeLimit: 50, aggregation: 'nodes' },
    { maxSpeed: 5.0, level: 'heavy', nodeLimit: 20, aggregation: 'lanes' },
    { maxSpeed: Infinity, level: 'extreme', nodeLimit: 8, aggregation: 'summary' }
  ];

  constructor(replaySpeed, maxNodes = 200) {
    this.replaySpeed = replaySpeed;
    this.maxNodes = maxNodes;
  }

  getLevel() {
    for (const level of ReplayCondenser.CONDENSATION_LEVELS) {
      if (this.replaySpeed <= level.maxSpeed) {
        return level;
      }
    }
    return ReplayCondenser.CONDENSATION_LEVELS[ReplayCondenser.CONDENSATION_LEVELS.length - 1];
  }

  condense(nodes) {
    const level = this.getLevel();
    
    if (level.aggregation === 'none') {
      return nodes; // No condensation
    }
    
    if (level.aggregation === 'nodes') {
      // Keep top N nodes by sequence
      const sorted = [...nodes].sort((a, b) => b.sequence - a.sequence);
      return sorted.slice(0, Math.min(level.nodeLimit, this.maxNodes));
    }
    
    if (level.aggregation === 'lanes') {
      // Group by lane, show lane summary
      const byLane = new Map();
      for (const node of nodes) {
        const laneId = node.laneId || 'default';
        if (!byLane.has(laneId)) {
          byLane.set(laneId, []);
        }
        byLane.get(laneId).push(node);
      }
      
      // Create lane summary nodes
      const summaries = [];
      for (const [laneId, laneNodes] of byLane) {
        const lastNode = laneNodes[laneNodes.length - 1]; // Highest sequence
        summaries.push({
          id: `summary_${laneId}`,
          kind: 'lane-summary',
          laneId: laneId,
          nodeCount: laneNodes.length,
          sequence: lastNode.sequence,
          state: lastNode.state,
          isSummary: true
        });
      }
      
      return summaries;
    }
    
    // Summary level: single runtime node
    const lastNode = nodes[nodes.length - 1];
    return [{
      id: 'runtime-summary',
      kind: 'runtime-summary',
      nodeCount: nodes.length,
      laneCount: new Set(nodes.map(n => n.laneId)).size,
      sequence: lastNode.sequence,
      state: lastNode.state,
      isSummary: true
    }];
  }
}
```

---

## Operational Clarity Preservation

### Clarity Requirements

Under all density conditions, the following must remain visible and distinguishable:

1. **Runtime State**: Overall execution state (streaming, stalled, complete, failed)
2. **Lane Boundaries**: Separation between execution contexts
3. **Integrity Violations**: Any integrity warnings or errors
4. **Active Proposals**: Currently active proposal chains
5. **Current Position**: Where we are in the execution/replay sequence

### Non-Negotiable Visibility

These elements are NEVER hidden, even under extreme density:

| Element | Minimum Size | Rationale |
|---------|--------------|-----------|
| Runtime state indicator | 20px | Overall system state |
| Integrity violation markers | 8px | Critical safety information |
| Current sequence marker | 6px | Position reference |
| Lane boundaries | 1px | Context separation |

### Visual Degradation Ladder

As density increases, elements are hidden in this order:

1. **Level 1**: Abbreviate labels (full → short → icon)
2. **Level 2**: Hide secondary labels
3. **Level 3**: Reduce node size
4. **Level 4**: Hide node labels entirely
5. **Level 5**: Collapse nodes within lane
6. **Level 6**: Collapse lanes

---

## Replay Fidelity Preservation

### Fidelity Requirements

Even when condensed, replay must preserve:

1. **Sequence Order**: Nodes remain in correct sequence order
2. **Causal Relationships**: Parent-child links preserved at higher level
3. **State Transitions**: All state changes visible at some aggregation level
4. **Violation History**: Integrity violations always visible (possibly aggregated)

### Aggregation Fidelity

When aggregating multiple nodes, the aggregate preserves:

- **Max Sequence**: Highest sequence number of aggregated nodes
- **Latest State**: State of the most recent (highest sequence) node
- **Max Severity**: Worst integrity state among aggregated nodes
- **Total Count**: Number of aggregated nodes

---

## Determinism Verification

### Determinism Tests

All density convergence must pass these tests:

```python
# tests/test_runtime_svg_instrumentation.py

def test_density_convergence_deterministic():
    """Same density conditions produce same convergence result."""
    nodes1 = create_test_nodes(150, seed=42)
    nodes2 = create_test_nodes(150, seed=42)
    
    condensed1 = apply_density_convergence(nodes1)
    condensed2 = apply_density_convergence(nodes2)
    
    assert condensed1 == condensed2

def test_replay_condensation_deterministic():
    """Replay condensation is deterministic across runs."""
    frames1 = create_replay_frames(500, speed=10.0)
    frames2 = create_replay_frames(500, speed=10.0)
    
    condensed1 = ReplayCondenser(speed=10.0).condense(frames1)
    condensed2 = ReplayCondenser(speed=10.0).condense(frames2)
    
    assert len(condensed1) == len(condensed2)
    for c1, c2 in zip(condensed1, condensed2):
        assert c1.sequence == c2.sequence
        assert c1.state == c2.state
```

---

## Implementation Checklist

- [ ] Topology compression levels defined
- [ ] Density-aware rendering strategies documented
- [ ] Deterministic lane collapsing implemented
- [ ] Replay-safe condensation implemented
- [ ] Operational clarity preservation verified
- [ ] Replay fidelity preservation verified
- [ ] Determinism tests written and passing

---

## Validation Commands

```bash
# Test topology density convergence
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_density_convergence_deterministic -v

# Test replay condensation
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_replay_condensation_deterministic -v

# Test operational clarity preservation
python3.14 -m pytest tests/test_runtime_svg_instrumentation.py::test_operational_clarity_preserved -v
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial topology density convergence specification |
