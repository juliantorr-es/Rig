/** Runtime Topology Panel Widget
 *
 * PHASE 2: Runtime Topology Visualization
 *
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers as authority source
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering
 * - Replay-safe rendering
 * - Advisory indicators only
 * - Truthful animations derive from real backend/runtime state
 *
 * This widget provides:
 * - Runtime topology visualization
 * - Execution flow lanes
 * - Capability routing paths
 * - Proposal progression visualization
 * - Replay markers
 * - Runtime state transitions
 *
 * Visual language:
 * - Geometric
 * - Restrained
 * - Operational
 * - Instrumentation-oriented
 * - Vector-first
 * - Terminal-era systems aesthetic
 *
 * Runtime state must visibly map to:
 * - Topology state
 * - Routing state
 * - Execution state
 * - Supervision state
 *
 * STRICT NON-GOALS:
 * - No fake motion disconnected from runtime state
 * - No decorative animation loops
 * - No synthetic "AI vibes"
 * - No canvas-heavy rendering
 * - No hidden frontend state
 * - No direct runtime authority in widgets
 * - No frontend fetching
 */

import {
  SvgExecutionLane,
  SvgRoutingPath,
  SvgProposalNode,
  SvgTopologyConnector,
  SvgIntegrityMarker,
  SvgReplaySweep,
  SvgStreamDensityLine,
  SvgThroughputBar,
  SvgInstrumentationLayer,
  ProjectionGeometryMapper,
  SvgAnimationState,
  SvgReconciliationLoopIndicator,
  SvgReconciliationCadenceIndicator,
  SvgDampingIndicator,
  SvgConvergenceIndicator,
  point,
  rect,
  size,
  MotionUtils,
  normalizeRuntimeEventEnvelope,
  normalizeOperationalStatusEnvelope
} from '../svg-runtime-instrumentation.js';

import { RuntimeInstrumentationState } from '../runtime-instrumentation.js';

function _renderReconciliationLayer(parentEl, topologyState) {
  /** Render reconciliation state in topology panel
   * Shows loop indicators for all active reconciliation loops
   */
  const reconcileData = topologyState.getReconciliationState && topologyState.getReconciliationState();
  
  if (!reconcileData || !reconcileData.loops || reconcileData.loops.length === 0) {
    return null;
  }

  const reconcileContainer = document.createElement('div');
  reconcileContainer.className = 'topology-reconciliation-layer';
  reconcileContainer.style.position = 'absolute';
  reconcileContainer.style.top = '8px';
  reconcileContainer.style.right = '8px';
  reconcileContainer.style.display = 'flex';
  reconcileContainer.style.gap = '4px';
  reconcileContainer.style.zIndex = 100;

  // Render small loop indicators for each active loop
  const svgSize = 24;
  
  for (const loop of reconcileData.loops) {
    const loopEl = document.createElement('div');
    loopEl.className = 'topology-loop-indicator';
    loopEl.title = `${loop.loopId}: ${loop.status}`;
    loopEl.style.width = svgSize + 'px';
    loopEl.style.height = svgSize + 'px';

    const bounds = rect(0, 0, svgSize, svgSize);
    const indicator = new SvgReconciliationLoopIndicator(
      `topology-${loop.loopId}`,
      bounds,
      {
        loopId: loop.loopId,
        controllerType: loop.controllerType,
        status: loop.status,
        iterations: loop.iterations || 0,
        convergence: loop.convergence || 0,
        dampingActive: loop.dampingActive || false,
        oscillationDetected: loop.oscillationDetected || false
      }
    );
    indicator.render(loopEl);
    reconcileContainer.appendChild(loopEl);
  }

  return reconcileContainer;
}

// =============================================================================
// Constants
// =============================================================================

/** Maximum lanes in topology view */
const MAX_TOPOLOGY_LANES = 8;

/** Maximum visible proposals per lane */
const MAX_PROPOSALS_PER_LANE = 20;

/** Maximum routing paths */
const MAX_ROUTING_PATHS = 50;

/** Maximum integrity markers */
const MAX_INTEGRITY_MARKERS = 30;

/** Panel dimensions */
const PANEL_MIN_WIDTH = 600;
const PANEL_MIN_HEIGHT = 400;
const PANEL_PADDING = 16;

/** Lane configuration */
const LANE_HEIGHT = 50;
const LANE_GAP = 12;
const LANE_LABEL_WIDTH = 120;

/** Animation timing derived from real state */
const TOPOLOGY_ANIMATION = {
  stateTransition: '200ms',
  proposalFlow: '300ms',
  replaySweep: '250ms',
  integrityFlash: '150ms'
};

const normalizeTopologyEnvelope = normalizeRuntimeEventEnvelope;

// =============================================================================
// Topology Node Model
// =============================================================================

/** Represents a node in the runtime topology
 * Maps directly to runtime/projection state
 */
export class TopologyNode {
  constructor(id, options = {}) {
    this.id = id;
    this.kind = options.kind || 'runtime';
    this.label = options.label || id;
    this.state = options.state || 'idle';
    this.capability = options.capability || 'default';
    this.x = options.x || 0;
    this.y = options.y || 0;
    this.width = options.width || 100;
    this.height = options.height || 40;
    this.connected = options.connected || false;
    this.runtimeId = options.runtimeId || '';
    this.provider = options.provider || '';
    this.trustTier = options.trustTier || 'default';
    this.sequence = options.sequence || 0;
    this.selected = options.selected || false;
    this.violationCount = options.violationCount || 0;
    this.lastActivity = options.lastActivity || 0;
  }

  toJSON() {
    return {
      id: this.id,
      kind: this.kind,
      label: this.label,
      state: this.state,
      capability: this.capability,
      x: this.x,
      y: this.y,
      width: this.width,
      height: this.height,
      connected: this.connected,
      runtimeId: this.runtimeId,
      provider: this.provider,
      trustTier: this.trustTier,
      sequence: this.sequence,
      selected: this.selected,
      violationCount: this.violationCount,
      lastActivity: this.lastActivity
    };
  }

  static fromJSON(data) {
    return new TopologyNode(data.id, data);
  }
}

// =============================================================================
// Topology Edge Model
// =============================================================================

/** Represents a connection/edge between topology nodes */
export class TopologyEdge {
  constructor(id, options = {}) {
    this.id = id;
    this.sourceId = options.sourceId || '';
    this.targetId = options.targetId || '';
    this.kind = options.kind || 'stream';
    this.state = options.state || 'connected';
    this.capability = options.capability || 'default';
    this.sequence = options.sequence || 0;
    this.bytesTransferred = options.bytesTransferred || 0;
    this.tokensTransferred = options.tokensTransferred || 0;
    this.active = options.active || false;
    this.bidirectional = options.bidirectional || false;
  }

  toJSON() {
    return {
      id: this.id,
      sourceId: this.sourceId,
      targetId: this.targetId,
      kind: this.kind,
      state: this.state,
      capability: this.capability,
      sequence: this.sequence,
      bytesTransferred: this.bytesTransferred,
      tokensTransferred: this.tokensTransferred,
      active: this.active,
      bidirectional: this.bidirectional
    };
  }

  static fromJSON(data) {
    return new TopologyEdge(data.id, data);
  }
}

// =============================================================================
// Runtime Topology State
// =============================================================================

/** Manages the complete topology state
 * Bounded, deterministic, replay-safe
 */
export class RuntimeTopologyState {
  constructor(options = {}) {
    this.nodes = new Map();
    this.edges = new Map();
    this.lanes = new Map();
    this.proposals = new Map();
    this.integrityMarkers = new Map();
    this.replayState = null;
    this.globalState = options.globalState || RuntimeInstrumentationState.IDLE;
    this.sequenceCounter = 0;
    this.maxNodes = options.maxNodes || MAX_TOPOLOGY_LANES * 10;
    this.maxEdges = options.maxEdges || MAX_ROUTING_PATHS;
    this.bounds = options.bounds || rect(0, 0, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT);
    this.geometryMapper = new ProjectionGeometryMapper(this.bounds);
    this.animationState = new SvgAnimationState();
  }

  /** Add or update a node */
  addNode(nodeOrId, options = {}) {
    const id = typeof nodeOrId === 'string' ? nodeOrId : nodeOrId.id;
    const existing = this.nodes.get(id);
    
    const node = existing ? Object.assign(existing, options) : 
      new TopologyNode(id, options);
    
    this.nodes.set(id, node);
    
    // Evict if over limit
    if (this.nodes.size > this.maxNodes) {
      const oldestId = this.nodes.keys().next().value;
      this.nodes.delete(oldestId);
    }
    
    return node;
  }

  /** Remove a node */
  removeNode(id) {
    this.nodes.delete(id);
    // Also remove edges connected to this node
    for (const [edgeId, edge] of this.edges) {
      if (edge.sourceId === id || edge.targetId === id) {
        this.edges.delete(edgeId);
      }
    }
  }

  /** Add or update an edge */
  addEdge(edgeOrId, options = {}) {
    const id = typeof edgeOrId === 'string' ? edgeOrId : edgeOrId.id;
    const existing = this.edges.get(id);
    
    const edge = existing ? Object.assign(existing, options) : 
      new TopologyEdge(id, options);
    
    this.edges.set(id, edge);
    
    if (this.edges.size > this.maxEdges) {
      const oldestId = this.edges.keys().next().value;
      this.edges.delete(oldestId);
    }
    
    return edge;
  }

  /** Remove an edge */
  removeEdge(id) {
    this.edges.delete(id);
  }

  /** Add a proposal node */
  addProposal(proposal) {
    const id = proposal.id || `prop-${this.sequenceCounter++}`;
    this.proposals.set(id, proposal);
    
    if (this.proposals.size > MAX_PROPOSALS_PER_LANE * MAX_TOPOLOGY_LANES) {
      const oldestId = this.proposals.keys().next().value;
      this.proposals.delete(oldestId);
    }
    
    return id;
  }

  /** Remove a proposal */
  removeProposal(id) {
    this.proposals.delete(id);
  }

  /** Add integrity marker */
  addIntegrityMarker(marker) {
    const id = marker.id || `integrity-${this.sequenceCounter++}`;
    this.integrityMarkers.set(id, marker);
    
    if (this.integrityMarkers.size > MAX_INTEGRITY_MARKERS) {
      const oldestId = this.integrityMarkers.keys().next().value;
      this.integrityMarkers.delete(oldestId);
    }
    
    return id;
  }

  /** Remove integrity marker */
  removeIntegrityMarker(id) {
    this.integrityMarkers.delete(id);
  }

  /** Update global state */
  setGlobalState(state) {
    this.globalState = state;
  }

  /** Set replay state */
  setReplayState(state) {
    this.replayState = state;
  }

  /** Get node by ID */
  getNode(id) {
    return this.nodes.get(id);
  }

  /** Get edge by ID */
  getEdge(id) {
    return this.edges.get(id);
  }

  /** Get all nodes */
  getAllNodes() {
    return Array.from(this.nodes.values());
  }

  /** Get all edges */
  getAllEdges() {
    return Array.from(this.edges.values());
  }

  /** Get all proposals */
  getAllProposals() {
    return Array.from(this.proposals.values());
  }

  /** Get all integrity markers */
  getAllIntegrityMarkers() {
    return Array.from(this.integrityMarkers.values());
  }

  /** Clear all state */
  clear() {
    this.nodes.clear();
    this.edges.clear();
    this.proposals.clear();
    this.integrityMarkers.clear();
    this.replayState = null;
    this.globalState = RuntimeInstrumentationState.IDLE;
    this.sequenceCounter = 0;
  }

  /** Update from projection data */
  updateFromProjection(projection) {
    if (!projection) return;

    // Update global state
    if (projection.globalState) {
      this.setGlobalState(projection.globalState);
    }

    // Update nodes from projection
    if (projection.nodes) {
      for (const nodeData of projection.nodes) {
        this.addNode(nodeData.id, nodeData);
      }
    }

    // Update edges from projection
    if (projection.edges) {
      for (const edgeData of projection.edges) {
        this.addEdge(edgeData.id, edgeData);
      }
    }

    // Update proposals from projection
    if (projection.proposals) {
      for (const proposalData of projection.proposals) {
        this.addProposal(proposalData);
      }
    }

    // Update integrity markers
    if (projection.integrityWarnings) {
      for (const warning of projection.integrityWarnings) {
        this.addIntegrityMarker(warning);
      }
    }

    // Update replay state
    if (projection.replayState) {
      this.setReplayState(projection.replayState);
    }

    // Update animation state
    if (projection.animationHint) {
      this.animationState.deriveFromProjection(projection);
    }
  }

  /** Derive animation state */
  getAnimationState() {
    return this.animationState;
  }

  /** Get nodes filtered by kind */
  getNodesByKind(kind) {
    return Array.from(this.nodes.values()).filter(n => n.kind === kind);
  }

  /** Get nodes by state */
  getNodesByState(state) {
    return Array.from(this.nodes.values()).filter(n => n.state === state);
  }

  /** Get selected runtime node */
  getSelectedRuntime() {
    return Array.from(this.nodes.values()).find(n => n.kind === 'runtime' && n.selected);
  }
}

// ============================================================================= 
// Runtime Topology Panel Widget
// =============================================================================

/** Main widget for rendering runtime topology visualization */
export function renderRuntimeTopologyPanel(id, data, context) {
  const container = document.createElement('div');
  container.className = 'widget runtime-topology-panel';
  container.id = id || 'runtime-topology-panel';
  container.setAttribute('role', 'region');
  container.setAttribute('aria-label', 'Runtime Topology');

  // Initialize topology state
  const topologyState = new RuntimeTopologyState({
    bounds: rect(0, 0, data.width || 800, data.height || 600)
  });

  // Update from data if provided
  if (data.projection) {
    topologyState.updateFromProjection(data.projection);
  }

  // Update from data nodes/edges directly
  if (data.nodes) {
    for (const nodeData of data.nodes) {
      topologyState.addNode(nodeData);
    }
  }
  if (data.edges) {
    for (const edgeData of data.edges) {
      topologyState.addEdge(edgeData);
    }
  }
  if (data.proposals) {
    for (const proposalData of data.proposals) {
      topologyState.addProposal(proposalData);
    }
  }
  if (data.globalState) {
    topologyState.setGlobalState(data.globalState);
  }

  // Create header
  const header = _createPanelHeader(
    data.title || 'Runtime Topology',
    normalizeRuntimeEventEnvelope(data.runtime_event || data.event_envelope),
    normalizeOperationalStatusEnvelope(data.condition || data.status || data.overall_status || data.runtime_status),
    data
  );
  container.appendChild(header);

  // Create SVG container
  const svgContainer = document.createElement('div');
  svgContainer.className = 'runtime-topology-svg-container';
  svgContainer.style.width = '100%';
  svgContainer.style.height = (data.height || 600) + 'px';
  svgContainer.style.position = 'relative';
  container.appendChild(svgContainer);

  // Create instrumentation layer
  const instrumentationLayer = new SvgInstrumentationLayer(svgContainer, {
    id: 'topology-layer',
    bounds: rect(0, 0, data.width || 800, data.height || 600)
  });

  // Render topology
  _renderTopology(topologyState, instrumentationLayer, data);

  // Store state on container for updates
  container._topologyState = topologyState;
  container._instrumentationLayer = instrumentationLayer;

  // Expose update method
  container.update = (newData) => {
    if (newData.projection) {
      topologyState.updateFromProjection(newData.projection);
    }
    if (newData.nodes) {
      for (const nodeData of newData.nodes) {
        topologyState.addNode(nodeData);
      }
    }
    if (newData.edges) {
      for (const edgeData of newData.edges) {
        topologyState.addEdge(edgeData);
      }
    }
    if (newData.proposals) {
      for (const proposalData of newData.proposals) {
        topologyState.addProposal(proposalData);
      }
    }
    if (newData.globalState) {
      topologyState.setGlobalState(newData.globalState);
    }
    
    // Re-render
    instrumentationLayer.clear();
    _renderTopology(topologyState, instrumentationLayer, newData);
  };

  // Expose state accessor
  container.getState = () => topologyState;

  return container;
}

// =============================================================================
// Rendering Functions
// =============================================================================

/** Create panel header */
function _createPanelHeader(title, runtimeEnvelope = null, operationalStatus = null, lineage = null) {
  const header = document.createElement('div');
  header.className = 'widget-header topology-header';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.padding = '12px 16px';
  header.style.borderBottom = '1px solid var(--color-border, #424242)';
  header.style.backgroundColor = 'var(--color-background-secondary, #252526)';

  const titleEl = document.createElement('h2');
  titleEl.className = 'widget-title';
  titleEl.textContent = title;
  titleEl.style.margin = '0';
  titleEl.style.fontSize = '14px';
  titleEl.style.fontWeight = '600';
  titleEl.style.color = 'var(--color-foreground, #E0E0E0)';
  header.appendChild(titleEl);

  if (runtimeEnvelope) {
    const eventBadge = document.createElement('div');
    eventBadge.className = 'badge severity-info';
    eventBadge.textContent = `${runtimeEnvelope.event_family} · ${runtimeEnvelope.event_type}`;
    header.appendChild(eventBadge);
  }

  if (lineage && (lineage.schema_version || lineage.projection_revision !== undefined)) {
    const lineageEl = document.createElement('div');
    lineageEl.className = 'topology-lineage';
    lineageEl.style.fontSize = '12px';
    lineageEl.style.color = 'var(--color-text-muted, #888)';
    lineageEl.textContent = [
      lineage.schema_version ? `schema: ${lineage.schema_version}` : null,
      lineage.projection_revision !== undefined ? `revision: ${lineage.projection_revision}` : null,
    ].filter(Boolean).join(' · ');
    header.appendChild(lineageEl);
  }

  // Status indicator
  const statusEl = document.createElement('div');
  statusEl.className = 'topology-status';
  statusEl.style.fontSize = '12px';
  statusEl.style.color = 'var(--color-text-muted, #888)';
  statusEl.textContent = operationalStatus
    ? `${operationalStatus.label || operationalStatus.value || 'unknown'} · ${operationalStatus.severity || 'info'}`
    : 'Initializing...';
  header.appendChild(statusEl);

  return header;
}

/** Render complete topology */
function _renderTopology(topologyState, layer, data = {}) {
  const bounds = layer.bounds || rect(0, 0, 800, 600);
  const geometryMapper = topologyState.geometryMapper;
  
  // Update mapper bounds if needed
  if (bounds.width !== geometryMapper.bounds.width || 
      bounds.height !== geometryMapper.bounds.height) {
    geometryMapper.bounds = rect(0, 0, bounds.width, bounds.height);
  }

  // Render lanes first (background)
  _renderLanes(topologyState, layer, bounds);

  // Render routing paths
  _renderRoutingPaths(topologyState, layer, bounds);

  // Render topology connectors (edges)
  _renderConnectors(topologyState, layer, bounds);

  // Render nodes
  _renderNodes(topologyState, layer, bounds);

  // Render proposals
  _renderProposals(topologyState, layer, bounds);

  // Render integrity markers
  _renderIntegrityMarkers(topologyState, layer, bounds);

  // Render replay sweep if active
  if (topologyState.replayState) {
    _renderReplaySweep(topologyState, layer, bounds);
  }

  // Render stream density lines
  _renderStreamDensity(topologyState, layer, bounds);

  // Render throughput bars
  _renderThroughputBars(topologyState, layer, bounds);
}

/** Render execution lanes */
function _renderLanes(topologyState, layer, bounds) {
  const geometryMapper = topologyState.geometryMapper;
  const nodeCount = topologyState.getAllNodes().length;
  const densityState = MotionUtils.calculateDensityCollapse(nodeCount, Math.max(1, Math.ceil(nodeCount / 5)), topologyState.getAllIntegrityMarkers().length);
  const laneCount = Math.min(MAX_TOPOLOGY_LANES, Math.ceil(nodeCount / 5));
  
  // Create lanes
  for (let i = 0; i < laneCount; i++) {
    const laneBounds = geometryMapper.laneToBounds(i);
    
    // Determine lane state based on nodes in this lane
    const laneNodes = topologyState.getAllNodes().filter(n => {
      const laneY = geometryMapper.laneToY(i);
      return Math.abs(n.y - laneY) < LANE_HEIGHT;
    });
    
    const states = laneNodes.map(n => n.state);
    const active = laneNodes.some(n => n.connected || n.state === 'streaming' || n.state === 'executing');
    const stalled = laneNodes.some(n => n.state === 'stalled' || n.violationCount > 0);
    const completed = laneNodes.every(n => n.state === 'complete' || n.state === 'completed');
    
    // Calculate throughput for lane
    const throughput = laneNodes.reduce((sum, n) => sum + (n.lastActivity || 0), 0);
    const maxThroughput = 1000; // TODO: derive from actual data

    const lane = new SvgExecutionLane(`lane-${i}`, laneBounds, {
      id: `lane-${i}`,
      label: `Lane ${i + 1}`,
      state: active ? (stalled ? 'stalled' : states[0] || 'active') : 'idle',
      active,
      stalled,
      completed,
      throughput: densityState.shouldCollapse ? Math.min(throughput, 500) : throughput,
      maxThroughput,
      index: i
    });
    
    layer.addPrimitive(lane);
  }
}

/** Render routing paths */
function _renderRoutingPaths(topologyState, layer, bounds) {
  const edges = topologyState.getAllEdges();
  const geometryMapper = topologyState.geometryMapper;

  for (const edge of edges) {
    const sourceNode = topologyState.getNode(edge.sourceId);
    const targetNode = topologyState.getNode(edge.targetId);

    if (!sourceNode || !targetNode) continue;

    const sourcePoint = point(sourceNode.x + sourceNode.width / 2, sourceNode.y + sourceNode.height / 2);
    const targetPoint = point(targetNode.x + targetNode.width / 2, targetNode.y + targetNode.height / 2);

    const path = new SvgRoutingPath(edge.id, [sourcePoint, targetPoint], {
      capability: edge.capability,
      state: edge.state,
      active: edge.active,
      thickness: edge.active ? STROKE_WIDTH_THICK : STROKE_WIDTH_NORMAL
    });

    layer.addPrimitive(path);
  }
}

/** Render topology connectors (edges as connectors) */
function _renderConnectors(topologyState, layer, bounds) {
  const edges = topologyState.getAllEdges();
  const nodes = topologyState.getAllNodes();
  const geometryMapper = topologyState.geometryMapper;

  for (const edge of edges) {
    const sourceNode = topologyState.getNode(edge.sourceId);
    const targetNode = topologyState.getNode(edge.targetId);

    if (!sourceNode || !targetNode) continue;

    const connector = new SvgTopologyConnector(edge.id, sourceNode, targetNode, {
      state: edge.state,
      kind: edge.kind,
      thickness: edge.active ? 2 : 1.5,
      inactive: !edge.active,
      sequence: edge.sequence
    });

    layer.addPrimitive(connector);
  }
}

/** Render topology nodes */
function _renderNodes(topologyState, layer, bounds) {
  const nodes = topologyState.getAllNodes();
  const geometryMapper = topologyState.geometryMapper;

  for (const node of nodes) {
    // Map node position based on kind
    let x = node.x;
    let y = node.y;

    if (!x && !y) {
      // Auto-position nodes
      const runtimeNodes = topologyState.getNodesByKind('runtime');
      const index = nodes.indexOf(node);
      const laneIndex = Math.floor(index / 5);
      const laneY = geometryMapper.laneToY(laneIndex);
      const nodeX = geometryMapper.padding + (index % 5) * 150;
      x = nodeX;
      y = laneY + LANE_HEIGHT / 2 - node.height / 2;
    }

    // Create node visualization
    const nodeWidth = node.width || 100;
    const nodeHeight = node.height || 40;
    
    const nodeBounds = rect(x, y, nodeWidth, nodeHeight);
    
    // Create a simple rectangle node for now
    // (Full node rendering would use more specific shapes)
    const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodeGroup.setAttribute('id', `topology-node-${node.id}`);
    nodeGroup.setAttribute('class', `topology-node kind-${node.kind} state-${node.state}`);
    nodeGroup.setAttribute('data-node-id', node.id);
    nodeGroup.setAttribute('data-kind', node.kind);
    nodeGroup.setAttribute('data-state', node.state);

    // Node background
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('x', x);
    bg.setAttribute('y', y);
    bg.setAttribute('width', nodeWidth);
    bg.setAttribute('height', nodeHeight);
    bg.setAttribute('rx', '4');
    bg.setAttribute('ry', '4');
    bg.setAttribute('fill', _getNodeFillColor(node));
    bg.setAttribute('stroke', _getNodeStrokeColor(node));
    bg.setAttribute('stroke-width', '1');
    nodeGroup.appendChild(bg);

    // Node label
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x + nodeWidth / 2);
    label.setAttribute('y', y + nodeHeight / 2 + 4);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('dominant-baseline', 'middle');
    label.setAttribute('fill', '#fff');
    label.setAttribute('font-size', '11');
    label.setAttribute('font-family', 'system-ui, sans-serif');
    label.textContent = node.label || node.id;
    nodeGroup.appendChild(label);

    // Selection indicator
    if (node.selected) {
      const selectionRing = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      selectionRing.setAttribute('x', x - 2);
      selectionRing.setAttribute('y', y - 2);
      selectionRing.setAttribute('width', nodeWidth + 4);
      selectionRing.setAttribute('height', nodeHeight + 4);
      selectionRing.setAttribute('rx', '6');
      selectionRing.setAttribute('ry', '6');
      selectionRing.setAttribute('fill', 'none');
      selectionRing.setAttribute('stroke', '#2196F3');
      selectionRing.setAttribute('stroke-width', '2');
      nodeGroup.insertBefore(selectionRing, nodeGroup.firstChild);
    }

    // Violation count badge
    if (node.violationCount > 0) {
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      badge.setAttribute('cx', x + nodeWidth + 6);
      badge.setAttribute('cy', y + 6);
      badge.setAttribute('r', 8);
      badge.setAttribute('fill', '#F44336');
      nodeGroup.appendChild(badge);

      const badgeLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      badgeLabel.setAttribute('x', x + nodeWidth + 6);
      badgeLabel.setAttribute('y', y + 8);
      badgeLabel.setAttribute('text-anchor', 'middle');
      badgeLabel.setAttribute('dominant-baseline', 'middle');
      badgeLabel.setAttribute('fill', '#fff');
      badgeLabel.setAttribute('font-size', '9');
      badgeLabel.textContent = String(node.violationCount);
      nodeGroup.appendChild(badgeLabel);
    }

    layer.svg.appendChild(nodeGroup);
    layer.elements.set(`node-${node.id}`, { 
      primitive: node, 
      element: nodeGroup 
    });
  }
}

/** Get fill color for a topology node */
function _getNodeFillColor(node) {
  const colors = {
    'runtime': '#607D8B',
    'capability': '#9C27B0',
    'sandbox': '#795548',
    'executor': '#4CAF50',
    'validator': '#FF9800',
    'supervisor': '#F44336',
    'registry': '#00BCD4'
  };
  return colors[node.kind] || '#607D8B';
}

/** Get stroke color for a topology node */
function _getNodeStrokeColor(node) {
  if (node.selected) return '#2196F3';
  if (node.violationCount > 0) return '#F44336';
  if (node.connected) return '#4CAF50';
  return '#616161';
}

/** Render proposals */
function _renderProposals(topologyState, layer, bounds) {
  const proposals = topologyState.getAllProposals();
  const geometryMapper = topologyState.geometryMapper;

  for (const proposal of proposals) {
    // Position proposal based on sequence
    const laneIndex = proposal.sequence % MAX_TOPOLOGY_LANES;
    const laneY = geometryMapper.laneToY(laneIndex);
    const x = geometryMapper.sequenceToX(proposal.sequence, 100);
    const y = laneY + LANE_HEIGHT / 2;

    const proposalNode = new SvgProposalNode(proposal.id || `prop-${proposal.sequence}`, point(x, y), {
      state: proposal.state || 'pending',
      kind: proposal.kind || 'tool',
      label: proposal.label || `Proposal ${proposal.sequence}`,
      sequence: proposal.sequence || 0,
      capability: proposal.capability || 'default',
      acknowledged: proposal.acknowledged || false,
      ignored: proposal.ignored || false
    });

    layer.addPrimitive(proposalNode);
  }
}

/** Render integrity markers */
function _renderIntegrityMarkers(topologyState, layer, bounds) {
  const markers = topologyState.getAllIntegrityMarkers();
  const geometryMapper = topologyState.geometryMapper;

  for (const marker of markers) {
    const markerPoint = geometryMapper.getIntegrityPosition(
      marker,
      marker.sequence % MAX_TOPOLOGY_LANES,
      marker.sequence
    );

    const integrityMarker = new SvgIntegrityMarker(marker.id || `int-${marker.sequence}`, markerPoint, {
      state: marker.state || 'warning',
      code: marker.code || 'UNKNOWN',
      severity: marker.severity || 'warning',
      message: marker.message || '',
      sequence: marker.sequence || 0,
      size: 14
    });

    layer.addPrimitive(integrityMarker);
  }
}

/** Render replay sweep */
function _renderReplaySweep(topologyState, layer, bounds) {
  const sweepBounds = rect(
    bounds.width - 100,
    bounds.height - 100,
    80,
    80
  );

  const progress = topologyState.replayState.progress || 0;
  const sequence = topologyState.replayState.sequence || 0;
  const total = topologyState.replayState.totalSequences || 100;
  const isReconstructed = topologyState.replayState.isReconstructed || false;

  const sweep = new SvgReplaySweep('replay-main', sweepBounds, {
    progress,
    sequence,
    totalSequences: total,
    isReconstructed
  });

  layer.addPrimitive(sweep);
}

/** Render stream density lines */
function _renderStreamDensity(topologyState, layer, bounds) {
  const edges = topologyState.getAllEdges().filter(e => e.kind === 'stream');
  const geometryMapper = topologyState.geometryMapper;
  const densityState = MotionUtils.calculateDensityCollapse(topologyState.getAllNodes().length, Math.max(1, topologyState.lanes.size || 1), topologyState.getAllIntegrityMarkers().length);

  for (const edge of edges) {
    const sourceNode = topologyState.getNode(edge.sourceId);
    const targetNode = topologyState.getNode(edge.targetId);

    if (!sourceNode || !targetNode) continue;

    const sourceX = sourceNode.x + sourceNode.width / 2;
    const sourceY = sourceNode.y + sourceNode.height / 2;
    const targetX = targetNode.x + targetNode.width / 2;
    const targetY = targetNode.y + targetNode.height / 2;

    const points = [
      point(sourceX, sourceY),
      point((sourceX + targetX) / 2, sourceY),
      point((sourceX + targetX) / 2, targetY),
      point(targetX, targetY)
    ];

    const intensity = densityState.shouldCollapse ? 0.45 : edge.active ? 1.0 : 0.5;

    const densityLine = new SvgStreamDensityLine(`density-${edge.id}`, points, {
      intensity,
      channel: edge.kind || 'assistant',
      state: edge.state,
      sequenceStart: edge.sequence,
      sequenceEnd: edge.sequence + (edge.bytesTransferred / 1000),
      bytesTotal: edge.bytesTransferred,
      tokensTotal: edge.tokensTransferred
    });

    layer.addPrimitive(densityLine);
  }
}

/** Render throughput bars */
function _renderThroughputBars(topologyState, layer, bounds) {
  const nodes = topologyState.getAllNodes().filter(n => n.kind === 'runtime');
  const geometryMapper = topologyState.geometryMapper;
  const padding = 16;
  if (nodes.length === 0) return;
  const barWidth = (bounds.width - padding * 2) / nodes.length - 8;

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const x = padding + i * (barWidth + 8);
    const barBounds = rect(x, bounds.height - 40, barWidth, 20);

    const throughputBar = new SvgThroughputBar(`throughput-${node.id}`, barBounds, {
      value: node.lastActivity || 0,
      maxValue: 1000,
      label: node.label || node.id,
      state: node.state,
      channel: 'assistant'
    });

    layer.addPrimitive(throughputBar);
  }
}

// =============================================================================
// Module Exports
// =============================================================================

export {
  _createPanelHeader as createTopologyHeader,
  _renderTopology as renderTopology
};
