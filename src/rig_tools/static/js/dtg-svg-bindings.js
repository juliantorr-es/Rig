/** Decision Trace Graph (DTG) SVG Bindings
 *
 * PHASE 1: Deterministic DTG SVG Bindings
 *
 * Core doctrine:
 * - Deterministic SVG graph bindings
 * - Replay-safe DTG rendering
 * - Bounded graph state
 * - Projection-derived graph topology
 * - Execution lineage visualization
 * - Proposal lineage visualization
 * - NO force-directed random layouts
 * - NO arbitrary graph positioning
 * - NO hidden topology mutation
 *
 * This module provides:
 * - Deterministic node IDs for DTG elements
 * - Deterministic edge ordering
 * - Replay-safe graph sequencing
 * - Bounded graph expansion
 * - Projection-only rendering
 *
 * Visualizes:
 * - Proposal chains
 * - Runtime routing transitions
 * - Integrity transitions
 * - Replay lineage
 * - Capability escalation paths
 * - Runtime supervision branches
 */

// =============================================================================
// Constants
// =============================================================================

/** SVG namespace */
const SVG_NS = 'http://www.w3.org/2000/svg';

/** DTG-specific constants */
const DTG_CONSTANTS = {
  // Maximum nodes in a single DTG view
  MAX_NODES: 200,
  
  // Maximum edges in a single DTG view
  MAX_EDGES: 500,
  
  // Maximum graph depth (proposal chain length)
  MAX_DEPTH: 50,
  
  // Maximum branching factor per node
  MAX_BRANCHING_FACTOR: 10,
  
  // Node dimensions
  NODE_WIDTH: 40,
  NODE_HEIGHT: 30,
  NODE_MIN_RADIUS: 12,
  NODE_PADDING: 8,
  
  // Edge dimensions
  EDGE_STROKE_THIN: 1,
  EDGE_STROKE_NORMAL: 1.5,
  EDGE_STROKE_THICK: 2,
  EDGE_STROKE_HEAVY: 3,
  
  // Layout spacing
  LAYER_SPACING: 80,
  NODE_SPACING: 60,
  RANK_SPACING: 50,
  
  // Animation bounds
  MAX_ANIMATION_FRAMES: 100,
  MAX_REPLAY_FRAMES: 200
};

/** DTG node kinds */
export const DtgNodeKind = {
  ROOT: 'root',
  PROPOSAL: 'proposal',
  DECISION: 'decision',
  ROUTING: 'routing',
  INTEGRITY: 'integrity',
  EXECUTION: 'execution',
  BRANCH: 'branch',
  MERGE: 'merge',
  SUPERVISION: 'supervision',
  CAPABILITY: 'capability',
  REPLAY: 'replay',
  TERMINAL: 'terminal'
};

/** DTG edge kinds */
export const DtgEdgeKind = {
  PROPOSAL: 'proposal',
  ACCEPT: 'accept',
  REJECT: 'reject',
  ROUTE: 'route',
  ESCALATE: 'escalate',
  SUPERVISE: 'supervise',
  INTEGRITY_CHECK: 'integrity-check',
  INTEGRITY_VIOLATION: 'integrity-violation',
  REPLAY_LINK: 'replay-link',
  CAPABILITY: 'capability',
  SEQUENCE: 'sequence',
  ALTERNATIVE: 'alternative'
};

/** DTG node states */
export const DtgNodeState = {
  PENDING: 'pending',
  ACTIVE: 'active',
  ACCEPTED: 'accepted',
  REJECTED: 'rejected',
  EXECUTING: 'executing',
  COMPLETE: 'complete',
  FAILED: 'failed',
  STALLED: 'stalled',
  INTEGRITY_OK: 'integrity-ok',
  INTEGRITY_WARNING: 'integrity-warning',
  INTEGRITY_ERROR: 'integrity-error',
  Supervised: 'supervised',
  ESCALATED: 'escalated',
  ROUTED: 'routed'
};

/** DTG edge states */
export const DtgEdgeState = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  COMPLETE: 'complete',
  FAILED: 'failed',
  STALLED: 'stalled',
  VIOLATED: 'violated',
  VERIFIED: 'verified',
  SUPERVISED: 'supervised'
};

// Color palette for DTG visualization
export const DTG_COLORS = {
  // Node colors by kind
  NODE_ROOT: 'var(--color-executing, #4CAF50)',
  NODE_PROPOSAL: 'var(--color-streaming, #2196F3)',
  NODE_DECISION: 'var(--color-proposing, #FF9800)',
  NODE_ROUTING: 'var(--color-validating, #9C27B0)',
  NODE_INTEGRITY: 'var(--color-failure, #F44336)',
  NODE_EXECUTION: 'var(--color-complete, #8BC34A)',
  NODE_BRANCH: 'var(--color-integrity-warning, #FFC107)',
  NODE_MERGE: 'var(--color-capability-default, #607D8B)',
  NODE_SUPERVISION: 'var(--color-capability-restricted, #E91E63)',
  NODE_CAPABILITY: 'var(--color-capability-elevated, #FF5722)',
  NODE_REPLAY: 'var(--color-replaying, #00BCD4)',
  NODE_TERMINAL: 'var(--color-stalled, #795548)',
  
  // Node colors by state
  NODE_PENDING: 'var(--color-idle, #9E9E9E)',
  NODE_ACTIVE: 'var(--color-streaming, #2196F3)',
  NODE_ACCEPTED: 'var(--color-executing, #4CAF50)',
  NODE_REJECTED: 'var(--color-failure, #F44336)',
  NODE_EXECUTING: 'var(--color-proposing, #FF9800)',
  NODE_COMPLETE: 'var(--color-complete, #8BC34A)',
  NODE_FAILED: 'var(--color-failure, #F44336)',
  NODE_STALLED: 'var(--color-stalled, #795548)',
  NODE_INTEGRITY_OK: 'var(--color-integrity-ok, #4CAF50)',
  NODE_INTEGRITY_WARNING: 'var(--color-integrity-warning, #FFC107)',
  NODE_INTEGRITY_ERROR: 'var(--color-integrity-error, #F44336)',
  
  // Edge colors by kind
  EDGE_PROPOSAL: 'var(--color-streaming, #2196F3)',
  EDGE_ACCEPT: 'var(--color-executing, #4CAF50)',
  EDGE_REJECT: 'var(--color-failure, #F44336)',
  EDGE_ROUTE: 'var(--color-validating, #9C27B0)',
  EDGE_ESCALATE: 'var(--color-capability-elevated, #FF5722)',
  EDGE_SUPERVISE: 'var(--color-capability-restricted, #E91E63)',
  EDGE_INTEGRITY_CHECK: 'var(--color-integrity-ok, #4CAF50)',
  EDGE_INTEGRITY_VIOLATION: 'var(--color-integrity-error, #F44336)',
  EDGE_REPLAY_LINK: 'var(--color-replaying, #00BCD4)',
  EDGE_CAPABILITY: 'var(--color-capability-default, #607D8B)',
  EDGE_SEQUENCE: 'var(--color-text-muted, #607D8B)',
  EDGE_ALTERNATIVE: 'var(--color-integrity-warning, #FFC107)',
  
  // Edge colors by state
  EDGE_ACTIVE: 'var(--color-streaming, #2196F3)',
  EDGE_INACTIVE: 'var(--color-idle, #9E9E9E)',
  EDGE_COMPLETE: 'var(--color-complete, #4CAF50)',
  EDGE_FAILED: 'var(--color-failure, #F44336)',
  EDGE_STALLED: 'var(--color-stalled, #795548)',
  EDGE_VIOLATED: 'var(--color-integrity-error, #F44336)',
  EDGE_VERIFIED: 'var(--color-integrity-ok, #4CAF50)',
  EDGE_SUPERVISED: 'var(--color-capability-restricted, #E91E63)',
  
  // Background and text
  BACKGROUND: 'var(--color-background, #1E1E1E)',
  FOREGROUND: 'var(--color-foreground, #E0E0E0)',
  TEXT_PRIMARY: 'var(--color-text, #E0E0E0)',
  TEXT_SECONDARY: 'var(--color-text-muted, #B0B0B0)',
  TEXT_MUTED: 'var(--color-text-muted, #808080)',
  
  // Opacity levels
  OPACITY_HIGH: 1.0,
  OPACITY_MEDIUM: 0.7,
  OPACITY_LOW: 0.4,
  OPACITY_MIN: 0.2
};

// =============================================================================
// Utility Functions
// =============================================================================

/** Create SVG element with attributes */
function createSvgElement(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, String(value));
  }
  return el;
}

/** Generate deterministic SVG ID for DTG elements
 * Uses hash-based approach matching the svgId function from svg-runtime-instrumentation.js
 */
export function dtgId(prefix, ...components) {
  const parts = [String(prefix), ...components.map(c => String(c || ''))].filter(p => p);
  const combined = parts.join('|');
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Keep within 32-bit range
  }
  const hex = Math.abs(hash).toString(16).padStart(8, '0');
  return `dtg-${prefix}-${hex.substring(0, 8)}`;
}

/** Simple deterministic hash for ordering */
function deterministicHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash);
}

/** Map value from one range to another */
function mapRange(value, inMin, inMax, outMin, outMax) {
  const clamped = clamp(value, inMin, inMax);
  const inRange = inMax - inMin;
  const outRange = outMax - outMin;
  if (inRange === 0) return outMin;
  return outMin + ((clamped - inMin) / inRange) * outRange;
}

/** Clamp value to range */
function clamp(value, min, max) {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/** 2D point */
export function point(x, y) {
  return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
}

/** Rectangle bounds */
export function rect(x, y, width, height) {
  return {
    x: Math.round(x * 100) / 100,
    y: Math.round(y * 100) / 100,
    width: Math.round(width * 100) / 100,
    height: Math.round(height * 100) / 100
  };
}

/** Size */
export function size(width, height) {
  return { width: Math.round(width * 100) / 100, height: Math.round(height * 100) / 100 };
}

/** Center of rectangle */
export function centerOf(bounds) {
  return point(
    bounds.x + bounds.width / 2,
    bounds.y + bounds.height / 2
  );
}

// =============================================================================
// DTG Node Class
// =============================================================================

/** Decision Trace Graph Node
 * Represents a single node in the DTG with deterministic positioning
 */
export class DtgNode {
  constructor(id, options = {}) {
    this.id = String(id);
    this.kind = options.kind || DtgNodeKind.DECISION;
    this.label = options.label || this.id;
    this.state = options.state || DtgNodeState.PENDING;
    this.sequence = options.sequence || 0;
    this.depth = options.depth || 0;
    this.layer = options.layer || 0;
    this.branchIndex = options.branchIndex || 0;
    
    // Projection-derived properties
    this.proposalId = options.proposalId || '';
    this.runtimeId = options.runtimeId || '';
    this.capability = options.capability || '';
    this.provider = options.provider || '';
    this.trustTier = options.trustTier || '';
    
    // Lineage tracking
    this.parentId = options.parentId || null;
    this.childrenIds = options.childrenIds || [];
    this.predecessors = options.predecessors || [];
    this.successors = options.successors || [];
    
    // Replay properties
    this.replaySequence = options.replaySequence || 0;
    this.isReplayAnchor = options.isReplayAnchor || false;
    this.isDeterministic = options.isDeterministic || true;
    
    // Integrity properties
    this.integrityState = options.integrityState || 'ok';
    this.violationCount = options.violationCount || 0;
    this.divergenceHash = options.divergenceHash || null;
    
    // Size properties
    this.width = options.width || DTG_CONSTANTS.NODE_WIDTH;
    this.height = options.height || DTG_CONSTANTS.NODE_HEIGHT;
    
    // Position (computed by layout)
    this.x = options.x || 0;
    this.y = options.y || 0;
    
    // Visual properties
    this.visible = options.visible !== false;
    this.opacity = options.opacity !== undefined ? options.opacity : DTG_COLORS.OPACITY_HIGH;
  }
  
  /** Generate deterministic ID for SVG element */
  get svgId() {
    return dtgId('node', this.id, this.sequence);
  }
  
  /** Generate group ID for this node's elements */
  get groupId() {
    return dtgId('node-group', this.id, this.sequence);
  }
  
  /** Get color based on state */
  get fillColor() {
    const stateColors = {
      [DtgNodeState.PENDING]: DTG_COLORS.NODE_PENDING,
      [DtgNodeState.ACTIVE]: DTG_COLORS.NODE_ACTIVE,
      [DtgNodeState.ACCEPTED]: DTG_COLORS.NODE_ACCEPTED,
      [DtgNodeState.REJECTED]: DTG_COLORS.NODE_REJECTED,
      [DtgNodeState.EXECUTING]: DTG_COLORS.NODE_EXECUTING,
      [DtgNodeState.COMPLETE]: DTG_COLORS.NODE_COMPLETE,
      [DtgNodeState.FAILED]: DTG_COLORS.NODE_FAILED,
      [DtgNodeState.STALLED]: DTG_COLORS.NODE_STALLED,
      [DtgNodeState.INTEGRITY_OK]: DTG_COLORS.NODE_INTEGRITY_OK,
      [DtgNodeState.INTEGRITY_WARNING]: DTG_COLORS.NODE_INTEGRITY_WARNING,
      [DtgNodeState.INTEGRITY_ERROR]: DTG_COLORS.NODE_INTEGRITY_ERROR
    };
    return stateColors[this.state] || DTG_COLORS.NODE_PENDING;
  }
  
  /** Get stroke color based on kind */
  get strokeColor() {
    const kindColors = {
      [DtgNodeKind.ROOT]: DTG_COLORS.NODE_ROOT,
      [DtgNodeKind.PROPOSAL]: DTG_COLORS.NODE_PROPOSAL,
      [DtgNodeKind.DECISION]: DTG_COLORS.NODE_DECISION,
      [DtgNodeKind.ROUTING]: DTG_COLORS.NODE_ROUTING,
      [DtgNodeKind.INTEGRITY]: DTG_COLORS.NODE_INTEGRITY,
      [DtgNodeKind.EXECUTION]: DTG_COLORS.NODE_EXECUTION,
      [DtgNodeKind.BRANCH]: DTG_COLORS.NODE_BRANCH,
      [DtgNodeKind.MERGE]: DTG_COLORS.NODE_MERGE,
      [DtgNodeKind.SUPERVISION]: DTG_COLORS.NODE_SUPERVISION,
      [DtgNodeKind.CAPABILITY]: DTG_COLORS.NODE_CAPABILITY,
      [DtgNodeKind.REPLAY]: DTG_COLORS.NODE_REPLAY,
      [DtgNodeKind.TERMINAL]: DTG_COLORS.NODE_TERMINAL
    };
    return kindColors[this.kind] || DTG_COLORS.FOREGROUND;
  }
  
  /** Get node shape based on kind */
  get shape() {
    const shapes = {
      [DtgNodeKind.ROOT]: 'circle',
      [DtgNodeKind.PROPOSAL]: 'diamond',
      [DtgNodeKind.DECISION]: 'square',
      [DtgNodeKind.ROUTING]: 'hexagon',
      [DtgNodeKind.INTEGRITY]: 'triangle',
      [DtgNodeKind.EXECUTION]: 'rounded-rect',
      [DtgNodeKind.BRANCH]: 'fork',
      [DtgNodeKind.MERGE]: 'merge',
      [DtgNodeKind.SUPERVISION]: 'star',
      [DtgNodeKind.CAPABILITY]: 'octagon',
      [DtgNodeKind.REPLAY]: 'replay',
      [DtgNodeKind.TERMINAL]: 'terminal'
    };
    return shapes[this.kind] || 'rounded-rect';
  }
  
  /** Convert to JSON */
  toJSON() {
    return {
      id: this.id,
      kind: this.kind,
      label: this.label,
      state: this.state,
      sequence: this.sequence,
      depth: this.depth,
      layer: this.layer,
      branchIndex: this.branchIndex,
      proposalId: this.proposalId,
      runtimeId: this.runtimeId,
      capability: this.capability,
      provider: this.provider,
      trustTier: this.trustTier,
      parentId: this.parentId,
      childrenIds: this.childrenIds,
      predecessors: this.predecessors,
      successors: this.successors,
      replaySequence: this.replaySequence,
      isReplayAnchor: this.isReplayAnchor,
      isDeterministic: this.isDeterministic,
      integrityState: this.integrityState,
      violationCount: this.violationCount,
      divergenceHash: this.divergenceHash,
      x: this.x,
      y: this.y,
      width: this.width,
      height: this.height,
      visible: this.visible,
      opacity: this.opacity
    };
  }
  
  /** Create a deep copy */
  clone() {
    return new DtgNode(this.id, { ...this.toJSON() });
  }
}

// =============================================================================
// DTG Edge Class
// =============================================================================

/** Decision Trace Graph Edge
 * Represents a connection between DTG nodes with deterministic routing
 */
export class DtgEdge {
  constructor(id, options = {}) {
    this.id = String(id);
    this.kind = options.kind || DtgEdgeKind.SEQUENCE;
    this.state = options.state || DtgEdgeState.INACTIVE;
    this.sequence = options.sequence || 0;
    this.weight = options.weight || 1;
    
    // Connection endpoints
    this.sourceId = options.sourceId || '';
    this.targetId = options.targetId || '';
    
    // Projection-derived properties
    this.proposalId = options.proposalId || '';
    this.runtimeId = options.runtimeId || '';
    this.capability = options.capability || '';
    
    // Lineage tracking
    this.isReplayEdge = options.isReplayEdge || false;
    this.replaySequence = options.replaySequence || 0;
    
    // Integrity properties
    this.integrityState = options.integrityState || 'ok';
    this.violationCount = options.violationCount || 0;
    
    // Visual properties
    this.visible = options.visible !== false;
    this.opacity = options.opacity !== undefined ? options.opacity : DTG_COLORS.OPACITY_HIGH;
    this.strokeWidth = options.strokeWidth || DTG_CONSTANTS.EDGE_STROKE_NORMAL;
    
    // Layout properties (computed)
    this.sourceX = options.sourceX || 0;
    this.sourceY = options.sourceY || 0;
    this.targetX = options.targetX || 0;
    this.targetY = options.targetY || 0;
    this.controlPoints = options.controlPoints || [];
  }
  
  /** Generate deterministic ID for SVG element */
  get svgId() {
    return dtgId('edge', this.sourceId, this.targetId, this.sequence);
  }
  
  /** Get color based on state and kind */
  get strokeColor() {
    // Edge color is primarily determined by state, then by kind
    const stateColors = {
      [DtgEdgeState.ACTIVE]: DTG_COLORS.EDGE_ACTIVE,
      [DtgEdgeState.INACTIVE]: DTG_COLORS.EDGE_INACTIVE,
      [DtgEdgeState.COMPLETE]: DTG_COLORS.EDGE_COMPLETE,
      [DtgEdgeState.FAILED]: DTG_COLORS.EDGE_FAILED,
      [DtgEdgeState.STALLED]: DTG_COLORS.EDGE_STALLED,
      [DtgEdgeState.VIOLATED]: DTG_COLORS.EDGE_VIOLATED,
      [DtgEdgeState.VERIFIED]: DTG_COLORS.EDGE_VERIFIED,
      [DtgEdgeState.SUPERVISED]: DTG_COLORS.EDGE_SUPERVISED
    };
    return stateColors[this.state] || DTG_COLORS.EDGE_INACTIVE;
  }
  
  /** Get stroke width based on weight */
  get computedStrokeWidth() {
    const widths = {
      1: DTG_CONSTANTS.EDGE_STROKE_THIN,
      2: DTG_CONSTANTS.EDGE_STROKE_NORMAL,
      3: DTG_CONSTANTS.EDGE_STROKE_THICK,
      4: DTG_CONSTANTS.EDGE_STROKE_HEAVY
    };
    return widths[this.weight] || DTG_CONSTANTS.EDGE_STROKE_NORMAL;
  }
  
  /** Convert to JSON */
  toJSON() {
    return {
      id: this.id,
      kind: this.kind,
      state: this.state,
      sequence: this.sequence,
      weight: this.weight,
      sourceId: this.sourceId,
      targetId: this.targetId,
      proposalId: this.proposalId,
      runtimeId: this.runtimeId,
      capability: this.capability,
      isReplayEdge: this.isReplayEdge,
      replaySequence: this.replaySequence,
      integrityState: this.integrityState,
      violationCount: this.violationCount,
      visible: this.visible,
      opacity: this.opacity,
      strokeWidth: this.strokeWidth,
      sourceX: this.sourceX,
      sourceY: this.sourceY,
      targetX: this.targetX,
      targetY: this.targetY,
      controlPoints: this.controlPoints
    };
  }
  
  /** Create a deep copy */
  clone() {
    return new DtgEdge(this.id, { ...this.toJSON() });
  }
}

// =============================================================================
// DTG Graph Class
// =============================================================================

/** Decision Trace Graph
 * Manages the complete DTG with bounded state and deterministic ordering
 */
export class DtgGraph {
  constructor(options = {}) {
    this.id = options.id || 'dtg-default';
    this.nodes = new Map();
    this.edges = new Map();
    this.nodeIndex = new Map(); // id -> node
    this.edgeIndex = new Map(); // sourceId|targetId|sequence -> edge
    
    // Bounded state
    this.maxNodes = options.maxNodes || DTG_CONSTANTS.MAX_NODES;
    this.maxEdges = options.maxEdges || DTG_CONSTANTS.MAX_EDGES;
    this.maxDepth = options.maxDepth || DTG_CONSTANTS.MAX_DEPTH;
    
    // Layout bounds
    this.bounds = options.bounds || rect(0, 0, 800, 600);
    
    // Sequence tracking for replay safety
    this.lastSequence = 0;
    this.lastReplaySequence = 0;
    
    // Graph metadata
    this.creationTime = options.creationTime || Date.now();
    this.lastUpdateTime = this.creationTime;
    this.version = options.version || 0;
    
    // Layout state
    this.layoutDirty = true;
    this:layout = options.layout || 'hierarchical';
  }
  
  /** Add a node to the graph with bounded checking */
  addNode(nodeOrOptions) {
    const node = nodeOrOptions instanceof DtgNode ? nodeOrOptions : new DtgNode(nodeOrOptions.id, nodeOrOptions);
    
    // Check bounds
    if (this.nodes.size >= this.maxNodes) {
      // Evict oldest node
      this._evictOldestNode();
    }
    
    // Check depth
    if (node.depth > this.maxDepth) {
      node.visible = false; // Hide nodes beyond max depth
    }
    
    this.nodes.set(node.id, node);
    this.nodeIndex.set(node.id, node);
    this.lastSequence = Math.max(this.lastSequence, node.sequence);
    this.lastUpdateTime = Date.now();
    this.version++;
    this.layoutDirty = true;
    
    return node;
  }
  
  /** Add an edge to the graph with bounded checking */
  addEdge(edgeOrOptions) {
    const edge = edgeOrOptions instanceof DtgEdge ? edgeOrOptions : new DtgEdge(edgeOrOptions.id, edgeOrOptions);
    
    // Check bounds
    if (this.edges.size >= this.maxEdges) {
      this._evictOldestEdge();
    }
    
    const edgeKey = this._edgeKey(edge);
    this.edges.set(edgeKey, edge);
    this.edgeIndex.set(edgeKey, edge);
    this.lastSequence = Math.max(this.lastSequence, edge.sequence);
    this.lastUpdateTime = Date.now();
    this.version++;
    this.layoutDirty = true;
    
    return edge;
  }
  
  /** Remove a node and its associated edges */
  removeNode(nodeId) {
    const node = this.nodes.get(nodeId);
    if (!node) return false;
    
    // Remove edges connected to this node
    const edgesToRemove = [];
    for (const [key, edge] of this.edges) {
      if (edge.sourceId === nodeId || edge.targetId === nodeId) {
        edgesToRemove.push(key);
      }
    }
    
    for (const key of edgesToRemove) {
      this.edges.delete(key);
      this.edgeIndex.delete(key);
    }
    
    this.nodes.delete(nodeId);
    this.nodeIndex.delete(nodeId);
    this.lastUpdateTime = Date.now();
    this.version++;
    this.layoutDirty = true;
    
    return true;
  }
  
  /** Remove an edge */
  removeEdge(edgeKeyOrEdge) {
    const key = typeof edgeKeyOrEdge === 'string' ? edgeKeyOrEdge : this._edgeKey(edgeKeyOrEdge);
    this.edges.delete(key);
    this.edgeIndex.delete(key);
    this.lastUpdateTime = Date.now();
    this.version++;
    this.layoutDirty = true;
    return true;
  }
  
  /** Get node by ID */
  getNode(nodeId) {
    return this.nodeIndex.get(nodeId);
  }
  
  /** Get edge by key */
  getEdge(edgeKey) {
    return this.edgeIndex.get(edgeKey);
  }
  
  /** Get edges for a node */
  getEdgesForNode(nodeId, direction = 'both') {
    const edges = [];
    for (const [key, edge] of this.edges) {
      const matchesSource = edge.sourceId === nodeId;
      const matchesTarget = edge.targetId === nodeId;
      
      if (direction === 'out' && matchesSource) edges.push(edge);
      if (direction === 'in' && matchesTarget) edges.push(edge);
      if (direction === 'both' && (matchesSource || matchesTarget)) edges.push(edge);
    }
    return edges;
  }
  
  /** Get children nodes */
  getChildren(nodeId) {
    const node = this.getNode(nodeId);
    if (!node) return [];
    return node.childrenIds.map(id => this.getNode(id)).filter(Boolean);
  }
  
  /** Get parent node */
  getParent(nodeId) {
    const node = this.getNode(nodeId);
    if (!node || !node.parentId) return null;
    return this.getNode(node.parentId);
  }
  
  /** Get root nodes */
  getRoots() {
    return Array.from(this.nodes.values())
      .filter(n => !n.parentId || !this.getNode(n.parentId));
  }
  
  /** Get leaf nodes */
  getLeaves() {
    return Array.from(this.nodes.values())
      .filter(n => n.childrenIds.length === 0 || 
                   n.childrenIds.every(id => !this.getNode(id)));
  }
  
  /** Get nodes in deterministic order (replay-safe) */
  getNodesOrdered() {
    return Array.from(this.nodes.values())
      .sort((a, b) => {
        // Primary sort: sequence
        if (a.sequence !== b.sequence) return a.sequence - b.sequence;
        // Secondary sort: depth
        if (a.depth !== b.depth) return a.depth - b.depth;
        // Tertiary sort: layer
        if (a.layer !== b.layer) return a.layer - b.layer;
        // Final sort: deterministic hash of id
        return deterministicHash(a.id) - deterministicHash(b.id);
      });
  }
  
  /** Get edges in deterministic order (replay-safe) */
  getEdgesOrdered() {
    const edges = Array.from(this.edges.values());
    return edges.sort((a, b) => {
      // Primary sort: sequence
      if (a.sequence !== b.sequence) return a.sequence - b.sequence;
      // Secondary sort: source then target
      const aSourceHash = deterministicHash(a.sourceId);
      const bSourceHash = deterministicHash(b.sourceId);
      if (aSourceHash !== bSourceHash) return aSourceHash - bSourceHash;
      return deterministicHash(a.targetId) - deterministicHash(b.targetId);
    });
  }
  
  /** Clear the graph */
  clear() {
    this.nodes.clear();
    this.edges.clear();
    this.nodeIndex.clear();
    this.edgeIndex.clear();
    this.lastSequence = 0;
    this.lastReplaySequence = 0;
    this.version++;
    this.layoutDirty = true;
  }
  
  /** Check if graph is empty */
  get isEmpty() {
    return this.nodes.size === 0;
  }
  
  /** Get graph size */
  get size() {
    return { nodes: this.nodes.size, edges: this.edges.size };
  }
  
  /** Evict oldest node (internal) */
  _evictOldestNode() {
    if (this.nodes.size === 0) return;
    const sorted = this.getNodesOrdered();
    const oldest = sorted[0];
    this.removeNode(oldest.id);
  }
  
  /** Evict oldest edge (internal) */
  _evictOldestEdge() {
    if (this.edges.size === 0) return;
    const sorted = this.getEdgesOrdered();
    const oldest = sorted[0];
    this.removeEdge(oldest);
  }
  
  /** Generate edge key */
  _edgeKey(edge) {
    return `${edge.sourceId}|${edge.targetId}|${edge.sequence}`;
  }
  
  /** Convert to JSON */
  toJSON() {
    return {
      id: this.id,
      nodes: Array.from(this.nodes.values()).map(n => n.toJSON()),
      edges: Array.from(this.edges.values()).map(e => e.toJSON()),
      bounds: this.bounds,
      maxNodes: this.maxNodes,
      maxEdges: this.maxEdges,
      maxDepth: this.maxDepth,
      lastSequence: this.lastSequence,
      lastReplaySequence: this.lastReplaySequence,
      version: this.version
    };
  }
}

// =============================================================================
// DTG Layout Engine
// =============================================================================

/** Deterministic hierarchical layout for DTG
 * Uses Sugiyama-style layered approach with fixed node ordering
 */
export class DtgHierarchicalLayout {
  constructor(graph, options = {}) {
    this.graph = graph;
    this.bounds = options.bounds || graph.bounds || rect(0, 0, 800, 600);
    this.nodeSpacing = options.nodeSpacing || DTG_CONSTANTS.NODE_SPACING;
    this.layerSpacing = options.layerSpacing || DTG_CONSTANTS.LAYER_SPACING;
    this.rankSpacing = options.rankSpacing || DTG_CONSTANTS.RANK_SPACING;
    this.padding = options.padding || 20;
  }
  
  /** Perform layout */
  layout() {
    const nodes = this.graph.getNodesOrdered();
    const levels = this._assignLevels(nodes);
    this._assignCoordinates(nodes, levels);
    this.graph.layoutDirty = false;
    return { nodes, levels };
  }
  
  /** Assign levels (depth) to nodes */
  _assignLevels(nodes) {
    const levels = new Map();
    const nodeLevels = new Map();
    
    // Start from roots
    const roots = this.graph.getRoots();
    for (const root of roots) {
      levels.set(root.id, 0);
      nodeLevels.set(root.id, 0);
    }
    
    // BFS traversal with deterministic ordering
    const queue = [...roots].sort((a, b) => 
      deterministicHash(a.id) - deterministicHash(b.id)
    );
    
    while (queue.length > 0) {
      const node = queue.shift();
      const children = this.graph.getChildren(node.id);
      
      for (const child of children) {
        const childLevel = nodeLevels.get(node.id) + 1;
        if (!levels.has(child.id)) {
          levels.set(child.id, childLevel);
          nodeLevels.set(child.id, childLevel);
        }
        
        if (!queue.includes(child)) {
          queue.push(child);
        }
      }
    }
    
    return levels;
  }
  
  /** Assign coordinates to nodes based on levels */
  _assignCoordinates(nodes, levels) {
    // Group nodes by level
    const levelNodes = new Map();
    for (const node of nodes) {
      const level = levels.get(node.id) || 0;
      if (!levelNodes.has(level)) {
        levelNodes.set(level, []);
      }
      levelNodes.get(level).push(node);
    }
    
    // Sort nodes within each level deterministically
    const sortedLevels = Array.from(levelNodes.entries())
      .sort((a, b) => a[0] - b[0]);
    
    for (const [level, levelNodeList] of sortedLevels) {
      const sorted = levelNodeList.sort((a, b) => 
        deterministicHash(a.id) - deterministicHash(b.id)
      );
      
      const y = this.padding + level * this.rankSpacing;
      const levelWidth = sorted.length * this.nodeSpacing;
      const startX = (this.bounds.width - levelWidth) / 2;
      
      for (let i = 0; i < sorted.length; i++) {
        const node = sorted[i];
        node.y = y + this.bounds.y;
        node.x = startX + i * this.nodeSpacing + this.bounds.x;
      }
    }
    
    // Update edge coordinates
    for (const edge of this.graph.getEdgesOrdered()) {
      const source = this.graph.getNode(edge.sourceId);
      const target = this.graph.getNode(edge.targetId);
      
      if (source && target) {
        edge.sourceX = source.x + source.width / 2;
        edge.sourceY = source.y + source.height / 2;
        edge.targetX = target.x + target.width / 2;
        edge.targetY = target.y + target.height / 2;
      }
    }
  }
}

// =============================================================================
// DTG SVG Renderer
// =============================================================================

/** Renders DTG to SVG with deterministic bindings */
export class DtgSvgRenderer {
  constructor(graph, options = {}) {
    this.graph = graph;
    this.layout = new DtgHierarchicalLayout(graph, options);
    this.bounds = options.bounds || rect(0, 0, 800, 600);
    this.containerId = options.containerId || dtgId('dtg-container');
    this.elastic = options.elastic || false;
    
    // Rendering options
    this.showLabels = options.showLabels !== false;
    this.showSequenceNumbers = options.showSequenceNumbers || false;
    this.showIntegrityMarkers = options.showIntegrityMarkers || false;
    this.showReplayMarkers = options.showReplayMarkers || false;
  }
  
  /** Render the complete DTG to an SVG element */
  render(parent = null) {
    const startTime = performance.now();
    if (window.__rig_metrics) {
      window.__rig_metrics.lifecycle.renderCalls++;
      window.__rig_metrics.topology.nodeCount = this.graph.nodes.length;
      window.__rig_metrics.topology.edgeCount = this.graph.edges.length;
      this.graph.nodes.forEach(n => window.__rig_metrics.topology.stableNodeIds.add(n.id));
      this.graph.edges.forEach(e => window.__rig_metrics.topology.stableEdgeIds.add(e.id));
    }
    
    // Ensure layout is current
    if (this.graph.layoutDirty) {
      this.layout.layout();
    }
    
    const svg = createSvgElement('svg', {
      id: this.containerId,
      width: String(this.bounds.width),
      height: String(this.bounds.height),
      viewBox: `0 0 ${this.bounds.width} ${this.bounds.height}`,
      'xmlns': SVG_NS,
      class: 'dtg-svg-container',
      'aria-hidden': 'true',
      'focusable': 'false'
    });
    
    // Define gradients and styles
    this._renderDefs(svg);
    
    // Render layers in order: edges first, then nodes
    this._renderEdgesLayer(svg);
    this._renderNodesLayer(svg);
    this._renderLabelsLayer(svg);
    this._renderMarkersLayer(svg);
    
    if (parent) {
      // Benchmark parent clearing if parent.innerHTML is used elsewhere, 
      // but here we just append.
      parent.appendChild(svg);
    }
    
    if (window.__rig_metrics) {
      window.__rig_metrics.lifecycle.totalRenderTimeMs += (performance.now() - startTime);
    }
    
    return svg;
  }
  
  /** Render SVG defs (gradients, markers) */
  _renderDefs(svg) {
    const defs = createSvgElement('defs');
    
    // Arrow marker for edges
    const arrow = createSvgElement('marker', {
      id: dtgId('arrowhead'),
      viewBox: '0 0 10 10',
      refX: '9',
      refY: '5',
      markerWidth: '10',
      markerHeight: '10',
      orient: 'auto-start-reverse'
    });
    
    const arrowPath = createSvgElement('path', {
      d: 'M 0 0 L 10 5 L 0 10 Z',
      fill: DTG_COLORS.EDGE_ACTIVE,
      stroke: 'none'
    });
    arrow.appendChild(arrowPath);
    defs.appendChild(arrow);
    
    svg.appendChild(defs);
  }
  
  /** Render edges layer */
  _renderEdgesLayer(svg) {
    const g = createSvgElement('g', {
      id: dtgId('edges-layer'),
      class: 'dtg-edges-layer'
    });
    
    const edges = this.graph.getEdgesOrdered();
    for (const edge of edges) {
      if (!edge.visible) continue;
      
      const path = this._renderEdge(edge);
      if (path) {
        g.appendChild(path);
      }
    }
    
    svg.appendChild(g);
  }
  
  /** Render a single edge as SVG path */
  _renderEdge(edge) {
    const source = this.graph.getNode(edge.sourceId);
    const target = this.graph.getNode(edge.targetId);
    
    if (!source || !target) return null;
    
    // Straight line for hierarchical layout
    const sx = source.x + source.width / 2;
    const sy = source.y + source.height / 2;
    const tx = target.x + target.width / 2;
    const ty = target.y + target.height / 2;
    
    const d = `M ${sx} ${sy} L ${tx} ${ty}`;
    
    return createSvgElement('path', {
      id: edge.svgId,
      d: d,
      stroke: edge.strokeColor,
      'stroke-width': String(edge.computedStrokeWidth),
      fill: 'none',
      opacity: String(edge.opacity),
      'marker-end': this.showLabels ? `url(#${dtgId('arrowhead')})` : 'none',
      class: `dtg-edge dtg-edge-${edge.kind} dtg-edge-${edge.state}`,
      'data-source': edge.sourceId,
      'data-target': edge.targetId,
      'data-kind': edge.kind,
      'data-state': edge.state,
      'data-sequence': String(edge.sequence)
    });
  }
  
  /** Render nodes layer */
  _renderNodesLayer(svg) {
    const g = createSvgElement('g', {
      id: dtgId('nodes-layer'),
      class: 'dtg-nodes-layer'
    });
    
    const nodes = this.graph.getNodesOrdered();
    for (const node of nodes) {
      if (!node.visible) continue;
      
      const nodeEl = this._renderNode(node);
      if (nodeEl) {
        g.appendChild(nodeEl);
      }
    }
    
    svg.appendChild(g);
  }
  
  /** Render a single node */
  _renderNode(node) {
    const group = createSvgElement('g', {
      id: node.groupId,
      class: `dtg-node dtg-node-${node.kind} dtg-node-${node.state}`,
      'data-id': node.id,
      'data-kind': node.kind,
      'data-state': node.state,
      'data-sequence': String(node.sequence),
      'data-depth': String(node.depth),
      'data-layer': String(node.layer),
      'data-parent': node.parentId || '',
      transform: `translate(${node.x} ${node.y})`
    });
    
    // Render node shape
    const shape = this._renderNodeShape(node);
    if (shape) {
      group.appendChild(shape);
    }
    
    // Render node background
    const bg = this._renderNodeBackground(node);
    if (bg) {
      group.appendChild(bg);
    }
    
    return group;
  }
  
  /** Render node shape based on kind */
  _renderNodeShape(node) {
    const halfWidth = node.width / 2;
    const halfHeight = node.height / 2;
    const cx = halfWidth;
    const cy = halfHeight;
    
    switch (node.shape) {
      case 'circle':
        return createSvgElement('circle', {
          cx: String(cx),
          cy: String(cy),
          r: String(Math.min(halfWidth, halfHeight) * 0.8),
          fill: node.fillColor,
          stroke: node.strokeColor,
          'stroke-width': '1.5',
          opacity: String(node.opacity),
          class: 'dtg-node-shape dtg-node-shape-circle'
        });
      
      case 'diamond':
        return createSvgElement('polygon', {
          points: [
            `${cx},${cy - halfHeight * 0.8}`,
            `${cx + halfWidth * 0.8},${cy}`,
            `${cx},${cy + halfHeight * 0.8}`,
            `${cx - halfWidth * 0.8},${cy}`
          ].join(' '),
          fill: node.fillColor,
          stroke: node.strokeColor,
          'stroke-width': '1.5',
          opacity: String(node.opacity),
          class: 'dtg-node-shape dtg-node-shape-diamond'
        });
      
      case 'square':
        return createSvgElement('rect', {
          x: String(cx - halfWidth * 0.8),
          y: String(cy - halfHeight * 0.8),
          width: String(halfWidth * 1.6),
          height: String(halfHeight * 1.6),
          fill: node.fillColor,
          stroke: node.strokeColor,
          'stroke-width': '1.5',
          opacity: String(node.opacity),
          'rx': '2',
          class: 'dtg-node-shape dtg-node-shape-square'
        });
      
      case 'rounded-rect':
      default:
        return createSvgElement('rect', {
          x: '0',
          y: '0',
          width: String(node.width),
          height: String(node.height),
          fill: node.fillColor,
          stroke: node.strokeColor,
          'stroke-width': '1.5',
          opacity: String(node.opacity),
          rx: '4',
          ry: '4',
          class: 'dtg-node-shape dtg-node-shape-rounded-rect'
        });
    }
  }
  
  /** Render node background (for selected/highlighted states) */
  _renderNodeBackground(node) {
    if (node.state === DtgNodeState.ACTIVE || node.state === DtgNodeState.EXECUTING) {
      return createSvgElement('rect', {
        x: '-4',
        y: '-4',
        width: String(node.width + 8),
        height: String(node.height + 8),
        fill: 'none',
        stroke: 'var(--color-integrity-warning, #FFFF00)',
        'stroke-width': '2',
        opacity: '0.5',
        rx: '6',
        ry: '6',
        class: 'dtg-node-background dtg-node-background-active'
      });
    }
    return null;
  }
  
  /** Render labels layer */
  _renderLabelsLayer(svg) {
    if (!this.showLabels) return;
    
    const g = createSvgElement('g', {
      id: dtgId('labels-layer'),
      class: 'dtg-labels-layer'
    });
    
    const nodes = this.graph.getNodesOrdered();
    for (const node of nodes) {
      if (!node.visible) continue;
      
      const label = this._renderNodeLabel(node);
      if (label) {
        g.appendChild(label);
      }
    }
    
    svg.appendChild(g);
  }
  
  /** Render node label */
  _renderNodeLabel(node) {
    const label = truncateLabel(node.label || node.id, 12);
    
    return createSvgElement('text', {
      x: String(node.x + node.width / 2),
      y: String(node.y + node.height / 2),
      'text-anchor': 'middle',
      'dominant-baseline': 'central',
      fill: DTG_COLORS.TEXT_PRIMARY,
      'font-size': '10',
      'font-family': 'system-ui, sans-serif',
      class: 'dtg-node-label',
      'data-node-id': node.id
    }, label);
  }
  
  /** Render markers layer (integrity, replay, sequence) */
  _renderMarkersLayer(svg) {
    const g = createSvgElement('g', {
      id: dtgId('markers-layer'),
      class: 'dtg-markers-layer'
    });
    
    if (this.showSequenceNumbers) {
      for (const node of this.graph.getNodesOrdered()) {
        if (!node.visible) continue;
        const seq = createSvgElement('text', {
          x: String(node.x + node.width / 2),
          y: String(node.y - 8),
          'text-anchor': 'middle',
          'dominant-baseline': 'bottom',
          fill: DTG_COLORS.TEXT_SECONDARY,
          'font-size': '8',
          'font-family': 'system-ui, sans-serif',
          class: 'dtg-sequence-number'
        }, String(node.sequence));
        g.appendChild(seq);
      }
    }
    
    if (this.showIntegrityMarkers) {
      for (const node of this.graph.getNodesOrdered()) {
        if (!node.visible) continue;
        if (node.violationCount > 0) {
          const marker = createSvgElement('circle', {
            cx: String(node.x + node.width / 2 + 10),
            cy: String(node.y - 8),
            r: '4',
            fill: DTG_COLORS.NODE_INTEGRITY_ERROR,
            class: 'dtg-integrity-marker'
          });
          g.appendChild(marker);
        }
      }
    }
    
    if (this.showReplayMarkers) {
      for (const node of this.graph.getNodesOrdered()) {
        if (!node.visible || !node.isReplayAnchor) continue;
        const marker = createSvgElement('rect', {
          x: String(node.x + node.width / 2 - 4),
          y: String(node.y - 12),
          width: '8',
          height: '8',
          fill: DTG_COLORS.NODE_REPLAY,
          class: 'dtg-replay-marker'
        });
        g.appendChild(marker);
      }
    }
    
    svg.appendChild(g);
  }
}

// =============================================================================
// DTG Geometry Mapper
// =============================================================================

/** Maps projection data to deterministic DTG geometry */
export class DtgGeometryMapper {
  constructor(bounds, options = {}) {
    this.bounds = bounds || rect(0, 0, 800, 600);
    this.padding = options.padding || 20;
    this.maxDepth = options.maxDepth || DTG_CONSTANTS.MAX_DEPTH;
    this.nodeSpacing = options.nodeSpacing || DTG_CONSTANTS.NODE_SPACING;
    this.layerSpacing = options.layerSpacing || DTG_CONSTANTS.LAYER_SPACING;
  }
  
  /** Map projection sequence to X coordinate */
  sequenceToX(sequence, maxSequence = 100) {
    return this.padding + mapRange(
      sequence,
      0,
      maxSequence,
      0,
      this.bounds.width - this.padding * 2
    );
  }
  
  /** Map depth to Y coordinate */
  depthToY(depth) {
    return this.padding + depth * this.layerSpacing;
  }
  
  /** Map node kind to geometry */
  kindToGeometry(kind) {
    const geometries = {
      [DtgNodeKind.ROOT]: { shape: 'circle', width: 48, height: 48 },
      [DtgNodeKind.PROPOSAL]: { shape: 'diamond', width: 44, height: 44 },
      [DtgNodeKind.DECISION]: { shape: 'square', width: 40, height: 40 },
      [DtgNodeKind.ROUTING]: { shape: 'hexagon', width: 52, height: 40 },
      [DtgNodeKind.INTEGRITY]: { shape: 'triangle', width: 44, height: 44 },
      [DtgNodeKind.EXECUTION]: { shape: 'rounded-rect', width: 100, height: 36 },
      [DtgNodeKind.BRANCH]: { shape: 'fork', width: 36, height: 36 },
      [DtgNodeKind.MERGE]: { shape: 'merge', width: 36, height: 36 },
      [DtgNodeKind.SUPERVISION]: { shape: 'star', width: 40, height: 40 },
      [DtgNodeKind.CAPABILITY]: { shape: 'octagon', width: 48, height: 48 },
      [DtgNodeKind.REPLAY]: { shape: 'replay', width: 44, height: 36 },
      [DtgNodeKind.TERMINAL]: { shape: 'terminal', width: 40, height: 40 }
    };
    return geometries[kind] || { shape: 'rounded-rect', width: 80, height: 36 };
  }
  
  /** Map projection to node position */
  projectionToNodePosition(projection) {
    const sequence = projection.sequence || 0;
    const depth = projection.depth || 0;
    const branchIndex = projection.branchIndex || 0;
    
    return point(
      this.sequenceToX(sequence, projection.maxSequence || 100),
      this.depthToY(depth) + branchIndex * this.nodeSpacing / 2
    );
  }
  
  /** Map edge projection to control points */
  projectionToEdgeControlPoints(projection) {
    const source = projection.sourcePosition || point(0, 0);
    const target = projection.targetPosition || point(100, 100);
    
    // Hierarchical layout: straight line
    return [
      point(source.x, source.y),
      point(target.x, target.y)
    ];
  }
}

// =============================================================================
// Utility: truncate label for display
// =============================================================================

function truncateLabel(label, maxLen) {
  if (!label) return '';
  const str = String(label);
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen - 2) + '..';
}

// =============================================================================
// Module Exports
// =============================================================================

export {
  SVG_NS,
  DTG_CONSTANTS,
  DtgNodeKind,
  DtgEdgeKind,
  DtgNodeState,
  DtgEdgeState,
  DTG_COLORS,
  DtgHierarchicalLayout,
  DtgSvgRenderer,
  DtgGeometryMapper,
  createSvgElement,
  dtgId,
  deterministicHash,
  mapRange,
  clamp,
  point,
  rect,
  size,
  centerOf
};
