/**
 * ADR 0011: Progressive Cognitive Disclosure Controller
 * 
 * Doctrine:
 * - Manage information density across Layers 1-4.
 * - Enable users to gracefully unfold system complexity.
 * - Provide semantic transitions between layers.
 */

const LAYERS = {
  HEALTH: 1,    // Intent, Progress, Health
  TOPOLOGY: 2,  // 1 + Execution Lanes & Runtime Topology
  TRACE: 3,     // 2 + Governance, Audits, Streams
  DEBUG: 4      // 3 + Replay, Internals, Telemetry
};

const WIDGET_LAYER_MAP = {
  // Layer 1: Intent & Health
  WorkspaceHeader: LAYERS.HEALTH,
  BackendStatus: LAYERS.HEALTH,
  WorkspaceGitState: LAYERS.HEALTH,
  IntegrityStatusCard: LAYERS.HEALTH,
  CommandProgressCard: LAYERS.HEALTH,
  EmptyStateCard: LAYERS.HEALTH,
  AppTitle: LAYERS.HEALTH,
  GateBadge: LAYERS.HEALTH,

  // Layer 2: Topology & Lanes
  WorkspaceLaneSummary: LAYERS.TOPOLOGY,
  RuntimeTopologyPanel: LAYERS.TOPOLOGY,
  ValidatorStack: LAYERS.TOPOLOGY,
  ProposalLifecycleConsole: LAYERS.TOPOLOGY,

  // Layer 3: Trace & Governance
  AuditTrailCard: LAYERS.TRACE,
  ReceiptList: LAYERS.TRACE,
  FundingSummaryCard: LAYERS.TRACE,
  LogStream: LAYERS.TRACE,

  // Layer 4: Debug & Replay
  ReplayTimelineCard: LAYERS.DEBUG,
  DebugPanel: LAYERS.DEBUG,
  EvidenceCard: LAYERS.DEBUG,
  MetricStack: LAYERS.DEBUG
};

let currentLayer = LAYERS.TOPOLOGY; // Default to Topology for now

export function setCognitiveLayer(layer) {
  if (typeof layer === 'string') {
    currentLayer = LAYERS[layer.toUpperCase()] || currentLayer;
  } else {
    currentLayer = layer;
  }
  document.body.setAttribute('data-cognitive-layer', currentLayer);
  
  // Update UI indicators
  document.querySelectorAll('.layer-toggle').forEach(el => {
    el.classList.toggle('active', parseInt(el.getAttribute('data-layer')) === currentLayer);
  });
}

export function getCognitiveLayer() {
  return currentLayer;
}

export function shouldShowWidget(widgetType) {
  const layer = WIDGET_LAYER_MAP[widgetType] || LAYERS.HEALTH;
  return layer <= currentLayer;
}

/**
 * Initialize the Layer Controller UI
 */
export function initLayerController(parent) {
  const container = document.createElement('div');
  container.className = 'layer-controller';
  container.style.display = 'flex';
  container.style.gap = 'var(--s-2)';
  container.style.alignItems = 'center';

  const label = document.createElement('span');
  label.textContent = 'Cognition:';
  label.style.fontSize = 'var(--fs-xs)';
  label.style.color = 'var(--color-text-dim)';
  container.appendChild(label);

  const layerNames = ['Health', 'Topology', 'Trace', 'Debug'];
  layerNames.forEach((name, index) => {
    const btn = document.createElement('button');
    const layerLevel = index + 1;
    btn.className = 'layer-toggle btn-subtle';
    if (layerLevel === currentLayer) btn.classList.add('active');
    btn.setAttribute('data-layer', layerLevel);
    btn.textContent = name;
    btn.onclick = () => setCognitiveLayer(layerLevel);
    container.appendChild(btn);
  });

  parent.appendChild(container);
  
  // Set initial attribute
  document.body.setAttribute('data-cognitive-layer', currentLayer);
}
